"""初始化演示数据。

用法：
    python -m scripts.seed          # 幂等：已有数据则跳过
    python -m scripts.seed --reset  # 清空业务数据后重建
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.security import derive_display_code, hash_secret  # noqa: E402
from app.db.session import SessionFactory, engine  # noqa: E402
from app.models.anomaly import Anomaly  # noqa: E402
from app.models.attendance import AttendanceRecord  # noqa: E402
from app.models.enums import (  # noqa: E402
    AnomalyStatus,
    AnomalyType,
    AttendanceKind,
    AttendanceStatus,
    CheckinMode,
    EventStatus,
    RegistrationStatus,
    UserRole,
)
from app.models.event import Event  # noqa: E402
from app.models.qr import QrChallenge  # noqa: E402
from app.models.registration import Registration  # noqa: E402
from app.models.user import Organization, User  # noqa: E402
from app.utils.time import utcnow  # noqa: E402

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_PASSWORD = "Passw0rd!"


def local(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SHANGHAI).astimezone(UTC)


async def reset_data(session: AsyncSession) -> None:
    await session.execute(
        text(
            "TRUNCATE attendance_records, anomalies, checkin_attempts, qr_usages, "
            "qr_challenges, registrations, events, face_templates, refresh_tokens, "
            "audit_logs, organizations, users RESTART IDENTITY CASCADE"
        )
    )
    await session.commit()


async def create_user(
    session: AsyncSession,
    *,
    student_no: str,
    name: str,
    role: UserRole,
    phone: str,
    college: str,
    password: str = DEFAULT_PASSWORD,
) -> User:
    user = User(
        student_no=student_no,
        name=name,
        phone=phone,
        college=college,
        role=role,
        password_hash=hash_secret(password),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def seed(session: AsyncSession) -> None:
    now = utcnow()
    today = now.astimezone(SHANGHAI)

    await create_user(
        session, student_no="A0001", name="系统管理员", role=UserRole.ADMIN,
        phone="13900000001", college="信息中心",
    )
    organizer_it = await create_user(
        session, student_no="T1001", name="张同学", role=UserRole.ORGANIZER,
        phone="13900000002", college="计算机学院",
    )
    organizer_vol = await create_user(
        session, student_no="T1002", name="李同学", role=UserRole.ORGANIZER,
        phone="13900000003", college="青年志愿者协会",
    )
    organizer_sport = await create_user(
        session, student_no="T1003", name="王老师", role=UserRole.ORGANIZER,
        phone="13900000004", college="体育部",
    )

    students = {
        "chen": await create_user(
            session, student_no="2023010118", name="陈雨桐", role=UserRole.STUDENT,
            phone="13800002218", college="计算机学院",
        ),
        "li": await create_user(
            session, student_no="2023010119", name="李昊然", role=UserRole.STUDENT,
            phone="13800002219", college="计算机学院",
        ),
        "zhou": await create_user(
            session, student_no="2023010120", name="周雅静", role=UserRole.STUDENT,
            phone="13800002220", college="外国语学院",
        ),
        "chu": await create_user(
            session, student_no="2023010121", name="褚梦琪", role=UserRole.STUDENT,
            phone="13800002221", college="数学学院",
        ),
        "feng": await create_user(
            session, student_no="2023010122", name="冯子墨", role=UserRole.STUDENT,
            phone="13800002222", college="计算机学院",
        ),
        "zheng": await create_user(
            session, student_no="2023010123", name="郑雨薇", role=UserRole.STUDENT,
            phone="13800002223", college="新闻学院",
        ),
        "wang": await create_user(
            session, student_no="2023010124", name="王梓萱", role=UserRole.STUDENT,
            phone="13800002224", college="法学院",
        ),
        "wu": await create_user(
            session, student_no="2023010125", name="吴俊杰", role=UserRole.STUDENT,
            phone="13800002225", college="体育学院",
        ),
    }

    org_it = Organization(
        name="计算机协会", description="校级技术社团，负责技术分享与竞赛组织",
        contact_name="张同学", contact_phone="13900000002",
        owner_id=organizer_it.id, verified=True,
    )
    org_vol = Organization(
        name="校青年志愿者协会", description="校园志愿服务组织",
        contact_name="李同学", contact_phone="13900000003",
        owner_id=organizer_vol.id, verified=True,
    )
    org_sport = Organization(
        name="校体育部", description="校园体育赛事主办方",
        contact_name="王老师", contact_phone="13900000004",
        owner_id=organizer_sport.id, verified=True,
    )
    session.add_all([org_it, org_vol, org_sport])
    await session.flush()

    # 活动一：今天进行中，动态二维码 + GPS + IP 叠加校验
    start1 = now - timedelta(minutes=30)
    end1 = now + timedelta(minutes=90)
    share = Event(
        org_id=org_it.id,
        created_by=organizer_it.id,
        title="前端工程化实践分享会",
        description=(
            "面向全校的前端技术分享，内容涵盖构建工具链、组件库设计、性能优化与工程规范落地。"
            "现场设有问答环节，欢迎带着项目问题来交流。"
        ),
        location_name="图书馆 3F 报告厅",
        latitude=31.230416,
        longitude=121.473701,
        cover_color="#1a73e8",
        start_at=start1,
        end_at=end1,
        registration_deadline=start1 - timedelta(hours=2),
        capacity=40,
        requires_approval=False,
        status=EventStatus.PUBLISHED,
        published_at=now - timedelta(days=2),
        checkin_mode=CheckinMode.CHECKIN_ONLY,
        checkin_opens_minutes_before=30,
        checkin_closes_minutes_after=60,
        require_qr=True,
        qr_rotation_seconds=10,
        require_gps=True,
        gps_radius_m=200,
        gps_max_accuracy_m=200,
        require_ip=True,
        # 127.0.0.1 便于本机联调；正式环境应只保留校园网段
        allowed_ip_cidrs=["10.20.0.0/16", "127.0.0.1/32"],
    )

    # 活动二：两天后，静态口令 + 签到签退 + 报名审核
    start2 = local(today.year, today.month, today.day, 9) + timedelta(days=2)
    vol = Event(
        org_id=org_vol.id,
        created_by=organizer_vol.id,
        title="图书馆古籍整理志愿活动",
        description="协助图书馆完成古籍除尘、编号与上架工作。活动计入志愿时长 3 小时，需自备口罩与手套。",
        location_name="图书馆 2F 古籍室",
        latitude=31.229905,
        longitude=121.474023,
        cover_color="#1e8e3e",
        start_at=start2,
        end_at=start2 + timedelta(hours=3),
        registration_deadline=start2 - timedelta(hours=12),
        capacity=30,
        requires_approval=True,
        status=EventStatus.PUBLISHED,
        published_at=now - timedelta(days=1),
        checkin_mode=CheckinMode.CHECKIN_CHECKOUT,
        checkin_opens_minutes_before=15,
        checkin_closes_minutes_after=15,
        checkout_deadline_minutes=30,
        require_static_code=True,
        static_code_hash=hash_secret("826519"),
        static_code_valid_from=start2,
        static_code_valid_to=start2 + timedelta(minutes=15),
    )

    # 活动三：四天后，人脸识别，名额已满
    start3 = local(today.year, today.month, today.day, 15) + timedelta(days=4)
    ball = Event(
        org_id=org_sport.id,
        created_by=organizer_sport.id,
        title="新生杯篮球赛观众报名",
        description="新生杯篮球赛决赛现场观赛报名。凭报名记录入场，现场设人脸识别通道，请提前 15 分钟到场核验。",
        location_name="东区体育馆",
        latitude=31.232611,
        longitude=121.480117,
        cover_color="#e8710a",
        start_at=start3,
        end_at=start3 + timedelta(hours=3),
        registration_deadline=start3 - timedelta(days=1),
        capacity=8,
        requires_approval=False,
        status=EventStatus.PUBLISHED,
        published_at=now - timedelta(days=1),
        checkin_mode=CheckinMode.CHECKIN_ONLY,
        require_face=True,
        face_match_threshold=0.85,
    )

    session.add_all([share, vol, ball])
    await session.flush()

    # 活动一：8 人报名，5 人已签到
    share_regs: dict[str, Registration] = {}
    for key in ("chen", "li", "zhou", "chu", "feng", "zheng", "wang", "wu"):
        registration = Registration(
            event_id=share.id,
            user_id=students[key].id,
            status=RegistrationStatus.APPROVED,
            ticket_code=secrets.token_hex(8).upper(),
            applied_at=now - timedelta(days=1),
        )
        session.add(registration)
        share_regs[key] = registration
    await session.flush()

    checkin_specs = [
        ("chen", 45.0, "10.20.33.71", 9),
        ("li", 88.0, "10.20.33.12", 9),
        ("zhou", 33.0, "10.20.31.05", 9),
        ("feng", 140.0, "10.20.33.66", 18),
        ("zheng", 95.0, "10.20.33.66", 18),
    ]
    for key, distance, ip, minutes_ago in checkin_specs:
        session.add(
            AttendanceRecord(
                event_id=share.id,
                registration_id=share_regs[key].id,
                user_id=students[key].id,
                kind=AttendanceKind.CHECKIN,
                status=AttendanceStatus.FLAGGED if key in ("feng", "zheng") else AttendanceStatus.NORMAL,
                occurred_at=now - timedelta(minutes=minutes_ago),
                verified_methods=["qr", "gps", "ip"],
                ip=ip,
                distance_m=distance,
                accuracy_m=12.0,
                created_at=now - timedelta(minutes=minutes_ago),
            )
        )

    session.add(
        Anomaly(
            event_id=share.id,
            user_id=students["zheng"].id,
            type=AnomalyType.SAME_IP,
            status=AnomalyStatus.OPEN,
            detail={
                "ip": "10.20.33.66",
                "window_minutes": 15,
                "peer_user_id": str(students["feng"].id),
                "peer_name": students["feng"].name,
                "peer_student_no": students["feng"].student_no,
            },
            detected_at=now - timedelta(minutes=18),
        )
    )
    session.add(
        Anomaly(
            event_id=share.id,
            user_id=students["feng"].id,
            type=AnomalyType.SAME_IP,
            status=AnomalyStatus.OPEN,
            detail={
                "ip": "10.20.33.66",
                "window_minutes": 15,
                "peer_user_id": str(students["zheng"].id),
                "peer_name": students["zheng"].name,
                "peer_student_no": students["zheng"].student_no,
            },
            detected_at=now - timedelta(minutes=18),
        )
    )

    # 活动二：两人待审核
    for key in ("wang", "wu"):
        session.add(
            Registration(
                event_id=vol.id,
                user_id=students[key].id,
                status=RegistrationStatus.PENDING,
                ticket_code=secrets.token_hex(8).upper(),
                applied_at=now - timedelta(hours=3),
            )
        )

    # 活动三：8 人报名，名额已满
    for key in ("chen", "li", "zhou", "chu", "feng", "zheng", "wang", "wu"):
        session.add(
            Registration(
                event_id=ball.id,
                user_id=students[key].id,
                status=RegistrationStatus.APPROVED,
                ticket_code=secrets.token_hex(8).upper(),
                applied_at=now - timedelta(hours=6),
            )
        )

    # 预置一个有效二维码，控制台首次打开即可展示
    nonce = secrets.token_hex(8)
    session.add(
        QrChallenge(
            event_id=share.id,
            nonce=nonce,
            code=derive_display_code(nonce),
            issued_by=organizer_it.id,
            issued_at=now,
            expires_at=now + timedelta(seconds=share.qr_rotation_seconds + 2),
        )
    )

    await session.commit()
    print("演示数据已生成")
    print(f"  管理员    A0001 / {DEFAULT_PASSWORD}")
    print(f"  组织者    T1001 / {DEFAULT_PASSWORD}（计算机协会）")
    print(f"  组织者    T1002 / {DEFAULT_PASSWORD}（校青协）")
    print(f"  学生      2023010118 / {DEFAULT_PASSWORD}（陈雨桐）")
    print("  静态口令  826519（古籍整理志愿活动）")
    print(f"  活动 ID   share={share.id} vol={vol.id} ball={ball.id}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="ActivityHub 演示数据初始化")
    parser.add_argument("--reset", action="store_true", help="清空业务数据后重建")
    args = parser.parse_args()

    async with SessionFactory() as session:
        if args.reset:
            await reset_data(session)
        existing = await session.scalar(select(User.id).limit(1))
        if existing is not None:
            print("已存在业务数据，跳过。如需重建请加 --reset")
            return
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
