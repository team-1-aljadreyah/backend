import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import (
    UnauthorizedException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnprocessableEntityException,
)
from app.core.security import (
    normalize_phone_local,
    normalize_patient_name,
    verify_password,
    get_password_hash,
    needs_rehash,
    create_access_token,
    create_refresh_token,
    decode_token,
    validate_three_part_name,
)
from app.database.models.profile import Profile, UserSession, PasswordResetOTP
from app.database.models.patient import Patient
from app.database.models.governance import Notification
from app.schemas.auth import LoginRequest, RegisterRequest, LoginResponse, UserSchema
from app.services.audit_service import log_audit
from app.integrations.supabase_auth import supabase_auth


_reset_codes: Dict[str, dict] = {}


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def _hash_otp(phone: str, code: str) -> str:
    raw = f"{phone}:{code}:{settings.SECRET_KEY}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def login(db: AsyncSession, req: LoginRequest) -> LoginResponse:
    phone = normalize_phone_local(req.phone)
    stmt = select(Profile).where(Profile.phone == phone)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        raise UnauthorizedException(message="Invalid phone number or password", code="invalid_credentials")

    if not user.is_active:
        raise ForbiddenException(message="Account is disabled", code="account_disabled")

    valid_pw = verify_password(req.password, user.password_hash or "")
    if not valid_pw:
        raise UnauthorizedException(message="Invalid phone number or password", code="invalid_credentials")

    # Transparent migration to modern Argon2id hash
    if needs_rehash(user.password_hash or ""):
        user.password_hash = get_password_hash(req.password)
        await db.flush()

    jti = secrets.token_hex(16)
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id), "role": user.role}, jti=jti)

    # Persist refresh token session
    token_hash = _hash_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        jti=jti,
        expires_at=expires_at,
    )
    db.add(session)

    await log_audit(db, user, "auth.login", user.name)
    await db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserSchema(
            id=user.id,
            name=user.name,
            phone=user.phone,
            role=user.role,
            doctor_id=user.doctor_id,
        ),
    )


async def register(db: AsyncSession, req: RegisterRequest) -> LoginResponse:
    validate_three_part_name(req.name)
    phone = normalize_phone_local(req.phone)
    norm_name = normalize_patient_name(req.name)
    norm_phone = normalize_phone_local(phone)

    # 1. Check if profile with this phone already exists
    stmt_prof = select(Profile).where(Profile.phone == phone)
    res_prof = await db.execute(stmt_prof)
    if res_prof.scalar_one_or_none():
        raise ConflictException(message="Phone number is already registered", code="phone_taken")

    # 2. Check if active patient record with same normalized phone and name already exists
    # If an existing walk-in matches: do not automatically claim or link it, do not delete it,
    # and do not bypass the unique index. Return a controlled 409 Conflict requiring authorized staff review.
    stmt_pat = select(Patient).where(
        Patient.normalized_phone == norm_phone,
        Patient.normalized_name == norm_name,
        Patient.merged_into_patient_id.is_(None),
    )
    res_pat = await db.execute(stmt_pat)
    existing_patient = res_pat.scalar_one_or_none()
    if existing_patient:
        logger.warning(
            f"Registration blocked: unlinked/active patient record already exists for phone [MASKED] and name [MASKED] (patient_id={existing_patient.id})"
        )
        raise ConflictException(
            message="A patient record with this phone number and name already exists. Please visit reception to link your account.",
            code="patient_record_exists",
        )

    try:
        hashed_pw = get_password_hash(req.password)
        user = Profile(
            name=req.name.strip(),
            phone=phone,
            password_hash=hashed_pw,
            role="patient",
        )
        db.add(user)
        await db.flush()

        # Create new isolated patient record (relation='self')
        new_patient = Patient(
            name=req.name.strip(),
            phone=phone,
            normalized_name=norm_name,
            normalized_phone=norm_phone,
            account_id=user.id,
            relation="self",
            allergies=[],
            conditions=[],
        )
        db.add(new_patient)
        await db.flush()

        jti = secrets.token_hex(16)
        access_token = create_access_token({"sub": str(user.id), "role": user.role})
        refresh_token = create_refresh_token({"sub": str(user.id), "role": user.role}, jti=jti)

        token_hash = _hash_token(refresh_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session = UserSession(
            user_id=user.id,
            token_hash=token_hash,
            jti=jti,
            expires_at=expires_at,
        )
        db.add(session)

        await log_audit(db, user, "account.register", user.name)
        await db.commit()

    except IntegrityError as exc:
        await db.rollback()
        err_str = str(exc.orig if hasattr(exc, "orig") else exc).lower()
        if "idx_unique_active_patient_phone_name" in err_str or ("patients" in err_str and "unique" in err_str):
            logger.warning("Registration integrity conflict on idx_unique_active_patient_phone_name")
            raise ConflictException(
                message="A patient record with this phone number and name already exists. Please visit reception to link your account.",
                code="patient_record_exists",
            )
        elif "profiles_phone_key" in err_str or ("profiles" in err_str and "phone" in err_str):
            logger.warning("Registration integrity conflict on profile phone uniqueness")
            raise ConflictException(
                message="Phone number is already registered",
                code="phone_taken",
            )
        else:
            logger.error(f"Unexpected database integrity error during registration: {exc}", exc_info=True)
            raise
    except (ConflictException, UnprocessableEntityException):
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(f"Unhandled registration database error: {exc}", exc_info=True)
        raise

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserSchema(
            id=user.id,
            name=user.name,
            phone=user.phone,
            role=user.role,
            doctor_id=user.doctor_id,
        ),
    )


