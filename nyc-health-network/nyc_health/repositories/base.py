from typing import Callable, Generic, List, Optional, TypeVar

from nyc_health.exceptions import NotFoundError, ValidationError
from nyc_health.utils.ids import IdGenerator

T = TypeVar("T")


class InMemoryRepository(Generic[T]):
    """Minimal id-keyed store. Subclasses add domain-specific queries."""

    entity_name = "entity"
    id_prefix = "ENT"

    def __init__(self, id_generator: IdGenerator) -> None:
        self._ids = id_generator
        self._store: dict = {}

    def next_id(self) -> str:
        return self._ids.next(self.id_prefix)

    def add(self, entity: T) -> T:
        if entity.id in self._store:
            raise ValidationError(f"{self.entity_name} '{entity.id}' already exists")
        self._store[entity.id] = entity
        return entity

    def get(self, entity_id: str) -> T:
        try:
            return self._store[entity_id]
        except KeyError:
            raise NotFoundError(self.entity_name, entity_id) from None

    def find_by_id(self, entity_id: str) -> Optional[T]:
        return self._store.get(entity_id)

    def update(self, entity: T) -> T:
        if entity.id not in self._store:
            raise NotFoundError(self.entity_name, entity.id)
        self._store[entity.id] = entity
        return entity

    def delete(self, entity_id: str) -> None:
        if entity_id not in self._store:
            raise NotFoundError(self.entity_name, entity_id)
        del self._store[entity_id]

    def list_all(self) -> List[T]:
        return list(self._store.values())

    def find(self, predicate: Callable[[T], bool]) -> List[T]:
        return [e for e in self._store.values() if predicate(e)]

    def count(self) -> int:
        return len(self._store)
