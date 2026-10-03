"""テーブル定義（設計6.2/6.3）。マイグレーションは alembic/versions を正とする。

- 金額は円単位の整数（浮動小数点を使わない）
- 税率は DECIMAL(5,4)
- 日時は UTC の DATETIME
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric,
    SmallInteger, String, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SALES_MODES = ("DINE_IN", "TAKEOUT")
ROUNDING_METHODS = ("FLOOR", "HALF_UP", "CEIL")


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    product_code: Mapped[str] = mapped_column(String(13), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)  # 税抜単価（暫定：設計14章 No.2）
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (CheckConstraint("unit_price >= 0", name="ck_products_unit_price"),)


class Member(Base):
    __tablename__ = "members"
    member_id: Mapped[str] = mapped_column(String(7), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(String(255))
    gender: Mapped[str | None] = mapped_column(String(10))
    age: Mapped[int | None] = mapped_column(SmallInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class Cashier(Base):
    __tablename__ = "cashiers"
    cashier_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    cashier_name: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)  # Argon2id
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 連続ログイン失敗ロック用（設計9.2「一時ロック」の実装に必要なため追加）
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class Session(Base):
    __tablename__ = "sessions"
    session_id_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    cashier_id: Mapped[str] = mapped_column(ForeignKey("cashiers.cashier_id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cashier: Mapped[Cashier] = relationship()
    __table_args__ = (
        Index("ix_sessions_cashier_id", "cashier_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )


class TaxRate(Base):
    __tablename__ = "tax_rates"
    tax_rate_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sales_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    rounding_method: Mapped[str] = mapped_column(String(10), nullable=False, default="FLOOR")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    __table_args__ = (
        CheckConstraint("sales_mode IN ('DINE_IN','TAKEOUT')", name="ck_tax_rates_sales_mode"),
        CheckConstraint("rounding_method IN ('FLOOR','HALF_UP','CEIL')", name="ck_tax_rates_rounding"),
        CheckConstraint("rate >= 0 AND rate < 1", name="ck_tax_rates_rate"),
        Index("ix_tax_rates_mode_from", "sales_mode", "effective_from"),
    )


class Transaction(Base):
    __tablename__ = "transactions"
    transaction_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 対外表示用ID（"T" + JST日付 + 内部連番6桁）。採番は取引INSERT直後に同一トランザクション内で行う
    transaction_no: Mapped[str | None] = mapped_column(String(32), unique=True)
    transaction_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    member_id: Mapped[str | None] = mapped_column(ForeignKey("members.member_id"))
    cashier_id: Mapped[str] = mapped_column(ForeignKey("cashiers.cashier_id"), nullable=False)
    sales_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    subtotal_excl_tax: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_incl_tax: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    items: Mapped[list["TransactionItem"]] = relationship(back_populates="transaction", order_by="TransactionItem.line_no")
    __table_args__ = (
        CheckConstraint("sales_mode IN ('DINE_IN','TAKEOUT')", name="ck_transactions_sales_mode"),
        Index("ix_transactions_transaction_at", "transaction_at"),
        Index("ix_transactions_cashier_id", "cashier_id"),
        Index("ix_transactions_member_id", "member_id"),
    )


class TransactionItem(Base):
    __tablename__ = "transaction_items"
    transaction_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.transaction_id"), nullable=False)
    line_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.product_code"), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    unit_price_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tax_rate_snapshot: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    line_subtotal: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_tax: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transaction: Mapped[Transaction] = relationship(back_populates="items")
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_transaction_items_quantity"),
        Index("ix_transaction_items_transaction_id", "transaction_id"),
    )
