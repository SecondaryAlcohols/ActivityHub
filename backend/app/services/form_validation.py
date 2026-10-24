"""按活动 form_schema 校验报名答案。"""

import re
from datetime import date, datetime
from typing import Any

from app.core.errors import AppError

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_TEXT_LENGTH = 200
MAX_TEXTAREA_LENGTH = 2000
MAX_MULTI_SELECT = 50


class FormValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(422, message, 42210)


def _invalid(label: str, message: str) -> FormValidationError:
    return FormValidationError(f"「{label}」{message}")


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def _clean_value(field: dict, raw: Any) -> Any:
    label = str(field.get("label") or field.get("key") or "字段")
    field_type = field.get("type") or "text"

    if field_type == "multi_select":
        options = [str(option) for option in (field.get("options") or [])]
        values = raw if isinstance(raw, (list, tuple)) else [raw]
        cleaned: list[str] = []
        for item in values:
            if _is_blank(item):
                continue
            text = str(item).strip()
            if text not in options:
                raise _invalid(label, f"包含无效选项：{text}")
            if text not in cleaned:
                cleaned.append(text)
        if len(cleaned) > MAX_MULTI_SELECT:
            raise _invalid(label, f"最多选择 {MAX_MULTI_SELECT} 项")
        return cleaned

    if isinstance(raw, (list, tuple, dict)):
        raise _invalid(label, "格式不正确")

    text = str(raw).strip()

    if field_type == "phone":
        if not PHONE_RE.match(text):
            raise _invalid(label, "不是有效的手机号")
        return text

    if field_type == "email":
        if len(text) > 200 or not EMAIL_RE.match(text):
            raise _invalid(label, "不是有效的邮箱地址")
        return text

    if field_type == "number":
        try:
            float(text)
        except ValueError as exc:
            raise _invalid(label, "必须是数字") from exc
        return text

    if field_type == "select":
        options = [str(option) for option in (field.get("options") or [])]
        if text not in options:
            raise _invalid(label, f"包含无效选项：{text}")
        return text

    if field_type == "date":
        try:
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            try:
                date.fromisoformat(text)
            except ValueError as exc:
                raise _invalid(label, "日期格式应为 YYYY-MM-DD") from exc
        return text

    limit = MAX_TEXTAREA_LENGTH if field_type == "textarea" else MAX_TEXT_LENGTH
    if len(text) > limit:
        raise _invalid(label, f"不能超过 {limit} 个字符")
    return text


def validate_answers(
    schema: list[dict], answers: dict[str, Any] | None
) -> tuple[dict[str, Any], str, str]:
    """返回 (清洗后的答案, 姓名, 手机号)。"""
    if not isinstance(answers, dict):
        raise FormValidationError("报名信息格式不正确")

    cleaned: dict[str, Any] = {}
    for field in schema or []:
        key = field.get("key")
        if not key:
            continue
        label = str(field.get("label") or key)
        raw = answers.get(key)
        required = bool(field.get("required"))

        if field.get("type") == "multi_select":
            value = _clean_value(field, raw) if not _is_blank(raw) else []
            if required and not value:
                raise FormValidationError(f"请填写「{label}」")
            if value:
                cleaned[key] = value
            continue

        if _is_blank(raw):
            if required:
                raise FormValidationError(f"请填写「{label}」")
            continue

        cleaned[key] = _clean_value(field, raw)

    name = str(cleaned.get("name", "")).strip()
    phone = str(cleaned.get("phone", "")).strip()
    if not name:
        raise FormValidationError("请填写姓名")
    if not phone:
        raise FormValidationError("请填写手机号")
    if not PHONE_RE.match(phone):
        raise FormValidationError("「手机号」不是有效的手机号")

    return cleaned, name, phone
