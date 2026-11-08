import json
from typing import Optional
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.services import lab_service
from app.integrations.supabase_storage import supabase_storage

router = APIRouter(prefix="/lab", tags=["Laboratory"])


@router.get("/orders")
async def list_orders(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("lab", "manager")),
):
    orders = await lab_service.list_lab_orders(db)
    return success_response([o.model_dump() for o in orders])


@router.put("/orders/{order_id}/result")
async def save_result(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("lab", "manager")),
):
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file: UploadFile = form.get("file")
        note = form.get("note", "")

        file_bytes = await uploaded_file.read()
        import re
        import os
        raw_name = os.path.basename(uploaded_file.filename or "file.dat")
        clean_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", raw_name)
        saved_file_name = f"{order_id}_{clean_name}"
        storage_url = await supabase_storage.upload_file(
            saved_file_name,
            file_bytes,
            uploaded_file.content_type or "application/octet-stream",
            bucket="lab-results",
        )

        result_data = {
            "type": "file",
            "file_name": uploaded_file.filename,
            "file_type": uploaded_file.content_type or "application/octet-stream",
            "data_url": storage_url,
            "note": str(note).strip(),
        }
    else:
        # JSON payload
        body = await request.json()
        result_data = body

    await lab_service.save_lab_result(db, order_id, result_data, user)
    return success_response(None)


@router.post("/orders/{order_id}/confirm")
async def confirm_result(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("lab", "manager")),
):
    await lab_service.confirm_lab_result(db, order_id, user)
    return success_response(None)
