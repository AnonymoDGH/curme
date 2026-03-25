#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    NVIDIA CODE - Markdown Renderer Pro                       ║
║                     Terminal Markdown Renderer v2.0                          ║
║                                                                              ║
║  Características:                                                            ║
║  • Renderizado completo de Markdown con colores ANSI                        ║
║  • Syntax highlighting para 20+ lenguajes                                   ║
║  • Tablas con bordes Unicode y alineación                                   ║
║  • Soporte para GFM (GitHub Flavored Markdown)                              ║
║  • Alertas/Admonitions estilo GitHub                                        ║
║  • Bloques matemáticos y código                                             ║
║  • Emojis, badges, progress bars                                            ║
║  • Temas personalizables                                                    ║
║  • Word wrapping inteligente                                                ║
║                                                                              ║
║  Autor: NVIDIA Code Assistant                                                ║
║  Licencia: MIT                                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import re
import os
import sys
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import lru_cache
from typing import (
    Callable, Dict, List, Optional, Pattern, 
    Tuple, Union, Any, NamedTuple, TypeVar
)

# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1: CÓDIGOS ANSI Y SISTEMA DE COLORES
# ══════════════════════════════════════════════════════════════════════════════

class AnsiCode:
    """Códigos ANSI para formateo de terminal"""
    
    # Reset
    RESET = "\033[0m"
    RESET_BOLD = "\033[22m"
    RESET_DIM = "\033[22m"
    RESET_ITALIC = "\033[23m"
    RESET_UNDERLINE = "\033[24m"
    RESET_BLINK = "\033[25m"
    RESET_REVERSE = "\033[27m"
    RESET_HIDDEN = "\033[28m"
    RESET_STRIKETHROUGH = "\033[29m"
    
    # Estilos de texto
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    BLINK_FAST = "\033[6m"
    REVERSE = "\033[7m"
    HIDDEN = "\033[8m"
    STRIKETHROUGH = "\033[9m"
    
    # Subrayados especiales (no soportado en todas las terminales)
    DOUBLE_UNDERLINE = "\033[21m"
    CURLY_UNDERLINE = "\033[4:3m"
    DOTTED_UNDERLINE = "\033[4:4m"
    DASHED_UNDERLINE = "\033[4:5m"
    
    # Colores de texto estándar (30-37)
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    DEFAULT = "\033[39m"
    
    # Colores de texto brillantes (90-97)
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # Colores de fondo estándar (40-47)
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"
    BG_DEFAULT = "\033[49m"
    
    # Colores de fondo brillantes (100-107)
    BG_BRIGHT_BLACK = "\033[100m"
    BG_BRIGHT_RED = "\033[101m"
    BG_BRIGHT_GREEN = "\033[102m"
    BG_BRIGHT_YELLOW = "\033[103m"
    BG_BRIGHT_BLUE = "\033[104m"
    BG_BRIGHT_MAGENTA = "\033[105m"
    BG_BRIGHT_CYAN = "\033[106m"
    BG_BRIGHT_WHITE = "\033[107m"
    
    @staticmethod
    def rgb(r: int, g: int, b: int) -> str:
        """Color de texto RGB (24-bit)"""
        return f"\033[38;2;{r};{g};{b}m"
    
    @staticmethod
    def bg_rgb(r: int, g: int, b: int) -> str:
        """Color de fondo RGB (24-bit)"""
        return f"\033[48;2;{r};{g};{b}m"
    
    @staticmethod
    def color_256(code: int) -> str:
        """Color de texto 256 colores"""
        return f"\033[38;5;{code}m"
    
    @staticmethod
    def bg_color_256(code: int) -> str:
        """Color de fondo 256 colores"""
        return f"\033[48;5;{code}m"
    
    @staticmethod
    def underline_color(r: int, g: int, b: int) -> str:
        """Color de subrayado RGB"""
        return f"\033[58;2;{r};{g};{b}m"


class ThemeColor(NamedTuple):
    """Definición de un color de tema"""
    fg: str
    bg: str = ""
    style: str = ""


class Theme(Enum):
    """Temas disponibles para el renderizador"""
    NVIDIA = auto()
    MONOKAI = auto()
    DRACULA = auto()
    NORD = auto()
    SOLARIZED_DARK = auto()
    SOLARIZED_LIGHT = auto()
    GRUVBOX = auto()
    ONE_DARK = auto()
    GITHUB_DARK = auto()
    CATPPUCCIN = auto()


