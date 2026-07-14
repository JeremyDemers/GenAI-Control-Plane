from fastapi import APIRouter, Depends

from app.auth.dependencies import current_user
from app.models.entities import User
from app.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=[role.name for role in user.roles],
    )
