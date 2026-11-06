from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import (
    NotFoundException,
    ConflictException,
    UnprocessableEntityException,
)
from app.database.models.profile import Profile
from app.database.models.patient import Patient
from app.database.models.visit import Visit
from app.database.models.pharmacy import StockItem, StockMove, PharmacySale
from app.database.models.governance import ClinicSettings
from app.schemas.pharmacy import (
    StockItemSchema,
    StockInput,
    ReceiveStockRequest,
    StockMoveSchema,
    CatalogMedicine,
    DispenseRequest,
    CounterSaleRequest,
    PharmacySaleSchema,
    SaleLine,
    PrescriptionSchema,
)
from app.schemas.clinical import Medicine, DoseInstructions
from app.services.audit_service import log_audit
from app.core.idempotency import check_idempotency, save_idempotency_record

EXPIRY_WARNING_DAYS = 30


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_stock_level(quantity: int, low_level: int) -> str:
    if quantity <= 0:
        return "out"
    return "low" if quantity <= low_level else "ok"


def get_stock_expiry(expires_on: Optional[date]) -> str:
    if not expires_on:
        return "none"
    today = date.today()
    if expires_on < today:
        return "expired"
    if expires_on <= today + timedelta(days=EXPIRY_WARNING_DAYS):
        return "soon"
    return "ok"


async def get_settings(db: AsyncSession) -> ClinicSettings:
    stmt = select(ClinicSettings).where(ClinicSettings.id == 1)
    res = await db.execute(stmt)
    s = res.scalar_one_or_none()
    if not s:
        s = ClinicSettings(id=1)
        db.add(s)
        await db.commit()
    return s


async def list_stock_items(db: AsyncSession) -> List[StockItemSchema]:
    stmt = select(StockItem)
    items = (await db.execute(stmt)).scalars().all()

    def rank(item: StockItem) -> int:
        lvl = get_stock_level(item.quantity, item.low_level)
        exp = get_stock_expiry(item.expires_on)
        if lvl == "out" or exp == "expired":
            return 0
        if lvl == "low" or exp == "soon":
            return 1
        return 2

    # Problems first: out/expired, then low/soon, then name
    sorted_items = sorted(items, key=lambda x: (rank(x), x.name.lower()))

    return [
        StockItemSchema(
            id=i.id,
            name=i.name,
            unit=i.unit,
            quantity=i.quantity,
            low_level=i.low_level,
            expires_on=str(i.expires_on) if i.expires_on else None,
            barcode=i.barcode,
            price=float(i.price),
            level=get_stock_level(i.quantity, i.low_level),
            expiry=get_stock_expiry(i.expires_on),
        )
        for i in sorted_items
    ]


async def get_medicine_catalog(db: AsyncSession) -> List[CatalogMedicine]:
    stmt = select(StockItem).order_by(StockItem.name.asc())
    items = (await db.execute(stmt)).scalars().all()

    catalog = []
    for item in items:
        lvl = get_stock_level(item.quantity, item.low_level)
        exp = get_stock_expiry(item.expires_on)
        if exp == "expired":
            avail = "expired"
        elif lvl == "out":
            avail = "out"
        elif lvl == "low":
            avail = "low"
        else:
            avail = "available"
        catalog.append(CatalogMedicine(name=item.name, availability=avail))
    return catalog


async def create_stock_item(db: AsyncSession, req: StockInput, user: Profile):
    chk = select(StockItem).where(func.lower(StockItem.name) == req.name.strip().lower())
    if (await db.execute(chk)).scalar_one_or_none():
        raise ConflictException(message="Item with this name already exists", code="stock_exists")

    if req.barcode:
        b_chk = select(StockItem).where(StockItem.barcode == req.barcode.strip())
        if (await db.execute(b_chk)).scalar_one_or_none():
            raise ConflictException(message="Barcode is already assigned to another item", code="barcode_taken")

    exp_date = date.fromisoformat(req.expires_on) if req.expires_on else None
    item = StockItem(
        name=req.name.strip(),
        price=req.price,
        unit=req.unit,
        quantity=req.quantity,
        low_level=req.low_level,
        expires_on=exp_date,
        barcode=req.barcode.strip() if req.barcode else None,
    )
    db.add(item)
    await db.flush()

    move = StockMove(
        at=datetime.now(timezone.utc),
        by=user.name,
        kind="create",
        stock_id=item.id,
        item_name=item.name,
        unit=item.unit,
        change=item.quantity,
        quantity_after=item.quantity,
        note="",
    )
    db.add(move)

    await log_audit(db, user, "stock.create", item.name)
    await db.commit()