@dataclass
class ColorScheme:
    """Esquema de colores completo para el renderizador"""
    
    # Colores principales
    primary: str = ""
    secondary: str = ""
    accent: str = ""
    
    # Headers
    h1: str = ""
    h2: str = ""
    h3: str = ""
    h4: str = ""
    h5: str = ""
    h6: str = ""
    
    # Texto
    text: str = ""
    text_dim: str = ""
    text_bold: str = ""
    text_italic: str = ""
    
    # Código
    code_bg: str = ""
    code_text: str = ""
    code_keyword: str = ""
    code_string: str = ""
    code_number: str = ""
    code_comment: str = ""
    code_function: str = ""
    code_class: str = ""
    code_variable: str = ""
    code_operator: str = ""
    code_punctuation: str = ""
    
    # Links
    link: str = ""
    link_visited: str = ""
    
    # Listas
    bullet: str = ""
    bullet_secondary: str = ""
    number: str = ""
    checkbox_done: str = ""
    checkbox_pending: str = ""
    
    # Bloques
    quote: str = ""
    quote_border: str = ""
    
    # Tablas
    table_border: str = ""
    table_header: str = ""
    table_row_odd: str = ""
    table_row_even: str = ""
    
    # Alertas/Admonitions
    alert_note: str = ""
    alert_tip: str = ""
    alert_important: str = ""
    alert_warning: str = ""
    alert_caution: str = ""
    
    # Misc
    hr: str = ""
    border: str = ""
    success: str = ""
    error: str = ""
    info: str = ""
    
    @classmethod
    def from_theme(cls, theme: Theme) -> 'ColorScheme':
        """Crea un esquema de colores basado en un tema predefinido"""
        schemes = {
            Theme.NVIDIA: cls._nvidia_theme(),
            Theme.MONOKAI: cls._monokai_theme(),
            Theme.DRACULA: cls._dracula_theme(),
            Theme.NORD: cls._nord_theme(),
            Theme.SOLARIZED_DARK: cls._solarized_dark_theme(),
            Theme.GRUVBOX: cls._gruvbox_theme(),
            Theme.ONE_DARK: cls._one_dark_theme(),
            Theme.GITHUB_DARK: cls._github_dark_theme(),
            Theme.CATPPUCCIN: cls._catppuccin_theme(),
        }
        return schemes.get(theme, cls._nvidia_theme())
    
    @classmethod
    def _nvidia_theme(cls) -> 'ColorScheme':
        """Tema NVIDIA - Verde característico"""
        return cls(
            primary=AnsiCode.rgb(118, 185, 0),  # NVIDIA Green
            secondary=AnsiCode.BRIGHT_WHITE,
            accent=AnsiCode.BRIGHT_CYAN,
            
            h1=AnsiCode.rgb(118, 185, 0),
            h2=AnsiCode.BRIGHT_WHITE,
            h3=AnsiCode.BRIGHT_CYAN,
            h4=AnsiCode.BRIGHT_YELLOW,
            h5=AnsiCode.BRIGHT_MAGENTA,
            h6=AnsiCode.DIM,
            
            text=AnsiCode.WHITE,
            text_dim=AnsiCode.DIM,
            text_bold=AnsiCode.BOLD,
            text_italic=AnsiCode.ITALIC,
            
            code_bg=AnsiCode.BG_BRIGHT_BLACK,
            code_text=AnsiCode.BRIGHT_YELLOW,
            code_keyword=AnsiCode.BRIGHT_MAGENTA,
            code_string=AnsiCode.BRIGHT_GREEN,
            code_number=AnsiCode.BRIGHT_YELLOW,
            code_comment=AnsiCode.DIM,
            code_function=AnsiCode.BRIGHT_CYAN,
            code_class=AnsiCode.BRIGHT_YELLOW,
            code_variable=AnsiCode.WHITE,
            code_operator=AnsiCode.BRIGHT_WHITE,
            code_punctuation=AnsiCode.DIM,
            
            link=AnsiCode.BRIGHT_BLUE + AnsiCode.UNDERLINE,
            link_visited=AnsiCode.BRIGHT_MAGENTA + AnsiCode.UNDERLINE,
            
            bullet=AnsiCode.rgb(118, 185, 0),
            bullet_secondary=AnsiCode.DIM,
            number=AnsiCode.BRIGHT_CYAN,
            checkbox_done=AnsiCode.BRIGHT_GREEN,
            checkbox_pending=AnsiCode.DIM,
            
            quote=AnsiCode.ITALIC + AnsiCode.DIM,
            quote_border=AnsiCode.rgb(118, 185, 0),
            
            table_border=AnsiCode.DIM,
            table_header=AnsiCode.BOLD + AnsiCode.BRIGHT_WHITE,
            table_row_odd="",
            table_row_even=AnsiCode.DIM,
            
            alert_note=AnsiCode.BRIGHT_BLUE,
            alert_tip=AnsiCode.BRIGHT_GREEN,
            alert_important=AnsiCode.BRIGHT_MAGENTA,
            alert_warning=AnsiCode.BRIGHT_YELLOW,
            alert_caution=AnsiCode.BRIGHT_RED,
            
            hr=AnsiCode.DIM,
            border=AnsiCode.DIM,
            success=AnsiCode.BRIGHT_GREEN,
            error=AnsiCode.BRIGHT_RED,
            info=AnsiCode.BRIGHT_BLUE,
        )
    
    @classmethod
    def _monokai_theme(cls) -> 'ColorScheme':
        """Tema Monokai"""
        return cls(
            primary=AnsiCode.rgb(249, 38, 114),  # Rosa Monokai
            secondary=AnsiCode.rgb(248, 248, 242),
            accent=AnsiCode.rgb(102, 217, 239),
            
            h1=AnsiCode.rgb(249, 38, 114),
            h2=AnsiCode.rgb(248, 248, 242),
            h3=AnsiCode.rgb(102, 217, 239),
            h4=AnsiCode.rgb(230, 219, 116),
            h5=AnsiCode.rgb(174, 129, 255),
            h6=AnsiCode.rgb(117, 113, 94),
            
            text=AnsiCode.rgb(248, 248, 242),
            text_dim=AnsiCode.rgb(117, 113, 94),
            text_bold=AnsiCode.BOLD,
            text_italic=AnsiCode.ITALIC,
            
            code_bg=AnsiCode.rgb(39, 40, 34),
            code_text=AnsiCode.rgb(248, 248, 242),
            code_keyword=AnsiCode.rgb(249, 38, 114),
            code_string=AnsiCode.rgb(230, 219, 116),
            code_number=AnsiCode.rgb(174, 129, 255),
            code_comment=AnsiCode.rgb(117, 113, 94),
            code_function=AnsiCode.rgb(166, 226, 46),
            code_class=AnsiCode.rgb(102, 217, 239),
            code_variable=AnsiCode.rgb(248, 248, 242),
            code_operator=AnsiCode.rgb(249, 38, 114),
            code_punctuation=AnsiCode.rgb(248, 248, 242),
            
            link=AnsiCode.rgb(102, 217, 239) + AnsiCode.UNDERLINE,
            link_visited=AnsiCode.rgb(174, 129, 255) + AnsiCode.UNDERLINE,
            
            bullet=AnsiCode.rgb(249, 38, 114),
            bullet_secondary=AnsiCode.rgb(117, 113, 94),
            number=AnsiCode.rgb(174, 129, 255),
            checkbox_done=AnsiCode.rgb(166, 226, 46),
            checkbox_pending=AnsiCode.rgb(117, 113, 94),
            
            quote=AnsiCode.ITALIC + AnsiCode.rgb(117, 113, 94),
            quote_border=AnsiCode.rgb(249, 38, 114),
            
            table_border=AnsiCode.rgb(117, 113, 94),
            table_header=AnsiCode.BOLD + AnsiCode.rgb(248, 248, 242),
            table_row_odd="",
            table_row_even=AnsiCode.DIM,
            
            alert_note=AnsiCode.rgb(102, 217, 239),
            alert_tip=AnsiCode.rgb(166, 226, 46),
            alert_important=AnsiCode.rgb(174, 129, 255),
            alert_warning=AnsiCode.rgb(230, 219, 116),
            alert_caution=AnsiCode.rgb(249, 38, 114),
            
            hr=AnsiCode.rgb(117, 113, 94),
            border=AnsiCode.rgb(117, 113, 94),
            success=AnsiCode.rgb(166, 226, 46),
            error=AnsiCode.rgb(249, 38, 114),
            info=AnsiCode.rgb(102, 217, 239),
        )
    
    @classmethod
    def _dracula_theme(cls) -> 'ColorScheme':
        """Tema Dracula"""
        return cls(
            primary=AnsiCode.rgb(189, 147, 249),  # Purple
            secondary=AnsiCode.rgb(248, 248, 242),
            accent=AnsiCode.rgb(139, 233, 253),  # Cyan
            
            h1=AnsiCode.rgb(255, 121, 198),  # Pink
            h2=AnsiCode.rgb(248, 248, 242),
            h3=AnsiCode.rgb(139, 233, 253),
            h4=AnsiCode.rgb(241, 250, 140),  # Yellow
            h5=AnsiCode.rgb(189, 147, 249),
            h6=AnsiCode.rgb(98, 114, 164),  # Comment
            
            text=AnsiCode.rgb(248, 248, 242),
            text_dim=AnsiCode.rgb(98, 114, 164),
            text_bold=AnsiCode.BOLD,
            text_italic=AnsiCode.ITALIC,
            
            code_bg=AnsiCode.bg_rgb(40, 42, 54),
            code_text=AnsiCode.rgb(248, 248, 242),
            code_keyword=AnsiCode.rgb(255, 121, 198),
            code_string=AnsiCode.rgb(241, 250, 140),
            code_number=AnsiCode.rgb(189, 147, 249),
            code_comment=AnsiCode.rgb(98, 114, 164),
            code_function=AnsiCode.rgb(80, 250, 123),
            code_class=AnsiCode.rgb(139, 233, 253),
            code_variable=AnsiCode.rgb(248, 248, 242),
            code_operator=AnsiCode.rgb(255, 121, 198),
            code_punctuation=AnsiCode.rgb(248, 248, 242),
            
            link=AnsiCode.rgb(139, 233, 253) + AnsiCode.UNDERLINE,
            link_visited=AnsiCode.rgb(189, 147, 249) + AnsiCode.UNDERLINE,
            
            bullet=AnsiCode.rgb(255, 121, 198),
            bullet_secondary=AnsiCode.rgb(98, 114, 164),
            number=AnsiCode.rgb(189, 147, 249),
            checkbox_done=AnsiCode.rgb(80, 250, 123),
            checkbox_pending=AnsiCode.rgb(98, 114, 164),
            
            quote=AnsiCode.ITALIC + AnsiCode.rgb(98, 114, 164),
            quote_border=AnsiCode.rgb(189, 147, 249),
            
            table_border=AnsiCode.rgb(98, 114, 164),
            table_header=AnsiCode.BOLD + AnsiCode.rgb(248, 248, 242),
            table_row_odd="",
            table_row_even=AnsiCode.DIM,
            
            alert_note=AnsiCode.rgb(139, 233, 253),
            alert_tip=AnsiCode.rgb(80, 250, 123),
            alert_important=AnsiCode.rgb(189, 147, 249),
            alert_warning=AnsiCode.rgb(255, 184, 108),
            alert_caution=AnsiCode.rgb(255, 85, 85),
            
            hr=AnsiCode.rgb(98, 114, 164),
            border=AnsiCode.rgb(98, 114, 164),
            success=AnsiCode.rgb(80, 250, 123),
            error=AnsiCode.rgb(255, 85, 85),
            info=AnsiCode.rgb(139, 233, 253),
        )
    
    @classmethod
    def _nord_theme(cls) -> 'ColorScheme':
        """Tema Nord"""
        return cls(
            primary=AnsiCode.rgb(136, 192, 208),  # Nord8 - Frost
            secondary=AnsiCode.rgb(236, 239, 244),  # Nord6
            accent=AnsiCode.rgb(129, 161, 193),  # Nord9
            
            h1=AnsiCode.rgb(136, 192, 208),
            h2=AnsiCode.rgb(236, 239, 244),
            h3=AnsiCode.rgb(129, 161, 193),
            h4=AnsiCode.rgb(235, 203, 139),  # Nord13
            h5=AnsiCode.rgb(180, 142, 173),  # Nord15
            h6=AnsiCode.rgb(76, 86, 106),  # Nord3
            
            text=AnsiCode.rgb(236, 239, 244),
            text_dim=AnsiCode.rgb(76, 86, 106),
            text_bold=AnsiCode.BOLD,
            text_italic=AnsiCode.ITALIC,
            
            code_bg=AnsiCode.bg_rgb(46, 52, 64),
            code_text=AnsiCode.rgb(236, 239, 244),
            code_keyword=AnsiCode.rgb(180, 142, 173),
            code_string=AnsiCode.rgb(163, 190, 140),  # Nord14
            code_number=AnsiCode.rgb(180, 142, 173),
            code_comment=AnsiCode.rgb(76, 86, 106),
            code_function=AnsiCode.rgb(136, 192, 208),
            code_class=AnsiCode.rgb(235, 203, 139),
            code_variable=AnsiCode.rgb(236, 239, 244),
            code_operator=AnsiCode.rgb(129, 161, 193),
            code_punctuation=AnsiCode.rgb(216, 222, 233),
            
            link=AnsiCode.rgb(136, 192, 208) + AnsiCode.UNDERLINE,
            link_visited=AnsiCode.rgb(180, 142, 173) + AnsiCode.UNDERLINE,
            
            bullet=AnsiCode.rgb(136, 192, 208),
            bullet_secondary=AnsiCode.rgb(76, 86, 106),
            number=AnsiCode.rgb(129, 161, 193),
            checkbox_done=AnsiCode.rgb(163, 190, 140),
            checkbox_pending=AnsiCode.rgb(76, 86, 106),
            
            quote=AnsiCode.ITALIC + AnsiCode.rgb(76, 86, 106),
            quote_border=AnsiCode.rgb(136, 192, 208),
            
            table_border=AnsiCode.rgb(76, 86, 106),
            table_header=AnsiCode.BOLD + AnsiCode.rgb(236, 239, 244),
            table_row_odd="",
            table_row_even=AnsiCode.DIM,
            
            alert_note=AnsiCode.rgb(129, 161, 193),
            alert_tip=AnsiCode.rgb(163, 190, 140),
            alert_important=AnsiCode.rgb(180, 142, 173),
            alert_warning=AnsiCode.rgb(235, 203, 139),
            alert_caution=AnsiCode.rgb(191, 97, 106),
            
            hr=AnsiCode.rgb(76, 86, 106),
            border=AnsiCode.rgb(76, 86, 106),
            success=AnsiCode.rgb(163, 190, 140),
            error=AnsiCode.rgb(191, 97, 106),
            info=AnsiCode.rgb(129, 161, 193),
        )
    
    @classmethod
    def _solarized_dark_theme(cls) -> 'ColorScheme':
        """Tema Solarized Dark"""
        return cls(
            primary=AnsiCode.rgb(38, 139, 210),  # Blue
            secondary=AnsiCode.rgb(253, 246, 227),  # Base3
            accent=AnsiCode.rgb(42, 161, 152),  # Cyan
            
            h1=AnsiCode.rgb(203, 75, 22),  # Orange
            h2=AnsiCode.rgb(253, 246, 227),
            h3=AnsiCode.rgb(38, 139, 210),
            h4=AnsiCode.rgb(181, 137, 0),  # Yellow
            h5=AnsiCode.rgb(211, 54, 130),  # Magenta
            h6=AnsiCode.rgb(88, 110, 117),  # Base01
            
            text=AnsiCode.rgb(253, 246, 227),
            text_dim=AnsiCode.rgb(88, 110, 117),
            text_bold=AnsiCode.BOLD,
            text_italic=AnsiCode.ITALIC,
            
            code_bg=AnsiCode.bg_rgb(0, 43, 54),
            code_text=AnsiCode.rgb(253, 246, 227),
            code_keyword=AnsiCode.rgb(133, 153, 0),  # Green
            code_string=AnsiCode.rgb(42, 161, 152),
            code_number=AnsiCode.rgb(211, 54, 130),
            code_comment=AnsiCode.rgb(88, 110, 117),
            code_function=AnsiCode.rgb(38, 139, 210),
            code_class=AnsiCode.rgb(181, 137, 0),
            code_variable=AnsiCode.rgb(253, 246, 227),
            code_operator=AnsiCode.rgb(133, 153, 0),
            code_punctuation=AnsiCode.rgb(147, 161, 161),
            
            link=AnsiCode.rgb(38, 139, 210) + AnsiCode.UNDERLINE,
            link_visited=AnsiCode.rgb(108, 113, 196) + AnsiCode.UNDERLINE,
            
            bullet=AnsiCode.rgb(203, 75, 22),
            bullet_secondary=AnsiCode.rgb(88, 110, 117),
            number=AnsiCode.rgb(38, 139, 210),
            checkbox_done=AnsiCode.rgb(133, 153, 0),
            checkbox_pending=AnsiCode.rgb(88, 110, 117),
            
            quote=AnsiCode.ITALIC + AnsiCode.rgb(88, 110, 117),
            quote_border=AnsiCode.rgb(38, 139, 210),
            
            table_border=AnsiCode.rgb(88, 110, 117),
            table_header=AnsiCode.BOLD + AnsiCode.rgb(253, 246, 227),
            table_row_odd="",
            table_row_even=AnsiCode.DIM,
            
            alert_note=AnsiCode.rgb(38, 139, 210),
            alert_tip=AnsiCode.rgb(133, 153, 0),
            alert_important=AnsiCode.rgb(108, 113, 196),
            alert_warning=AnsiCode.rgb(181, 137, 0),
            alert_caution=AnsiCode.rgb(220, 50, 47),
            
            hr=AnsiCode.rgb(88, 110, 117),
            border=AnsiCode.rgb(88, 110, 117),
            success=AnsiCode.rgb(133, 153, 0),
            error=AnsiCode.rgb(220, 50, 47),
            info=AnsiCode.rgb(38, 139, 210),
        )
    
    @classmethod
    def _gruvbox_theme(cls) -> 'ColorScheme':
        """Tema Gruvbox Dark"""
        return cls(
            primary=AnsiCode.rgb(214, 93, 14),  # Orange
            secondary=AnsiCode.rgb(235, 219, 178),  # fg
            accent=AnsiCode.rgb(69, 133, 136),  # Aqua
            
            h1=AnsiCode.rgb(251, 73, 52),  # Red
            h2=AnsiCode.rgb(235, 219, 178),
            h3=AnsiCode.rgb(131, 165, 152),  # Aqua
            h4=AnsiCode.rgb(250, 189, 47),  # Yellow
            h5=AnsiCode.rgb(211, 134, 155),  # Purple
            h6=AnsiCode.rgb(146, 131, 116),  # Gray
            
            text=AnsiCode.rgb(235, 219, 178),
            text_dim=AnsiCode.rgb(146, 131, 116),
            text_bold=AnsiCode.BOLD,
            text_italic=AnsiCode.ITALIC,
            
            code_bg=AnsiCode.bg_rgb(40, 40, 40),
            code_text=AnsiCode.rgb(235, 219, 178),
            code_keyword=AnsiCode.rgb(251, 73, 52),
            code_string=AnsiCode.rgb(184, 187, 38),  # Green
            code_number=AnsiCode.rgb(211, 134, 155),
            code_comment=AnsiCode.rgb(146, 131, 116),
            code_function=AnsiCode.rgb(131, 165, 152),
            code_class=AnsiCode.rgb(250, 189, 47),
            code_variable=AnsiCode.rgb(235, 219, 178),
            code_operator=AnsiCode.rgb(254, 128, 25),
            code_punctuation=AnsiCode.rgb(168, 153, 132),
            
            link=AnsiCode.rgb(131, 165, 152) + AnsiCode.UNDERLINE,
            link_visited=AnsiCode.rgb(211, 134, 155) + AnsiCode.UNDERLINE,
            
            bullet=AnsiCode.rgb(214, 93, 14),
            bullet_secondary=AnsiCode.rgb(146, 131, 116),
            number=AnsiCode.rgb(131, 165, 152),
            checkbox_done=AnsiCode.rgb(184, 187, 38),
            checkbox_pending=AnsiCode.rgb(146, 131, 116),
            
            quote=AnsiCode.ITALIC + AnsiCode.rgb(146, 131, 116),
            quote_border=AnsiCode.rgb(214, 93, 14),
            
            table_border=AnsiCode.rgb(146, 131, 116),
            table_header=AnsiCode.BOLD + AnsiCode.rgb(235, 219, 178),
            table_row_odd="",
            table_row_even=AnsiCode.DIM,
            
            alert_note=AnsiCode.rgb(131, 165, 152),
            alert_tip=AnsiCode.rgb(184, 187, 38),
            alert_important=AnsiCode.rgb(211, 134, 155),
            alert_warning=AnsiCode.rgb(250, 189, 47),
            alert_caution=AnsiCode.rgb(251, 73, 52),
            
            hr=AnsiCode.rgb(146, 131, 116),
            border=AnsiCode.rgb(146, 131, 116),
            success=AnsiCode.rgb(184, 187, 38),
            error=AnsiCode.rgb(251, 73, 52),
            info=AnsiCode.rgb(131, 165, 152),
        )
    
    @classmethod
    def _one_dark_theme(cls) -> 'ColorScheme':
        """Tema One Dark (Atom)"""
        return cls(
            primary=AnsiCode.rgb(97, 175, 239),  # Blue
            secondary=AnsiCode.rgb(171, 178, 191),  # fg
            accent=AnsiCode.rgb(86, 182, 194),  # Cyan
            
            h1=AnsiCode.rgb(224, 108, 117),  # Red
            h2=AnsiCode.rgb(171, 178, 191),
            h3=AnsiCode.rgb(97, 175, 239),
            h4=AnsiCode.rgb(229, 192, 123),  # Yellow
            h5=AnsiCode.rgb(198, 120, 221),  # Purple
            h6=AnsiCode.rgb(92, 99, 112),  # Comment
            
            text=AnsiCode.rgb(171, 178, 191),
            text_dim=AnsiCode.rgb(92, 99, 112),
            text_bold=AnsiCode.BOLD,
            text_italic=AnsiCode.ITALIC,
            
            code_bg=AnsiCode.bg_rgb(40, 44, 52),
            code_text=AnsiCode.rgb(171, 178, 191),
            code_keyword=AnsiCode.rgb(198, 120, 221),
            code_string=AnsiCode.rgb(152, 195, 121),  # Green
            code_number=AnsiCode.rgb(209, 154, 102),  # Orange
            code_comment=AnsiCode.rgb(92, 99, 112),
            code_function=AnsiCode.rgb(97, 175, 239),
            code_class=AnsiCode.rgb(229, 192, 123),
            code_variable=AnsiCode.rgb(224, 108, 117),
            code_operator=AnsiCode.rgb(86, 182, 194),
            code_punctuation=AnsiCode.rgb(171, 178, 191),
            
            link=AnsiCode.rgb(97, 175, 239) + AnsiCode.UNDERLINE,
            link_visited=AnsiCode.rgb(198, 120, 221) + AnsiCode.UNDERLINE,
            
            bullet=AnsiCode.rgb(224, 108, 117),
            bullet_secondary=AnsiCode.rgb(92, 99, 112),
            number=AnsiCode.rgb(97, 175, 239),
            checkbox_done=AnsiCode.rgb(152, 195, 121),
            checkbox_pending=AnsiCode.rgb(92, 99, 112),
            
            quote=AnsiCode.ITALIC + AnsiCode.rgb(92, 99, 112),
            quote_border=AnsiCode.rgb(97, 175, 239),
            
            table_border=AnsiCode.rgb(92, 99, 112),
            table_header=AnsiCode.BOLD + AnsiCode.rgb(171, 178, 191),
            table_row_odd="",
            table_row_even=AnsiCode.DIM,
            
            alert_note=AnsiCode.rgb(97, 175, 239),
            alert_tip=AnsiCode.rgb(152, 195, 121),
            alert_important=AnsiCode.rgb(198, 120, 221),
            alert_warning=AnsiCode.rgb(229, 192, 123),
            alert_caution=AnsiCode.rgb(224, 108, 117),
            
            hr=AnsiCode.rgb(92, 99, 112),
            border=AnsiCode.rgb(92, 99, 112),
            success=AnsiCode.rgb(152, 195, 121),
            error=AnsiCode.rgb(224, 108, 117),
            info=AnsiCode.rgb(97, 175, 239),
        )
    
    @classmethod
    def _github_dark_theme(cls) -> 'ColorScheme':
        """Tema GitHub Dark"""
        return cls(
            primary=AnsiCode.rgb(88, 166, 255),  # Blue
            secondary=AnsiCode.rgb(230, 237, 243),  # fg
            accent=AnsiCode.rgb(57, 211, 83),  # Green
            
            h1=AnsiCode.rgb(88, 166, 255),
            h2=AnsiCode.rgb(230, 237, 243),
            h3=AnsiCode.rgb(121, 192, 255),
            h4=AnsiCode.rgb(210, 168, 255),
            h5=AnsiCode.rgb(255, 166, 87),
            h6=AnsiCode.rgb(139, 148, 158),
            
            text=AnsiCode.rgb(230, 237, 243),
            text_dim=AnsiCode.rgb(139, 148, 158),
            text_bold=AnsiCode.BOLD,
            text_italic=AnsiCode.ITALIC,
            
            code_bg=AnsiCode.bg_rgb(22, 27, 34),
            code_text=AnsiCode.rgb(230, 237, 243),
            code_keyword=AnsiCode.rgb(255, 123, 114),
            code_string=AnsiCode.rgb(165, 214, 255),
            code_number=AnsiCode.rgb(121, 192, 255),
            code_comment=AnsiCode.rgb(139, 148, 158),
            code_function=AnsiCode.rgb(210, 168, 255),
            code_class=AnsiCode.rgb(255, 166, 87),
            code_variable=AnsiCode.rgb(121, 192, 255),
            code_operator=AnsiCode.rgb(255, 123, 114),
            code_punctuation=AnsiCode.rgb(230, 237, 243),
            
            link=AnsiCode.rgb(88, 166, 255) + AnsiCode.UNDERLINE,
            link_visited=AnsiCode.rgb(210, 168, 255) + AnsiCode.UNDERLINE,
            
            bullet=AnsiCode.rgb(88, 166, 255),
            bullet_secondary=AnsiCode.rgb(139, 148, 158),
            number=AnsiCode.rgb(121, 192, 255),
            checkbox_done=AnsiCode.rgb(57, 211, 83),
            checkbox_pending=AnsiCode.rgb(139, 148, 158),
            
            quote=AnsiCode.ITALIC + AnsiCode.rgb(139, 148, 158),
            quote_border=AnsiCode.rgb(88, 166, 255),
            
            table_border=AnsiCode.rgb(48, 54, 61),
            table_header=AnsiCode.BOLD + AnsiCode.rgb(230, 237, 243),
            table_row_odd="",
            table_row_even=AnsiCode.DIM,
            
            alert_note=AnsiCode.rgb(88, 166, 255),
            alert_tip=AnsiCode.rgb(57, 211, 83),
            alert_important=AnsiCode.rgb(210, 168, 255),
            alert_warning=AnsiCode.rgb(210, 153, 34),
            alert_caution=AnsiCode.rgb(248, 81, 73),
            
            hr=AnsiCode.rgb(48, 54, 61),
            border=AnsiCode.rgb(48, 54, 61),
            success=AnsiCode.rgb(57, 211, 83),
            error=AnsiCode.rgb(248, 81, 73),
            info=AnsiCode.rgb(88, 166, 255),
        )
    
    @classmethod
    def _catppuccin_theme(cls) -> 'ColorScheme':
        """Tema Catppuccin Mocha"""
        return cls(
            primary=AnsiCode.rgb(203, 166, 247),  # Mauve
            secondary=AnsiCode.rgb(205, 214, 244),  # Text
            accent=AnsiCode.rgb(137, 220, 235),  # Sky
            
            h1=AnsiCode.rgb(243, 139, 168),  # Red
            h2=AnsiCode.rgb(205, 214, 244),
            h3=AnsiCode.rgb(137, 220, 235),
            h4=AnsiCode.rgb(249, 226, 175),  # Yellow
            h5=AnsiCode.rgb(203, 166, 247),
            h6=AnsiCode.rgb(108, 112, 134),  # Overlay0
            
            text=AnsiCode.rgb(205, 214, 244),
            text_dim=AnsiCode.rgb(108, 112, 134),
            text_bold=AnsiCode.BOLD,
            text_italic=AnsiCode.ITALIC,
            
            code_bg=AnsiCode.bg_rgb(30, 30, 46),
            code_text=AnsiCode.rgb(205, 214, 244),
            code_keyword=AnsiCode.rgb(203, 166, 247),
            code_string=AnsiCode.rgb(166, 227, 161),  # Green
            code_number=AnsiCode.rgb(250, 179, 135),  # Peach
            code_comment=AnsiCode.rgb(108, 112, 134),
            code_function=AnsiCode.rgb(137, 180, 250),  # Blue
            code_class=AnsiCode.rgb(249, 226, 175),
            code_variable=AnsiCode.rgb(243, 139, 168),
            code_operator=AnsiCode.rgb(137, 220, 235),
            code_punctuation=AnsiCode.rgb(166, 173, 200),
            
            link=AnsiCode.rgb(137, 180, 250) + AnsiCode.UNDERLINE,
            link_visited=AnsiCode.rgb(203, 166, 247) + AnsiCode.UNDERLINE,
            
            bullet=AnsiCode.rgb(243, 139, 168),
            bullet_secondary=AnsiCode.rgb(108, 112, 134),
            number=AnsiCode.rgb(137, 180, 250),
            checkbox_done=AnsiCode.rgb(166, 227, 161),
            checkbox_pending=AnsiCode.rgb(108, 112, 134),
            
            quote=AnsiCode.ITALIC + AnsiCode.rgb(108, 112, 134),
            quote_border=AnsiCode.rgb(203, 166, 247),
            
            table_border=AnsiCode.rgb(69, 71, 90),
            table_header=AnsiCode.BOLD + AnsiCode.rgb(205, 214, 244),
            table_row_odd="",
            table_row_even=AnsiCode.DIM,
            
            alert_note=AnsiCode.rgb(137, 180, 250),
            alert_tip=AnsiCode.rgb(166, 227, 161),
            alert_important=AnsiCode.rgb(203, 166, 247),
            alert_warning=AnsiCode.rgb(249, 226, 175),
            alert_caution=AnsiCode.rgb(243, 139, 168),
            
            hr=AnsiCode.rgb(69, 71, 90),
            border=AnsiCode.rgb(69, 71, 90),
            success=AnsiCode.rgb(166, 227, 161),
            error=AnsiCode.rgb(243, 139, 168),
            info=AnsiCode.rgb(137, 180, 250),
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2: UTILIDADES Y HELPERS
# ══════════════════════════════════════════════════════════════════════════════

class BoxChars:
    """Caracteres Unicode para dibujar cajas y bordes"""
    
    # Líneas simples
    H = "─"      # Horizontal
    V = "│"      # Vertical
    TL = "┌"     # Top-left
    TR = "┐"     # Top-right
    BL = "└"     # Bottom-left
    BR = "┘"     # Bottom-right
    LT = "├"     # Left-tee
    RT = "┤"     # Right-tee
    TT = "┬"     # Top-tee
    BT = "┴"     # Bottom-tee
    CR = "┼"     # Cross
    
    # Líneas dobles
    DH = "═"     # Double horizontal
    DV = "║"     # Double vertical
    DTL = "╔"    # Double top-left
    DTR = "╗"    # Double top-right
    DBL = "╚"    # Double bottom-left
    DBR = "╝"    # Double bottom-right
    DLT = "╠"    # Double left-tee
    DRT = "╣"    # Double right-tee
    DTT = "╦"    # Double top-tee
    DBT = "╩"    # Double bottom-tee
    DCR = "╬"    # Double cross
    
    # Líneas gruesas
    TH = "━"     # Thick horizontal
    TV = "┃"     # Thick vertical
    TTL = "┏"    # Thick top-left
    TTR = "┓"    # Thick top-right
    TBL = "┗"    # Thick bottom-left
    TBR = "┛"    # Thick bottom-right
    
    # Líneas redondeadas
    RTL = "╭"    # Rounded top-left
    RTR = "╮"    # Rounded top-right
    RBL = "╰"    # Rounded bottom-left
    RBR = "╯"    # Rounded bottom-right
    
    # Líneas punteadas
    DH2 = "╌"    # Dashed horizontal (2)
    DH3 = "┄"    # Dashed horizontal (3)
    DH4 = "┈"    # Dashed horizontal (4)
    DV2 = "╎"    # Dashed vertical (2)
    DV3 = "┆"    # Dashed vertical (3)
    DV4 = "┊"    # Dashed vertical (4)
    
    # Bloques
    FULL = "█"
    DARK = "▓"
    MEDIUM = "▒"
    LIGHT = "░"
    
    # Medios bloques
    UPPER_HALF = "▀"
    LOWER_HALF = "▄"
    LEFT_HALF = "▌"
    RIGHT_HALF = "▐"
    
    # Cuartos
    UPPER_LEFT = "▘"
    UPPER_RIGHT = "▝"
    LOWER_LEFT = "▖"
    LOWER_RIGHT = "▗"
    
    # Flechas
    ARROW_RIGHT = "→"
    ARROW_LEFT = "←"
    ARROW_UP = "↑"
    ARROW_DOWN = "↓"
    ARROW_RIGHT_DOUBLE = "⇒"
    ARROW_LEFT_DOUBLE = "⇐"
    
    # Bullets
    BULLET = "•"
    BULLET_HOLLOW = "◦"
    BULLET_TRIANGLE = "‣"
    DIAMOND = "◆"
    DIAMOND_HOLLOW = "◇"
    SQUARE = "■"
    SQUARE_HOLLOW = "□"
    CIRCLE = "●"
    CIRCLE_HOLLOW = "○"
    STAR = "★"
    STAR_HOLLOW = "☆"
    
    # Checkboxes
    CHECK = "✓"
    CHECK_HEAVY = "✔"
    CROSS = "✗"
    CROSS_HEAVY = "✘"
    CHECKBOX_EMPTY = "☐"
    CHECKBOX_CHECKED = "☑"
    CHECKBOX_CROSSED = "☒"


class Icons:
    """Iconos Unicode para diferentes tipos de contenido"""
    
    # Archivos y carpetas
    FILE = "📄"
    FOLDER = "📁"
    FOLDER_OPEN = "📂"
    
    # Lenguajes de programación
    PYTHON = "🐍"
    JAVASCRIPT = "🟨"
    TYPESCRIPT = "🔷"
    RUST = "🦀"
    GO = "🐹"
    JAVA = "☕"
    RUBY = "💎"
    PHP = "🐘"
    SWIFT = "🍎"
    KOTLIN = "🅺"
    
    # Tecnologías
    DOCKER = "🐳"
    GIT = "📦"
    DATABASE = "🗄️"
    TERMINAL = "💻"
    CODE = "📝"
    CONFIG = "⚙️"
    
    # Estados
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    QUESTION = "❓"
    
    # Alertas
    NOTE = "📝"
    TIP = "💡"
    IMPORTANT = "📌"
    CAUTION = "🚫"
    
    # Misc
    LINK = "🔗"
    IMAGE = "🖼️"
    VIDEO = "🎬"
    AUDIO = "🎵"
    BOOK = "📚"
    CHART = "📊"
    GRAPH = "📈"
    TABLE = "📋"
    CLOCK = "🕐"
    CALENDAR = "📅"
    STAR = "⭐"
    FIRE = "🔥"
    ROCKET = "🚀"
    SPARKLES = "✨"
    ZAP = "⚡"
    HEART = "❤️"
    THUMBS_UP = "👍"
    THUMBS_DOWN = "👎"
    EYES = "👀"
    BRAIN = "🧠"
    LIGHT_BULB = "💡"
    WRENCH = "🔧"
    HAMMER = "🔨"
    KEY = "🔑"
    LOCK = "🔒"
    UNLOCK = "🔓"
    SHIELD = "🛡️"
    BUG = "🐛"
    MEMO = "📝"
    PENCIL = "✏️"
    MAGNIFIER = "🔍"
    PACKAGE = "📦"


class TextUtils:
    """Utilidades para manipulación de texto"""
    
    # Mapas de conversión para subíndices y superíndices
    SUB_MAP = str.maketrans("0123456789+-=()aehijklmnoprstuvx", 
                            "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")
    
    SUP_MAP = str.maketrans("0123456789+-=()abcdefghijklmnoprstuvwxyzABDEGHIJKLMNOPRTUVW",
                            "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂ")
    
    # Regex compilados para mejor rendimiento
    ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "]+", 
        flags=re.UNICODE
    )
    
    @classmethod
    def strip_ansi(cls, text: str) -> str:
        """Elimina códigos ANSI de escape del texto"""
        return cls.ANSI_ESCAPE.sub('', text)
    
    @classmethod
    def visible_length(cls, text: str) -> int:
        """Calcula la longitud visible del texto (sin códigos ANSI)"""
        clean = cls.strip_ansi(text)
        # Considerar caracteres de ancho doble (CJK, emojis, etc.)
        width = 0
        for char in clean:
            if unicodedata.east_asian_width(char) in ('F', 'W'):
                width += 2
            else:
                width += 1
        return width
    
    @classmethod
    def pad_visible(cls, text: str, width: int, align: str = 'left', fill: str = ' ') -> str:
        """Rellena el texto hasta un ancho visible específico"""
        visible_len = cls.visible_length(text)
        padding = max(0, width - visible_len)
        
        if align == 'left':
            return text + fill * padding
        elif align == 'right':
            return fill * padding + text
        elif align == 'center':
            left_pad = padding // 2
            right_pad = padding - left_pad
            return fill * left_pad + text + fill * right_pad
        return text
    
    @classmethod
    def truncate(cls, text: str, max_width: int, suffix: str = '…') -> str:
        """Trunca el texto a un ancho máximo preservando códigos ANSI"""
        if cls.visible_length(text) <= max_width:
            return text
        
        # Necesitamos truncar preservando los códigos ANSI
        result = []
        visible_count = 0
        suffix_len = cls.visible_length(suffix)
        target_width = max_width - suffix_len
        
        i = 0
        while i < len(text) and visible_count < target_width:
            if text[i] == '\x1b':
                # Inicio de secuencia ANSI
                end = text.find('m', i)
                if end != -1:
                    result.append(text[i:end+1])
                    i = end + 1
                    continue
            
            char_width = 2 if unicodedata.east_asian_width(text[i]) in ('F', 'W') else 1
            if visible_count + char_width <= target_width:
                result.append(text[i])
                visible_count += char_width
            i += 1
        
        return ''.join(result) + suffix + AnsiCode.RESET
    
    @classmethod
    def word_wrap(cls, text: str, width: int, indent: str = '', 
                  first_indent: str = None) -> List[str]:
        """Envuelve el texto en líneas de ancho máximo"""
        if first_indent is None:
            first_indent = indent
        
        words = text.split()
        lines = []
        current_line = []
        current_width = 0
        is_first = True
        current_indent = first_indent
        
        for word in words:
            word_width = cls.visible_length(word)
            indent_width = cls.visible_length(current_indent)
            
            if current_width + word_width + (1 if current_line else 0) + indent_width <= width:
                current_line.append(word)
                current_width += word_width + (1 if len(current_line) > 1 else 0)
            else:
                if current_line:
                    lines.append(current_indent + ' '.join(current_line))
                current_line = [word]
                current_width = word_width
                is_first = False
                current_indent = indent
        
        if current_line:
            lines.append(current_indent + ' '.join(current_line))
        
        return lines if lines else [first_indent]
    
    @classmethod
    def to_subscript(cls, text: str) -> str:
        """Convierte texto a subíndice"""
        return text.translate(cls.SUB_MAP)
    
    @classmethod
    def to_superscript(cls, text: str) -> str:
        """Convierte texto a superíndice"""
        return text.translate(cls.SUP_MAP)
    
    @classmethod
    def create_progress_bar(cls, progress: float, width: int = 20, 
                           filled: str = '█', empty: str = '░',
                           show_percentage: bool = True) -> str:
        """Crea una barra de progreso visual"""
        progress = max(0, min(1, progress))
        filled_width = int(progress * width)
        empty_width = width - filled_width
        
        bar = filled * filled_width + empty * empty_width
        
        if show_percentage:
            return f"[{bar}] {progress*100:.1f}%"
        return f"[{bar}]"
    
    @classmethod
    def create_sparkline(cls, values: List[float], width: int = None) -> str:
        """Crea un sparkline (mini gráfico de línea)"""
        if not values:
            return ""
        
        chars = '▁▂▃▄▅▆▇█'
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            return chars[3] * len(values)
        
        result = []
        for val in values:
            normalized = (val - min_val) / (max_val - min_val)
            index = int(normalized * (len(chars) - 1))
            result.append(chars[index])
        
        return ''.join(result)


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3: MAPEO DE EMOJIS (Shortcodes)
# ══════════════════════════════════════════════════════════════════════════════

