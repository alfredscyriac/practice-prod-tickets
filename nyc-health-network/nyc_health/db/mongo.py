"""A tiny MongoDB look-alike: collections of plain-dict documents with a pymongo-flavoured API.

Supported: insert_one, find_one, find (filter/sort/limit), update_one, replace_one,
find_one_and_update, delete_one, count_documents, create_index (equality hash indexes, optionally
unique). Filter operators: $eq $ne $gt $gte $lt $lte $in $nin. Update operators: $set $inc $unset.

Documents are deep-copied on the way in and out, exactly like a real driver round-trip: mutating a
dict (or a model rebuilt from it) never changes what is stored until you write it back.

`database.stats` counts documents examined by queries so tests can tell an indexed lookup from a
full collection scan.
"""
import copy
import threading
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


class DuplicateKeyError(Exception):
    """Raised when an insert/replace would violate the _id or a unique index."""


@dataclass
class QueryStats:
    queries: int = 0
    docs_examined: int = 0
    index_hits: int = 0
    full_scans: int = 0


_OPERATORS = {
    "$eq": lambda value, arg: value == arg,
    "$ne": lambda value, arg: value != arg,
    "$gt": lambda value, arg: value is not None and value > arg,
    "$gte": lambda value, arg: value is not None and value >= arg,
    "$lt": lambda value, arg: value is not None and value < arg,
    "$lte": lambda value, arg: value is not None and value <= arg,
    "$in": lambda value, arg: value in arg,
    "$nin": lambda value, arg: value not in arg,
}


def _matches(document: Dict[str, Any], flt: Dict[str, Any]) -> bool:
    for field_name, condition in flt.items():
        value = document.get(field_name)
        if isinstance(condition, dict) and condition and all(k.startswith("$") for k in condition):
            for op, arg in condition.items():
                if op not in _OPERATORS:
                    raise ValueError(f"unsupported query operator {op}")
                if not _OPERATORS[op](value, arg):
                    return False
        elif value != condition:
            return False
    return True


class _Index:
    def __init__(self, fields: Sequence[str], unique: bool) -> None:
        self.fields = tuple(fields)
        self.unique = unique
        self.entries: Dict[Tuple, set] = {}

    def key_for(self, document: Dict[str, Any]) -> Tuple:
        return tuple(document.get(f) for f in self.fields)

    def add(self, document: Dict[str, Any]) -> None:
        self.entries.setdefault(self.key_for(document), set()).add(document["_id"])

    def remove(self, document: Dict[str, Any]) -> None:
        key = self.key_for(document)
        ids = self.entries.get(key)
        if ids:
            ids.discard(document["_id"])
            if not ids:
                del self.entries[key]

    def covered_by(self, flt: Dict[str, Any]) -> bool:
        """True if the filter has a plain equality condition on every indexed field."""
        for f in self.fields:
            cond = flt.get(f)
            if f not in flt or (isinstance(cond, dict) and any(k.startswith("$") for k in cond)):
                return False
        return True


