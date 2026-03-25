# tools/search_tools.py
"""
NVIDIA CODE — Herramientas de Búsqueda

Búsqueda de archivos, búsqueda de texto en archivos (grep),
listado de directorios con vista de árbol, y detección de duplicados.
"""

import fnmatch
import hashlib
import os
import re
import stat
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

from .base import BaseTool, ToolParameter


# ─── Utilidades compartidas ──────────────────────────────────────────────────

# Extensiones conocidas por categoría
_EXT_CATEGORIES: Dict[str, Set[str]] = {
    "python":  {".py", ".pyi", ".pyx", ".pxd"},
    "js":      {".js", ".jsx", ".mjs", ".cjs"},
    "ts":      {".ts", ".tsx", ".mts"},
    "web":     {".html", ".htm", ".css", ".scss", ".sass", ".less", ".vue", ".svelte"},
    "rust":    {".rs"},
    "go":      {".go"},
    "java":    {".java", ".kt", ".kts", ".scala"},
    "c":       {".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hxx"},
    "ruby":    {".rb", ".erb"},
    "php":     {".php"},
    "shell":   {".sh", ".bash", ".zsh", ".fish"},
    "config":  {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".conf"},
    "doc":     {".md", ".rst", ".txt", ".adoc"},
    "data":    {".csv", ".tsv", ".xml", ".sql"},
    "image":   {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp"},
    "font":    {".ttf", ".otf", ".woff", ".woff2"},
    "archive": {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"},
    "binary":  {".exe", ".dll", ".so", ".dylib", ".o", ".a", ".pyc", ".pyo", ".class"},
}

# Directorios ignorados por defecto
_DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git", ".svn", ".hg",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", "bower_components",
    ".venv", "venv", "env", ".env",
    ".tox", ".nox",
    "dist", "build", "target",
    ".eggs", "*.egg-info",
    ".idea", ".vscode", ".vs",
    "htmlcov", ".coverage",
}

# Extensiones de archivo de texto comunes
_TEXT_EXTENSIONS: Set[str] = set()
for _cat in ("python", "js", "ts", "web", "rust", "go", "java", "c",
             "ruby", "php", "shell", "config", "doc", "data"):
    _TEXT_EXTENSIONS.update(_EXT_CATEGORIES[_cat])

_BINARY_EXTENSIONS: Set[str] = set()
for _cat in ("image", "font", "archive", "binary"):
    _BINARY_EXTENSIONS.update(_EXT_CATEGORIES[_cat])


def _format_size(size_bytes: int) -> str:
    """Formatea bytes a unidad legible."""
    if size_bytes < 0:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            if unit == "B":
                return f"{size_bytes} {unit}"
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def _format_time_ago(timestamp: float) -> str:
    """Formatea un timestamp como 'hace X'."""
    delta = time.time() - timestamp
    if delta < 60:
        return "hace unos segundos"
    if delta < 3600:
        return f"hace {int(delta / 60)} min"
    if delta < 86400:
        return f"hace {int(delta / 3600)} h"
    if delta < 604800:
        return f"hace {int(delta / 86400)} días"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


def _parse_size(size_str: str) -> Optional[int]:
    """Parsea tamaño: '10KB', '5MB', '1GB' → bytes."""
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)$", size_str.strip().upper())
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return int(value * multipliers[unit])


def _parse_time_delta(time_str: str) -> Optional[timedelta]:
    """Parsea duración: '7d', '24h', '30m', '2w' → timedelta."""
    match = re.match(r"^(\d+)\s*([mhdwMy])$", time_str.strip())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    mapping = {
        "m": timedelta(minutes=value),
        "h": timedelta(hours=value),
        "d": timedelta(days=value),
        "w": timedelta(weeks=value),
        "M": timedelta(days=value * 30),
        "y": timedelta(days=value * 365),
    }
    return mapping.get(unit)


def _should_ignore_dir(name: str, extra_ignores: Set[str]) -> bool:
    """Determina si un directorio debe ignorarse."""
    all_ignores = _DEFAULT_IGNORE_DIRS | extra_ignores
    for pattern in all_ignores:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def _is_likely_binary(path: Path) -> bool:
    """Heurística rápida para detectar archivos binarios."""
    if path.suffix.lower() in _BINARY_EXTENSIONS:
        return True
    if path.suffix.lower() in _TEXT_EXTENSIONS:
        return False
    # Leer primeros bytes
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
        # Null bytes indican binario
        return b"\x00" in chunk
    except (OSError, PermissionError):
        return True


def _file_icon(path: Path) -> str:
    """Retorna emoji apropiado según tipo de archivo."""
    if path.is_dir():
        return "📁"

    ext = path.suffix.lower()
    icons = {
        ".py": "🐍", ".pyi": "🐍",
        ".js": "🟨", ".jsx": "⚛️ ", ".ts": "🔷", ".tsx": "⚛️ ",
        ".html": "🌐", ".css": "🎨", ".scss": "🎨",
        ".rs": "🦀", ".go": "🔵",
        ".java": "☕", ".kt": "🟣",
        ".c": "⚙️ ", ".cpp": "⚙️ ", ".h": "⚙️ ",
        ".rb": "💎", ".php": "🐘",
        ".sh": "🐚", ".bash": "🐚",
        ".json": "📋", ".yaml": "📋", ".yml": "📋", ".toml": "📋",
        ".md": "📝", ".rst": "📝", ".txt": "📝",
        ".sql": "🗃️ ", ".csv": "📊",
        ".png": "🖼️ ", ".jpg": "🖼️ ", ".svg": "🖼️ ",
        ".zip": "📦", ".tar": "📦", ".gz": "📦",
        ".lock": "🔒",
        ".env": "🔐",
        ".dockerfile": "🐳",
        ".gitignore": "🙈",
    }

    # Nombres especiales
    name = path.name.lower()
    name_icons = {
        "dockerfile": "🐳",
        "makefile": "🔨",
        "license": "📜",
        "readme.md": "📖",
        "requirements.txt": "📦",
        "pyproject.toml": "📦",
        "package.json": "📦",
        "cargo.toml": "📦",
    }

    return name_icons.get(name, icons.get(ext, "📄"))


def _walk_filtered(
    root: Path,
    ignore_dirs: Set[str],
    max_depth: Optional[int] = None,
    follow_links: bool = False,
    _current_depth: int = 0,
) -> Generator[Tuple[Path, int], None, None]:
    """
    Recorre directorios respetando exclusiones y profundidad máxima.
    Yields (path, depth).
    """
    if max_depth is not None and _current_depth > max_depth:
        return

    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return

    for entry in entries:
        if entry.is_symlink() and not follow_links:
            yield entry, _current_depth
            continue

        if entry.is_dir():
            if _should_ignore_dir(entry.name, ignore_dirs):
                continue
            yield entry, _current_depth
            yield from _walk_filtered(
                entry, ignore_dirs, max_depth, follow_links, _current_depth + 1,
            )
        else:
            yield entry, _current_depth


# ─── 1. SEARCH FILES TOOL ───────────────────────────────────────────────────