EMOJI_MAP: Dict[str, str] = {
    # Caras y emociones
    "smile": "😊", "grin": "😁", "joy": "😂", "rofl": "🤣", "wink": "😉",
    "blush": "😊", "heart_eyes": "😍", "kissing": "😗", "thinking": "🤔",
    "neutral": "😐", "expressionless": "😑", "unamused": "😒", "sweat": "😓",
    "pensive": "😔", "confused": "😕", "upside_down": "🙃", "money_face": "🤑",
    "astonished": "😲", "flushed": "😳", "scream": "😱", "fearful": "😨",
    "cold_sweat": "😰", "cry": "😢", "sob": "😭", "angry": "😠", "rage": "😡",
    "triumph": "😤", "sleepy": "😪", "drool": "🤤", "sleeping": "😴",
    "mask": "😷", "nerd": "🤓", "sunglasses": "😎", "cowboy": "🤠",
    "clown": "🤡", "devil": "😈", "skull": "💀", "ghost": "👻",
    "alien": "👽", "robot": "🤖", "poop": "💩", "cat": "😺", "dog": "🐶",
    
    # Gestos
    "wave": "👋", "raised_hand": "✋", "ok_hand": "👌", "pinching": "🤏",
    "victory": "✌️", "crossed_fingers": "🤞", "love_you": "🤟", "rock": "🤘",
    "call_me": "🤙", "point_left": "👈", "point_right": "👉", "point_up": "👆",
    "point_down": "👇", "middle_finger": "🖕", "thumbsup": "👍", "+1": "👍",
    "thumbsdown": "👎", "-1": "👎", "fist": "✊", "punch": "👊",
    "clap": "👏", "raised_hands": "🙌", "open_hands": "👐", "palms_up": "🤲",
    "handshake": "🤝", "pray": "🙏", "muscle": "💪", "brain": "🧠",
    
    # Corazones
    "heart": "❤️", "red_heart": "❤️", "orange_heart": "🧡", "yellow_heart": "💛",
    "green_heart": "💚", "blue_heart": "💙", "purple_heart": "💜",
    "black_heart": "🖤", "white_heart": "🤍", "brown_heart": "🤎",
    "broken_heart": "💔", "sparkling_heart": "💖", "heartbeat": "💓",
    "two_hearts": "💕", "revolving_hearts": "💞", "heart_decoration": "💟",
    
    # Símbolos
    "check": "✅", "checkmark": "✓", "x": "❌", "cross": "❌",
    "warning": "⚠️", "exclamation": "❗", "question": "❓",
    "info": "ℹ️", "copyright": "©️", "registered": "®️", "tm": "™️",
    "star": "⭐", "star2": "🌟", "sparkles": "✨", "zap": "⚡",
    "fire": "🔥", "boom": "💥", "collision": "💥", "droplet": "💧",
    "100": "💯", "money": "💰", "dollar": "💵", "euro": "💶",
    
    # Naturaleza
    "sun": "☀️", "moon": "🌙", "cloud": "☁️", "rain": "🌧️", "snow": "❄️",
    "rainbow": "🌈", "umbrella": "☂️", "thunder": "⛈️", "tornado": "🌪️",
    "flower": "🌸", "rose": "🌹", "tulip": "🌷", "sunflower": "🌻",
    "tree": "🌳", "palm": "🌴", "cactus": "🌵", "leaf": "🍃",
    "earth": "🌍", "globe": "🌐", "mountain": "⛰️", "volcano": "🌋",
    
    # Animales
    "monkey": "🐵", "gorilla": "🦍", "dog": "🐶", "wolf": "🐺",
    "fox": "🦊", "cat": "🐱", "lion": "🦁", "tiger": "🐯",
    "horse": "🐴", "unicorn": "🦄", "cow": "🐮", "pig": "🐷",
    "mouse": "🐭", "rabbit": "🐰", "bear": "🐻", "panda": "🐼",
    "chicken": "🐔", "penguin": "🐧", "bird": "🐦", "eagle": "🦅",
    "duck": "🦆", "owl": "🦉", "frog": "🐸", "snake": "🐍",
    "dragon": "🐉", "whale": "🐳", "dolphin": "🐬", "fish": "🐟",
    "octopus": "🐙", "crab": "🦀", "shrimp": "🦐", "bug": "🐛",
    "butterfly": "🦋", "bee": "🐝", "ant": "🐜", "spider": "🕷️",
    
    # Comida
    "apple": "🍎", "green_apple": "🍏", "pear": "🍐", "orange": "🍊",
    "lemon": "🍋", "banana": "🍌", "watermelon": "🍉", "grapes": "🍇",
    "strawberry": "🍓", "cherry": "🍒", "peach": "🍑", "mango": "🥭",
    "pizza": "🍕", "burger": "🍔", "fries": "🍟", "hotdog": "🌭",
    "sandwich": "🥪", "taco": "🌮", "burrito": "🌯", "egg": "🥚",
    "coffee": "☕", "tea": "🍵", "beer": "🍺", "wine": "🍷",
    "cocktail": "🍸", "cake": "🎂", "cookie": "🍪", "chocolate": "🍫",
    "candy": "🍬", "icecream": "🍦", "donut": "🍩", "popcorn": "🍿",
    
    # Objetos
    "phone": "📱", "computer": "💻", "keyboard": "⌨️", "mouse_computer": "🖱️",
    "printer": "🖨️", "camera": "📷", "video": "📹", "tv": "📺",
    "radio": "📻", "headphones": "🎧", "microphone": "🎤", "guitar": "🎸",
    "piano": "🎹", "trumpet": "🎺", "drum": "🥁", "clapper": "🎬",
    "book": "📚", "notebook": "📓", "newspaper": "📰", "pencil": "✏️",
    "pen": "🖊️", "scissors": "✂️", "paperclip": "📎", "pushpin": "📌",
    "calendar": "📅", "clock": "🕐", "hourglass": "⏳", "alarm": "⏰",
    "key": "🔑", "lock": "🔒", "unlock": "🔓", "hammer": "🔨",
    "wrench": "🔧", "gear": "⚙️", "magnet": "🧲", "link": "🔗",
    "bulb": "💡", "flashlight": "🔦", "candle": "🕯️", "bomb": "💣",
    "gun": "🔫", "pill": "💊", "syringe": "💉", "dna": "🧬",
    
    # Transporte
    "car": "🚗", "taxi": "🚕", "bus": "🚌", "ambulance": "🚑",
    "truck": "🚚", "train": "🚆", "metro": "🚇", "tram": "🚊",
    "bike": "🚲", "scooter": "🛴", "motorcycle": "🏍️", "airplane": "✈️",
    "helicopter": "🚁", "rocket": "🚀", "ship": "🚢", "boat": "⛵",
    "anchor": "⚓", "fuel": "⛽", "traffic_light": "🚦", "construction": "🚧",
    
    # Lugares
    "house": "🏠", "office": "🏢", "hospital": "🏥", "bank": "🏦",
    "hotel": "🏨", "school": "🏫", "church": "⛪", "mosque": "🕌",
    "temple": "🛕", "castle": "🏰", "stadium": "🏟️", "tent": "⛺",
    "factory": "🏭", "store": "🏪", "fountain": "⛲", "bridge": "🌉",
    
    # Deportes
    "soccer": "⚽", "basketball": "🏀", "football": "🏈", "baseball": "⚾",
    "tennis": "🎾", "volleyball": "🏐", "rugby": "🏉", "pool": "🎱",
    "golf": "⛳", "hockey": "🏒", "cricket": "🏏", "badminton": "🏸",
    "boxing": "🥊", "martial_arts": "🥋", "goal": "🥅", "ski": "⛷️",
    "snowboard": "🏂", "skate": "⛸️", "fishing": "🎣", "diving": "🤿",
    "swimming": "🏊", "surfing": "🏄", "medal": "🏅", "trophy": "🏆",
    
    # Banderas (algunas)
    "flag_us": "🇺🇸", "flag_gb": "🇬🇧", "flag_de": "🇩🇪", "flag_fr": "🇫🇷",
    "flag_es": "🇪🇸", "flag_it": "🇮🇹", "flag_jp": "🇯🇵", "flag_cn": "🇨🇳",
    "flag_kr": "🇰🇷", "flag_br": "🇧🇷", "flag_mx": "🇲🇽", "flag_ca": "🇨🇦",
    "flag_au": "🇦🇺", "flag_ru": "🇷🇺", "flag_in": "🇮🇳", "rainbow_flag": "🏳️‍🌈",
    
    # Tecnología/Dev
    "octocat": "🐙", "github": "🐙", "python": "🐍", "java": "☕",
    "ruby": "💎", "rust": "🦀", "go": "🐹", "docker": "🐳",
    "linux": "🐧", "terminal": "💻", "database": "🗄️", "api": "🔌",
    "debug": "🐛", "deploy": "🚀", "merge": "🔀", "branch": "🌿",
    "commit": "📝", "push": "⬆️", "pull": "⬇️", "sync": "🔄",
}


def replace_emoji_shortcodes(text: str) -> str:
    """Reemplaza shortcodes de emoji :name: por el emoji real"""
    def replace(match):
        code = match.group(1).lower()
        return EMOJI_MAP.get(code, match.group(0))
    
    return re.sub(r':([a-zA-Z0-9_+-]+):', replace, text)


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4: PATRONES REGEX COMPILADOS
# ══════════════════════════════════════════════════════════════════════════════

class Patterns:
    """Patrones regex compilados para mejor rendimiento"""
    
    # Bloques
    CODE_FENCE = re.compile(r'^(`{3,}|~{3,})(\w*)?(.*)$')
    MATH_BLOCK = re.compile(r'^\$\$$')
    HEADER = re.compile(r'^(#{1,6})\s+(.+)$')
    HEADER_ALT_H1 = re.compile(r'^=+$')
    HEADER_ALT_H2 = re.compile(r'^-+$')
    HR = re.compile(r'^(\s*[-*_]\s*){3,}$')
    BLOCKQUOTE = re.compile(r'^(\s*>)+\s*(.*)$')
    
    # Listas
    UNORDERED_LIST = re.compile(r'^(\s*)([-*+])\s+(.*)$')
    ORDERED_LIST = re.compile(r'^(\s*)(\d+)(\.|\))\s+(.*)$')
    TASK_LIST = re.compile(r'^(\s*)([-*+])\s+\[([ xX])\]\s+(.*)$')
    DEFINITION_LIST = re.compile(r'^:\s+(.*)$')
    
    # Tablas
    TABLE_ROW = re.compile(r'^\|(.+)\|$')
    TABLE_SEPARATOR = re.compile(r'^[\s|:-]+$')
    TABLE_ALIGNMENT = re.compile(r'^(:)?-+(:)?$')
    
    # Inline
    INLINE_CODE = re.compile(r'`([^`]+)`')
    INLINE_MATH = re.compile(r'\$([^$]+)\$')
    BOLD_ITALIC = re.compile(r'(\*\*\*|___)(.+?)\1')
    BOLD = re.compile(r'(\*\*|__)(.+?)\1')
    ITALIC = re.compile(r'(?<![*_])(\*|_)(?![*_])(.+?)\1(?![*_])')
    STRIKETHROUGH = re.compile(r'~~(.+?)~~')
    UNDERLINE = re.compile(r'<u>(.+?)</u>', re.IGNORECASE)
    MARK = re.compile(r'<mark>(.+?)</mark>', re.IGNORECASE)
    SUPERSCRIPT = re.compile(r'<sup>(.+?)</sup>', re.IGNORECASE)
    SUBSCRIPT = re.compile(r'<sub>(.+?)</sub>', re.IGNORECASE)
    KBD = re.compile(r'<kbd>(.+?)</kbd>', re.IGNORECASE)
    INS = re.compile(r'<ins>(.+?)</ins>', re.IGNORECASE)
    DEL = re.compile(r'<del>(.+?)</del>', re.IGNORECASE)
    
    # Links e imágenes
    IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    LINK = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    LINK_REF = re.compile(r'\[([^\]]+)\]\[([^\]]*)\]')
    LINK_REF_DEF = re.compile(r'^\[([^\]]+)\]:\s*(.+)$')
    AUTOLINK = re.compile(r'<(https?://[^>]+)>')
    EMAIL_AUTOLINK = re.compile(r'<([^@>]+@[^>]+)>')
    
    # URLs automáticas (sin < >)
    URL_PLAIN = re.compile(r'(?<![(<])(https?://[^\s<>\[\]()]+)')
    
    # HTML tags
    HTML_COMMENT = re.compile(r'<!--.*?-->', re.DOTALL)
    HTML_TAG = re.compile(r'</?(\w+)(\s+[^>]*)?>') 
    HTML_ENTITY = re.compile(r'&(\w+|#\d+|#x[0-9a-fA-F]+);')
    
    # Escapes
    ESCAPE = re.compile(r'\\([\\`*_{}[\]()#+\-.!|>~])')
    
    # GitHub Alerts
    GH_ALERT = re.compile(r'^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]', re.IGNORECASE)
    
    # Footnotes
    FOOTNOTE_REF = re.compile(r'\[\^([^\]]+)\]')
    FOOTNOTE_DEF = re.compile(r'^\[\^([^\]]+)\]:\s*(.*)$')
    
    # Abbreviations
    ABBR_DEF = re.compile(r'^\*\[([^\]]+)\]:\s*(.+)$')
    
    # Emoji shortcodes
    EMOJI = re.compile(r':([a-zA-Z0-9_+-]+):')
    
    # Diff syntax
    DIFF_ADD = re.compile(r'^\+\s*(.*)$')
    DIFF_DEL = re.compile(r'^-\s*(.*)$')
    DIFF_CONTEXT = re.compile(r'^\s(.*)$')
    
    # Metadata (YAML frontmatter)
    FRONTMATTER = re.compile(r'^---\s*$')


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5: SYNTAX HIGHLIGHTER
# ══════════════════════════════════════════════════════════════════════════════

