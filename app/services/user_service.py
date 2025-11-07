"""User service layer for business logic."""
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserResponse
from app.models.user import User


class UserService:
    """Service layer for user business logic."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self.repository = UserRepository(db)

    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """
        Create a new user.

        Args:
            user_data: User creation data

        Returns:
            Created user response
        """
        user = await self.repository.create(
            name=user_data.name,
            email=user_data.email,
        )

        await self.db.commit()
        return await self._user_to_response(user)

    async def get_user_by_id(self, user_id: UUID) -> Optional[UserResponse]:
        """
        Get user by ID.

        Args:
            user_id: User UUID

        Returns:
            User response or None if not found
        """
        user = await self.repository.get_by_id(user_id)
        if not user:
            return None

        return await self._user_to_response(user)


    async def _user_to_response(self, user: User) -> UserResponse:
        """
        Convert User model to UserResponse.

        Args:
            user: User model

        Returns:
            UserResponse object
        """
        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
