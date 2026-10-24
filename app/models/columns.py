"""通用列类型工厂。"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum


def enum_type(enum_cls: type[Enum], name: str) -> SAEnum:
    """PostgreSQL 原生枚举，数据库存枚举值（小写）而非成员名。"""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        native_enum=True,
        validate_strings=True,
    )