class SyntaxHighlighter:
    """Resaltador de sintaxis para múltiples lenguajes"""
    
    def __init__(self, scheme: ColorScheme):
        self.scheme = scheme
        self._init_languages()
    
    def _init_languages(self):
        """Inicializa los patrones de cada lenguaje"""
        self.languages = {
            'python': self._python_patterns(),
            'py': self._python_patterns(),
            'javascript': self._javascript_patterns(),
            'js': self._javascript_patterns(),
            'typescript': self._typescript_patterns(),
            'ts': self._typescript_patterns(),
            'java': self._java_patterns(),
            'c': self._c_patterns(),
            'cpp': self._cpp_patterns(),
            'c++': self._cpp_patterns(),
            'csharp': self._csharp_patterns(),
            'cs': self._csharp_patterns(),
            'go': self._go_patterns(),
            'golang': self._go_patterns(),
            'rust': self._rust_patterns(),
            'rs': self._rust_patterns(),
            'ruby': self._ruby_patterns(),
            'rb': self._ruby_patterns(),
            'php': self._php_patterns(),
            'swift': self._swift_patterns(),
            'kotlin': self._kotlin_patterns(),
            'kt': self._kotlin_patterns(),
            'scala': self._scala_patterns(),
            'bash': self._bash_patterns(),
            'sh': self._bash_patterns(),
            'shell': self._bash_patterns(),
            'zsh': self._bash_patterns(),
            'powershell': self._powershell_patterns(),
            'ps1': self._powershell_patterns(),
            'sql': self._sql_patterns(),
            'html': self._html_patterns(),
            'xml': self._xml_patterns(),
            'css': self._css_patterns(),
            'scss': self._scss_patterns(),
            'sass': self._scss_patterns(),
            'json': self._json_patterns(),
            'yaml': self._yaml_patterns(),
            'yml': self._yaml_patterns(),
            'toml': self._toml_patterns(),
            'ini': self._ini_patterns(),
            'markdown': self._markdown_patterns(),
            'md': self._markdown_patterns(),
            'dockerfile': self._dockerfile_patterns(),
            'docker': self._dockerfile_patterns(),
            'makefile': self._makefile_patterns(),
            'make': self._makefile_patterns(),
            'lua': self._lua_patterns(),
            'perl': self._perl_patterns(),
            'r': self._r_patterns(),
            'julia': self._julia_patterns(),
            'haskell': self._haskell_patterns(),
            'hs': self._haskell_patterns(),
            'elixir': self._elixir_patterns(),
            'ex': self._elixir_patterns(),
            'erlang': self._erlang_patterns(),
            'erl': self._erlang_patterns(),
            'clojure': self._clojure_patterns(),
            'clj': self._clojure_patterns(),
            'vim': self._vim_patterns(),
            'diff': self._diff_patterns(),
            'mermaid': self._mermaid_patterns(),
            'regex': self._regex_patterns(),
            're': self._regex_patterns(),
            'graphql': self._graphql_patterns(),
            'gql': self._graphql_patterns(),
            'terraform': self._terraform_patterns(),
            'tf': self._terraform_patterns(),
            'nginx': self._nginx_patterns(),
            'apache': self._apache_patterns(),
        }
    
    def highlight(self, code: str, language: str) -> str:
        """Resalta el código según el lenguaje"""
        lang = language.lower().strip()
        
        if lang not in self.languages:
            # Lenguaje no soportado, devolver con color genérico
            return f"{self.scheme.code_text}{code}{AnsiCode.RESET}"
        
        patterns = self.languages[lang]
        return self._apply_patterns(code, patterns)
    
    def _apply_patterns(self, code: str, patterns: List[Tuple[Pattern, str]]) -> str:
        """Aplica los patrones de resaltado al código"""
        # Tokenizar para evitar conflictos
        tokens = []
        remaining = code
        pos = 0
        
        while remaining:
            best_match = None
            best_pattern = None
            best_start = len(remaining)
            
            for pattern, color in patterns:
                match = pattern.search(remaining)
                if match and match.start() < best_start:
                    best_match = match
                    best_pattern = (pattern, color)
                    best_start = match.start()
            
            if best_match:
                # Añadir texto antes del match
                if best_start > 0:
                    tokens.append((remaining[:best_start], self.scheme.code_text))
                
                # Añadir el match resaltado
                tokens.append((best_match.group(0), best_pattern[1]))
                
                remaining = remaining[best_match.end():]
            else:
                # No más matches, añadir el resto
                tokens.append((remaining, self.scheme.code_text))
                break
        
        # Construir resultado
        result = []
        for text, color in tokens:
            result.append(f"{color}{text}")
        
        return ''.join(result) + AnsiCode.RESET
    
    # ─────────────────────────────────────────────────────────────────────────
    # Patrones por lenguaje
    # ─────────────────────────────────────────────────────────────────────────
    
    def _python_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            # Comentarios
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            # Strings triple-quoted
            (re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\''), self.scheme.code_string),
            # Strings
            (re.compile(r'f?r?["\'](?:[^"\'\\]|\\.)*["\']'), self.scheme.code_string),
            # Keywords
            (re.compile(r'\b(def|class|import|from|return|if|elif|else|for|while|'
                       r'try|except|finally|with|as|yield|lambda|pass|break|continue|'
                       r'raise|assert|global|nonlocal|del|in|is|and|or|not|True|False|'
                       r'None|async|await|match|case)\b'), self.scheme.code_keyword),
            # Decorators
            (re.compile(r'@\w+'), self.scheme.code_function),
            # Functions
            (re.compile(r'\b(\w+)(?=\s*\()'), self.scheme.code_function),
            # Numbers
            (re.compile(r'\b\d+\.?\d*([eE][+-]?\d+)?j?\b'), self.scheme.code_number),
            # Self
            (re.compile(r'\bself\b'), self.scheme.code_variable),
            # Builtins
            (re.compile(r'\b(print|len|range|str|int|float|list|dict|tuple|set|'
                       r'bool|type|isinstance|hasattr|getattr|setattr|open|'
                       r'input|map|filter|zip|enumerate|sorted|reversed|'
                       r'sum|min|max|abs|round|any|all)\b'), self.scheme.code_function),
        ]
    
    def _javascript_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            # Comentarios
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            # Template strings
            (re.compile(r'`[^`]*`'), self.scheme.code_string),
            # Strings
            (re.compile(r'["\'](?:[^"\'\\]|\\.)*["\']'), self.scheme.code_string),
            # Keywords
            (re.compile(r'\b(const|let|var|function|return|if|else|for|while|do|'
                       r'switch|case|break|continue|try|catch|finally|throw|'
                       r'class|extends|new|this|super|import|export|from|default|'
                       r'async|await|yield|typeof|instanceof|in|of|delete|void|'
                       r'true|false|null|undefined|NaN|Infinity)\b'), self.scheme.code_keyword),
            # Arrow functions
            (re.compile(r'=>'), self.scheme.code_operator),
            # Functions
            (re.compile(r'\b(\w+)(?=\s*\()'), self.scheme.code_function),
            # Numbers
            (re.compile(r'\b\d+\.?\d*([eE][+-]?\d+)?\b'), self.scheme.code_number),
            # Operators
            (re.compile(r'[+\-*/%=<>!&|^~?:]+'), self.scheme.code_operator),
        ]
    
    def _typescript_patterns(self) -> List[Tuple[Pattern, str]]:
        patterns = self._javascript_patterns()
        patterns.extend([
            # Types
            (re.compile(r'\b(string|number|boolean|void|any|never|unknown|'
                       r'interface|type|enum|namespace|module|declare|'
                       r'readonly|private|public|protected|static|abstract|'
                       r'implements|keyof|infer|as|is)\b'), self.scheme.code_keyword),
            # Type annotations
            (re.compile(r':\s*([A-Z]\w*(\[\])?(<[^>]+>)?)+'), self.scheme.code_class),
            # Generics
            (re.compile(r'<[^<>]+>'), self.scheme.code_class),
        ])
        return patterns
    
    def _java_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            # Comentarios
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            # Strings
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            # Characters
            (re.compile(r"'(?:[^'\\]|\\.)'"), self.scheme.code_string),
            # Keywords
            (re.compile(r'\b(abstract|assert|boolean|break|byte|case|catch|char|'
                       r'class|const|continue|default|do|double|else|enum|extends|'
                       r'final|finally|float|for|goto|if|implements|import|'
                       r'instanceof|int|interface|long|native|new|package|private|'
                       r'protected|public|return|short|static|strictfp|super|switch|'
                       r'synchronized|this|throw|throws|transient|try|void|volatile|'
                       r'while|true|false|null|var|record|sealed|permits|yield)\b'), 
             self.scheme.code_keyword),
            # Annotations
            (re.compile(r'@\w+'), self.scheme.code_function),
            # Classes
            (re.compile(r'\b[A-Z]\w*\b'), self.scheme.code_class),
            # Numbers
            (re.compile(r'\b\d+\.?\d*[fFdDlL]?\b'), self.scheme.code_number),
        ]
    
    def _c_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            # Comentarios
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            # Preprocesador
            (re.compile(r'^\s*#\s*\w+.*$', re.MULTILINE), self.scheme.code_keyword),
            # Strings
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            # Characters
            (re.compile(r"'(?:[^'\\]|\\.)'"), self.scheme.code_string),
            # Keywords
            (re.compile(r'\b(auto|break|case|char|const|continue|default|do|double|'
                       r'else|enum|extern|float|for|goto|if|inline|int|long|register|'
                       r'restrict|return|short|signed|sizeof|static|struct|switch|'
                       r'typedef|union|unsigned|void|volatile|while|_Bool|_Complex|'
                       r'_Imaginary|_Alignas|_Alignof|_Atomic|_Generic|_Noreturn|'
                       r'_Static_assert|_Thread_local)\b'), self.scheme.code_keyword),
            # Numbers
            (re.compile(r'\b\d+\.?\d*[uUlLfF]?\b'), self.scheme.code_number),
            (re.compile(r'\b0[xX][0-9a-fA-F]+\b'), self.scheme.code_number),
        ]
    
    def _cpp_patterns(self) -> List[Tuple[Pattern, str]]:
        patterns = self._c_patterns()
        patterns.extend([
            (re.compile(r'\b(alignas|alignof|and|and_eq|asm|bitand|bitor|bool|'
                       r'catch|char16_t|char32_t|class|compl|concept|consteval|'
                       r'constexpr|constinit|const_cast|co_await|co_return|co_yield|'
                       r'decltype|delete|dynamic_cast|explicit|export|false|friend|'
                       r'mutable|namespace|new|noexcept|not|not_eq|nullptr|operator|'
                       r'or|or_eq|private|protected|public|reinterpret_cast|requires|'
                       r'static_assert|static_cast|template|this|thread_local|throw|'
                       r'true|try|typeid|typename|using|virtual|wchar_t|xor|xor_eq)\b'), 
             self.scheme.code_keyword),
        ])
        return patterns
    
    def _csharp_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            (re.compile(r'@?"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r'\$"[^"]*"'), self.scheme.code_string),
            (re.compile(r'\b(abstract|as|base|bool|break|byte|case|catch|char|'
                       r'checked|class|const|continue|decimal|default|delegate|do|'
                       r'double|else|enum|event|explicit|extern|false|finally|fixed|'
                       r'float|for|foreach|goto|if|implicit|in|int|interface|internal|'
                       r'is|lock|long|namespace|new|null|object|operator|out|override|'
                       r'params|private|protected|public|readonly|ref|return|sbyte|'
                       r'sealed|short|sizeof|stackalloc|static|string|struct|switch|'
                       r'this|throw|true|try|typeof|uint|ulong|unchecked|unsafe|ushort|'
                       r'using|var|virtual|void|volatile|while|async|await|dynamic|'
                       r'nameof|record|init|with|required)\b'), self.scheme.code_keyword),
            (re.compile(r'\b[A-Z]\w*\b'), self.scheme.code_class),
            (re.compile(r'\b\d+\.?\d*[mMfFdD]?\b'), self.scheme.code_number),
        ]
    
    def _go_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r'`[^`]*`'), self.scheme.code_string),
            (re.compile(r'\b(break|case|chan|const|continue|default|defer|else|'
                       r'fallthrough|for|func|go|goto|if|import|interface|map|'
                       r'package|range|return|select|struct|switch|type|var|'
                       r'true|false|nil|iota|append|cap|close|complex|copy|delete|'
                       r'imag|len|make|new|panic|print|println|real|recover)\b'), 
             self.scheme.code_keyword),
            (re.compile(r'\b(bool|byte|complex64|complex128|error|float32|float64|'
                       r'int|int8|int16|int32|int64|rune|string|uint|uint8|uint16|'
                       r'uint32|uint64|uintptr)\b'), self.scheme.code_class),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _rust_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"b?'(?:[^'\\]|\\.)'"), self.scheme.code_string),
            (re.compile(r'r#*"[\s\S]*?"#*'), self.scheme.code_string),
            (re.compile(r'\b(as|async|await|break|const|continue|crate|dyn|else|'
                       r'enum|extern|false|fn|for|if|impl|in|let|loop|match|mod|'
                       r'move|mut|pub|ref|return|self|Self|static|struct|super|'
                       r'trait|true|type|unsafe|use|where|while|abstract|become|'
                       r'box|do|final|macro|override|priv|try|typeof|unsized|'
                       r'virtual|yield)\b'), self.scheme.code_keyword),
            (re.compile(r'\b(i8|i16|i32|i64|i128|isize|u8|u16|u32|u64|u128|usize|'
                       r'f32|f64|bool|char|str|String|Vec|Option|Result|Box|Rc|Arc|'
                       r'Cell|RefCell|Mutex|RwLock)\b'), self.scheme.code_class),
            (re.compile(r'#\[[\w:()]+\]'), self.scheme.code_function),
            (re.compile(r'\b\d+\.?\d*(_\d+)*\b'), self.scheme.code_number),
            (re.compile(r'\b[A-Z]\w*\b'), self.scheme.code_class),
        ]
    
    def _ruby_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'=begin[\s\S]*?=end'), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), self.scheme.code_string),
            (re.compile(r'%[qQwWiIxsr]?[{(\[<].*?[})\]>]'), self.scheme.code_string),
            (re.compile(r'/(?:[^/\\]|\\.)*/', re.MULTILINE), self.scheme.code_string),
            (re.compile(r'\b(BEGIN|END|alias|and|begin|break|case|class|def|defined\?|'
                       r'do|else|elsif|end|ensure|false|for|if|in|module|next|nil|not|'
                       r'or|redo|rescue|retry|return|self|super|then|true|undef|unless|'
                       r'until|when|while|yield|__FILE__|__LINE__|require|require_relative|'
                       r'include|extend|attr_reader|attr_writer|attr_accessor|private|'
                       r'protected|public|raise|lambda|proc)\b'), self.scheme.code_keyword),
            (re.compile(r':\w+'), self.scheme.code_string),
            (re.compile(r'@{1,2}\w+'), self.scheme.code_variable),
            (re.compile(r'\$\w+'), self.scheme.code_variable),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _php_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), self.scheme.code_string),
            (re.compile(r'<<<[\'"]?(\w+)[\'"]?\n[\s\S]*?\n\1'), self.scheme.code_string),
            (re.compile(r'\b(abstract|and|array|as|break|callable|case|catch|class|'
                       r'clone|const|continue|declare|default|die|do|echo|else|elseif|'
                       r'empty|enddeclare|endfor|endforeach|endif|endswitch|endwhile|'
                       r'eval|exit|extends|final|finally|fn|for|foreach|function|global|'
                       r'goto|if|implements|include|include_once|instanceof|insteadof|'
                       r'interface|isset|list|match|namespace|new|or|print|private|'
                       r'protected|public|readonly|require|require_once|return|static|'
                       r'switch|throw|trait|try|unset|use|var|while|xor|yield|'
                       r'true|false|null)\b', re.IGNORECASE), self.scheme.code_keyword),
            (re.compile(r'\$\w+'), self.scheme.code_variable),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _swift_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r'"""[\s\S]*?"""'), self.scheme.code_string),
            (re.compile(r'\b(associatedtype|class|deinit|enum|extension|fileprivate|'
                       r'func|import|init|inout|internal|let|open|operator|private|'
                       r'precedencegroup|protocol|public|rethrows|static|struct|'
                       r'subscript|typealias|var|break|case|catch|continue|default|'
                       r'defer|do|else|fallthrough|for|guard|if|in|repeat|return|'
                       r'switch|throw|try|where|while|Any|as|catch|false|is|nil|'
                       r'self|Self|super|throws|true|async|await|actor)\b'), 
             self.scheme.code_keyword),
            (re.compile(r'@\w+'), self.scheme.code_function),
            (re.compile(r'\b[A-Z]\w*\b'), self.scheme.code_class),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _kotlin_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r'"""[\s\S]*?"""'), self.scheme.code_string),
            (re.compile(r'\b(abstract|actual|annotation|as|break|by|catch|class|'
                       r'companion|const|constructor|continue|crossinline|data|do|'
                       r'dynamic|else|enum|expect|external|false|final|finally|for|'
                       r'fun|get|if|import|in|infix|init|inline|inner|interface|'
                       r'internal|is|lateinit|noinline|null|object|open|operator|out|'
                       r'override|package|private|protected|public|reified|return|'
                       r'sealed|set|super|suspend|tailrec|this|throw|true|try|typealias|'
                       r'typeof|val|var|vararg|when|where|while)\b'), self.scheme.code_keyword),
            (re.compile(r'@\w+'), self.scheme.code_function),
            (re.compile(r'\b[A-Z]\w*\b'), self.scheme.code_class),
            (re.compile(r'\b\d+\.?\d*[fFdDlL]?\b'), self.scheme.code_number),
        ]
    
    def _scala_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r'"""[\s\S]*?"""'), self.scheme.code_string),
            (re.compile(r'\b(abstract|case|catch|class|def|do|else|extends|false|'
                       r'final|finally|for|forSome|if|implicit|import|lazy|match|new|'
                       r'null|object|override|package|private|protected|return|sealed|'
                       r'super|this|throw|trait|true|try|type|val|var|while|with|yield|'
                       r'given|using|enum|extension|then|end)\b'), self.scheme.code_keyword),
            (re.compile(r'@\w+'), self.scheme.code_function),
            (re.compile(r'\b[A-Z]\w*\b'), self.scheme.code_class),
            (re.compile(r'\b\d+\.?\d*[fFdDlL]?\b'), self.scheme.code_number),
        ]
    
    def _bash_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\$]|\\.|\$[^(])*"'), self.scheme.code_string),
            (re.compile(r"'[^']*'"), self.scheme.code_string),
            (re.compile(r'\$\{?[\w@#?$!*-]+\}?'), self.scheme.code_variable),
            (re.compile(r'\b(if|then|else|elif|fi|case|esac|for|while|until|do|done|'
                       r'in|function|select|time|coproc|return|exit|break|continue|'
                       r'declare|local|export|readonly|typeset|unset|shift|source|'
                       r'alias|unalias|test|eval|exec|trap|wait|kill|jobs|fg|bg|'
                       r'true|false)\b'), self.scheme.code_keyword),
            (re.compile(r'\b(cd|ls|echo|cat|grep|sed|awk|find|xargs|sort|uniq|'
                       r'wc|head|tail|cut|tr|mkdir|rm|cp|mv|chmod|chown|'
                       r'curl|wget|tar|gzip|gunzip|ssh|scp|rsync|git|docker|'
                       r'sudo|apt|yum|brew|npm|pip|python|node)\b'), 
             self.scheme.code_function),
            (re.compile(r'\b\d+\b'), self.scheme.code_number),
            (re.compile(r'[|&;><]+'), self.scheme.code_operator),
        ]
    
    def _powershell_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'<#[\s\S]*?#>'), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\`]|\\.|`[^$])*"'), self.scheme.code_string),
            (re.compile(r"'[^']*'"), self.scheme.code_string),
            (re.compile(r'\$[\w:]+'), self.scheme.code_variable),
            (re.compile(r'\b(Begin|Break|Catch|Class|Continue|Data|Define|Do|DynamicParam|'
                       r'Else|ElseIf|End|Enum|Exit|Filter|Finally|For|ForEach|From|Function|'
                       r'Hidden|If|In|InlineScript|Param|Process|Return|Sequence|Static|'
                       r'Switch|Throw|Trap|Try|Until|Using|Var|While|Workflow)\b', 
                       re.IGNORECASE), self.scheme.code_keyword),
            (re.compile(r'-\w+'), self.scheme.code_keyword),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _sql_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'--.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), self.scheme.code_string),
            (re.compile(r'\b(SELECT|FROM|WHERE|AND|OR|NOT|IN|LIKE|BETWEEN|IS|NULL|'
                       r'ORDER|BY|ASC|DESC|LIMIT|OFFSET|JOIN|INNER|LEFT|RIGHT|FULL|'
                       r'OUTER|CROSS|ON|AS|INSERT|INTO|VALUES|UPDATE|SET|DELETE|'
                       r'CREATE|TABLE|DATABASE|INDEX|VIEW|DROP|ALTER|ADD|COLUMN|'
                       r'PRIMARY|KEY|FOREIGN|REFERENCES|UNIQUE|CHECK|DEFAULT|'
                       r'CONSTRAINT|CASCADE|TRUNCATE|EXISTS|UNION|ALL|DISTINCT|'
                       r'GROUP|HAVING|COUNT|SUM|AVG|MIN|MAX|CASE|WHEN|THEN|ELSE|END|'
                       r'CAST|CONVERT|COALESCE|NULLIF|IF|IFNULL|ISNULL|'
                       r'BEGIN|COMMIT|ROLLBACK|TRANSACTION|GRANT|REVOKE|WITH|'
                       r'RECURSIVE|CTE|OVER|PARTITION|ROW_NUMBER|RANK|DENSE_RANK|'
                       r'TRUE|FALSE)\b', re.IGNORECASE), self.scheme.code_keyword),
            (re.compile(r'\b(INT|INTEGER|BIGINT|SMALLINT|TINYINT|DECIMAL|NUMERIC|'
                       r'FLOAT|REAL|DOUBLE|CHAR|VARCHAR|TEXT|NCHAR|NVARCHAR|NTEXT|'
                       r'DATE|TIME|DATETIME|TIMESTAMP|BOOLEAN|BOOL|BLOB|BINARY|'
                       r'VARBINARY|JSON|XML|UUID|SERIAL|IDENTITY)\b', re.IGNORECASE), 
             self.scheme.code_class),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _html_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'<!--[\s\S]*?-->'), self.scheme.code_comment),
            (re.compile(r'<!DOCTYPE[^>]*>', re.IGNORECASE), self.scheme.code_keyword),
            (re.compile(r'</?[a-zA-Z][\w-]*'), self.scheme.code_keyword),
            (re.compile(r'>'), self.scheme.code_keyword),
            (re.compile(r'\s[\w-]+(?==)'), self.scheme.code_variable),
            (re.compile(r'"[^"]*"'), self.scheme.code_string),
            (re.compile(r"'[^']*'"), self.scheme.code_string),
            (re.compile(r'&\w+;|&#\d+;|&#x[0-9a-fA-F]+;'), self.scheme.code_number),
        ]
    
    def _xml_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'<!--[\s\S]*?-->'), self.scheme.code_comment),
            (re.compile(r'<\?xml[^?]*\?>'), self.scheme.code_keyword),
            (re.compile(r'<!\[CDATA\[[\s\S]*?\]\]>'), self.scheme.code_string),
            (re.compile(r'</?\w[\w:-]*'), self.scheme.code_keyword),
            (re.compile(r'>'), self.scheme.code_keyword),
            (re.compile(r'\s[\w:-]+(?==)'), self.scheme.code_variable),
            (re.compile(r'"[^"]*"'), self.scheme.code_string),
            (re.compile(r"'[^']*'"), self.scheme.code_string),
        ]
    
    def _css_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            (re.compile(r'"[^"]*"'), self.scheme.code_string),
            (re.compile(r"'[^']*'"), self.scheme.code_string),
            (re.compile(r'#[0-9a-fA-F]{3,8}\b'), self.scheme.code_number),
            (re.compile(r'\d+\.?\d*(px|em|rem|%|vh|vw|vmin|vmax|ch|ex|cm|mm|in|pt|pc|deg|rad|grad|turn|s|ms|Hz|kHz|dpi|dpcm|dppx)?'), 
             self.scheme.code_number),
            (re.compile(r'[.#][\w-]+'), self.scheme.code_class),
            (re.compile(r'@\w+'), self.scheme.code_keyword),
            (re.compile(r':[\w-]+'), self.scheme.code_keyword),
            (re.compile(r'[\w-]+(?=\s*:)'), self.scheme.code_variable),
            (re.compile(r'\b(inherit|initial|unset|revert|none|auto|normal)\b'), 
             self.scheme.code_keyword),
        ]
    
    def _scss_patterns(self) -> List[Tuple[Pattern, str]]:
        patterns = self._css_patterns()
        patterns.extend([
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'\$[\w-]+'), self.scheme.code_variable),
            (re.compile(r'@(mixin|include|extend|function|return|if|else|for|each|while|use|forward|import|at-root|debug|warn|error)\b'), 
             self.scheme.code_keyword),
            (re.compile(r'&'), self.scheme.code_keyword),
        ])
        return patterns
    
    def _json_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'"(?:[^"\\]|\\.)*"(?=\s*:)'), self.scheme.code_variable),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r'\b(true|false|null)\b'), self.scheme.code_keyword),
            (re.compile(r'-?\d+\.?\d*([eE][+-]?\d+)?'), self.scheme.code_number),
        ]
    
    def _yaml_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), self.scheme.code_string),
            (re.compile(r'^[\w.-]+(?=\s*:)', re.MULTILINE), self.scheme.code_variable),
            (re.compile(r'\b(true|false|yes|no|on|off|null|~)\b', re.IGNORECASE), 
             self.scheme.code_keyword),
            (re.compile(r'[|>][-+]?'), self.scheme.code_operator),
            (re.compile(r'<<|&\w+|\*\w+'), self.scheme.code_keyword),
            (re.compile(r'-?\d+\.?\d*([eE][+-]?\d+)?'), self.scheme.code_number),
        ]
    
    def _toml_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"""[\s\S]*?"""'), self.scheme.code_string),
            (re.compile(r"'''[\s\S]*?'''"), self.scheme.code_string),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'[^']*'"), self.scheme.code_string),
            (re.compile(r'^\s*\[+[\w.-]+\]+', re.MULTILINE), self.scheme.code_class),
            (re.compile(r'^[\w.-]+(?=\s*=)', re.MULTILINE), self.scheme.code_variable),
            (re.compile(r'\b(true|false)\b'), self.scheme.code_keyword),
            (re.compile(r'\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}:\d{2}(.\d+)?(Z|[+-]\d{2}:\d{2})?)?'), 
             self.scheme.code_number),
            (re.compile(r'-?\d+\.?\d*([eE][+-]?\d+)?'), self.scheme.code_number),
        ]
    
    def _ini_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'[;#].*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'^\s*\[[^\]]+\]', re.MULTILINE), self.scheme.code_class),
            (re.compile(r'^[\w.-]+(?=\s*=)', re.MULTILINE), self.scheme.code_variable),
            (re.compile(r'"[^"]*"'), self.scheme.code_string),
            (re.compile(r"'[^']*'"), self.scheme.code_string),
            (re.compile(r'\b(true|false|yes|no|on|off)\b', re.IGNORECASE), 
             self.scheme.code_keyword),
            (re.compile(r'\d+'), self.scheme.code_number),
        ]
    
    def _markdown_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'^#{1,6}\s+.*$', re.MULTILINE), self.scheme.code_keyword),
            (re.compile(r'\*\*[^*]+\*\*'), self.scheme.code_keyword),
            (re.compile(r'\*[^*]+\*'), self.scheme.code_variable),
            (re.compile(r'`[^`]+`'), self.scheme.code_string),
            (re.compile(r'\[[^\]]+\]\([^)]+\)'), self.scheme.code_function),
            (re.compile(r'^\s*[-*+]\s', re.MULTILINE), self.scheme.code_operator),
            (re.compile(r'^\s*\d+\.\s', re.MULTILINE), self.scheme.code_number),
        ]
    
    def _dockerfile_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), self.scheme.code_string),
            (re.compile(r'\b(FROM|RUN|CMD|LABEL|MAINTAINER|EXPOSE|ENV|ADD|COPY|'
                       r'ENTRYPOINT|VOLUME|USER|WORKDIR|ARG|ONBUILD|STOPSIGNAL|'
                       r'HEALTHCHECK|SHELL|AS)\b'), self.scheme.code_keyword),
            (re.compile(r'\$\{?[\w]+\}?'), self.scheme.code_variable),
        ]
    
    def _makefile_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), self.scheme.code_string),
            (re.compile(r'^[\w.-]+(?=\s*[:?]?=)', re.MULTILINE), self.scheme.code_variable),
            (re.compile(r'^[\w.-]+(?=\s*:(?!=))', re.MULTILINE), self.scheme.code_function),
            (re.compile(r'\$[({][\w]+[)}]|\$[\w]'), self.scheme.code_variable),
            (re.compile(r'\b(ifeq|ifneq|ifdef|ifndef|else|endif|define|endef|'
                       r'include|override|export|unexport|vpath|.PHONY|.SUFFIXES|'
                       r'.DEFAULT|.PRECIOUS|.INTERMEDIATE|.SECONDARY|.SECONDEXPANSION|'
                       r'.DELETE_ON_ERROR|.IGNORE|.LOW_RESOLUTION_TIME|.SILENT|'
                       r'.EXPORT_ALL_VARIABLES|.NOTPARALLEL|.ONESHELL|.POSIX)\b'), 
             self.scheme.code_keyword),
            (re.compile(r'[@-]'), self.scheme.code_operator),
        ]
    
    def _lua_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'--\[\[[\s\S]*?\]\]'), self.scheme.code_comment),
            (re.compile(r'--.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'\[\[[\s\S]*?\]\]'), self.scheme.code_string),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), self.scheme.code_string),
            (re.compile(r'\b(and|break|do|else|elseif|end|false|for|function|goto|if|'
                       r'in|local|nil|not|or|repeat|return|then|true|until|while)\b'), 
             self.scheme.code_keyword),
            (re.compile(r'\b(print|type|pairs|ipairs|next|tonumber|tostring|'
                       r'error|assert|pcall|xpcall|require|dofile|loadfile|'
                       r'setmetatable|getmetatable|rawget|rawset|rawequal|'
                       r'select|unpack|table|string|math|io|os|debug|coroutine)\b'), 
             self.scheme.code_function),
            (re.compile(r'\b\d+\.?\d*([eE][+-]?\d+)?\b'), self.scheme.code_number),
            (re.compile(r'\b0[xX][0-9a-fA-F]+\b'), self.scheme.code_number),
        ]
    
    def _perl_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'=\w+[\s\S]*?=cut'), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), self.scheme.code_string),
            (re.compile(r'[qw]+\{[^}]*\}|[qw]+\([^)]*\)|[qw]+\[[^\]]*\]'), self.scheme.code_string),
            (re.compile(r'/(?:[^/\\]|\\.)+/[gimsx]*'), self.scheme.code_string),
            (re.compile(r'\b(if|elsif|else|unless|while|until|for|foreach|'
                       r'do|last|next|redo|return|goto|sub|my|our|local|'
                       r'use|no|require|package|BEGIN|END|__DATA__|__END__)\b'), 
             self.scheme.code_keyword),
            (re.compile(r'[\$@%]\w+'), self.scheme.code_variable),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _r_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), self.scheme.code_string),
            (re.compile(r'\b(if|else|repeat|while|for|in|next|break|return|'
                       r'function|TRUE|FALSE|NULL|Inf|NaN|NA|NA_integer_|'
                       r'NA_real_|NA_complex_|NA_character_)\b'), self.scheme.code_keyword),
            (re.compile(r'\b(print|cat|paste|paste0|sprintf|library|require|'
                       r'source|c|list|data\.frame|matrix|vector|factor|'
                       r'length|nrow|ncol|dim|names|class|typeof|str|summary|'
                       r'mean|median|sd|var|min|max|sum|range|sort|order|'
                       r'unique|table|apply|lapply|sapply|mapply|tapply|'
                       r'read\.csv|write\.csv|read\.table|write\.table)\b'), 
             self.scheme.code_function),
            (re.compile(r'<-|->|<<-|->>|='), self.scheme.code_operator),
            (re.compile(r'\b\d+\.?\d*([eE][+-]?\d+)?[iL]?\b'), self.scheme.code_number),
        ]
    
    def _julia_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#=[\s\S]*?=#'), self.scheme.code_comment),
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"""[\s\S]*?"""'), self.scheme.code_string),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)'"), self.scheme.code_string),
            (re.compile(r'\b(baremodule|begin|break|catch|const|continue|do|else|'
                       r'elseif|end|export|finally|for|function|global|if|import|'
                       r'let|local|macro|module|quote|return|struct|try|using|while|'
                       r'abstract|mutable|primitive|type|where|true|false|nothing)\b'), 
             self.scheme.code_keyword),
            (re.compile(r'\b(Int|Int8|Int16|Int32|Int64|Int128|UInt|UInt8|UInt16|'
                       r'UInt32|UInt64|UInt128|Float16|Float32|Float64|Bool|Char|'
                       r'String|Symbol|Any|Union|Nothing|Missing|Array|Vector|Matrix|'
                       r'Dict|Set|Tuple|NamedTuple|Pair)\b'), self.scheme.code_class),
            (re.compile(r'\b\d+\.?\d*([eE][+-]?\d+)?(im)?\b'), self.scheme.code_number),
        ]
    
    def _haskell_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'\{-[\s\S]*?-\}'), self.scheme.code_comment),
            (re.compile(r'--.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)+'"), self.scheme.code_string),
            (re.compile(r'\b(case|class|data|default|deriving|do|else|family|'
                       r'forall|foreign|hiding|if|import|in|infix|infixl|infixr|'
                       r'instance|let|module|newtype|of|qualified|then|type|where|'
                       r'True|False|Nothing|Just|Left|Right|IO|Maybe|Either)\b'), 
             self.scheme.code_keyword),
            (re.compile(r'\b[A-Z]\w*\b'), self.scheme.code_class),
            (re.compile(r'::|->|<-|=>|\\'), self.scheme.code_operator),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _elixir_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'@doc\s+"""[\s\S]*?"""'), self.scheme.code_comment),
            (re.compile(r'"""[\s\S]*?"""'), self.scheme.code_string),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), self.scheme.code_string),
            (re.compile(r'~[a-z]\{[^}]*\}|~[a-z]\([^)]*\)|~[a-z]\[[^\]]*\]'), 
             self.scheme.code_string),
            (re.compile(r'\b(after|and|case|catch|cond|def|defp|defmodule|defmacro|'
                       r'defmacrop|defprotocol|defimpl|defstruct|defguard|defguardp|'
                       r'defdelegate|defexception|defoverridable|do|else|end|fn|for|'
                       r'if|import|in|not|or|quote|raise|receive|require|rescue|'
                       r'try|unless|unquote|use|when|with|true|false|nil)\b'), 
             self.scheme.code_keyword),
            (re.compile(r'@\w+'), self.scheme.code_function),
            (re.compile(r':\w+'), self.scheme.code_string),
            (re.compile(r'\b[A-Z]\w*\b'), self.scheme.code_class),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _erlang_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'%.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r'\b(after|and|andalso|band|begin|bnot|bor|bsl|bsr|bxor|'
                       r'case|catch|cond|div|end|fun|if|let|not|of|or|orelse|'
                       r'receive|rem|try|when|xor)\b'), self.scheme.code_keyword),
            (re.compile(r'\b(true|false|ok|error|undefined)\b'), self.scheme.code_keyword),
            (re.compile(r'\b[a-z]\w*\b'), self.scheme.code_function),
            (re.compile(r'\b[A-Z]\w*\b'), self.scheme.code_variable),
            (re.compile(r'\?\w+'), self.scheme.code_class),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _clojure_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r';.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r'\b(def|defn|defmacro|defmethod|defmulti|defonce|defprotocol|'
                       r'defrecord|defstruct|deftype|fn|if|do|let|loop|recur|throw|'
                       r'try|catch|finally|monitor-enter|monitor-exit|new|quote|var|'
                       r'cond|case|when|when-not|when-let|when-first|when-some|'
                       r'if-let|if-not|if-some|for|doseq|dotimes|while|and|or|not|'
                       r'nil|true|false|ns|require|use|import|refer)\b'), 
             self.scheme.code_keyword),
            (re.compile(r':\w[\w-]*'), self.scheme.code_string),
            (re.compile(r"'\w[\w-]*"), self.scheme.code_string),
            (re.compile(r'\b\d+\.?\d*[MN]?\b'), self.scheme.code_number),
        ]
    
    def _vim_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'".*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r"'[^']*'"), self.scheme.code_string),
            (re.compile(r'\b(if|else|elseif|endif|while|endwhile|for|endfor|'
                       r'try|catch|finally|endtry|function|endfunction|'
                       r'return|call|let|unlet|set|setlocal|echo|echom|'
                       r'execute|normal|autocmd|augroup|command|map|nmap|'
                       r'vmap|imap|nnoremap|vnoremap|inoremap|source|'
                       r'syntax|highlight|colorscheme)\b', re.IGNORECASE), 
             self.scheme.code_keyword),
            (re.compile(r'<[^>]+>'), self.scheme.code_function),
            (re.compile(r'\b\d+\b'), self.scheme.code_number),
        ]
    
    def _diff_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'^@@[^@]+@@.*$', re.MULTILINE), self.scheme.code_class),
            (re.compile(r'^---.*$', re.MULTILINE), self.scheme.code_keyword),
            (re.compile(r'^\+\+\+.*$', re.MULTILINE), self.scheme.code_keyword),
            (re.compile(r'^\+.*$', re.MULTILINE), self.scheme.success),
            (re.compile(r'^-.*$', re.MULTILINE), self.scheme.error),
            (re.compile(r'^diff.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'^index.*$', re.MULTILINE), self.scheme.code_comment),
        ]
    
    def _mermaid_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'%%.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"[^"]*"'), self.scheme.code_string),
            (re.compile(r'\b(graph|subgraph|end|flowchart|sequenceDiagram|'
                       r'classDiagram|stateDiagram|erDiagram|journey|gantt|pie|'
                       r'gitGraph|mindmap|timeline|quadrantChart|sankey|'
                       r'participant|actor|activate|deactivate|Note|loop|alt|'
                       r'else|opt|par|critical|break|rect|autonumber|'
                       r'direction|TB|TD|BT|RL|LR|class|style|linkStyle|'
                       r'click|callback|title|section|dateFormat|axisFormat|'
                       r'excludes|includes|todayMarker)\b'), self.scheme.code_keyword),
            (re.compile(r'-->|->|-->>|->>|--x|--o|<-->|o--o|x--x'), self.scheme.code_operator),
            (re.compile(r'\|[^|]+\|'), self.scheme.code_string),
            (re.compile(r'\[[^\]]+\]'), self.scheme.code_class),
            (re.compile(r'\{[^}]+\}'), self.scheme.code_class),
            (re.compile(r'\([^)]+\)'), self.scheme.code_function),
        ]
    
    def _regex_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'\\.'), self.scheme.code_string),
            (re.compile(r'\[(?:\^)?\]?[^\]]*\]'), self.scheme.code_class),
            (re.compile(r'\(\?[:=!<>]|\(\?P[<]?\w+[>]?|\('), self.scheme.code_keyword),
            (re.compile(r'\)'), self.scheme.code_keyword),
            (re.compile(r'[*+?]|\{\d+(?:,\d*)?\}'), self.scheme.code_number),
            (re.compile(r'\^|\$|\\[bBAZzGdDwWsS]'), self.scheme.code_keyword),
            (re.compile(r'\|'), self.scheme.code_operator),
        ]
    
    def _graphql_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"""[\s\S]*?"""'), self.scheme.code_string),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r'\b(query|mutation|subscription|fragment|on|type|interface|'
                       r'union|enum|scalar|input|extend|directive|schema|'
                       r'implements|repeatable)\b'), self.scheme.code_keyword),
            (re.compile(r'\b(Int|Float|String|Boolean|ID)\b'), self.scheme.code_class),
            (re.compile(r'@\w+'), self.scheme.code_function),
            (re.compile(r'\$\w+'), self.scheme.code_variable),
            (re.compile(r'\b(true|false|null)\b'), self.scheme.code_keyword),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _terraform_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'//.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'/\*[\s\S]*?\*/'), self.scheme.code_comment),
            (re.compile(r'<<-?\w+[\s\S]*?^\w+$', re.MULTILINE), self.scheme.code_string),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r'\b(resource|data|variable|output|locals|module|provider|'
                       r'terraform|backend|required_providers|required_version|'
                       r'for_each|count|depends_on|lifecycle|provisioner|connection|'
                       r'dynamic|content|for|in|if|else|endif)\b'), self.scheme.code_keyword),
            (re.compile(r'\b(string|number|bool|list|map|set|object|tuple|any)\b'), 
             self.scheme.code_class),
            (re.compile(r'\b(true|false|null)\b'), self.scheme.code_keyword),
            (re.compile(r'\$\{[^}]+\}'), self.scheme.code_variable),
            (re.compile(r'\b\d+\.?\d*\b'), self.scheme.code_number),
        ]
    
    def _nginx_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r"'(?:[^'\\]|\\.)*'"), self.scheme.code_string),
            (re.compile(r'\b(server|location|upstream|http|events|stream|mail|'
                       r'if|set|rewrite|return|proxy_pass|fastcgi_pass|'
                       r'include|root|index|try_files|error_page|access_log|'
                       r'error_log|listen|server_name|ssl_certificate|'
                       r'ssl_certificate_key|add_header|expires|gzip|'
                       r'client_max_body_size|proxy_set_header|'
                       r'proxy_read_timeout|proxy_connect_timeout)\b'), 
             self.scheme.code_keyword),
            (re.compile(r'\$\w+'), self.scheme.code_variable),
            (re.compile(r'\b(on|off)\b'), self.scheme.code_keyword),
            (re.compile(r'\b\d+[smhdwMy]?\b'), self.scheme.code_number),
        ]
    
    def _apache_patterns(self) -> List[Tuple[Pattern, str]]:
        return [
            (re.compile(r'#.*$', re.MULTILINE), self.scheme.code_comment),
            (re.compile(r'"(?:[^"\\]|\\.)*"'), self.scheme.code_string),
            (re.compile(r'</?[A-Za-z]\w*'), self.scheme.code_keyword),
            (re.compile(r'>'), self.scheme.code_keyword),
            (re.compile(r'\b(ServerRoot|Listen|LoadModule|ServerAdmin|ServerName|'
                       r'DocumentRoot|ErrorLog|CustomLog|LogLevel|Directory|'
                       r'DirectoryIndex|Options|AllowOverride|Require|Order|'
                       r'Allow|Deny|RewriteEngine|RewriteCond|RewriteRule|'
                       r'RedirectMatch|Redirect|Alias|ScriptAlias|'
                       r'SetEnv|SetEnvIf|Header|ExpiresActive|ExpiresByType|'
                       r'SSLEngine|SSLCertificateFile|SSLCertificateKeyFile)\b'), 
             self.scheme.code_keyword),
            (re.compile(r'%\{[^}]+\}'), self.scheme.code_variable),
            (re.compile(r'\b(On|Off|All|None)\b'), self.scheme.code_keyword),
        ]


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 6: RENDERIZADOR PRINCIPAL DE MARKDOWN
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RenderContext:
    """Contexto de renderizado para mantener estado"""
    in_code_block: bool = False
    code_language: str = ""
    code_fence_char: str = ""
    code_fence_count: int = 0
    
    in_math_block: bool = False
    in_table: bool = False
    in_blockquote: bool = False
    blockquote_depth: int = 0
    
    in_list: bool = False
    list_type: str = ""  # 'ul' o 'ol'
    list_indent: int = 0
    list_counter: int = 0
    
    in_frontmatter: bool = False
    frontmatter_started: bool = False
    
    # Buffers
    table_buffer: List[str] = field(default_factory=list)
    code_buffer: List[str] = field(default_factory=list)
    
    # Referencias
    link_references: Dict[str, str] = field(default_factory=dict)
    footnotes: Dict[str, str] = field(default_factory=dict)
    abbreviations: Dict[str, str] = field(default_factory=dict)
    
    # Contadores
    heading_count: Dict[int, int] = field(default_factory=lambda: {i: 0 for i in range(1, 7)})
    footnote_counter: int = 0


