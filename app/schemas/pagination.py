"""Pagination schemas and utilities."""
from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field

# Generic type for paginated data
T = TypeVar('T')


class PaginationParams(BaseModel):
    """Common pagination parameters."""
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Number of items per page")

    @property
    def skip(self) -> int:
        """Calculate the number of records to skip."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get the limit for database query."""
        return self.page_size


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""
    items: List[T] = Field(..., description="List of items for the current page")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")

    @staticmethod
    def create(
        items: List[T],
        total_items: int,
        page: int,
        page_size: int
    ) -> "PaginatedResponse[T]":
        """
        Create a paginated response with metadata.

        Args:
            items: List of items for the current page
            total_items: Total number of items across all pages
            page: Current page number (1-indexed)
            page_size: Number of items per page

        Returns:
            PaginatedResponse with items and metadata
        """
        total_pages = (total_items + page_size - 1) // page_size  # Ceiling division

        return PaginatedResponse(
            items=items,
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_previous=page > 1
            )
        )
