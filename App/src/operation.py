import shutil
from dataclasses import dataclass, field
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont

from font_cache import refresh_windows_font_cache
from font_generation import build_font
from fonts import validate_selection
from operation_files import (
    backup_canonical_fonts,
    cleanup_orphaned_pending_ops,
    purge_system_font_cache,
    schedule_canonical_replacement,
    schedule_canonical_restore,
)
from settings import CHINESE_WEIGHTS, FONTS_DIR, default_registry_targets
from app_state import hash_file, iso_now


@dataclass
class OperationResult:
    success: bool
    message: str
    details: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class FontWorkflow:
    def __init__(
        self,
        paths,
        registry,
        state_store,
        preflight,
        identity_fonts_root=None,
        active_fonts_root=None,
    ):
        self.paths = paths
        self.registry = registry
        self.state_store = state_store
        self.preflight = preflight
        self.identity_fonts_root = Path(identity_fonts_root or FONTS_DIR)
        self.active_fonts_root = Path(active_fonts_root or FONTS_DIR)
        self.include_chinese = False
        self.include_explorer = False
        self.font_scale = 100

    def _explorer_service(self):
        from explorer_fonts import ExplorerFontService
        return ExplorerFontService(self.paths.local_root / "explorer-fonts.json")

    def _system_weights(self):
        from settings import get_system_weights
        return get_system_weights(self.identity_fonts_root, include_chinese=self.include_chinese)

    def _system_font_files(self):
        from settings import get_existing_mono_companions
        files = list(dict.fromkeys(self._system_weights().values()))
        target_dir = self.identity_fonts_root if self.identity_fonts_root.exists() else self.active_fonts_root
        for companion_file in get_existing_mono_companions(target_dir):
            if companion_file not in files:
                files.append(companion_file)
        return files

    def validate(self, selection, source_labels=None):
        return validate_selection(selection, source_labels, weights=self._system_weights())

    def apply(self, selection, source_labels=None, progress=None):
        report = self.preflight.collect()
        if not report.is_supported:
            return OperationResult(False, "Fontscape supports Windows 10 (build 10240+) and Windows 11.", report.issues, report.warnings)

        if not report.is_admin:
            return OperationResult(False, "Run Fontscape as Administrator before applying fonts.", report.issues, report.warnings)

        if report.install_state == "pending_reboot_recovery":
            return OperationResult(
                False,
                "Restart Windows before applying another font.",
                ["A previous recovery still has file updates waiting for restart."],
                report.warnings,
            )

        previous_install = self.state_store.load_or_empty().get("install", {})
        if (report.install_state == "pending_reboot_apply"
                and bool(previous_install.get("include_chinese")) != self.include_chinese):
            return OperationResult(False, "请先重启 Windows 完成上次替换，再切换中文兼容模式。")

        summary = self.validate(selection, source_labels)
        if not summary.ok:
            return OperationResult(False, summary.errors[0] if summary.errors else "The selected font cannot be used.", summary.errors, summary.warnings)

        stage_dir = self.paths.make_temp_dir("fontwizard-build-")
        system_files = self._system_font_files()

        try:
            self._emit(progress, 5, "Backing up original Windows system fonts...")
            backup_warnings, backed_count = backup_canonical_fonts(self, system_files)
            if self.include_chinese:
                # Never replace a collection without a verified, restorable donor.
                from winsxs import expected_entry, is_authentic_font
                for name in CHINESE_WEIGHTS.values():
                    backup = self.paths.backup_root / name
                    if not backup.is_file() or not is_authentic_font(backup, expected_entry(name)):
                        raise RuntimeError(f"未找到可验证的原始中文字体备份：{name}。未安排字体替换。")
            if backed_count < len(system_files):
                backup_warnings.append(
                    f"Note: {backed_count} of {len(system_files)} original fonts were backed up."
                )

            self._emit(progress, 30, "Compiling custom TrueType font weights...")
            artifacts = build_artifacts(self, summary.entries, stage_dir)

            if self.include_explorer:
                self._explorer_service().prepare()

            self._emit(progress, 70, "Cleaning up old pending operations...")
            pending_cleanup_warnings, _ = cleanup_orphaned_pending_ops(self)

            self._emit(progress, 75, "Scheduling physical in-place replacement on boot...")
            manifest, schedule_warnings = schedule_canonical_replacement(self, artifacts)
            if not self.include_chinese:
                # Unchecking stops future changes; preserve active Chinese fonts
                # in the manifest so verification and Recovery still cover them.
                for key, value in previous_install.get("fonts", {}).items():
                    if key in CHINESE_WEIGHTS:
                        manifest.setdefault(key, value)

            self._emit(progress, 88, "Purging system font caches...")
            cache_warnings = purge_system_font_cache()
            refresh_windows_font_cache()

            # Ensure Segoe WPC substitute is set in registry
            try:
                self.registry.ensure_font_substitutes()
            except Exception:
                pass

            self._emit(progress, 95, "Saving installation state...")
            explorer_warnings = []
            if self.include_explorer:
                try:
                    self._explorer_service().apply()
                except Exception as exc:
                    explorer_warnings.append(f"资源管理器字体设置未完成：{exc}；系统字体仍已安排重启替换。")
            state = self.state_store.load_or_empty()
            state["install"] = {
                "status": "pending_reboot_apply",
                "include_chinese": self.include_chinese,
                "include_explorer": self.include_explorer,
                "font_scale": self.font_scale,
                "fonts": manifest,
                "backed_up_count": backed_count,
                "applied_at": iso_now(),
                "restored_at": None,
            }
            state["last_action"] = {
                "kind": "apply",
                "status": "success",
                "timestamp": iso_now(),
                "details": "Scheduled physical in-place replacement on boot.",
            }
            self.state_store.save(state)

            self._emit(progress, 100, "Font setup complete!")
            all_warnings = [
                *summary.warnings,
                *backup_warnings,
                *pending_cleanup_warnings,
                *schedule_warnings,
                *cache_warnings,
                *explorer_warnings,
            ]
            return OperationResult(
                True,
                "Font changes scheduled. Restart Windows now to finish applying your font.",
                warnings=all_warnings,
            )
        except Exception as exc:
            state = self.state_store.load_or_empty()
            state["last_action"] = {
                "kind": "apply",
                "status": "failed",
                "timestamp": iso_now(),
                "details": str(exc),
            }
            self.state_store.save(state)
            return OperationResult(False, f"Failed to apply font changes: {exc}", [str(exc)], summary.warnings)
        finally:
            shutil.rmtree(stage_dir, ignore_errors=True)

    def restore(self, progress=None):
        report = self.preflight.collect()
        if not report.is_admin:
            return OperationResult(False, "Run Fontscape as Administrator before restoring fonts.", report.issues, report.warnings)

        system_files = self._system_font_files()

        # Recovery must include Chinese fonts even after the option is unchecked
        # or the application has been restarted without a selected source font.
        for name in CHINESE_WEIGHTS.values():
            if (self.paths.backup_root / name).is_file() and name not in system_files:
                system_files.append(name)

        try:
            self._emit(progress, 10, "Cleaning up stale pending files...")
            pending_cleanup_warnings, _ = cleanup_orphaned_pending_ops(self)

            self._emit(progress, 35, "Scheduling restore of original fonts on boot...")
            scheduled_count, restore_warnings = schedule_canonical_restore(self, system_files)
            explorer_warnings = []
            explorer_restored = False
            try:
                explorer_restored = self._explorer_service().restore()
            except Exception as exc:
                explorer_warnings.append(f"资源管理器字体设置恢复未完成：{exc}；请保留备份并重试恢复。")
            if scheduled_count == 0:
                if explorer_restored:
                    return OperationResult(
                        True, "资源管理器原始字体设置已恢复。未找到可用于恢复系统字体文件的备份。",
                        warnings=[*restore_warnings, *explorer_warnings],
                    )
                return OperationResult(
                    False,
                    "No authentic backup font files were found. You can restore original Windows fonts by running 'sfc /scannow' or 'DISM /Online /Cleanup-Image /RestoreHealth' in an Administrator terminal.",
                    [*restore_warnings, *explorer_warnings],
                )

            self._emit(progress, 75, "Purging system font caches...")
            cache_warnings = purge_system_font_cache()
            refresh_windows_font_cache()

            # Clean up FontSubstitutes overrides on restore
            try:
                self.registry.remove_font_substitutes()
            except Exception:
                pass

            self._emit(progress, 92, "Saving restore state...")
            state = self.state_store.load_or_empty()
            state["install"] = {
                "status": "pending_reboot_recovery",
                "fonts": {},
                "applied_at": state.get("install", {}).get("applied_at"),
                "restored_at": iso_now(),
            }
            state["last_action"] = {
                "kind": "restore",
                "status": "success",
                "timestamp": iso_now(),
                "details": f"Scheduled restore of {scheduled_count} original Microsoft fonts on boot.",
            }
            self.state_store.save(state)

            self._emit(progress, 100, "Font restore scheduled!")
            all_warnings = [
                *pending_cleanup_warnings,
                *restore_warnings,
                *cache_warnings,
                *explorer_warnings,
            ]
            return OperationResult(
                True,
                f"Original Windows fonts ({scheduled_count}/{len(system_files)}) scheduled for restore. Restart Windows now to finish.",
                warnings=all_warnings,
            )
        except Exception as exc:
            return OperationResult(False, f"Font restore failed: {exc}", [str(exc)])

    def _emit(self, callback, value, message):
        if callback:
            callback(value, message)