class FakeCollection:
    def __init__(self, name: str, stats: QueryStats, lock: threading.RLock) -> None:
        self.name = name
        self._stats = stats
        self._lock = lock
        self._docs: Dict[str, Dict[str, Any]] = {}
        self._indexes: List[_Index] = []

    # ------------------------------------------------------------------ indexes
    def create_index(self, fields: Iterable[str], unique: bool = False) -> None:
        index = _Index(list(fields), unique)
        with self._lock:
            for doc in self._docs.values():
                self._check_unique_for(index, doc)
                index.add(doc)
            self._indexes.append(index)

    def index_fields(self) -> List[Tuple[str, ...]]:
        return [index.fields for index in self._indexes]

    # -------------------------------------------------------------------- writes
    def insert_one(self, document: Dict[str, Any]) -> str:
        doc = copy.deepcopy(document)
        with self._lock:
            if doc["_id"] in self._docs:
                raise DuplicateKeyError(f"{self.name}: duplicate _id {doc['_id']!r}")
            self._check_unique(doc)
            self._docs[doc["_id"]] = doc
            for index in self._indexes:
                index.add(doc)
        return doc["_id"]

    def replace_one(self, flt: Dict[str, Any], replacement: Dict[str, Any]) -> bool:
        with self._lock:
            current = self._first_match(flt)
            if current is None:
                return False
            new_doc = copy.deepcopy(replacement)
            new_doc["_id"] = current["_id"]
            self._check_unique(new_doc, ignore_id=current["_id"])
            self._swap(current, new_doc)
            return True

    def update_one(self, flt: Dict[str, Any], update: Dict[str, Any]) -> bool:
        with self._lock:
            current = self._first_match(flt)
            if current is None:
                return False
            self._swap(current, self._apply_update(current, update))
            return True

    def find_one_and_update(
        self, flt: Dict[str, Any], update: Dict[str, Any], sort: Optional[List[Tuple[str, int]]] = None
    ) -> Optional[Dict[str, Any]]:
        """Atomically find the first match, apply `update`, and return the NEW document (or None).

        This is the primitive for "claim a free resource": the match and the write happen under
        one lock, so two callers can never claim the same document.
        """
        with self._lock:
            matches = self._scan(flt)
            if sort:
                matches = self._sorted(matches, sort)
            if not matches:
                return None
            current = matches[0]
            updated = self._apply_update(current, update)
            self._swap(current, updated)
            return copy.deepcopy(updated)

    def delete_one(self, flt: Dict[str, Any]) -> bool:
        with self._lock:
            current = self._first_match(flt)
            if current is None:
                return False
            for index in self._indexes:
                index.remove(current)
            del self._docs[current["_id"]]
            return True

    # --------------------------------------------------------------------- reads
    def find_one(self, flt: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        with self._lock:
            match = self._first_match(flt or {})
            return copy.deepcopy(match) if match else None

    def find(
        self,
        flt: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Tuple[str, int]]] = None,
        limit: int = 0,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            matches = self._scan(flt or {})
            if sort:
                matches = self._sorted(matches, sort)
            if limit:
                matches = matches[:limit]
            return [copy.deepcopy(d) for d in matches]

    def count_documents(self, flt: Optional[Dict[str, Any]] = None) -> int:
        with self._lock:
            return len(self._scan(flt or {}))

    # ------------------------------------------------------------------ internals
    def _scan(self, flt: Dict[str, Any]) -> List[Dict[str, Any]]:
        self._stats.queries += 1
        candidates: Iterable[Dict[str, Any]]
        index = next((i for i in self._indexes if i.covered_by(flt)), None)
        if "_id" in flt and not isinstance(flt["_id"], dict):
            doc = self._docs.get(flt["_id"])
            candidates = [doc] if doc else []
            self._stats.index_hits += 1
        elif index is not None:
            ids = index.entries.get(tuple(flt[f] for f in index.fields), set())
            candidates = [self._docs[i] for i in sorted(ids)]
            self._stats.index_hits += 1
        else:
            candidates = list(self._docs.values())
            self._stats.full_scans += 1
        results = []
        for doc in candidates:
            self._stats.docs_examined += 1
            if _matches(doc, flt):
                results.append(doc)
        return results

    def _first_match(self, flt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        matches = self._scan(flt)
        return matches[0] if matches else None

    @staticmethod
    def _sorted(docs: List[Dict[str, Any]], sort: List[Tuple[str, int]]) -> List[Dict[str, Any]]:
        ordered = list(docs)
        for field_name, direction in reversed(sort):
            ordered.sort(key=lambda d: (d.get(field_name) is None, d.get(field_name)), reverse=direction < 0)
        return ordered

    def _apply_update(self, current: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        new_doc = copy.deepcopy(current)
        for op, fields in update.items():
            if op == "$set":
                new_doc.update(copy.deepcopy(fields))
            elif op == "$inc":
                for k, v in fields.items():
                    new_doc[k] = new_doc.get(k, 0) + v
            elif op == "$unset":
                for k in fields:
                    new_doc.pop(k, None)
            else:
                raise ValueError(f"unsupported update operator {op}")
        self._check_unique(new_doc, ignore_id=current["_id"])
        return new_doc

    def _swap(self, old: Dict[str, Any], new: Dict[str, Any]) -> None:
        for index in self._indexes:
            index.remove(old)
        self._docs[old["_id"]] = new
        for index in self._indexes:
            index.add(new)

    def _check_unique(self, doc: Dict[str, Any], ignore_id: Optional[str] = None) -> None:
        for index in self._indexes:
            self._check_unique_for(index, doc, ignore_id)

    def _check_unique_for(self, index: _Index, doc: Dict[str, Any], ignore_id: Optional[str] = None) -> None:
        if not index.unique:
            return
        existing = index.entries.get(index.key_for(doc), set()) - {ignore_id}
        if existing:
            raise DuplicateKeyError(f"{self.name}: duplicate key on {index.fields}")


class FakeMongoDatabase:
    """Hands out collections by name, like `client["nyc_health"]["appointments"]`."""

    def __init__(self, name: str = "nyc_health") -> None:
        self.name = name
        self.stats = QueryStats()
        self._lock = threading.RLock()
        self._collections: Dict[str, FakeCollection] = {}

    def __getitem__(self, collection_name: str) -> FakeCollection:
        if collection_name not in self._collections:
            self._collections[collection_name] = FakeCollection(collection_name, self.stats, self._lock)
        return self._collections[collection_name]

    def collection_names(self) -> List[str]:
        return sorted(self._collections)

    def reset_stats(self) -> None:
        self.stats.queries = self.stats.docs_examined = 0
        self.stats.index_hits = self.stats.full_scans = 0
