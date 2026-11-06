from typing import Optional
from fastapi import APIRouter, Depends, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.pharmacy import StockInput, ReceiveStockRequest, CounterSaleRequest
from app.services import pharmacy_service

router = APIRouter(prefix="/pharmacy", tags=["Pharmacy"])


@router.get("/catalog")
async def medicine_catalog(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("doctor", "pharmacy", "manager")),
):
    catalog = await pharmacy_service.get_medicine_catalog(db)
    return success_response([c.model_dump() for c in catalog])


@router.get("/stock")
async def list_stock(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("pharmacy", "manager")),
):
    stock = await pharmacy_service.list_stock_items(db)
    return success_response([s.model_dump() for s in stock])


@router.post("/stock")
async def create_stock(
    req: StockInput,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("pharmacy", "manager")),
):
    await pharmacy_service.create_stock_item(db, req, user)
    return success_response(None)


@router.put("/stock/{item_id}")
async def update_stock(
    item_id: int,
    req: StockInput,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("pharmacy", "manager")),
):
    await pharmacy_service.update_stock_item(db, item_id, req, user)
    return success_response(None)


@router.post("/stock/{item_id}/receive")
async def receive_stock(
    item_id: int,
    req: ReceiveStockRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("pharmacy", "manager")),
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_idempotency_key_header: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    if not req.idempotency_key:
        req.idempotency_key = idempotency_key_header or x_idempotency_key_header
    await pharmacy_service.receive_stock(db, item_id, req, user)
    return success_response(None)


@router.get("/stock/log")
async def stock_log(
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("pharmacy", "manager")),
):
    moves = await pharmacy_service.get_stock_log(db, limit)
    return success_response([m.model_dump() for m in moves])


@router.post("/sales")
async def sell_over_counter(
    req: CounterSaleRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("pharmacy", "manager")),
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_idempotency_key_header: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    if not req.idempotency_key:
        req.idempotency_key = idempotency_key_header or x_idempotency_key_header
    sale = await pharmacy_service.sell_over_counter(db, req, user)
    return success_response(sale.model_dump())


@router.get("/sales")
async def list_sales(
    date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("pharmacy", "accountant", "manager")),
):
    from datetime import date as dt_date
    target_date = date or dt_date.today().isoformat()
    sales = await pharmacy_service.list_sales_by_date(db, target_date)
    return success_response([s.model_dump() for s in sales])