def _verify_build_output(output_path: Path, segoe_path: Path, font_number=-1):
    built_font = None
    donor_font = None
    try:
        try:
            built_font = TTFont(output_path, fontNumber=font_number)
        except Exception as exc:
            raise RuntimeError(f"Built font could not be reopened: {output_path.name}") from exc

        try:
            donor_font = TTFont(segoe_path, fontNumber=font_number)
        except Exception as exc:
            raise RuntimeError(f"Could not inspect donor font: {segoe_path.name}") from exc

        expected = {
            "family_name": donor_font["name"].getBestFamilyName(),
            "full_name": donor_font["name"].getBestFullName(),
            "subfamily_name": donor_font["name"].getBestSubFamilyName(),
            "mac_style": donor_font["head"].macStyle,
            "os2_version": donor_font["OS/2"].version,
            "weight_class": donor_font["OS/2"].usWeightClass,
            "width_class": donor_font["OS/2"].usWidthClass,
            "fs_selection": donor_font["OS/2"].fsSelection,
            "italic_angle": donor_font["post"].italicAngle,
        }
        actual = {
            "family_name": built_font["name"].getBestFamilyName(),
            "full_name": built_font["name"].getBestFullName(),
            "subfamily_name": built_font["name"].getBestSubFamilyName(),
            "mac_style": built_font["head"].macStyle,
            "os2_version": built_font["OS/2"].version,
            "weight_class": built_font["OS/2"].usWeightClass,
            "width_class": built_font["OS/2"].usWidthClass,
            "fs_selection": built_font["OS/2"].fsSelection,
            "italic_angle": built_font["post"].italicAngle,
        }

        for key, expected_value in expected.items():
            if actual[key] != expected_value:
                if ("fvar" in built_font or "fvar" in donor_font) and key in ("os2_version", "weight_class", "fs_selection"):
                    continue
                raise RuntimeError(
                    f"Built font identity check failed for {output_path.name}: "
                    f"{key} was {actual[key]!r}, expected {expected_value!r}."
                )
    finally:
        if built_font is not None:
            built_font.close()
        if donor_font is not None:
            donor_font.close()


