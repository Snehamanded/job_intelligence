import shutil
import uuid
from pathlib import Path

from app.core.config import Settings


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
        key = f"{user_id}/{uuid.uuid4().hex}.{extension}"
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


def get_storage(settings: Settings) -> LocalFileStorage:
    return LocalFileStorage(settings.storage_path)
