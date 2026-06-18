"""Artifact directory management."""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class ArtifactFile(BaseModel):
    name: str
    size: int
    modified_at: datetime


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def dir_for(self, task_id: int) -> Path:
        d = self.root / str(int(task_id))
        d.mkdir(parents=True, exist_ok=True)
        return d

    def list_for(self, task_id: int) -> list[ArtifactFile]:
        d = self.dir_for(task_id)
        out: list[ArtifactFile] = []
        for p in sorted(d.iterdir()):
            if not p.is_file():
                continue
            st = p.stat()
            out.append(
                ArtifactFile(
                    name=p.name,
                    size=st.st_size,
                    modified_at=datetime.utcfromtimestamp(st.st_mtime),
                )
            )
        return out

    def resolve_safe(self, task_id: int, filename: str) -> Path:
        if not _SAFE_NAME.match(filename):
            raise ValueError("invalid filename")
        d = self.dir_for(task_id).resolve()
        p = (d / filename).resolve()
        if not str(p).startswith(str(d) + "/") and p != d:
            raise ValueError("path traversal")
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(filename)
        return p

    def cleanup_older_than(self, days: int) -> int:
        threshold = time.time() - days * 86400
        removed = 0
        for sub in self.root.iterdir():
            if not sub.is_dir():
                continue
            try:
                if sub.stat().st_mtime < threshold:
                    for child in sub.rglob("*"):
                        if child.is_file():
                            child.unlink(missing_ok=True)
                    for child in sorted(sub.rglob("*"), reverse=True):
                        if child.is_dir():
                            child.rmdir()
                    sub.rmdir()
                    removed += 1
            except OSError:
                continue
        return removed
