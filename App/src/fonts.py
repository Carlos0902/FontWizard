from dataclasses import dataclass, field
from pathlib import Path

from font_detection import inspect_font
from settings import CJK_WEIGHTS, JHENGHEI_WEIGHTS, REGISTRY_NAMES, get_system_weights, mod_filename

@dataclass
class FontPlanEntry:
    weight: str
    source_path: Path
    source_label: str
    system_filename: str
    registry_name: str
    generated_filename: str
    family_name: str
    full_name: str


@dataclass
class ValidationSummary:
    entries: list[FontPlanEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors and bool(self.entries)


def resolve_font_selection(selection, weights=None):
    active_weights = weights if weights is not None else get_system_weights()
    regular_path = selection.get("regular")
    if not regular_path:
        return {}

    resolved = {}
    mono_fallback = selection.get("consolas_regular") or regular_path
    for weight in active_weights:
        if weight.startswith("consolas_"):
            resolved[weight] = selection.get(weight) or mono_fallback
        else:
            resolved[weight] = selection.get(weight) or regular_path
    return resolved


def validate_selection(selection, source_labels=None, weights=None):
    active_weights = weights if weights is not None else get_system_weights()
    summary = ValidationSummary()
    resolved = resolve_font_selection(selection, active_weights)
    if not resolved:
        summary.errors.append("Choose a regular font to continue.")
        return summary

    metadata_cache = {}
    ui_family_names = set()
    mono_family_names = set()
    variable_rejections = set()
    invalid_source_rejections = set()
    chinese_checked = set()
    source_labels = source_labels or {}

    for weight, source in resolved.items():
        source_path = Path(source)
        if not source_path.exists():
            summary.errors.append(f"Font file not found for {weight.replace('_', ' ')}.")
            continue
        cache_key = str(source_path.resolve())
        if cache_key not in metadata_cache:
            try:
                metadata_cache[cache_key] = inspect_font(source_path)
            except ValueError as exc:
                if cache_key not in invalid_source_rejections:
                    ext = source_path.suffix.lower()
                    if ext == ".otf":
                        summary.errors.append(
                            f"OpenType (.otf) fonts are not supported. "
                            f"System font replacement requires TrueType (.ttf) files. "
                            f"File: {source_path.name}"
                        )
                    elif ext != ".ttf":
                        summary.errors.append(
                            f"This file type ({ext}) is not supported. "
                            f"Choose a .ttf font file."
                        )
                    else:
                        summary.errors.append(str(exc))
                    invalid_source_rejections.add(cache_key)
                continue

        metadata = metadata_cache[cache_key]
        if weight in CJK_WEIGHTS and cache_key not in chinese_checked:
            from chinese_fonts import validate_chinese_source
            try:
                validate_chinese_source(source_path)
            except Exception as exc:
                summary.errors.append(str(exc))
            chinese_checked.add(cache_key)
        if metadata.is_variable and weight != "variable":
            if cache_key not in variable_rejections:
                summary.errors.append(
                    "Variable fonts can only be used for the Variable UI slot. Choose a static .ttf file for static weights."
                )
                variable_rejections.add(cache_key)
            continue

        if weight.startswith("consolas_"):
            mono_family_names.add(metadata.family_name)
        elif weight not in CJK_WEIGHTS:
            ui_family_names.add(metadata.family_name)

        system_filename = active_weights[weight]
        summary.entries.append(
            FontPlanEntry(
                weight=weight,
                source_path=metadata.path,
                source_label=source_labels.get(weight, "resolved"),
                system_filename=system_filename,
                registry_name=REGISTRY_NAMES[weight],
                generated_filename=mod_filename(system_filename, metadata.path),
                family_name=metadata.family_name,
                full_name=metadata.full_name,
            )
        )

    if len(ui_family_names) > 1 or len(mono_family_names) > 1:
        summary.warnings.append(
            "Selected styles come from multiple font families. Review them carefully before applying."
        )

    if any(weight.startswith("yahei_") for weight in active_weights):
        summary.warnings.append(
            "此操作会替换系统微软雅黑和微软雅黑 UI，影响使用这些系统字体的界面。"
            "需重启 Windows；应用内置字体可能不受影响。常用字检查不代表完整字库覆盖。"
        )
    if JHENGHEI_WEIGHTS.keys() & active_weights.keys():
        summary.warnings.append("将替换微软正黑体常规字重，也会影响使用该系统字体的其他应用。重启后请验证微信输入框。")

    return summary

