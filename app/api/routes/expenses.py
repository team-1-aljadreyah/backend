from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.finance import ExpenseInput
from app.services import finance_service

router = APIRouter(prefix="/expenses", tags=["Expenses"])


@router.get("")
async def list_expenses(
    month: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("accountant", "manager")),
):
    target_month = month or datetime.now().strftime("%Y-%m")
    expenses = await finance_service.list_expenses(db, target_month)
    return success_response([e.model_dump() for e in expenses])


@router.post("")
async def add_expense(
    req: ExpenseInput,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("accountant", "manager")),
):
    expense = await finance_service.add_expense(db, req, user)
    return success_response(expense.model_dump())


@router.post("/{expense_id}/void")
async def void_expense(
    expense_id: int,
    reason: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("accountant", "manager")),
):
    expense = await finance_service.void_expense(db, expense_id, reason, user)
    return success_response(expense.model_dump())