class SearchFilesTool(BaseTool):
    """
    Búsqueda avanzada de archivos con filtros por nombre, tamaño, fecha,
    tipo, contenido y extensión. Soporta exclusiones y múltiples patrones.
    """

    name = "search_files"
    description = (
        "Busca archivos por patrón, tamaño, fecha, tipo y contenido. "
        "Soporta glob, regex, múltiples filtros y exclusiones."
    )
    category = "search"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "pattern": ToolParameter(
                name="pattern",
                type="string",
                description="Patrón glob (ej: '*.py', 'test_*.py') o regex con prefijo 're:'",
                required=True,
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio raíz de búsqueda (default: '.')",
                required=False,
            ),
            "max_depth": ToolParameter(
                name="max_depth",
                type="integer",
                description="Profundidad máxima de búsqueda (default: sin límite)",
                required=False,
            ),
            "type": ToolParameter(
                name="type",
                type="string",
                description=(
                    "Filtro por tipo: file|dir|link|python|js|ts|web|config|doc|data|image|binary "
                    "(default: todos)"
                ),
                required=False,
            ),
            "min_size": ToolParameter(
                name="min_size",
                type="string",
                description="Tamaño mínimo (ej: '1KB', '5MB')",
                required=False,
            ),
            "max_size": ToolParameter(
                name="max_size",
                type="string",
                description="Tamaño máximo (ej: '100MB')",
                required=False,
            ),
            "modified_within": ToolParameter(
                name="modified_within",
                type="string",
                description="Modificado en los últimos N (ej: '7d', '24h', '2w')",
                required=False,
            ),
            "modified_before": ToolParameter(
                name="modified_before",
                type="string",
                description="Modificado antes de N (ej: '30d', '1y')",
                required=False,
            ),
            "contains": ToolParameter(
                name="contains",
                type="string",
                description="Filtrar archivos que contengan este texto",
                required=False,
            ),
            "exclude": ToolParameter(
                name="exclude",
                type="string",
                description="Patrones a excluir separados por coma (ej: '*.pyc,*.log')",
                required=False,
            ),
            "ignore_dirs": ToolParameter(
                name="ignore_dirs",
                type="string",
                description="Directorios adicionales a ignorar (coma-separados)",
                required=False,
            ),
            "sort_by": ToolParameter(
                name="sort_by",
                type="string",
                description="Ordenar por: name|size|date|type|path (default: path)",
                required=False,
            ),
            "limit": ToolParameter(
                name="limit",
                type="integer",
                description="Máximo de resultados (default: 100)",
                required=False,
            ),
            "show_stats": ToolParameter(
                name="show_stats",
                type="boolean",
                description="Mostrar estadísticas de la búsqueda (default: true)",
                required=False,
            ),
        }

    def execute(
        self,
        pattern: Optional[str] = None,
        directory: str = ".",
        max_depth: Optional[int] = None,
        type: Optional[str] = None,
        min_size: Optional[str] = None,
        max_size: Optional[str] = None,
        modified_within: Optional[str] = None,
        modified_before: Optional[str] = None,
        contains: Optional[str] = None,
        exclude: Optional[str] = None,
        ignore_dirs: Optional[str] = None,
        sort_by: str = "path",
        limit: int = 100,
        show_stats: bool = True,
        **kwargs,
    ) -> str:
        pattern = pattern or kwargs.get("pattern", "*")
        directory = directory or kwargs.get("directory", ".")

        dir_path = Path(directory).resolve()
        if not dir_path.exists():
            return f"❌ Directorio no encontrado: {directory}"
        if not dir_path.is_dir():
            return f"❌ No es un directorio: {directory}"

        # ── Preparar filtros ──────────────────────────────────────────────
        use_regex = pattern.startswith("re:")
        if use_regex:
            try:
                regex = re.compile(pattern[3:])
            except re.error as e:
                return f"❌ Regex inválido: {e}"
        else:
            regex = None

        # Parsear tamaños
        min_bytes = _parse_size(min_size) if min_size else None
        max_bytes = _parse_size(max_size) if max_size else None

        # Parsear tiempos
        now = time.time()
        min_mtime = None
        max_mtime = None

        if modified_within:
            delta = _parse_time_delta(modified_within)
            if delta:
                min_mtime = now - delta.total_seconds()

        if modified_before:
            delta = _parse_time_delta(modified_before)
            if delta:
                max_mtime = now - delta.total_seconds()

        # Exclusiones
        exclude_patterns = set()
        if exclude:
            exclude_patterns = {p.strip() for p in exclude.split(",") if p.strip()}

        extra_ignore = set()
        if ignore_dirs:
            extra_ignore = {d.strip() for d in ignore_dirs.split(",") if d.strip()}

        # Tipo de archivo
        type_filter = type.lower().strip() if type else None
        type_extensions = _EXT_CATEGORIES.get(type_filter, set()) if type_filter else set()

        # ── Buscar ────────────────────────────────────────────────────────
        matches: List[Dict[str, Any]] = []
        scanned = 0
        dirs_scanned = 0
        total_size = 0
        skipped = 0

        for entry, depth in _walk_filtered(dir_path, extra_ignore, max_depth):
            scanned += 1

            if entry.is_dir():
                dirs_scanned += 1
                if type_filter and type_filter not in ("dir", "directory"):
                    continue
                if type_filter in ("dir", "directory"):
                    if not self._matches_pattern(entry.name, pattern, regex, use_regex):
                        continue
                    matches.append(self._file_info(entry, dir_path))
                    if len(matches) >= limit:
                        break
                continue

            # Es archivo
            name = entry.name

            # ── Filtro: exclusión ─────────────────────────────────────
            if any(fnmatch.fnmatch(name, ep) for ep in exclude_patterns):
                skipped += 1
                continue

            # ── Filtro: tipo ──────────────────────────────────────────
            if type_filter:
                if type_filter == "file":
                    pass  # Todos los archivos
                elif type_filter == "link":
                    if not entry.is_symlink():
                        continue
                elif type_extensions:
                    if entry.suffix.lower() not in type_extensions:
                        continue
                elif type_filter in ("dir", "directory"):
                    continue

            # ── Filtro: patrón de nombre ──────────────────────────────
            if not self._matches_pattern(name, pattern, regex, use_regex):
                skipped += 1
                continue

            # ── Filtro: tamaño ────────────────────────────────────────
            try:
                file_stat = entry.stat()
                file_size = file_stat.st_size
                file_mtime = file_stat.st_mtime
            except (OSError, PermissionError):
                continue

            if min_bytes is not None and file_size < min_bytes:
                continue
            if max_bytes is not None and file_size > max_bytes:
                continue

            # ── Filtro: tiempo ────────────────────────────────────────
            if min_mtime is not None and file_mtime < min_mtime:
                continue
            if max_mtime is not None and file_mtime > max_mtime:
                continue

            # ── Filtro: contenido ─────────────────────────────────────
            if contains:
                if _is_likely_binary(entry):
                    continue
                try:
                    text = entry.read_text(encoding="utf-8", errors="ignore")
                    if contains.lower() not in text.lower():
                        continue
                except (OSError, PermissionError):
                    continue

            # ── Match ─────────────────────────────────────────────────
            info = self._file_info(entry, dir_path)
            info["size_bytes"] = file_size
            info["mtime"] = file_mtime
            matches.append(info)
            total_size += file_size

            if len(matches) >= limit:
                break

        # ── Ordenar ───────────────────────────────────────────────────────
        sort_keys = {
            "name": lambda m: m["name"].lower(),
            "size": lambda m: m.get("size_bytes", 0),
            "date": lambda m: m.get("mtime", 0),
            "type": lambda m: m.get("ext", ""),
            "path": lambda m: m["rel_path"].lower(),
        }
        sort_fn = sort_keys.get(sort_by, sort_keys["path"])
        reverse = sort_by in ("size", "date")
        matches.sort(key=sort_fn, reverse=reverse)

        # ── Formatear resultado ───────────────────────────────────────────
        if not matches:
            filters = [f"patrón='{pattern}'"]
            if type_filter:
                filters.append(f"tipo={type_filter}")
            if contains:
                filters.append(f"contiene='{contains}'")
            if min_size:
                filters.append(f"min={min_size}")
            return f"🔍 Sin resultados ({', '.join(filters)}) en `{dir_path}`"

        # Header
        lines = [
            f"🔍 **{len(matches)} archivo(s) encontrados**"
            f" — patrón: `{pattern}` en `{dir_path.name}/`",
            "",
        ]

        # Tabla de resultados
        for m in matches:
            icon = m["icon"]
            rel = m["rel_path"]
            size = m.get("size_str", "")
            modified = m.get("modified_ago", "")

            if size and modified:
                lines.append(f"  {icon} {rel}  ({size}, {modified})")
            elif size:
                lines.append(f"  {icon} {rel}  ({size})")
            else:
                lines.append(f"  {icon} {rel}")

        # Indicador de truncamiento
        if len(matches) >= limit:
            lines.append(f"\n  ⚠️  Mostrando primeros {limit} resultados. Usa 'limit' para ver más.")

        # Estadísticas
        if show_stats and matches:
            lines.append("")
            lines.append(self._build_stats(matches, scanned, dirs_scanned, skipped, total_size))

        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _matches_pattern(
        name: str, pattern: str, regex: Optional[re.Pattern], use_regex: bool,
    ) -> bool:
        """Verifica si un nombre matchea el patrón."""
        if use_regex and regex:
            return bool(regex.search(name))
        return fnmatch.fnmatch(name, pattern)

    @staticmethod
    def _file_info(path: Path, root: Path) -> Dict[str, Any]:
        """Extrae información de un archivo para display."""
        try:
            st = path.stat()
            size = st.st_size
            mtime = st.st_mtime
        except (OSError, PermissionError):
            size = -1
            mtime = 0

        rel = path.relative_to(root) if path.is_relative_to(root) else path

        return {
            "name": path.name,
            "ext": path.suffix.lower(),
            "rel_path": str(rel),
            "abs_path": str(path),
            "icon": _file_icon(path),
            "is_dir": path.is_dir(),
            "size_bytes": size,
            "size_str": _format_size(size) if not path.is_dir() else "",
            "mtime": mtime,
            "modified_ago": _format_time_ago(mtime) if mtime > 0 else "",
        }

    @staticmethod
    def _build_stats(
        matches: List[Dict], scanned: int, dirs: int, skipped: int, total_size: int,
    ) -> str:
        """Construye bloque de estadísticas."""
        # Distribución por extensión
        ext_counts: Counter = Counter()
        for m in matches:
            ext = m.get("ext", "(sin ext)")
            ext_counts[ext or "(sin ext)"] += 1

        top_exts = ext_counts.most_common(8)
        ext_bar = "  ".join(f"`{ext}`: {cnt}" for ext, cnt in top_exts)

        lines = [
            f"📊 **Estadísticas:**",
            f"  Escaneados: {scanned} items ({dirs} dirs)",
            f"  Omitidos: {skipped}",
            f"  Tamaño total: {_format_size(total_size)}",
            f"  Extensiones: {ext_bar}",
        ]

        return "\n".join(lines)


