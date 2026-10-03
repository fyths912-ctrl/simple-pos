"""初期スキーマ（設計仕様書 v1.1 6.2/6.3）

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

_TS = dict(nullable=False, server_default=sa.func.now())
_TABLE_OPTS = dict(mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_bin")


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("product_code", sa.String(13), primary_key=True, comment="商品コード（13桁）"),
        sa.Column("product_name", sa.String(100), nullable=False, comment="商品名称"),
        sa.Column("unit_price", sa.Integer, nullable=False, comment="単価（税抜・円）"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, **_TS),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
        sa.CheckConstraint("unit_price >= 0", name="ck_products_unit_price"),
        comment="商品マスタ", **_TABLE_OPTS,
    )
    op.create_table(
        "members",
        sa.Column("member_id", sa.String(7), primary_key=True, comment="会員ID（M+6桁）"),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("address", sa.String(255)),
        sa.Column("gender", sa.String(10)),
        sa.Column("age", sa.SmallInteger),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true(), comment="退会は論理削除"),
        sa.Column("created_at", sa.DateTime, **_TS),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
        comment="会員", **_TABLE_OPTS,
    )
    op.create_table(
        "cashiers",
        sa.Column("cashier_id", sa.String(20), primary_key=True),
        sa.Column("cashier_name", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False, comment="Argon2id"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("failed_login_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime, comment="ログイン失敗ロック期限（UTC）"),
        sa.Column("created_at", sa.DateTime, **_TS),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
        comment="レジ担当者", **_TABLE_OPTS,
    )
    op.create_table(
        "sessions",
        sa.Column("session_id_hash", sa.String(64), primary_key=True, comment="セッションIDのSHA-256"),
        sa.Column("cashier_id", sa.String(20), sa.ForeignKey("cashiers.cashier_id", name="fk_sessions_cashier"), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False, comment="UTC"),
        sa.Column("created_at", sa.DateTime, nullable=False, comment="UTC"),
        comment="ログインセッション", **_TABLE_OPTS,
    )
    op.create_index("ix_sessions_cashier_id", "sessions", ["cashier_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "tax_rates",
        sa.Column("tax_rate_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sales_mode", sa.String(10), nullable=False, comment="DINE_IN / TAKEOUT"),
        sa.Column("rate", sa.Numeric(5, 4), nullable=False, comment="例: 0.1000"),
        sa.Column("effective_from", sa.Date, nullable=False, comment="適用開始日（JST）"),
        sa.Column("effective_to", sa.Date, comment="適用終了日（JST、NULL=期限なし）"),
        sa.Column("rounding_method", sa.String(10), nullable=False, server_default="FLOOR", comment="FLOOR / HALF_UP / CEIL"),
        sa.Column("created_at", sa.DateTime, **_TS),
        sa.CheckConstraint("sales_mode IN ('DINE_IN','TAKEOUT')", name="ck_tax_rates_sales_mode"),
        sa.CheckConstraint("rounding_method IN ('FLOOR','HALF_UP','CEIL')", name="ck_tax_rates_rounding"),
        sa.CheckConstraint("rate >= 0 AND rate < 1", name="ck_tax_rates_rate"),
        comment="消費税率マスタ（期間管理）", **_TABLE_OPTS,
    )
    op.create_index("ix_tax_rates_mode_from", "tax_rates", ["sales_mode", "effective_from"])

    op.create_table(
        "transactions",
        sa.Column("transaction_id", sa.BigInteger, primary_key=True, autoincrement=True, comment="内部連番"),
        sa.Column("transaction_no", sa.String(32), comment="対外表示用ID（T+日付+連番）"),
        sa.Column("transaction_at", sa.DateTime, nullable=False, comment="取引日時（UTC）"),
        sa.Column("member_id", sa.String(7), sa.ForeignKey("members.member_id", name="fk_transactions_member"), comment="非会員はNULL"),
        sa.Column("cashier_id", sa.String(20), sa.ForeignKey("cashiers.cashier_id", name="fk_transactions_cashier"), nullable=False),
        sa.Column("sales_mode", sa.String(10), nullable=False),
        sa.Column("subtotal_excl_tax", sa.BigInteger, nullable=False),
        sa.Column("tax_amount", sa.BigInteger, nullable=False),
        sa.Column("total_incl_tax", sa.BigInteger, nullable=False),
        sa.Column("idempotency_key", sa.String(36), nullable=False, comment="二重送信対策"),
        sa.Column("created_at", sa.DateTime, **_TS),
        sa.UniqueConstraint("transaction_no", name="uq_transactions_transaction_no"),
        sa.UniqueConstraint("idempotency_key", name="uq_transactions_idempotency_key"),
        sa.CheckConstraint("sales_mode IN ('DINE_IN','TAKEOUT')", name="ck_transactions_sales_mode"),
        comment="取引（ヘッダ）", **_TABLE_OPTS,
    )
    op.create_index("ix_transactions_transaction_at", "transactions", ["transaction_at"])
    op.create_index("ix_transactions_cashier_id", "transactions", ["cashier_id"])
    op.create_index("ix_transactions_member_id", "transactions", ["member_id"])

    op.create_table(
        "transaction_items",
        sa.Column("transaction_item_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("transaction_id", sa.BigInteger, sa.ForeignKey("transactions.transaction_id", name="fk_items_transaction"), nullable=False),
        sa.Column("line_no", sa.SmallInteger, nullable=False),
        sa.Column("product_code", sa.String(13), sa.ForeignKey("products.product_code", name="fk_items_product"), nullable=False),
        sa.Column("product_name_snapshot", sa.String(100), nullable=False),
        sa.Column("unit_price_snapshot", sa.Integer, nullable=False),
        sa.Column("quantity", sa.SmallInteger, nullable=False),
        sa.Column("tax_rate_snapshot", sa.Numeric(5, 4), nullable=False),
        sa.Column("line_subtotal", sa.BigInteger, nullable=False),
        sa.Column("line_tax", sa.BigInteger, nullable=False),
        sa.Column("line_total", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("transaction_id", "line_no", name="uq_items_transaction_line"),
        sa.CheckConstraint("quantity >= 1", name="ck_transaction_items_quantity"),
        comment="取引明細（確定時スナップショット）", **_TABLE_OPTS,
    )
    op.create_index("ix_transaction_items_transaction_id", "transaction_items", ["transaction_id"])


def downgrade() -> None:
    for table in ("transaction_items", "transactions", "tax_rates", "sessions", "cashiers", "members", "products"):
        op.drop_table(table)
