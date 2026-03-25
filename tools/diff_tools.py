# tools/diff_tools.py
"""
NVIDIA CODE — Diff Visual, Parches y Merge

Herramientas para comparación, parcheo y fusión de código con soporte para
múltiples formatos de visualización, diff semántico (AST), y operaciones
seguras con backup automático.
"""

import ast
import difflib
import hashlib
import os
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .base import BaseTool, ToolParameter


# ─── Colores (standalone, sin dependencia de ui.colors) ──────────────────────

class _Colors:
    """
    Colores ANSI autocontenidos con detección de soporte de terminal.
    Evita dependencia dura de ui.colors.
    """

    _ENABLED: Optional[bool] = None

    @classmethod
    def _is_enabled(cls) -> bool:
        if cls._ENABLED is None:
            cls._ENABLED = (
                os.environ.get("NO_COLOR") is None
                and os.environ.get("TERM") != "dumb"
                and hasattr(os, "isatty")
            )
        return cls._ENABLED

    @classmethod
    def _code(cls, code: str) -> str:
        return f"\033[{code}m" if cls._is_enabled() else ""

    # Estilos
    RESET      = property(lambda s: _Colors._code("0"))
    BOLD       = property(lambda s: _Colors._code("1"))
    DIM        = property(lambda s: _Colors._code("2"))
    ITALIC     = property(lambda s: _Colors._code("3"))
    UNDERLINE  = property(lambda s: _Colors._code("4"))

    # Colores
    RED        = property(lambda s: _Colors._code("31"))
    GREEN      = property(lambda s: _Colors._code("32"))
    YELLOW     = property(lambda s: _Colors._code("33"))
    BLUE       = property(lambda s: _Colors._code("34"))
    MAGENTA    = property(lambda s: _Colors._code("35"))
    CYAN       = property(lambda s: _Colors._code("36"))
    WHITE      = property(lambda s: _Colors._code("37"))

    # Colores brillantes
    BRIGHT_RED    = property(lambda s: _Colors._code("91"))
    BRIGHT_GREEN  = property(lambda s: _Colors._code("92"))
    BRIGHT_YELLOW = property(lambda s: _Colors._code("93"))
    BRIGHT_CYAN   = property(lambda s: _Colors._code("96"))

    # Backgrounds
    BG_RED     = property(lambda s: _Colors._code("41"))
    BG_GREEN   = property(lambda s: _Colors._code("42"))
    BG_YELLOW  = property(lambda s: _Colors._code("43"))
    BG_BLUE    = property(lambda s: _Colors._code("44"))

    # NVIDIA
    NVIDIA_GREEN = property(lambda s: _Colors._code("38;5;118"))


C = _Colors()


# ─── Utilidades compartidas ──────────────────────────────────────────────────

def _read_content(source: str) -> Tuple[List[str], str]:
    """
    Lee contenido desde archivo o string inline.

    Returns:
        (líneas, nombre_para_display)
    """
    path = Path(source)
    if path.exists() and path.is_file():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")
        return text.splitlines(keepends=False), str(path)

    # Es contenido inline
    lines = source.splitlines(keepends=False)
    if len(lines) <= 1:
        return lines, "inline"

    # Detectar si la primera línea parece un nombre de archivo
    return lines, "inline"


