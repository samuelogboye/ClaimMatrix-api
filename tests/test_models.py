"""Tests for database models."""
import pytest

from app.models import User
from app.utils.auth import hash_password


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_model_creation(db_session):
    """Test creating a User model instance."""
    user = User(
        name="John Doe",
        email="john@example.com",
        hashed_password=hash_password("testpassword"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.name == "John Doe"
    assert user.email == "john@example.com"
    assert user.created_at is not None
    assert user.updated_at is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_email_uniqueness(db_session):
    """Test that user email must be unique."""
    user1 = User(name="John Doe", email="john@example.com", hashed_password=hash_password("test"))
    db_session.add(user1)
    await db_session.commit()

    user2 = User(name="Jane Doe", email="john@example.com", hashed_password=hash_password("test"))
    db_session.add(user2)

    with pytest.raises(Exception):  # IntegrityError for duplicate email
        await db_session.commit()

    # Rollback the session after the expected error
    await db_session.rollback()