# ─── 2. SEARCH IN FILES TOOL (grep) ─────────────────────────────────────────


class SearchInFilesTool(BaseTool):
    """
    Búsqueda de texto dentro de archivos estilo grep con soporte para
    regex, contexto, word boundaries, agrupación y reemplazo.
    """

    name = "search_in_files"
    description = (
        "Busca texto dentro de archivos (grep). Soporta regex, líneas de "
        "contexto, word boundaries, case sensitivity y agrupación por archivo."
    )
    category = "search"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "query": ToolParameter(
                name="query",
                type="string",
                description="Texto o regex a buscar",
                required=True,
            ),
            "file_pattern": ToolParameter(
                name="file_pattern",
                type="string",
                description="Patrón de archivos (ej: '*.py', '*.{py,js}'). Default: '*'",
                required=False,
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio raíz (default: '.')",
                required=False,
            ),
            "regex": ToolParameter(
                name="regex",
                type="boolean",
                description="Tratar query como regex (default: false)",
                required=False,
            ),
            "case_sensitive": ToolParameter(
                name="case_sensitive",
                type="boolean",
                description="Búsqueda sensible a mayúsculas (default: false)",
                required=False,
            ),
            "whole_word": ToolParameter(
                name="whole_word",
                type="boolean",
                description="Buscar palabra completa (default: false)",
                required=False,
            ),
            "context": ToolParameter(
                name="context",
                type="integer",
                description="Líneas de contexto antes/después del match (default: 0)",
                required=False,
            ),
            "before_context": ToolParameter(
                name="before_context",
                type="integer",
                description="Líneas de contexto antes del match",
                required=False,
            ),
            "after_context": ToolParameter(
                name="after_context",
                type="integer",
                description="Líneas de contexto después del match",
                required=False,
            ),
            "max_results": ToolParameter(
                name="max_results",
                type="integer",
                description="Máximo de coincidencias totales (default: 100)",
                required=False,
            ),
            "max_per_file": ToolParameter(
                name="max_per_file",
                type="integer",
                description="Máximo de coincidencias por archivo (default: 20)",
                required=False,
            ),
            "exclude": ToolParameter(
                name="exclude",
                type="string",
                description="Patrones de archivo a excluir (coma-separados)",
                required=False,
            ),
            "ignore_dirs": ToolParameter(
                name="ignore_dirs",
                type="string",
                description="Directorios adicionales a ignorar",
                required=False,
            ),
            "invert": ToolParameter(
                name="invert",
                type="boolean",
                description="Invertir: mostrar líneas que NO coinciden (default: false)",
                required=False,
            ),
            "count_only": ToolParameter(
                name="count_only",
                type="boolean",
                description="Solo contar coincidencias sin mostrar líneas (default: false)",
                required=False,
            ),
            "group_by": ToolParameter(
                name="group_by",
                type="string",
                description="Agrupar resultados: file|none (default: file)",
                required=False,
            ),
            "max_depth": ToolParameter(
                name="max_depth",
                type="integer",
                description="Profundidad máxima de búsqueda",
                required=False,
            ),
            "max_line_length": ToolParameter(
                name="max_line_length",
                type="integer",
                description="Truncar líneas a N caracteres (default: 200)",
                required=False,
            ),
        }

    def execute(
        self,
        query: Optional[str] = None,
        file_pattern: str = "*",
        directory: str = ".",
        regex: bool = False,
        case_sensitive: bool = False,
        whole_word: bool = False,
        context: int = 0,
        before_context: Optional[int] = None,
        after_context: Optional[int] = None,
        max_results: int = 100,
        max_per_file: int = 20,
        exclude: Optional[str] = None,
        ignore_dirs: Optional[str] = None,
        invert: bool = False,
        count_only: bool = False,
        group_by: str = "file",
        max_depth: Optional[int] = None,
        max_line_length: int = 200,
        **kwargs,
    ) -> str:
        query = query or kwargs.get("query", "")
        if not query:
            return "❌ Se requiere 'query'."

        dir_path = Path(directory or ".").resolve()
        if not dir_path.exists():
            return f"❌ Directorio no encontrado: {directory}"

        # ── Compilar patrón de búsqueda ───────────────────────────────────
        try:
            search_pattern = self._compile_pattern(
                query, regex, case_sensitive, whole_word,
            )
        except re.error as e:
            return f"❌ Regex inválido: {e}"

        # ── Preparar filtros ──────────────────────────────────────────────
        ctx_before = before_context if before_context is not None else context
        ctx_after = after_context if after_context is not None else context

        exclude_patterns = set()
        if exclude:
            exclude_patterns = {p.strip() for p in exclude.split(",") if p.strip()}

        extra_ignore = set()
        if ignore_dirs:
            extra_ignore = {d.strip() for d in ignore_dirs.split(",") if d.strip()}

        # Parsear múltiples patrones de archivo: "*.{py,js}" o "*.py,*.js"
        file_patterns = self._expand_file_pattern(file_pattern or "*")

        # ── Buscar en archivos ────────────────────────────────────────────
        all_results: List[Dict[str, Any]] = []
        files_with_matches = 0
        files_searched = 0
        total_matches = 0
        truncated = False

        for entry, depth in _walk_filtered(dir_path, extra_ignore, max_depth):
            if not entry.is_file():
                continue

            # Filtro de patrón de archivo
            if not any(fnmatch.fnmatch(entry.name, fp) for fp in file_patterns):
                continue

            # Filtro de exclusión
            if any(fnmatch.fnmatch(entry.name, ep) for ep in exclude_patterns):
                continue

            # Saltar binarios
            if _is_likely_binary(entry):
                continue

            files_searched += 1

            # Leer y buscar
            try:
                text = entry.read_text(encoding="utf-8", errors="ignore")
            except (OSError, PermissionError):
                continue

            lines_list = text.splitlines()
            file_matches = self._search_in_lines(
                lines_list, search_pattern, invert,
                ctx_before, ctx_after, max_per_file,
                max_line_length,
            )

            if file_matches:
                rel_path = str(
                    entry.relative_to(dir_path)
                    if entry.is_relative_to(dir_path)
                    else entry
                )
                all_results.append({
                    "file": rel_path,
                    "icon": _file_icon(entry),
                    "matches": file_matches,
                    "total_in_file": len(file_matches),
                })
                files_with_matches += 1
                total_matches += len(file_matches)

                if total_matches >= max_results:
                    truncated = True
                    break

        # ── Formatear resultado ───────────────────────────────────────────
        if not all_results:
            return (
                f"🔍 Sin resultados para `{query}` "
                f"en `{dir_path.name}/` ({files_searched} archivos buscados)"
            )

        if count_only:
            return self._format_count_only(
                query, all_results, files_searched, total_matches,
            )

        if group_by == "file":
            return self._format_grouped(
                query, all_results, files_searched,
                total_matches, truncated, max_results,
            )
        else:
            return self._format_flat(
                query, all_results, files_searched,
                total_matches, truncated, max_results,
            )

    # ── Motor de búsqueda ─────────────────────────────────────────────────

    @staticmethod
    def _compile_pattern(
        query: str, is_regex: bool, case_sensitive: bool, whole_word: bool,
    ) -> re.Pattern:
        """Compila el patrón de búsqueda."""
        if is_regex:
            pattern = query
        else:
            pattern = re.escape(query)

        if whole_word:
            pattern = rf"\b{pattern}\b"

        flags = 0 if case_sensitive else re.IGNORECASE
        return re.compile(pattern, flags)

    @staticmethod
    def _expand_file_pattern(pattern: str) -> List[str]:
        """
        Expande patrones de archivo.
        "*.{py,js}" → ["*.py", "*.js"]
        "*.py,*.js" → ["*.py", "*.js"]
        """
        # Primero: separar por coma (fuera de llaves)
        patterns: List[str] = []
        brace_match = re.match(r"^(.*)\{([^}]+)\}(.*)$", pattern)

        if brace_match:
            prefix = brace_match.group(1)
            options = brace_match.group(2).split(",")
            suffix = brace_match.group(3)
            for opt in options:
                patterns.append(f"{prefix}{opt.strip()}{suffix}")
        elif "," in pattern:
            patterns = [p.strip() for p in pattern.split(",") if p.strip()]
        else:
            patterns = [pattern]

        return patterns

    def _search_in_lines(
        self,
        lines: List[str],
        pattern: re.Pattern,
        invert: bool,
        ctx_before: int,
        ctx_after: int,
        max_matches: int,
        max_line_length: int,
    ) -> List[Dict[str, Any]]:
        """Busca en líneas y retorna matches con contexto."""
        results: List[Dict[str, Any]] = []
        total_lines = len(lines)

        for i, line in enumerate(lines):
            has_match = bool(pattern.search(line))
            if invert:
                has_match = not has_match

            if not has_match:
                continue

            # Línea match
            match_info: Dict[str, Any] = {
                "line_num": i + 1,
                "line": line[:max_line_length],
                "truncated": len(line) > max_line_length,
            }

            # Resaltar coincidencias (posiciones)
            if not invert:
                highlights = [
                    (m.start(), m.end())
                    for m in pattern.finditer(line[:max_line_length])
                ]
                match_info["highlights"] = highlights

            # Contexto
            if ctx_before > 0 or ctx_after > 0:
                before_lines = []
                for j in range(max(0, i - ctx_before), i):
                    before_lines.append({
                        "line_num": j + 1,
                        "line": lines[j][:max_line_length],
                    })

                after_lines = []
                for j in range(i + 1, min(total_lines, i + 1 + ctx_after)):
                    after_lines.append({
                        "line_num": j + 1,
                        "line": lines[j][:max_line_length],
                    })

                match_info["before"] = before_lines
                match_info["after"] = after_lines

            results.append(match_info)

            if len(results) >= max_matches:
                break

        return results

    # ── Formateadores ─────────────────────────────────────────────────────

    def _format_grouped(
        self,
        query: str,
        results: List[Dict],
        files_searched: int,
        total_matches: int,
        truncated: bool,
        limit: int,
    ) -> str:
        """Formato agrupado por archivo."""
        lines = [
            f"🔍 **{total_matches} coincidencias** en "
            f"**{len(results)} archivos** — `{query}`",
            f"   ({files_searched} archivos buscados)",
            "",
        ]

        for file_result in results:
            file_path = file_result["file"]
            icon = file_result["icon"]
            count = file_result["total_in_file"]
            lines.append(f"  {icon} **{file_path}** ({count} coincidencia{'s' if count > 1 else ''})")

            for match in file_result["matches"]:
                ln = match["line_num"]
                text = match["line"].rstrip()

                # Contexto antes
                for ctx in match.get("before", []):
                    lines.append(f"     {ctx['line_num']:>5d}  │ {ctx['line'].rstrip()}")

                # Línea con match (resaltada)
                highlighted = self._highlight_line(text, match.get("highlights", []))
                marker = "►"
                lines.append(f"     {ln:>5d} {marker}│ {highlighted}")

                # Contexto después
                for ctx in match.get("after", []):
                    lines.append(f"     {ctx['line_num']:>5d}  │ {ctx['line'].rstrip()}")

                # Separador entre matches con contexto
                if match.get("before") or match.get("after"):
                    lines.append(f"          │ {'·' * 40}")

            lines.append("")

        if truncated:
            lines.append(f"⚠️  Resultados truncados a {limit}. Usa 'max_results' para ver más.")

        return "\n".join(lines)

    def _format_flat(
        self,
        query: str,
        results: List[Dict],
        files_searched: int,
        total_matches: int,
        truncated: bool,
        limit: int,
    ) -> str:
        """Formato plano estilo grep."""
        lines = [
            f"🔍 **{total_matches} coincidencias** — `{query}`",
            "",
        ]

        for file_result in results:
            file_path = file_result["file"]
            for match in file_result["matches"]:
                ln = match["line_num"]
                text = match["line"].rstrip()
                highlighted = self._highlight_line(text, match.get("highlights", []))
                lines.append(f"  {file_path}:{ln}: {highlighted}")

        if truncated:
            lines.append(f"\n⚠️  Truncado a {limit}.")

        return "\n".join(lines)

    def _format_count_only(
        self,
        query: str,
        results: List[Dict],
        files_searched: int,
        total_matches: int,
    ) -> str:
        """Solo conteos por archivo."""
        lines = [
            f"🔍 **{total_matches} coincidencias** en "
            f"**{len(results)} archivos** — `{query}`",
            "",
        ]

        # Ordenar por cantidad de matches (descendente)
        sorted_results = sorted(results, key=lambda r: r["total_in_file"], reverse=True)

        max_path_len = max(len(r["file"]) for r in sorted_results)
        bar_width = 30

        for r in sorted_results:
            count = r["total_in_file"]
            max_count = sorted_results[0]["total_in_file"]
            filled = int(count / max_count * bar_width) if max_count > 0 else 0
            bar = "█" * filled + "░" * (bar_width - filled)
            lines.append(f"  {r['icon']} {r['file']:<{max_path_len}s}  {bar} {count}")

        lines.append(f"\n  Total: {total_matches} en {files_searched} archivos buscados")

        return "\n".join(lines)

    @staticmethod
    def _highlight_line(text: str, highlights: List[Tuple[int, int]]) -> str:
        """
        Inserta marcadores de resaltado en una línea.
        Usa **negrita** Markdown como marcador portable.
        """
        if not highlights:
            return text

        result: List[str] = []
        last_end = 0

        for start, end in sorted(highlights):
            if start > last_end:
                result.append(text[last_end:start])
            result.append(f"**{text[start:end]}**")
            last_end = end

        if last_end < len(text):
            result.append(text[last_end:])

        return "".join(result)


