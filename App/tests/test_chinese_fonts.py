import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection, TTFont

from app_state import ManagedStateStore
from chinese_fonts import COMMON_UI_TEXT, build_chinese_collection, validate_chinese_source
from font_generation import build_font
from font_detection import detect_weight_overrides, infer_family_label_from_strings
from fonts import FontPlanEntry, ValidationSummary, validate_selection
from operation import FontWorkflow, build_artifacts
from settings import CHINESE_WEIGHTS, get_system_weights


def make_font(path, family, weight=400, chinese=True):
    chars = set("ABC " + (COMMON_UI_TEXT if chinese else ""))
    cmap = {ord(char): f"uni{ord(char):04X}" for char in chars}
    names = [".notdef", *cmap.values()]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap(cmap)
    glyphs = {}
    for name in names:
        pen = TTGlyphPen(None)
        pen.moveTo((100, 0))
        pen.lineTo((400, 0))
        pen.lineTo((400, 700))
        pen.closePath()
        glyphs[name] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (1000, 0) for name in names})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": family, "styleName": "Regular",
                            "fullName": family, "psName": family.replace(" ", ""),
                            "uniqueFontIdentifier": family})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200,
                    usWinAscent=800, usWinDescent=200, usWeightClass=weight)
    builder.setupPost()
    builder.save(path)


class ChineseFontTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "custom.ttf"
        make_font(self.source, "Custom Chinese")
        self.donor = self.root / "msyh.ttc"
        collection = TTCollection()
        for family in ("Microsoft YaHei", "Microsoft YaHei UI"):
            path = self.root / (family.replace(" ", "") + ".ttf")
            make_font(path, family, 700)
            collection.fonts.append(TTFont(path))
        collection.save(self.donor)
        collection.close()

    def test_collection_keeps_both_identities_and_source_glyphs(self):
        output = self.root / "output.ttc"
        build_chinese_collection(self.source, self.donor, output)
        with TTCollection(output) as result, TTCollection(self.donor) as donor, TTFont(self.source) as source:
            self.assertEqual(len(result.fonts), 2)
            for built, original in zip(result.fonts, donor.fonts):
                self.assertEqual(built["name"].getBestFamilyName(), original["name"].getBestFamilyName())
                self.assertEqual(built["OS/2"].usWeightClass, 700)
                self.assertEqual(built.getBestCmap(), source.getBestCmap())
                self.assertEqual(built["glyf"].compile(built), source["glyf"].compile(source))

    def test_latin_only_source_is_rejected_before_output(self):
        latin = self.root / "latin.ttf"
        make_font(latin, "Latin Only", chinese=False)
        with self.assertRaisesRegex(ValueError, "缺少"):
            validate_chinese_source(latin)
        summary = validate_selection({"regular": str(latin)}, weights=CHINESE_WEIGHTS)
        self.assertFalse(summary.ok)

    def test_chinese_auto_detection_skips_fonts_without_ui_glyphs(self):
        latin = self.root / "latin.ttf"
        make_font(latin, "界面字体", chinese=False)
        self.assertEqual(infer_family_label_from_strings("界面字体"), "界面字体")
        detected = detect_weight_overrides(latin, weights={"yahei_regular": "msyh.ttc"})
        self.assertNotEqual(detected["yahei_regular"], str(latin))
        validate_chinese_source(detected["yahei_regular"])

    def test_artifact_pipeline_verifies_all_collection_faces(self):
        stage = self.root / "stage"
        stage.mkdir()
        backup = self.root / "backup"
        backup.mkdir()
        workflow = SimpleNamespace(paths=SimpleNamespace(backup_root=backup),
                                   identity_fonts_root=self.root, font_scale=125)
        entry = FontPlanEntry("yahei_regular", self.source, "manual", "msyh.ttc",
                              "Microsoft YaHei", "msyh.ttc", "Custom Chinese", "Custom Chinese")
        artifacts = build_artifacts(workflow, [entry], stage)
        self.assertTrue((stage / "msyh.ttc").is_file())
        self.assertEqual(len(artifacts["yahei_regular"]["hash"]), 64)
        with TTCollection(stage / "msyh.ttc") as result:
            self.assertEqual([font["head"].unitsPerEm for font in result.fonts], [800, 800])

    def test_scaled_static_font_keeps_design_units_and_changes_rendered_size(self):
        output = self.root / "scaled.ttf"
        donor = self.root / "MicrosoftYaHei.ttf"
        build_font(self.source, donor, output, font_scale=125)
        with TTFont(self.source) as source, TTFont(output) as result:
            self.assertEqual(result["head"].unitsPerEm, 800)
            self.assertEqual(result["hmtx"].metrics, source["hmtx"].metrics)
            self.assertEqual(result["name"].getBestFamilyName(), "Microsoft YaHei")

    def workflow(self):
        backup = self.root / "backup"
        backup.mkdir(exist_ok=True)
        paths = SimpleNamespace(backup_root=backup, local_root=self.root / "local",
                                make_temp_dir=lambda _: tempfile.mkdtemp(dir=self.root))
        report = SimpleNamespace(is_supported=True, is_admin=True, install_state="clean", issues=[], warnings=[])
        return FontWorkflow(paths, Mock(), ManagedStateStore(self.root / "state.json"),
                            SimpleNamespace(collect=lambda: report), self.root, self.root)

    def test_missing_backup_aborts_before_pending_changes(self):
        workflow = self.workflow()
        workflow.include_chinese = True
        workflow.validate = Mock(return_value=ValidationSummary(entries=[Mock()]))
        with patch("operation.backup_canonical_fonts", return_value=([], 0)), \
                patch("operation.cleanup_orphaned_pending_ops") as cleanup, \
                patch("operation.schedule_canonical_replacement") as schedule:
            result = workflow.apply({"regular": str(self.source)})
        self.assertFalse(result.success)
        self.assertIn("备份", result.message)
        cleanup.assert_not_called()
        schedule.assert_not_called()

    def test_recovery_includes_chinese_after_option_disabled(self):
        workflow = self.workflow()
        for name in CHINESE_WEIGHTS.values():
            (workflow.paths.backup_root / name).write_bytes(b"backup")
        with patch("operation.cleanup_orphaned_pending_ops", return_value=([], 0)), \
                patch("operation.schedule_canonical_restore", return_value=(3, [])) as restore, \
                patch("operation.purge_system_font_cache", return_value=[]), \
                patch("operation.refresh_windows_font_cache"):
            result = workflow.restore()
        self.assertTrue(result.success)
        self.assertTrue(set(CHINESE_WEIGHTS.values()).issubset(restore.call_args.args[1]))

    def test_reapply_without_chinese_keeps_existing_manifest(self):
        workflow = self.workflow()
        state = workflow.state_store.load_or_empty()
        existing = {"system_filename": "msyh.ttc", "sha256": "original-managed-hash"}
        state["install"]["fonts"] = {"yahei_regular": existing}
        workflow.state_store.save(state)
        workflow.validate = Mock(return_value=ValidationSummary(entries=[Mock()]))
        with patch("operation.backup_canonical_fonts", return_value=([], 20)), \
                patch("operation.build_artifacts", return_value={}), \
                patch("operation.cleanup_orphaned_pending_ops", return_value=([], 0)), \
                patch("operation.schedule_canonical_replacement", return_value=({}, [])), \
                patch("operation.purge_system_font_cache", return_value=[]), \
                patch("operation.refresh_windows_font_cache"):
            result = workflow.apply({"regular": str(self.source)})
        self.assertTrue(result.success)
        self.assertEqual(workflow.state_store.load()["install"]["fonts"]["yahei_regular"], existing)

    def test_build_failure_does_not_cancel_previous_pending_operations(self):
        workflow = self.workflow()
        workflow.validate = Mock(return_value=ValidationSummary(entries=[Mock()]))
        with patch("operation.backup_canonical_fonts", return_value=([], 20)), \
                patch("operation.build_artifacts", side_effect=ValueError("invalid donor")), \
                patch("operation.cleanup_orphaned_pending_ops") as cleanup:
            result = workflow.apply({"regular": str(self.source)})
        self.assertFalse(result.success)
        cleanup.assert_not_called()

    def test_chinese_mode_is_opt_in(self):
        self.assertFalse(set(CHINESE_WEIGHTS) & set(get_system_weights(self.root)))
        self.assertTrue(set(CHINESE_WEIGHTS).issubset(get_system_weights(self.root, include_chinese=True)))

    def test_collection_backup_family_matches_normalized_profile(self):
        from winsxs import expected_entry, profile
        self.assertEqual(profile(self.donor)["family_label"], expected_entry("msyh.ttc")["family_label"])


if __name__ == "__main__":
    unittest.main()
