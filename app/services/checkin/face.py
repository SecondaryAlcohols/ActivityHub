"""人脸校验：特征模板比对 + 阈值判定。"""

from __future__ import annotations

from app.core.crypto import decrypt_text
from app.models.user import FaceTemplate
from app.providers.face import decode_image_payload, get_face_provider
from app.services.checkin.base import CheckinError, VerificationContext


async def verify(ctx: VerificationContext) -> None:
    if not ctx.payload.face_image:
        raise CheckinError("face_required", "请完成人脸识别后提交")

    template_row = await ctx.session.get(FaceTemplate, ctx.user.id)
    if template_row is None:
        raise CheckinError("face_not_enrolled", "尚未录入人脸信息，请先在「我的」中完成录入")

    image = decode_image_payload(ctx.payload.face_image)
    similarity = await get_face_provider().compare(decrypt_text(template_row.template), image)

    if similarity < ctx.event.face_match_threshold:
        raise CheckinError(
            "face_low_similarity",
            "人脸比对未通过，请正对镜头重试",
            {
                "similarity": round(similarity, 4),
                "threshold": ctx.event.face_match_threshold,
            },
        )

    ctx.face_similarity = round(similarity, 4)
    ctx.passed_methods.append("face")
