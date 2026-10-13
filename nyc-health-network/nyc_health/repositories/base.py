from typing import Any, Callable, Dict, Generic, List, Optional, Sequence, Tuple, Type, TypeVar

from nyc_health.db import codec
from nyc_health.db.mongo import DuplicateKeyError, FakeMongoDatabase
from nyc_health.exceptions import NotFoundError, ValidationError
from nyc_health.utils.ids import IdGenerator

T = TypeVar("T")


class MongoRepository(Generic[T]):
    """Id-keyed repository on top of a (fake) Mongo collection.

    Entities are converted to documents on write and rebuilt on read, so an entity returned by the
    repository is a *copy*: changes only persist once `update()` is called. Subclasses set `model`,
    `collection_name`, optional `indexes`, and add domain-specific queries.

    Prefer `find_where` (a Mongo filter, can use an index) over `find` (loads every document and
    filters in Python) for anything that runs on a hot path.
    """

    entity_name = "entity"
    id_prefix = "ENT"
    collection_name = "entities"
    model: Type[T]
    indexes: Sequence[Tuple[str, ...]] = ()

    def __init__(self, db: FakeMongoDatabase, id_generator: IdGenerator) -> None:
        self._ids = id_generator
        self._collection = db[self.collection_name]
        for fields in self.indexes:
            self._collection.create_index(fields)

    def next_id(self) -> str:
        return self._ids.next(self.id_prefix)

    # ----------------------------------------------------------------- mapping
    def _to_doc(self, entity: T) -> Dict[str, Any]:
        doc = codec.to_document(entity)
        doc["_id"] = doc.pop("id")
        return doc

    def _from_doc(self, doc: Dict[str, Any]) -> T:
        doc = dict(doc)
        doc["id"] = doc.pop("_id")
        return codec.from_document(self.model, doc)

    # -------------------------------------------------------------------- CRUD
    def add(self, entity: T) -> T:
        try:
            self._collection.insert_one(self._to_doc(entity))
        except DuplicateKeyError:
            raise ValidationError(f"{self.entity_name} '{entity.id}' already exists") from None
        return entity

    def get(self, entity_id: str) -> T:
        entity = self.find_by_id(entity_id)
        if entity is None:
            raise NotFoundError(self.entity_name, entity_id)
        return entity

    def find_by_id(self, entity_id: str) -> Optional[T]:
        doc = self._collection.find_one({"_id": entity_id})
        return self._from_doc(doc) if doc else None

    def update(self, entity: T) -> T:
        if not self._collection.replace_one({"_id": entity.id}, self._to_doc(entity)):
            raise NotFoundError(self.entity_name, entity.id)
        return entity

    def delete(self, entity_id: str) -> None:
        if not self._collection.delete_one({"_id": entity_id}):
            raise NotFoundError(self.entity_name, entity_id)

    # ----------------------------------------------------------------- queries
    def list_all(self) -> List[T]:
        return [self._from_doc(d) for d in self._collection.find({})]

    def find(self, predicate: Callable[[T], bool]) -> List[T]:
        """Full scan: loads every document, then filters in Python."""
        return [e for e in self.list_all() if predicate(e)]

    def find_where(
        self, flt: Dict[str, Any], sort: Optional[List[Tuple[str, int]]] = None, limit: int = 0
    ) -> List[T]:
        """Run a Mongo-style filter in the database (uses an index when one covers the filter)."""
        return [self._from_doc(d) for d in self._collection.find(flt, sort=sort, limit=limit)]

    def count(self, flt: Optional[Dict[str, Any]] = None) -> int:
        return self._collection.count_documents(flt or {})
