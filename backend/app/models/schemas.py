"""API の入出力スキーマ（Pydantic）。"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 暫定書式（テスト設計書1.3の仮値）
PRODUCT_CODE_PATTERN = r"^[0-9]{13}$"   # \d は全角数字にも一致するため [0-9] を使う
MEMBER_ID_PATTERN = r"^M[0-9]{6}$"
CASHIER_ID_PATTERN = r"^[A-Za-z0-9]{1,20}$"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cashier_id: str = Field(min_length=1, max_length=20, pattern=CASHIER_ID_PATTERN)
    password: str = Field(min_length=8, max_length=64)


class CashierOut(BaseModel):
    cashier_id: str
    cashier_name: str


class LoginResponse(BaseModel):
    cashier: CashierOut


class MemberOut(BaseModel):
    """会計に必要な最小限（NF-008）。住所・電話番号・性別・年齢は返さない。"""
    member_id: str
    display_name: str


class ProductOut(BaseModel):
    product_code: str
    product_name: str
    unit_price: int


class TransactionItemIn(BaseModel):
    model_config = ConfigDict(extra="ignore")  # 単価・小計などクライアント値は読み捨てる（T-034）
    product_code: str = Field(pattern=PRODUCT_CODE_PATTERN)
    quantity: int = Field(ge=1, le=99)


class TransactionCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")  # 合計金額・担当者IDなどが送られても使わない
    member_id: str | None = Field(default=None, pattern=MEMBER_ID_PATTERN)
    sales_mode: Literal["DINE_IN", "TAKEOUT"]
    idempotency_key: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    # 空配列は 422 ではなく業務エラー 400 EMPTY_CART として扱う（設計8.6）ため min_length は付けない
    items: list[TransactionItemIn] = Field(max_length=100)


class TransactionResult(BaseModel):
    transaction_id: str
    subtotal_excl_tax: int
    tax_amount: int
    total_incl_tax: int
    transaction_at: str
