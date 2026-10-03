from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session as DbSession

from app.core.deps import current_cashier
from app.core.errors import AppError
from app.db.session import get_db
from app.models.schemas import MEMBER_ID_PATTERN, MemberOut
from app.repositories import member_repository

router = APIRouter(prefix="/api/members", tags=["members"], dependencies=[Depends(current_cashier)])


@router.get("/{member_id}", response_model=MemberOut)
def get_member(member_id: Annotated[str, Path(pattern=MEMBER_ID_PATTERN)], db: DbSession = Depends(get_db)):
    member = member_repository.get_active(db, member_id)
    if member is None:  # 未登録・退会済みは同じ扱い（T-012）
        raise AppError(404, "MEMBER_NOT_FOUND", "会員IDが見つかりません。再入力するか、非会員を選択してください。")
    return MemberOut(member_id=member.member_id, display_name=member.name)
