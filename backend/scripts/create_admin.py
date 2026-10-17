import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models.admin_user import AdminUser  # noqa: E402


async def create_admin(username: str, password: str, display_name: str, role: str) -> None:
    async with SessionLocal() as db:
        existing = await db.scalar(
            select(AdminUser).where(AdminUser.username == username)
        )
        if existing is not None:
            print(f"账号 {username} 已存在，未做修改")
            return

        db.add(
            AdminUser(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name,
                role=role,
                status=True,
            )
        )
        await db.commit()
        print(f"管理员账号已创建: {username}（角色: {role}）")


def main() -> None:
    parser = argparse.ArgumentParser(description="创建后台管理员账号")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="管理员")
    parser.add_argument(
        "--role",
        default="super_admin",
        choices=["super_admin", "operator", "staff"],
    )
    args = parser.parse_args()
    asyncio.run(create_admin(args.username, args.password, args.name, args.role))


if __name__ == "__main__":
    main()
