import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from explorer_fonts import ExplorerFontService, SNAPSHOT_KEYS, with_family


def snapshot(family="Original"):
    # Distinct sizes/weights and byte flags, to catch accidental resets.
    return {key: (bytes([index + 1]) * 28 + family.encode("utf-16-le").ljust(64, b"\0")).hex()
            for index, key in enumerate(SNAPSHOT_KEYS)}


class FakeShell:
    def __init__(self):
        self.value = snapshot()
        self.fail_next = False

    def snapshot(self):
        return copy.deepcopy(self.value)

    def replace(self, value):
        self.value = copy.deepcopy(value)
        if self.fail_next:
            self.fail_next = False
            raise OSError("simulated partial write")


class ExplorerFontsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "explorer-fonts.json"
        self.shell = FakeShell()
        self.service = ExplorerFontService(self.path, self.shell)

    def test_only_family_changes(self):
        original = snapshot()
        changed = with_family(original, "Segoe UI")
        for key in SNAPSHOT_KEYS:
            self.assertEqual(bytes.fromhex(changed[key])[:28], bytes.fromhex(original[key])[:28])
            self.assertEqual(bytes.fromhex(changed[key])[28:].decode("utf-16-le").rstrip("\0"), "Segoe UI")

    def test_reapply_and_restart_keep_first_backup(self):
        original = self.shell.snapshot()
        self.service.apply()
        self.assertNotEqual(self.shell.snapshot(), original)
        restarted = ExplorerFontService(self.path, self.shell)
        restarted.apply()
        self.assertEqual(json.loads(self.path.read_text())["original"], original)
        self.assertTrue(restarted.restore())
        self.assertEqual(self.shell.snapshot(), original)
        self.assertFalse(restarted.restore())

    def test_partial_write_rolls_back_and_keeps_original(self):
        original = self.shell.snapshot()
        self.shell.fail_next = True
        with self.assertRaises(OSError):
            self.service.apply()
        self.assertEqual(self.shell.snapshot(), original)
        self.assertEqual(json.loads(self.path.read_text())["original"], original)

    def test_corrupt_backup_blocks_apply(self):
        self.path.write_text('{"version":1,"active":true,"original":{}}')
        original = self.shell.snapshot()
        with self.assertRaises(ValueError):
            self.service.apply()
        self.assertEqual(self.shell.snapshot(), original)

    def test_next_apply_after_restore_backs_up_new_user_settings(self):
        self.service.apply()
        self.service.restore()
        new = snapshot("Changed by user")
        self.shell.value = new
        self.service.apply()
        self.service.restore()
        self.assertEqual(self.shell.snapshot(), new)

    def test_prepare_persists_without_changing_current_fonts(self):
        original = self.shell.snapshot()
        self.service.prepare()
        self.assertEqual(self.shell.snapshot(), original)
        self.assertEqual(json.loads(self.path.read_text())["original"], original)

    def test_restore_preserves_distinct_next_login_fonts(self):
        self.shell.persistent = snapshot("Next login font")
        self.shell.persistent_snapshot = lambda: copy.deepcopy(self.shell.persistent)
        self.shell.restore_persistent = lambda value: setattr(self.shell, "persistent", copy.deepcopy(value))
        original_persistent = copy.deepcopy(self.shell.persistent)
        self.service.apply()
        self.shell.persistent = snapshot("Segoe UI")
        self.service.restore()
        self.assertEqual(self.shell.persistent, original_persistent)


if __name__ == "__main__":
    unittest.main()
