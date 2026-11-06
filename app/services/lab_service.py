from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundException, ConflictException
from app.database.models.profile import Profile, Doctor
from app.database.models.patient import Patient
from app.database.models.visit import LabOrder, Service
from app.schemas.lab import LabOrderSchema, TestResult, ResultEdit
from app.schemas.service import ServiceSchema
from app.services.audit_service import log_audit
from app.services.notification_service import notify_patient, notify_user


def check_is_abnormal(result: Optional[Dict[str, Any]]) -> bool:
    if not result or result.get("type") != "values":
        return False
    rows = result.get("rows", [])
    for r in rows:
        val = r.get("value")
        low = r.get("ref_low")
        high = r.get("ref_high")
        if val is not None:
            if low is not None and val < low:
                return True
            if high is not None and val > high:
                return True
    return False


async def list_lab_orders(db: AsyncSession) -> List[LabOrderSchema]:
    stmt = (
        select(LabOrder, Patient.name, Doctor.name_ar, Service)
        .join(Patient, LabOrder.patient_id == Patient.id)
        .join(Doctor, LabOrder.doctor_id == Doctor.id)
        .join(Service, LabOrder.service_id == Service.id)
        .order_by(LabOrder.id.desc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        LabOrderSchema(
            id=order.id,
            patient_name=patient_name,
            doctor_name=doctor_name,
            test=ServiceSchema(
                id=svc.id,
                name=svc.name,
                name_ar=svc.name_ar,
                kind=svc.kind,
                price=float(svc.price),
                currency=svc.currency,
                template=svc.template,
            ),
            status=order.status,
            result=order.result,
            history=[ResultEdit(**h) for h in (order.history or [])],
            requested_at=order.requested_at.isoformat(),
        )
        for order, patient_name, doctor_name, svc in rows
    ]


async def save_lab_result(db: AsyncSession, order_id: int, result_data: Dict[str, Any], user: Profile):
    stmt = select(LabOrder, Patient).join(Patient, LabOrder.patient_id == Patient.id).where(
        LabOrder.id == order_id
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise NotFoundException(message="Lab order not found", code="not_found")
    order, patient = row

    now_str = datetime.now(timezone.utc).isoformat()
    if order.status == "confirmed" and order.result:
        history = list(order.history or [])
        history.insert(0, {
            "at": now_str,
            "by": user.name,
            "before": order.result,
        })
        order.history = history
        await log_audit(db, user, "lab.edit", patient.name)
    else:
        order.status = "entered"
        await log_audit(db, user, "lab.result", patient.name)

    order.result = result_data
    await db.commit()


async def confirm_lab_result(db: AsyncSession, order_id: int, user: Profile):
    stmt = select(LabOrder, Patient, Service).join(
        Patient, LabOrder.patient_id == Patient.id
    ).join(
        Service, LabOrder.service_id == Service.id
    ).where(
        LabOrder.id == order_id
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise NotFoundException(message="Lab order not found", code="not_found")
    order, patient, service = row

    if order.status != "entered":
        raise ConflictException(message="Only entered results can be confirmed", code="nothing_to_confirm")

    now_utc = datetime.now(timezone.utc)
    order.status = "confirmed"
    order.confirmed_at = now_utc

    # Notify patient
    await notify_patient(
        db,
        order.patient_id,
        f"result:{order.id}",
        "result_ready",
        {"test": service.name_ar},
    )

    # Notify ordering doctor
    doc_profile_stmt = select(Profile).where(Profile.doctor_id == order.doctor_id, Profile.role == "doctor")
    doc_user = (await db.execute(doc_profile_stmt)).scalars().first()
    if doc_user:
        abnormal = 1 if check_is_abnormal(order.result) else 0
        await notify_user(
            db,
            doc_user.id,
            f"doctor-result:{order.id}",
            "result_for_doctor",
            {
                "test": service.name_ar,
                "patient": patient.name,
                "abnormal": abnormal,
            },
        )

    await log_audit(db, user, "lab.confirm", patient.name)
    await db.commit()


async def get_my_results(db: AsyncSession, user: Profile) -> List[TestResult]:
    p_stmt = select(Patient.id).where(Patient.account_id == user.id)
    patient_ids = list((await db.execute(p_stmt)).scalars().all())
    if not patient_ids:
        return []

    stmt = select(LabOrder, Patient.name, Service).join(
        Patient, LabOrder.patient_id == Patient.id
    ).join(
        Service, LabOrder.service_id == Service.id
    ).where(
        LabOrder.patient_id.in_(patient_ids),
        LabOrder.status == "confirmed",
        LabOrder.result.is_not(None),
    ).order_by(LabOrder.confirmed_at.desc())
    rows = (await db.execute(stmt)).all()

    return [
        TestResult(
            id=order.id,
            patient_name=patient_name,
            test=ServiceSchema(
                id=svc.id,
                name=svc.name,
                name_ar=svc.name_ar,
                kind=svc.kind,
                price=float(svc.price),
                currency=svc.currency,
                template=svc.template,
            ),
            result=order.result,
            confirmed_at=order.confirmed_at.isoformat() if order.confirmed_at else "",
        )
        for order, patient_name, svc in rows
    ]
