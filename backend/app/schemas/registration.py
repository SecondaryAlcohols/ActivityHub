from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.activity import FormField

RegistrationStatus = Literal["pending", "approved", "rejected", "cancelled"]
SignupReason = Literal[
    "not_started",
    "closed",
    "full",
    "already_registered",
    "activity_closed",
]


class SignupState(BaseModel):
    can_signup: bool
    reason: SignupReason | None = None


class RegistrationCreate(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class RegistrationReview(BaseModel):
    action: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_note(self):
        if self.action == "reject" and not (self.note or "").strip():
            raise ValueError("拒绝报名必须填写原因")
        return self


class RegistrationBatchReview(RegistrationReview):
    ids: list[int] = Field(min_length=1, max_length=100)


class BatchReviewResult(BaseModel):
    approved: int = 0
    rejected: int = 0
    skipped: int = 0


class RegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activity_id: int
    status: RegistrationStatus
    applicant_name: str
    applicant_phone: str
    answers: dict[str, Any]
    reviewed_at: datetime | None = None
    review_note: str | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ActivityBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    cover_url: str | None = None
    location_name: str
    start_at: datetime
    end_at: datetime
    capacity: int
    taken_count: int
    need_review: bool
    status: str


class AttendeeBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    avatar_url: str | None = None
    phone: str | None = None


class AdminRegistrationItem(RegistrationOut):
    attendee_nickname: str = ""


class AdminRegistrationDetail(RegistrationOut):
    activity: ActivityBrief | None = None
    form_schema: list[FormField] = Field(default_factory=list)
    attendee: AttendeeBrief | None = None


class RegistrationStats(BaseModel):
    total: int
    pending: int
    approved: int
    rejected: int
    cancelled: int
    capacity: int
    remaining: int
    signup_rate: int


class TicketOut(BaseModel):
    token: str
    registration_id: int
    activity_id: int
    activity_title: str
    applicant_name: str
    status: RegistrationStatus
    start_at: datetime
    end_at: datetime
    location_name: str
