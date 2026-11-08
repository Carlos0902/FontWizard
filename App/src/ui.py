import ctypes
import math
import re
import subprocess
import sys
import time
import winreg
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QSize, QPoint, QPointF, QRect, QRectF, QUrl, QTimer, QEvent, QPropertyAnimation, QAbstractAnimation, QEasingCurve, QVariantAnimation
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QFontMetrics, QIcon, QImage, QLinearGradient, QRadialGradient, QColor, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QBoxLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
    QLayout,
)

from settings import APP_GITHUB_URL, APP_NAME, CJK_WEIGHTS, WEIGHT_TARGETS
from core import FontWizardController
from font_detection import inspect_font
from font_generation import MAX_FONT_SCALE, MIN_FONT_SCALE
from operation import OperationResult

WM_SETTINGCHANGE = 0x001A
WM_THEMECHANGED = 0x031A
WM_DWMCOLORIZATIONCOLORCHANGED = 0x0320

def is_windows_11() -> bool:
    try:
        winver = sys.getwindowsversion()
        return winver.major == 10 and winver.build >= 22000
    except Exception:
        return False

def get_windows_accent_color(is_dark: bool = True) -> tuple[str, str, str, str]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent") as key:
            palette, _ = winreg.QueryValueEx(key, "AccentPalette")
            if len(palette) >= 32:
                colors = []
                for i in range(0, 32, 4):
                    chunk = palette[i:i+4]
                    colors.append(f"#{chunk[0]:02X}{chunk[1]:02X}{chunk[2]:02X}")
                if is_dark:
                    return colors[3], colors[2], "#FFFFFF", colors[1]
                else:
                    return colors[4], colors[3], "#FFFFFF", colors[5]
    except Exception:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
            val, _ = winreg.QueryValueEx(key, "AccentColor")
            r = val & 0xFF
            g = (val >> 8) & 0xFF
            b = (val >> 16) & 0xFF
            if is_dark:
                r_h = min(255, int(r * 1.25 + 30))
                g_h = min(255, int(g * 1.25 + 30))
                b_h = min(255, int(b * 1.25 + 30))
                r_i = min(255, int(r * 1.45 + 50))
                g_i = min(255, int(g * 1.45 + 50))
                b_i = min(255, int(b * 1.45 + 50))
            else:
                r_h = max(0, int(r * 0.85))
                g_h = max(0, int(g * 0.85))
                b_h = max(0, int(b * 0.85))
                r_i = r
                g_i = g
                b_i = b
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            text_color = "#000000" if lum > 160 else "#FFFFFF"
            return f"#{r:02X}{g:02X}{b:02X}", f"#{r_h:02X}{g_h:02X}{b_h:02X}", text_color, f"#{r_i:02X}{g_i:02X}{b_i:02X}"
    except Exception:
        pass
    return ("#2993CC", "#59C5FF", "#FFFFFF", "#80D2FF") if is_dark else ("#006499", "#2993CC", "#FFFFFF", "#004B73")

def get_theme_colors(is_dark: bool, is_win11: bool = True) -> dict[str, str]:
    accent, accent_hover, accent_text, accent_icon = get_windows_accent_color(is_dark)
    if is_dark:
        return {
            "bg_window": "transparent" if is_win11 else "#202020",
            "bg_card": "rgba(255, 255, 255, 0.04)" if is_win11 else "#2B2B2B",
            "bg_card_hover": "rgba(255, 255, 255, 0.07)" if is_win11 else "#353535",
            "bg_button": "rgba(255, 255, 255, 0.06)" if is_win11 else "#2D2D2D",
            "bg_button_hover": "rgba(255, 255, 255, 0.09)" if is_win11 else "#383838",
            "bg_button_pressed": "rgba(255, 255, 255, 0.03)" if is_win11 else "#242424",
            "border_card": "rgba(255, 255, 255, 0.08)" if is_win11 else "#383838",
            "border_button": "rgba(255, 255, 255, 0.08)" if is_win11 else "#383838",

            "text_primary": "#FFFFFF",
            "text_secondary": "rgba(255, 255, 255, 0.78)" if is_win11 else "#CCCCCC",
            "text_muted": "rgba(255, 255, 255, 0.55)" if is_win11 else "#888888",
            "accent": accent,
            "accent_hover": accent_hover,
            "accent_text": accent_text,
            "accent_icon": accent_icon,
            "success": accent,
            "success_hover": accent_hover,
            "warning": accent,
            "warning_hover": accent_hover,
            "warning_text": accent_text,
            "danger": accent,
            "danger_hover": accent_hover,
            "danger_text": accent_text,
            "bg_dialog": "#202020",
        }
    return {
        "bg_window": "transparent" if is_win11 else "#F3F3F3",
        "bg_card": "rgba(255, 255, 255, 0.7)" if is_win11 else "#FFFFFF",
        "bg_card_hover": "rgba(0, 0, 0, 0.05)" if is_win11 else "#F0F0F0",
        "bg_button": "rgba(255, 255, 255, 0.7)" if is_win11 else "#E5E5E5",
        "bg_button_hover": "rgba(0, 0, 0, 0.07)" if is_win11 else "#D8D8D8",
        "bg_button_pressed": "rgba(0, 0, 0, 0.13)" if is_win11 else "#C4C4C4",
        "border_card": "rgba(0, 0, 0, 0.06)" if is_win11 else "#E0E0E0",
        "border_button": "rgba(0, 0, 0, 0.06)" if is_win11 else "#D0D0D0",

        "text_primary": "rgba(0, 0, 0, 0.9)" if is_win11 else "#1A1A1A",
        "text_secondary": "rgba(0, 0, 0, 0.6)" if is_win11 else "#555555",
        "text_muted": "rgba(0, 0, 0, 0.45)" if is_win11 else "#777777",
        "accent": accent,
        "accent_hover": accent_hover,
        "accent_text": accent_text,
        "accent_icon": accent_icon,
        "success": accent,
        "success_hover": accent_hover,
        "warning": accent,
        "warning_hover": accent_hover,
        "warning_text": accent_text,
        "danger": accent,
        "danger_hover": accent_hover,
        "danger_text": accent_text,
        "bg_dialog": "#F3F3F3",
    }

def get_asset_path(name):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / name
    return Path(__file__).parent / "assets" / name

class MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]

def apply_native_mica(hwnd_id, is_dark):
    try:
        dwmapi = ctypes.windll.dwmapi
        hwnd = wintypes.HWND(hwnd_id)
        dark_mode = ctypes.c_int(1 if is_dark else 0)
        res = dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode))
        if res != 0:
            dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode))

        if is_windows_11():
            backdrop_type = ctypes.c_int(2)  # 2 for Mica (DWMSBT_MAINWINDOW on Win 11 22H2 / 23H2 / 24H2)
            res_backdrop = dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop_type), ctypes.sizeof(backdrop_type))
            if res_backdrop != 0:
                # Fallback for Windows 11 Build 22000 (21H2)
                mica_val = ctypes.c_int(1)
                dwmapi.DwmSetWindowAttribute(hwnd, 1029, ctypes.byref(mica_val), ctypes.sizeof(mica_val))

            margins = MARGINS(-1, -1, -1, -1)
            dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
            caption_color = ctypes.c_int(0xFFFFFFFE)
            dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption_color), ctypes.sizeof(caption_color))
    except Exception:
        pass

def is_system_dark_mode():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
    except Exception:
        return True


