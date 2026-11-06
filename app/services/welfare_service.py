import os
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import UploadFile
from sqlalchemy import select, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundException, ConflictException, UnprocessableEntityException, ForbiddenException
from app.database.models.appointment import Appointment
from app.database.models.finance import InvoiceItem
from app.database.models.patient import Patient, WelfareRequest
from app.database.models.profile import Profile
from app.schemas.welfare import WelfareRequestSchema, WelfareReviewRequest
from app.services.audit_service import log_audit
from app.services.notification_service import notify_patient, notify_role

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads", "welfare")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _welfare_to_schema(w: WelfareRequest) -> WelfareRequestSchema:
    return WelfareRequestSchema(
        id=w.id,
        patient_id=w.patient_id,
        patient_name=w.patient_name,
        patient_phone=w.patient_phone,
        card_number=w.card_number,
        photo_url=w.photo_url,
        status=w.status,
        submitted_at=w.submitted_at.isoformat() if w.submitted_at else "",
        reviewed_by=w.reviewed_by,
        reviewed_at=w.reviewed_at.isoformat() if w.reviewed_at else None,
        valid_until=w.valid_until.isoformat() if w.valid_until else None,
        reject_reason=w.reject_reason or "",
    )


async def get_active_welfare(db: AsyncSession, patient_id: int, on_date: Optional[date] = None) -> Optional[WelfareRequest]:
    target_date = on_date or date.today()
    stmt = (
        select(WelfareRequest)
        .where(
            WelfareRequest.patient_id == patient_id,
            WelfareRequest.status == "approved",
            WelfareRequest.valid_until.isnot(None),
            WelfareRequest.valid_until >= target_date,
        )
        .order_by(desc(WelfareRequest.valid_until))
    )
    res = await db.execute(stmt)
    return res.scalars().first()


async def get_welfare_percent(db: AsyncSession, patient_id: int, on_date: Optional[date] = None) -> int:
    w = await get_active_welfare(db, patient_id, on_date)
    if not w:
        return 0
    from app.services import admin_service
    settings = await admin_service.get_clinic_settings(db)
    return getattr(settings, "welfare_discount_percent", 25) or 25


async def add_welfare_discount(db: AsyncSession, appointment_id: int):
    stmt = select(Appointment).where(Appointment.id == appointment_id)
    appt = (await db.execute(stmt)).scalar_one_or_none()
    if not appt:
        return

    percent = await get_welfare_percent(db, appt.patient_id, appt.date)
    if percent <= 0:
        return

    # Check if discount line item already exists
    stmt_items = select(InvoiceItem).where(
        InvoiceItem.appointment_id == appointment_id,
        InvoiceItem.kind == "discount",
    )
    existing_discount = (await db.execute(stmt_items)).scalars().first()
    if existing_discount:
        return

    # Find total visit fee in IQD
    stmt_visit = select(InvoiceItem).where(
        InvoiceItem.appointment_id == appointment_id,
        InvoiceItem.kind == "visit",
        InvoiceItem.currency == "IQD",
    )
    visit_items = (await db.execute(stmt_visit)).scalars().all()
    visit_total = sum(float(i.price) for i in visit_items)
    if visit_total <= 0:
        return

    # Discount rounded to 250 IQD
    discount_amount = round((visit_total * percent / 100.0) / 250.0) * 250.0
    if discount_amount <= 0:
        return

    discount_item = InvoiceItem(
        appointment_id=appointment_id,
        label=f"Social welfare discount ({percent}%)",
        label_ar=f"خصم الرعاية الاجتماعية ({percent}%)",
        kind="discount",
        price=-discount_amount,
        currency="IQD",
        created_at=datetime.now(timezone.utc),
    )
    db.add(discount_item)
    await db.flush()


async def submit_welfare(
    db: AsyncSession,
    patient_id: int,
    card_number: str,
    photo: UploadFile,
    user: Profile,
) -> WelfareRequestSchema:
    # Verify patient exists
    stmt_patient = select(Patient).where(Patient.id == patient_id)
    patient = (await db.execute(stmt_patient)).scalar_one_or_none()
    if not patient:
        raise NotFoundException("Patient not found", "not_found")

    if user.role == "patient" and patient.account_id != user.id:
        raise ForbiddenException("Cannot manage other patients' welfare", "forbidden")

    card_clean = card_number.strip() if card_number else ""
    if not card_clean:
        raise UnprocessableEntityException("Card number is required", "bad_card_number")

    # Read and save photo file
    ext = os.path.splitext(photo.filename or "")[1] or ".jpg"
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    local_path = os.path.join(UPLOAD_DIR, unique_filename)
    content = await photo.read()
    with open(local_path, "wb") as f:
        f.write(content)

    photo_url = f"/uploads/welfare/{unique_filename}"
    try:
        from app.integrations.supabase_storage import supabase_storage
        ct = photo.content_type or ("image/png" if ext == ".png" else "image/jpeg")
        storage_file = await supabase_storage.upload_file(unique_filename, content, ct)
        if storage_file and not storage_file.startswith("data:"):
            photo_url = f"/storage/v1/object/authenticated/{supabase_storage.bucket}/{storage_file}"
    except Exception:
        pass

    # Check for existing pending request
    stmt_pending = select(WelfareRequest).where(
        WelfareRequest.patient_id == patient_id,
        WelfareRequest.status == "pending",
    )
    pending_req = (await db.execute(stmt_pending)).scalars().first()

    now = datetime.now(timezone.utc)
    if pending_req:
        pending_req.card_number = card_clean
        pending_req.photo_url = photo_url
        pending_req.submitted_at = now
        w = pending_req
    else:
        w = WelfareRequest(
            patient_id=patient_id,
            patient_name=patient.name,
            patient_phone=patient.phone,
            card_number=card_clean,
            photo_url=photo_url,
            status="pending",
            submitted_at=now,
            reject_reason="",
        )
        db.add(w)

    await db.flush()
    await db.refresh(w)

    # Notify receptionists
    await notify_role(
        db,
        "reception",
        f"welfare-submitted-{w.id}",
        "welfare_submitted",
        {"patient": patient.name},
    )

    await log_audit(db, user, "welfare.submit", patient.name)
    await db.commit()
    await db.refresh(w)
    return _welfare_to_schema(w)


