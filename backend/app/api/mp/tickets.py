import io

import qrcode
from fastapi import APIRouter
from fastapi.responses import Response

from app.core.errors import AppError
from app.core.ticket import verify_ticket_token

router = APIRouter(prefix="/mp/tickets", tags=["电子票"])


@router.get("/{token}.png", include_in_schema=False)
async def ticket_qr(token: str):
    if verify_ticket_token(token) is None:
        raise AppError(404, "电子票无效", 40403)

    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(token)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