def _solid_color(foreground, background):
    match = re.match(
        r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)",
        foreground,
    )
    if not match:
        return foreground
    red, green, blue, alpha = (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        float(match.group(4)),
    )
    base = background.lstrip("#")
    base_red, base_green, base_blue = (int(base[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02X%02X%02X" % (
        round(red * alpha + base_red * (1.0 - alpha)),
        round(green * alpha + base_green * (1.0 - alpha)),
        round(blue * alpha + base_blue * (1.0 - alpha)),
    )


def _opaque_window_bg(is_dark):
    return "#202020" if is_dark else "#F3F3F3"


def _accent_signature():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent") as key:
            palette, _ = winreg.QueryValueEx(key, "AccentPalette")
            return bytes(bytearray(palette))
    except Exception:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
            value, _ = winreg.QueryValueEx(key, "AccentColor")
            return int(value).to_bytes(4, "little", signed=False)
    except Exception:
        return b""


_github_icon_cache = {}

def get_wizard_stylesheet(is_dark: bool) -> str:
    is_win11 = is_windows_11()
    colors = get_theme_colors(is_dark, is_win11)
    win_bg = colors["bg_window"]
    font_stack = "'Segoe UI Variable Text', 'Segoe UI', sans-serif" if is_win11 else "'Segoe UI', sans-serif"
    title_font_stack = "'Segoe UI Variable Display', 'Segoe UI', sans-serif" if is_win11 else "'Segoe UI', sans-serif"

    return f"""
    QMainWindow {{ background-color: {win_bg}; }}
    QWidget#CentralWidget {{ background-color: {win_bg}; }}
    QScrollArea#WeightScrollArea {{ 
        background: transparent; 
        background-color: transparent; 
        border: none; 
    }}
    QWidget#WeightContainer {{ 
        background: transparent; 
        background-color: transparent; 
        border: none; 
    }}
    QScrollArea {{ 
        background: transparent; 
        background-color: transparent; 
        border: none; 
    }}
    QWidget {{ 
        color: {colors["text_primary"]}; 
        font-family: {font_stack}; 
        font-size: 14px; 
    }}
    QDialog, QMessageBox, QToolTip {{ 
        background-color: {colors["bg_dialog"]}; 
        border: 1px solid {colors["border_card"]}; 
        border-radius: 8px;
    }}
    #AppTitle {{ font-size: 28px; font-weight: 600; font-family: {title_font_stack}; letter-spacing: -0.5px; }}
    #AppSubtitle {{ color: {colors["text_secondary"]}; font-size: 14px; margin-top: 0px; }}
    #SectionHeader {{ font-weight: 600; font-size: 18px; padding: 0; font-family: {title_font_stack}; }}
    #SectionMeta {{ color: {colors["text_muted"]}; font-size: 13px; }}
    
    #Banner, #SetupCard, #VariantCard, #EmptyState {{ 
        background-color: {colors["bg_card"]}; 
        border: 1px solid {colors["border_card"]}; 
        border-radius: 8px; 
    }}
    #VariantCard:hover {{ 
        background-color: {colors["bg_card_hover"]}; 
    }}
    #BannerIcon {{ font-family: 'Segoe Fluent Icons'; font-size: 20px; }}
    #BannerTitle {{ font-size: 15px; font-weight: 600; }}
    #BannerText {{ font-size: 14px; color: {colors["text_secondary"]}; }}
    
    #CardTitle {{ font-weight: 600; font-size: 15px; }}
    #CardDesc {{ color: {colors["text_secondary"]}; font-size: 14px; }}
    #FontOptions {{
        background-color: {colors["bg_dialog"]};
        border: 1px solid {colors["border_card"]};
        border-radius: 8px;
    }}
    #FontOptions QCheckBox {{ color: {colors["text_primary"]}; font-size: 14px; spacing: 8px; }}
    #FontOptions #ScaleValue {{ color: {colors["text_primary"]}; font-size: 14px; font-weight: 600; }}
    #SelectedFont {{ color: {colors["text_secondary"]}; font-size: 14px; }}
    #VariantPreview {{ color: {colors["text_primary"]}; font-size: 18px; }}
    #VariantMeta {{ color: {colors["text_muted"]}; font-size: 12px; }}
    
    #CardChangeBtn {{
        background-color: transparent;
        border: none;
        border-radius: 4px;
        padding: 0 0 2px 0;
        min-width: 28px;
        max-width: 28px;
        min-height: 28px;
        max-height: 28px;
        font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
        font-size: 18px;
        font-weight: 400;
        color: {colors["accent_icon"]};
        outline: none;
    }}
    #CardChangeBtn:hover {{
        background-color: {colors["bg_button_hover"]};
        color: {colors["accent_hover"]};
    }}
    #CardChangeBtn:pressed {{
        background-color: {colors["bg_button_pressed"]};
    }}
    
    QPushButton {{ 
        background-color: {colors["bg_button"]}; 
        border: 1px solid {colors["border_button"]}; 
        border-radius: 4px; 
        padding: 0 16px; 
        min-height: 34px; 
        max-height: 34px; 
        font-weight: 600; 
        font-size: 13px;
        outline: none;
    }}
    QPushButton:focus {{ outline: none; }}
    #ActionButton {{
        background-color: {colors["bg_button"]};
        border: 1px solid {colors["border_button"]};
        border-radius: 4px;
    }}
    #ActionButton[buttonRole="primary"] {{
        background-color: {colors["accent"]};
        border: 1px solid {colors["accent"]};
    }}
    #ActionButton:hover {{
        background-color: {colors["bg_button_hover"]};
    }}
    #ActionButton[buttonRole="primary"]:hover {{
        background-color: {colors["accent_hover"]};
        border-color: {colors["accent_hover"]};
    }}
    #ActionButton[pressed="true"] {{
        background-color: {colors["bg_button_pressed"]};
    }}
    #ActionButton:disabled {{
        background-color: {colors["bg_card"]};
        border-color: {colors["border_card"]};
    }}
    #ActionButton #ActionIconLocal {{
        color: {colors["accent_icon"]};
        background: transparent;
        border: none;
        font-family: 'Segoe MDL2 Assets';
        font-size: 18px;
        font-weight: 400;
    }}
    #ActionButton #ActionText {{
        color: {colors["text_primary"]};
        background: transparent;
        border: none;
        font-family: 'Segoe UI';
        font-size: 13px;
        font-weight: 700;
    }}
    QPushButton:hover {{ background-color: {colors["bg_button_hover"]}; }}
    QPushButton:pressed {{ background-color: {colors["bg_button_pressed"]}; }}
    QPushButton:disabled {{ color: {colors["text_muted"]}; background-color: {colors["bg_card"]}; border-color: {colors["border_card"]}; }}
    
    QPushButton[buttonRole="primary"] {{ 
        background-color: {colors["accent"]}; 
        border: 1px solid {colors["accent"]}; 
        color: {colors["accent_text"]}; 
        outline: none;
    }}
    QPushButton[buttonRole="primary"]:hover {{ background-color: {colors["accent_hover"]}; border-color: {colors["accent_hover"]}; }}
    
    QPushButton[buttonRole="warning"] {{ 
        background-color: {colors["accent"]}; 
        border: 1px solid {colors["accent"]}; 
        color: {colors["accent_text"]}; 
        outline: none;
    }}
    QPushButton[buttonRole="warning"]:hover {{ 
        background-color: {colors["accent_hover"]}; 
        border-color: {colors["accent_hover"]}; 
    }}
    
    QPushButton[buttonRole="danger"] {{ 
        background-color: {colors["bg_card"]}; 
        border: 1px solid {colors["border_card"]}; 
        color: {colors["text_primary"]}; 
    }}
    QPushButton[buttonRole="danger"]:hover {{ 
        background-color: {colors["bg_button_hover"]}; 
        border-color: {colors["border_button"]}; 
    }}
    QPushButton[buttonRole="secondary"] {{ 
        background-color: {colors["bg_card"]}; 
        color: {colors["text_primary"]}; 
    }}
    QPushButton[buttonRole="secondary"]:hover {{ background-color: {colors["bg_button_hover"]}; }}
    QPushButton:disabled,
    QPushButton[buttonRole="primary"]:disabled,
    QPushButton[buttonRole="warning"]:disabled,
    QPushButton[buttonRole="danger"]:disabled,
    QPushButton[buttonRole="secondary"]:disabled {{ 
        color: {colors["text_muted"]}; 
        background-color: {colors["bg_card"]}; 
        border-color: {colors["border_card"]}; 
    }}
    #HeaderIconButton {{
        background-color: transparent;
        border: none;
        padding: 0;
        min-width: 32px;
        max-width: 32px;
        min-height: 32px;
        max-height: 32px;
        border-radius: 4px;
    }}
    #HeaderIconButton:hover {{
        background-color: {colors["bg_button_hover"]};
    }}
    #HeaderIconButton:pressed {{
        background-color: {colors["bg_button_pressed"]};
    }}
    
    QScrollBar:vertical {{ border: none; background: transparent; width: 12px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {colors["border_card"]}; border-radius: 3px; min-height: 30px; margin: 0 3px; }}
    QScrollBar::handle:vertical:hover {{ background: {colors["text_secondary"]}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ border: none; background: none; height: 0px; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    """

class OperationThread(QThread):
    progress = Signal(int, str)
    done = Signal(object)
    def __init__(self, job, parent=None):
        super().__init__(parent)
        self._job = job
    def run(self):
        try:
            result = self._job(progress=self.progress.emit)
        except Exception as exc:
            result = OperationResult(False, "The operation failed before it could finish.", [str(exc)])
        self.done.emit(result)

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def addItem(self, item):
        self.itemList.append(item)
        self.invalidate()

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if index >= 0 and index < len(self.itemList):
            item = self.itemList.pop(index)
            self.invalidate()
            return item
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _column_count(self, width):
        if not self.itemList:
            return 1
        spacing = max(0, self.spacing())
        min_width = max(item.minimumSize().width() for item in self.itemList)
        return max(1, (width + spacing) // (min_width + spacing))

    def doLayout(self, rect, testOnly):
        spacing = max(0, self.spacing())
        margins = self.contentsMargins()
        content_rect = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        columns = self._column_count(content_rect.width())
        item_width = max(0, (content_rect.width() - spacing * (columns - 1)) // columns)
        row_height = max((item.sizeHint().height() for item in self.itemList), default=0)

        for index, item in enumerate(self.itemList):
            row = index // columns
            column = index % columns
            x = content_rect.x() + column * (item_width + spacing)
            y = content_rect.y() + row * (row_height + spacing)

            if not testOnly:
                item.setGeometry(QRect(x, y, item_width, row_height))

        rows = (len(self.itemList) + columns - 1) // columns
        content_height = rows * row_height + max(0, rows - 1) * spacing
        return margins.top() + content_height + margins.bottom()


class BoldIconLabel(QLabel):
    BANNER_ICON_PX = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ink = QColor("#FFFFFF")
        self._icon_font = QFont("Segoe Fluent Icons")
        self._icon_font.setPixelSize(self.BANNER_ICON_PX)
        self.setAlignment(Qt.AlignCenter)

    def set_ink(self, color):
        self._ink = QColor(color)
        self.update()

    def sizeHint(self):
        metrics = QFontMetrics(self._icon_font)
        text = self.text() or " "
        width = metrics.horizontalAdvance(text)
        height = metrics.ascent() + metrics.descent()
        return QSize(int(width) + 8, height + 8)

    def paintEvent(self, event):
        # Plain glyph rendering (no outline stroke), matching the weight of
        # the other chrome icons in the app.
        text = self.text()
        if not text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self._icon_font)
        painter.setPen(self._ink)
        painter.drawText(self.rect(), Qt.AlignCenter, text)
        painter.end()


class StatusBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Banner")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(16)
        
        self.icon_lbl = BoldIconLabel()
        self.icon_lbl.setObjectName("BannerIcon")
        self.icon_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.icon_lbl, 0, Qt.AlignVCenter)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        self.title = QLabel("")
        self.title.setObjectName("BannerTitle")
        self.title.setWordWrap(True)
        self.title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.text = QLabel("")
        self.text.setObjectName("BannerText")
        self.text.setWordWrap(True)
        self.text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.text.hide()
        text_layout.addWidget(self.title)
        text_layout.addWidget(self.text)
        layout.addLayout(text_layout, 1)

    def set_content(self, title, message):
        self.title.setText(title)
        self.text.setText(message)
        self.text.hide()

    def set_icon(self, icon_char, color):
        self.icon_lbl.setText(icon_char)
        self.icon_lbl.set_ink(QColor(color))

class WeightCard(QFrame):
    def __init__(self, weight, font_path, is_manual=False, is_dark=False, on_change=None, on_reset=None, parent=None):
        super().__init__(parent)
        self.setObjectName("VariantCard")
        self.setMinimumSize(280, 140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._font_id = -1
        self.weight = weight
        self.on_change = on_change
        self.on_reset = on_reset
        colors = get_theme_colors(is_dark, is_windows_11())
        
        try:
            metadata = inspect_font(font_path)
            detected_weight = metadata.weight_class
            detected_italic = metadata.is_italic
        except Exception:
            detected_weight, detected_italic = WEIGHT_TARGETS.get(weight, (400, False))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        
        header_row = QWidget()
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        if weight == "variable":
            is_var_file = getattr(metadata, "is_variable", False)
            title_str = "可变界面字体"
        elif weight.startswith("consolas_"):
            title_str = "等宽 · " + weight.replace("consolas_", "").replace("_", " ").title()
        elif weight.startswith("yahei_"):
            title_str = {"yahei_regular": "中文 · 常规", "yahei_bold": "中文 · 粗体", "yahei_light": "中文 · 细体"}[weight]
        elif weight == "jhenghei_regular":
            title_str = "微软正黑体 · 常规"
        else:
            title_str = weight.replace("_", " ").title()

        title = QLabel(title_str)
        title.setObjectName("CardTitle")
        title.setStyleSheet(f"color: {colors['text_primary']}; font-weight: 600; font-size: 14px;")
        header_layout.addWidget(title, 0, Qt.AlignVCenter)

        header_layout.addStretch(1)

        action_btn = QPushButton("\uE7A7" if is_manual else "\uE7C3")
        action_btn.setObjectName("CardChangeBtn")
        action_btn.setProperty("isCustom", "true" if is_manual else "false")
        action_btn.setCursor(Qt.PointingHandCursor)
        action_btn.setFocusPolicy(Qt.NoFocus)
        if is_manual:
            if on_reset:
                action_btn.clicked.connect(lambda: on_reset(self.weight))
        else:
            if on_change:
                action_btn.clicked.connect(lambda: on_change(self.weight))
        header_layout.addWidget(action_btn, 0, Qt.AlignVCenter)

        layout.addWidget(header_row)
        
        is_mono = weight.startswith("consolas_")
        sample_text = "The quick brown fox jumps over the lazy dog"
        if weight in CJK_WEIGHTS:
            sample_text = "文件资源管理器 · 最近使用：你好，世界！123"
        self.preview = QLabel(sample_text)
        self.preview.setObjectName("VariantPreview")
        self.preview.setWordWrap(True)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self._font_id = QFontDatabase.addApplicationFont(str(font_path))
        font_family_name = ""
        if self._font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(self._font_id)
            if families:
                font_family_name = families[0]

        style_str = "italic" if detected_italic else "normal"
        font_family_rule = f"font-family: '{font_family_name}', monospace;" if is_mono and font_family_name else (f"font-family: '{font_family_name}', sans-serif;" if font_family_name else "")
        self._preview_style = (
            f"color: {colors['text_primary']}; "
            f"{font_family_rule} "
            f"font-weight: {detected_weight}; "
            f"font-style: {style_str};"
        )
        self.set_preview_scale(100)
        layout.addWidget(self.preview)

        filename_str = Path(font_path).name
        if weight == "variable":
            if is_var_file:
                meta_text = f"Variable Font • {filename_str}"
            else:
                meta_text = f"Static Fallback • Weight {detected_weight} • {filename_str}"
        else:
            meta_text = f"Weight {detected_weight}" + (" • Italic" if detected_italic else "") + f" • {filename_str}"
        meta = QLabel(meta_text)
        meta.setObjectName("VariantMeta")
        meta.setStyleSheet(f"color: {colors['text_muted']}; font-size: 11px;")
        meta.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(meta)

    def set_preview_scale(self, percent):
        self.preview.setStyleSheet(f"{self._preview_style} font-size: {12 * percent / 100:g}pt;")

    def cleanup(self):
        if hasattr(self, "preview") and self.preview:
            self.preview.setStyleSheet("")
        if self._font_id >= 0:
            QFontDatabase.removeApplicationFont(self._font_id)
            self._font_id = -1


class LocalFontsGuide(QWidget):
    """Informational guide displayed in the empty space when no font is selected."""

    POINTS = (
        "将同一家族的 .ttf 放在同一文件夹，选择常规字重后会自动匹配其他样式。",
        "开启系统中文字体替换后，优先从同目录中选用覆盖常用汉字的字体。",
        "可在预览卡片中为每种字重手动更换字体。",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LocalFontsGuideContainer")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        outer_lay = QVBoxLayout(self)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.addStretch(1)

        h_center = QHBoxLayout()
        h_center.setContentsMargins(0, 0, 0, 0)
        h_center.addStretch(1)

        self._inner = QWidget()
        inner_lay = QVBoxLayout(self._inner)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.setSpacing(14)

        self._title_lbl = QLabel("使用本地字体")
        self._title_lbl.setAlignment(Qt.AlignCenter)
        self._title_lbl.setStyleSheet("font-size: 15px; font-weight: 600; font-family: 'Segoe UI';")
        inner_lay.addWidget(self._title_lbl)

        points_lay = QVBoxLayout()
        points_lay.setSpacing(10)

        self._labels = []

        for html_text in self.POINTS:
            lbl = QLabel()
            lbl.setTextFormat(Qt.RichText)
            lbl.setText(html_text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(False)
            points_lay.addWidget(lbl, 0, Qt.AlignCenter)
            self._labels.append(lbl)

        inner_lay.addLayout(points_lay)
        h_center.addWidget(self._inner)
        h_center.addStretch(1)

        outer_lay.addLayout(h_center)
        outer_lay.addStretch(1)

    def refresh_theme(self, is_dark: bool):
        colors = get_theme_colors(is_dark, is_windows_11())
        self._title_lbl.setStyleSheet(
            f"color: {colors['text_muted']}; font-size: 14px; font-weight: 600; font-family: 'Segoe UI';"
        )
        for lbl in self._labels:
            lbl.setStyleSheet(f"color: {colors['text_muted']}; font-size: 13px; font-family: 'Segoe UI';")


class IconActionButton(QFrame):
    """Standalone action button with an MDL2 glyph icon and a text label.

    Styling matches the old split-button halves exactly: per-icon glyph
    size at regular weight with accent ink, plus a bold Segoe UI caption.
    Unlike the old split control, the whole button is clickable.
    """

    clicked = Signal()

    _LEFT_PAD = 12
    _ICON_GAP = 8
    _RIGHT_PAD = 16

    def __init__(self, icon_char, icon_px, icon_object_name, text, parent=None):
        super().__init__(parent)
        self.setObjectName("ActionButton")
        # 36px total so the frame lines up exactly with real QPushButtons
        # (34px QSS content height + 1px border on each side).
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)
        self.setAccessibleName(text)
        self._enabled = True
        self._hover = False
        self._pressed = False
        self.setProperty("pressed", False)
        self._icon_px = icon_px
        self._icon_label = QLabel(icon_char, self)
        self._icon_label.setObjectName(icon_object_name)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._text_label = QLabel(text, self)
        self._text_label.setObjectName("ActionText")
        self._text_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._text_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._icon_label.raise_()
        self._text_label.raise_()
        self._sync_width()
        self.refresh_action_style()

    def text(self):
        try:
            return self._text_label.text()
        except RuntimeError:
            return ""

    def _sync_width(self):
        # Frame width follows the caption: pad + icon + gap + text + pad.
        try:
            metrics = QFontMetrics(self._text_label.font())
            text_w = int(metrics.horizontalAdvance(self.text()))
        except RuntimeError:
            text_w = 90
        icon_w = self._icon_px + 12
        total = self._LEFT_PAD + icon_w + self._ICON_GAP + text_w + self._RIGHT_PAD
        try:
            self.setFixedWidth(max(110, int(total)))
        except RuntimeError:
            pass
        self._layout_content()

    def _layout_content(self):
        try:
            width, height = self.width(), self.height()
        except RuntimeError:
            return
        icon_w = self._icon_px + 12
        try:
            self._icon_label.setGeometry(self._LEFT_PAD, 1, icon_w, max(1, height - 2))
            tx = self._LEFT_PAD + icon_w + self._ICON_GAP
            self._text_label.setGeometry(
                tx, 1, max(1, width - tx - self._RIGHT_PAD + 4), max(1, height - 2))
        except RuntimeError:
            pass

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self._enabled = bool(enabled)
        if not enabled:
            self._hover = False
            self._pressed = False
        self._paint_pressed(False)
        self.refresh_action_style()

    def hideEvent(self, event):
        self._hover = False
        self._pressed = False
        self._paint_pressed(False)
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_content()

    def showEvent(self, event):
        super().showEvent(event)
        # QSS font resolves on polish: re-measure once it is real.
        self._sync_width()

    def refresh_action_style(self):
        """Caption/icon ink follows state/role (set in code, not QSS).

        Qt mis-applies ancestor pseudo-state selectors (e.g. a disabled
        parent greying labels out like disabled controls), so the ink is
        set here instead of in QSS.
        """
        window = self.window()
        is_dark = getattr(window, "is_dark", None)
        if is_dark is None:
            is_dark = is_system_dark_mode()
        colors = get_theme_colors(is_dark)
        role = self.property("buttonRole") or "secondary"
        if not self._enabled:
            icon_ink = colors["text_muted"]
            text_ink = colors["text_muted"]
        elif role in ("primary", "warning"):
            icon_ink = colors["accent_text"]
            text_ink = colors["accent_text"]
        else:
            icon_ink = colors["accent_icon"]
            text_ink = colors["text_primary"]
        try:
            self._icon_label.setStyleSheet(f"color: {icon_ink};")
            self._text_label.setStyleSheet(f"color: {text_ink};")
        except RuntimeError:
            pass

    def _paint_pressed(self, pressed):
        # QFrame gets no :pressed pseudo-state, so the press fill is
        # driven by a dynamic property + QSS. Never an inline
        # stylesheet: an inline background on the frame cascades onto
        # the transparent icon/caption labels and double-darkens them
        # in patches (grey boxes behind icon and text on click).
        if not self._enabled:
            pressed = False
        try:
            if bool(self.property("pressed")) != bool(pressed):
                self.setProperty("pressed", bool(pressed))
                self.style().unpolish(self)
                self.style().polish(self)
                self.update()
        except RuntimeError:
            pass

    def mouseMoveEvent(self, event):
        if self._enabled:
            try:
                inside = self.rect().contains(
                    int(event.position().x()), int(event.position().y()))
            except (AttributeError, RuntimeError):
                inside = True
            self._hover = bool(inside)
            self.setCursor(Qt.PointingHandCursor if inside else Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._pressed = False
        self.setCursor(Qt.ArrowCursor)
        self._paint_pressed(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._enabled:
            self._pressed = True
            self._paint_pressed(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            pressed = self._pressed
            self._pressed = False
            self._paint_pressed(False)
            if pressed and self._enabled and self.rect().contains(int(event.position().x()), int(event.position().y())):
                event.accept()
                self.clicked.emit()
                return
            event.accept()
            return
        super().mouseReleaseEvent(event)


def _star_outline_3d():
    points = []
    for i in range(10):
        radius = 1.0 if i % 2 == 0 else 0.44
        angle = math.radians(-90.0 + i * 36.0)
        points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return points


def _render_star_satin(px=96, palette=None):
    """Option 1 Clean Satin Star in accent theme color.
    Smooth vertical gradient, zero white glare in middle, no dark outline stroke.
    """
    image = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    center = px / 2.0
    scale = px * 0.42
    outline = _star_outline_3d()
    pts = [QPointF(center + x * scale, center - y * scale) for x, y in outline]
    poly = QPolygonF(pts)

    grad = QLinearGradient(center, center - scale, center, center + scale)
    hi = (palette.get("hi") if isinstance(palette, dict) else None) or "#60CDFF"
    mid = (palette.get("mid") if isinstance(palette, dict) else None) or "#0078D4"
    grad.setColorAt(0.0, QColor(hi))
    grad.setColorAt(1.0, QColor(mid))

    painter.setPen(Qt.NoPen)
    painter.setBrush(grad)
    painter.drawPolygon(poly)
    painter.end()
    return QPixmap.fromImage(image)


def _render_star_flat(angle_deg=0.0, px=96):
    return _render_star3d(angle_deg, px=px)


def _render_star3d(angle_deg, px=96, palette=None):
    if palette is None:
        colors = get_theme_colors(True)
        base = QColor(colors.get("accent", "#0078D4"))
        hi = QColor(colors.get("accent_icon", colors.get("accent", "#60CDFF")))
        if hi == base:
            hi = base.lighter(135)
        pal = {
            "hi": hi,
            "mid": base,
            "deep": base.darker(135),
            "edge": base.darker(165),
            "side": base.lighter(110),
        }
    else:
        pal = {
            "hi": QColor(palette["hi"]),
            "mid": QColor(palette["mid"]),
            "deep": QColor(palette["deep"]),
            "edge": QColor(palette["edge"]),
            "side": QColor(palette["side"]),
        }
    theta = math.radians(angle_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    half = 0.20
    light_len = math.sqrt(0.45 * 0.45 + 0.55 * 0.55 + 0.75 * 0.75)
    light = (-0.45 / light_len, 0.55 / light_len, 0.75 / light_len)

    def rotate_point(point):
        x, y, z = point
        return (x * cos_t + z * sin_t, y, -x * sin_t + z * cos_t)

    def face_facing(normal):
        nx, ny, nz = normal
        rx = nx * cos_t + nz * sin_t
        ry = ny
        rz = -nx * sin_t + nz * cos_t
        return rx * light[0] + ry * light[1] + rz * light[2]

    outline = _star_outline_3d()
    count = len(outline)
    faces = [
        {"pts": [(x, y, half) for x, y in outline], "normal": (0.0, 0.0, 1.0), "kind": "front"},
        {"pts": [(x, y, -half) for x, y in outline], "normal": (0.0, 0.0, -1.0), "kind": "back"},
    ]
    for i in range(count):
        x0, y0 = outline[i]
        x1, y1 = outline[(i + 1) % count]
        dx = x1 - x0
        dy = y1 - y0
        length = math.hypot(dx, dy) or 1.0
        faces.append({
            "pts": [(x0, y0, half), (x1, y1, half), (x1, y1, -half), (x0, y0, -half)],
            "normal": (dy / length, -dx / length, 0.0),
            "kind": "side",
        })

    scale = px * 0.40
    center = px / 2.0

    def to_screen(point):
        rx, ry, rz = rotate_point(point)
        return (center + rx * scale, center - ry * scale, rz)

    layers = {"front": None, "back": None, "sides": []}
    for face in faces:
        shown = [to_screen(p) for p in face["pts"]]
        depth = sum(p[2] for p in shown) / len(shown)
        entry = (depth, face, shown)
        if face["kind"] == "front":
            layers["front"] = entry
        elif face["kind"] == "back":
            layers["back"] = entry
        else:
            layers["sides"].append(entry)
    layers["sides"].sort(key=lambda item: item[0])
    if cos_t >= 0.0:
        ordered = [layers["back"], *layers["sides"], layers["front"]]
    else:
        ordered = [layers["front"], *layers["sides"], layers["back"]]

    def shaded(color, facing_value):
        c = QColor(color)
        brightness = 0.65 + 0.35 * max(0.0, facing_value)
        return QColor(
            max(0, min(255, int(c.red() * brightness))),
            max(0, min(255, int(c.green() * brightness))),
            max(0, min(255, int(c.blue() * brightness))),
        )

    image = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(pal["edge"])
    pen.setWidthF(max(1.0, px * 0.022))
    pen.setJoinStyle(Qt.RoundJoin)
    front_facing_camera = cos_t >= 0.0
    for _, face, shown in ordered:
        poly = QPolygonF([QPointF(sx, sy) for sx, sy, _ in shown])
        facing_value = face_facing(face["normal"])
        kind = face["kind"]
        is_camera_facing_star = (kind == "front" and front_facing_camera) or (kind == "back" and not front_facing_camera)
        if is_camera_facing_star:
            puff = QRadialGradient(center, center - scale * 0.30, scale * 1.15)
            puff.setColorAt(0.0, pal["hi"])
            puff.setColorAt(0.55, pal["mid"])
            puff.setColorAt(1.0, pal["deep"])
            painter.setBrush(puff)
            painter.setPen(pen)
            painter.drawPolygon(poly)
            painter.save()
            clip = QPainterPath()
            clip.addPolygon(poly)
            painter.setClipPath(clip)
            painter.setPen(Qt.NoPen)
            shade_grad = QLinearGradient(0, center - scale * 0.1, 0, center + scale)
            shade_grad.setColorAt(0.0, QColor(pal["deep"].red(), pal["deep"].green(), pal["deep"].blue(), 0))
            shade_grad.setColorAt(1.0, QColor(pal["deep"].red(), pal["deep"].green(), pal["deep"].blue(), 85))
            painter.setBrush(shade_grad)
            painter.drawRect(int(center - scale), int(center - scale), int(scale * 2), int(scale * 2))
            spec = QRadialGradient(center - scale * 0.22, center - scale * 0.32, scale * 0.65)
            spec.setColorAt(0.0, QColor(255, 255, 255, 120))
            spec.setColorAt(0.45, QColor(255, 255, 255, 35))
            spec.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(spec)
            painter.drawRect(int(center - scale), int(center - scale), int(scale * 2), int(scale * 2))
            painter.restore()
        else:
            base = pal["mid"] if kind in ("front", "back") else pal["side"]
            painter.setPen(pen if kind in ("front", "back") else Qt.NoPen)
            painter.setBrush(shaded(base, facing_value))
            painter.drawPolygon(poly)
    painter.end()
    return QPixmap.fromImage(image)


class FontWizardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self._action_buttons = ()
        self.controller = FontWizardController()
        self.setWindowTitle(APP_NAME)
        icon_path = get_asset_path("fontscape.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Fontscape.Windows")

        self.setMinimumSize(980, 600)
        self.resize(1050, 650)
        self._selection_dirty = False
        self._hide_applied_variants = True
        self._apply_action = "apply"
        self._browse_action = "select"
        self._op_thread = None
        self._armed_button = None
        self._armed_action = None
        self._armed_face = None
        self._arm_labels = None
        self._op_cover = None
        self._op_cover_btn = None
        self._armed_at = 0.0
        self._star_active = False
        self._cards_sig = None
        self._last_theme_sig = None
        self._variant_geom_key = None
        self._compact_layout = None
        self.is_dark = is_system_dark_mode()
        if is_windows_11():
            self.setAttribute(Qt.WA_TranslucentBackground)

        central = QWidget(objectName="CentralWidget")
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(40, 36, 40, 36)
        self.main_layout.setSpacing(24)

        self._build_header()
        self._build_font_setup()
        self._build_chinese_option()
        self._build_variants()
        self.main_layout.addStretch(1)
        self._action_buttons = (self.local_btn, self.apply_btn, self.restore_btn)

        self.local_btn.clicked.connect(self._on_local_pick)
        self.apply_btn.clicked.connect(self.on_apply_action)
        self.restore_btn.clicked.connect(self.on_restore)

        self._sync_responsive_layout()
        self._apply_theme(self.is_dark)

    def _build_header(self):
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)

        title_container = QWidget()
        tc_layout = QHBoxLayout(title_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(14)
        tc_layout.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        logo_lbl = QLabel()
        logo_size = 64
        logo_lbl.setFixedSize(QSize(logo_size, logo_size))
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_path = get_asset_path("fontscape.png")
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            dpr = self.devicePixelRatioF()
            target_w = int(logo_size * dpr)
            target_h = int(logo_size * dpr)
            scaled_pixmap = pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled_pixmap.setDevicePixelRatio(dpr)
            logo_lbl.setPixmap(scaled_pixmap)
        tc_layout.addWidget(logo_lbl, 0, Qt.AlignVCenter)

        text_container = QWidget()
        text_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        text_layout.setSizeConstraint(QLayout.SetFixedSize)

        title_row = QWidget()
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.setSpacing(8)

        title = QLabel(APP_NAME)
        title.setObjectName("AppTitle")
        title.setFixedHeight(34)
        title.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        title.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        title_row_layout.addWidget(title, 0, Qt.AlignBottom)

        self.github_btn = QPushButton()
        self.github_btn.setObjectName("HeaderIconButton")
        self.github_btn.setFlat(True)
        self.github_btn.setIconSize(QSize(20, 20))
        self.github_btn.setCursor(Qt.PointingHandCursor)
        self.github_btn.setAccessibleName("GitHub")
        self.github_btn.clicked.connect(self._on_github_clicked)
        self._star_timer = QTimer(self)
        self._star_timer.setSingleShot(True)
        self._star_timer.timeout.connect(self._restore_github_logo)
        self._update_github_icon()
        title_row_layout.addWidget(self.github_btn, 0, Qt.AlignBottom)
        text_layout.addWidget(title_row, 0, Qt.AlignLeft)

        subtitle = QLabel("自定义 Windows 系统字体")
        subtitle.setObjectName("AppSubtitle")
        subtitle.setFixedHeight(20)
        subtitle.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        subtitle.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        text_layout.addWidget(subtitle, 0, Qt.AlignLeft)

        tc_layout.addWidget(text_container, 0, Qt.AlignVCenter)
        header_layout.addWidget(title_container)
        self.banner = StatusBanner()
        header_layout.addWidget(self.banner)
        self.main_layout.addWidget(header)

    def _build_font_setup(self):
        self.setup_card = QFrame(objectName="SetupCard")
        self.setup_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setup_layout = QHBoxLayout(self.setup_card)
        self.setup_layout.setContentsMargins(20, 14, 20, 14)
        self.setup_layout.setSpacing(16)

        self.font_summary = QWidget()
        summary_layout = QVBoxLayout(self.font_summary)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(2)

        title = QLabel("界面字体")
        title.setObjectName("CardTitle")
        summary_layout.addWidget(title)

        self.cur_font_lbl = QLabel("尚未选择字体")
        self.cur_font_lbl.setObjectName("SelectedFont")
        self.cur_font_lbl.setWordWrap(True)
        summary_layout.addWidget(self.cur_font_lbl)

        self.setup_layout.addWidget(self.font_summary, 1, Qt.AlignVCenter)

        self.actions_widget = QWidget()
        self.actions_layout = QHBoxLayout(self.actions_widget)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(10)

        self.local_btn = IconActionButton(chr(0xE8E5), 18, "ActionIconLocal", "本地字体")
        self.apply_btn = QPushButton("应用字体")
        self.restore_btn = QPushButton("恢复原始字体")

        self.local_btn.setToolTip("选择本地字体")
        for button in (self.apply_btn, self.restore_btn):
            button.setFixedHeight(34)
            button.setMinimumWidth(150)
        for button in (self.local_btn, self.apply_btn, self.restore_btn):
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.NoFocus)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button.installEventFilter(self)
            self.actions_layout.addWidget(button, 0, Qt.AlignVCenter)

        self.setup_layout.addWidget(self.actions_widget, 0, Qt.AlignVCenter)
        self.main_layout.addWidget(self.setup_card)


    def _build_variants(self):
        self.variants_header = QWidget()
        v_layout = QHBoxLayout(self.variants_header)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(12)

        text_lbl = QLabel("字重与样式", objectName="SectionHeader")
        self.variant_count_lbl = QLabel("")
        self.variant_count_lbl.setObjectName("SectionMeta")
        v_layout.addWidget(text_lbl)
        v_layout.addWidget(self.variant_count_lbl)
        v_layout.addStretch()
        self.main_layout.addWidget(self.variants_header)

        self.empty_variants = QFrame(objectName="EmptyState")
        self.empty_variants.setMinimumHeight(140)
        self.empty_variants.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        empty_layout = QVBoxLayout(self.empty_variants)
        empty_layout.setContentsMargins(24, 24, 24, 24)
        empty_layout.setSpacing(8)
        empty_title = QLabel("暂无样式")
        empty_title.setObjectName("CardTitle")
        empty_desc = QLabel("选择字体后可预览各字重和样式。")
        empty_desc.setObjectName("CardDesc")
        empty_desc.setWordWrap(True)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_desc)
        empty_layout.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.empty_variants, 1000)

        self.weight_scroll = QScrollArea(objectName="WeightScrollArea")
        # Keep the viewport transparent.
        self.weight_scroll.setAutoFillBackground(False)
        self.weight_scroll.setWidgetResizable(True)
        self.weight_scroll.setFrameShape(QFrame.NoFrame)
        self.weight_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.weight_scroll.viewport().setAutoFillBackground(False)
        self.weight_scroll.hide()

        self.weight_widget = QWidget(objectName="WeightContainer")
        self.weight_widget.setAutoFillBackground(False)
        self.weight_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.weight_layout = FlowLayout(self.weight_widget, margin=0, spacing=16)
        self.weight_layout.setContentsMargins(0, 0, 0, 0)

        self.weight_scroll.setWidget(self.weight_widget)
        # setWidget() re-enables auto-fill on the widget.
        self.weight_widget.setAutoFillBackground(False)
        self.weight_scroll.viewport().installEventFilter(self)
        self.main_layout.addWidget(self.weight_scroll, 1000)

        self.local_fonts_guide = LocalFontsGuide()
        self.main_layout.addWidget(self.local_fonts_guide, 1000)

    def _build_chinese_option(self):
        row = QFrame(objectName="FontOptions")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        self.chinese_option = QCheckBox("替换微软雅黑")
        self.chinese_option.setChecked(self.controller.workflow.include_chinese)
        self.chinese_option.setToolTip(
            "替换系统微软雅黑和微软雅黑 UI 的常规、粗体、细体，需重启 Windows。\n"
            "使用系统微软雅黑的界面会受到影响。\n"
            "取消勾选仅停止后续替换，已应用的中文字体需通过 「恢复原始字体」恢复。"
        )
        note = QLabel("需要包含中文的静态 TTF，重启后生效。")
        note.setObjectName("CardDesc")
        note.setWordWrap(True)
        note.setContentsMargins(26, 0, 0, 0)
        layout.addWidget(self.chinese_option)
        layout.addWidget(note)
        self.jhenghei_option = QCheckBox("替换微软正黑体（微信输入框试验）")
        self.jhenghei_option.setChecked(self.controller.workflow.include_jhenghei)
        self.jhenghei_option.setToolTip(
            "替换微软正黑体及微软正黑体 UI 的常规字重，重启后生效。\n"
            "也会影响使用该系统字体的其他应用。微信中的效果取决于版本和实际字体选择。\n"
            "恢复请使用「恢复原始字体」。"
        )
        layout.addWidget(self.jhenghei_option)
        self.explorer_option = QCheckBox("同时应用到资源管理器和桌面")
        self.explorer_option.setChecked(self.controller.workflow.include_explorer)
        self.explorer_option.setToolTip(
            "让文件列表、桌面图标及系统菜单字体跟随所选界面字体，保留字号与字重。\n"
            "会影响其他使用系统菜单/消息字体的软件；完整效果需重启 Windows。\n"
            "原设置自动备份；恢复请使用「恢复原始字体」，取消勾选不会自动恢复。"
        )
        layout.addWidget(self.explorer_option)
        size_row = QHBoxLayout()
        size_label = QLabel("替换字号")
        size_label.setObjectName("CardDesc")
        self.font_scale = QSlider(Qt.Horizontal)
        self.font_scale.setRange(MIN_FONT_SCALE, MAX_FONT_SCALE)
        self.font_scale.setValue(self.controller.workflow.font_scale)
        self.font_scale.setAccessibleName("替换字号百分比")
        self.font_scale.setMaximumWidth(180)
        self.font_scale.setToolTip("拖动或使用方向键调整。下方样例实时更新。")
        self.font_scale_value = QLabel(f"{self.font_scale.value()}%", objectName="ScaleValue")
        self.font_scale_value.setMinimumWidth(54)
        self.font_scale_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        size_row.addWidget(size_label)
        size_row.addWidget(self.font_scale)
        size_row.addWidget(self.font_scale_value)
        size_row.addStretch()
        layout.addLayout(size_row)
        self.font_scale.valueChanged.connect(self._on_font_scale)
        self.explorer_option.toggled.connect(self._on_explorer_option)
        self.main_layout.addWidget(row)
        self.chinese_option.toggled.connect(self._on_chinese_option)
        self.jhenghei_option.toggled.connect(self._on_jhenghei_option)

    def _on_chinese_option(self, enabled):
        try:
            self.controller.set_include_chinese(enabled)
        except Exception as exc:
            self.chinese_option.blockSignals(True)
            self.chinese_option.setChecked(not enabled)
            self.chinese_option.blockSignals(False)
            self.controller.workflow.include_chinese = not enabled
            QMessageBox.warning(self, "中文字体", str(exc))
            return
        self._selection_dirty = True
        self.refresh_all()

    def _on_explorer_option(self, enabled):
        self.controller.workflow.include_explorer = bool(enabled)
        self._selection_dirty = True
        self.refresh_all()

    def _on_jhenghei_option(self, enabled):
        try:
            self.controller.set_include_jhenghei(enabled)
        except Exception as exc:
            self.jhenghei_option.blockSignals(True)
            self.jhenghei_option.setChecked(not enabled)
            self.jhenghei_option.blockSignals(False)
            self.controller.workflow.include_jhenghei = not enabled
            QMessageBox.warning(self, "微软正黑体", str(exc))
            return
        self._selection_dirty = True
        self.refresh_all()

    def _on_font_scale(self, percent):
        self.controller.workflow.font_scale = percent
        self.font_scale_value.setText(f"{percent}%")
        self._selection_dirty = True
        self._disarm()
        for index in range(self.weight_layout.count()):
            self.weight_layout.itemAt(index).widget().set_preview_scale(percent)

    def _set_button_role(self, button, role):
        if button.property("buttonRole") == role:
            return
        button.setProperty("buttonRole", role)
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()
        refresh = getattr(button, "refresh_action_style", None)
        if refresh:
            refresh()

    def _apply_widget_theme(self):
        for button in self._action_buttons:
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()
            refresh = getattr(button, "refresh_action_style", None)
            if refresh:
                refresh()
        if hasattr(self, "local_fonts_guide"):
            self.local_fonts_guide.refresh_theme(self.is_dark)

    def _update_github_icon(self):
        if not hasattr(self, "github_btn"):
            return
        if getattr(self, "_star_active", False):
            return
        if self.is_dark not in _github_icon_cache:
            fill_color = "#FFFFFF" if self.is_dark else "#1F2328"
            svg_path = get_asset_path("github-mark.svg")
            pixmap = QPixmap()
            try:
                if svg_path.exists():
                    svg_content = svg_path.read_text(encoding="utf-8").replace("#ffffff", fill_color).replace("#FFFFFF", fill_color)
                    if not pixmap.loadFromData(svg_content.encode("utf-8"), "SVG"):
                        pixmap = QPixmap()
            except Exception:
                pixmap = QPixmap()
            _github_icon_cache[self.is_dark] = pixmap
        pixmap = _github_icon_cache.get(self.is_dark)
        if pixmap and not pixmap.isNull():
            try:
                self.github_btn.setIcon(QIcon(pixmap))
                return
            except Exception:
                pass
        try:
            self.github_btn.setIcon(QIcon(str(get_asset_path("github-mark.svg"))))
        except Exception:
            pass

    _STAR_REST_PX = 28
    _STAR_SHOW_MS = 13000
    _STAR_SPIN_DELAY_MS = 350

    def _star_palette(self):
        """Accent-derived palette for the 3D coin-flip star (theme-dynamic)."""
        colors = get_theme_colors(self.is_dark)
        base = QColor(colors["accent"])
        hi = QColor(colors.get("accent_icon", colors["accent"]))
        if hi == base:
            hi = base.lighter(135)
        return {
            "hi": hi,
            "mid": base,
            "deep": base.darker(135),
            "edge": base.darker(165),
            "side": base.lighter(110),
        }

    def _on_github_clicked(self):
        QDesktopServices.openUrl(QUrl(APP_GITHUB_URL))
        if getattr(self, "_star_active", False):
            self._restore_github_logo()

    def _stop_star_anim(self):
        try:
            self._star_timer.stop()
        except (RuntimeError, AttributeError):
            pass
        spin = getattr(self, "_star_spin_anim", None)
        if spin is not None:
            try:
                spin.stop()
            except RuntimeError:
                pass
            self._star_spin_anim = None
        button = getattr(self, "github_btn", None)
        if button is not None:
            try:
                button.setGraphicsEffect(None)
            except RuntimeError:
                pass

    def _morph_to_star(self):
        if getattr(self, "_star_active", False):
            self._star_timer.start(self._STAR_SHOW_MS)
            return
        self._star_active = True
        self._star_timer.start(self._STAR_SHOW_MS)
        button = self.github_btn
        button.setAccessibleName("在 GitHub 查看 Fontscape")
        effect = QGraphicsOpacityEffect(button)
        button.setGraphicsEffect(effect)
        fade_out = QPropertyAnimation(effect, b"opacity", self)
        fade_out.setDuration(120)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)

        def _swap_to_star():
            if not self._star_active:
                return
            button.setIcon(QIcon(_render_star3d(0.0, palette=self._star_palette())))
            self._star_angle = 0.0
            button.setIconSize(QSize(12, 12))
            button.setText("")
            fade_in = QPropertyAnimation(effect, b"opacity", self)
            fade_in.setDuration(160)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.finished.connect(lambda: button.setGraphicsEffect(None))
            fade_in.start(QAbstractAnimation.DeleteWhenStopped)
            pop = QPropertyAnimation(button, b"iconSize", self)
            pop.setDuration(280)
            pop.setStartValue(QSize(12, 12))
            pop.setEndValue(QSize(self._STAR_REST_PX, self._STAR_REST_PX))
            pop.setEasingCurve(QEasingCurve.OutBack)
            pop.start(QAbstractAnimation.DeleteWhenStopped)
            QTimer.singleShot(self._STAR_SPIN_DELAY_MS, self._start_star_spin)

        fade_out.finished.connect(_swap_to_star)
        fade_out.start(QAbstractAnimation.DeleteWhenStopped)

    def _start_star_spin(self):
        if not getattr(self, "_star_active", False):
            return
        spin = QVariantAnimation(self)
        spin.setDuration(1200)
        spin.setStartValue(0.0)
        spin.setEndValue(360.0)
        spin.setEasingCurve(QEasingCurve.InOutQuad)
        spin.valueChanged.connect(self._spin_star_frame)
        spin.finished.connect(self._finish_star_spin)
        self._star_spin_anim = spin
        spin.start(QAbstractAnimation.DeleteWhenStopped)

    def _spin_star_frame(self, angle):
        if not getattr(self, "_star_active", False):
            return
        try:
            self._star_angle = float(angle)
            self.github_btn.setIcon(QIcon(_render_star3d(angle, palette=self._star_palette())))
        except Exception:
            pass

    def _finish_star_spin(self):
        self._star_spin_anim = None
        if not getattr(self, "_star_active", False):
            return
        try:
            self._star_angle = 0.0
            self.github_btn.setIcon(QIcon(_render_star3d(0.0, palette=self._star_palette())))
        except Exception:
            pass

    def _restore_github_logo(self):
        if not getattr(self, "_star_active", False):
            return
        self._star_active = False
        try:
            self._star_timer.stop()
        except RuntimeError:
            pass
        button = self.github_btn
        button.setGraphicsEffect(None)
        button.setText("")
        button.setAccessibleName("GitHub")
        button.setIconSize(QSize(20, 20))
        self._update_github_icon()
        # Instant swap, then fade the logo back in (mirrors the 160ms
        # fade-in the star uses on the way out).
        try:
            effect = QGraphicsOpacityEffect(button)
            effect.setOpacity(0.0)
            button.setGraphicsEffect(effect)
            fade_in = QPropertyAnimation(effect, b"opacity", self)
            fade_in.setDuration(160)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.finished.connect(lambda: button.setGraphicsEffect(None))
            fade_in.start(QAbstractAnimation.DeleteWhenStopped)
        except (RuntimeError, AttributeError):
            try:
                button.setGraphicsEffect(None)
            except RuntimeError:
                pass

    def _apply_theme(self, is_dark: bool):
        if getattr(self, "_is_updating_theme", False):
            return
        self._is_updating_theme = True
        try:
            self.is_dark = is_dark
            self.setStyleSheet(get_wizard_stylesheet(is_dark))
            apply_native_mica(int(self.winId()), is_dark)
            self._update_github_icon()
            self._apply_widget_theme()
            self.refresh_all()
            if getattr(self, "_star_active", False):
                try:
                    self.github_btn.setIcon(QIcon(_render_star3d(getattr(self, "_star_angle", 0.0), palette=self._star_palette())))
                except Exception:
                    pass
        finally:
            self._is_updating_theme = False

    def _sync_theme(self):
        if getattr(self, "_is_updating_theme", False):
            return
        current_dark = is_system_dark_mode()
        theme_sig = (current_dark, _accent_signature())
        if theme_sig == getattr(self, "_last_theme_sig", None):
            return
        self._last_theme_sig = theme_sig
        self._apply_theme(current_dark)

    def keyPressEvent(self, event):
        if self._armed_button is not None:
            if event.key() == Qt.Key_Escape:
                self._disarm()
                event.accept()
                return
            if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
                self._confirm_armed()
                event.accept()
                return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event):
        try:
            weight_vp = (
                self.weight_scroll.viewport()
                if getattr(self, "weight_scroll", None) is not None
                else None
            )
        except RuntimeError:
            # Widget already destroyed during teardown; never touch it.
            weight_vp = None
        if (
            weight_vp is not None
            and watched is weight_vp
            and event.type() == QEvent.Type.Resize
        ):
            # A scrollbar showing/hiding re-wraps the flow into a different
            # row count; re-pin the container after Qt settles so the pinned
            # height can never drift from the real layup.
            QTimer.singleShot(0, self._resync_variant_height)
        if watched is self._armed_button:
            etype = event.type()
            if etype in (QEvent.Type.Enter, QEvent.Type.MouseMove):
                try:
                    x = event.position().x()
                except AttributeError:
                    x = event.pos().x()
                half = self._arm_half_at(x, watched.width())
                if getattr(self, "_armed_hover_half", None) != half:
                    self._armed_hover_half = half
                    self._paint_arm_halves(half)
            elif etype == QEvent.Type.Leave:
                if getattr(self, "_armed_hover_half", None) is not None:
                    self._armed_hover_half = None
                    self._paint_arm_halves(None)
        if (
            watched is self._armed_button
            and event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            try:
                pos = event.position()
                x, y = pos.x(), pos.y()
            except AttributeError:
                x, y = event.pos().x(), event.pos().y()
            inside = watched.rect().contains(int(x), int(y))
            left_half = x < watched.width() * self._CONFIRM_FRACTION
            ready = time.monotonic() - self._armed_at >= self._ARM_DELAY_S
            if inside and left_half and ready:
                action = self._armed_action
                self._disarm()
                action()
            elif inside and left_half:
                # Early left-half click: ignore and stay armed, so a fast
                # double-click reads as "confirm" rather than "cancel".
                pass
            else:
                self._disarm()
            return True
        return super().eventFilter(watched, event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if getattr(self, "_is_updating_theme", False):
            return
        if event.type() in (QEvent.ThemeChange, QEvent.ApplicationPaletteChange):
            self._sync_theme()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_responsive_layout()
        self._sync_variant_layout_height()
        if self._armed_button is not None:
            self._layout_arm_halves()
        cover = getattr(self, "_op_cover", None)
        cover_btn = getattr(self, "_op_cover_btn", None)
        if cover is not None and cover_btn is not None:
            try:
                cover.setGeometry(1, 1, max(1, cover_btn.width() - 2), max(1, cover_btn.height() - 2))
            except RuntimeError:
                pass

    def _sync_responsive_layout(self):
        if not hasattr(self, "setup_layout"):
            return

        is_compact = self.width() < 700
        if self._compact_layout == is_compact:
            return

        self._compact_layout = is_compact
        if is_compact:
            self.main_layout.setContentsMargins(24, 20, 24, 20)
            self.main_layout.setSpacing(16)
        else:
            self.main_layout.setContentsMargins(36, 28, 36, 28)
            self.main_layout.setSpacing(20)

        self.setup_card.updateGeometry()
        self.banner.updateGeometry()

    def _sync_variant_layout_height(self):
        if not hasattr(self, "weight_scroll"):
            return
        if not self.weight_scroll.isVisible() or self.weight_layout.count() == 0:
            self.weight_widget.setMinimumHeight(0)
            self.weight_widget.setMaximumHeight(16777215)
            # Forget the key while hidden: the next show must re-pin.
            # Keeping it let a later sync early-return while the container
            # was unpinned (collapsed to the viewport), which made the list
            # scroll through dead space past the last card.
            self._variant_geom_key = None
            return

        # Pin to the height the cards ACTUALLY occupy. A separate
        # heightForWidth() pass can disagree with the real layup (stale
        # viewport width, different column count after a scrollbar toggles,
        # unpolished cards), and any leftover shows up as empty rows past
        # the last card plus extra scroll range.
        content_height = 0
        for i in range(self.weight_layout.count()):
            item = self.weight_layout.itemAt(i)
            card = item.widget() if item is not None else None
            if card is None:
                continue
            try:
                g = card.geometry()
            except RuntimeError:
                continue
            content_height = max(content_height, g.y() + g.height())
        if content_height <= 0:
            # Cards not laid out yet (first build): estimate from the flow.
            viewport_width = self.weight_scroll.viewport().width()
            if viewport_width <= 0:
                viewport_width = self.weight_scroll.width()
            content_height = max(
                0, int(self.weight_layout.heightForWidth(max(0, viewport_width)))
            )

        geom_key = (self.weight_layout.count(), content_height)
        if geom_key == getattr(self, "_variant_geom_key", None):
            return
        self._variant_geom_key = geom_key
        try:
            self.weight_widget.setMinimumHeight(content_height)
            self.weight_widget.setMaximumHeight(content_height)
        except RuntimeError:
            return
        self.weight_widget.updateGeometry()

    def _resync_variant_height(self):
        try:
            if not hasattr(self, "weight_scroll"):
                return
            if self.weight_scroll.isVisible() and self.weight_layout.count():
                self.weight_layout.activate()
            self._sync_variant_layout_height()
        except RuntimeError:
            pass

    def nativeEvent(self, event_type, message):
        if event_type != b"windows_generic_MSG":
            return super().nativeEvent(event_type, message)

        try:
            msg = wintypes.MSG.from_address(int(message))
        except Exception:
            return super().nativeEvent(event_type, message)

        if msg.message in {
            WM_SETTINGCHANGE,
            WM_THEMECHANGED,
            WM_DWMCOLORIZATIONCOLORCHANGED,
        }:
            self._sync_theme()

        return super().nativeEvent(event_type, message)

    _ARMED_TICK = chr(0xE73E)
    _ARMED_CROSS = chr(0xE711)
    _ARMED_FONT_FAMILY = "Segoe MDL2 Assets"
    _ARMED_FONT_SIZE = 24
    _ARMED_CROSS_SIZE = 20
    _ARM_DELAY_S = 0.3
    _CONFIRM_FRACTION = 0.5

    def _arm_or_confirm(self, button, kind):
        now = time.monotonic()
        if self._armed_button is button:
            if now - self._armed_at < self._ARM_DELAY_S:
                return
            action = self._armed_action
            self._disarm()
            action()
            return
        self._arm(button, kind)

    def _arm(self, button, kind):
        self._disarm()
        self._armed_button = button
        self._armed_action = {
            "apply": self.on_apply,
            "restore": self._start_restore_op,
            "restart": self._do_restart,
        }[kind]
        colors = get_theme_colors(self.is_dark)
        window_bg = _opaque_window_bg(self.is_dark)
        role = button.property("buttonRole") or "secondary"
        face = {
            "primary": ("accent", "accent_hover", "accent_text"),
            "warning": ("accent", "accent_hover", "warning_text"),
        }.get(role, ("bg_card", "bg_button_hover", "text_primary"))
        self._armed_face = {
            "bg": _solid_color(colors[face[0]], window_bg),
            "hover": _solid_color(colors[face[1]], window_bg),
            "ink": colors[face[2]],
        }
        yes_label = QLabel(self._ARMED_TICK, button)
        no_label = QLabel(self._ARMED_CROSS, button)
        self._arm_labels = (yes_label, no_label)
        for label in self._arm_labels:
            label.setAttribute(Qt.WA_TransparentForMouseEvents)
            label.setAlignment(Qt.AlignCenter)
        self._armed_hover_half = None
        try:
            button.setMouseTracking(True)
        except RuntimeError:
            pass
        self._layout_arm_halves()
        self._paint_arm_halves(None)
        for label in self._arm_labels:
            label.show()
        button.setAccessibleDescription("Armed. Activate the left side or press Enter to confirm, or press Escape to cancel.")
        self._armed_at = time.monotonic()

    def _layout_arm_halves(self):
        button = self._armed_button
        labels = getattr(self, "_arm_labels", None)
        if button is None or not labels:
            return
        try:
            width, height = button.width(), button.height()
            mid = width // 2
            labels[0].setGeometry(0, 0, mid, height)
            labels[1].setGeometry(mid, 0, width - mid, height)
        except RuntimeError:
            pass

    def _arm_half_at(self, x, width):
        try:
            return 0 if float(x) < float(width) * self._CONFIRM_FRACTION else 1
        except (TypeError, ValueError):
            return 0

    def _paint_arm_halves(self, half):
        labels = getattr(self, "_arm_labels", None)
        face = getattr(self, "_armed_face", None)
        if not labels or not face:
            return
        for index, label in enumerate(labels):
            background = face["hover"] if index == half else face["bg"]
            try:
                size = self._ARMED_CROSS_SIZE if index == 1 else self._ARMED_FONT_SIZE
                divider = "border: none;"
                radius_css = (
                    "border-top-left-radius: 4px; border-bottom-left-radius: 4px; border-top-right-radius: 0px; border-bottom-right-radius: 0px;"
                    if index == 0
                    else "border-top-right-radius: 4px; border-bottom-right-radius: 4px; border-top-left-radius: 0px; border-bottom-left-radius: 0px;"
                )
                label.setText(self._ARMED_TICK if index == 0 else self._ARMED_CROSS)
                label.setStyleSheet(
                    f"font-family: '{self._ARMED_FONT_FAMILY}'; "
                    f"font-size: {size}px; "
                    f"color: {face['ink']}; background-color: {background}; {divider} {radius_css}"
                )
            except RuntimeError:
                pass

    def _confirm_armed(self):
        if self._armed_button is None:
            return
        if time.monotonic() - self._armed_at >= self._ARM_DELAY_S:
            action = self._armed_action
            self._disarm()
            action()

    def _disarm(self):
        button = self._armed_button
        self._armed_button = None
        self._armed_action = None
        self._armed_face = None
        self._armed_hover_half = None
        for label in (getattr(self, "_arm_labels", None) or ()):
            try:
                label.hide()
                label.deleteLater()
            except RuntimeError:
                pass
        self._arm_labels = None
        if button is not None:
            try:
                button.setAccessibleDescription("")
            except RuntimeError:
                pass
            try:
                button.setMouseTracking(False)
            except RuntimeError:
                pass

    def _on_local_pick(self):
        font_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择静态 TrueType 字体",
            "",
            "静态 TrueType 字体 (*.ttf)",
        )
        if not font_path:
            return
        self._select_regular(font_path)

    def _select_regular(self, font_path):
        try:
            self.controller.set_regular_font(font_path)
        except Exception as exc:
            QMessageBox.warning(self, "不支持此字体", str(exc))
            return False
        self._selection_dirty = True
        self._hide_applied_variants = False
        self.refresh_all()
        return True

    def on_apply_action(self):
        if self._apply_action == "restart":
            self._arm_or_confirm(self.apply_btn, "restart")
        else:
            self._arm_or_confirm(self.apply_btn, "apply")

    def _run_operation(self, func, btn, text):
        self._disarm()
        if self._op_thread and self._op_thread.isRunning():
            return

        for button in self._action_buttons:
            button.setEnabled(False)
        self.chinese_option.setEnabled(False)
        self.jhenghei_option.setEnabled(False)
        self.explorer_option.setEnabled(False)
        self.font_scale.setEnabled(False)
        colors = get_theme_colors(self.is_dark)
        cover = QLabel(text, btn)
        cover.setAlignment(Qt.AlignCenter)
        cover.setGeometry(0, 0, btn.width(), btn.height())
        cover.setStyleSheet(
            "font-family: 'Segoe UI'; font-size: 13px; font-weight: 600; "
            f"color: {colors['accent_text']}; background-color: {colors['accent']}; "
            f"border: 1px solid {colors['accent']}; border-radius: 4px;"
        )
        cover.show()
        self._op_cover = cover
        self._op_cover_btn = btn
        self._set_button_role(btn, "primary")
        self._op_thread = OperationThread(func, self)
        self._op_thread.done.connect(lambda r: self._on_operation_done(r, btn))
        self._op_thread.finished.connect(self._op_thread.deleteLater)
        self._op_thread.start()

    def _on_operation_done(self, result, btn):
        cover = getattr(self, "_op_cover", None)
        self._op_cover = None
        self._op_cover_btn = None
        if cover is not None:
            try:
                cover.hide()
                cover.deleteLater()
            except RuntimeError:
                pass
        self._op_thread = None

        if not isinstance(result, OperationResult):
            result = OperationResult(
                False,
                "The operation finished with an unexpected result.",
                [repr(result)],
            )

        if btn == self.apply_btn and result.success:
            self._selection_dirty = False

        if not result.success:
            QMessageBox.warning(self, "操作结果", result.message)
        elif result.warnings:
            QMessageBox.information(self, "操作结果", result.message + "\n\n" + "\n".join(result.warnings))
        self.refresh_all()
        if btn == self.apply_btn and result.success:
            self._morph_to_star()

    def on_apply(self):
        self._run_operation(self.controller.apply, self.apply_btn, "Applying...")

    def on_restore(self):
        if getattr(self, "_restore_action", "restore") == "restart":
            self._arm_or_confirm(self.restore_btn, "restart")
            return
        self._arm_or_confirm(self.restore_btn, "restore")

    def _start_restore_op(self):
        self._run_operation(self.controller.restore, self.restore_btn, "Restoring...")

    def _do_restart(self):
        try:
            subprocess.run(["shutdown", "/r", "/t", "0"], check=True)
        except Exception as exc:
            QMessageBox.warning(self, "重启失败", f"Could not initiate Windows restart: {exc}\n\nPlease restart your computer manually to finish the setup.")

    def refresh_all(self):
        self._disarm()
        report = self.controller.refresh_preflight()
        colors = get_theme_colors(self.is_dark)

        is_pending = report.install_state in ("pending_reboot_apply", "pending_reboot_recovery")
        if not report.is_supported:
            self.banner.set_icon("\uEA39", colors["accent_icon"])
        elif not report.is_admin:
            self.banner.set_icon("\uE83D", colors["accent_icon"])
        elif is_pending:
            self.banner.set_icon("\uE895", colors["accent_icon"])
        elif report.install_state == "managed":
            self.banner.set_icon("\uE930", colors["accent_icon"])
        elif report.install_state == "partial":
            self.banner.set_icon("\uEA39", colors["accent_icon"])
        elif report.issues:
            self.banner.set_icon("\uEA39", colors["accent_icon"])
        else:
            self.banner.set_icon("\uE930", colors["accent_icon"])

        self.banner.set_content(report.headline, report.summary)

        regular_font = self.controller.selection.paths.get("regular")
        can_apply = report.can_apply_changes and regular_font is not None
        has_selected_font = regular_font is not None
        is_apply_pending = report.install_state == "pending_reboot_apply"
        is_recovery_pending = report.install_state == "pending_reboot_recovery"
        self.chinese_option.setEnabled(not is_pending)
        self.jhenghei_option.setEnabled(not is_pending)
        self.explorer_option.setEnabled(not is_pending)
        self.font_scale.setEnabled(not is_pending)

        if is_recovery_pending:
            self._browse_action = "select"
            self._apply_action = "restart"
            self._restore_action = "restart"
            apply_text = "重启 Windows"
            restore_text = "重启 Windows"
            apply_visible = True
            restore_visible = False
            apply_available = True
            restore_available = True
        elif is_apply_pending:
            self._browse_action = "select"
            self._restore_action = "restore"
            if has_selected_font and self._selection_dirty:
                self._apply_action = "apply"
                apply_text = "应用字体"
                apply_available = can_apply
            else:
                self._apply_action = "restart"
                apply_text = "重启 Windows"
                apply_available = True
            restore_text = "恢复原始字体"
            apply_visible = True
            restore_visible = False
            restore_available = False
        else:
            self._browse_action = "select"
            self._apply_action = "apply"
            self._restore_action = "restore"
            apply_text = "应用字体"
            apply_available = can_apply
            restore_text = "恢复原始字体"
            apply_visible = has_selected_font
            restore_visible = report.install_state in ("managed", "partial")
            apply_available = apply_visible and can_apply
            restore_available = restore_visible and report.can_restore_defaults

        self.local_btn.setEnabled(not is_recovery_pending)
        self.local_btn.setVisible(not is_recovery_pending)

        self.apply_btn.setText(apply_text)
        self.apply_btn.setEnabled(apply_available)
        self.apply_btn.setVisible(apply_visible)

        self.restore_btn.setEnabled(restore_available)
        self.restore_btn.setVisible(restore_visible)
        self.restore_btn.setText(restore_text)

        if not can_apply and self._apply_action != "restart":
            if not regular_font:
                self.apply_btn.setToolTip("请先选择要应用的字体。")
            else:
                self.apply_btn.setToolTip(
                    "\n".join(report.issues) if report.issues else "Cannot apply changes right now."
                )
        else:
            self.apply_btn.setToolTip("")

        if not self.restore_btn.isEnabled() and self._restore_action != "restart":
            self.restore_btn.setToolTip("当前无法恢复字体。")
        else:
            self.restore_btn.setToolTip("")

        apply_role = "primary"
        restore_role = "secondary"

        self._set_button_role(self.local_btn, "secondary" if has_selected_font else "primary")
        self._set_button_role(self.apply_btn, apply_role)
        self._set_button_role(self.restore_btn, restore_role)

        self.cur_font_lbl.setText(Path(regular_font).name if regular_font else "尚未选择字体")

        cards_sig = (
            tuple(sorted((key, str(value)) for key, value in self.controller.selection.paths.items())),
            tuple(sorted((key, value) for key, value in self.controller.selection.labels.items())),
            self.is_dark,
        )
        rebuild_cards = cards_sig != getattr(self, "_cards_sig", None)
        if rebuild_cards:
            self._cards_sig = cards_sig
            self._variant_geom_key = None
            while self.weight_layout.count():
                item = self.weight_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    if hasattr(widget, "cleanup"):
                        widget.cleanup()
                    widget.deleteLater()

        def _handle_card_change(w):
            current_path = self.controller.selection.paths.get(w) or self.controller.selection.paths.get("regular") or "."
            start_dir = str(Path(current_path).parent)
            if w == "variable":
                display_name = "可变界面字体"
            else:
                display_name = w.replace("consolas_", "Consolas ").replace("_", " ").title()
            chosen_file, _ = QFileDialog.getOpenFileName(
                self,
                f"Select Font File for {display_name}",
                start_dir,
                "TrueType Fonts (*.ttf);;All Files (*.*)",
            )
            if chosen_file:
                try:
                    self.controller.set_card_override(w, chosen_file)
                    self._selection_dirty = True
                    self.refresh_all()
                except Exception as exc:
                    QMessageBox.warning(self, "字体无效", str(exc))

        def _handle_card_reset(w):
            self.controller.reset_card_override(w)
            self._selection_dirty = True
            self.refresh_all()

        cards_added = 0
        if rebuild_cards:
            for weight, font_path in self.controller.selection.paths.items():
                if font_path:
                    try:
                        is_manual = (self.controller.selection.labels.get(weight) == "manual")
                        card = WeightCard(
                            weight,
                            font_path,
                            is_manual=is_manual,
                            is_dark=self.is_dark,
                            on_change=_handle_card_change,
                            on_reset=_handle_card_reset,
                        )
                        card.set_preview_scale(self.controller.workflow.font_scale)
                        self.weight_layout.addWidget(card)
                        card.show()
                        cards_added += 1
                    except (ValueError, OSError):
                        pass
        else:
            cards_added = self.weight_layout.count()

        show_variant_section = has_selected_font and not is_recovery_pending
        has_variants = show_variant_section and cards_added > 0
        self.variant_count_lbl.setText(f"{cards_added} 种样式" if has_variants else "暂无预览")

        self.variants_header.setVisible(show_variant_section)
        self.empty_variants.setVisible(show_variant_section and not has_variants)
        self.weight_scroll.setVisible(has_variants)
        if hasattr(self, "local_fonts_guide"):
            show_guide = not has_selected_font and not is_recovery_pending
            self.local_fonts_guide.setVisible(show_guide)
        if has_variants:
            self.weight_widget.show()
        # Lay the cards first, then pin to their real geometry: syncing
        # before activate() measured a stale or estimated layup.
        self.weight_layout.activate()
        self._sync_variant_layout_height()
        self.weight_widget.update()

    def closeEvent(self, event):
        op_thread = getattr(self, "_op_thread", None)
        if op_thread is not None and op_thread.isRunning():
            event.ignore()
            return
        try:
            self._stop_star_anim()
        except Exception:
            pass
        event.accept()

    def run(self):
        self.show()
        # Re-assert the default size once native: creating the native
        # window during __init__ (mica/winId) eats ~20px of height.
        self.resize(1050, 650)
        return QApplication.instance().exec()

if __name__ == "__main__":
    from main import main
    sys.exit(main())