def _file_hash(path: Path) -> str:
    """SHA-256 truncado de un archivo."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _make_backup(path: Path) -> Optional[Path]:
    """Crea backup con timestamp. Retorna path del backup."""
    if not path.exists():
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(f".{ts}.bak")
    shutil.copy2(path, backup)
    return backup


def _count_diff_stats(
    diff_lines: List[str],
) -> Dict[str, int]:
    """Cuenta estadísticas de un diff unificado."""
    stats = {"added": 0, "removed": 0, "modified": 0, "context": 0, "hunks": 0}

    for line in diff_lines:
        if line.startswith("@@"):
            stats["hunks"] += 1
        elif line.startswith("+") and not line.startswith("+++"):
            stats["added"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            stats["removed"] += 1
        elif not line.startswith(("---", "+++", "@@")):
            stats["context"] += 1

    # Estimación de modificadas (mínimo entre added/removed por hunk)
    stats["modified"] = min(stats["added"], stats["removed"])
    stats["net"] = stats["added"] - stats["removed"]

    return stats


def _word_diff(line_a: str, line_b: str) -> Tuple[str, str]:
    """
    Genera diff a nivel de palabra entre dos líneas.
    Retorna las líneas con marcadores de cambio.
    """
    words_a = re.findall(r"\S+|\s+", line_a)
    words_b = re.findall(r"\S+|\s+", line_b)

    matcher = difflib.SequenceMatcher(None, words_a, words_b)

    result_a: List[str] = []
    result_b: List[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            result_a.extend(words_a[i1:i2])
            result_b.extend(words_b[j1:j2])
        elif tag == "replace":
            old = "".join(words_a[i1:i2])
            new = "".join(words_b[j1:j2])
            result_a.append(f"{C.BG_RED}{C.BOLD}{old}{C.RESET}{C.BRIGHT_RED}")
            result_b.append(f"{C.BG_GREEN}{C.BOLD}{new}{C.RESET}{C.BRIGHT_GREEN}")
        elif tag == "delete":
            old = "".join(words_a[i1:i2])
            result_a.append(f"{C.BG_RED}{C.BOLD}{old}{C.RESET}{C.BRIGHT_RED}")
        elif tag == "insert":
            new = "".join(words_b[j1:j2])
            result_b.append(f"{C.BG_GREEN}{C.BOLD}{new}{C.RESET}{C.BRIGHT_GREEN}")

    return "".join(result_a), "".join(result_b)


# ─── 1. DIFF TOOL ───────────────────────────────────────────────────────────


class DiffTool(BaseTool):
    """
    Muestra diferencias entre dos archivos o fragmentos de código con
    múltiples formatos de visualización y estadísticas detalladas.

    Formatos:
        - unified:    Diff unificado estándar (default)
        - side:       Vista lado a lado
        - inline:     Cambios resaltados dentro de cada línea
        - word:       Diff a nivel de palabra
        - char:       Diff a nivel de carácter
        - summary:    Solo estadísticas, sin detalle
        - html:       Diff en formato HTML
        - patch:      Formato patch aplicable
    """

    name = "diff"
    description = (
        "Muestra diferencias entre dos archivos o código con "
        "múltiples formatos: unified, side-by-side, inline, word, char, summary, html."
    )
    category = "diff"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "file1": ToolParameter(
                name="file1",
                type="string",
                description="Primer archivo/código (original)",
                required=True,
            ),
            "file2": ToolParameter(
                name="file2",
                type="string",
                description="Segundo archivo/código (modificado)",
                required=True,
            ),
            "context": ToolParameter(
                name="context",
                type="integer",
                description="Líneas de contexto alrededor de cambios (default: 3)",
                required=False,
            ),
            "format": ToolParameter(
                name="format",
                type="string",
                description="Formato: unified|side|inline|word|char|summary|html|patch (default: unified)",
                required=False,
            ),
            "ignore_whitespace": ToolParameter(
                name="ignore_whitespace",
                type="boolean",
                description="Ignorar cambios de espacios en blanco (default: false)",
                required=False,
            ),
            "ignore_case": ToolParameter(
                name="ignore_case",
                type="boolean",
                description="Ignorar diferencias de mayúsculas/minúsculas (default: false)",
                required=False,
            ),
            "output": ToolParameter(
                name="output",
                type="string",
                description="Archivo para guardar el diff (opcional)",
                required=False,
            ),
            "width": ToolParameter(
                name="width",
                type="integer",
                description="Ancho para vista side-by-side (default: 120)",
                required=False,
            ),
        }

    def execute(
        self,
        file1: Optional[str] = None,
        file2: Optional[str] = None,
        context: int = 3,
        format: str = "unified",
        ignore_whitespace: bool = False,
        ignore_case: bool = False,
        output: Optional[str] = None,
        width: int = 120,
        **kwargs,
    ) -> str:
        file1 = file1 or kwargs.get("file1", "")
        file2 = file2 or kwargs.get("file2", "")

        if not file1 or not file2:
            return "❌ Se requieren 'file1' y 'file2'."

        # ── Leer contenido ────────────────────────────────────────────────
        try:
            content1, name1 = _read_content(file1)
            content2, name2 = _read_content(file2)
        except Exception as e:
            return f"❌ Error leyendo archivos: {e}"

        # ── Preprocesar ───────────────────────────────────────────────────
        proc1, proc2 = list(content1), list(content2)

        if ignore_whitespace:
            proc1 = [re.sub(r"\s+", " ", line).strip() for line in proc1]
            proc2 = [re.sub(r"\s+", " ", line).strip() for line in proc2]

        if ignore_case:
            proc1 = [line.lower() for line in proc1]
            proc2 = [line.lower() for line in proc2]

        # ── Verificar si son idénticos ────────────────────────────────────
        if proc1 == proc2:
            flags = []
            if ignore_whitespace:
                flags.append("ignore-whitespace")
            if ignore_case:
                flags.append("ignore-case")
            flag_str = f" ({', '.join(flags)})" if flags else ""
            return f"✅ Los archivos son idénticos{flag_str}."

        # ── Generar diff según formato ────────────────────────────────────
        fmt = format.lower().strip()
        generators = {
            "unified":  self._fmt_unified,
            "side":     self._fmt_side_by_side,
            "inline":   self._fmt_inline,
            "word":     self._fmt_word,
            "char":     self._fmt_char,
            "summary":  self._fmt_summary,
            "html":     self._fmt_html,
            "patch":    self._fmt_patch,
        }

        generator = generators.get(fmt)
        if not generator:
            opts = ", ".join(generators.keys())
            return f"❌ Formato '{fmt}' no soportado. Opciones: {opts}"

        result = generator(
            content1, content2, proc1, proc2,
            name1, name2, context, width,
        )

        # ── Guardar si se pide ────────────────────────────────────────────
        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            # Guardar sin códigos ANSI
            clean = re.sub(r"\033\[[0-9;]*m", "", result)
            out_path.write_text(clean, encoding="utf-8")
            result += f"\n\n💾 Diff guardado en: `{output}`"

        return result

    # ── Formato: Unified ──────────────────────────────────────────────────

    def _fmt_unified(
        self, orig, mod, proc1, proc2, name1, name2, context, width,
    ) -> str:
        diff_lines = list(difflib.unified_diff(
            proc1, proc2, fromfile=name1, tofile=name2,
            lineterm="", n=context,
        ))

        stats = _count_diff_stats(diff_lines)

        # Header
        output_parts = [
            f"\n{C.NVIDIA_GREEN}╭─ Diff: {name1} → {name2} {'─' * max(1, 50 - len(name1) - len(name2))}╮{C.RESET}",
            self._stats_bar(stats),
            "",
        ]

        # Diff coloreado
        for line in diff_lines:
            if line.startswith("+++") or line.startswith("---"):
                output_parts.append(f"{C.BOLD}{C.WHITE}{line}{C.RESET}")
            elif line.startswith("+"):
                output_parts.append(f"{C.BRIGHT_GREEN}+{line[1:]}{C.RESET}")
            elif line.startswith("-"):
                output_parts.append(f"{C.BRIGHT_RED}-{line[1:]}{C.RESET}")
            elif line.startswith("@@"):
                # Parsear números de línea
                match = re.match(r"@@ -(\d+),?\d* \+(\d+),?\d* @@(.*)", line)
                if match:
                    hunk_info = f"@@ -{match.group(1)} +{match.group(2)} @@"
                    hunk_ctx = match.group(3)
                    output_parts.append(
                        f"{C.BRIGHT_CYAN}{C.BOLD}{hunk_info}{C.RESET}"
                        f"{C.DIM}{hunk_ctx}{C.RESET}"
                    )
                else:
                    output_parts.append(f"{C.BRIGHT_CYAN}{line}{C.RESET}")
            else:
                output_parts.append(f"{C.DIM} {line}{C.RESET}")

        output_parts.append(
            f"{C.NVIDIA_GREEN}╰{'─' * 52}╯{C.RESET}"
        )

        return "\n".join(output_parts)

    # ── Formato: Side by Side ─────────────────────────────────────────────

    def _fmt_side_by_side(
        self, orig, mod, proc1, proc2, name1, name2, context, width,
    ) -> str:
        half = (width - 7) // 2  # 7 = " │ " + gutter
        line_num_w = max(len(str(len(orig))), len(str(len(mod))), 3)

        # Header
        lines = [
            f"{C.NVIDIA_GREEN}╭{'─' * (width - 2)}╮{C.RESET}",
            f"{C.BOLD}  {'← ' + name1:<{half}s} │ {'→ ' + name2:<{half}s}{C.RESET}",
            f"{C.NVIDIA_GREEN}├{'─' * half}─┼─{'─' * half}┤{C.RESET}",
        ]

        matcher = difflib.SequenceMatcher(None, proc1, proc2)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                # Solo mostrar líneas de contexto alrededor de cambios
                eq_lines = list(range(i1, i2))
                if len(eq_lines) > context * 2 + 1:
                    # Mostrar primeras 'context', separador, últimas 'context'
                    show = eq_lines[:context] + [None] + eq_lines[-context:]
                else:
                    show = eq_lines

                for idx in show:
                    if idx is None:
                        skip = i2 - i1 - context * 2
                        msg = f"··· {skip} líneas iguales ···"
                        lines.append(
                            f"{C.DIM}  {msg:^{half}s} │ {msg:^{half}s}{C.RESET}"
                        )
                    else:
                        left = orig[idx][:half - line_num_w - 1]
                        right = mod[idx][:half - line_num_w - 1] if idx < len(mod) else ""
                        ln = f"{idx + 1:>{line_num_w}}"
                        lines.append(
                            f"{C.DIM}{ln} {left:<{half - line_num_w - 1}s}{C.RESET}"
                            f" │ "
                            f"{C.DIM}{ln} {right:<{half - line_num_w - 1}s}{C.RESET}"
                        )

            elif tag == "replace":
                max_range = max(i2 - i1, j2 - j1)
                for offset in range(max_range):
                    li = i1 + offset
                    lj = j1 + offset

                    if li < i2:
                        left = orig[li][:half - line_num_w - 1]
                        ln_l = f"{li + 1:>{line_num_w}}"
                        left_str = f"{C.BRIGHT_RED}{ln_l} {left:<{half - line_num_w - 1}s}{C.RESET}"
                    else:
                        left_str = f"{' ' * half}"

                    if lj < j2:
                        right = mod[lj][:half - line_num_w - 1]
                        ln_r = f"{lj + 1:>{line_num_w}}"
                        right_str = f"{C.BRIGHT_GREEN}{ln_r} {right:<{half - line_num_w - 1}s}{C.RESET}"
                    else:
                        right_str = f"{' ' * half}"

                    lines.append(f"{left_str} {C.YELLOW}│{C.RESET} {right_str}")

            elif tag == "delete":
                for li in range(i1, i2):
                    left = orig[li][:half - line_num_w - 1]
                    ln = f"{li + 1:>{line_num_w}}"
                    lines.append(
                        f"{C.BRIGHT_RED}{ln} {left:<{half - line_num_w - 1}s}{C.RESET}"
                        f" {C.RED}│{C.RESET} "
                        f"{C.DIM}{' ' * (half - 1)}{C.RESET}"
                    )

            elif tag == "insert":
                for lj in range(j1, j2):
                    right = mod[lj][:half - line_num_w - 1]
                    ln = f"{lj + 1:>{line_num_w}}"
                    lines.append(
                        f"{C.DIM}{' ' * half}{C.RESET}"
                        f" {C.GREEN}│{C.RESET} "
                        f"{C.BRIGHT_GREEN}{ln} {right:<{half - line_num_w - 1}s}{C.RESET}"
                    )

        lines.append(f"{C.NVIDIA_GREEN}╰{'─' * (width - 2)}╯{C.RESET}")

        # Stats
        diff_all = list(difflib.unified_diff(proc1, proc2, lineterm=""))
        stats = _count_diff_stats(diff_all)
        lines.insert(2, self._stats_bar(stats))

        return "\n".join(lines)

    # ── Formato: Inline (cambios resaltados en línea) ─────────────────────

    def _fmt_inline(
        self, orig, mod, proc1, proc2, name1, name2, context, width,
    ) -> str:
        matcher = difflib.SequenceMatcher(None, proc1, proc2)
        lines = [
            f"\n{C.NVIDIA_GREEN}╭─ Inline Diff: {name1} → {name2} ─╮{C.RESET}",
            "",
        ]

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                eq_range = range(i1, i2)
                if len(eq_range) > context * 2 + 1:
                    for idx in list(eq_range[:context]):
                        lines.append(f"{C.DIM}{idx + 1:>4d} │ {orig[idx]}{C.RESET}")
                    skip = len(eq_range) - context * 2
                    lines.append(f"{C.DIM}     │ ··· {skip} líneas iguales ···{C.RESET}")
                    for idx in list(eq_range[-context:]):
                        lines.append(f"{C.DIM}{idx + 1:>4d} │ {orig[idx]}{C.RESET}")
                else:
                    for idx in eq_range:
                        lines.append(f"{C.DIM}{idx + 1:>4d} │ {orig[idx]}{C.RESET}")

            elif tag == "replace":
                for li in range(i1, i2):
                    lines.append(f"{C.BRIGHT_RED}{li + 1:>4d} │ ‒ {orig[li]}{C.RESET}")
                for lj in range(j1, j2):
                    lines.append(f"{C.BRIGHT_GREEN}{lj + 1:>4d} │ + {mod[lj]}{C.RESET}")

            elif tag == "delete":
                for li in range(i1, i2):
                    lines.append(f"{C.BRIGHT_RED}{li + 1:>4d} │ ‒ {orig[li]}{C.RESET}")

            elif tag == "insert":
                for lj in range(j1, j2):
                    lines.append(f"{C.BRIGHT_GREEN}{lj + 1:>4d} │ + {mod[lj]}{C.RESET}")

        lines.append(f"\n{C.NVIDIA_GREEN}╰{'─' * 52}╯{C.RESET}")
        return "\n".join(lines)

    # ── Formato: Word-level ───────────────────────────────────────────────

    def _fmt_word(
        self, orig, mod, proc1, proc2, name1, name2, context, width,
    ) -> str:
        matcher = difflib.SequenceMatcher(None, proc1, proc2)
        lines = [
            f"\n{C.NVIDIA_GREEN}╭─ Word Diff: {name1} → {name2} ─╮{C.RESET}",
            "",
        ]

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                if i2 - i1 > context * 2 + 1:
                    lines.append(f"{C.DIM}     ··· {i2 - i1 - context * 2} líneas iguales ···{C.RESET}")
                continue

            if tag == "replace":
                max_range = max(i2 - i1, j2 - j1)
                for offset in range(max_range):
                    line_a = orig[i1 + offset] if (i1 + offset) < i2 else ""
                    line_b = mod[j1 + offset] if (j1 + offset) < j2 else ""

                    if line_a and line_b:
                        wa, wb = _word_diff(line_a, line_b)
                        ln_a = i1 + offset + 1
                        ln_b = j1 + offset + 1
                        lines.append(f"{C.BRIGHT_RED}{ln_a:>4d} │ ‒ {wa}{C.RESET}")
                        lines.append(f"{C.BRIGHT_GREEN}{ln_b:>4d} │ + {wb}{C.RESET}")
                    elif line_a:
                        lines.append(f"{C.BRIGHT_RED}{i1 + offset + 1:>4d} │ ‒ {line_a}{C.RESET}")
                    else:
                        lines.append(f"{C.BRIGHT_GREEN}{j1 + offset + 1:>4d} │ + {line_b}{C.RESET}")

            elif tag == "delete":
                for li in range(i1, i2):
                    lines.append(f"{C.BRIGHT_RED}{li + 1:>4d} │ ‒ {orig[li]}{C.RESET}")

            elif tag == "insert":
                for lj in range(j1, j2):
                    lines.append(f"{C.BRIGHT_GREEN}{lj + 1:>4d} │ + {mod[lj]}{C.RESET}")

        lines.append(f"\n{C.NVIDIA_GREEN}╰{'─' * 52}╯{C.RESET}")
        return "\n".join(lines)

    # ── Formato: Char-level ───────────────────────────────────────────────

    def _fmt_char(
        self, orig, mod, proc1, proc2, name1, name2, context, width,
    ) -> str:
        matcher = difflib.SequenceMatcher(None, proc1, proc2)
        lines = [
            f"\n{C.NVIDIA_GREEN}╭─ Char Diff: {name1} → {name2} ─╮{C.RESET}",
            "",
        ]

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                if i2 - i1 > context * 2:
                    lines.append(f"{C.DIM}     ··· {i2 - i1} líneas iguales ···{C.RESET}")
                continue

            if tag == "replace":
                for offset in range(max(i2 - i1, j2 - j1)):
                    line_a = orig[i1 + offset] if (i1 + offset) < i2 else ""
                    line_b = mod[j1 + offset] if (j1 + offset) < j2 else ""

                    char_matcher = difflib.SequenceMatcher(None, line_a, line_b)
                    result_a: List[str] = []
                    result_b: List[str] = []

                    for ct, ci1, ci2, cj1, cj2 in char_matcher.get_opcodes():
                        if ct == "equal":
                            result_a.append(line_a[ci1:ci2])
                            result_b.append(line_b[cj1:cj2])
                        elif ct == "replace":
                            result_a.append(f"{C.BG_RED}{C.BOLD}{line_a[ci1:ci2]}{C.RESET}{C.BRIGHT_RED}")
                            result_b.append(f"{C.BG_GREEN}{C.BOLD}{line_b[cj1:cj2]}{C.RESET}{C.BRIGHT_GREEN}")
                        elif ct == "delete":
                            result_a.append(f"{C.BG_RED}{C.BOLD}{line_a[ci1:ci2]}{C.RESET}{C.BRIGHT_RED}")
                        elif ct == "insert":
                            result_b.append(f"{C.BG_GREEN}{C.BOLD}{line_b[cj1:cj2]}{C.RESET}{C.BRIGHT_GREEN}")

                    if line_a:
                        lines.append(f"{C.BRIGHT_RED}   ‒ │ {''.join(result_a)}{C.RESET}")
                    if line_b:
                        lines.append(f"{C.BRIGHT_GREEN}   + │ {''.join(result_b)}{C.RESET}")

            elif tag == "delete":
                for li in range(i1, i2):
                    lines.append(f"{C.BRIGHT_RED}   ‒ │ {orig[li]}{C.RESET}")

            elif tag == "insert":
                for lj in range(j1, j2):
                    lines.append(f"{C.BRIGHT_GREEN}   + │ {mod[lj]}{C.RESET}")

        lines.append(f"\n{C.NVIDIA_GREEN}╰{'─' * 52}╯{C.RESET}")
        return "\n".join(lines)

    # ── Formato: Summary ──────────────────────────────────────────────────

    def _fmt_summary(
        self, orig, mod, proc1, proc2, name1, name2, context, width,
    ) -> str:
        diff_lines = list(difflib.unified_diff(proc1, proc2, lineterm=""))
        stats = _count_diff_stats(diff_lines)

        # Similarity
        ratio = difflib.SequenceMatcher(None, proc1, proc2).ratio()

        # Líneas cambiadas por sección (hunk analysis)
        matcher = difflib.SequenceMatcher(None, proc1, proc2)
        change_regions: List[Dict[str, Any]] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != "equal":
                change_regions.append({
                    "type": tag,
                    "orig_range": (i1 + 1, i2),
                    "mod_range": (j1 + 1, j2),
                    "orig_lines": i2 - i1,
                    "mod_lines": j2 - j1,
                })

        lines = [
            f"\n{C.NVIDIA_GREEN}╭─ Diff Summary ─╮{C.RESET}",
            f"",
            f"  📄 Original:  {name1} ({len(orig)} líneas)",
            f"  📄 Modificado: {name2} ({len(mod)} líneas)",
            f"",
            self._stats_bar(stats),
            f"",
            f"  📊 Similitud: {ratio:.1%}",
            f"  📊 Regiones cambiadas: {len(change_regions)}",
            f"",
        ]

        if change_regions:
            lines.append(f"  {'Tipo':<10s} {'Original':>15s} {'Modificado':>15s} {'Líneas':>8s}")
            lines.append(f"  {'─' * 10} {'─' * 15} {'─' * 15} {'─' * 8}")

            for region in change_regions[:20]:
                r_type = {
                    "replace": "✏️  Cambio",
                    "delete":  "🗑️  Borrado",
                    "insert":  "➕ Inserción",
                }.get(region["type"], region["type"])

                orig_r = f"L{region['orig_range'][0]}-{region['orig_range'][1]}"
                mod_r = f"L{region['mod_range'][0]}-{region['mod_range'][1]}"
                total = max(region["orig_lines"], region["mod_lines"])

                lines.append(f"  {r_type:<10s} {orig_r:>15s} {mod_r:>15s} {total:>8d}")

            if len(change_regions) > 20:
                lines.append(f"  ... y {len(change_regions) - 20} regiones más")

        lines.append(f"\n{C.NVIDIA_GREEN}╰{'─' * 52}╯{C.RESET}")
        return "\n".join(lines)

    # ── Formato: HTML ─────────────────────────────────────────────────────

    def _fmt_html(
        self, orig, mod, proc1, proc2, name1, name2, context, width,
    ) -> str:
        html_diff = difflib.HtmlDiff(wrapcolumn=width)
        table = html_diff.make_table(
            proc1, proc2,
            fromdesc=name1, todesc=name2,
            context=True, numlines=context,
        )

        full_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Diff: {name1} → {name2}</title>
    <style>
        body {{ font-family: 'Fira Code', 'Cascadia Code', monospace; margin: 2rem; background: #1a1a2e; color: #e0e0e0; }}
        h1 {{ color: #76b900; }}
        table.diff {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
        td {{ padding: 2px 8px; white-space: pre-wrap; border: 1px solid #333; }}
        .diff_header {{ background: #1e3a5f; color: #7ec8e3; font-weight: bold; }}
        .diff_next {{ background: #2a2a4a; }}
        .diff_add {{ background: #1a3d1a; color: #90ee90; }}
        .diff_chg {{ background: #3d3d1a; color: #eeee90; }}
        .diff_sub {{ background: #3d1a1a; color: #ee9090; }}
        td:first-child, td:nth-child(4) {{ color: #666; text-align: right; user-select: none; }}
    </style>
</head>
<body>
    <h1>🔀 Diff: {name1} → {name2}</h1>
    {table}
</body>
</html>"""
        return full_html

    # ── Formato: Patch (aplicable) ────────────────────────────────────────

    def _fmt_patch(
        self, orig, mod, proc1, proc2, name1, name2, context, width,
    ) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        patch_lines = list(difflib.unified_diff(
            proc1, proc2,
            fromfile=f"a/{name1}",
            tofile=f"b/{name2}",
            lineterm="",
            n=context,
        ))

        if not patch_lines:
            return "# No hay diferencias"

        header = [
            f"# Patch generado: {ts}",
            f"# Original: {name1} ({len(orig)} líneas)",
            f"# Modificado: {name2} ({len(mod)} líneas)",
            "",
        ]

        return "\n".join(header + patch_lines)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _stats_bar(self, stats: Dict[str, int]) -> str:
        """Genera barra visual de estadísticas."""
        added = stats["added"]
        removed = stats["removed"]
        total = added + removed or 1

        bar_len = 40
        green_len = int(added / total * bar_len)
        red_len = bar_len - green_len

        bar = (
            f"{C.BRIGHT_GREEN}{'█' * green_len}{C.RESET}"
            f"{C.BRIGHT_RED}{'█' * red_len}{C.RESET}"
        )

        return (
            f"  {bar} "
            f"{C.BRIGHT_GREEN}+{added}{C.RESET} "
            f"{C.BRIGHT_RED}-{removed}{C.RESET} "
            f"{C.DIM}({stats['hunks']} hunks, neto: {stats['net']:+d}){C.RESET}"
        )