# ─── 3. LIST DIRECTORY TOOL ─────────────────────────────────────────────────


class ListDirectoryTool(BaseTool):
    """
    Lista contenido de directorios con vista de árbol, estadísticas,
    filtros por tipo/tamaño y resumen de proyecto.
    """

    name = "list_directory"
    description = (
        "Lista archivos y carpetas con vista de árbol, estadísticas, "
        "filtros por tipo/tamaño e información de proyecto."
    )
    category = "search"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(
                name="path",
                type="string",
                description="Ruta del directorio (default: '.')",
                required=False,
            ),
            "depth": ToolParameter(
                name="depth",
                type="integer",
                description="Profundidad del árbol (default: 2)",
                required=False,
            ),
            "show_hidden": ToolParameter(
                name="show_hidden",
                type="boolean",
                description="Mostrar archivos ocultos (default: false)",
                required=False,
            ),
            "show_size": ToolParameter(
                name="show_size",
                type="boolean",
                description="Mostrar tamaño de archivos (default: true)",
                required=False,
            ),
            "show_date": ToolParameter(
                name="show_date",
                type="boolean",
                description="Mostrar fecha de modificación (default: false)",
                required=False,
            ),
            "view": ToolParameter(
                name="view",
                type="string",
                description="Vista: tree|flat|stats|summary (default: tree)",
                required=False,
            ),
            "sort_by": ToolParameter(
                name="sort_by",
                type="string",
                description="Ordenar: name|size|date|type (default: name)",
                required=False,
            ),
            "filter": ToolParameter(
                name="filter",
                type="string",
                description="Filtro por extensión o tipo (ej: 'python', '*.py', 'dir')",
                required=False,
            ),
            "ignore_default": ToolParameter(
                name="ignore_default",
                type="boolean",
                description="Ignorar directorios estándar (.git, node_modules, etc). Default: true",
                required=False,
            ),
            "max_items": ToolParameter(
                name="max_items",
                type="integer",
                description="Máximo de items a mostrar (default: 200)",
                required=False,
            ),
        }

    def execute(
        self,
        path: str = ".",
        depth: int = 2,
        show_hidden: bool = False,
        show_size: bool = True,
        show_date: bool = False,
        view: str = "tree",
        sort_by: str = "name",
        filter: Optional[str] = None,
        ignore_default: bool = True,
        max_items: int = 200,
        **kwargs,
    ) -> str:
        path = path or kwargs.get("path", ".")
        dir_path = Path(path).resolve()

        if not dir_path.exists():
            return f"❌ No existe: {path}"
        if not dir_path.is_dir():
            return f"❌ No es un directorio: {path}"

        view = (view or "tree").lower().strip()
        views = {
            "tree":    self._view_tree,
            "flat":    self._view_flat,
            "stats":   self._view_stats,
            "summary": self._view_summary,
        }

        generator = views.get(view)
        if not generator:
            return f"❌ Vista '{view}' no soportada. Opciones: {', '.join(views)}"

        return generator(
            dir_path=dir_path,
            depth=depth,
            show_hidden=show_hidden,
            show_size=show_size,
            show_date=show_date,
            sort_by=sort_by,
            filter_str=filter,
            ignore_default=ignore_default,
            max_items=max_items,
        )

    # ── Vista: Árbol ──────────────────────────────────────────────────────

    def _view_tree(self, dir_path: Path, depth: int, show_hidden: bool,
                   show_size: bool, show_date: bool, sort_by: str,
                   filter_str: Optional[str], ignore_default: bool,
                   max_items: int) -> str:
        lines = [f"📂 **{dir_path.name}/**", ""]

        count = self._build_tree(
            lines, dir_path, "", depth, 0,
            show_hidden, show_size, show_date,
            sort_by, filter_str, ignore_default, max_items,
        )

        if count >= max_items:
            lines.append(f"\n⚠️  Truncado a {max_items} items. Usa 'max_items' o reduce 'depth'.")

        return "\n".join(lines)

    def _build_tree(
        self,
        lines: List[str],
        path: Path,
        prefix: str,
        max_depth: int,
        current_depth: int,
        show_hidden: bool,
        show_size: bool,
        show_date: bool,
        sort_by: str,
        filter_str: Optional[str],
        ignore_default: bool,
        max_items: int,
    ) -> int:
        """Construye árbol recursivamente. Retorna items procesados."""
        if current_depth > max_depth:
            return 0

        try:
            entries = list(path.iterdir())
        except PermissionError:
            lines.append(f"{prefix}⚠️  (sin permisos)")
            return 0

        # Filtrar ocultos
        if not show_hidden:
            entries = [e for e in entries if not e.name.startswith(".")]

        # Filtrar dirs ignorados
        if ignore_default:
            entries = [
                e for e in entries
                if not (e.is_dir() and _should_ignore_dir(e.name, set()))
            ]

        # Aplicar filtro
        if filter_str:
            entries = self._apply_filter(entries, filter_str)

        # Ordenar
        entries = self._sort_entries(entries, sort_by)

        count = 0
        total = len(entries)

        for idx, entry in enumerate(entries):
            if count >= max_items:
                break

            is_last = idx == total - 1
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")

            icon = _file_icon(entry)
            name = entry.name

            # Metadata
            meta_parts: List[str] = []
            if entry.is_file():
                if show_size:
                    try:
                        meta_parts.append(_format_size(entry.stat().st_size))
                    except OSError:
                        pass
                if show_date:
                    try:
                        meta_parts.append(_format_time_ago(entry.stat().st_mtime))
                    except OSError:
                        pass

            meta = f"  ({', '.join(meta_parts)})" if meta_parts else ""

            if entry.is_dir():
                # Contar contenido del directorio
                try:
                    child_count = sum(1 for _ in entry.iterdir())
                    dir_meta = f"  ({child_count} items)" if child_count > 0 else "  (vacío)"
                except PermissionError:
                    dir_meta = "  (sin permisos)"

                lines.append(f"{prefix}{connector}{icon} {name}/{dir_meta}")
                count += 1

                # Recursión
                if current_depth < max_depth:
                    count += self._build_tree(
                        lines, entry, child_prefix, max_depth, current_depth + 1,
                        show_hidden, show_size, show_date, sort_by,
                        filter_str, ignore_default, max_items - count,
                    )
            else:
                lines.append(f"{prefix}{connector}{icon} {name}{meta}")
                count += 1

        return count

    # ── Vista: Flat ───────────────────────────────────────────────────────

    def _view_flat(self, dir_path: Path, depth: int, show_hidden: bool,
                   show_size: bool, show_date: bool, sort_by: str,
                   filter_str: Optional[str], ignore_default: bool,
                   max_items: int) -> str:
        """Lista plana con detalles."""
        items: List[Dict[str, Any]] = []
        ignore_set = set() if not ignore_default else set()

        for entry, d in _walk_filtered(dir_path, ignore_set, depth):
            if not show_hidden and entry.name.startswith("."):
                continue

            if filter_str and not self._matches_filter(entry, filter_str):
                continue

            try:
                st = entry.stat()
            except (OSError, PermissionError):
                continue

            rel = entry.relative_to(dir_path) if entry.is_relative_to(dir_path) else entry

            items.append({
                "path": entry,
                "rel": str(rel),
                "name": entry.name,
                "icon": _file_icon(entry),
                "is_dir": entry.is_dir(),
                "size": st.st_size if entry.is_file() else 0,
                "mtime": st.st_mtime,
                "ext": entry.suffix.lower(),
            })

            if len(items) >= max_items:
                break

        # Ordenar
        items = self._sort_items(items, sort_by)

        # Formatear
        lines = [f"📂 **{dir_path.name}/** — {len(items)} items", ""]

        # Calcular anchos
        max_name = max((len(i["rel"]) for i in items), default=20)
        max_name = min(max_name, 60)

        for item in items:
            parts = [f"  {item['icon']} {item['rel']:<{max_name}s}"]

            if show_size and not item["is_dir"]:
                parts.append(f"  {_format_size(item['size']):>8s}")

            if show_date:
                parts.append(f"  {_format_time_ago(item['mtime']):>15s}")

            lines.append("".join(parts))

        return "\n".join(lines)

    # ── Vista: Stats ──────────────────────────────────────────────────────

    def _view_stats(self, dir_path: Path, depth: int, show_hidden: bool,
                    ignore_default: bool, max_items: int, **kw) -> str:
        """Estadísticas detalladas del directorio."""
        ext_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"count": 0, "size": 0})
        dir_count = 0
        file_count = 0
        total_size = 0
        largest_files: List[Tuple[str, int]] = []
        newest_files: List[Tuple[str, float]] = []
        empty_dirs: List[str] = []

        for entry, d in _walk_filtered(dir_path, set(), depth, max_depth=depth):
            if not show_hidden and entry.name.startswith("."):
                continue

            if entry.is_dir():
                dir_count += 1
                try:
                    if not any(entry.iterdir()):
                        rel = str(
                            entry.relative_to(dir_path)
                            if entry.is_relative_to(dir_path)
                            else entry
                        )
                        empty_dirs.append(rel)
                except PermissionError:
                    pass
                continue

            file_count += 1
            try:
                st = entry.stat()
                size = st.st_size
                mtime = st.st_mtime
            except (OSError, PermissionError):
                continue

            ext = entry.suffix.lower() or "(sin ext)"
            ext_stats[ext]["count"] += 1
            ext_stats[ext]["size"] += size
            total_size += size

            rel = str(
                entry.relative_to(dir_path)
                if entry.is_relative_to(dir_path)
                else entry
            )
            largest_files.append((rel, size))
            newest_files.append((rel, mtime))

        # Ordenar
        largest_files.sort(key=lambda x: x[1], reverse=True)
        newest_files.sort(key=lambda x: x[1], reverse=True)

        # ── Formatear ─────────────────────────────────────────────────────
        lines = [
            f"📊 **Estadísticas de `{dir_path.name}/`**",
            "",
            f"  📁 Directorios: {dir_count}",
            f"  📄 Archivos:    {file_count}",
            f"  💾 Tamaño total: {_format_size(total_size)}",
            "",
        ]

        # Distribución por extensión
        if ext_stats:
            sorted_exts = sorted(ext_stats.items(), key=lambda x: x[1]["count"], reverse=True)
            lines.append("  📊 **Por extensión:**")

            max_count = sorted_exts[0][1]["count"] if sorted_exts else 1
            bar_width = 25

            for ext, stats in sorted_exts[:15]:
                cnt = stats["count"]
                sz = stats["size"]
                filled = int(cnt / max_count * bar_width)
                bar = "█" * filled + "░" * (bar_width - filled)
                lines.append(
                    f"    {ext:>10s} {bar} {cnt:>4d} archivos ({_format_size(sz)})"
                )

            if len(sorted_exts) > 15:
                lines.append(f"    ... y {len(sorted_exts) - 15} tipos más")
            lines.append("")

        # Top archivos más grandes
        if largest_files:
            lines.append("  📦 **Archivos más grandes:**")
            for path_str, size in largest_files[:8]:
                lines.append(f"    {_format_size(size):>10s}  {path_str}")
            lines.append("")

        # Archivos más recientes
        if newest_files:
            lines.append("  🕐 **Modificados recientemente:**")
            for path_str, mtime in newest_files[:8]:
                lines.append(f"    {_format_time_ago(mtime):>15s}  {path_str}")
            lines.append("")

        # Directorios vacíos
        if empty_dirs:
            lines.append(f"  🗑️  **Directorios vacíos ({len(empty_dirs)}):**")
            for d in empty_dirs[:10]:
                lines.append(f"    📁 {d}")
            if len(empty_dirs) > 10:
                lines.append(f"    ... y {len(empty_dirs) - 10} más")

        return "\n".join(lines)

    # ── Vista: Summary (detección de proyecto) ────────────────────────────

    def _view_summary(self, dir_path: Path, ignore_default: bool, **kw) -> str:
        """Resumen inteligente del proyecto."""
        lines = [f"📋 **Resumen de `{dir_path.name}/`**", ""]

        # ── Detectar tipo de proyecto ─────────────────────────────────────
        project_markers = {
            "pyproject.toml":   ("Python (moderno)", "🐍"),
            "setup.py":         ("Python (legacy)", "🐍"),
            "setup.cfg":        ("Python", "🐍"),
            "requirements.txt": ("Python", "🐍"),
            "Pipfile":          ("Python (Pipenv)", "🐍"),
            "package.json":     ("Node.js", "🟢"),
            "Cargo.toml":       ("Rust", "🦀"),
            "go.mod":           ("Go", "🔵"),
            "pom.xml":          ("Java (Maven)", "☕"),
            "build.gradle":     ("Java (Gradle)", "☕"),
            "Gemfile":          ("Ruby", "💎"),
            "composer.json":    ("PHP", "🐘"),
            "CMakeLists.txt":   ("C/C++ (CMake)", "⚙️ "),
            "Makefile":         ("Make", "🔨"),
            "Dockerfile":       ("Docker", "🐳"),
            "docker-compose.yml": ("Docker Compose", "🐳"),
            ".terraform":       ("Terraform", "🏗️ "),
        }

        detected: List[Tuple[str, str]] = []
        for marker, (ptype, icon) in project_markers.items():
            if (dir_path / marker).exists():
                detected.append((ptype, icon))

        if detected:
            lines.append("  🏷️  **Tipo de proyecto:**")
            for ptype, icon in detected:
                lines.append(f"    {icon} {ptype}")
            lines.append("")

        # ── Leer metadata del proyecto ────────────────────────────────────
        metadata = self._read_project_metadata(dir_path)
        if metadata:
            lines.append("  📦 **Metadata:**")
            for key, value in metadata.items():
                lines.append(f"    {key}: {value}")
            lines.append("")

        # ── Estructura de directorios de primer nivel ─────────────────────
        lines.append("  📁 **Estructura:**")
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            for entry in entries:
                if entry.name.startswith(".") and entry.name not in (".env", ".gitignore", ".dockerignore"):
                    continue
                if entry.is_dir() and _should_ignore_dir(entry.name, set()):
                    continue

                icon = _file_icon(entry)
                if entry.is_dir():
                    try:
                        count = sum(1 for _ in entry.iterdir())
                        lines.append(f"    {icon} {entry.name}/ ({count} items)")
                    except PermissionError:
                        lines.append(f"    {icon} {entry.name}/ (sin permisos)")
                else:
                    lines.append(f"    {icon} {entry.name}")
        except PermissionError:
            lines.append("    ⚠️  Sin permisos para listar")

        lines.append("")

        # ── Archivos de configuración detectados ──────────────────────────
        config_files = []
        config_names = {
            ".gitignore", ".editorconfig", ".prettierrc", ".eslintrc.json",
            ".flake8", "ruff.toml", ".pre-commit-config.yaml",
            "tox.ini", "noxfile.py", ".github",
            "tsconfig.json", "webpack.config.js", "vite.config.ts",
        }
        for name in sorted(config_names):
            if (dir_path / name).exists():
                config_files.append(name)

        if config_files:
            lines.append("  ⚙️  **Configuración detectada:**")
            for cf in config_files:
                lines.append(f"    📋 {cf}")
            lines.append("")

        # ── README preview ────────────────────────────────────────────────
        for readme_name in ("README.md", "README.rst", "README.txt", "README"):
            readme_path = dir_path / readme_name
            if readme_path.exists():
                try:
                    content = readme_path.read_text(encoding="utf-8", errors="ignore")
                    preview = content[:300].strip()
                    if len(content) > 300:
                        preview += "..."
                    lines.append(f"  📖 **README** ({readme_name}):")
                    for line in preview.splitlines()[:8]:
                        lines.append(f"    {line}")
                except (OSError, PermissionError):
                    pass
                break

        return "\n".join(lines)

    @staticmethod
    def _read_project_metadata(dir_path: Path) -> Dict[str, str]:
        """Lee metadata del proyecto desde archivos de configuración."""
        metadata: Dict[str, str] = {}

        # pyproject.toml
        pyproject = dir_path / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore
                except ImportError:
                    tomllib = None  # type: ignore

            if tomllib:
                try:
                    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
                    project = data.get("project", {})
                    if project.get("name"):
                        metadata["Nombre"] = project["name"]
                    if project.get("version"):
                        metadata["Versión"] = project["version"]
                    if project.get("description"):
                        metadata["Descripción"] = project["description"][:80]
                    if project.get("requires-python"):
                        metadata["Python"] = project["requires-python"]
                except Exception:
                    pass

        # package.json
        pkg_json = dir_path / "package.json"
        if pkg_json.exists():
            try:
                import json
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                if data.get("name"):
                    metadata["Nombre"] = data["name"]
                if data.get("version"):
                    metadata["Versión"] = data["version"]
                if data.get("description"):
                    metadata["Descripción"] = data["description"][:80]
            except Exception:
                pass

        # Cargo.toml (básico, sin parser TOML)
        cargo = dir_path / "Cargo.toml"
        if cargo.exists() and not metadata:
            try:
                text = cargo.read_text(encoding="utf-8")
                for line in text.splitlines():
                    for key in ("name", "version"):
                        match = re.match(rf'^{key}\s*=\s*"(.+?)"', line)
                        if match:
                            metadata[key.capitalize()] = match.group(1)
            except (OSError, PermissionError):
                pass

        return metadata

    # ── Helpers compartidos ───────────────────────────────────────────────

    @staticmethod
    def _apply_filter(entries: List[Path], filter_str: str) -> List[Path]:
        """Aplica filtro a lista de entradas."""
        f = filter_str.lower().strip()

        # Filtro por tipo de entrada
        if f in ("dir", "directory", "dirs"):
            return [e for e in entries if e.is_dir()]
        if f in ("file", "files"):
            return [e for e in entries if e.is_file()]

        # Filtro por categoría de extensión
        if f in _EXT_CATEGORIES:
            exts = _EXT_CATEGORIES[f]
            return [
                e for e in entries
                if e.is_dir() or e.suffix.lower() in exts
            ]

        # Filtro por glob
        if "*" in f or "?" in f:
            return [
                e for e in entries
                if e.is_dir() or fnmatch.fnmatch(e.name, f)
            ]

        # Filtro por extensión directa
        if f.startswith("."):
            return [
                e for e in entries
                if e.is_dir() or e.suffix.lower() == f
            ]

        return entries

    @staticmethod
    def _matches_filter(entry: Path, filter_str: str) -> bool:
        """Verifica si un entry pasa el filtro."""
        f = filter_str.lower().strip()
        if f in ("dir", "directory"):
            return entry.is_dir()
        if f in ("file", "files"):
            return entry.is_file()
        if f in _EXT_CATEGORIES:
            return entry.is_dir() or entry.suffix.lower() in _EXT_CATEGORIES[f]
        if "*" in f or "?" in f:
            return entry.is_dir() or fnmatch.fnmatch(entry.name, f)
        if f.startswith("."):
            return entry.is_dir() or entry.suffix.lower() == f
        return True

    @staticmethod
    def _sort_entries(entries: List[Path], sort_by: str) -> List[Path]:
        """Ordena entradas (directorios siempre primero)."""
        def key_fn(e: Path) -> tuple:
            is_file = e.is_file()
            try:
                st = e.stat()
            except (OSError, PermissionError):
                return (is_file, "")

            if sort_by == "size":
                return (is_file, -st.st_size if is_file else 0)
            if sort_by == "date":
                return (is_file, -st.st_mtime)
            if sort_by == "type":
                return (is_file, e.suffix.lower(), e.name.lower())
            # name (default)
            return (is_file, e.name.lower())

        return sorted(entries, key=key_fn)

    @staticmethod
    def _sort_items(items: List[Dict], sort_by: str) -> List[Dict]:
        """Ordena items dict."""
        if sort_by == "size":
            return sorted(items, key=lambda i: (-1 if i["is_dir"] else 0, -i["size"]))
        if sort_by == "date":
            return sorted(items, key=lambda i: -i["mtime"])
        if sort_by == "type":
            return sorted(items, key=lambda i: (-1 if i["is_dir"] else 0, i["ext"], i["name"].lower()))
        # name
        return sorted(items, key=lambda i: (-1 if i["is_dir"] else 0, i["name"].lower()))


