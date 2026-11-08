import os
from dataclasses import dataclass
from pathlib import Path

from settings import APP_NAME


def _app_directory(base, override):
    explicit = os.environ.get(f"FONTSCAPE_{override}") or os.environ.get(f"FONTWIZARD_{override}")
    if explicit:
        return Path(explicit)
    current = base / APP_NAME
    legacy = base / "Font Wizard"
    return legacy if legacy.is_dir() and not current.exists() else current


@dataclass(frozen=True)
class RuntimePaths:
    source_root: Path
    project_root: Path

    data_root: Path
    local_root: Path
    managed_font_root: Path
    pending_ops_root: Path
    backup_root: Path
    log_root: Path
    temp_root: Path
    state_path: Path

    @classmethod
    def discover(cls):
        source_root = Path(__file__).resolve().parent
        project_root = source_root.parent

        data_root = _app_directory(Path(os.environ.get("PROGRAMDATA", project_root)), "DATA_DIR")
        local_root = _app_directory(Path(os.environ.get("LOCALAPPDATA", project_root)), "LOCAL_DIR")

        return cls(
            source_root=source_root,
            project_root=project_root,

            data_root=data_root,
            local_root=local_root,
            managed_font_root=data_root / "managed_fonts",
            pending_ops_root=data_root / "managed_fonts" / "pending_ops",
            backup_root=data_root / "backup",
            log_root=local_root / "logs",
            temp_root=local_root / "temp",
            state_path=data_root / "state.json",
        )

    def ensure_runtime_dirs(self):
        for path in (
            self.data_root,
            self.local_root,
            self.managed_font_root,
            self.pending_ops_root,
            self.backup_root,
            self.log_root,
            self.temp_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def make_temp_dir(self, prefix):
        import tempfile
        self.ensure_runtime_dirs()
        return Path(tempfile.mkdtemp(prefix=prefix, dir=self.temp_root))