# ─── 2. PATCH TOOL ──────────────────────────────────────────────────────────


class PatchTool(BaseTool):
    """
    Aplica cambios a archivos con preview, backup automático y múltiples
    modos de operación (buscar/reemplazar, regex, multi-patch, unified patch).
    """

    name = "patch"
    description = (
        "Aplica parches a archivos con preview, backup automático, "
        "soporte regex y múltiples reemplazos en secuencia."
    )
    category = "diff"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "file": ToolParameter(
                name="file",
                type="string",
                description="Archivo a parchear",
                required=True,
            ),
            "find": ToolParameter(
                name="find",
                type="string",
                description="Texto o patrón a encontrar",
                required=False,
            ),
            "replace": ToolParameter(
                name="replace",
                type="string",
                description="Texto de reemplazo",
                required=False,
            ),
            "patches": ToolParameter(
                name="patches",
                type="array",
                description=(
                    "Lista de parches: [{'find':'x','replace':'y'}, ...] "
                    "para múltiples reemplazos en secuencia"
                ),
                required=False,
            ),
            "regex": ToolParameter(
                name="regex",
                type="boolean",
                description="Usar regex en find (default: false)",
                required=False,
            ),
            "count": ToolParameter(
                name="count",
                type="integer",
                description="Máximo de ocurrencias a reemplazar (default: 1, 0=todas)",
                required=False,
            ),
            "preview": ToolParameter(
                name="preview",
                type="boolean",
                description="Solo mostrar preview sin aplicar (default: true)",
                required=False,
            ),
            "backup": ToolParameter(
                name="backup",
                type="boolean",
                description="Crear backup antes de aplicar (default: true)",
                required=False,
            ),
            "line_range": ToolParameter(
                name="line_range",
                type="string",
                description="Rango de líneas a afectar: '10-20' (opcional)",
                required=False,
            ),
            "insert_after": ToolParameter(
                name="insert_after",
                type="string",
                description="Insertar texto después de la línea que contiene este patrón",
                required=False,
            ),
            "insert_before": ToolParameter(
                name="insert_before",
                type="string",
                description="Insertar texto antes de la línea que contiene este patrón",
                required=False,
            ),
            "delete_lines": ToolParameter(
                name="delete_lines",
                type="string",
                description="Eliminar líneas que contengan este patrón",
                required=False,
            ),
        }

    def execute(
        self,
        file: Optional[str] = None,
        find: Optional[str] = None,
        replace: Optional[str] = None,
        patches: Optional[List[Dict[str, str]]] = None,
        regex: bool = False,
        count: int = 1,
        preview: bool = True,
        backup: bool = True,
        line_range: Optional[str] = None,
        insert_after: Optional[str] = None,
        insert_before: Optional[str] = None,
        delete_lines: Optional[str] = None,
        **kwargs,
    ) -> str:
        file = file or kwargs.get("file", "")

        if not file:
            return "❌ Se requiere 'file'."

        file_path = Path(file)
        if not file_path.exists():
            return f"❌ No encontrado: {file}"

        if not file_path.is_file():
            return f"❌ '{file}' no es un archivo."

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="latin-1")

        original = content

        # ── Determinar modo de operación ──────────────────────────────────
        operations: List[Dict[str, Any]] = []

        if patches:
            # Multi-patch
            for p in patches:
                operations.append({
                    "type": "replace",
                    "find": p.get("find", ""),
                    "replace": p.get("replace", ""),
                    "regex": p.get("regex", regex),
                    "count": p.get("count", count),
                })
        elif find is not None and replace is not None:
            operations.append({
                "type": "replace",
                "find": find,
                "replace": replace,
                "regex": regex,
                "count": count,
            })

        if insert_after:
            operations.append({
                "type": "insert_after",
                "pattern": insert_after,
                "content": replace or "",
            })

        if insert_before:
            operations.append({
                "type": "insert_before",
                "pattern": insert_before,
                "content": replace or "",
            })

        if delete_lines:
            operations.append({
                "type": "delete_lines",
                "pattern": delete_lines,
            })

        if not operations:
            return "❌ Se requiere al menos una operación (find/replace, patches, insert_after, insert_before, delete_lines)."

        # ── Parsear rango de líneas ───────────────────────────────────────
        range_start, range_end = None, None
        if line_range:
            match = re.match(r"(\d+)\s*[-:]\s*(\d+)", line_range)
            if match:
                range_start = int(match.group(1)) - 1  # 0-indexed
                range_end = int(match.group(2))

        # ── Aplicar operaciones ───────────────────────────────────────────
        results: List[str] = []
        total_changes = 0

        for i, op in enumerate(operations, 1):
            op_type = op["type"]

            if op_type == "replace":
                content, n = self._apply_replace(
                    content, op["find"], op["replace"],
                    op.get("regex", False), op.get("count", 1),
                    range_start, range_end,
                )
                total_changes += n
                if n > 0:
                    results.append(f"  ✅ Op {i}: {n} reemplazo(s) de '{op['find'][:30]}'")
                else:
                    results.append(f"  ⚠️  Op {i}: '{op['find'][:30]}' no encontrado")

            elif op_type == "insert_after":
                content, n = self._apply_insert(
                    content, op["pattern"], op["content"], after=True,
                )
                total_changes += n
                results.append(f"  ✅ Op {i}: insertado después de '{op['pattern'][:30]}' ({n})")

            elif op_type == "insert_before":
                content, n = self._apply_insert(
                    content, op["pattern"], op["content"], after=False,
                )
                total_changes += n
                results.append(f"  ✅ Op {i}: insertado antes de '{op['pattern'][:30]}' ({n})")

            elif op_type == "delete_lines":
                content, n = self._apply_delete_lines(content, op["pattern"])
                total_changes += n
                results.append(f"  ✅ Op {i}: {n} línea(s) eliminadas con '{op['pattern'][:30]}'")

        # ── Sin cambios ──────────────────────────────────────────────────
        if content == original:
            ops_log = "\n".join(results)
            return (
                f"⚠️  Sin cambios en `{file}`\n\n"
                f"**Operaciones:**\n{ops_log}"
            )

        # ── Generar diff de preview ───────────────────────────────────────
        diff_tool = DiffTool()
        diff_output = diff_tool.execute(
            file1=original, file2=content,
            format="word", context=3,
        )

        ops_log = "\n".join(results)

        # ── Aplicar o preview ─────────────────────────────────────────────
        if preview:
            return (
                f"🔍 **Preview de parche** para `{file}`\n\n"
                f"**Operaciones ({total_changes} cambios):**\n{ops_log}\n\n"
                f"{diff_output}\n\n"
                f"{C.YELLOW}ℹ️  Preview — usa preview=false para aplicar{C.RESET}"
            )

        # Backup
        backup_path = None
        if backup:
            backup_path = _make_backup(file_path)

        # Escribir
        file_path.write_text(content, encoding="utf-8")

        backup_msg = f"\n💾 Backup: `{backup_path}`" if backup_path else ""

        return (
            f"✅ **Parche aplicado** a `{file}`\n\n"
            f"**Operaciones ({total_changes} cambios):**\n{ops_log}\n\n"
            f"{diff_output}"
            f"{backup_msg}"
        )

    # ── Operaciones de parcheo ────────────────────────────────────────────

    def _apply_replace(
        self,
        content: str,
        find: str,
        replace: str,
        use_regex: bool,
        max_count: int,
        range_start: Optional[int],
        range_end: Optional[int],
    ) -> Tuple[str, int]:
        """Aplica reemplazo. Retorna (nuevo_contenido, num_reemplazos)."""
        if range_start is not None and range_end is not None:
            lines = content.splitlines(keepends=True)
            target = "".join(lines[range_start:range_end])
            replacement_count = 0

            if use_regex:
                new_target, replacement_count = re.subn(
                    find, replace, target, count=max_count or 0,
                )
            else:
                if max_count == 0:
                    replacement_count = target.count(find)
                    new_target = target.replace(find, replace)
                else:
                    replacement_count = min(target.count(find), max_count)
                    new_target = target.replace(find, replace, max_count)

            new_lines = lines[:range_start] + [new_target] + lines[range_end:]
            return "".join(new_lines), replacement_count

        if use_regex:
            new_content, n = re.subn(find, replace, content, count=max_count or 0)
            return new_content, n

        if max_count == 0:
            n = content.count(find)
            return content.replace(find, replace), n

        n = min(content.count(find), max_count)
        return content.replace(find, replace, max_count), n

    def _apply_insert(
        self, content: str, pattern: str, new_content: str, after: bool,
    ) -> Tuple[str, int]:
        """Inserta contenido antes o después de líneas que matchean."""
        lines = content.splitlines(keepends=True)
        result: List[str] = []
        count = 0

        for line in lines:
            if pattern in line:
                if after:
                    result.append(line)
                    # Preservar indentación
                    indent = re.match(r"^(\s*)", line)
                    prefix = indent.group(1) if indent else ""
                    for insert_line in new_content.splitlines():
                        result.append(f"{prefix}{insert_line}\n")
                else:
                    indent = re.match(r"^(\s*)", line)
                    prefix = indent.group(1) if indent else ""
                    for insert_line in new_content.splitlines():
                        result.append(f"{prefix}{insert_line}\n")
                    result.append(line)
                count += 1
            else:
                result.append(line)

        return "".join(result), count

    def _apply_delete_lines(
        self, content: str, pattern: str,
    ) -> Tuple[str, int]:
        """Elimina líneas que contengan el patrón."""
        lines = content.splitlines(keepends=True)
        filtered = [line for line in lines if pattern not in line]
        removed = len(lines) - len(filtered)
        return "".join(filtered), removed