@dataclass
class RendererConfig:
    """Configuración del renderizador"""
    width: int = 80
    tab_size: int = 4
    theme: Theme = Theme.NVIDIA
    
    # Características habilitadas
    enable_emoji: bool = True
    enable_syntax_highlight: bool = True
    enable_tables: bool = True
    enable_math: bool = True
    enable_footnotes: bool = True
    enable_abbreviations: bool = True
    enable_task_lists: bool = True
    enable_definition_lists: bool = True
    enable_alerts: bool = True
    enable_mermaid: bool = True
    enable_frontmatter: bool = True
    enable_toc: bool = False
    enable_line_numbers: bool = False
    enable_word_wrap: bool = True
    
    # Estilos
    use_rounded_corners: bool = True
    use_icons: bool = True
    use_color: bool = True
    compact_mode: bool = False
    
    # Indentación
    list_indent: int = 2
    quote_indent: int = 2
    code_indent: int = 2


class MarkdownRenderer:
    """
    Renderizador de Markdown avanzado para terminal.
    
    Soporta:
    - CommonMark completo
    - GitHub Flavored Markdown (GFM)
    - Extensiones adicionales (matemáticas, diagramas, etc.)
    - Múltiples temas de colores
    - Syntax highlighting para 40+ lenguajes
    - Tablas con alineación
    - Alertas/Admonitions
    - Emojis con shortcodes
    - Y mucho más...
    """
    
    def __init__(self, config: RendererConfig = None):
        """Inicializa el renderizador con la configuración dada"""
        self.config = config or RendererConfig()
        self.scheme = ColorScheme.from_theme(self.config.theme)
        self.highlighter = SyntaxHighlighter(self.scheme)
        self.ctx = RenderContext()
        
        # Box characters según configuración
        if self.config.use_rounded_corners:
            self.box = {
                'tl': BoxChars.RTL, 'tr': BoxChars.RTR,
                'bl': BoxChars.RBL, 'br': BoxChars.RBR,
                'h': BoxChars.H, 'v': BoxChars.V,
                'lt': BoxChars.LT, 'rt': BoxChars.RT,
                'tt': BoxChars.TT, 'bt': BoxChars.BT,
                'cr': BoxChars.CR,
            }
        else:
            self.box = {
                'tl': BoxChars.TL, 'tr': BoxChars.TR,
                'bl': BoxChars.BL, 'br': BoxChars.BR,
                'h': BoxChars.H, 'v': BoxChars.V,
                'lt': BoxChars.LT, 'rt': BoxChars.RT,
                'tt': BoxChars.TT, 'bt': BoxChars.BT,
                'cr': BoxChars.CR,
            }
        
        # Caché para patrones compilados
        self._pattern_cache: Dict[str, Pattern] = {}
    
    def render(self, text: str) -> str:
        """
        Renderiza texto Markdown completo.
        
        Args:
            text: Texto en formato Markdown
            
        Returns:
            Texto formateado con códigos ANSI para terminal
        """
        if not text:
            return ""
        
        # Resetear contexto
        self.ctx = RenderContext()
        
        # Pre-procesamiento
        text = self._preprocess(text)
        
        # Primera pasada: recoger referencias y definiciones
        lines = text.split('\n')
        self._collect_references(lines)
        
        # Segunda pasada: renderizar
        result = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Manejar frontmatter YAML
            if i == 0 and Patterns.FRONTMATTER.match(line):
                rendered, consumed = self._handle_frontmatter(lines, i)
                result.append(rendered)
                i += consumed
                continue
            
            # Manejar bloques de código
            fence_match = Patterns.CODE_FENCE.match(line)
            if fence_match:
                rendered, consumed = self._handle_code_block(lines, i, fence_match)
                result.append(rendered)
                i += consumed
                continue
            
            # Manejar bloques matemáticos
            if Patterns.MATH_BLOCK.match(line.strip()):
                rendered, consumed = self._handle_math_block(lines, i)
                result.append(rendered)
                i += consumed
                continue
            
            # Manejar tablas
            if self._is_table_line(line) and not self.ctx.in_code_block:
                rendered, consumed = self._handle_table(lines, i)
                result.append(rendered)
                i += consumed
                continue
            
            # Renderizar línea individual
            rendered = self._render_line(line)
            result.append(rendered)
            i += 1
        
        # Post-procesamiento
        output = '\n'.join(result)
        output = self._postprocess(output)
        
        return output
    
    def _preprocess(self, text: str) -> str:
        """Pre-procesa el texto antes del renderizado"""
        # Normalizar saltos de línea
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Expandir tabs
        text = text.expandtabs(self.config.tab_size)
        
        # Reemplazar emojis
        if self.config.enable_emoji:
            text = replace_emoji_shortcodes(text)
        
        return text
    
    def _postprocess(self, text: str) -> str:
        """Post-procesa el texto después del renderizado"""
        # Eliminar líneas vacías múltiples
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Agregar footnotes al final si existen
        if self.ctx.footnotes and self.config.enable_footnotes:
            text += self._render_footnotes()
        
        return text.strip()
    
    def _collect_references(self, lines: List[str]) -> None:
        """Recolecta referencias de links, footnotes y abreviaciones"""
        for line in lines:
            # Link references [id]: url
            match = Patterns.LINK_REF_DEF.match(line)
            if match:
                ref_id = match.group(1).lower()
                url = match.group(2).strip()
                self.ctx.link_references[ref_id] = url
                continue
            
            # Footnote definitions [^id]: content
            match = Patterns.FOOTNOTE_DEF.match(line)
            if match:
                fn_id = match.group(1)
                content = match.group(2)
                self.ctx.footnotes[fn_id] = content
                continue
            
            # Abbreviation definitions *[abbr]: full text
            match = Patterns.ABBR_DEF.match(line)
            if match:
                abbr = match.group(1)
                full = match.group(2)
                self.ctx.abbreviations[abbr] = full
    
    def _is_table_line(self, line: str) -> bool:
        """Determina si una línea es parte de una tabla"""
        stripped = line.strip()
        if not stripped:
            return False
        return stripped.startswith('|') or '|' in stripped
    
    # ─────────────────────────────────────────────────────────────────────────
    # Manejadores de bloques
    # ─────────────────────────────────────────────────────────────────────────
    
    def _handle_frontmatter(self, lines: List[str], start: int) -> Tuple[str, int]:
        """Maneja bloques de frontmatter YAML"""
        if not self.config.enable_frontmatter:
            return "", 1
        
        i = start + 1
        content = []
        
        while i < len(lines):
            if Patterns.FRONTMATTER.match(lines[i]):
                i += 1
                break
            content.append(lines[i])
            i += 1
        
        consumed = i - start
        
        if not content:
            return "", consumed
        
        # Renderizar como bloque de código YAML
        result = []
        width = self.config.width
        
        result.append("")
        result.append(f"{self.scheme.border}{self.box['tl']}{self.box['h']} 📋 FRONTMATTER {self.box['h'] * (width - 17)}{self.box['tr']}{AnsiCode.RESET}")
        
        for line in content:
            highlighted = self.highlighter.highlight(line, 'yaml')
            result.append(f"{self.scheme.border}{self.box['v']}{AnsiCode.RESET} {highlighted}")
        
        result.append(f"{self.scheme.border}{self.box['bl']}{self.box['h'] * (width - 2)}{self.box['br']}{AnsiCode.RESET}")
        result.append("")
        
        return '\n'.join(result), consumed
    
    def _handle_code_block(self, lines: List[str], start: int, 
                           fence_match: re.Match) -> Tuple[str, int]:
        """Maneja bloques de código fenced"""
        fence_char = fence_match.group(1)[0]
        fence_count = len(fence_match.group(1))
        language = fence_match.group(2) or ""
        meta = fence_match.group(3) or ""
        
        i = start + 1
        content = []
        
        # Buscar el cierre del bloque
        while i < len(lines):
            line = lines[i]
            # El cierre debe usar el mismo caracter y al menos el mismo número
            close_match = re.match(rf'^{fence_char}{{{fence_count},}}$', line.strip())
            if close_match:
                i += 1
                break
            content.append(line)
            i += 1
        
        consumed = i - start
        
        # Renderizar el bloque
        return self._render_code_block(content, language, meta), consumed
    
    def _render_code_block(self, content: List[str], language: str, 
                           meta: str = "") -> str:
        """Renderiza un bloque de código con syntax highlighting"""
        result = []
        width = self.config.width
        lang_display = language.upper() if language else "CODE"
        
        # Determinar icono
        icon_map = {
            'python': Icons.PYTHON, 'py': Icons.PYTHON,
            'javascript': Icons.JAVASCRIPT, 'js': Icons.JAVASCRIPT,
            'typescript': Icons.TYPESCRIPT, 'ts': Icons.TYPESCRIPT,
            'rust': Icons.RUST, 'rs': Icons.RUST,
            'go': Icons.GO, 'golang': Icons.GO,
            'java': Icons.JAVA,
            'ruby': Icons.RUBY, 'rb': Icons.RUBY,
            'php': Icons.PHP,
            'swift': Icons.SWIFT,
            'docker': Icons.DOCKER, 'dockerfile': Icons.DOCKER,
            'bash': Icons.TERMINAL, 'sh': Icons.TERMINAL, 'shell': Icons.TERMINAL,
            'sql': Icons.DATABASE,
            'mermaid': Icons.CHART,
        }
        icon = icon_map.get(language.lower(), Icons.CODE) if self.config.use_icons else ""
        
        # Header del bloque
        header_text = f" {icon} {lang_display} " if icon else f" {lang_display} "
        header_len = TextUtils.visible_length(header_text)
        fill = width - header_len - 4
        
        result.append("")
        result.append(
            f"{self.scheme.border}{self.box['tl']}{self.box['h']}"
            f"{self.scheme.code_keyword}{header_text}{AnsiCode.RESET}"
            f"{self.scheme.border}{self.box['h'] * fill}{self.box['tr']}{AnsiCode.RESET}"
        )
        
        # Contenido con syntax highlighting
        for idx, line in enumerate(content):
            line_num = ""
            if self.config.enable_line_numbers:
                line_num = f"{self.scheme.text_dim}{idx + 1:4} {AnsiCode.RESET}"
            
            if self.config.enable_syntax_highlight and language:
                highlighted = self.highlighter.highlight(line, language)
            else:
                highlighted = f"{self.scheme.code_text}{line}{AnsiCode.RESET}"
            
            result.append(
                f"{self.scheme.border}{self.box['v']}{AnsiCode.RESET}"
                f"{line_num} {highlighted}"
            )
        
        # Footer del bloque
        result.append(
            f"{self.scheme.border}{self.box['bl']}{self.box['h'] * (width - 2)}"
            f"{self.box['br']}{AnsiCode.RESET}"
        )
        result.append("")
        
        return '\n'.join(result)
    
    def _handle_math_block(self, lines: List[str], start: int) -> Tuple[str, int]:
        """Maneja bloques matemáticos $$...$$"""
        if not self.config.enable_math:
            return "", 1
        
        i = start + 1
        content = []
        
        while i < len(lines):
            if Patterns.MATH_BLOCK.match(lines[i].strip()):
                i += 1
                break
            content.append(lines[i])
            i += 1
        
        consumed = i - start
        
        # Renderizar bloque matemático
        result = []
        width = self.config.width
        
        result.append("")
        result.append(
            f"{self.scheme.border}{self.box['tl']}{self.box['h']} 📐 MATH "
            f"{self.box['h'] * (width - 11)}{self.box['tr']}{AnsiCode.RESET}"
        )
        
        for line in content:
            # Centrar contenido matemático
            centered = line.center(width - 4)
            result.append(
                f"{self.scheme.border}{self.box['v']}{AnsiCode.RESET}"
                f"{self.scheme.accent} {centered} {AnsiCode.RESET}"
                f"{self.scheme.border}{self.box['v']}{AnsiCode.RESET}"
            )
        
        result.append(
            f"{self.scheme.border}{self.box['bl']}{self.box['h'] * (width - 2)}"
            f"{self.box['br']}{AnsiCode.RESET}"
        )
        result.append("")
        
        return '\n'.join(result), consumed
    
    def _handle_table(self, lines: List[str], start: int) -> Tuple[str, int]:
        """Maneja tablas Markdown"""
        if not self.config.enable_tables:
            # Simplemente devolver las líneas sin formato
            i = start
            while i < len(lines) and self._is_table_line(lines[i]):
                i += 1
            return '\n'.join(lines[start:i]), i - start
        
        # Recoger todas las líneas de la tabla
        table_lines = []
        i = start
        
        while i < len(lines) and self._is_table_line(lines[i]):
            table_lines.append(lines[i])
            i += 1
        
        consumed = i - start
        
        if len(table_lines) < 2:
            return '\n'.join(table_lines), consumed
        
        return self._render_table(table_lines), consumed
    
    def _render_table(self, lines: List[str]) -> str:
        """Renderiza una tabla completa con bordes Unicode"""
        # Parsear filas
        rows = []
        alignments = []
        separator_idx = -1
        
        for idx, line in enumerate(lines):
            # Limpiar y dividir por |
            line = line.strip()
            if line.startswith('|'):
                line = line[1:]
            if line.endswith('|'):
                line = line[:-1]
            
            cells = [cell.strip() for cell in line.split('|')]
            
            # Detectar fila separadora
            if all(re.match(r'^:?-+:?$', cell) for cell in cells):
                separator_idx = idx
                # Extraer alineaciones
                for cell in cells:
                    if cell.startswith(':') and cell.endswith(':'):
                        alignments.append('center')
                    elif cell.endswith(':'):
                        alignments.append('right')
                    else:
                        alignments.append('left')
                continue
            
            rows.append(cells)
        
        if not rows:
            return ""
        
        # Normalizar número de columnas
        num_cols = max(len(row) for row in rows)
        for row in rows:
            while len(row) < num_cols:
                row.append("")
        
        # Asegurar que tenemos suficientes alineaciones
        while len(alignments) < num_cols:
            alignments.append('left')
        
        # Calcular anchos de columna
        col_widths = []
        for col_idx in range(num_cols):
            max_width = 0
            for row in rows:
                cell_len = TextUtils.visible_length(row[col_idx])
                if cell_len > max_width:
                    max_width = cell_len
            col_widths.append(max_width + 2)  # +2 para padding
        
        # Construir tabla
        result = []
        border = self.scheme.table_border
        header_style = self.scheme.table_header
        
        # Línea superior
        top = f"{border}{self.box['tl']}"
        top += f"{self.box['tt']}".join([self.box['h'] * w for w in col_widths])
        top += f"{self.box['tr']}{AnsiCode.RESET}"
        result.append(top)
        
        for row_idx, row in enumerate(rows):
            # Renderizar celdas
            cells_rendered = []
            for col_idx, cell in enumerate(row):
                width = col_widths[col_idx] - 2  # sin padding
                align = alignments[col_idx] if col_idx < len(alignments) else 'left'
                
                # Renderizar contenido inline
                content = self._render_inline(cell)
                content_visible = TextUtils.visible_length(cell)
                
                # Aplicar alineación
                padding = width - content_visible
                if align == 'center':
                    left_pad = padding // 2
                    right_pad = padding - left_pad
                    formatted = ' ' * left_pad + content + ' ' * right_pad
                elif align == 'right':
                    formatted = ' ' * padding + content
                else:
                    formatted = content + ' ' * padding
                
                # Estilo para header
                if row_idx == 0 and separator_idx > 0:
                    formatted = f"{header_style}{formatted}{AnsiCode.RESET}"
                
                cells_rendered.append(f" {formatted} ")
            
            line = f"{border}{self.box['v']}{AnsiCode.RESET}"
            line += f"{border}{self.box['v']}{AnsiCode.RESET}".join(cells_rendered)
            line += f"{border}{self.box['v']}{AnsiCode.RESET}"
            result.append(line)
            
            # Separador después del header
            if row_idx == 0 and separator_idx > 0:
                sep = f"{border}{self.box['lt']}"
                sep += f"{self.box['cr']}".join([self.box['h'] * w for w in col_widths])
                sep += f"{self.box['rt']}{AnsiCode.RESET}"
                result.append(sep)
        
        # Línea inferior
        bottom = f"{border}{self.box['bl']}"
        bottom += f"{self.box['bt']}".join([self.box['h'] * w for w in col_widths])
        bottom += f"{self.box['br']}{AnsiCode.RESET}"
        result.append(bottom)
        
        return '\n'.join(result)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Renderizado de líneas individuales
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_line(self, line: str) -> str:
        """Renderiza una línea individual de Markdown"""
        
        # Línea vacía
        if not line.strip():
            return ""
        
        # Headers
        header_match = Patterns.HEADER.match(line)
        if header_match:
            return self._render_header(
                len(header_match.group(1)), 
                header_match.group(2)
            )
        
        # Horizontal rules
        if Patterns.HR.match(line):
            return self._render_hr()
        
        # Blockquotes (incluyendo alertas GFM)
        quote_match = Patterns.BLOCKQUOTE.match(line)
        if quote_match:
            return self._render_blockquote(line)
        
        # Listas de tareas
        task_match = Patterns.TASK_LIST.match(line)
        if task_match and self.config.enable_task_lists:
            return self._render_task_item(
                task_match.group(1),  # indent
                task_match.group(3),  # checkbox state
                task_match.group(4)   # content
            )
        
        # Listas no ordenadas
        ul_match = Patterns.UNORDERED_LIST.match(line)
        if ul_match:
            return self._render_unordered_item(
                ul_match.group(1),  # indent
                ul_match.group(3)   # content
            )
        
        # Listas ordenadas
        ol_match = Patterns.ORDERED_LIST.match(line)
        if ol_match:
            return self._render_ordered_item(
                ol_match.group(1),  # indent
                ol_match.group(2),  # number
                ol_match.group(4)   # content
            )
        
        # Definition lists
        if self.config.enable_definition_lists:
            def_match = Patterns.DEFINITION_LIST.match(line)
            if def_match:
                return self._render_definition(def_match.group(1))
        
        # Línea de referencia (no renderizar)
        if Patterns.LINK_REF_DEF.match(line):
            return ""
        if Patterns.FOOTNOTE_DEF.match(line):
            return ""
        if Patterns.ABBR_DEF.match(line):
            return ""
        
        # Párrafo normal
        return self._render_paragraph(line)
    
    def _render_header(self, level: int, content: str) -> str:
        """Renderiza un encabezado H1-H6"""
        # Actualizar contador
        self.ctx.heading_count[level] += 1
        
        # Renderizar contenido inline
        rendered_content = self._render_inline(content)
        width = self.config.width
        
        # Estilos según nivel
        if level == 1:
            # H1: Título principal con caja doble
            line = BoxChars.DH * width
            return (
                f"\n{self.scheme.h1}{line}\n"
                f"  {AnsiCode.BOLD}{rendered_content.upper()}\n"
                f"{line}{AnsiCode.RESET}\n"
            )
        
        elif level == 2:
            # H2: Subtítulo con línea inferior
            underline = self.box['h'] * (width // 2)
            return (
                f"\n{self.scheme.h2}{AnsiCode.BOLD}{rendered_content}{AnsiCode.RESET}\n"
                f"{self.scheme.text_dim}{underline}{AnsiCode.RESET}"
            )
        
        elif level == 3:
            # H3: Con símbolo
            return f"\n{self.scheme.h3}{AnsiCode.BOLD}◆ {rendered_content}{AnsiCode.RESET}"
        
        elif level == 4:
            # H4: Con símbolo hueco
            return f"\n{self.scheme.h4}{AnsiCode.BOLD}◇ {rendered_content}{AnsiCode.RESET}"
        
        elif level == 5:
            # H5: Con flecha
            return f"\n{self.scheme.h5}{AnsiCode.BOLD}▸ {rendered_content}{AnsiCode.RESET}"
        
        else:
            # H6: Dim
            return f"\n{self.scheme.h6}{AnsiCode.BOLD}{rendered_content}{AnsiCode.RESET}"
    
    def _render_hr(self) -> str:
        """Renderiza una línea horizontal"""
        width = self.config.width
        return f"\n{self.scheme.hr}{self.box['h'] * width}{AnsiCode.RESET}\n"
    
    def _render_blockquote(self, line: str) -> str:
        """Renderiza una cita o alerta GFM"""
        # Contar profundidad y extraer contenido
        depth = 0
        remaining = line
        
        while remaining.strip().startswith('>'):
            depth += 1
            remaining = remaining.strip()[1:].strip()
        
        content = remaining
        
        # Verificar si es una alerta GFM
        if self.config.enable_alerts:
            alert_match = Patterns.GH_ALERT.match(content)
            if alert_match:
                alert_type = alert_match.group(1).upper()
                return self._render_alert(alert_type)
        
        # Cita normal
        prefix = ""
        for i in range(depth):
            if i == 0:
                prefix += f"{self.scheme.quote_border}{self.box['v']}{AnsiCode.RESET} "
            else:
                prefix += f"{self.scheme.text_dim}{self.box['v']}{AnsiCode.RESET} "
        
        rendered_content = self._render_inline(content)
        return f"{prefix}{self.scheme.quote}{rendered_content}{AnsiCode.RESET}"
    
    def _render_alert(self, alert_type: str) -> str:
        """Renderiza una alerta/admonition estilo GitHub"""
        color_map = {
            'NOTE': (self.scheme.alert_note, Icons.INFO, "Note"),
            'TIP': (self.scheme.alert_tip, Icons.TIP, "Tip"),
            'IMPORTANT': (self.scheme.alert_important, Icons.IMPORTANT, "Important"),
            'WARNING': (self.scheme.alert_warning, Icons.WARNING, "Warning"),
            'CAUTION': (self.scheme.alert_caution, Icons.CAUTION, "Caution"),
        }
        
        color, icon, title = color_map.get(
            alert_type, 
            (self.scheme.info, Icons.INFO, alert_type.title())
        )
        
        if self.config.use_icons:
            return f"{self.scheme.quote_border}{self.box['v']}{AnsiCode.RESET} {color}{AnsiCode.BOLD}{icon} {title}{AnsiCode.RESET}"
        else:
            return f"{self.scheme.quote_border}{self.box['v']}{AnsiCode.RESET} {color}{AnsiCode.BOLD}[{title}]{AnsiCode.RESET}"
    
    def _render_task_item(self, indent: str, state: str, content: str) -> str:
        """Renderiza un elemento de lista de tareas"""
        is_done = state.lower() == 'x'
        
        if is_done:
            checkbox = f"{self.scheme.checkbox_done}{BoxChars.CHECKBOX_CHECKED}{AnsiCode.RESET}"
            text_style = f"{self.scheme.text_dim}{AnsiCode.STRIKETHROUGH}"
        else:
            checkbox = f"{self.scheme.checkbox_pending}{BoxChars.CHECKBOX_EMPTY}{AnsiCode.RESET}"
            text_style = ""
        
        rendered_content = self._render_inline(content)
        return f"{indent}{checkbox} {text_style}{rendered_content}{AnsiCode.RESET}"
    
    def _render_unordered_item(self, indent: str, content: str) -> str:
        """Renderiza un elemento de lista no ordenada"""
        indent_level = len(indent) // self.config.list_indent
        
        if indent_level == 0:
            bullet = f"{self.scheme.bullet}{BoxChars.BULLET}{AnsiCode.RESET}"
        elif indent_level == 1:
            bullet = f"{self.scheme.bullet_secondary}{BoxChars.BULLET_HOLLOW}{AnsiCode.RESET}"
        else:
            bullet = f"{self.scheme.text_dim}{BoxChars.BULLET_TRIANGLE}{AnsiCode.RESET}"
        
        rendered_content = self._render_inline(content)
        return f"{indent}{bullet} {rendered_content}"
    
    def _render_ordered_item(self, indent: str, number: str, content: str) -> str:
        """Renderiza un elemento de lista ordenada"""
        rendered_content = self._render_inline(content)
        return f"{indent}{self.scheme.number}{number}.{AnsiCode.RESET} {rendered_content}"
    
    def _render_definition(self, content: str) -> str:
        """Renderiza una definición en lista de definiciones"""
        rendered_content = self._render_inline(content)
        return f"   {self.scheme.text_dim}→{AnsiCode.RESET} {rendered_content}"
    
    def _render_paragraph(self, line: str) -> str:
        """Renderiza un párrafo normal"""
        rendered = self._render_inline(line)
        
        # Word wrap si está habilitado
        if self.config.enable_word_wrap:
            # Por ahora, devolver sin wrap (el wrap completo requiere
            # preservar códigos ANSI, lo cual es más complejo)
            pass
        
        return rendered
    
    def _render_footnotes(self) -> str:
        """Renderiza todas las notas al pie al final del documento"""
        if not self.ctx.footnotes:
            return ""
        
        result = ["\n", self._render_hr()]
        result.append(f"{self.scheme.text_dim}Footnotes:{AnsiCode.RESET}\n")
        
        for idx, (fn_id, content) in enumerate(self.ctx.footnotes.items(), 1):
            superscript = TextUtils.to_superscript(str(idx))
            rendered_content = self._render_inline(content)
            result.append(f"  {superscript} {rendered_content}")
        
        return '\n'.join(result)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Renderizado inline
    # ─────────────────────────────────────────────────────────────────────────
    
    def _render_inline(self, text: str) -> str:
        """Renderiza formateo inline (negrita, cursiva, código, links, etc.)"""
        if not text:
            return ""
        
        # Procesar escapes primero
        text = Patterns.ESCAPE.sub(r'\1', text)
        
        # Código inline (procesar primero para proteger contenido)
        text = Patterns.INLINE_CODE.sub(
            lambda m: self._format_inline_code(m.group(1)), 
            text
        )
        
        # Matemáticas inline
        if self.config.enable_math:
            text = Patterns.INLINE_MATH.sub(
                lambda m: f"{self.scheme.accent}{m.group(1)}{AnsiCode.RESET}",
                text
            )
        
        # Imágenes (antes que links)
        text = Patterns.IMAGE.sub(
            lambda m: self._format_image(m.group(1), m.group(2)),
            text
        )
        
        # Links
        text = Patterns.LINK.sub(
            lambda m: self._format_link(m.group(1), m.group(2)),
            text
        )
        
        # Link references
        text = Patterns.LINK_REF.sub(
            lambda m: self._format_link_ref(m.group(1), m.group(2)),
            text
        )
        
        # Autolinks
        text = Patterns.AUTOLINK.sub(
            lambda m: f"{self.scheme.link}{m.group(1)}{AnsiCode.RESET}",
            text
        )
        
        # Email autolinks
        text = Patterns.EMAIL_AUTOLINK.sub(
            lambda m: f"{self.scheme.link}{m.group(1)}{AnsiCode.RESET}",
            text
        )
        
        # URLs planas
        text = Patterns.URL_PLAIN.sub(
            lambda m: f"{self.scheme.link}{m.group(1)}{AnsiCode.RESET}",
            text
        )
        
        # Bold + Italic
        text = Patterns.BOLD_ITALIC.sub(
            lambda m: f"{AnsiCode.BOLD}{AnsiCode.ITALIC}{m.group(2)}{AnsiCode.RESET}",
            text
        )
        
        # Bold
        text = Patterns.BOLD.sub(
            lambda m: f"{AnsiCode.BOLD}{m.group(2)}{AnsiCode.RESET}",
            text
        )
        
        # Italic
        text = Patterns.ITALIC.sub(
            lambda m: f"{AnsiCode.ITALIC}{m.group(2)}{AnsiCode.RESET}",
            text
        )
        
        # Strikethrough
        text = Patterns.STRIKETHROUGH.sub(
            lambda m: f"{AnsiCode.STRIKETHROUGH}{m.group(1)}{AnsiCode.RESET}",
            text
        )
        
        # HTML inline elements
        text = Patterns.UNDERLINE.sub(
            lambda m: f"{AnsiCode.UNDERLINE}{m.group(1)}{AnsiCode.RESET}",
            text
        )
        
        text = Patterns.MARK.sub(
            lambda m: f"{AnsiCode.BG_YELLOW}{AnsiCode.BLACK}{m.group(1)}{AnsiCode.RESET}",
            text
        )
        
        text = Patterns.KBD.sub(
            lambda m: f"{AnsiCode.REVERSE} {m.group(1)} {AnsiCode.RESET}",
            text
        )
        
        text = Patterns.INS.sub(
            lambda m: f"{AnsiCode.UNDERLINE}{self.scheme.success}{m.group(1)}{AnsiCode.RESET}",
            text
        )
        
        text = Patterns.DEL.sub(
            lambda m: f"{AnsiCode.STRIKETHROUGH}{self.scheme.error}{m.group(1)}{AnsiCode.RESET}",
            text
        )
        
        # Superscript / Subscript
        text = Patterns.SUPERSCRIPT.sub(
            lambda m: TextUtils.to_superscript(m.group(1)),
            text
        )
        
        text = Patterns.SUBSCRIPT.sub(
            lambda m: TextUtils.to_subscript(m.group(1)),
            text
        )
        
        # Footnote references
        if self.config.enable_footnotes:
            text = Patterns.FOOTNOTE_REF.sub(
                lambda m: self._format_footnote_ref(m.group(1)),
                text
            )
        
        # Abreviaciones
        if self.config.enable_abbreviations:
            for abbr, full in self.ctx.abbreviations.items():
                pattern = re.compile(rf'\b{re.escape(abbr)}\b')
                text = pattern.sub(
                    f"{AnsiCode.UNDERLINE}{abbr}{AnsiCode.RESET}",
                    text
                )
        
        # Entidades HTML
        text = self._decode_html_entities(text)
        
        return text
    
    def _format_inline_code(self, code: str) -> str:
        """Formatea código inline"""
        return (
            f"{self.scheme.code_bg} "
            f"{self.scheme.code_text}{code}"
            f"{AnsiCode.RESET}{self.scheme.code_bg} "
            f"{AnsiCode.RESET}"
        )
    
    def _format_image(self, alt: str, url: str) -> str:
        """Formatea una imagen"""
        icon = Icons.IMAGE if self.config.use_icons else "[IMG]"
        return f"{icon} {self.scheme.text_dim}[{alt}]({url}){AnsiCode.RESET}"
    
    def _format_link(self, text: str, url: str) -> str:
        """Formatea un link"""
        return f"{self.scheme.link}{text}{AnsiCode.RESET}"
    
    def _format_link_ref(self, text: str, ref: str) -> str:
        """Formatea un link de referencia"""
        ref_id = ref.lower() if ref else text.lower()
        if ref_id in self.ctx.link_references:
            return f"{self.scheme.link}{text}{AnsiCode.RESET}"
        return f"[{text}][{ref}]"
    
    def _format_footnote_ref(self, fn_id: str) -> str:
        """Formatea una referencia a nota al pie"""
        self.ctx.footnote_counter += 1
        superscript = TextUtils.to_superscript(str(self.ctx.footnote_counter))
        return f"{self.scheme.link}{superscript}{AnsiCode.RESET}"
    
    def _decode_html_entities(self, text: str) -> str:
        """Decodifica entidades HTML comunes"""
        entities = {
            '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"',
            '&apos;': "'", '&nbsp;': ' ', '&copy;': '©', '&reg;': '®',
            '&trade;': '™', '&mdash;': '—', '&ndash;': '–', '&hellip;': '…',
            '&laquo;': '«', '&raquo;': '»', '&bull;': '•', '&middot;': '·',
            '&deg;': '°', '&plusmn;': '±', '&times;': '×', '&divide;': '÷',
            '&euro;': '€', '&pound;': '£', '&yen;': '¥', '&cent;': '¢',
        }
        
        for entity, char in entities.items():
            text = text.replace(entity, char)
        
        # Entidades numéricas
        def replace_numeric(m):
            try:
                code = m.group(1)
                if code.startswith('x') or code.startswith('X'):
                    return chr(int(code[1:], 16))
                return chr(int(code))
            except (ValueError, OverflowError):
                return m.group(0)
        
        text = re.sub(r'&#([xX]?[0-9a-fA-F]+);', replace_numeric, text)
        
        return text


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 7: FUNCIONES DE CONVENIENCIA Y API PÚBLICA
# ══════════════════════════════════════════════════════════════════════════════

# Instancia global con configuración por defecto
_default_renderer: Optional[MarkdownRenderer] = None


def get_renderer(config: RendererConfig = None) -> MarkdownRenderer:
    """Obtiene o crea el renderizador global"""
    global _default_renderer
    
    if config is not None:
        return MarkdownRenderer(config)
    
    if _default_renderer is None:
        _default_renderer = MarkdownRenderer()
    
    return _default_renderer


def render_markdown(text: str, **kwargs) -> str:
    """
    Renderiza texto Markdown a formato de terminal.
    
    Args:
        text: Texto en formato Markdown
        **kwargs: Opciones de configuración (ver RendererConfig)
        
    Returns:
        Texto formateado con códigos ANSI
        
    Example:
        >>> print(render_markdown("# Hello **World**"))
        >>> print(render_markdown("- Item 1\\n- Item 2", theme=Theme.DRACULA))
    """
    if kwargs:
        config = RendererConfig(**kwargs)
        renderer = MarkdownRenderer(config)
    else:
        renderer = get_renderer()
    
    return renderer.render(text)


def print_markdown(text: str, **kwargs) -> None:
    """
    Renderiza e imprime texto Markdown.
    
    Args:
        text: Texto en formato Markdown
        **kwargs: Opciones de configuración
    """
    print(render_markdown(text, **kwargs))


def render_file(filepath: str, **kwargs) -> str:
    """
    Renderiza un archivo Markdown.
    
    Args:
        filepath: Ruta al archivo .md
        **kwargs: Opciones de configuración
        
    Returns:
        Texto formateado con códigos ANSI
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return render_markdown(content, **kwargs)


def print_file(filepath: str, **kwargs) -> None:
    """
    Renderiza e imprime un archivo Markdown.
    
    Args:
        filepath: Ruta al archivo .md
        **kwargs: Opciones de configuración
    """
    print(render_file(filepath, **kwargs))


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 8: COMPONENTES ESPECIALES
# ══════════════════════════════════════════════════════════════════════════════

class ProgressBar:
    """Genera barras de progreso para Markdown"""
    
    @staticmethod
    def render(progress: float, width: int = 20, 
               style: str = 'default') -> str:
        """
        Renderiza una barra de progreso.
        
        Args:
            progress: Valor entre 0 y 1
            width: Ancho de la barra
            style: 'default', 'blocks', 'gradient', 'emoji'
        """
        progress = max(0, min(1, progress))
        filled = int(progress * width)
        empty = width - filled
        
        styles = {
            'default': ('█', '░'),
            'blocks': ('▓', '░'),
            'thin': ('━', '─'),
            'dots': ('●', '○'),
            'squares': ('■', '□'),
        }
        
        filled_char, empty_char = styles.get(style, styles['default'])
        
        # Color según progreso
        if progress < 0.3:
            color = AnsiCode.BRIGHT_RED
        elif progress < 0.7:
            color = AnsiCode.BRIGHT_YELLOW
        else:
            color = AnsiCode.BRIGHT_GREEN
        
        bar = filled_char * filled + AnsiCode.DIM + empty_char * empty + AnsiCode.RESET
        percentage = f"{progress * 100:.1f}%"
        
        return f"{color}[{bar}]{AnsiCode.RESET} {percentage}"
    
    @staticmethod
    def render_gradient(progress: float, width: int = 20) -> str:
        """Renderiza una barra de progreso con gradiente"""
        progress = max(0, min(1, progress))
        
        # Caracteres de bloque parcial
        blocks = ' ▏▎▍▌▋▊▉█'
        
        filled_blocks = progress * width
        full_blocks = int(filled_blocks)
        partial = filled_blocks - full_blocks
        partial_idx = int(partial * 8)
        
        result = '█' * full_blocks
        if partial_idx > 0 and full_blocks < width:
            result += blocks[partial_idx]
        result = result.ljust(width)
        
        # Gradiente de color
        colors = []
        for i in range(width):
            ratio = i / width
            if ratio < 0.5:
                r = int(255 * ratio * 2)
                g = 255
            else:
                r = 255
                g = int(255 * (1 - (ratio - 0.5) * 2))
            colors.append(AnsiCode.rgb(r, g, 0))
        
        output = ""
        for i, char in enumerate(result):
            if i < len(colors):
                output += colors[i] + char
        
        return f"[{output}{AnsiCode.RESET}] {progress * 100:.1f}%"


class Badge:
    """Genera badges estilo GitHub para terminal"""
    
    @staticmethod
    def render(label: str, value: str, color: str = 'blue') -> str:
        """
        Renderiza un badge.
        
        Args:
            label: Texto de la etiqueta
            value: Texto del valor
            color: Color del valor ('blue', 'green', 'red', 'yellow', etc.)
        """
        color_map = {
            'blue': AnsiCode.bg_rgb(0, 123, 255),
            'green': AnsiCode.bg_rgb(40, 167, 69),
            'red': AnsiCode.bg_rgb(220, 53, 69),
            'yellow': AnsiCode.bg_rgb(255, 193, 7),
            'orange': AnsiCode.bg_rgb(253, 126, 20),
            'purple': AnsiCode.bg_rgb(111, 66, 193),
            'pink': AnsiCode.bg_rgb(232, 62, 140),
            'gray': AnsiCode.bg_rgb(108, 117, 125),
            'success': AnsiCode.bg_rgb(40, 167, 69),
            'warning': AnsiCode.bg_rgb(255, 193, 7),
            'danger': AnsiCode.bg_rgb(220, 53, 69),
            'info': AnsiCode.bg_rgb(23, 162, 184),
        }
        
        bg_label = AnsiCode.bg_rgb(85, 85, 85)
        bg_value = color_map.get(color, color_map['blue'])
        
        return (
            f"{bg_label}{AnsiCode.WHITE} {label} {AnsiCode.RESET}"
            f"{bg_value}{AnsiCode.WHITE} {value} {AnsiCode.RESET}"
        )
    
    @staticmethod
    def version(version: str) -> str:
        """Badge de versión"""
        return Badge.render("version", version, "blue")
    
    @staticmethod
    def license(license_type: str) -> str:
        """Badge de licencia"""
        return Badge.render("license", license_type, "green")
    
    @staticmethod
    def build(status: str) -> str:
        """Badge de estado de build"""
        color = "green" if status.lower() in ("passing", "success") else "red"
        return Badge.render("build", status, color)
    
    @staticmethod
    def coverage(percentage: float) -> str:
        """Badge de cobertura de código"""
        if percentage >= 80:
            color = "green"
        elif percentage >= 60:
            color = "yellow"
        else:
            color = "red"
        return Badge.render("coverage", f"{percentage:.0f}%", color)


class Tree:
    """Genera árboles de directorios para terminal"""
    
    BRANCH = "├── "
    LAST_BRANCH = "└── "
    PIPE = "│   "
    SPACE = "    "
    
    @staticmethod
    def render(structure: Dict[str, Any], prefix: str = "") -> str:
        """
        Renderiza un árbol de estructura.
        
        Args:
            structure: Diccionario con la estructura (strings = archivos, dicts = carpetas)
            prefix: Prefijo para la indentación
            
        Example:
            >>> tree = {
            ...     "src": {
            ...         "main.py": None,
            ...         "utils": {
            ...             "helpers.py": None,
            ...         }
            ...     },
            ...     "README.md": None
            ... }
            >>> print(Tree.render(tree))
        """
        lines = []
        items = list(structure.items())
        
        for i, (name, value) in enumerate(items):
            is_last = i == len(items) - 1
            branch = Tree.LAST_BRANCH if is_last else Tree.BRANCH
            
            # Determinar icono
            if isinstance(value, dict):
                icon = Icons.FOLDER
            else:
                # Icono según extensión
                ext = name.split('.')[-1].lower() if '.' in name else ''
                icon_map = {
                    'py': Icons.PYTHON,
                    'js': Icons.JAVASCRIPT,
                    'ts': Icons.TYPESCRIPT,
                    'rs': Icons.RUST,
                    'go': Icons.GO,
                    'java': Icons.JAVA,
                    'rb': Icons.RUBY,
                    'php': Icons.PHP,
                    'md': Icons.BOOK,
                    'json': Icons.CONFIG,
                    'yaml': Icons.CONFIG,
                    'yml': Icons.CONFIG,
                    'toml': Icons.CONFIG,
                    'dockerfile': Icons.DOCKER,
                }
                icon = icon_map.get(ext, Icons.FILE)
            
            lines.append(f"{prefix}{branch}{icon} {name}")
            
            if isinstance(value, dict):
                extension = Tree.SPACE if is_last else Tree.PIPE
                lines.append(Tree.render(value, prefix + extension))
        
        return '\n'.join(lines)


class Diff:
    """Renderiza diffs con colores"""
    
    @staticmethod
    def render(diff_text: str) -> str:
        """
        Renderiza texto de diff con colores.
        
        Args:
            diff_text: Texto de diff (formato unified)
        """
        lines = []
        
        for line in diff_text.split('\n'):
            if line.startswith('+++') or line.startswith('---'):
                lines.append(f"{AnsiCode.BOLD}{line}{AnsiCode.RESET}")
            elif line.startswith('@@'):
                lines.append(f"{AnsiCode.BRIGHT_CYAN}{line}{AnsiCode.RESET}")
            elif line.startswith('+'):
                lines.append(f"{AnsiCode.BRIGHT_GREEN}{line}{AnsiCode.RESET}")
            elif line.startswith('-'):
                lines.append(f"{AnsiCode.BRIGHT_RED}{line}{AnsiCode.RESET}")
            else:
                lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def side_by_side(old: str, new: str, width: int = 80) -> str:
        """
        Renderiza diff lado a lado.
        
        Args:
            old: Texto original
            new: Texto nuevo
            width: Ancho total
        """
        half_width = width // 2 - 2
        old_lines = old.split('\n')
        new_lines = new.split('\n')
        max_lines = max(len(old_lines), len(new_lines))
        
        result = []
        separator = f" {AnsiCode.DIM}│{AnsiCode.RESET} "
        
        for i in range(max_lines):
            left = old_lines[i] if i < len(old_lines) else ""
            right = new_lines[i] if i < len(new_lines) else ""
            
            # Truncar si es necesario
            left = TextUtils.truncate(left, half_width)
            right = TextUtils.truncate(right, half_width)
            
            # Padding
            left = TextUtils.pad_visible(left, half_width)
            right = TextUtils.pad_visible(right, half_width)
            
            # Color según diferencias
            if i >= len(old_lines):
                right = f"{AnsiCode.BRIGHT_GREEN}{right}{AnsiCode.RESET}"
            elif i >= len(new_lines):
                left = f"{AnsiCode.BRIGHT_RED}{left}{AnsiCode.RESET}"
            elif old_lines[i] != (new_lines[i] if i < len(new_lines) else ""):
                left = f"{AnsiCode.BRIGHT_RED}{left}{AnsiCode.RESET}"
                right = f"{AnsiCode.BRIGHT_GREEN}{right}{AnsiCode.RESET}"
            
            result.append(f"{left}{separator}{right}")
        
        return '\n'.join(result)


class Spinner:
    """Caracteres para spinners animados"""
    
    DOTS = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    LINE = ['|', '/', '-', '\\']
    CIRCLE = ['◐', '◓', '◑', '◒']
    SQUARE = ['◰', '◳', '◲', '◱']
    ARROW = ['←', '↖', '↑', '↗', '→', '↘', '↓', '↙']
    BOUNCE = ['⠁', '⠂', '⠄', '⠂']
    GROWING = ['▁', '▃', '▄', '▅', '▆', '▇', '█', '▇', '▆', '▅', '▄', '▃']
    CLOCK = ['🕛', '🕐', '🕑', '🕒', '🕓', '🕔', '🕕', '🕖', '🕗', '🕘', '🕙', '🕚']
    MOON = ['🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘']
    EARTH = ['🌍', '🌎', '🌏']


class Chart:
    """Genera gráficos simples para terminal"""
    
    @staticmethod
    def bar_horizontal(data: Dict[str, float], width: int = 40, 
                       show_values: bool = True) -> str:
        """
        Genera un gráfico de barras horizontal.
        
        Args:
            data: Diccionario {etiqueta: valor}
            width: Ancho máximo de las barras
            show_values: Mostrar valores numéricos
        """
        if not data:
            return ""
        
        max_val = max(data.values())
        max_label_len = max(len(str(k)) for k in data.keys())
        
        lines = []
        colors = [
            AnsiCode.BRIGHT_BLUE, AnsiCode.BRIGHT_GREEN, 
            AnsiCode.BRIGHT_YELLOW, AnsiCode.BRIGHT_MAGENTA,
            AnsiCode.BRIGHT_CYAN, AnsiCode.BRIGHT_RED,
        ]
        
        for i, (label, value) in enumerate(data.items()):
            bar_len = int((value / max_val) * width) if max_val > 0 else 0
            color = colors[i % len(colors)]
            
            bar = BoxChars.FULL * bar_len
            padded_label = label.rjust(max_label_len)
            
            line = f"{padded_label} {color}{bar}{AnsiCode.RESET}"
            if show_values:
                line += f" {value}"
            
            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def bar_vertical(data: Dict[str, float], height: int = 10,
                     bar_width: int = 3) -> str:
        """
        Genera un gráfico de barras vertical.
        
        Args:
            data: Diccionario {etiqueta: valor}
            height: Altura máxima
            bar_width: Ancho de cada barra
        """
        if not data:
            return ""
        
        max_val = max(data.values())
        items = list(data.items())
        
        lines = []
        
        for row in range(height, 0, -1):
            line_parts = []
            for label, value in items:
                bar_height = int((value / max_val) * height) if max_val > 0 else 0
                if bar_height >= row:
                    line_parts.append(BoxChars.FULL * bar_width)
                else:
                    line_parts.append(' ' * bar_width)
            lines.append(' '.join(line_parts))
        
        # Línea base
        lines.append(BoxChars.H * (len(items) * (bar_width + 1) - 1))
        
        # Etiquetas
        labels = ' '.join(label[:bar_width].center(bar_width) for label, _ in items)
        lines.append(labels)
        
        return '\n'.join(lines)
    
    @staticmethod
    def sparkline(values: List[float], width: int = None) -> str:
        """
        Genera un sparkline (mini gráfico de línea).
        
        Args:
            values: Lista de valores numéricos
            width: Ancho máximo (None = usar todos los valores)
        """
        return TextUtils.create_sparkline(values, width)
    
    @staticmethod
    def pie_simple(data: Dict[str, float], radius: int = 4) -> str:
        """
        Genera una representación simple de gráfico de pie.
        
        Nota: Los gráficos de pie en terminal son limitados,
        esto genera una representación textual.
        """
        total = sum(data.values())
        if total == 0:
            return ""
        
        lines = []
        colors = [
            AnsiCode.BRIGHT_RED, AnsiCode.BRIGHT_GREEN, 
            AnsiCode.BRIGHT_BLUE, AnsiCode.BRIGHT_YELLOW,
            AnsiCode.BRIGHT_MAGENTA, AnsiCode.BRIGHT_CYAN,
        ]
        
        for i, (label, value) in enumerate(data.items()):
            percentage = (value / total) * 100
            color = colors[i % len(colors)]
            
            # Barra proporcional
            bar_len = int(percentage / 5)  # 20 chars = 100%
            bar = BoxChars.FULL * bar_len
            
            lines.append(
                f"{color}{BoxChars.CIRCLE}{AnsiCode.RESET} "
                f"{label}: {color}{bar}{AnsiCode.RESET} {percentage:.1f}%"
            )
        
        return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 9: CLI Y PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

def _detect_terminal_width() -> int:
    """Detecta el ancho de la terminal"""
    try:
        import shutil
        width = shutil.get_terminal_size().columns
        return max(40, min(width, 200))
    except Exception:
        return 80


def main():
    """Punto de entrada para CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Renderizador de Markdown para terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python markdown_renderer.py README.md
  python markdown_renderer.py README.md --theme dracula
  cat README.md | python markdown_renderer.py -
  echo "# Hello" | python markdown_renderer.py --width 60
        """
    )
    
    parser.add_argument(
        'file', 
        nargs='?', 
        default='-',
        help='Archivo Markdown a renderizar (- para stdin)'
    )
    
    parser.add_argument(
        '-w', '--width',
        type=int,
        default=_detect_terminal_width(),
        help='Ancho de salida (default: ancho de terminal)'
    )
    
    parser.add_argument(
        '-t', '--theme',
        choices=['nvidia', 'monokai', 'dracula', 'nord', 'solarized', 
                 'gruvbox', 'onedark', 'github', 'catppuccin'],
        default='nvidia',
        help='Tema de colores (default: nvidia)'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Desactivar colores'
    )
    
    parser.add_argument(
        '--no-emoji',
        action='store_true',
        help='No reemplazar shortcodes de emoji'
    )
    
    parser.add_argument(
        '-n', '--line-numbers',
        action='store_true',
        help='Mostrar números de línea en bloques de código'
    )
    
    parser.add_argument(
        '--compact',
        action='store_true',
        help='Modo compacto (menos espaciado)'
    )
    
    args = parser.parse_args()
    
    # Leer entrada
    if args.file == '-':
        content = sys.stdin.read()
    else:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"Error: Archivo no encontrado: {args.file}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error leyendo archivo: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Mapeo de temas
    theme_map = {
        'nvidia': Theme.NVIDIA,
        'monokai': Theme.MONOKAI,
        'dracula': Theme.DRACULA,
        'nord': Theme.NORD,
        'solarized': Theme.SOLARIZED_DARK,
        'gruvbox': Theme.GRUVBOX,
        'onedark': Theme.ONE_DARK,
        'github': Theme.GITHUB_DARK,
        'catppuccin': Theme.CATPPUCCIN,
    }
    
    # Configurar renderer
    config = RendererConfig(
        width=args.width,
        theme=theme_map.get(args.theme, Theme.NVIDIA),
        use_color=not args.no_color,
        enable_emoji=not args.no_emoji,
        enable_line_numbers=args.line_numbers,
        compact_mode=args.compact,
    )
    
    # Renderizar e imprimir
    renderer = MarkdownRenderer(config)
    output = renderer.render(content)
    print(output)


if __name__ == "__main__":
    main()