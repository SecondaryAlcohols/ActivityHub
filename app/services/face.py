"""人脸录入与状态查询。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_text
from app.models.enums import AuditAction
from app.models.user import FaceTemplate, User
from app.providers.face import decode_image_payload, get_face_provider
from app.schemas.auth import FaceEnrollResponse
from app.schemas.user import FaceStatus
from app.services import audit
from app.utils.time import utcnow

PRIVACY_NOTE = "仅保存加密后的人脸特征值，原始照片不落库；特征仅用于本系统考勤比对。"


async def enroll(session: AsyncSession, user: User, image_payload: str, ip: str) -> FaceEnrollResponse:
    image = decode_image_payload(image_payload)
    provider = get_face_provider()
    template = await provider.build_template(image)
    now = utcnow()

    row = await session.get(FaceTemplate, user.id)
    if row is None:
        session.add(
            FaceTemplate(
                user_id=user.id,
                template=encrypt_text(template),
                provider=provider.name,
                created_at=now,
                updated_at=now,
            )
        )
    else:
        row.template = encrypt_text(template)
        row.provider = provider.name
        row.updated_at = now

    await audit.record(
        session,
        actor=user,
        action=AuditAction.FACE_ENROLLED,
        target_type="user",
        target_id=user.id,
        ip=ip,
    )
    await session.commit()
    return FaceEnrollResponse(provider=provider.name, enrolled_at=now)


async def get_status(session: AsyncSession, user_id) -> FaceStatus:
    row = await session.get(FaceTemplate, user_id)
    return FaceStatus(
        enrolled=row is not None,
        provider=row.provider if row else None,
        updated_at=row.updated_at if row else None,
        note=PRIVACY_NOTE,
    )
