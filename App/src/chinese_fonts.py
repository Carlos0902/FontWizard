"""Build Windows CJK collections while retaining their family identities."""

from fontTools.misc.fixedTools import otRound
from fontTools.ttLib import TTCollection, TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
from fontTools.ttLib.tables.ttProgram import Program

from font_generation import apply_font_scale, apply_identity, read_segoe_identity


CJK_SAMPLE = "中文字体微软雅黑聊天消息你好世界测试，。！？（）"
COMMON_UI_TEXT = CJK_SAMPLE + "文件编辑查看设置保存打开关闭搜索复制粘贴删除确认取消系统更新网络账号登录输入发送下载"


def validate_chinese_source(path):
    with TTFont(path) as font:
        if "glyf" not in font or "fvar" in font:
            raise ValueError("中文替换需要静态 TrueType (.ttf) 字体。")
        cmap = font.getBestCmap() or {}
        missing = [char for char in dict.fromkeys(COMMON_UI_TEXT) if not cmap.get(ord(char))
                   or cmap[ord(char)] == ".notdef"]
        if missing:
            raise ValueError(
                f"中文字体缺少常用汉字或标点：{''.join(missing)}。请选择包含中文的字体。"
            )


def _preserve_original_coverage(font, donor):
    source_cmap = font.getBestCmap()
    donor_cmap = donor.getBestCmap()
    missing = {code: name for code, name in donor_cmap.items()
               if name != ".notdef" and source_cmap.get(code) in (None, ".notdef")}
    if not missing:
        return

    order = font.getGlyphOrder().copy()
    if len(order) + len(set(missing.values())) > 65535:
        raise ValueError("补齐微软正黑体字符后将超过 TrueType 字形数量上限，请选择其他字体。")
    scale = font["head"].unitsPerEm / donor["head"].unitsPerEm
    donor_glyf = donor["glyf"]
    glyphs = {}
    for code, name in missing.items():
        if name in glyphs:
            continue
        glyph_name = f"fontscape.fallback.{code:06X}"
        while glyph_name in font["glyf"]:
            glyph_name += "_"
        # Flatten composites and omit the donor's hinting program, which
        # would reference the donor's control values and font program.
        points, endpoints, flags = donor_glyf[name].getCoordinates(donor_glyf)
        glyph = Glyph()
        glyph.numberOfContours = len(endpoints)
        glyph.coordinates = GlyphCoordinates((otRound(x * scale), otRound(y * scale)) for x, y in points)
        glyph.endPtsOfContours = list(endpoints)
        glyph.flags = flags[:]
        glyph.program = Program()
        glyph.program.fromBytecode([])
        font["glyf"][glyph_name] = glyph
        order.append(glyph_name)
        for tag in ("hmtx", "vmtx"):
            if tag in font:
                metrics = donor[tag].metrics[name]
                font[tag].metrics[glyph_name] = tuple(otRound(value * scale) for value in metrics)
        glyphs[name] = glyph_name

    font.setGlyphOrder(order)
    for table in font["cmap"].tables:
        if table.isUnicode() and table.format in (4, 12):
            table.cmap.update({code: glyphs[name] for code, name in missing.items()
                               if table.format == 12 or code < 0xFFFF})
    if any(font.getBestCmap().get(code) != glyphs[name] for code, name in missing.items()):
        raise ValueError("无法完整保留微软正黑体的字符映射，请选择其他字体。")


def build_chinese_collection(source_path, donor_path, output_path, font_scale=100, *, preserve_coverage=False):
    validate_chinese_source(source_path)
    result = TTCollection()
    try:
        with TTCollection(donor_path) as donor:
            if not donor.fonts:
                raise ValueError("原始中文字体集合为空。")
            for index, original in enumerate(donor.fonts):
                font = TTFont(source_path)
                result.fonts.append(font)
                if preserve_coverage:
                    _preserve_original_coverage(font, original)
                apply_identity(font, read_segoe_identity(donor_path, index))
                apply_font_scale(font, font_scale)
        result.save(output_path)
    finally:
        result.close()
