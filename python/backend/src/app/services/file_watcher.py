"""File watcher service — monitors vault for note changes and triggers re-indexing."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class VaultChangeHandler(FileSystemEventHandler):
    def __init__(self, vault_path: str, on_change: Callable[[str, str], None]) -> None:
        super().__init__()
        self.vault_path = vault_path
        self.on_change = on_change
        self._skip_hidden = True

    def _rel(self, path: str) -> str | None:
        """Convert absolute path to relative vault path. Returns None if hidden."""
        rel = os.path.relpath(path, self.vault_path).replace("\\", "/")
        parts = os.path.normpath(rel).split(os.sep)
        if self._skip_hidden and any(p.startswith(".") for p in parts):
            return None
        return rel if rel.endswith(".md") else None

    def on_created(self, event: Any) -> None:
        if event.is_directory:
            return
        rel = self._rel(event.src_path)
        if rel:
            self.on_change("create", rel)

    def on_modified(self, event: Any) -> None:
        if event.is_directory:
            return
        rel = self._rel(event.src_path)
        if rel:
            self.on_change("modify", rel)

    def on_deleted(self, event: Any) -> None:
        if event.is_directory:
            return
        rel = self._rel(event.src_path)
        if rel:
            self.on_change("delete", rel)


class FileWatcher:
    def __init__(self, vault_path: str, on_change: Callable[[str, str], None]) -> None:
        self.vault_path = vault_path
        self.on_change = on_change
        self._observer: Any = None

    def start(self) -> None:
        if not os.path.isdir(self.vault_path):
            logger.warning(
                "Vault path not found, file watcher not started: %s", self.vault_path
            )
            return
        handler = VaultChangeHandler(self.vault_path, self.on_change)
        self._observer = Observer()
        self._observer.schedule(handler, self.vault_path, recursive=True)
        self._observer.start()
        logger.info("File watcher started for vault: %s", self.vault_path)

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("File watcher stopped.")
