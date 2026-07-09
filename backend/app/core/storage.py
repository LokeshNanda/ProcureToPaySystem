import os
import uuid
from abc import ABC, abstractmethod

from app.core.config import settings


class StorageBackend(ABC):
    def generate_key(self, suffix: str = "") -> str:
        return f"{uuid.uuid4().hex}{suffix}"

    @abstractmethod
    async def save(self, key: str, data: bytes) -> str: ...

    @abstractmethod
    async def open(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    def url_for(self, key: str) -> str: ...


class LocalStorage(StorageBackend):
    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.root, key)

    async def save(self, key: str, data: bytes) -> str:
        with open(self._path(key), "wb") as f:
            f.write(data)
        return key

    async def open(self, key: str) -> bytes:
        with open(self._path(key), "rb") as f:
            return f.read()

    async def delete(self, key: str) -> None:
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass

    def url_for(self, key: str) -> str:
        return f"/files/{key}"


def get_storage() -> StorageBackend:
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_local_root)
    raise NotImplementedError(f"storage backend {settings.storage_backend} not implemented in Slice 0")
