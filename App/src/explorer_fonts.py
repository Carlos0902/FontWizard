"""Current-user Shell fonts, backed up separately from system font files."""

import ctypes
import json
import os
import winreg
from ctypes import wintypes
from pathlib import Path


class LOGFONTW(ctypes.Structure):
    _fields_ = [(name, wintypes.LONG) for name in
                ("lfHeight", "lfWidth", "lfEscapement", "lfOrientation", "lfWeight")] + [
        (name, wintypes.BYTE) for name in ("lfItalic", "lfUnderline", "lfStrikeOut",
        "lfCharSet", "lfOutPrecision", "lfClipPrecision", "lfQuality", "lfPitchAndFamily")
    ] + [("lfFaceName", wintypes.WCHAR * 32)]


class NONCLIENTMETRICSW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT), ("iBorderWidth", ctypes.c_int),
        ("iScrollWidth", ctypes.c_int), ("iScrollHeight", ctypes.c_int),
        ("iCaptionWidth", ctypes.c_int), ("iCaptionHeight", ctypes.c_int),
        ("lfCaptionFont", LOGFONTW), ("iSmCaptionWidth", ctypes.c_int),
        ("iSmCaptionHeight", ctypes.c_int), ("lfSmCaptionFont", LOGFONTW),
        ("iMenuWidth", ctypes.c_int), ("iMenuHeight", ctypes.c_int),
        ("lfMenuFont", LOGFONTW), ("lfStatusFont", LOGFONTW),
        ("lfMessageFont", LOGFONTW), ("iPaddedBorderWidth", ctypes.c_int),
    ]


FONT_FIELDS = ("lfCaptionFont", "lfSmCaptionFont", "lfMenuFont", "lfStatusFont", "lfMessageFont")
SNAPSHOT_KEYS = ("icon", *FONT_FIELDS)
REGISTRY_FONTS = dict(zip(SNAPSHOT_KEYS, (
    "IconFont", "CaptionFont", "SmCaptionFont", "MenuFont", "StatusFont", "MessageFont")))
WINDOW_METRICS = r"Control Panel\Desktop\WindowMetrics"


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != set(SNAPSHOT_KEYS):
        raise ValueError("资源管理器字体备份格式不正确，未修改设置。")
    for value in snapshot.values():
        if not isinstance(value, str) or len(bytes.fromhex(value)) != 92:
            raise ValueError("资源管理器字体备份损坏，未修改设置。")


def with_family(snapshot, family):
    validate_snapshot(snapshot)
    encoded = family.encode("utf-16-le")
    if not encoded or len(encoded) > 62 or "\0" in family:
        raise ValueError("Windows 界面字体名称过长或无效。")
    # Change only lfFaceName. Keep size, weight, charset and rendering flags.
    return {key: (bytes.fromhex(value)[:28] + encoded.ljust(64, b"\0")).hex()
            for key, value in snapshot.items()}


