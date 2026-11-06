from typing import List, Optional, Union, Literal, Any
from pydantic import BaseModel
from app.schemas.common import SampleType, LabStatus
from app.schemas.service import ServiceSchema


class ResultRow(BaseModel):
    name: str
    value: float
    unit: str
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None


class LabResultValues(BaseModel):
    type: Literal["values"] = "values"
    rows: List[ResultRow]
    sample: SampleType
    note: str = ""


class LabResultFile(BaseModel):
    type: Literal["file"] = "file"
    file_name: str
    file_type: str
    data_url: str
    note: Optional[str] = ""


class LabResultNumber(BaseModel):
    type: Literal["number"] = "number"
    value: float
    unit: str


LabResult = Union[LabResultValues, LabResultFile, LabResultNumber]


class ResultEdit(BaseModel):
    at: str
    by: str
    before: Any


class LabOrderSchema(BaseModel):
    id: int
    patient_name: str
    doctor_name: str
    test: ServiceSchema
    status: LabStatus
    result: Optional[Any] = None
    history: List[ResultEdit]
    requested_at: str


class TestResult(BaseModel):
    id: int
    patient_name: str
    test: ServiceSchema
    result: Any
    confirmed_at: str


class ResultInputValues(BaseModel):
    type: Literal["values"] = "values"
    rows: List[ResultRow]
    sample: SampleType
    note: str = ""
