"""Application palettes and Windows title-bar theme handling."""

from __future__ import annotations

import sys
from typing import Any


LIGHT_COLORS = {
    "window": "#f7f7f8",
    "panel": "#ffffff",
    "sidebar": "#f1f2f3",
    "text": "#202123",
    "strong_text": "#17181a",
    "muted": "#72767d",
    "icon": "#46505a",
    "border": "#d7d9dd",
    "divider": "#e2e3e5",
    "hover": "#eceeef",
    "pressed": "#e7e9eb",
    "disabled_bg": "#f4f4f5",
    "disabled_text": "#a2a5aa",
    "accent": "#176b5b",
    "accent_hover": "#12594c",
    "accent_text": "#ffffff",
    "selection": "#dde9e6",
    "selection_text": "#111111",
    "focus": "#4d8f82",
    "code_bg": "#f4f6f8",
    "code_border": "#cfd5db",
    "highlight": "#fff0a8",
    "badge_bg": "#e2efec",
    "badge_text": "#285c52",
}

DARK_COLORS = {
    "window": "#080807",
    "panel": "#000000",
    "sidebar": "#0e0d0c",
    "text": "#dfdedc",
    "strong_text": "#ffffff",
    "muted": "#8d8982",
    "icon": "#b9afa5",
    "border": "#282622",
    "divider": "#1d1c1a",
    "hover": "#131110",
    "pressed": "#181614",
    "disabled_bg": "#0b0b0a",
    "disabled_text": "#5d5a55",
    "accent": "#b8ddd5",
    "accent_hover": "#cde9e3",
    "accent_text": "#000000",
    "selection": "#123d36",
    "selection_text": "#ffffff",
    "focus": "#b2707d",
    "code_bg": "#0b0907",
    "code_border": "#302a24",
    "highlight": "#000f57",
    "badge_bg": "#1d1013",
    "badge_text": "#d7a39a",
}


def theme_colors(theme: str) -> dict[str, str]:
    return DARK_COLORS if theme == "dark" else LIGHT_COLORS


def system_theme(app: Any | None = None) -> str:
    """Return the current operating-system color scheme."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication

        application = app or QApplication.instance()
        if application is not None:
            scheme = application.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return "dark"
            if scheme == Qt.ColorScheme.Light:
                return "light"
    except (AttributeError, ImportError, RuntimeError):
        pass

    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                apps_use_light, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if int(apps_use_light) else "dark"
        except (OSError, ValueError):
            pass
    return "light"


def resolved_theme(preference: str, app: Any | None = None) -> str:
    """Resolve light/dark/system preference to a concrete rendering theme."""
    return system_theme(app) if preference == "system" else preference


def create_palette(theme: str):
    """Create a stable palette independent of the operating-system theme."""
    from PyQt6.QtGui import QColor, QPalette

    colors = theme_colors(theme)
    palette = QPalette()
    values = {
        QPalette.ColorRole.Window: colors["window"],
        QPalette.ColorRole.WindowText: colors["text"],
        QPalette.ColorRole.Base: colors["panel"],
        QPalette.ColorRole.AlternateBase: colors["window"],
        QPalette.ColorRole.ToolTipBase: colors["panel"],
        QPalette.ColorRole.ToolTipText: colors["text"],
        QPalette.ColorRole.Text: colors["text"],
        QPalette.ColorRole.Button: colors["panel"],
        QPalette.ColorRole.ButtonText: colors["text"],
        QPalette.ColorRole.BrightText: colors["strong_text"],
        QPalette.ColorRole.Highlight: colors["selection"],
        QPalette.ColorRole.HighlightedText: colors["selection_text"],
        QPalette.ColorRole.PlaceholderText: colors["muted"],
        QPalette.ColorRole.Link: colors["accent"],
        QPalette.ColorRole.LinkVisited: colors["accent_hover"],
    }
    for role, color in values.items():
        palette.setColor(role, QColor(color))
    return palette


def apply_application_palette(app: Any, theme: str) -> None:
    app.setPalette(create_palette(theme))


def set_windows_title_bar_theme(window: Any, theme: str) -> None:
    """Match the Windows native title bar to the selected application theme."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        enabled = ctypes.c_int(1 if theme == "dark" else 0)
        hwnd = int(window.winId())
        for attribute in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(enabled),
                ctypes.sizeof(enabled),
            )
            if result == 0:
                break
    except (AttributeError, OSError, TypeError, ValueError):
        pass


__all__ = [
    "apply_application_palette",
    "create_palette",
    "resolved_theme",
    "set_windows_title_bar_theme",
    "system_theme",
    "theme_colors",
]
