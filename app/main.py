import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from fastapi import FastAPI, Request, Header, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.core.exceptions import AppException
from app.database.connection import engine, AsyncSessionLocal
from app.database.base import Base
from app.database.models import (
    Branch,
    Doctor,
    Profile,
    Patient,
    Service,
    StockItem,
    ClinicSettings,
)
from app.core.security import get_password_hash

# Import API routes
from app.api.routes import (
    auth,
    public,
    doctors,
    appointments,
    me,
    patients,
    lab,
    prescriptions,
    pharmacy,
    invoices,
    cash,
    payments,
    expenses,
    ledger,
    reports,
    manager,
    users,
    settings as settings_route,
    services,
    audit,
    health,
    welfare,
    realtime,
)
from app.services.realtime_service import realtime_manager


async def init_default_data():
    """Initializes tables and basic safe seed data if running on local SQLite or fresh instance."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check if settings exist
        from sqlalchemy import select
        chk = await session.execute(select(ClinicSettings).where(ClinicSettings.id == 1))
        if not chk.scalar_one_or_none():
            logger.info("Seeding default clinic configuration...")
            session.add(ClinicSettings(id=1, cancel_hours=3, no_show_limit=3, deposit_amount=10000, prescription_days=7, usd_rate=1310))
            
            # Branches
            session.add_all([
                Branch(id="main", name="Al-Jadreyah Main Branch", name_ar="الفرع الرئيسي - الجادرية", address="بغداد - الجادرية"),
                Branch(id="second", name="Al-Mansour Branch", name_ar="فرع المنصور", address="بغداد - المنصور"),
            ])
            
            # Default doctors
            doc1 = Doctor(
                id=1,
                name="Dr. Ali Hassan",
                name_ar="د. علي حسن",
                specialty="Internal Medicine",
                specialty_ar="باطنية",
                fee=25000,
                new_minutes=20,
                followup_minutes=10,
                clinic_percent=30,
                service_percent=20,
                days=[
                    {"branch": "main", "shift": "morning"},
                    {"branch": "main", "shift": "morning"},
                    {"branch": "main", "shift": "morning"},
                    {"branch": "main", "shift": "morning"},
                    {"branch": "second", "shift": "evening"},
                    None,
                    {"branch": "main", "shift": "morning"},
                ],
                absences=[],
            )
            doc2 = Doctor(
                id=2,
                name="Dr. Noor Jasim",
                name_ar="د. نور جاسم",
                specialty="Pediatrics",
                specialty_ar="أطفال",
                fee=20000,
                new_minutes=15,
                followup_minutes=10,
                clinic_percent=25,
                service_percent=25,
                days=[
                    {"branch": "second", "shift": "evening"},
                    {"branch": "main", "shift": "morning"},
                    {"branch": "second", "shift": "evening"},
                    {"branch": "second", "shift": "evening"},
                    {"branch": "second", "shift": "evening"},
                    None,
                    {"branch": "second", "shift": "evening"},
                ],
                absences=[],
            )
            session.add_all([doc1, doc2])
            await session.flush()

            # Default users (Both 0780... and 0770... supported)
            pw_hash = get_password_hash("password123")
            users_list = [
                # Standard demo users
                Profile(id=1, name="سارة موظفة", phone="07800000001", password_hash=pw_hash, role="reception"),
                Profile(id=2, name="د. علي حسن", phone="07800000002", password_hash=pw_hash, role="doctor", doctor_id=1),
                Profile(id=3, name="د. نور جاسم", phone="07800000003", password_hash=pw_hash, role="doctor", doctor_id=2),
                Profile(id=4, name="أحمد الصيدلي", phone="07800000004", password_hash=pw_hash, role="pharmacy"),
                Profile(id=5, name="زينب كريم", phone="07800000005", password_hash=pw_hash, role="patient"),
                Profile(id=6, name="مدير المجمع", phone="07800000006", password_hash=pw_hash, role="manager"),
                Profile(id=7, name="حيدر المختبر", phone="07800000007", password_hash=pw_hash, role="lab"),
                Profile(id=8, name="رنا المحاسبة", phone="07800000008", password_hash=pw_hash, role="accountant"),
                # Explicit Production Test Credentials
                Profile(id=9, name="سارة الاستقبال", phone="07701234567", password_hash=get_password_hash("Reception123!"), role="reception"),
                Profile(id=10, name="د. أحمد السعدي", phone="07702345678", password_hash=get_password_hash("Doctor123!"), role="doctor", doctor_id=1),
                Profile(id=11, name="صيدلي المركز", phone="07703456789", password_hash=get_password_hash("Pharmacy123!"), role="pharmacy"),
                Profile(id=12, name="تقني المختبر", phone="07704567890", password_hash=get_password_hash("Lab123!"), role="lab"),
                Profile(id=13, name="محاسب العيادة", phone="07705678901", password_hash=get_password_hash("Accountant123!"), role="accountant"),
                Profile(id=14, name="مدير المركز", phone="07706789012", password_hash=get_password_hash("Manager123!"), role="manager"),
                Profile(id=15, name="علي جاسم", phone="07707890123", password_hash=get_password_hash("Patient123!"), role="patient"),
            ]
            session.add_all(users_list)
            await session.flush()

            # Seed patients
            session.add_all([
                Patient(id=1, name="زينب كريم", phone="07800000005", account_id=5, relation="self", allergies=[], conditions=[]),
                Patient(id=2, name="مصطفى كريم", phone="07700000002", account_id=5, relation="child", allergies=[], conditions=[]),
                Patient(id=3, name="حسن عباس", phone="07700000003", account_id=None, relation="self", allergies=[], conditions=[]),
                Patient(id=4, name="مريم ناصر", phone="07700000004", account_id=None, relation="self", allergies=["Aspirin", "Ibuprofen"], conditions=["ارتفاع ضغط الدم"], blood_type="O+"),
                Patient(id=5, name="علي جاسم", phone="07707890123", account_id=15, relation="self", allergies=[], conditions=[]),
            ])

            # Seed services
            session.add_all([
                Service(id=1, name="Blood sugar", name_ar="سكر الدم", kind="test", price=5000, currency="IQD", template=[{"name": "Fasting glucose", "unit": "mg/dL", "ref_low": 70, "ref_high": 110}]),
                Service(id=2, name="Complete blood count", name_ar="تحليل دم شامل", kind="test", price=15000, currency="IQD", template=[
                    {"name": "Hemoglobin (Hb)", "unit": "g/dL", "ref_low": 12, "ref_high": 17},
                    {"name": "White cells (WBC)", "unit": "10³/µL", "ref_low": 4, "ref_high": 11},
                    {"name": "Red cells (RBC)", "unit": "10⁶/µL", "ref_low": 4.2, "ref_high": 5.9},
                    {"name": "Platelets (PLT)", "unit": "10³/µL", "ref_low": 150, "ref_high": 450},
                ]),
                Service(id=3, name="Vitamin D", name_ar="فيتامين د", kind="test", price=25000, currency="IQD", template=[{"name": "25-OH Vitamin D", "unit": "ng/mL", "ref_low": 30, "ref_high": 100}]),
                Service(id=4, name="Chest X-ray", name_ar="أشعة صدر", kind="xray", price=20, currency="USD"),
                Service(id=5, name="Wound dressing", name_ar="تضميد جرح", kind="procedure", price=10000, currency="IQD"),
            ])

            # Seed stock
            session.add_all([
                StockItem(id=60, name="Paracetamol 500mg", unit="tablet", price=250, quantity=240, low_level=50, barcode="06290000000011"),
                StockItem(id=61, name="Amoxicillin 500mg", unit="capsule", price=500, quantity=30, low_level=40, barcode="06290000000028"),
                StockItem(id=62, name="Vitamin D3 5000 IU", unit="capsule", price=750, quantity=0, low_level=20),
                StockItem(id=63, name="Omeprazole 20mg", unit="capsule", price=400, quantity=120, low_level=30, barcode="06290000000035"),
                StockItem(id=64, name="Amlodipine 5mg", unit="tablet", price=300, quantity=90, low_level=30),
                StockItem(id=65, name="Cetirizine 10mg", unit="tablet", price=250, quantity=60, low_level=20),
                StockItem(id=66, name="Ibuprofen 400mg", unit="tablet", price=250, quantity=45, low_level=20),
                StockItem(id=67, name="Cough syrup 100ml", unit="bottle", price=3000, quantity=12, low_level=5),
            ])

            await session.commit()
            logger.info("Default seed data initialized successfully.")



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()

    logger.info(
        f"Starting {settings.APP_NAME} "
        f"in {settings.APP_ENV} mode..."
    )

    if settings.APP_ENV.lower() in {"development", "testing"}:
        await init_default_data()
    else:
        logger.info(
            "Production mode: automatic schema creation "
            "and demo seeding are disabled."
        )

    await realtime_manager.start_worker_engine()

    yield

    logger.info("Shutting down application...")
    await realtime_manager.stop_worker_engine()
    await engine.dispose()



app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise REST API for Al-Jadreyah Clinic Management System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Explicit production allowlist for CORS
allowed_origins = [
    "https://alrahma.ama8.uk",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
configured_origins = settings.FRONTEND_ORIGINS
if isinstance(configured_origins, list):
    for o in configured_origins:
        o_clean = str(o).strip().rstrip("/")
        if o_clean and o_clean != "*" and o_clean not in allowed_origins:
            allowed_origins.append(o_clean)
elif isinstance(configured_origins, str) and configured_origins.strip() != "*":
    for o in configured_origins.split(","):
        o_clean = o.strip().rstrip("/")
        if o_clean and o_clean != "*" and o_clean not in allowed_origins:
            allowed_origins.append(o_clean)

allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
allowed_headers = [
    "Authorization",
    "Content-Type",
    "Accept",
    "Origin",
    "User-Agent",
    "X-Requested-With",
    "Idempotency-Key",
    "Accept-Language",
    "X-Terminal-Id",
]
exposed_headers = ["Content-Length", "Content-Range", "Retry-After", "Idempotency-Key"]


def _is_allowed_origin(origin: Optional[str]) -> bool:
    if not origin:
        return False
    norm = origin.strip().rstrip("/")
    return norm in allowed_origins


def add_cors_headers(request: Request, response: JSONResponse) -> JSONResponse:
    origin = request.headers.get("origin")
    if origin and _is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


# ---------------------------------------------------------------------------
# Global Exception Handlers Matching Axios Response Interceptor Envelope
# ---------------------------------------------------------------------------

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    resp = JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "code": exc.code or "ERROR",
            "errors": exc.errors or {},
        },
    )
    return add_cors_headers(request, resp)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {}
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []))
        errors[loc] = [err.get("msg")]
    resp = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Validation error occurred",
            "code": "validation_error",
            "errors": errors,
        },
    )
    return add_cors_headers(request, resp)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code = "rate_limited" if exc.status_code == 429 else f"HTTP_{exc.status_code}"
    resp = JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail),
            "code": code,
            "errors": {},
        },
        headers=getattr(exc, "headers", None),
    )
    return add_cors_headers(request, resp)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    resp = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An internal server error occurred",
            "code": "internal_server_error",
            "errors": {},
        },
    )
    return add_cors_headers(request, resp)


# Register all API routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(public.router)
app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(me.router)
app.include_router(patients.router)
app.include_router(lab.router)
app.include_router(prescriptions.router)
app.include_router(pharmacy.router)
app.include_router(invoices.router)
app.include_router(cash.router)
app.include_router(payments.router)
app.include_router(expenses.router)
app.include_router(ledger.router)
app.include_router(reports.router)
app.include_router(manager.router)
app.include_router(users.router)
app.include_router(settings_route.router)
app.include_router(services.router)
app.include_router(audit.router)
app.include_router(welfare.router)
app.include_router(realtime.router)

# Secure File Access Routes (Replacing public static directory mount)
@app.get("/storage/v1/object/authenticated/{bucket}/{filename}")
async def get_storage_file(
    bucket: str,
    filename: str,
    token: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    from fastapi import Response, HTTPException
    from sqlalchemy import select
    from app.core.security import verify_file_download_token, decode_token
    from app.integrations.supabase_storage import supabase_storage
    from app.database.connection import AsyncSessionLocal
    from app.database.models.patient import Patient, WelfareRequest
    from app.database.models.visit import LabOrder

    safe_filename = os.path.basename(filename)
    if not safe_filename or safe_filename != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    user_info = None
    if token:
        user_info = verify_file_download_token(token=token, filename=safe_filename, bucket=bucket)

    if not user_info and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            payload = decode_token(parts[1])
            if payload and payload.get("type") == "access":
                user_info = {
                    "user_id": int(payload.get("sub", 0)),
                    "role": payload.get("role", "patient"),
                }

    if not user_info:
        raise HTTPException(status_code=401, detail="Authentication required to access protected files")

    role = user_info.get("role", "patient")
    user_id = user_info.get("user_id")

    # Access control
    if role not in ("manager", "accountant", "reception", "doctor", "lab", "welfare_viewer"):
        if role == "patient" and user_id:
            async with AsyncSessionLocal() as session:
                if bucket == "welfare":
                    stmt = select(WelfareRequest).join(Patient, WelfareRequest.patient_id == Patient.id).where(
                        Patient.account_id == user_id,
                        WelfareRequest.photo_url.contains(safe_filename),
                    )
                    res = await session.execute(stmt)
                    if not res.scalar_one_or_none():
                        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this document")
                elif bucket == "lab-results":
                    stmt = select(LabOrder).join(Patient, LabOrder.patient_id == Patient.id).where(
                        Patient.account_id == user_id,
                        LabOrder.attachment_url.contains(safe_filename),
                    )
                    res = await session.execute(stmt)
                    if not res.scalar_one_or_none():
                        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this document")
                else:
                    raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this document")
        else:
            raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this document")

    res = await supabase_storage.get_file_content(safe_filename, bucket=bucket)
    if res:
        content, ct = res
        return Response(
            content=content,
            media_type=ct,
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, max-age=300",
            },
        )

    raise HTTPException(status_code=404, detail="File not found")


@app.get("/files/{bucket}/{filename}")
async def get_secure_file(
    bucket: str,
    filename: str,
    token: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    return await get_storage_file(bucket, filename, token, authorization)


# Wrap complete application with CORSMiddleware at the ASGI level
# after all routes and exception handlers have been registered
api_app = app
app = CORSMiddleware(
    api_app,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=allowed_methods,
    allow_headers=allowed_headers,
    expose_headers=exposed_headers,
    max_age=86400,
)
