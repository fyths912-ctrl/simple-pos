from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.config import Settings, get_settings
from app.core.deps import current_cashier, require_csrf_header
from app.db.session import get_db
from app.models.db_models import Cashier
from app.models.schemas import TransactionCreate, TransactionResult
from app.services import transaction_service

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.post("", status_code=201, response_model=TransactionResult, dependencies=[Depends(require_csrf_header)])
def create_transaction(body: TransactionCreate, cashier: Cashier = Depends(current_cashier),
                       db: DbSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    # 担当者IDはリクエストではなくセッションから確定する
    return transaction_service.create_transaction(db, settings, cashier.cashier_id, body)
