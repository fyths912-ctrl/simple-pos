import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.core.deps import current_cashier
from app.core.errors import AppError
from app.db.session import get_db
from app.models.schemas import PRODUCT_CODE_PATTERN, ProductOut
from app.repositories import product_repository

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[Depends(current_cashier)])
_CODE = re.compile(PRODUCT_CODE_PATTERN)


@router.get("/{product_code}", response_model=ProductOut)
def get_product(product_code: str, db: DbSession = Depends(get_db)):
    code = product_code.strip()  # 前後の空白は除去してから検証・検索（T-019）
    if not _CODE.fullmatch(code):
        raise AppError(422, "VALIDATION_ERROR", "商品コードは13桁の数字で入力してください")
    product = product_repository.get_active(db, code)
    if product is None:  # 未登録・無効化は同じ扱い（T-020）
        raise AppError(404, "PRODUCT_NOT_FOUND", "商品がマスタ未登録です。商品コードを確認してください。")
    return ProductOut(product_code=product.product_code, product_name=product.product_name, unit_price=product.unit_price)