async def refresh_tokens(db: AsyncSession, refresh_token_str: str) -> LoginResponse:
    payload = decode_token(refresh_token_str)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedException(message="Invalid or expired refresh token", code="invalid_token")

    token_hash = _hash_token(refresh_token_str)
    stmt_sess = select(UserSession).where(UserSession.token_hash == token_hash)
    res_sess = await db.execute(stmt_sess)
    user_session = res_sess.scalar_one_or_none()

    now_utc = datetime.now(timezone.utc)

    # Detect reuse: if token session exists but was already revoked, potential token theft!
    if user_session and user_session.revoked_at is not None:
        # Revoke all active sessions for this user to mitigate breach
        await db.execute(
            update(UserSession)
            .where(UserSession.user_id == user_session.user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now_utc)
        )
        await db.commit()
        raise UnauthorizedException(message="Refresh token was revoked. All sessions invalidated.", code="token_revoked")

    if not user_session or ensure_utc(user_session.expires_at) < now_utc:
        raise UnauthorizedException(message="Invalid or expired refresh token", code="invalid_token")

    try:
        user_id = int(payload.get("sub") or payload.get("user_id"))
    except (TypeError, ValueError):
        raise UnauthorizedException(message="Malformed token claims", code="invalid_token")

    stmt = select(Profile).where(Profile.id == user_id, Profile.is_active == True)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        raise UnauthorizedException(message="User not found or disabled", code="user_not_found")

    # Rotate refresh token: revoke old session and issue new one
    user_session.revoked_at = now_utc

    new_jti = secrets.token_hex(16)
    new_access_token = create_access_token({"sub": str(user.id), "role": user.role})
    new_refresh_token = create_refresh_token({"sub": str(user.id), "role": user.role}, jti=new_jti)

    new_token_hash = _hash_token(new_refresh_token)
    new_expires_at = now_utc + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_session = UserSession(
        user_id=user.id,
        token_hash=new_token_hash,
        jti=new_jti,
        expires_at=new_expires_at,
    )
    db.add(new_session)
    await db.commit()

    return LoginResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user=UserSchema(
            id=user.id,
            name=user.name,
            phone=user.phone,
            role=user.role,
            doctor_id=user.doctor_id,
        ),
    )


async def logout(db: AsyncSession, current_user: Profile, refresh_token_str: Optional[str] = None):
    now_utc = datetime.now(timezone.utc)
    if refresh_token_str:
        token_hash = _hash_token(refresh_token_str)
        await db.execute(
            update(UserSession)
            .where(UserSession.token_hash == token_hash)
            .values(revoked_at=now_utc)
        )
    else:
        # Revoke all sessions for this user
        await db.execute(
            update(UserSession)
            .where(UserSession.user_id == current_user.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now_utc)
        )
    await log_audit(db, current_user, "auth.logout", current_user.name)
    await db.commit()


