"""
KYC Application - Base Repository

Generic async CRUD repository using SQLAlchemy 2.0 async API.
All domain repositories inherit from this base class to get
standard create/read/update/delete operations.
"""

from typing import Any, Dict, Generic, List, Optional, Sequence, Type, TypeVar
from uuid import UUID

from sqlalchemy import Select, func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Generic type variable for SQLAlchemy model classes
ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Generic async CRUD repository.

    Provides common database operations for any SQLAlchemy model.
    Domain repositories should inherit from this and add
    model-specific query methods.

    Type Parameter:
        ModelT: SQLAlchemy model class

    Usage:
        class UserRepository(BaseRepository[User]):
            def __init__(self, session: AsyncSession):
                super().__init__(User, session)
    """

    def __init__(self, model: Type[ModelT], session: AsyncSession) -> None:
        """
        Initialize the repository.

        Args:
            model: The SQLAlchemy model class
            session: The async database session
        """
        self.model = model
        self.session = session

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(self, data: Dict[str, Any]) -> ModelT:
        """
        Create a new model instance and persist it.

        Args:
            data: Dictionary of field name -> value mappings

        Returns:
            The newly created model instance (refreshed from DB)
        """
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        logger.debug(
            "Created record",
            model=self.model.__name__,
            id=getattr(instance, "id", None),
        )
        return instance

    async def bulk_create(self, data_list: List[Dict[str, Any]]) -> List[ModelT]:
        """
        Create multiple model instances in a single operation.

        Args:
            data_list: List of data dictionaries

        Returns:
            List of created model instances
        """
        instances = [self.model(**data) for data in data_list]
        self.session.add_all(instances)
        await self.session.flush()
        for instance in instances:
            await self.session.refresh(instance)
        return instances

    # =========================================================================
    # READ
    # =========================================================================

    async def get_by_id(self, id: UUID | str | int) -> Optional[ModelT]:
        """
        Get a single record by primary key.

        Args:
            id: Primary key value

        Returns:
            Model instance if found, None otherwise
        """
        result = await self.session.get(self.model, id)
        return result

    async def get_or_raise(self, id: UUID | str | int) -> ModelT:
        """
        Get a single record by primary key, raising an error if not found.

        Args:
            id: Primary key value

        Returns:
            Model instance

        Raises:
            ValueError: If record not found
        """
        instance = await self.get_by_id(id)
        if instance is None:
            raise ValueError(
                f"{self.model.__name__} with id={id} not found"
            )
        return instance

    async def get_by_field(
        self,
        field_name: str,
        value: Any,
    ) -> Optional[ModelT]:
        """
        Get a single record by a specific field value.

        Args:
            field_name: Name of the model field
            value: Value to match

        Returns:
            First matching model instance, or None
        """
        stmt = select(self.model).where(
            getattr(self.model, field_name) == value
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        order_desc: bool = False,
    ) -> List[ModelT]:
        """
        Get all records with optional pagination and ordering.

        Args:
            offset: Number of records to skip
            limit: Maximum records to return (max 1000)
            order_by: Field name to order by
            order_desc: If True, order descending

        Returns:
            List of model instances
        """
        limit = min(limit, 1000)  # Safety cap
        stmt = select(self.model).offset(offset).limit(limit)

        if order_by:
            col = getattr(self.model, order_by, None)
            if col is not None:
                stmt = stmt.order_by(col.desc() if order_desc else col.asc())

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_many_by_ids(self, ids: List[UUID | str | int]) -> List[ModelT]:
        """
        Get multiple records by a list of primary keys.

        Args:
            ids: List of primary key values

        Returns:
            List of found model instances (may be fewer than ids if some not found)
        """
        if not ids:
            return []
        stmt = select(self.model).where(self.model.id.in_(ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def exists(self, id: UUID | str | int) -> bool:
        """
        Check if a record with the given ID exists.

        Args:
            id: Primary key value

        Returns:
            True if record exists, False otherwise
        """
        stmt = select(func.count()).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0

    async def exists_by_field(self, field_name: str, value: Any) -> bool:
        """
        Check if any record with the given field value exists.

        Args:
            field_name: Name of the model field
            value: Value to check

        Returns:
            True if at least one matching record exists
        """
        stmt = select(func.count()).where(
            getattr(self.model, field_name) == value
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records, optionally filtered.

        Args:
            filters: Optional field name -> value filter conditions

        Returns:
            Count of matching records
        """
        stmt = select(func.count(self.model.id))
        if filters:
            for field, value in filters.items():
                col = getattr(self.model, field, None)
                if col is not None:
                    stmt = stmt.where(col == value)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def paginate(
        self,
        stmt: Select,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """
        Execute a paginated query.

        Args:
            stmt: Base SELECT statement (without LIMIT/OFFSET)
            page: Page number (1-indexed)
            size: Items per page

        Returns:
            Dictionary with keys: items, total, page, size, pages
        """
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Get page items
        offset = (page - 1) * size
        paginated_stmt = stmt.offset(offset).limit(size)
        items_result = await self.session.execute(paginated_stmt)
        items = list(items_result.scalars().all())

        pages = (total + size - 1) // size if total > 0 else 0

        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
        }

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def update(
        self,
        id: UUID | str | int,
        data: Dict[str, Any],
    ) -> Optional[ModelT]:
        """
        Update a record by primary key.

        Args:
            id: Primary key value
            data: Dictionary of fields to update

        Returns:
            Updated model instance, or None if not found
        """
        instance = await self.get_by_id(id)
        if instance is None:
            return None

        for field, value in data.items():
            if hasattr(instance, field):
                setattr(instance, field, value)

        await self.session.flush()
        await self.session.refresh(instance)

        logger.debug(
            "Updated record",
            model=self.model.__name__,
            id=id,
            fields=list(data.keys()),
        )
        return instance

    async def bulk_update(
        self,
        filters: Dict[str, Any],
        data: Dict[str, Any],
    ) -> int:
        """
        Update multiple records matching filter conditions.

        Args:
            filters: Field conditions to match
            data: Fields to update

        Returns:
            Number of records updated
        """
        stmt = update(self.model)
        for field, value in filters.items():
            col = getattr(self.model, field, None)
            if col is not None:
                stmt = stmt.where(col == value)
        stmt = stmt.values(**data)
        result = await self.session.execute(stmt)
        return result.rowcount

    # =========================================================================
    # DELETE
    # =========================================================================

    async def delete_by_id(self, id: UUID | str | int) -> bool:
        """
        Hard delete a record by primary key.

        Args:
            id: Primary key value

        Returns:
            True if record was found and deleted, False if not found
        """
        instance = await self.get_by_id(id)
        if instance is None:
            return False

        await self.session.delete(instance)
        await self.session.flush()

        logger.debug(
            "Deleted record",
            model=self.model.__name__,
            id=id,
        )
        return True

    async def soft_delete(
        self,
        id: UUID | str | int,
        deleted_at_field: str = "deleted_at",
    ) -> Optional[ModelT]:
        """
        Soft delete a record by setting deleted_at timestamp.

        Args:
            id: Primary key value
            deleted_at_field: Name of the deleted_at timestamp field

        Returns:
            Updated model instance, or None if not found
        """
        from datetime import datetime, timezone
        return await self.update(
            id,
            {deleted_at_field: datetime.now(timezone.utc)},
        )

    # =========================================================================
    # UTILITY
    # =========================================================================

    async def execute_raw(self, stmt: Select) -> Sequence:
        """
        Execute a custom SELECT statement.

        Args:
            stmt: SQLAlchemy SELECT statement

        Returns:
            Sequence of results
        """
        result = await self.session.execute(stmt)
        return result.scalars().all()

    def _apply_filters(
        self,
        stmt: Select,
        filters: Dict[str, Any],
    ) -> Select:
        """
        Apply equality filters to a SELECT statement.

        Args:
            stmt: Base SELECT statement
            filters: Field name -> value filter conditions

        Returns:
            Statement with filters applied
        """
        for field, value in filters.items():
            col = getattr(self.model, field, None)
            if col is not None and value is not None:
                stmt = stmt.where(col == value)
        return stmt
