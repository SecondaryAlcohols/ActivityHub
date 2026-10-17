from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FieldType = Literal[
    "text",
    "textarea",
    "phone",
    "email",
    "number",
    "select",
    "multi_select",
    "date",
]

ActivityStatus = Literal["draft", "published", "closed", "finished"]


class FormField(BaseModel):
    key: str = Field(
        min_length=1, max_length=64, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$"
    )
    label: str = Field(min_length=1, max_length=64)
    type: FieldType
    required: bool = False
    placeholder: str | None = Field(default=None, max_length=200)
    options: list[str] | None = None
    system: bool = False

    @model_validator(mode="after")
    def validate_options(self):
        if self.type in ("select", "multi_select"):
            if not self.options:
                raise ValueError(f"字段「{self.label}」需要配置选项")
        return self


def default_form_schema() -> list[FormField]:
    return [
        FormField(
            key="name",
            label="姓名",
            type="text",
            required=True,
            system=True,
        ),
        FormField(
            key="phone",
            label="手机号",
            type="phone",
            required=True,
            system=True,
        ),
    ]


class ActivityBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    cover_url: str | None = Field(default=None, max_length=500)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = None
    location_name: str = Field(min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    start_at: datetime
    end_at: datetime
    signup_start_at: datetime
    signup_end_at: datetime
    checkin_open_at: datetime | None = None
    checkin_close_at: datetime | None = None
    capacity: int = Field(ge=1, le=100000)
    need_review: bool = False
    allow_cancel: bool = True
    cancel_deadline: datetime | None = None
    form_schema: list[FormField] = Field(default_factory=default_form_schema)

    @model_validator(mode="after")
    def validate_rules(self):
        if self.end_at <= self.start_at:
            raise ValueError("活动结束时间必须晚于开始时间")
        if self.signup_end_at <= self.signup_start_at:
            raise ValueError("报名截止时间必须晚于报名开始时间")
        if self.signup_end_at > self.end_at:
            raise ValueError("报名截止时间不能晚于活动结束时间")
        if (
            self.checkin_open_at
            and self.checkin_close_at
            and self.checkin_close_at <= self.checkin_open_at
        ):
            raise ValueError("签到关闭时间必须晚于签到开放时间")

        keys = [field.key for field in self.form_schema]
        if len(keys) != len(set(keys)):
            raise ValueError("报名表单中存在重复的字段标识")
        missing = {"name", "phone"} - set(keys)
        if missing:
            raise ValueError(
                "报名表单缺少系统字段: " + ", ".join(sorted(missing))
            )
        return self


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(ActivityBase):
    version: int = Field(ge=1)


class ActivityOut(ActivityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ActivityStatus
    version: int
    taken_count: int
    created_by: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ActivityListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    cover_url: str | None
    location_name: str
    start_at: datetime
    end_at: datetime
    capacity: int
    taken_count: int
    need_review: bool
    status: ActivityStatus
    created_at: datetime
