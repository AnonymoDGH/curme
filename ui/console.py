"""
NVIDIA CODE - Consola e Interfaz (Versión Mejorada)
Sistema completo de utilidades para interfaz de terminal
"""

import os
import sys
import re
import time
import shutil
import difflib
import unicodedata
import threading
from typing import Optional, List, Any, Dict, Tuple, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from .colors import Colors
from .markdown import render_markdown, MarkdownRenderer

C = Colors()


# ─────────────────────────────────────────────────────────────────────
#  Enumeraciones y Configuración
# ─────────────────────────────────────────────────────────────────────

class Alignment(Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class BorderStyle(Enum):
    SINGLE = "single"
    DOUBLE = "double"
    ROUNDED = "rounded"
    BOLD = "bold"
    DASHED = "dashed"
    HEAVY_DASHED = "heavy_dashed"
    ASCII = "ascii"
    NONE = "none"


class Severity(Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    CRITICAL = "critical"


@dataclass
class BoxStyle:
    border: BorderStyle = BorderStyle.ROUNDED
    color: str = ""
    padding_x: int = 1
    padding_y: int = 0
    width: Optional[int] = None
    align: Alignment = Alignment.LEFT
    title_align: Alignment = Alignment.LEFT
    dim_border: bool = False
    shadow: bool = False


@dataclass
class TableStyle:
    border: BorderStyle = BorderStyle.ROUNDED
    color: str = ""
    header_color: str = ""
    stripe: bool = True
    stripe_color: str = ""
    compact: bool = False
    align: List[Alignment] = field(default_factory=list)
    max_col_width: int = 50
    min_col_width: int = 3


# ─────────────────────────────────────────────────────────────────────
#  Motor de Bordes
# ─────────────────────────────────────────────────────────────────────

BORDER_CHARS = {
    BorderStyle.SINGLE: {
        'tl': '┌', 'tr': '┐', 'bl': '└', 'br': '┘',
        'h': '─', 'v': '│', 'lt': '├', 'rt': '┤',
        'tt': '┬', 'bt': '┴', 'cr': '┼',
    },
    BorderStyle.DOUBLE: {
        'tl': '╔', 'tr': '╗', 'bl': '╚', 'br': '╝',
        'h': '═', 'v': '║', 'lt': '╠', 'rt': '╣',
        'tt': '╦', 'bt': '╩', 'cr': '╬',
    },
    BorderStyle.ROUNDED: {
        'tl': '╭', 'tr': '╮', 'bl': '╰', 'br': '╯',
        'h': '─', 'v': '│', 'lt': '├', 'rt': '┤',
        'tt': '┬', 'bt': '┴', 'cr': '┼',
    },
    BorderStyle.BOLD: {
        'tl': '┏', 'tr': '┓', 'bl': '┗', 'br': '┛',
        'h': '━', 'v': '┃', 'lt': '┣', 'rt': '┫',
        'tt': '┳', 'bt': '┻', 'cr': '╋',
    },
    BorderStyle.DASHED: {
        'tl': '┌', 'tr': '┐', 'bl': '└', 'br': '┘',
        'h': '┄', 'v': '┆', 'lt': '├', 'rt': '┤',
        'tt': '┬', 'bt': '┴', 'cr': '┼',
    },
    BorderStyle.HEAVY_DASHED: {
        'tl': '┏', 'tr': '┓', 'bl': '┗', 'br': '┛',
        'h': '┅', 'v': '┇', 'lt': '┣', 'rt': '┫',
        'tt': '┳', 'bt': '┻', 'cr': '╋',
    },
    BorderStyle.ASCII: {
        'tl': '+', 'tr': '+', 'bl': '+', 'br': '+',
        'h': '-', 'v': '|', 'lt': '+', 'rt': '+',
        'tt': '+', 'bt': '+', 'cr': '+',
    },
}


# ─────────────────────────────────────────────────────────────────────
#  Iconos y Glyphs
# ─────────────────────────────────────────────────────────────────────

SEVERITY_THEME: Dict[str, Tuple[str, str, str]] = {
    # severity:  (color,             icon, label)
    "success":   (C.BRIGHT_GREEN,    "✔",  "OK"),
    "error":     (C.BRIGHT_RED,      "✖",  "ERROR"),
    "warning":   (C.BRIGHT_YELLOW,   "⚠",  "WARN"),
    "info":      (C.BRIGHT_CYAN,     "ℹ",  "INFO"),
    "debug":     (C.DIM,             "⚙",  "DEBUG"),
    "critical":  (C.BRIGHT_RED,      "◈",  "CRIT"),
    "loading":   (C.BRIGHT_BLUE,     "◐",  "…"),
    "question":  (C.BRIGHT_MAGENTA,  "?",  "ASK"),
    "important": (C.BRIGHT_YELLOW,   "★",  "NOTE"),
    "hint":      (C.BRIGHT_BLUE,     "»",  "HINT"),
    "done":      (C.BRIGHT_GREEN,    "●",  "DONE"),
    "skip":      (C.DIM,             "○",  "SKIP"),
    "pending":   (C.YELLOW,          "◌",  "PEND"),
}

FILE_ICONS: Dict[str, str] = {
    'py':     '🐍', 'pyw':    '🐍', 'pyx':    '🐍',
    'js':     '📜', 'jsx':    '⚛️',  'mjs':    '📜',
    'ts':     '📘', 'tsx':    '⚛️',
    'json':   '📋', 'jsonc':  '📋',
    'yaml':   '📝', 'yml':    '📝', 'toml':   '📝',
    'md':     '📖', 'mdx':    '📖', 'rst':    '📖',
    'txt':    '📄', 'log':    '📃', 'csv':    '📊',
    'html':   '🌐', 'htm':    '🌐', 'xml':    '🌐',
    'css':    '🎨', 'scss':   '🎨', 'sass':   '🎨', 'less': '🎨',
    'jpg':    '🖼️',  'jpeg':   '🖼️',  'png':    '🖼️',
    'gif':    '🖼️',  'svg':    '🖼️',  'webp':   '🖼️',  'ico':  '🖼️',
    'pdf':    '📕', 'doc':    '📕', 'docx':   '📕',
    'zip':    '📦', 'tar':    '📦', 'gz':     '📦', '7z':   '📦', 'rar': '📦',
    'exe':    '⚙️',  'msi':    '⚙️',  'app':    '⚙️',
    'sh':     '🔧', 'bash':   '🔧', 'zsh':    '🔧', 'fish': '🔧',
    'bat':    '🔧', 'ps1':    '🔧', 'cmd':    '🔧',
    'c':      '🔵', 'h':      '🔵', 'cpp':    '🔵', 'hpp':  '🔵',
    'rs':     '🦀', 'go':     '🐹', 'rb':     '💎', 'java': '☕',
    'sql':    '🗃️',  'db':     '🗃️',  'sqlite': '🗃️',
    'env':    '🔒', 'pem':    '🔒', 'key':    '🔒',
    'lock':   '🔐', 'git':    '🌿', 'gitignore': '🌿',
    'docker': '🐳', 'dockerfile': '🐳',
    'cfg':    '⚙️',  'ini':    '⚙️',  'conf':   '⚙️',
}

SPINNER_FRAMES = {
    "dots":    ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "line":    ["─", "\\", "│", "/"],
    "arc":     ["◜", "◠", "◝", "◞", "◡", "◟"],
    "circle":  ["◐", "◓", "◑", "◒"],
    "pulse":   ["░", "▒", "▓", "█", "▓", "▒"],
    "bounce":  ["⠁", "⠂", "⠄", "⠂"],
    "arrows":  ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
    "grow":    ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"],
    "toggle":  ["⊶", "⊷"],
    "nvidia":  ["▰▱▱", "▰▰▱", "▰▰▰", "▱▰▰", "▱▱▰", "▱▱▱"],
}


# ─────────────────────────────────────────────────────────────────────
#  Clase principal Console
# ─────────────────────────────────────────────────────────────────────

class Console:
    """Utilidades avanzadas de interfaz para la terminal."""

    # ── Helpers básicos ──────────────────────────────────────────────

    @staticmethod
    def get_terminal_size() -> Tuple[int, int]:
        size = shutil.get_terminal_size((80, 24))
        return size.columns, size.lines

    @staticmethod
    def clear():
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def strip_ansi(text: str) -> str:
        return re.compile(r'\x1b\[[0-9;]*m').sub('', text)

    @staticmethod
    def visible_length(text: str) -> int:
        clean = Console.strip_ansi(text)
        width = 0
        for ch in clean:
            if unicodedata.east_asian_width(ch) in ('F', 'W'):
                width += 2
            else:
                width += 1
        return width

    @staticmethod
    def _effective_width(requested: Optional[int] = None, margin: int = 2) -> int:
        tw, _ = Console.get_terminal_size()
        if requested:
            return min(requested, tw - margin)
        return min(100, tw - margin)

    # ── Texto padding / truncamiento ─────────────────────────────────

    @staticmethod
    def pad_text(
        text: str,
        width: int,
        align: Alignment = Alignment.LEFT,
        fill: str = ' ',
    ) -> str:
        pad = max(0, width - Console.visible_length(text))
        if align == Alignment.RIGHT:
            return fill * pad + text
        if align == Alignment.CENTER:
            lp = pad // 2
            return fill * lp + text + fill * (pad - lp)
        return text + fill * pad

    @staticmethod
    def truncate_text(text: str, max_width: int, suffix: str = '…') -> str:
        if Console.visible_length(text) <= max_width:
            return text
        target = max_width - Console.visible_length(suffix)
        result, vis = [], 0
        i = 0
        while i < len(text) and vis < target:
            if text[i:i + 2] == '\x1b[':
                end = text.find('m', i)
                if end != -1:
                    result.append(text[i:end + 1])
                    i = end + 1
                    continue
            result.append(text[i])
            vis += 1
            i += 1
        return ''.join(result) + suffix + C.RESET

    @staticmethod
    def _wrap_line(line: str, max_width: int) -> List[str]:
        if Console.visible_length(line) <= max_width:
            return [line]
        words = line.split(' ')
        lines: List[str] = []
        cur: List[str] = []
        cur_len = 0
        for w in words:
            wl = Console.visible_length(w)
            sep = 1 if cur else 0
            if cur_len + wl + sep <= max_width:
                cur.append(w)
                cur_len += wl + sep
            else:
                if cur:
                    lines.append(' '.join(cur))
                cur = [w]
                cur_len = wl
        if cur:
            lines.append(' '.join(cur))
        return lines or [line[:max_width]]

    @staticmethod
    def _wrap_text(text: str, width: int) -> List[str]:
        result: List[str] = []
        for line in text.split('\n'):
            result.extend(Console._wrap_line(line, width))
        return result

    # ── Reglas horizontales ──────────────────────────────────────────

    @staticmethod
    def rule(
        label: str = "",
        char: str = "─",
        color: str = "",
        width: Optional[int] = None,
        align: Alignment = Alignment.CENTER,
    ):
        w = Console._effective_width(width, 0)
        clr = color or C.DIM
        if not label:
            print(f"{clr}{char * w}{C.RESET}")
            return
        tag = f" {label} "
        tag_len = Console.visible_length(tag)
        remaining = max(0, w - tag_len)
        if align == Alignment.LEFT:
            lp, rp = 2, remaining - 2
        elif align == Alignment.RIGHT:
            lp, rp = remaining - 2, 2
        else:
            lp = remaining // 2
            rp = remaining - lp
        print(f"{clr}{char * max(0, lp)}{C.RESET}{C.BOLD}{tag}{C.RESET}{clr}{char * max(0, rp)}{C.RESET}")

    # ── Mensajes de estado ───────────────────────────────────────────

    @staticmethod
    def print_status(
        message: str,
        status: str = "info",
        bold_message: bool = False,
    ):
        color, icon, _ = SEVERITY_THEME.get(status, (C.DIM, "•", ""))
        msg = f"{C.BOLD}{message}{C.RESET}" if bold_message else message
        print(f" {color}{icon}{C.RESET}  {msg}")

    @staticmethod
    def success(msg: str):
        Console.print_status(msg, "success")

    @staticmethod
    def error(msg: str):
        Console.print_status(msg, "error")

    @staticmethod
    def warning(msg: str):
        Console.print_status(msg, "warning")

    @staticmethod
    def info(msg: str):
        Console.print_status(msg, "info")

    @staticmethod
    def debug(msg: str):
        Console.print_status(msg, "debug")

    # ── Badges / Etiquetas ───────────────────────────────────────────

    @staticmethod
    def badge(
        text: str,
        color: str = "",
        bg: str = "",
    ) -> str:
        clr = color or C.BRIGHT_WHITE
        background = bg or ""
        return f"{background}{clr} {text} {C.RESET}"

    @staticmethod
    def print_badges(badges: List[Tuple[str, str]]):
        parts = []
        for label, status in badges:
            color, _, _ = SEVERITY_THEME.get(status, (C.DIM, "", ""))
            parts.append(f"{color}[{label}]{C.RESET}")
        print(" ".join(parts))

    # ── Cajas y Paneles ──────────────────────────────────────────────

    @staticmethod
    def print_box(
        title: str = "",
        content: str = "",
        style: BoxStyle = None,
        color: str = None,
    ):
        if style is None:
            style = BoxStyle()
        if style.border == BorderStyle.NONE:
            Console._print_box_no_border(title, content)
            return

        w = Console._effective_width(style.width)
        bc = color or style.color or C.NVIDIA_GREEN
        dim = C.DIM if style.dim_border else ""
        b = BORDER_CHARS[style.border]
        inner = w - 2
        pad_x = style.padding_x

        def hline(l, m, r):
            print(f"{dim}{bc}{l}{m * inner}{r}{C.RESET}")

        def empty_row():
            print(f"{dim}{bc}{b['v']}{C.RESET}{' ' * inner}{dim}{bc}{b['v']}{C.RESET}")

        def content_row(text: str, align: Alignment = style.align):
            usable = inner - pad_x * 2
            padded = Console.pad_text(text, usable, align)
            lp = ' ' * pad_x
            rp = ' ' * max(0, inner - Console.visible_length(padded) - pad_x)
            print(
                f"{dim}{bc}{b['v']}{C.RESET}"
                f"{lp}{padded}{rp}"
                f"{dim}{bc}{b['v']}{C.RESET}"
            )

        # ── Top border
        if title:
            title_rendered = f" {C.BOLD}{title}{C.RESET} "
            title_vl = Console.visible_length(title_rendered)
            if style.title_align == Alignment.LEFT:
                gap_l = 2
            elif style.title_align == Alignment.RIGHT:
                gap_l = max(0, inner - title_vl - 2)
            else:
                gap_l = max(0, (inner - title_vl) // 2)
            gap_r = max(0, inner - gap_l - title_vl)
            print(
                f"{dim}{bc}{b['tl']}"
                f"{b['h'] * gap_l}{C.RESET}"
                f"{title_rendered}"
                f"{dim}{bc}{b['h'] * gap_r}"
                f"{b['tr']}{C.RESET}"
            )
        else:
            hline(b['tl'], b['h'], b['tr'])

        # ── Padding top
        for _ in range(style.padding_y):
            empty_row()

        # ── Contenido
        rendered = content
        if content and any(m in content for m in ['```', '**', '##', '- ', '> ']):
            try:
                rendered = render_markdown(content)
            except Exception:
                pass

        for raw_line in rendered.split('\n'):
            usable = inner - pad_x * 2
            if Console.visible_length(raw_line) > usable:
                for wl in Console._wrap_line(raw_line, usable):
                    content_row(wl)
            else:
                content_row(raw_line)

        # ── Padding bottom
        for _ in range(style.padding_y):
            empty_row()

        # ── Bottom border
        hline(b['bl'], b['h'], b['br'])

        # ── Shadow (optional)
        if style.shadow:
            print(f" {C.DIM}{'░' * inner} {C.RESET}")

    @staticmethod
    def _print_box_no_border(title: str, content: str):
        if title:
            print(f"\n  {C.BOLD}{title}{C.RESET}")
            print(f"  {C.DIM}{'─' * Console.visible_length(title)}{C.RESET}")
        for line in content.split('\n'):
            print(f"  {line}")
        print()

    @staticmethod
    def panel(
        content: str,
        title: str = "",
        subtitle: str = "",
        border: BorderStyle = BorderStyle.ROUNDED,
        color: str = "",
        width: Optional[int] = None,
        padding: int = 1,
        expand: bool = False,
    ):
        bc = color or C.DIM
        w = Console._effective_width(width)
        if expand:
            w, _ = Console.get_terminal_size()
            w -= 2
        b = BORDER_CHARS[border]
        inner = w - 2

        def hline(l, r, fill=b['h']):
            print(f"{bc}{l}{fill * inner}{r}{C.RESET}")

        def text_row(t: str, align: Alignment = Alignment.LEFT):
            usable = inner - 2
            padded = Console.pad_text(t, usable, align)
            print(f"{bc}{b['v']}{C.RESET} {padded} {bc}{b['v']}{C.RESET}")

        # top
        if title:
            tag = f" {C.BOLD}{title}{C.RESET} "
            tvl = Console.visible_length(tag)
            gl = 2
            gr = max(0, inner - gl - tvl)
            print(f"{bc}{b['tl']}{b['h'] * gl}{C.RESET}{tag}{bc}{b['h'] * gr}{b['tr']}{C.RESET}")
        else:
            hline(b['tl'], b['tr'])

        # padding
        for _ in range(padding):
            text_row("")

        # content
        for raw in content.split('\n'):
            usable = inner - 2
            for wl in Console._wrap_line(raw, usable):
                text_row(wl)

        # padding
        for _ in range(padding):
            text_row("")

        # bottom
        if subtitle:
            tag = f" {C.DIM}{subtitle}{C.RESET} "
            tvl = Console.visible_length(tag)
            gl = max(0, inner - tvl - 2)
            print(f"{bc}{b['bl']}{b['h'] * gl}{C.RESET}{tag}{bc}{b['h'] * 2}{b['br']}{C.RESET}")
        else:
            hline(b['bl'], b['br'])

    # ── Banner / Callout ─────────────────────────────────────────────

    @staticmethod
    def banner(
        message: str,
        severity: str = "info",
        width: Optional[int] = None,
    ):
        color, icon, label = SEVERITY_THEME.get(severity, (C.DIM, "•", ""))
        w = Console._effective_width(width)
        inner = w - 2
        b = BORDER_CHARS[BorderStyle.ROUNDED]

        header_tag = f" {icon} {label} "
        hl = Console.visible_length(header_tag)
        print(f"{color}{b['tl']}{b['h'] * 2}{C.RESET}{C.BOLD}{color}{header_tag}{C.RESET}{color}{b['h'] * max(0, inner - hl - 2)}{b['tr']}{C.RESET}")

        for raw in message.split('\n'):
            for wl in Console._wrap_line(raw, inner - 2):
                padded = Console.pad_text(wl, inner - 2)
                print(f"{color}{b['v']}{C.RESET} {padded} {color}{b['v']}{C.RESET}")

        print(f"{color}{b['bl']}{b['h'] * inner}{b['br']}{C.RESET}")

    # ── Tablas ───────────────────────────────────────────────────────

    @staticmethod
    def print_table(
        headers: List[str],
        rows: List[List[Any]],
        style: Union[BorderStyle, TableStyle] = None,
        color: str = None,
        align: List[Alignment] = None,
        col_widths: List[int] = None,
        title: str = "",
        footer: str = "",
        max_rows: Optional[int] = None,
    ):
        if not headers and not rows:
            return

        if isinstance(style, BorderStyle):
            ts = TableStyle(border=style)
        elif isinstance(style, TableStyle):
            ts = style
        else:
            ts = TableStyle()

        bc = color or ts.color or C.DIM
        hc = ts.header_color or C.BOLD
        b = BORDER_CHARS[ts.border]

        num_cols = len(headers) if headers else (len(rows[0]) if rows else 0)
        aligns = align or ts.align or [Alignment.LEFT] * num_cols
        while len(aligns) < num_cols:
            aligns.append(Alignment.LEFT)

        # ── Calcular anchos
        if not col_widths:
            col_widths = Console._calculate_column_widths(headers, rows, ts)

        # ── Helpers
        def sep(l, m, r, ch=b['h']):
            segs = [ch * (cw + 2) for cw in col_widths]
            print(f"{bc}{l}{m.join(segs)}{r}{C.RESET}")

        def data_row(cells: List[str], colors_: str = "", is_header=False):
            parts = [f"{bc}{b['v']}{C.RESET}"]
            for i, cell in enumerate(cells[:num_cols]):
                cell_str = str(cell)
                if Console.visible_length(cell_str) > col_widths[i]:
                    cell_str = Console.truncate_text(cell_str, col_widths[i])
                cell_color = hc if is_header else colors_
                padded = Console.pad_text(
                    f"{cell_color}{cell_str}{C.RESET}",
                    col_widths[i],
                    aligns[i],
                )
                parts.append(f" {padded} {bc}{b['v']}{C.RESET}")
            print(''.join(parts))

        # ── Título
        if title:
            total_w = sum(col_widths) + num_cols * 3 + 1
            Console.rule(title, color=bc, width=total_w)

        # ── Dibujar
        sep(b['tl'], b['tt'], b['tr'])

        if headers:
            data_row(headers, is_header=True)
            sep(b['lt'], b['cr'], b['rt'])

        display_rows = rows[:max_rows] if max_rows else rows
        for idx, row in enumerate(display_rows):
            row_color = ts.stripe_color or C.DIM if (ts.stripe and idx % 2 == 1) else ""
            data_row(row, row_color)

        if max_rows and len(rows) > max_rows:
            remaining = len(rows) - max_rows
            msg = f"… {remaining} filas más …"
            total_inner = sum(col_widths) + (num_cols - 1) * 3 + 2
            centered = Console.pad_text(f"{C.DIM}{msg}{C.RESET}", total_inner, Alignment.CENTER)
            print(f"{bc}{b['v']}{C.RESET}{centered}{bc}{b['v']}{C.RESET}")

        sep(b['bl'], b['bt'], b['br'])

        if footer:
            total_w = sum(col_widths) + num_cols * 3 + 1
            print(f"{C.DIM}{Console.pad_text(footer, total_w, Alignment.RIGHT)}{C.RESET}")

    @staticmethod
    def _calculate_column_widths(
        headers: List[str],
        rows: List[List[Any]],
        style: TableStyle = None,
    ) -> List[int]:
        if not headers and not rows:
            return []
        s = style or TableStyle()
        num_cols = len(headers) if headers else len(rows[0])
        widths = [s.min_col_width] * num_cols

        if headers:
            for i, h in enumerate(headers):
                widths[i] = max(widths[i], Console.visible_length(str(h)))
        for row in rows:
            for i, cell in enumerate(row[:num_cols]):
                widths[i] = max(widths[i], Console.visible_length(str(cell)))

        widths = [min(w, s.max_col_width) for w in widths]

        tw, _ = Console.get_terminal_size()
        total = sum(widths) + num_cols * 3 + 1
        if total > tw:
            scale = (tw - num_cols * 3 - 1) / sum(widths)
            widths = [max(s.min_col_width, int(w * scale)) for w in widths]

        return widths

    # ── Key-Value (detalles) ─────────────────────────────────────────

    @staticmethod
    def print_kv(
        data: Dict[str, Any],
        title: str = "",
        color: str = "",
        separator: str = ":",
        indent: int = 2,
    ):
        clr = color or C.BRIGHT_WHITE
        if title:
            print(f"\n{C.BOLD}{title}{C.RESET}")
            Console.rule(width=Console.visible_length(title) + 4)

        max_key_len = max((Console.visible_length(str(k)) for k in data), default=0)
        prefix = ' ' * indent

        for key, value in data.items():
            padded_key = Console.pad_text(str(key), max_key_len, Alignment.RIGHT)
            print(f"{prefix}{clr}{padded_key}{C.RESET} {C.DIM}{separator}{C.RESET} {value}")

    # ── Salida de herramienta ────────────────────────────────────────

    @staticmethod
    def print_tool_output(
        tool_name: str,
        output: str,
        status: str = "success",
        duration: Optional[float] = None,
    ):
        color, icon, _ = SEVERITY_THEME.get(status, (C.DIM, "●", ""))
        w = Console._effective_width()
        b = BORDER_CHARS[BorderStyle.ROUNDED]
        inner = w - 2

        # ── Header
        header_text = f"{color}{icon}{C.RESET} {C.BOLD}{tool_name}{C.RESET}"
        if duration is not None:
            header_text += f"  {C.DIM}({duration:.1f}s){C.RESET}"
        hvl = Console.visible_length(header_text)
        dash_r = max(0, inner - hvl - 3)
        print(f"{color}{b['tl']}─{C.RESET} {header_text} {color}{'─' * dash_r}{b['tr']}{C.RESET}")

        # ── Contenido
        if output:
            rendered = output
            try:
                if any(m in output for m in ['```', '**', '##', '- ', '1. ', '> ']):
                    rendered = render_markdown(output)
            except Exception:
                pass

            for raw_line in rendered.split('\n'):
                for wl in Console._wrap_line(raw_line, inner - 2):
                    print(f"{color}{b['v']}{C.RESET} {wl}")

        # ── Footer
        print(f"{color}{b['bl']}{'─' * inner}{b['br']}{C.RESET}")

    # ── Código ───────────────────────────────────────────────────────

    @staticmethod
    def print_code(
        code: str,
        language: str = "python",
        title: Optional[str] = None,
        line_numbers: bool = True,
        highlight_lines: List[int] = None,
        start_line: int = 1,
    ):
        hl_set = set(highlight_lines or [])
        lines = code.rstrip('\n').split('\n')
        num_w = len(str(start_line + len(lines) - 1))
        w = Console._effective_width()

        # ── Header
        lang_badge = f"{C.DIM}[{language}]{C.RESET}" if language else ""
        label = title or ""
        if label or lang_badge:
            left = f" {C.BOLD}{label}{C.RESET}" if label else ""
            right = f"{lang_badge} " if lang_badge else ""
            mid_len = max(0, w - Console.visible_length(left) - Console.visible_length(right) - 4)
            print(f"{C.DIM}╭─{C.RESET}{left} {C.DIM}{'─' * mid_len}{C.RESET} {right}{C.DIM}─╮{C.RESET}")
        else:
            print(f"{C.DIM}╭{'─' * (w - 2)}╮{C.RESET}")

        # ── Líneas
        rendered = render_markdown(f"```{language}\n{code}\n```")
        rendered_lines = rendered.split('\n')
        # Strip fence lines from rendered
        if rendered_lines and '```' in Console.strip_ansi(rendered_lines[0]):
            rendered_lines = rendered_lines[1:]
        if rendered_lines and '```' in Console.strip_ansi(rendered_lines[-1]):
            rendered_lines = rendered_lines[:-1]

        for i, rline in enumerate(rendered_lines):
            line_num = start_line + i
            is_hl = line_num in hl_set
            bg = f"{C.BG_YELLOW}{C.BLACK}" if is_hl else ""

            if line_numbers:
                num_str = f"{C.DIM}{line_num:>{num_w}} │{C.RESET} "
                gutter = f"{bg}{num_str}"
            else:
                gutter = f"{bg}{C.DIM}│{C.RESET} "

            print(f"{gutter}{rline}{C.RESET}")

        # ── Footer
        print(f"{C.DIM}╰{'─' * (w - 2)}╯{C.RESET}")

    # ── Diff ─────────────────────────────────────────────────────────

    @staticmethod
    def print_diff(
        old: str,
        new: str,
        old_label: str = "original",
        new_label: str = "modified",
        context_lines: int = 3,
    ):
        old_lines = old.split('\n')
        new_lines = new.split('\n')

        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=old_label, tofile=new_label,
            lineterm='', n=context_lines,
        ))

        if not diff:
            Console.print_status("Sin diferencias", "success")
            return

        w = Console._effective_width()
        print(f"{C.DIM}╭{'─' * (w - 2)}╮{C.RESET}")

        for line in diff:
            stripped = line
            if stripped.startswith('+++'):
                print(f"{C.DIM}│{C.RESET} {C.BOLD}{C.GREEN}{stripped}{C.RESET}")
            elif stripped.startswith('---'):
                print(f"{C.DIM}│{C.RESET} {C.BOLD}{C.RED}{stripped}{C.RESET}")
            elif stripped.startswith('@@'):
                pad = Console.pad_text(f"{C.CYAN}{C.BOLD}{stripped}{C.RESET}", w - 4, Alignment.CENTER)
                print(f"{C.DIM}│{C.RESET} {pad}")
            elif stripped.startswith('+'):
                print(f"{C.DIM}│{C.RESET} {C.GREEN}+{stripped[1:]}{C.RESET}")
            elif stripped.startswith('-'):
                print(f"{C.DIM}│{C.RESET} {C.RED}-{stripped[1:]}{C.RESET}")
            else:
                print(f"{C.DIM}│{C.RESET} {C.DIM} {stripped}{C.RESET}")

        print(f"{C.DIM}╰{'─' * (w - 2)}╯{C.RESET}")

        # Stats
        added = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
        removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))
        print(f"  {C.GREEN}+{added}{C.RESET}  {C.RED}-{removed}{C.RESET}")

    # ── Árbol de archivos ────────────────────────────────────────────

    @staticmethod
    def print_tree(
        data: Dict[str, Any],
        indent: str = "",
        is_last: bool = True,
        is_root: bool = True,
        show_size: bool = False,
    ):
        if is_root:
            print(f"\n  {C.BRIGHT_BLUE}📁{C.RESET} {C.BOLD}.{C.RESET}")
            indent = "  "

        items = list(data.items())
        for i, (key, value) in enumerate(items):
            last = i == len(items) - 1
            connector = "└── " if last else "├── "
            child_indent = indent + ("    " if last else "│   ")

            if isinstance(value, dict):
                count = Console._count_tree_items(value)
                meta = f" {C.DIM}({count} items){C.RESET}" if count > 0 else ""
                print(f"{C.DIM}{indent}{connector}{C.RESET}{C.BRIGHT_BLUE}📁{C.RESET} {C.BOLD}{key}{C.RESET}{meta}")
                Console.print_tree(value, child_indent, last, False, show_size)
            else:
                icon = Console._get_file_icon(key)
                size_str = ""
                if show_size and isinstance(value, (int, float)):
                    size_str = f"  {C.DIM}{Console._format_size(value)}{C.RESET}"
                print(f"{C.DIM}{indent}{connector}{C.RESET}{icon} {key}{size_str}")

        if is_root:
            print()

    @staticmethod
    def _count_tree_items(d: Dict) -> int:
        count = 0
        for v in d.values():
            count += 1
            if isinstance(v, dict):
                count += Console._count_tree_items(v)
        return count

    @staticmethod
    def _get_file_icon(filename: str) -> str:
        name_lower = filename.lower()
        ext = name_lower.rsplit('.', 1)[-1] if '.' in name_lower else ''
        # Check full name matches (e.g., Dockerfile)
        full_match = FILE_ICONS.get(name_lower)
        if full_match:
            return full_match
        icon = FILE_ICONS.get(ext, '📄')
        return icon

    @staticmethod
    def _format_size(size_bytes: Union[int, float]) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if abs(size_bytes) < 1024:
                return f"{size_bytes:.1f} {unit}" if unit != 'B' else f"{int(size_bytes)} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    # ── Progreso ─────────────────────────────────────────────────────

    @staticmethod
    def print_progress(
        current: int,
        total: int,
        prefix: str = "",
        suffix: str = "",
        length: int = 40,
        fill: str = "█",
        empty: str = "░",
        show_percent: bool = True,
        show_count: bool = False,
        color: str = "",
    ):
        if total <= 0:
            return
        pct = min(1.0, current / total)
        filled = int(length * pct)

        # Color gradient (green → yellow → red inverted)
        bar_color = color or (
            C.BRIGHT_GREEN if pct >= 0.8
            else C.BRIGHT_YELLOW if pct >= 0.4
            else C.BRIGHT_CYAN
        )

        bar = f"{bar_color}{fill * filled}{C.DIM}{empty * (length - filled)}{C.RESET}"

        parts = []
        if prefix:
            parts.append(prefix)
        parts.append(f"│{bar}│")
        if show_percent:
            parts.append(f"{pct * 100:5.1f}%")
        if show_count:
            parts.append(f"({current}/{total})")
        if suffix:
            parts.append(suffix)

        sys.stdout.write(f"\r{' '.join(parts)}")
        sys.stdout.flush()
        if current >= total:
            print()

    @staticmethod
    def progress_bar(iterable, total: Optional[int] = None, prefix: str = "", length: int = 30):
        """Iterador con barra de progreso."""
        total = total or len(iterable)
        for i, item in enumerate(iterable, 1):
            Console.print_progress(i, total, prefix=prefix, length=length, show_count=True)
            yield item

    # ── Spinner ──────────────────────────────────────────────────────

    @staticmethod
    def spinner(
        message: str = "Procesando",
        style: str = "dots",
        color: str = "",
    ) -> 'SpinnerContext':
        return SpinnerContext(message, style, color)

    # ── Markdown ─────────────────────────────────────────────────────

    @staticmethod
    def print_markdown(text: str, width: Optional[int] = None):
        rendered = render_markdown(text)
        if width:
            lines = []
            for line in rendered.split('\n'):
                lines.extend(Console._wrap_line(line, width))
            print('\n'.join(lines))
        else:
            print(rendered)

    # ── Entradas interactivas ────────────────────────────────────────

    @staticmethod
    def confirm(
        message: str,
        default: bool = False,
        yes_text: str = "Y",
        no_text: str = "n",
    ) -> bool:
        if default:
            hint = f"{C.BOLD}{yes_text}{C.RESET}/{no_text}"
        else:
            hint = f"{yes_text}/{C.BOLD}{no_text}{C.RESET}"

        response = input(
            f" {C.BRIGHT_YELLOW}?{C.RESET}  {message} [{hint}]: "
        ).strip().lower()

        if not response:
            return default
        return response in ('s', 'si', 'sí', 'yes', 'y', '1', 'true')

    @staticmethod
    def prompt(
        message: str,
        default: str = None,
        validator: Optional[Callable[[str], bool]] = None,
        error_message: str = "Entrada inválida. Intenta de nuevo.",
        max_attempts: int = 5,
        password: bool = False,
    ) -> Optional[str]:
        attempts = 0
        default_hint = f" {C.DIM}({default}){C.RESET}" if default else ""

        while attempts < max_attempts:
            if password:
                import getpass
                response = getpass.getpass(
                    f" {C.BRIGHT_CYAN}›{C.RESET}  {message}{default_hint}: "
                ).strip()
            else:
                response = input(
                    f" {C.BRIGHT_CYAN}›{C.RESET}  {message}{default_hint}: "
                ).strip()

            if not response and default:
                response = default

            if not response:
                attempts += 1
                continue

            if validator:
                if validator(response):
                    return response
                Console.print_status(error_message, "error")
                attempts += 1
            else:
                return response

        return None

    @staticmethod
    def select(
        prompt_text: str,
        options: List[str],
        default: int = 0,
        descriptions: List[str] = None,
    ) -> int:
        print(f"\n {C.BRIGHT_WHITE}{prompt_text}{C.RESET}")
        Console.rule(width=Console.visible_length(prompt_text) + 4)

        for i, option in enumerate(options):
            marker = f"{C.NVIDIA_GREEN}❯{C.RESET}" if i == default else " "
            num = f"{C.DIM}{i + 1}.{C.RESET}"
            desc = ""
            if descriptions and i < len(descriptions):
                desc = f"  {C.DIM}— {descriptions[i]}{C.RESET}"
            hl = C.BRIGHT_WHITE if i == default else ""
            print(f"  {marker} {num} {hl}{option}{C.RESET}{desc}")

        print()
        while True:
            response = input(f" {C.CYAN}›{C.RESET} Selecciona [{default + 1}]: ").strip()
            if not response:
                return default
            try:
                choice = int(response) - 1
                if 0 <= choice < len(options):
                    return choice
                Console.print_status("Fuera de rango", "error")
            except ValueError:
                for i, opt in enumerate(options):
                    if opt.lower().startswith(response.lower()):
                        return i
                Console.print_status("Opción no válida", "error")

    @staticmethod
    def multiselect(
        prompt_text: str,
        options: List[str],
        selected: List[int] = None,
    ) -> List[int]:
        sel = set(selected or [])

        print(f"\n {C.BRIGHT_WHITE}{prompt_text}{C.RESET}")
        print(f" {C.DIM}Números separados por espacio/coma. Enter para confirmar.{C.RESET}")
        Console.rule(width=50)

        for i, option in enumerate(options):
            check = f"{C.BRIGHT_GREEN}◉{C.RESET}" if i in sel else f"{C.DIM}○{C.RESET}"
            print(f"  {check} {C.DIM}{i + 1}.{C.RESET} {option}")

        print()
        response = input(f" {C.CYAN}›{C.RESET} ").strip()
        if not response:
            return sorted(sel)

        for part in response.replace(',', ' ').split():
            try:
                num = int(part) - 1
                if 0 <= num < len(options):
                    sel.symmetric_difference_update({num})
            except ValueError:
                continue
        return sorted(sel)

    # ── Columns / Grid ───────────────────────────────────────────────

    @staticmethod
    def print_columns(
        items: List[str],
        num_cols: Optional[int] = None,
        padding: int = 2,
        color: str = "",
    ):
        if not items:
            return
        tw, _ = Console.get_terminal_size()
        max_item_w = max(Console.visible_length(it) for it in items)
        col_w = max_item_w + padding

        if num_cols is None:
            num_cols = max(1, tw // col_w)

        for i in range(0, len(items), num_cols):
            chunk = items[i:i + num_cols]
            parts = []
            for item in chunk:
                padded = Console.pad_text(f"{color}{item}{C.RESET}", col_w)
                parts.append(padded)
            print(''.join(parts))

    # ── Layout ───────────────────────────────────────────────────────

    @staticmethod
    def create_layout(
        sections: List[Tuple[str, str]],
        orientation: str = "vertical",
        gap: int = 1,
    ):
        tw, _ = Console.get_terminal_size()

        if orientation == "vertical":
            for i, (title, content) in enumerate(sections):
                Console.panel(content, title=title, width=tw - 4)
                if i < len(sections) - 1:
                    for _ in range(gap):
                        print()
        else:
            ncols = len(sections)
            col_w = (tw - 4) // ncols
            for title, content in sections:
                Console.panel(content, title=title, width=col_w)

    # ── Mini gráficos ────────────────────────────────────────────────

    @staticmethod
    def sparkline(
        values: List[float],
        color: str = "",
        label: str = "",
    ) -> str:
        if not values:
            return ""
        blocks = " ▁▂▃▄▅▆▇█"
        mn, mx = min(values), max(values)
        rng = mx - mn or 1
        clr = color or C.BRIGHT_CYAN
        spark = ''.join(
            blocks[min(len(blocks) - 1, int((v - mn) / rng * (len(blocks) - 1)))]
            for v in values
        )
        prefix = f"{C.DIM}{label}{C.RESET} " if label else ""
        stats = f" {C.DIM}(min={mn:.1f} max={mx:.1f}){C.RESET}"
        return f"{prefix}{clr}{spark}{C.RESET}{stats}"

    @staticmethod
    def print_sparkline(values: List[float], **kwargs):
        print(Console.sparkline(values, **kwargs))

    @staticmethod
    def bar_chart(
        data: Dict[str, float],
        max_width: int = 40,
        color: str = "",
        show_values: bool = True,
    ):
        if not data:
            return
        clr = color or C.BRIGHT_CYAN
        max_val = max(data.values()) or 1
        max_label = max(Console.visible_length(k) for k in data)

        for label, value in data.items():
            bar_len = int((value / max_val) * max_width)
            padded_label = Console.pad_text(label, max_label, Alignment.RIGHT)
            bar = f"{clr}{'█' * bar_len}{C.RESET}"
            val_str = f" {C.DIM}{value:.1f}{C.RESET}" if show_values else ""
            print(f"  {padded_label} {C.DIM}│{C.RESET} {bar}{val_str}")


# ─────────────────────────────────────────────────────────────────────
#  Spinner Context Manager
# ─────────────────────────────────────────────────────────────────────

class SpinnerContext:
    """Context manager para mostrar un spinner animado."""

    def __init__(self, message: str, style: str = "dots", color: str = ""):
        self.message = message
        self.frames = SPINNER_FRAMES.get(style, SPINNER_FRAMES["dots"])
        self.color = color or C.BRIGHT_CYAN
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.result: Optional[str] = None

    def _spin(self):
        idx = 0
        while not self._stop.is_set():
            frame = self.frames[idx % len(self.frames)]
            sys.stdout.write(f"\r {self.color}{frame}{C.RESET}  {self.message}")
            sys.stdout.flush()
            idx += 1
            self._stop.wait(0.08)
        # Clear line
        sys.stdout.write(f"\r{' ' * (Console.visible_length(self.message) + 10)}\r")
        sys.stdout.flush()

    def update(self, message: str):
        self.message = message

    def __enter__(self):
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)

        if exc_type:
            Console.print_status(f"{self.message} — falló", "error")
        elif self.result:
            Console.print_status(f"{self.message} — {self.result}", "success")
        else:
            Console.print_status(self.message, "success")
        return False


# ─────────────────────────────────────────────────────────────────────
#  Funciones de conveniencia (backward compatibility)
# ─────────────────────────────────────────────────────────────────────

def clear():
    Console.clear()

def print_markdown(text: str):
    Console.print_markdown(text)

def print_tool_output(tool_name: str, output: str):
    Console.print_tool_output(tool_name, output)

def confirm(message: str, default: bool = False) -> bool:
    return Console.confirm(message, default)

def prompt(message: str, default: str = None) -> str:
    return Console.prompt(message, default)