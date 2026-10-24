"""人脸比对服务抽象。

约定：
* 只有加密后的人脸特征模板会落库，原始图像仅在请求内存中存在；
* 生产环境必须使用 ``http`` 实现，``stub`` 仅用于本地开发与自动化测试。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.core.exceptions import BadRequest, ServiceUnavailable

MAX_IMAGE_BYTES = 4 * 1024 * 1024


def decode_image_payload(value: str) -> bytes:
    """解析 base64 或 data URL 形式的人脸图像。"""
    payload = value.strip()
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise BadRequest("人脸图像不是合法的 base64 数据", code="invalid_face_image") from exc

    if not raw:
        raise BadRequest("人脸图像为空", code="invalid_face_image")
    if len(raw) > MAX_IMAGE_BYTES:
        raise BadRequest("人脸图像超过 4MB 限制", code="face_image_too_large")
    return raw


class FaceProvider(Protocol):
    name: str

    async def build_template(self, image: bytes) -> str:
        """把图像转换为人脸特征模板（明文，由调用方负责加密）。"""
        ...

    async def compare(self, template: str, image: bytes) -> float:
        """返回 0~1 的相似度。"""
        ...


class StubFaceProvider:
    """本地桩实现，禁止用于生产。

    * ``build_template`` 取图像摘要，不具备任何生物特征能力；
    * ``compare`` 支持 ``stub:0.92`` 形式的测试图像以得到确定分数；
    * 其他图像返回基于摘要的确定性伪分数，便于联调。
    """

    name = "stub"

    async def build_template(self, image: bytes) -> str:
        return f"stub:{hashlib.sha256(image).hexdigest()[:32]}"

    async def compare(self, template: str, image: bytes) -> float:
        if image.startswith(b"stub:"):
            try:
                return max(0.0, min(1.0, float(image[5:].decode())))
            except (ValueError, UnicodeDecodeError) as exc:
                raise BadRequest("桩实现的人脸分数格式应为 stub:0.92", code="invalid_face_image") from exc

        digest = hashlib.sha256(template.encode() + image).digest()
        return 0.5 + int.from_bytes(digest[:2], "big") / 65535 * 0.5


class HttpFaceProvider:
    """对接外部人脸比对服务。

    入参：{"template": "...", "image": "base64"}；出参：{"similarity": 0.93}
    """

    name = "http"

    def __init__(self, base_url: str, token: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def build_template(self, image: bytes) -> str:
        data = await self._post("/v1/face/template", {"image": base64.b64encode(image).decode()})
        template = data.get("template")
        if not isinstance(template, str) or not template:
            raise ServiceUnavailable("人脸服务未返回有效特征", code="face_provider_error")
        return template

    async def compare(self, template: str, image: bytes) -> float:
        data = await self._post(
            "/v1/face/compare", {"template": template, "image": base64.b64encode(image).decode()}
        )
        similarity = data.get("similarity")
        if not isinstance(similarity, int | float):
            raise ServiceUnavailable("人脸服务未返回相似度", code="face_provider_error")
        return max(0.0, min(1.0, float(similarity)))

    async def _post(self, path: str, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    f"{self.base_url}{path}", json=payload, headers=self._headers()
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceUnavailable("人脸比对服务暂不可用", code="face_provider_error") from exc
        if not isinstance(data, dict):
            raise ServiceUnavailable("人脸服务响应格式异常", code="face_provider_error")
        return data


@lru_cache
def get_face_provider() -> FaceProvider:
    settings = get_settings()
    if settings.face_provider == "http":
        if not settings.face_provider_url:
            raise ServiceUnavailable("未配置 FACE_PROVIDER_URL", code="face_provider_error")
        return HttpFaceProvider(settings.face_provider_url, settings.face_provider_token)
    return StubFaceProvider()
