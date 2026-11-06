from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.patient import (
    MedicalAlerts,
    DuplicateCheckRequest,
    PatientMergeRequest,
)
from app.services import patient_service, clinical_service, appointment_service

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("")
async def search_patients(
    q: Optional[str] = Query("", alias="q"),
    limit: Optional[int] = Query(None),
    offset: Optional[int] = Query(0),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
):
    results = await patient_service.search_patients(db, q or "")
    total = len(results)
    if limit is not None:
        off = offset or 0
        items = results[off : off + limit]
    else:
        items = results
    return success_response({
        "items": [p.model_dump() for p in items],
        "total": total,
    })


@router.get("/duplicates")
async def list_patient_duplicates(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
):
    """
    Lists suspicious duplicate groups across the clinic for Manager/Reception review.
    """
    groups = await patient_service.list_duplicate_groups(db)
    return success_response([g.model_dump() for g in groups])


@router.post("/duplicates/check")
async def check_patient_duplicates(
    req: DuplicateCheckRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
):
    """
    Runs duplicate detection for patient registration or walk-in.
    Evaluates normalized phone, Arabic normalized full name, and birth date.
    Distinguishes exact duplicate patients from family members sharing a phone.
    """
    result = await patient_service.check_patient_duplicates(db, req)
    return success_response(result.model_dump())


@router.post("/merge")
async def merge_patients(
    req: PatientMergeRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    """
    Atomically merges a duplicate source patient record into a primary patient record.
    Transfers appointments, visits, prescriptions, lab orders, vitals, and welfare requests.
    Soft-merges the source record without deletion.
    Accessible ONLY by Manager role.
    """
    result = await patient_service.merge_patients(db, req, user)
    return success_response(result.model_dump())


@router.post("/{source_patient_id}/merge")
async def merge_patient_by_path(
    source_patient_id: int,
    req: PatientMergeRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    """
    Alternative endpoint to merge patient by source path parameter.
    Accessible ONLY by Manager role.
    """
    req.source_patient_id = source_patient_id
    result = await patient_service.merge_patients(db, req, user)
    return success_response(result.model_dump())


@router.get("/{patient_id}/file")
async def get_patient_file(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("doctor", "reception", "manager")),
):
    file = await patient_service.get_patient_file(db, patient_id, user)
    return success_response(file.model_dump())


@router.get("/{patient_id}/alerts")
async def get_patient_alerts(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("doctor", "reception", "manager")),
):
    alerts = await clinical_service.get_patient_alerts(db, patient_id, user)
    return success_response(alerts.model_dump())


@router.put("/{patient_id}/alerts")
async def update_patient_alerts(
    patient_id: int,
    req: MedicalAlerts,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("doctor")),
):
    alerts = await clinical_service.update_patient_alerts(db, patient_id, req, user)
    return success_response(alerts.model_dump())


@router.get("/{patient_id}/vitals")
async def get_patient_vitals(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("doctor", "reception", "manager")),
):
    vitals = await clinical_service.get_patient_vitals(db, patient_id, user)
    return success_response([v.model_dump() for v in vitals])


@router.get("/{patient_id}/visits")
async def get_patient_history(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("doctor", "reception", "manager")),
):
    history = await clinical_service.get_patient_history(db, patient_id, user)
    return success_response([h.model_dump() for h in history])


@router.get("/{patient_id}/booking-rules")
async def get_booking_rules(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    rules = await appointment_service.get_patient_booking_rules(db, patient_id)
    return success_response(rules.model_dump())