def validate_persistent(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != set(SNAPSHOT_KEYS):
        raise ValueError("持久化字体备份格式不正确。")
    for value in snapshot.values():
        if value is not None and (not isinstance(value, str) or len(bytes.fromhex(value)) != 92):
            raise ValueError("持久化字体备份损坏。")


class WindowsShellFonts:
    def __init__(self):
        self.spi = ctypes.WinDLL("user32", use_last_error=True).SystemParametersInfoW
        self.spi.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
        self.spi.restype = wintypes.BOOL

    def _call(self, action, data, flags=0):
        if not self.spi(action, ctypes.sizeof(data), ctypes.byref(data), flags):
            raise ctypes.WinError(ctypes.get_last_error())

    def _metrics(self):
        data = NONCLIENTMETRICSW()
        data.cbSize = ctypes.sizeof(data)
        self._call(0x0029, data)  # SPI_GETNONCLIENTMETRICS
        return data

    def snapshot(self):
        icon = LOGFONTW()
        self._call(0x001F, icon)  # SPI_GETICONTITLELOGFONT
        metrics = self._metrics()
        return {"icon": bytes(icon).hex(), **{
            field: bytes(getattr(metrics, field)).hex() for field in FONT_FIELDS}}

    def replace(self, snapshot):
        validate_snapshot(snapshot)
        # Read non-font metrics afresh so spacing/scrollbar dimensions survive.
        metrics = self._metrics()
        for field in FONT_FIELDS:
            setattr(metrics, field, LOGFONTW.from_buffer_copy(bytes.fromhex(snapshot[field])))
        icon = LOGFONTW.from_buffer_copy(bytes.fromhex(snapshot["icon"]))
        self._call(0x0022, icon, 3)  # SETICONTITLELOGFONT; persist + notify
        self._call(0x002A, metrics, 3)  # SETNONCLIENTMETRICS; persist + notify
        if self.snapshot() != snapshot:
            raise RuntimeError("Windows 未保留请求的字体设置。")

    def persistent_snapshot(self):
        result = {}
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOW_METRICS) as key:
            for field, name in REGISTRY_FONTS.items():
                try:
                    value, kind = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    result[field] = None
                    continue
                if kind != winreg.REG_BINARY or len(value) != 92:
                    raise ValueError(f"无法备份非标准 Windows 字体设置：{name}")
                result[field] = value.hex()
        return result

    def _write_persistent(self, snapshot):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOW_METRICS, 0, winreg.KEY_SET_VALUE) as key:
            for field, name in REGISTRY_FONTS.items():
                value = snapshot[field]
                if value is None:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
                else:
                    winreg.SetValueEx(key, name, 0, winreg.REG_BINARY, bytes.fromhex(value))

    def restore_persistent(self, snapshot):
        validate_persistent(snapshot)
        before = self.persistent_snapshot()
        try:
            self._write_persistent(snapshot)
            if self.persistent_snapshot() != snapshot:
                raise RuntimeError("原始字体注册表设置恢复校验失败。")
        except Exception:
            self._write_persistent(before)
            raise


class ExplorerFontService:
    def __init__(self, backup_path, backend=None):
        self.backup_path = Path(backup_path)
        self.backend = backend if backend is not None else WindowsShellFonts()

    def _load(self):
        if not self.backup_path.exists():
            return None
        data = json.loads(self.backup_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1 or type(data.get("active")) is not bool:
            raise ValueError("资源管理器字体备份版本或格式不正确。")
        validate_snapshot(data.get("original"))
        if "persistent" in data:
            validate_persistent(data["persistent"])
        return data

    def _save(self, data):
        self.backup_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.backup_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temporary, self.backup_path)
        if self._load() != data:
            raise RuntimeError("资源管理器字体备份写入校验失败。")

    def _replace(self, target):
        before = self.backend.snapshot()
        try:
            self.backend.replace(target)
        except Exception as exc:
            try:
                self.backend.replace(before)
            except Exception as rollback:
                raise RuntimeError(f"字体设置失败：{exc}；回滚失败：{rollback}。原始备份已保留。") from exc
            raise

    def prepare(self):
        """Persist the original before scheduling any system font changes."""
        backup = self._load()
        if backup is None or not backup["active"]:
            original = self.backend.snapshot()
            validate_snapshot(original)
            data = {"version": 1, "active": True, "original": original}
            if hasattr(self.backend, "persistent_snapshot"):
                data["persistent"] = self.backend.persistent_snapshot()
                validate_persistent(data["persistent"])
            self._save(data)

    def has_active_backup(self):
        backup = self._load()
        return bool(backup and backup["active"])

    def apply(self):
        self.prepare()
        self._replace(with_family(self.backend.snapshot(), "Segoe UI"))

    def restore(self):
        backup = self._load()
        if backup is None or not backup["active"]:
            return False
        self._replace(backup["original"])
        if "persistent" in backup:
            # Persisted settings can differ from the current session. Preserve
            # both rather than silently replacing the user's next-login fonts.
            self.backend.restore_persistent(backup["persistent"])
        self._save({**backup, "active": False})
        return True
