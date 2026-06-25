from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path
    data_dir: Path
    logs_dir: Path
    backups_dir: Path
    documents_dir: Path

    @classmethod
    def from_workspace(cls, root: Path) -> AppPaths:
        base = root.resolve()
        return cls(
            root=base,
            data_dir=base / "data",
            logs_dir=base / "logs",
            backups_dir=base / "backups",
            documents_dir=base / "documents",
        )

    def ensure_directories(self) -> None:
        for directory in [self.data_dir, self.logs_dir, self.backups_dir, self.documents_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def resolve_app_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path
