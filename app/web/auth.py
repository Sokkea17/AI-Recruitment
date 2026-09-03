from typing import Optional
from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.session import get_db
from app.models.user import User
from app.utils.security import verify_session_token

async def get_current_user_optional(
    request: Request,
    session: AsyncSession = Depends(get_db)
) -> Optional[User]:
    token = request.cookies.get("session_token")
    if not token:
        return None

    payload = verify_session_token(token, settings.SECRET_KEY)
    if not payload:
        return None

    user_id = payload.get("user_id")
    if not user_id:
        return None

    stmt = select(User).where(User.id == user_id, User.is_active == True)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_current_user_required(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    if not user:
        # Check if API request or browser request
        if request.url.path.startswith("/api/"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required."
            )
        # Redirect browser to login
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": f"/login?next={request.url.path}"}
        )
    return user