# ─── 4. DUPLICATE FINDER TOOL ───────────────────────────────────────────────


class DuplicateFinderTool(BaseTool):
    """
    Encuentra archivos duplicados por contenido (hash), nombre o tamaño.
    Útil para limpieza de proyectos.
    """

    name = "find_duplicates"
    description = (
        "Encuentra archivos duplicados por contenido (hash SHA-256), "
        "nombre o tamaño exacto."
    )
    category = "search"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio raíz (default: '.')",
                required=False,
            ),
            "method": ToolParameter(
                name="method",
                type="string",
                description="Método: hash|name|size (default: hash)",
                required=False,
            ),
            "file_pattern": ToolParameter(
                name="file_pattern",
                type="string",
                description="Patrón de archivos (default: '*')",
                required=False,
            ),
            "min_size": ToolParameter(
                name="min_size",
                type="string",
                description="Tamaño mínimo para considerar (ej: '1KB'). Default: 1B",
                required=False,
            ),
            "max_depth": ToolParameter(
                name="max_depth",
                type="integer",
                description="Profundidad máxima de búsqueda",
                required=False,
            ),
        }

    def execute(
        self,
        directory: str = ".",
        method: str = "hash",
        file_pattern: str = "*",
        min_size: Optional[str] = None,
        max_depth: Optional[int] = None,
        **kwargs,
    ) -> str:
        dir_path = Path(directory or ".").resolve()
        if not dir_path.exists() or not dir_path.is_dir():
            return f"❌ Directorio no válido: {directory}"

        min_bytes = _parse_size(min_size) if min_size else 1
        method = (method or "hash").lower().strip()

        if method not in ("hash", "name", "size"):
            return f"❌ Método '{method}' no soportado. Usa: hash, name, size."

        # ── Recolectar archivos ───────────────────────────────────────────
        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        scanned = 0

        for entry, depth in _walk_filtered(dir_path, set(), max_depth):
            if not entry.is_file():
                continue
            if not fnmatch.fnmatch(entry.name, file_pattern):
                continue
            if _is_likely_binary(entry) and method == "hash":
                # Incluir binarios solo si son significativos
                pass

            try:
                st = entry.stat()
                if st.st_size < (min_bytes or 0):
                    continue
            except (OSError, PermissionError):
                continue

            scanned += 1

            rel = str(
                entry.relative_to(dir_path) if entry.is_relative_to(dir_path) else entry
            )
            info = {
                "path": rel,
                "abs_path": str(entry),
                "size": st.st_size,
                "mtime": st.st_mtime,
            }

            if method == "hash":
                # Fase 1: Agrupar por tamaño (optimización)
                key = f"size:{st.st_size}"
            elif method == "name":
                key = entry.name.lower()
            else:  # size
                key = str(st.st_size)

            buckets[key].append(info)

        # ── Fase 2: Refinar con hash (solo para method=hash) ──────────────
        if method == "hash":
            refined: Dict[str, List[Dict]] = defaultdict(list)
            for size_key, files in buckets.items():
                if len(files) < 2:
                    continue
                # Calcular hash real
                for f in files:
                    try:
                        h = hashlib.sha256(Path(f["abs_path"]).read_bytes()).hexdigest()
                        f["hash"] = h
                        refined[h].append(f)
                    except (OSError, PermissionError):
                        continue
            buckets = refined

        # ── Filtrar solo duplicados ───────────────────────────────────────
        duplicates = {k: v for k, v in buckets.items() if len(v) >= 2}

        if not duplicates:
            return (
                f"✅ No se encontraron duplicados ({method}) "
                f"en `{dir_path.name}/` ({scanned} archivos escaneados)"
            )

        # ── Formatear resultado ───────────────────────────────────────────
        total_groups = len(duplicates)
        total_dupes = sum(len(v) - 1 for v in duplicates.values())
        wasted_size = sum(
            sum(f["size"] for f in files[1:])
            for files in duplicates.values()
        )

        lines = [
            f"🔍 **Duplicados encontrados** (método: {method})",
            f"  {total_groups} grupos, {total_dupes} archivos duplicados",
            f"  Espacio recuperable: {_format_size(wasted_size)}",
            f"  ({scanned} archivos escaneados)",
            "",
        ]

        # Ordenar grupos por tamaño desperdiciado
        sorted_groups = sorted(
            duplicates.items(),
            key=lambda item: sum(f["size"] for f in item[1]),
            reverse=True,
        )

        for group_idx, (key, files) in enumerate(sorted_groups[:20], 1):
            size = files[0]["size"]
            key_display = key[:16] + "..." if len(key) > 16 else key

            lines.append(
                f"  📎 **Grupo {group_idx}** — {_format_size(size)} × {len(files)} copias"
                f" ({method}: `{key_display}`)"
            )
            for f in files:
                age = _format_time_ago(f["mtime"])
                lines.append(f"    📄 {f['path']}  ({age})")
            lines.append("")

        if len(sorted_groups) > 20:
            lines.append(f"  ... y {len(sorted_groups) - 20} grupos más")

        return "\n".join(lines)