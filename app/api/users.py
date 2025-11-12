"""User API endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.user_service import UserService


router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Get the profile of the authenticated user.",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get current user profile.

    Args:
        current_user: Authenticated user (from JWT)

    Returns:
        User profile

    Raises:
        HTTPException 401: If not authenticated
    """
    # Simply return the user that was already fetched by get_current_user dependency
    # No need to query the database again!
    return current_user