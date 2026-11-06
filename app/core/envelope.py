from typing import Generic, Optional, TypeVar, Any, Dict
from pydantic import BaseModel

T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: str = "Operation completed successfully"


class ErrorEnvelope(BaseModel):
    success: bool = False
    message: str
    code: Optional[str] = None
    errors: Optional[Dict[str, Any]] = None


def success_response(data: Any = None, message: str = "Operation completed successfully") -> Dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "message": message,
    }
