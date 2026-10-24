"""报名与电子票契约。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import RegistrationStatus
from app.schemas.user import MyRegistrationItem


class RegistrationResult(BaseModel):
    id: UUID
    event_id: UUID
    status: RegistrationStatus
    ticket_code: str
    applied_at: datetime
    requires_approval: bool
    message: str


class TicketOut(BaseModel):
    ticket_token: str = Field(..., description="HMAC 签名票据，可离线校验防伪")
    ticket_code: str
    event_id: UUID
    event_title: str
    holder_name: str
    student_no: str
    valid_until: datetime


class MyRegistrations(BaseModel):
    items: list[MyRegistrationItem]
    total: int