async def delete_my_account(db: AsyncSession, current_user: Profile, password: str):
    if not verify_password(password, current_user.password_hash or ""):
        raise UnauthorizedException(message="Incorrect password", code="wrong_password")

    # Revoke all active sessions
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == current_user.id)
        .values(revoked_at=datetime.now(timezone.utc))
    )
    # The login goes away, but medical files stay unlinked (account_id = None)
    await db.execute(
        update(Patient).where(Patient.account_id == current_user.id).values(account_id=None)
    )
    await db.execute(
        delete(Notification).where(Notification.user_id == current_user.id)
    )
    await log_audit(db, current_user, "account.delete", current_user.name)
    await db.delete(current_user)
    await db.commit()


async def change_password(db: AsyncSession, current_user: Profile, current_password: str, new_password: str):
    valid = verify_password(current_password, current_user.password_hash or "")
    if not valid:
        raise UnprocessableEntityException(message="Wrong current password", code="wrong_password")

    current_user.password_hash = get_password_hash(new_password)

    # Invalidate all existing sessions upon password change
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == current_user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await log_audit(db, current_user, "account.change_password", current_user.name)
    await db.commit()


async def forgot_password(db: AsyncSession, phone: str) -> Dict[str, Any]:
    norm_phone = normalize_phone_local(phone)
    now_utc = datetime.now(timezone.utc)

    stmt = select(Profile).where(Profile.phone == norm_phone)
    user = (await db.execute(stmt)).scalar_one_or_none()

    res = {"expires_in_minutes": 10}
    if not user:
        # Uniform timing / response to prevent phone enumeration
        return res

    # Check cooldown
    stmt_otp = select(PasswordResetOTP).where(PasswordResetOTP.phone == norm_phone)
    existing_otp = (await db.execute(stmt_otp)).scalar_one_or_none()

    if existing_otp and ensure_utc(existing_otp.cooldown_until) > now_utc:
        # Respect 60s cooldown without giving attackers timing cues
        return res

    # Generate cryptographically secure 6-digit OTP
    code_int = secrets.randbelow(900000) + 100000
    code = f"{code_int:06d}"
    otp_hash = _hash_otp(norm_phone, code)

    expires_at = now_utc + timedelta(minutes=10)
    cooldown_until = now_utc + timedelta(seconds=60)

    # In test/dev environment, store code in memory for automated test harness verification
    if settings.APP_ENV in ("development", "testing"):
        _reset_codes[norm_phone] = {"code": code, "expires_at": expires_at}
        _reset_codes[phone] = {"code": code, "expires_at": expires_at}

    if existing_otp:
        existing_otp.otp_hash = otp_hash
        existing_otp.attempts = 0
        existing_otp.cooldown_until = cooldown_until
        existing_otp.expires_at = expires_at
    else:
        new_otp = PasswordResetOTP(
            phone=norm_phone,
            otp_hash=otp_hash,
            attempts=0,
            cooldown_until=cooldown_until,
            expires_at=expires_at,
        )
        db.add(new_otp)

    # Dispatch via SMS provider if enabled
    try:
        await supabase_auth.send_phone_otp(norm_phone)
    except Exception:
        pass

    await db.commit()
    return res


async def reset_password(db: AsyncSession, phone: str, code: str, new_password: str):
    norm_phone = normalize_phone_local(phone)
    now_utc = datetime.now(timezone.utc)

    stmt_otp = select(PasswordResetOTP).where(PasswordResetOTP.phone == norm_phone)
    otp_record = (await db.execute(stmt_otp)).scalar_one_or_none()

    if not otp_record or ensure_utc(otp_record.expires_at) < now_utc:
        raise UnprocessableEntityException(message="Reset code expired or not found", code="code_expired")

    if otp_record.attempts >= 5:
        await db.delete(otp_record)
        await db.commit()
        raise UnprocessableEntityException(message="Too many failed attempts. Request a new code.", code="too_many_tries")

    expected_hash = _hash_otp(norm_phone, code.strip())
    if not secrets.compare_digest(otp_record.otp_hash, expected_hash):
        otp_record.attempts += 1
        await db.commit()
        raise UnprocessableEntityException(message="Invalid verification code", code="code_wrong")

    stmt_user = select(Profile).where(Profile.phone == norm_phone)
    user = (await db.execute(stmt_user)).scalar_one_or_none()
    if not user:
        raise NotFoundException(message="User not found", code="user_not_found")

    user.password_hash = get_password_hash(new_password)

    # Revoke all active sessions for this user on password reset
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now_utc)
    )

    # One-time consumption of OTP
    await db.delete(otp_record)
    await log_audit(db, user, "account.reset_password", user.name)
    await db.commit()