# ─── 3. MERGE TOOL ──────────────────────────────────────────────────────────


class MergeTool(BaseTool):
    """
    Fusiona dos versiones de un archivo usando un ancestro común (three-way merge)
    o fusión directa (two-way) con detección y marcado de conflictos.
    """

    name = "merge"
    description = (
        "Fusiona dos versiones de un archivo. Soporta three-way merge "
        "con ancestro común y detección automática de conflictos."
    )
    category = "diff"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "ours": ToolParameter(
                name="ours",
                type="string",
                description="Nuestra versión (archivo o código)",
                required=True,
            ),
            "theirs": ToolParameter(
                name="theirs",
                type="string",
                description="Su versión (archivo o código)",
                required=True,
            ),
            "base": ToolParameter(
                name="base",
                type="string",
                description="Ancestro común para three-way merge (opcional)",
                required=False,
            ),
            "output": ToolParameter(
                name="output",
                type="string",
                description="Archivo de salida para el merge",
                required=False,
            ),
            "strategy": ToolParameter(
                name="strategy",
                type="string",
                description="Estrategia: auto|ours|theirs|union (default: auto)",
                required=False,
            ),
            "conflict_style": ToolParameter(
                name="conflict_style",
                type="string",
                description="Estilo de marcadores: merge|diff3 (default: merge)",
                required=False,
            ),
        }

    def execute(
        self,
        ours: Optional[str] = None,
        theirs: Optional[str] = None,
        base: Optional[str] = None,
        output: Optional[str] = None,
        strategy: str = "auto",
        conflict_style: str = "merge",
        **kwargs,
    ) -> str:
        if not ours or not theirs:
            return "❌ Se requieren 'ours' y 'theirs'."

        try:
            ours_lines, ours_name = _read_content(ours)
            theirs_lines, theirs_name = _read_content(theirs)
            base_lines, base_name = (_read_content(base) if base else ([], "empty"))
        except Exception as e:
            return f"❌ Error leyendo archivos: {e}"

        strategy = strategy.lower().strip()

        # ── Estrategias no-merge ──────────────────────────────────────────
        if strategy == "ours":
            merged = ours_lines
            conflicts = 0
        elif strategy == "theirs":
            merged = theirs_lines
            conflicts = 0
        elif strategy == "union":
            # Unir todo sin conflictos
            merged, conflicts = self._merge_union(ours_lines, theirs_lines)
        else:
            # Auto merge (three-way si hay base)
            if base_lines:
                merged, conflicts = self._three_way_merge(
                    base_lines, ours_lines, theirs_lines,
                    ours_name, theirs_name, base_name,
                    conflict_style,
                )
            else:
                merged, conflicts = self._two_way_merge(
                    ours_lines, theirs_lines,
                    ours_name, theirs_name,
                    conflict_style,
                )

        result_text = "\n".join(merged)

        # ── Guardar resultado ─────────────────────────────────────────────
        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(result_text + "\n", encoding="utf-8")

        # ── Construir reporte ─────────────────────────────────────────────
        status = "✅ Merge limpio" if conflicts == 0 else f"⚠️  {conflicts} conflicto(s)"

        lines = [
            f"🔀 **Merge: {ours_name} + {theirs_name}**",
            f"",
            f"  Estrategia: {strategy}",
            f"  Base: {base_name if base else '(sin base — two-way)'}",
            f"  Estado: {status}",
            f"  Resultado: {len(merged)} líneas",
            f"",
        ]

        if output:
            lines.append(f"  💾 Guardado en: `{output}`")

        if conflicts > 0:
            lines.append(f"")
            lines.append(f"  {C.YELLOW}⚠️  Resolver conflictos marcados con <<<<<<< / ======= / >>>>>>>{C.RESET}")

        # Preview del resultado
        preview = result_text[:1500]
        if len(result_text) > 1500:
            preview += "\n... (truncado)"
        lines.append(f"\n```\n{preview}\n```")

        return "\n".join(lines)

    # ── Three-way merge ───────────────────────────────────────────────────

    def _three_way_merge(
        self,
        base: List[str],
        ours: List[str],
        theirs: List[str],
        ours_name: str,
        theirs_name: str,
        base_name: str,
        conflict_style: str,
    ) -> Tuple[List[str], int]:
        """
        Merge de tres vías usando el ancestro común.
        """
        # Calcular diffs desde base
        matcher_ours = difflib.SequenceMatcher(None, base, ours)
        matcher_theirs = difflib.SequenceMatcher(None, base, theirs)

        ops_ours = matcher_ours.get_opcodes()
        ops_theirs = matcher_theirs.get_opcodes()

        # Construir mapa de cambios por línea base
        changes_ours: Dict[int, str] = {}   # base_line_idx → 'delete'|'replace'
        inserts_ours: Dict[int, List[str]] = defaultdict(list)  # before base_line → lines
        changes_theirs: Dict[int, str] = {}
        inserts_theirs: Dict[int, List[str]] = defaultdict(list)

        for tag, i1, i2, j1, j2 in ops_ours:
            if tag == "replace":
                for i in range(i1, i2):
                    changes_ours[i] = "delete"
                inserts_ours[i1].extend(ours[j1:j2])
            elif tag == "delete":
                for i in range(i1, i2):
                    changes_ours[i] = "delete"
            elif tag == "insert":
                inserts_ours[i1].extend(ours[j1:j2])

        for tag, i1, i2, j1, j2 in ops_theirs:
            if tag == "replace":
                for i in range(i1, i2):
                    changes_theirs[i] = "delete"
                inserts_theirs[i1].extend(theirs[j1:j2])
            elif tag == "delete":
                for i in range(i1, i2):
                    changes_theirs[i] = "delete"
            elif tag == "insert":
                inserts_theirs[i1].extend(theirs[j1:j2])

        # Merge
        merged: List[str] = []
        conflicts = 0

        for i in range(len(base)):
            # Inserciones antes de esta línea
            ins_o = inserts_ours.get(i, [])
            ins_t = inserts_theirs.get(i, [])

            if ins_o and ins_t and ins_o != ins_t:
                # Conflicto de inserción
                merged.append(f"<<<<<<< {ours_name}")
                merged.extend(ins_o)
                merged.append("=======")
                merged.extend(ins_t)
                merged.append(f">>>>>>> {theirs_name}")
                conflicts += 1
            elif ins_o:
                merged.extend(ins_o)
            elif ins_t:
                merged.extend(ins_t)

            # La línea base
            del_o = i in changes_ours
            del_t = i in changes_theirs

            if del_o and del_t:
                # Ambos cambiaron → conflicto (ya manejado arriba en inserts)
                pass
            elif del_o:
                pass  # Ours lo borró
            elif del_t:
                pass  # Theirs lo borró
            else:
                merged.append(base[i])

        # Inserciones al final
        ins_o = inserts_ours.get(len(base), [])
        ins_t = inserts_theirs.get(len(base), [])
        if ins_o and ins_t and ins_o != ins_t:
            merged.append(f"<<<<<<< {ours_name}")
            merged.extend(ins_o)
            merged.append("=======")
            merged.extend(ins_t)
            merged.append(f">>>>>>> {theirs_name}")
            conflicts += 1
        elif ins_o:
            merged.extend(ins_o)
        elif ins_t:
            merged.extend(ins_t)

        return merged, conflicts

    # ── Two-way merge ─────────────────────────────────────────────────────

    def _two_way_merge(
        self,
        ours: List[str],
        theirs: List[str],
        ours_name: str,
        theirs_name: str,
        conflict_style: str,
    ) -> Tuple[List[str], int]:
        """Merge de dos vías con marcadores de conflicto."""
        matcher = difflib.SequenceMatcher(None, ours, theirs)
        merged: List[str] = []
        conflicts = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                merged.extend(ours[i1:i2])
            elif tag == "replace":
                merged.append(f"<<<<<<< {ours_name}")
                merged.extend(ours[i1:i2])
                merged.append("=======")
                merged.extend(theirs[j1:j2])
                merged.append(f">>>>>>> {theirs_name}")
                conflicts += 1
            elif tag == "delete":
                # Solo en ours → mantener (ours lo tiene, theirs no)
                merged.extend(ours[i1:i2])
            elif tag == "insert":
                # Solo en theirs → incluir
                merged.extend(theirs[j1:j2])

        return merged, conflicts

    # ── Union merge ───────────────────────────────────────────────────────

    def _merge_union(
        self, ours: List[str], theirs: List[str],
    ) -> Tuple[List[str], int]:
        """Unión simple: incluye todas las líneas de ambas versiones."""
        matcher = difflib.SequenceMatcher(None, ours, theirs)
        merged: List[str] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                merged.extend(ours[i1:i2])
            elif tag == "replace":
                merged.extend(ours[i1:i2])
                merged.extend(theirs[j1:j2])
            elif tag == "delete":
                merged.extend(ours[i1:i2])
            elif tag == "insert":
                merged.extend(theirs[j1:j2])

        return merged, 0


