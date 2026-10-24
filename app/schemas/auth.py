"""认证与账号契约。"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import UserRole
from app.schemas.common import ORMModel

PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
STUDENT_NO_PATTERN = re.compile(r"^[A-Za-z0-9]{4,32}$")


class LoginRequest(BaseModel):
    account: str = Field(..., min_length=4, max_length=32, description="学号或手机号")
    password: str = Field(..., min_length=8, max_length=64)


class RegisterRequest(BaseModel):
    student_no: str = Field(..., min_length=4, max_length=32, examples=["2023010118"])
    name: str = Field(..., min_length=1, max_length=64, examples=["陈雨桐"])
    password: str = Field(..., min_length=8, max_length=64)
    phone: str | None = Field(None, description="手机号，选填但需唯一")
    email: str | None = Field(None, max_length=120)
    college: str | None = Field(None, max_length=120)

    @field_validator("student_no")
    @classmethod
    def _valid_student_no(cls, value: str) -> str:
        if not STUDENT_NO_PATTERN.fullmatch(value):
            raise ValueError("学号只能包含字母与数字，长度 4-32 位")
        return value.upper()

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not PHONE_PATTERN.fullmatch(value):
            raise ValueError("手机号格式不正确")
        return value

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if value.isdigit() or value.isalpha():
            raise ValueError("密码需同时包含字母与数字")
        return value


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="访问令牌有效期（秒）")
    refresh_expires_in: int = Field(..., description="刷新令牌有效期（秒）")


class UserProfile(ORMModel):
    id: UUID
    student_no: str
    name: str
    phone: str | None = None
    email: str | None = None
    college: str | None = None
    role: UserRole
    has_face: bool = Field(False, description="是否已录入人脸特征")
    created_at: datetime


class FaceEnrollRequest(BaseModel):
    image: str = Field(..., min_length=8, description="人脸图像 base64（仅在内存中比对，不落库）")


class FaceEnrollResponse(BaseModel):
    provider: str
    enrolled_at: datetime