async def list_welfare(db: AsyncSession, status: str) -> List[WelfareRequestSchema]:
    stmt = select(WelfareRequest).where(WelfareRequest.status == status)
    if status == "pending":
        stmt = stmt.order_by(asc(WelfareRequest.submitted_at))
    else:
        stmt = stmt.order_by(desc(WelfareRequest.reviewed_at))

    rows = (await db.execute(stmt)).scalars().all()
    return [_welfare_to_schema(w) for w in rows]


async def review_welfare(
    db: AsyncSession,
    request_id: int,
    review: WelfareReviewRequest,
    user: Profile,
) -> WelfareRequestSchema:
    stmt = select(WelfareRequest).where(WelfareRequest.id == request_id)
    w = (await db.execute(stmt)).scalar_one_or_none()
    if not w:
        raise NotFoundException("Welfare request not found", "not_found")

    if w.status != "pending":
        raise ConflictException("Request has already been reviewed", "already_reviewed")

    stmt_p = select(Patient).where(Patient.id == w.patient_id)
    patient = (await db.execute(stmt_p)).scalar_one_or_none()
    patient_name = patient.name if patient else w.patient_name

    now = datetime.now(timezone.utc)
    today_str = str(date.today())

    if review.approve:
        if not review.valid_until or review.valid_until <= today_str:
            raise UnprocessableEntityException("Valid until date must be in the future", "bad_valid_until")

        w.status = "approved"
        w.valid_until = datetime.strptime(review.valid_until, "%Y-%m-%d").date()
        w.reviewed_by = user.name
        w.reviewed_at = now

        # Add discount to booked unpaid appointments for this patient
        from app.services import finance_service, admin_service
        stmt_appts = select(Appointment).where(
            Appointment.patient_id == w.patient_id,
            Appointment.status == "booked",
            Appointment.date >= date.today(),
        )
        appts = (await db.execute(stmt_appts)).scalars().all()
        for a in appts:
            money = await finance_service.get_money_summary(db, a.id)
            if money.paid.get("IQD", 0) == 0:
                await add_welfare_discount(db, a.id)

        settings = await admin_service.get_clinic_settings(db)
        discount_percent = getattr(settings, "welfare_discount_percent", 25) or 25

        await notify_patient(
            db,
            w.patient_id,
            f"welfare-approved-{w.id}",
            "welfare_approved",
            {
                "patient": patient_name,
                "percent": discount_percent,
                "date": review.valid_until,
            },
        )
        await log_audit(db, user, "welfare.approve", patient_name)
    else:
        reason = (review.reason or "").strip()
        if len(reason) < 3:
            raise UnprocessableEntityException("Rejection reason must be provided", "reason_needed")

        w.status = "rejected"
        w.reject_reason = reason
        w.reviewed_by = user.name
        w.reviewed_at = now

        await notify_patient(
            db,
            w.patient_id,
            f"welfare-rejected-{w.id}",
            "welfare_rejected",
            {
                "patient": patient_name,
                "reason": w.reject_reason,
            },
        )
        await log_audit(db, user, "welfare.reject", f"{patient_name} · {w.reject_reason}")

    await db.commit()
    await db.refresh(w)
    return _welfare_to_schema(w)


async def get_family_welfare(db: AsyncSession, user: Profile) -> List[WelfareRequestSchema]:
    stmt_p = select(Patient.id).where(Patient.account_id == user.id)
    patient_ids = (await db.execute(stmt_p)).scalars().all()
    if not patient_ids:
        return []

    results: List[WelfareRequestSchema] = []
    for pid in patient_ids:
        stmt_w = (
            select(WelfareRequest)
            .where(WelfareRequest.patient_id == pid)
            .order_by(desc(WelfareRequest.submitted_at))
        )
        latest = (await db.execute(stmt_w)).scalars().first()
        if latest:
            results.append(_welfare_to_schema(latest))

    return results
