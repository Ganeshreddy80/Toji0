"""Base repository and generic ORM repository operations with transaction safety and concurrency locks.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Type, TypeVar
from sqlalchemy import select, asc, desc
from sqlalchemy.orm import Session, declarative_base

Base = declarative_base()

T = TypeVar("T", bound=Base)


class BaseRepository:
    """Provides generic CRUD operations for database entities."""

    _db_lock = threading.RLock()

    def __init__(self, session_factory: Any, model_class: Type[T]) -> None:
        self.session_factory = session_factory
        self.model_class = model_class

    def get_session(self) -> Session:
        return self.session_factory.get_session()

    def create(self, entity: T) -> T:
        with self._db_lock:
            with self.session_factory.session_scope() as session:
                session.add(entity)
                return entity

    def get(self, id_val: Any) -> Optional[T]:
        with self._db_lock:
            session = self.get_session()
            try:
                return session.get(self.model_class, id_val)
            finally:
                if not self.session_factory.active_session:
                    session.close()

    def update(self, id_val: Any, updates: Dict[str, Any]) -> Optional[T]:
        with self._db_lock:
            with self.session_factory.session_scope() as session:
                entity = session.get(self.model_class, id_val)
                if entity:
                    for k, v in updates.items():
                        setattr(entity, k, v)
                return entity

    def delete(self, id_val: Any) -> bool:
        with self._db_lock:
            with self.session_factory.session_scope() as session:
                entity = session.get(self.model_class, id_val)
                if entity:
                    session.delete(entity)
                    return True
                return False

    def list_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[T]:
        with self._db_lock:
            session = self.get_session()
            try:
                stmt = select(self.model_class)
                
                # Filtering
                if filters:
                    for field, value in filters.items():
                        if hasattr(self.model_class, field):
                            stmt = stmt.where(getattr(self.model_class, field) == value)
                
                # Sorting
                if sort_by and hasattr(self.model_class, sort_by):
                    col = getattr(self.model_class, sort_by)
                    stmt = stmt.order_by(asc(col) if sort_order == "asc" else desc(col))
                    
                # Pagination
                if limit is not None:
                    stmt = stmt.limit(limit)
                if offset is not None:
                    stmt = stmt.offset(offset)
                    
                return session.scalars(stmt).all()
            finally:
                if not self.session_factory.active_session:
                    session.close()