def build_artifacts(workflow, entries, stage_dir):
    artifacts = {}
    mono_regular_entry = None
    for entry in entries:
        if entry.weight == "consolas_regular":
            mono_regular_entry = entry

        backup_segoe = workflow.paths.backup_root / entry.system_filename
        if backup_segoe.exists() and backup_segoe.stat().st_size > 50_000:
            segoe_path = backup_segoe
        else:
            segoe_path = workflow.identity_fonts_root / entry.system_filename
        output_path = stage_dir / entry.system_filename

        if entry.system_filename.lower().endswith(".ttc"):
            from chinese_fonts import build_chinese_collection
            build_chinese_collection(entry.source_path, segoe_path, output_path, workflow.font_scale)
            with TTCollection(segoe_path) as donor, TTCollection(output_path) as built:
                if len(donor.fonts) != len(built.fonts):
                    raise RuntimeError(f"字体集合成员数量不一致：{output_path.name}")
                for index in range(len(donor.fonts)):
                    _verify_build_output(output_path, segoe_path, index)
        elif entry.system_filename.lower() == "seguivar.ttf":
            from font_generation import build_variable_font
            build_variable_font(entry.source_path, segoe_path, output_path, workflow.font_scale)
        else:
            build_font(entry.source_path, segoe_path, output_path, workflow.font_scale)
        if not entry.system_filename.lower().endswith(".ttc"):
            _verify_build_output(output_path, segoe_path)

        artifacts[entry.weight] = {
            "weight": entry.weight,
            "registry_name": entry.registry_name,
            "system_filename": entry.system_filename,
            "generated_filename": entry.system_filename,
            "source_path": str(entry.source_path),
            "family_name": entry.family_name,
            "full_name": entry.full_name,
            "staged_path": str(output_path),
            "hash": hash_file(output_path),
        }

    if mono_regular_entry is not None:
        from font_detection import inspect_font
        from settings import get_existing_mono_companions
        try:
            mono_meta = inspect_font(mono_regular_entry.source_path)
            is_mono = getattr(mono_meta, "is_monospace", False) or mono_regular_entry.source_label == "manual"
        except Exception:
            is_mono = True

        if is_mono:
            companions = get_existing_mono_companions(workflow.identity_fonts_root)
            for companion_file, companion_reg_name in companions.items():
                backup_comp = workflow.paths.backup_root / companion_file
                if backup_comp.exists() and backup_comp.stat().st_size > 50_000:
                    companion_sys_path = backup_comp
                else:
                    companion_sys_path = workflow.identity_fonts_root / companion_file
                companion_out_path = stage_dir / companion_file
                build_font(mono_regular_entry.source_path, companion_sys_path, companion_out_path, workflow.font_scale)
                _verify_build_output(companion_out_path, companion_sys_path)
                companion_key = f"mono_companion_{companion_file.lower().replace('.', '_')}"
                artifacts[companion_key] = {
                    "weight": companion_key,
                    "registry_name": companion_reg_name,
                    "system_filename": companion_file,
                    "generated_filename": companion_file,
                    "source_path": str(mono_regular_entry.source_path),
                    "family_name": mono_regular_entry.family_name,
                    "full_name": mono_regular_entry.full_name,
                    "staged_path": str(companion_out_path),
                    "hash": hash_file(companion_out_path),
                }

    return artifacts
