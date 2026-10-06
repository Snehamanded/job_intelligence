import shutil
import uuid
from pathlib import Path
from typing import Protocol

from sqlalchemy import delete, select

from app.core.config import Settings


class FileStorage(Protocol):
    """Where uploads live. Keys are generated here, never taken from users."""

    def save(self, user_id: uuid.UUID, data: bytes, extension: str) -> str: ...

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def delete_user(self, user_id: uuid.UUID) -> None: ...


def _new_key(user_id: uuid.UUID, extension: str) -> str:
    return f"{user_id}/{uuid.uuid4().hex}.{extension}"


class LocalFileStorage:
    """Stores files under STORAGE_PATH/<user_id>/<random>.<ext>. Keys never come from users."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("storage key escapes the storage root")
        return path

    def save(self, user_id: uuid.UUID, data: bytes, extension: str) -> str:
        key = _new_key(user_id, extension)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def delete_user(self, user_id: uuid.UUID) -> None:
        shutil.rmtree(self._path(str(user_id)), ignore_errors=True)


class DatabaseFileStorage:
    """Stores files in Postgres, for hosts whose disk is temporary or not shared with the worker
    (e.g. free web services). Uses its own short transactions."""

    def save(self, user_id: uuid.UUID, data: bytes, extension: str) -> str:
        from app.core.db import get_sessionmaker
        from app.models import StoredFile

        key = _new_key(user_id, extension)
        with get_sessionmaker()() as session:
            session.add(StoredFile(key=key, user_id=user_id, data=data))
            session.commit()
        return key

    def read(self, key: str) -> bytes:
        from app.core.db import get_sessionmaker
        from app.models import StoredFile

        with get_sessionmaker()() as session:
            data = session.scalar(select(StoredFile.data).where(StoredFile.key == key))
        if data is None:
            raise FileNotFoundError(key)
        return data

    def delete(self, key: str) -> None:
        from app.core.db import get_sessionmaker
        from app.models import StoredFile

        with get_sessionmaker()() as session:
            session.execute(delete(StoredFile).where(StoredFile.key == key))
            session.commit()

    def delete_user(self, user_id: uuid.UUID) -> None:
        from app.core.db import get_sessionmaker
        from app.models import StoredFile

        with get_sessionmaker()() as session:
            session.execute(delete(StoredFile).where(StoredFile.user_id == user_id))
            session.commit()


def get_storage(settings: Settings) -> FileStorage:
    if settings.storage_backend == "database":
        return DatabaseFileStorage()
    return LocalFileStorage(settings.storage_path)