async def update_stock_item(db: AsyncSession, item_id: int, req: StockInput, user: Profile):
    stmt = select(StockItem).where(StockItem.id == item_id)
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise NotFoundException(message="Stock item not found", code="not_found")

    if req.barcode:
        b_chk = select(StockItem).where(StockItem.barcode == req.barcode.strip(), StockItem.id != item_id)
        if (await db.execute(b_chk)).scalar_one_or_none():
            raise ConflictException(message="Barcode is already assigned to another item", code="barcode_taken")

    before_qty = item.quantity
    item.name = req.name.strip()
    item.price = req.price
    item.unit = req.unit
    item.quantity = req.quantity
    item.low_level = req.low_level
    item.expires_on = date.fromisoformat(req.expires_on) if req.expires_on else None
    item.barcode = req.barcode.strip() if req.barcode else None

    diff = item.quantity - before_qty
    if diff != 0:
        move = StockMove(
            at=datetime.now(timezone.utc),
            by=user.name,
            kind="edit",
            stock_id=item.id,
            item_name=item.name,
            unit=item.unit,
            change=diff,
            quantity_after=item.quantity,
            note="",
        )
        db.add(move)

    await log_audit(db, user, "stock.update", item.name)
    await db.commit()


async def receive_stock(db: AsyncSession, item_id: int, req: ReceiveStockRequest, user: Profile):
    if req.idempotency_key:
        cached = await check_idempotency(db, req.idempotency_key, "stock.receive", req, user.id)
        if cached:
            return

    if req.quantity <= 0:
        raise UnprocessableEntityException(message="Quantity must be greater than 0", code="bad_amount")

    stmt = select(StockItem).where(StockItem.id == item_id)
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise NotFoundException(message="Stock item not found", code="not_found")

    item.quantity += req.quantity
    if req.expires_on:
        item.expires_on = date.fromisoformat(req.expires_on)

    move = StockMove(
        at=datetime.now(timezone.utc),
        by=user.name,
        kind="receive",
        stock_id=item.id,
        item_name=item.name,
        unit=item.unit,
        change=req.quantity,
        quantity_after=item.quantity,
        note="",
    )
    db.add(move)

    await log_audit(db, user, "stock.receive", f"{item.name} · {req.quantity}")
    if req.idempotency_key:
        await save_idempotency_record(db, req.idempotency_key, "stock.receive", req, 200, {"success": True}, user.id)
    await db.commit()


async def get_stock_log(db: AsyncSession, limit: int) -> List[StockMoveSchema]:
    stmt = select(StockMove).order_by(StockMove.id.desc()).limit(limit)
    moves = (await db.execute(stmt)).scalars().all()
    return [
        StockMoveSchema(
            id=m.id,
            at=m.at.isoformat(),
            by=m.by,
            kind=m.kind,
            stock_id=m.stock_id,
            item_name=m.item_name,
            unit=m.unit,
            change=m.change,
            quantity_after=m.quantity_after,
            note=m.note,
        )
        for m in moves
    ]