# ─── 4. SEMANTIC DIFF TOOL ──────────────────────────────────────────────────


class SemanticDiffTool(BaseTool):
    """
    Diff semántico para Python: analiza cambios a nivel de AST,
    reportando funciones/clases/métodos agregados, eliminados o modificados.
    """

    name = "semantic_diff"
    description = (
        "Diff semántico (AST) para Python. Reporta cambios a nivel de "
        "funciones, clases, métodos, imports y decoradores."
    )
    category = "diff"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "file1": ToolParameter(
                name="file1",
                type="string",
                description="Archivo/código Python original",
                required=True,
            ),
            "file2": ToolParameter(
                name="file2",
                type="string",
                description="Archivo/código Python modificado",
                required=True,
            ),
            "detail": ToolParameter(
                name="detail",
                type="string",
                description="Nivel de detalle: summary|full (default: full)",
                required=False,
            ),
        }

    def execute(
        self,
        file1: Optional[str] = None,
        file2: Optional[str] = None,
        detail: str = "full",
        **kwargs,
    ) -> str:
        if not file1 or not file2:
            return "❌ Se requieren 'file1' y 'file2'."

        try:
            content1, name1 = _read_content(file1)
            content2, name2 = _read_content(file2)
        except Exception as e:
            return f"❌ Error leyendo archivos: {e}"

        src1 = "\n".join(content1)
        src2 = "\n".join(content2)

        try:
            tree1 = ast.parse(src1)
            tree2 = ast.parse(src2)
        except SyntaxError as e:
            return f"❌ Error de sintaxis: {e}"

        # ── Extraer símbolos ──────────────────────────────────────────────
        symbols1 = self._extract_symbols(tree1, src1)
        symbols2 = self._extract_symbols(tree2, src2)

        keys1 = set(symbols1.keys())
        keys2 = set(symbols2.keys())

        added = keys2 - keys1
        removed = keys1 - keys2
        common = keys1 & keys2

        modified: List[Tuple[str, Dict, Dict]] = []
        unchanged: List[str] = []

        for key in sorted(common):
            s1 = symbols1[key]
            s2 = symbols2[key]
            if s1["source"] != s2["source"]:
                modified.append((key, s1, s2))
            else:
                unchanged.append(key)

        # ── Construir reporte ─────────────────────────────────────────────
        lines = [
            f"🔬 **Semantic Diff: {name1} → {name2}**",
            f"",
            f"  📊 Símbolos: {len(keys1)} → {len(keys2)}"
            f" ({C.BRIGHT_GREEN}+{len(added)}{C.RESET}"
            f" {C.BRIGHT_RED}-{len(removed)}{C.RESET}"
            f" ✏️ {len(modified)}"
            f" ={len(unchanged)})",
            f"",
        ]

        # ── Agregados ────────────────────────────────────────────────────
        if added:
            lines.append(f"{C.BRIGHT_GREEN}  ➕ Agregados ({len(added)}):{C.RESET}")
            for key in sorted(added):
                s = symbols2[key]
                lines.append(
                    f"    {C.GREEN}{s['icon']} {key}{C.RESET}"
                    f" {C.DIM}(L{s['line']}){C.RESET}"
                )
                if s.get("args") and detail == "full":
                    lines.append(f"      {C.DIM}args: {s['args']}{C.RESET}")
            lines.append("")

        # ── Eliminados ────────────────────────────────────────────────────
        if removed:
            lines.append(f"{C.BRIGHT_RED}  🗑️  Eliminados ({len(removed)}):{C.RESET}")
            for key in sorted(removed):
                s = symbols1[key]
                lines.append(
                    f"    {C.RED}{s['icon']} {key}{C.RESET}"
                    f" {C.DIM}(L{s['line']}){C.RESET}"
                )
            lines.append("")

        # ── Modificados ──────────────────────────────────────────────────
        if modified:
            lines.append(f"{C.BRIGHT_YELLOW}  ✏️  Modificados ({len(modified)}):{C.RESET}")
            for key, s1, s2 in modified:
                lines.append(
                    f"    {C.YELLOW}{s1['icon']} {key}{C.RESET}"
                    f" {C.DIM}(L{s1['line']} → L{s2['line']}){C.RESET}"
                )

                if detail == "full":
                    changes = self._describe_changes(s1, s2)
                    for change in changes:
                        lines.append(f"      {change}")

                    # Mini diff del body
                    src_lines1 = s1["source"].splitlines()
                    src_lines2 = s2["source"].splitlines()
                    ratio = difflib.SequenceMatcher(None, src_lines1, src_lines2).ratio()
                    lines.append(f"      {C.DIM}similitud: {ratio:.0%}{C.RESET}")

            lines.append("")

        # ── Resumen de imports ────────────────────────────────────────────
        imports1 = self._extract_imports(tree1)
        imports2 = self._extract_imports(tree2)

        new_imports = imports2 - imports1
        removed_imports = imports1 - imports2

        if new_imports or removed_imports:
            lines.append("  📦 Imports:")
            for imp in sorted(new_imports):
                lines.append(f"    {C.GREEN}+ {imp}{C.RESET}")
            for imp in sorted(removed_imports):
                lines.append(f"    {C.RED}- {imp}{C.RESET}")
            lines.append("")

        return "\n".join(lines)

    # ── Extracción de símbolos ────────────────────────────────────────────

    def _extract_symbols(
        self, tree: ast.AST, source: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Extrae funciones, clases, métodos del AST."""
        symbols: Dict[str, Dict[str, Any]] = {}
        source_lines = source.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                key = f"class:{node.name}"
                symbols[key] = {
                    "type": "class",
                    "icon": "🏷️ ",
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "bases": [ast.unparse(b) for b in node.bases],
                    "decorators": [ast.unparse(d) for d in node.decorator_list],
                    "methods": [
                        n.name for n in node.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ],
                    "source": self._get_source(node, source_lines),
                    "args": None,
                }

                # Métodos como sub-símbolos
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_key = f"method:{node.name}.{item.name}"
                        symbols[method_key] = {
                            "type": "method",
                            "icon": "  🔧",
                            "name": f"{node.name}.{item.name}",
                            "line": item.lineno,
                            "end_line": getattr(item, "end_lineno", item.lineno),
                            "args": self._get_args(item),
                            "decorators": [ast.unparse(d) for d in item.decorator_list],
                            "returns": ast.unparse(item.returns) if item.returns else None,
                            "is_async": isinstance(item, ast.AsyncFunctionDef),
                            "source": self._get_source(item, source_lines),
                        }

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Solo funciones de nivel superior
                if not any(
                    isinstance(parent, ast.ClassDef)
                    for parent in ast.walk(tree)
                    if hasattr(parent, "body") and node in getattr(parent, "body", [])
                ):
                    key = f"func:{node.name}"
                    symbols[key] = {
                        "type": "function",
                        "icon": "⚡",
                        "name": node.name,
                        "line": node.lineno,
                        "end_line": getattr(node, "end_lineno", node.lineno),
                        "args": self._get_args(node),
                        "decorators": [ast.unparse(d) for d in node.decorator_list],
                        "returns": ast.unparse(node.returns) if node.returns else None,
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "source": self._get_source(node, source_lines),
                    }

        return symbols

    def _extract_imports(self, tree: ast.AST) -> set:
        """Extrae todos los imports como strings."""
        imports: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.add(f"from {module} import {alias.name}")
        return imports

    @staticmethod
    def _get_source(node: ast.AST, lines: List[str]) -> str:
        """Extrae el código fuente de un nodo AST."""
        start = node.lineno - 1
        end = getattr(node, "end_lineno", start + 1)
        return "\n".join(lines[start:end])

    @staticmethod
    def _get_args(node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
        """Extrae la firma de argumentos."""
        args = []
        for arg in node.args.args:
            if arg.arg in ("self", "cls"):
                continue
            ann = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
            args.append(f"{arg.arg}{ann}")

        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        return f"({', '.join(args)})"

    def _describe_changes(
        self, s1: Dict[str, Any], s2: Dict[str, Any],
    ) -> List[str]:
        """Describe los cambios entre dos versiones de un símbolo."""
        changes: List[str] = []

        # Cambio de firma
        if s1.get("args") != s2.get("args"):
            changes.append(
                f"{C.DIM}firma: {s1.get('args', '?')} → {s2.get('args', '?')}{C.RESET}"
            )

        # Cambio de return type
        if s1.get("returns") != s2.get("returns"):
            changes.append(
                f"{C.DIM}retorno: {s1.get('returns', 'None')} → {s2.get('returns', 'None')}{C.RESET}"
            )

        # Cambio de decoradores
        if s1.get("decorators") != s2.get("decorators"):
            old_dec = set(s1.get("decorators", []))
            new_dec = set(s2.get("decorators", []))
            for d in new_dec - old_dec:
                changes.append(f"{C.GREEN}+ @{d}{C.RESET}")
            for d in old_dec - new_dec:
                changes.append(f"{C.RED}- @{d}{C.RESET}")

        # Cambio de bases (para clases)
        if s1.get("bases") != s2.get("bases"):
            changes.append(
                f"{C.DIM}bases: {s1.get('bases', [])} → {s2.get('bases', [])}{C.RESET}"
            )

        # Cambio de async
        if s1.get("is_async") != s2.get("is_async"):
            if s2.get("is_async"):
                changes.append(f"{C.CYAN}→ async{C.RESET}")
            else:
                changes.append(f"{C.CYAN}→ sync{C.RESET}")

        # Cambio de métodos (para clases)
        if "methods" in s1 and "methods" in s2:
            old_m = set(s1["methods"])
            new_m = set(s2["methods"])
            for m in new_m - old_m:
                changes.append(f"{C.GREEN}+ método {m}(){C.RESET}")
            for m in old_m - new_m:
                changes.append(f"{C.RED}- método {m}(){C.RESET}")

        if not changes:
            changes.append(f"{C.DIM}(cambios en el body){C.RESET}")

        return changes