"""小程序视图组装。"""

from app.models.activity import Activity
from app.models.registration import Registration
from app.schemas.mp import (
    MpActivityDetail,
    MpActivityItem,
    MpRegistrationDetail,
    MpRegistrationItem,
)
from app.schemas.registration import RegistrationOut, SignupState


def activity_item(activity: Activity) -> MpActivityItem:
    return MpActivityItem(
        id=activity.id,
        title=activity.title,
        cover_url=activity.cover_url,
        summary=activity.summary,
        location_name=activity.location_name,
        start_at=activity.start_at,
        end_at=activity.end_at,
        signup_start_at=activity.signup_start_at,
        signup_end_at=activity.signup_end_at,
        capacity=activity.capacity,
        taken_count=activity.taken_count,
        remaining=max(0, activity.capacity - activity.taken_count),
        need_review=activity.need_review,
        allow_cancel=activity.allow_cancel,
        cancel_deadline=activity.cancel_deadline,
        status=activity.status,
    )


def activity_detail(
    activity: Activity,
    registration: Registration | None,
    can_signup: bool,
    reason: str | None,
) -> MpActivityDetail:
    return MpActivityDetail(
        id=activity.id,
        title=activity.title,
        cover_url=activity.cover_url,
        summary=activity.summary,
        description=activity.description,
        location_name=activity.location_name,
        address=activity.address,
        start_at=activity.start_at,
        end_at=activity.end_at,
        signup_start_at=activity.signup_start_at,
        signup_end_at=activity.signup_end_at,
        capacity=activity.capacity,
        taken_count=activity.taken_count,
        remaining=max(0, activity.capacity - activity.taken_count),
        need_review=activity.need_review,
        allow_cancel=activity.allow_cancel,
        cancel_deadline=activity.cancel_deadline,
        status=activity.status,
        form_schema=activity.form_schema,
        my_registration=(
            RegistrationOut.model_validate(registration) if registration else None
        ),
        signup_state=SignupState(can_signup=can_signup, reason=reason),
    )


def registration_item(
    registration: Registration, activity: Activity
) -> MpRegistrationItem:
    return MpRegistrationItem(
        **RegistrationOut.model_validate(registration).model_dump(),
        activity=activity_item(activity),
    )


def registration_detail(
    registration: Registration, activity: Activity
) -> MpRegistrationDetail:
    return MpRegistrationDetail(
        **RegistrationOut.model_validate(registration).model_dump(),
        activity=activity_item(activity),
        form_schema=activity.form_schema,
    )
