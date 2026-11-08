"""Build YaHei collections while retaining every original family identity."""

from fontTools.ttLib import TTCollection, TTFont

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


def build_chinese_collection(source_path, donor_path, output_path, font_scale=100):
    validate_chinese_source(source_path)
    result = TTCollection()
    try:
        with TTCollection(donor_path) as donor:
            if not donor.fonts:
                raise ValueError("原始微软雅黑字体集合为空。")
            for index in range(len(donor.fonts)):
                font = TTFont(source_path)
                result.fonts.append(font)
                apply_identity(font, read_segoe_identity(donor_path, index))
                apply_font_scale(font, font_scale)
        result.save(output_path)
    finally:
        result.close()
