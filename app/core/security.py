import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from app.core.config import settings


def normalize_phone_local(phone: str) -> str:
    """
    Normalizes phone numbers to Iraqi local format (07XXXXXXXXX).
    """
    if not phone:
        return ""
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if cleaned.startswith("+964"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("00964"):
        cleaned = "0" + cleaned[5:]
    elif cleaned.startswith("964"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("7") and len(cleaned) == 10:
        cleaned = "0" + cleaned
    return cleaned


def normalize_patient_name(name: str) -> str:
    """
    Normalizes Arabic names by unifying Alef forms, Taa Marbuta, Yaa,
    stripping diacritics/tashkeel and redundant spaces.
    """
    if not name:
        return ""
    s = name.strip()
    # Remove diacritics / tashkeel and tatweel
    s = re.sub(r"[\u064B-\u0652\u0640]", "", s)
    # Normalize Alefs
    s = re.sub(r"[أإآٱ]", "ا", s)
    # Normalize Taa Marbuta
    s = re.sub(r"ة", "ه", s)
    # Normalize Alef Maksura / Yaa
    s = re.sub(r"[ىي]", "ي", s)
    s = re.sub(r"ؤ", "و", s)
    s = re.sub(r"ئ", "ي", s)
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def normalize_role(role: Optional[str]) -> Optional[str]:
    """
    Normalizes a role/job filter string into a standard Profile.role identifier.
    Supports English and Arabic aliases, plurals, and phrases (e.g. 'doctors only', 'الأطباء فقط').
    Returns None if 'all', empty, or indicating no filter.
    """
    if not role:
        return None
    r = role.strip().lower()
    if not r:
        return None

    # Handle 'all' variants
    if r in {
        "all",
        "all roles",
        "all jobs",
        "all_roles",
        "all_jobs",
        "allroles",
        "none",
        "any",
        "الكل",
        "كل",
        "كل الوظائف",
        "جميع الوظائف",
        "كل الأدوار",
        "جميع الأدوار",
    }:
        return None

    valid_roles = {"patient", "reception", "doctor", "pharmacy", "manager", "lab", "accountant"}
    if r in valid_roles:
        return r

    role_mappings = {
        # Doctor
        "doctors": "doctor",
        "doctors only": "doctor",
        "doctor only": "doctor",
        "doctors_only": "doctor",
        "dr": "doctor",
        "physician": "doctor",
        "physicians": "doctor",
        "طبيب": "doctor",
        "الأطباء": "doctor",
        "الاطباء": "doctor",
        "أطباء": "doctor",
        "اطباء": "doctor",
        "دكتور": "doctor",
        "دكاترة": "doctor",
        "الأطباء فقط": "doctor",
        "طبيب فقط": "doctor",
        # Reception
        "receptionist": "reception",
        "receptionists": "reception",
        "reception only": "reception",
        "frontdesk": "reception",
        "front desk": "reception",
        "استقبال": "reception",
        "الاستقبال": "reception",
        "موظف استقبال": "reception",
        "موظفي الاستقبال": "reception",
        # Manager
        "managers": "manager",
        "manager only": "manager",
        "admin": "manager",
        "admins": "manager",
        "administrator": "manager",
        "administrators": "manager",
        "management": "manager",
        "مدير": "manager",
        "المدير": "manager",
        "مدراء": "manager",
        "إدارة": "manager",
        "ادارة": "manager",
        # Pharmacy
        "pharmacist": "pharmacy",
        "pharmacists": "pharmacy",
        "pharmacy only": "pharmacy",
        "pharmacist only": "pharmacy",
        "صيدلية": "pharmacy",
        "الصيدلية": "pharmacy",
        "صيدلي": "pharmacy",
        "صيادلة": "pharmacy",
        # Lab
        "labs": "lab",
        "laboratory": "lab",
        "laboratories": "lab",
        "lab only": "lab",
        "lab technician": "lab",
        "lab technicians": "lab",
        "مختبر": "lab",
        "المختبر": "lab",
        "تحاليل": "lab",
        "فني مختبر": "lab",
        # Accountant
        "accountants": "accountant",
        "accountant only": "accountant",
        "accounting": "accountant",
        "finance": "accountant",
        "محاسب": "accountant",
        "المحاسب": "accountant",
        "محاسبين": "accountant",
        "محاسبة": "accountant",
        "مالية": "accountant",
        # Patient
        "patients": "patient",
        "patient only": "patient",
        "مريض": "patient",
        "المريض": "patient",
        "مرضى": "patient",
    }

    if r in role_mappings:
        return role_mappings[r]

    for key, role_val in role_mappings.items():
        if key in r:
            return role_val

    for std_role in valid_roles:
        if std_role in r:
            return std_role

    return r


# ---------------------------------------------------------------------------
# Arabic / English Three-Part Name Validation (First, Father, Grandfather)
# ---------------------------------------------------------------------------

COMPOUND_PREFIXES = {
    "عبد", "ابو", "أبو", "ابي", "أبي", "ابا", "أبا", "ام", "أم", "ابن", "ابنة", "بنت", "آل"
}
COMPOUND_SUFFIXES = {"الدين", "الله", "الاسلام", "الإسلام"}
TITLES = {
    "د.", "د/", "د", "دكتور", "دكتورة", "الدكتور", "الدكتورة",
    "أ.", "أ/", "أستاذ", "أستاذة", "الأستاذ", "الأستاذة",
    "م.", "مهندس", "مهندسة", "المهندس", "المهندسة",
    "سيد", "سيدة", "السيد", "السيدة",
    "شيخ", "شيخة", "الشيخ", "الشيخة",
    "حاج", "حاجة", "الحاج", "الحاجة",
    "dr.", "dr", "mr.", "mr", "mrs.", "mrs", "ms.", "ms"
}


def extract_name_parts(raw_name: str) -> list[str]:
    """
    Extracts name parts by stripping honorary titles and treating compound
    prefixes (like 'عبد الكريم' or 'أبو بكر') and suffixes as a single part.
    """
    text = (raw_name or "").strip()
    words = text.split()
    if not words:
        return []

    # Strip leading titles
    first_clean = words[0].rstrip(".").strip()
    if words[0].lower() in TITLES or first_clean.lower() in TITLES:
        words = words[1:]

    merged = []
    i = 0
    while i < len(words):
        w = words[i].strip()
        if not w:
            i += 1
            continue

        # Check prefix compounds (e.g. عبد الكريم, أبو بكر)
        if w in COMPOUND_PREFIXES and i + 1 < len(words):
            merged.append(f"{w} {words[i+1]}")
            i += 2
            continue

        # Check suffix compounds (e.g. نور الدين, فضل الله)
        if i + 1 < len(words) and words[i+1] in COMPOUND_SUFFIXES:
            merged.append(f"{w} {words[i+1]}")
            i += 2
            continue

        # Check common double names like 'محمد علي' when exactly 4 words remain
        if w == "محمد" and i + 1 < len(words) and words[i+1] in {"علي", "حسن", "حسين", "باقر", "صادق", "مهدي", "رضا", "جواد", "كاظم", "أمين", "امين"}:
            remaining_after_pair = len(words) - (i + 2)
            if remaining_after_pair == 2:
                merged.append(f"{w} {words[i+1]}")
                i += 2
                continue

        merged.append(w)
        i += 1
    return merged


def validate_three_part_name(name: str):
    """
    Validates that a name consists of exactly three parts (name, father, grandfather).
    Rejects names that have fewer or more than 3 parts.
    """
    parts = extract_name_parts(name)
    if len(parts) != 3:
        from app.core.exceptions import UnprocessableEntityException
        raise UnprocessableEntityException(
            message="Name must be exactly three parts (name, father, grandfather)",
            code="invalid_name",
        )


def normalize_phone_e164(phone: str) -> str:
    """
    Normalizes phone numbers to international E.164 format (+9647XXXXXXXXX).
    """
    local = normalize_phone_local(phone)
    if local.startswith("0") and len(local) == 11:
        return "+964" + local[1:]
    if local.startswith("+"):
        return local
    return "+964" + local


# ---------------------------------------------------------------------------
# Password Hashing (Argon2id with safe migration from Bcrypt & PBKDF2)
# ---------------------------------------------------------------------------

import argon2
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
import bcrypt
import jwt

_argon2_hasher = argon2.PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def get_password_hash(password: str) -> str:
    """
    Hashes a plain password using Argon2id.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    return _argon2_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a password against an Argon2id, bcrypt, or PBKDF2 hash.
    Provides transparent migration support for legacy hashes without hardcoded bypasses.
    Rejects plaintext passwords and insecure fallbacks.
    """
    if not hashed_password or not plain_password:
        return False

    # 1. Argon2id hash
    if hashed_password.startswith("$argon2"):
        try:
            return _argon2_hasher.verify(hashed_password, plain_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    # 2. Bcrypt hash ($2a$, $2b$, $2y$)
    if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False

    # 3. PBKDF2 hash (pbkdf2:sha256:...)
    if hashed_password.startswith("pbkdf2:sha256:"):
        try:
            parts = hashed_password.split("$")
            iterations = int(parts[0].split(":")[2])
            salt = parts[1]
            key_hex = parts[2]
            computed = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations,
            ).hex()
            return hmac.compare_digest(computed, key_hex)
        except Exception:
            return False

    return False


def needs_rehash(hashed_password: str) -> bool:
    """
    Determines if a stored hash should be upgraded to modern Argon2id upon next authentication.
    """
    if not hashed_password or not hashed_password.startswith("$argon2"):
        return True
    try:
        return _argon2_hasher.check_needs_rehash(hashed_password)
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Strict Cryptographic JWT Implementation (PyJWT with HS256 algorithm enforcement)
# ---------------------------------------------------------------------------

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": now_utc,
        "nbf": now_utc,
        "type": "access",
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None, jti: Optional[str] = None) -> str:
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    token_jti = jti or secrets.token_hex(16)
    to_encode.update({
        "exp": expire,
        "iat": now_utc,
        "nbf": now_utc,
        "type": "refresh",
        "jti": token_jti,
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Strict cryptographic verification of JWT token signature, expiration, and claims.
    Rejects unsigned, malformed, expired, or mock tokens.
    """
    if not token or not isinstance(token, str):
        return {}
    try:
        payload = jwt.decode(
            token.strip(),
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={
                "require": ["exp", "iat", "type"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_signature": True,
            },
        )
        return payload
    except Exception:
        return {}


def create_file_download_token(
    filename: str,
    bucket: str,
    user_id: int,
    role: str,
    expires_in_seconds: int = 3600,
) -> str:
    """
    Creates a secure, signed short-lived token for authenticated file downloads.
    Enables secure image rendering in standard frontend <img> tags without exposing Bearer tokens.
    """
    now_utc = datetime.now(timezone.utc)
    expire = now_utc + timedelta(seconds=expires_in_seconds)
    payload = {
        "sub": str(user_id),
        "role": role,
        "bucket": bucket,
        "filename": filename,
        "type": "file_download",
        "iat": now_utc,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_file_download_token(
    token: str,
    filename: str,
    bucket: str,
) -> Optional[Dict[str, Any]]:
    """
    Cryptographically verifies a file download token against the requested bucket and filename.
    """
    if not token or not isinstance(token, str):
        return None
    try:
        payload = jwt.decode(
            token.strip(),
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "type"], "verify_exp": True, "verify_signature": True},
        )
        if payload.get("type") != "file_download":
            return None
        if payload.get("bucket") != bucket or payload.get("filename") != filename:
            return None
        return {
            "user_id": int(payload["sub"]),
            "role": payload.get("role", "patient"),
        }
    except Exception:
        return None