async def list_prescriptions(db: AsyncSession) -> List[PrescriptionSchema]:
    settings = await get_settings(db)
    validity_days = settings.prescription_days
    now_dt = datetime.now(timezone.utc)

    stmt = select(Visit, Patient).join(Patient, Visit.patient_id == Patient.id).order_by(Visit.created_at.desc())
    rows = (await db.execute(stmt)).all()

    prescriptions = []
    for visit, patient in rows:
        meds = visit.medicines or []
        if not meds:
            continue

        created_dt = to_utc(visit.created_at) or now_dt
        exp_dt = created_dt + timedelta(days=validity_days)
        is_expired = now_dt > exp_dt

        # Filter out old dispensed prescriptions
        if visit.dispensed and is_expired:
            continue

        prescriptions.append(
            PrescriptionSchema(
                id=visit.id,
                patient_name=patient.name,
                allergies=list(patient.allergies or []),
                medicines=[Medicine(**m) for m in meds],
                dispensed=visit.dispensed,
                created_at=created_dt.isoformat(),
                expires_at=exp_dt.isoformat(),
                expired=not visit.dispensed and is_expired,
            )
        )
    return prescriptions


async def dispense_prescription(db: AsyncSession, visit_id: int, req: DispenseRequest, user: Profile) -> Optional[PharmacySaleSchema]:
    stmt = select(Visit, Patient).join(Patient, Visit.patient_id == Patient.id).where(Visit.id == visit_id)
    row = (await db.execute(stmt)).first()
    if not row:
        raise NotFoundException(message="Prescription not found", code="not_found")
    visit, patient = row

    if visit.dispensed:
        raise ConflictException(message="Prescription has already been dispensed", code="already_dispensed")

    settings = await get_settings(db)
    created_dt = to_utc(visit.created_at) or datetime.now(timezone.utc)
    exp_dt = created_dt + timedelta(days=settings.prescription_days)
    if datetime.now(timezone.utc) > exp_dt:
        raise ConflictException(message="Prescription has expired", code="expired")

    if len(req.lines) != len(visit.medicines or []):
        raise UnprocessableEntityException(message="Line items count does not match prescription medicines", code="validation_error")

    # Aggregate stock item requirements
    needed: Dict[int, int] = {}
    for line in req.lines:
        if line.stock_id is not None:
            if line.quantity <= 0:
                raise UnprocessableEntityException(message="Quantity must be greater than 0", code="bad_amount")
            needed[line.stock_id] = needed.get(line.stock_id, 0) + line.quantity

    # Validate stock quantities and expiration
    stock_items_map = {}
    for stock_id, qty in needed.items():
        s_stmt = select(StockItem).where(StockItem.id == stock_id)
        item = (await db.execute(s_stmt)).scalar_one_or_none()
        if not item:
            raise NotFoundException(message=f"Stock item {stock_id} not found", code="not_found")
        if get_stock_expiry(item.expires_on) == "expired":
            raise ConflictException(message=f"Stock item '{item.name}' is expired", code="stock_expired")
        if item.quantity < qty:
            raise ConflictException(message=f"Stock item '{item.name}' is out of stock (available: {item.quantity}, requested: {qty})", code="out_of_stock")
        stock_items_map[stock_id] = item

    # Execute inventory decrements & create sale lines
    sale_lines = []
    now_utc = datetime.now(timezone.utc)
    for stock_id, qty in needed.items():
        item = stock_items_map[stock_id]
        item.quantity -= qty
        move = StockMove(
            at=now_utc,
            by=user.name,
            kind="dispense",
            stock_id=item.id,
            item_name=item.name,
            unit=item.unit,
            change=-qty,
            quantity_after=item.quantity,
            note=patient.name,
        )
        db.add(move)

        u_price = float(item.price)
        sale_lines.append(
            SaleLine(
                stock_id=item.id,
                name=item.name,
                unit=item.unit,
                quantity=qty,
                unit_price=u_price,
                total=u_price * qty,
            )
        )

    # Attach instructions to prescription medicines
    current_meds = list(visit.medicines or [])
    for idx, line in enumerate(req.lines):
        if idx < len(current_meds):
            current_meds[idx]["instructions"] = line.instructions.model_dump()
    visit.medicines = current_meds
    visit.dispensed = True

    sale_result = None
    if sale_lines:
        total_amt = sum(l.total for l in sale_lines)
        sale = PharmacySale(
            at=now_utc,
            by=user.name,
            kind="prescription",
            customer=patient.name,
            lines=[l.model_dump() for l in sale_lines],
            total=total_amt,
        )
        db.add(sale)
        await db.flush()
        sale_result = PharmacySaleSchema(
            id=sale.id,
            at=sale.at.isoformat(),
            by=sale.by,
            kind="prescription",
            customer=sale.customer,
            lines=sale_lines,
            total=float(sale.total),
        )

    await log_audit(db, user, "prescription.dispense", patient.name)
    await db.commit()
    return sale_result


