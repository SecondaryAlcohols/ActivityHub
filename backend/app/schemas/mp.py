from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.activity import FormField
from app.schemas.registration import RegistrationOut, SignupState


class MpLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=128)


class AttendeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    avatar_url: str | None = None
    phone: str | None = None


class MpLoginResult(BaseModel):
    access_token: str
    attendee: AttendeeOut


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    avatar_url: str | None = Field(default=None, max_length=500)

    def is_empty(self) -> bool:
        return self.nickname is None and self.avatar_url is None


class MpActivityItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    cover_url: str | None = None
    summary: str | None = None
    location_name: str
    start_at: datetime
    end_at: datetime
    signup_start_at: datetime
    signup_end_at: datetime
    capacity: int
    taken_count: int
    remaining: int
    need_review: bool
    allow_cancel: bool = True
    cancel_deadline: datetime | None = None
    status: str


class MpActivityDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    cover_url: str | None = None
    summary: str | None = None
    description: str | None = None
    location_name: str
    address: str | None = None
    start_at: datetime
    end_at: datetime
    signup_start_at: datetime
    signup_end_at: datetime
    capacity: int
    taken_count: int
    remaining: int
    need_review: bool
    allow_cancel: bool
    cancel_deadline: datetime | None = None
    status: str
    form_schema: list[FormField] = Field(default_factory=list)
    my_registration: RegistrationOut | None = None
    signup_state: SignupState


class MpRegistrationItem(RegistrationOut):
    activity: MpActivityItem


class MpRegistrationDetail(RegistrationOut):
    activity: MpActivityItem
    form_schema: list[FormField] = Field(default_factory=list)
