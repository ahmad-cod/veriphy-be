from typing import TypeVar, Generic, Type, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone

from src.domain.base import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: Any) -> Optional[ModelType]:
        statement = select(self.model).where(getattr(self.model, 'id') == id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create(self, obj_in: dict) -> ModelType:
        db_obj = self.model(**obj_in)
        self.session.add(db_obj)
        await self.session.flush() # Flush to get DB-generated fields like timestamps/UUIDs
        return db_obj

    async def update(self, db_obj: ModelType, obj_in: dict) -> ModelType:
        """Dynamically updates an existing SQLAlchemy model object."""
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def soft_delete(self, db_obj: ModelType) -> ModelType:
        """Safely marks a record as deleted if the model supports it."""
        if hasattr(db_obj, 'is_active') and hasattr(db_obj, 'deleted_at'):
            setattr(db_obj, 'is_active', False)
            setattr(db_obj, 'deleted_at', datetime.now(timezone.utc))

            self.session.add(db_obj)
            await self.session.flush()
        return db_obj

    async def hard_delete(self, db_obj: ModelType) -> None:
        """Permanently removes a record from the database."""
        await self.session.delete(db_obj)
        await self.session.flush()