"""購入確定（設計8.6/11.3、F-003、NF-002）。

クライアントから受け取るのは 商品コード・数量・会員ID・取引区分・冪等性キー のみ。
単価・税率・合計はすべて DB から取り直してサーバー側で計算する（T-034）。
"""
import logging
import time
from collections import OrderedDict

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session as DbSession

from app.config import Settings
from app.core import clock
from app.core.errors import AppError
from app.models.db_models import Transaction, TransactionItem
from app.models.schemas import TransactionCreate, TransactionResult
from app.repositories import member_repository, product_repository
from app.repositories import transaction_repository as repo
from app.services import tax_service

purchase_log = logging.getLogger("pos.purchase")

SAVE_FAILED = ("TRANSACTION_SAVE_FAILED", "購入を確定できませんでした。再度お試しください。")


def to_result(t: Transaction) -> TransactionResult:
    return TransactionResult(
        transaction_id=t.transaction_no or str(t.transaction_id),
        subtotal_excl_tax=t.subtotal_excl_tax,
        tax_amount=t.tax_amount,
        total_incl_tax=t.total_incl_tax,
        transaction_at=clock.to_jst(t.transaction_at).isoformat(),
    )


def make_transaction_no(t: Transaction) -> str:
    """対外表示用ID：T + JST日付(YYYYMMDD) + 内部連番(6桁以上)。内部連番が一意なので重複しない（T-073）。"""
    return f"T{clock.to_jst(t.transaction_at):%Y%m%d}{t.transaction_id:06d}"


def _merge_items(req: TransactionCreate, settings: Settings) -> "OrderedDict[str, int]":
    merged: OrderedDict[str, int] = OrderedDict()
    for item in req.items:
        merged[item.product_code] = merged.get(item.product_code, 0) + item.quantity
    if any(q > settings.max_quantity_per_item for q in merged.values()):
        raise AppError(422, "VALIDATION_ERROR", f"数量は1〜{settings.max_quantity_per_item}で指定してください")
    if len(merged) > settings.max_cart_lines:
        raise AppError(422, "VALIDATION_ERROR", f"購入リストは{settings.max_cart_lines}行までです")
    return merged


def create_transaction(db: DbSession, settings: Settings, cashier_id: str, req: TransactionCreate) -> TransactionResult:
    started = time.perf_counter()

    # 1) 冪等性チェック：同じキーの取引があれば保存せずにその結果を返す（T-035/T-038）
    existing = repo.find_by_idempotency_key(db, req.idempotency_key)
    if existing is not None:
        _log(existing.transaction_no, cashier_id, "idempotent_replay", started)
        return to_result(existing)

    # 2) 入力確認
    if not req.items:
        raise AppError(400, "EMPTY_CART", "商品を1件以上追加してください。")
    merged = _merge_items(req, settings)

    if req.member_id is not None and member_repository.get_active(db, req.member_id) is None:
        raise AppError(404, "MEMBER_NOT_FOUND", "会員IDが見つかりません。再入力するか、非会員を選択してください。")

    # 3) マスタ再取得
    products = product_repository.get_active_many(db, list(merged.keys()))
    if len(products) != len(merged):
        raise AppError(
            409, "PRODUCT_CHANGED_OR_NOT_FOUND",
            "購入リストに販売できない商品が含まれています。商品を確認してください。",
        )

    now = clock.utcnow()
    tax_rate = tax_service.get_effective_rate(db, req.sales_mode, clock.business_date(now))

    # 4) 金額計算
    line_subtotals = [products[code].unit_price * qty for code, qty in merged.items()]
    breakdown = tax_service.calculate(line_subtotals, tax_rate.rate, tax_rate.rounding_method)

    # 5) 取引ヘッダ＋明細を1トランザクションで保存
    try:
        header = repo.insert_header(db, Transaction(
            transaction_at=now,
            member_id=req.member_id,
            cashier_id=cashier_id,
            sales_mode=req.sales_mode,
            subtotal_excl_tax=breakdown.subtotal_excl_tax,
            tax_amount=breakdown.tax_amount,
            total_incl_tax=breakdown.total_incl_tax,
            idempotency_key=req.idempotency_key,
        ))
        header.transaction_no = make_transaction_no(header)
        items = []
        for line_no, ((code, qty), sub, tax) in enumerate(zip(merged.items(), line_subtotals, breakdown.line_taxes), 1):
            p = products[code]
            items.append(TransactionItem(
                transaction_id=header.transaction_id, line_no=line_no, product_code=code,
                product_name_snapshot=p.product_name, unit_price_snapshot=p.unit_price, quantity=qty,
                tax_rate_snapshot=tax_rate.rate, line_subtotal=sub, line_tax=tax, line_total=sub + tax,
            ))
        repo.insert_items(db, items)
        db.commit()
    except IntegrityError:
        db.rollback()
        # 同じキーの並行リクエストが先に COMMIT した場合はその結果を返す
        winner = repo.find_by_idempotency_key(db, req.idempotency_key)
        if winner is not None:
            _log(winner.transaction_no, cashier_id, "idempotent_replay", started)
            return to_result(winner)
        _log(None, cashier_id, "save_failed", started, exc_info=True)
        raise AppError(500, *SAVE_FAILED)
    except SQLAlchemyError:
        db.rollback()
        _log(None, cashier_id, "save_failed", started, exc_info=True)
        raise AppError(500, *SAVE_FAILED)

    # 6) COMMIT 成功後のみ結果を返す
    _log(header.transaction_no, cashier_id, "success", started)
    return to_result(header)


def _log(transaction_no: str | None, cashier_id: str, result: str, started: float, exc_info: bool = False) -> None:
    purchase_log.log(
        logging.ERROR if result == "save_failed" else logging.INFO,
        "purchase",
        extra={
            "transaction_id": transaction_no, "cashier_id": cashier_id, "result": result,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
        exc_info=exc_info,
    )