async def sell_over_counter(db: AsyncSession, req: CounterSaleRequest, user: Profile) -> PharmacySaleSchema:
    if req.idempotency_key:
        cached = await check_idempotency(db, req.idempotency_key, "pharmacy.sale", req, user.id)
        if cached:
            return PharmacySaleSchema(**cached[1])

    if not req.lines:
        raise UnprocessableEntityException(message="Sale lines cannot be empty", code="empty_sale")

    needed: Dict[int, int] = {}
    for line in req.lines:
        if line.quantity <= 0:
            raise UnprocessableEntityException(message="Quantity must be greater than 0", code="bad_amount")
        needed[line.stock_id] = needed.get(line.stock_id, 0) + line.quantity

    stock_items_map = {}
    for stock_id, qty in needed.items():
        s_stmt = select(StockItem).where(StockItem.id == stock_id)
        item = (await db.execute(s_stmt)).scalar_one_or_none()
        if not item:
            raise NotFoundException(message=f"Stock item {stock_id} not found", code="not_found")
        if get_stock_expiry(item.expires_on) == "expired":
            raise ConflictException(message=f"Item '{item.name}' is expired", code="stock_expired")
        if item.quantity < qty:
            raise ConflictException(message=f"Item '{item.name}' out of stock", code="out_of_stock")
        stock_items_map[stock_id] = item

    now_utc = datetime.now(timezone.utc)
    sale_lines = []
    for stock_id, qty in needed.items():
        item = stock_items_map[stock_id]
        item.quantity -= qty
        move = StockMove(
            at=now_utc,
            by=user.name,
            kind="sale",
            stock_id=item.id,
            item_name=item.name,
            unit=item.unit,
            change=-qty,
            quantity_after=item.quantity,
            note=req.customer.strip(),
        )
        db.add(move)

        u_price = float(item.price)
        sale_lines.append(
            SaleLine(
                stock_id=item.id,
                name=item.name,
                unit=item.unit,
                quantity=qty,
                unit_price=u_price,
                total=u_price * qty,
            )
        )

    total_amt = sum(l.total for l in sale_lines)
    sale = PharmacySale(
        at=now_utc,
        by=user.name,
        kind="counter",
        customer=req.customer.strip(),
        lines=[l.model_dump() for l in sale_lines],
        total=total_amt,
        idempotency_key=req.idempotency_key,
    )
    db.add(sale)
    await db.flush()

    await log_audit(db, user, "pharmacy.sale", f"{req.customer.strip() or '—'} · {int(total_amt):,} IQD")
    result_schema = PharmacySaleSchema(
        id=sale.id,
        at=sale.at.isoformat(),
        by=sale.by,
        kind="counter",
        customer=sale.customer,
        lines=sale_lines,
        total=float(sale.total),
    )
    if req.idempotency_key:
        await save_idempotency_record(db, req.idempotency_key, "pharmacy.sale", req, 200, result_schema.model_dump(), user.id)
    await db.commit()

    return result_schema


async def list_sales_by_date(db: AsyncSession, date_str: str) -> List[PharmacySaleSchema]:
    target_date = date.fromisoformat(date_str)
    stmt = select(PharmacySale).where(
        func.date(PharmacySale.at) == target_date
    ).order_by(PharmacySale.id.desc())
    sales = (await db.execute(stmt)).scalars().all()

    return [
        PharmacySaleSchema(
            id=s.id,
            at=s.at.isoformat(),
            by=s.by,
            kind=s.kind,
            customer=s.customer,
            lines=[SaleLine(**l) for l in (s.lines or [])],
            total=float(s.total),
        )
        for s in sales
    ]
