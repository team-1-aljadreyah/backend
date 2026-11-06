from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class AppException(HTTPException):
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        message: str = "An error occurred",
        code: Optional[str] = None,
        errors: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=message)
        self.message = message
        self.code = code
        self.errors = errors or {}


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Invalid credentials", code: str = "invalid_credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=message,
            code=code,
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "Access forbidden", code: str = "forbidden"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            message=message,
            code=code,
        )


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "not_found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message=message,
            code=code,
        )


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict", code: str = "conflict"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            message=message,
            code=code,
        )


class UnprocessableEntityException(AppException):
    def __init__(self, message: str = "Validation failed", code: str = "validation_error", errors: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=message,
            code=code,
            errors=errors,
        )
