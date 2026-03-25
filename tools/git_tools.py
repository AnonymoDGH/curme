# tools/git_tools.py
"""
NVIDIA CODE — Herramientas de Git

Operaciones Git seguras con validación, output estructurado,
análisis de repositorio y protección contra operaciones destructivas.
"""

import os
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from .base import BaseTool, ToolParameter


# ─── Infraestructura Git segura ──────────────────────────────────────────────


@dataclass
class GitResult:
    """Resultado estructurado de un comando git."""
    success: bool
    stdout: str
    stderr: str
    returncode: int
    command: List[str]

    @property
    def output(self) -> str:
        return self.stdout.strip()

    @property
    def lines(self) -> List[str]:
        return [l for l in self.stdout.strip().splitlines() if l]

    @property
    def error(self) -> str:
        return self.stderr.strip()


class GitError(Exception):
    """Error específico de operaciones Git."""
    def __init__(self, message: str, result: Optional[GitResult] = None):
        super().__init__(message)
        self.result = result


def _run_git(
    *args: str,
    cwd: Optional[str] = None,
    timeout: int = 30,
    check: bool = True,
    env_override: Optional[Dict[str, str]] = None,
) -> GitResult:
    """
    Ejecuta un comando git de forma segura (sin shell=True).

    Args:
        *args: Argumentos del comando git (sin 'git' al inicio).
        cwd: Directorio de trabajo.
        timeout: Timeout en segundos.
        check: Lanzar GitError si el comando falla.
        env_override: Variables de entorno adicionales.

    Returns:
        GitResult con stdout, stderr y metadata.

    Raises:
        GitError: Si check=True y el comando falla.
    """
    cmd = ["git"] + list(args)
    env = None
    if env_override:
        env = {**os.environ, **env_override}

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
    except FileNotFoundError:
        raise GitError("Git no está instalado o no está en el PATH.")
    except subprocess.TimeoutExpired:
        raise GitError(f"Timeout ({timeout}s) ejecutando: git {' '.join(args)}")

    result = GitResult(
        success=proc.returncode == 0,
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
        command=cmd,
    )

    if check and not result.success:
        error_msg = result.error or f"Comando falló con código {result.returncode}"
        raise GitError(error_msg, result)

    return result


def _find_git_root(start: Optional[str] = None) -> Optional[Path]:
    """Encuentra la raíz del repositorio git."""
    try:
        result = _run_git(
            "rev-parse", "--show-toplevel",
            cwd=start, check=False,
        )
        if result.success:
            return Path(result.output)
    except GitError:
        pass
    return None


def _is_git_repo(path: Optional[str] = None) -> bool:
    """Verifica si estamos dentro de un repositorio git."""
    return _find_git_root(path) is not None


def _current_branch(cwd: Optional[str] = None) -> str:
    """Obtiene la rama actual."""
    try:
        result = _run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd, check=False)
        return result.output if result.success else "(detached)"
    except GitError:
        return "(unknown)"


def _has_staged(cwd: Optional[str] = None) -> bool:
    """Verifica si hay cambios en staging."""
    result = _run_git("diff", "--cached", "--quiet", cwd=cwd, check=False)
    return not result.success


def _has_unstaged(cwd: Optional[str] = None) -> bool:
    """Verifica si hay cambios sin staging."""
    result = _run_git("diff", "--quiet", cwd=cwd, check=False)
    return not result.success


def _has_untracked(cwd: Optional[str] = None) -> bool:
    """Verifica si hay archivos sin tracking."""
    result = _run_git(
        "ls-files", "--others", "--exclude-standard",
        cwd=cwd, check=False,
    )
    return bool(result.output)


def _require_git_repo(cwd: Optional[str] = None) -> str:
    """Valida que estamos en un repo git. Retorna el cwd efectivo."""
    if not _is_git_repo(cwd):
        raise GitError(
            f"No se encontró repositorio Git en '{cwd or os.getcwd()}'.\n"
            "Ejecuta 'git init' para crear uno."
        )
    return cwd or "."


def _format_relative_date(iso_date: str) -> str:
    """Formatea fecha ISO a relativa."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        delta = datetime.now(dt.tzinfo) - dt
        if delta.days == 0:
            hours = delta.seconds // 3600
            if hours == 0:
                mins = delta.seconds // 60
                return f"hace {mins} min" if mins > 0 else "ahora"
            return f"hace {hours}h"
        if delta.days < 7:
            return f"hace {delta.days}d"
        if delta.days < 30:
            return f"hace {delta.days // 7} sem"
        if delta.days < 365:
            return f"hace {delta.days // 30} meses"
        return f"hace {delta.days // 365} años"
    except (ValueError, TypeError):
        return iso_date[:10] if len(iso_date) >= 10 else iso_date


# Archivos protegidos que requieren confirmación
_PROTECTED_PATTERNS = {
    ".env", ".env.production", ".env.local",
    "id_rsa", "id_ed25519", "credentials",
    ".secret", "secret_key", "password",
}

# Ramas protegidas
_PROTECTED_BRANCHES = {"main", "master", "production", "prod", "release"}


def _check_sensitive_files(files: List[str]) -> List[str]:
    """Detecta archivos sensibles en una lista."""
    warnings = []
    for f in files:
        name = Path(f).name.lower()
        for pattern in _PROTECTED_PATTERNS:
            if pattern in name:
                warnings.append(f"⚠️  Archivo sensible detectado: {f}")
                break
    return warnings


# ─── 1. GIT STATUS TOOL ─────────────────────────────────────────────────────


class GitStatusTool(BaseTool):
    """
    Muestra el estado del repositorio con información rica:
    rama, staging, cambios, archivos sin tracking, stashes,
    upstream status, y advertencias.
    """

    name = "git_status"
    description = (
        "Muestra estado completo del repositorio: rama, staging, "
        "cambios, upstream, stashes y advertencias."
    )
    category = "git"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio del repositorio (default: '.')",
                required=False,
            ),
            "short": ToolParameter(
                name="short",
                type="boolean",
                description="Mostrar versión compacta (default: false)",
                required=False,
            ),
        }

    def execute(
        self,
        directory: Optional[str] = None,
        short: bool = False,
        **kwargs,
    ) -> str:
        try:
            cwd = _require_git_repo(directory)
        except GitError as e:
            return f"❌ {e}"

        try:
            return self._full_status(cwd) if not short else self._short_status(cwd)
        except GitError as e:
            return f"❌ Error git: {e}"

    def _short_status(self, cwd: str) -> str:
        """Status compacto de una línea."""
        branch = _current_branch(cwd)
        result = _run_git("status", "--porcelain", cwd=cwd, check=False)
        changes = len(result.lines) if result.success else 0

        staged = sum(1 for l in result.lines if l and l[0] in "MADRCU")
        unstaged = sum(1 for l in result.lines if l and len(l) > 1 and l[1] in "MADRCU")
        untracked = sum(1 for l in result.lines if l.startswith("??"))

        parts = [f"🔀 `{branch}`"]
        if staged:
            parts.append(f"📦 {staged} staged")
        if unstaged:
            parts.append(f"✏️  {unstaged} modificados")
        if untracked:
            parts.append(f"❓ {untracked} sin tracking")
        if changes == 0:
            parts.append("✅ limpio")

        return " │ ".join(parts)

    def _full_status(self, cwd: str) -> str:
        """Status detallado con toda la información."""
        lines: List[str] = []

        # ── Rama y HEAD ───────────────────────────────────────────────────
        branch = _current_branch(cwd)
        head = _run_git("rev-parse", "--short", "HEAD", cwd=cwd, check=False)
        head_sha = head.output if head.success else "?"

        lines.append(f"🔀 **Git Status**")
        lines.append(f"  Rama: `{branch}` ({head_sha})")

        # ── Upstream ──────────────────────────────────────────────────────
        upstream = _run_git(
            "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}",
            cwd=cwd, check=False,
        )
        if upstream.success:
            ahead_behind = _run_git(
                "rev-list", "--left-right", "--count",
                f"{branch}...{upstream.output}",
                cwd=cwd, check=False,
            )
            if ahead_behind.success:
                parts = ahead_behind.output.split()
                if len(parts) == 2:
                    ahead, behind = int(parts[0]), int(parts[1])
                    status_parts = []
                    if ahead > 0:
                        status_parts.append(f"↑{ahead} adelante")
                    if behind > 0:
                        status_parts.append(f"↓{behind} detrás")
                    if not status_parts:
                        status_parts.append("✅ sincronizado")

                    lines.append(
                        f"  Upstream: `{upstream.output}` ({', '.join(status_parts)})"
                    )
        else:
            lines.append("  Upstream: (sin upstream configurado)")

        lines.append("")

        # ── Porcelain status ──────────────────────────────────────────────
        result = _run_git("status", "--porcelain=v1", cwd=cwd, check=False)

        staged: List[Tuple[str, str]] = []
        unstaged: List[Tuple[str, str]] = []
        untracked: List[str] = []
        conflicts: List[str] = []

        status_icons = {
            "M": ("✏️ ", "modificado"),
            "A": ("➕", "agregado"),
            "D": ("🗑️ ", "eliminado"),
            "R": ("📛", "renombrado"),
            "C": ("📋", "copiado"),
            "U": ("⚔️ ", "conflicto"),
        }

        for line in result.lines:
            if len(line) < 4:
                continue

            x, y = line[0], line[1]
            filepath = line[3:]

            # Conflictos de merge
            if x == "U" or y == "U" or (x == "A" and y == "A") or (x == "D" and y == "D"):
                conflicts.append(filepath)
                continue

            # Staged (index)
            if x != " " and x != "?":
                icon, desc = status_icons.get(x, ("❓", x))
                staged.append((f"{icon} {desc}", filepath))

            # Unstaged (working tree)
            if y != " " and y != "?":
                icon, desc = status_icons.get(y, ("❓", y))
                unstaged.append((f"{icon} {desc}", filepath))

            # Untracked
            if x == "?" and y == "?":
                untracked.append(filepath)

        # ── Conflictos ────────────────────────────────────────────────────
        if conflicts:
            lines.append(f"⚔️  **Conflictos de merge ({len(conflicts)}):**")
            for f in conflicts[:15]:
                lines.append(f"    ⚔️  {f}")
            if len(conflicts) > 15:
                lines.append(f"    ... y {len(conflicts) - 15} más")
            lines.append("")

        # ── Staging area ──────────────────────────────────────────────────
        if staged:
            lines.append(f"📦 **Staging area ({len(staged)}):**")
            for desc, filepath in staged[:20]:
                lines.append(f"    {desc}: {filepath}")
            if len(staged) > 20:
                lines.append(f"    ... y {len(staged) - 20} más")
            lines.append("")
        else:
            lines.append("📦 Staging area: (vacía)")
            lines.append("")

        # ── Cambios sin staging ───────────────────────────────────────────
        if unstaged:
            lines.append(f"✏️  **Cambios sin staging ({len(unstaged)}):**")
            for desc, filepath in unstaged[:20]:
                lines.append(f"    {desc}: {filepath}")
            if len(unstaged) > 20:
                lines.append(f"    ... y {len(unstaged) - 20} más")
            lines.append("")

        # ── Sin tracking ──────────────────────────────────────────────────
        if untracked:
            lines.append(f"❓ **Sin tracking ({len(untracked)}):**")
            for f in untracked[:15]:
                lines.append(f"    📄 {f}")
            if len(untracked) > 15:
                lines.append(f"    ... y {len(untracked) - 15} más")
            lines.append("")

        # ── Clean? ────────────────────────────────────────────────────────
        if not staged and not unstaged and not untracked and not conflicts:
            lines.append("✅ Directorio de trabajo limpio.")
            lines.append("")

        # ── Stashes ───────────────────────────────────────────────────────
        stash = _run_git("stash", "list", cwd=cwd, check=False)
        if stash.success and stash.output:
            stash_count = len(stash.lines)
            lines.append(f"📥 **Stashes ({stash_count}):**")
            for s in stash.lines[:5]:
                lines.append(f"    {s}")
            if stash_count > 5:
                lines.append(f"    ... y {stash_count - 5} más")
            lines.append("")

        # ── Advertencias ──────────────────────────────────────────────────
        all_files = [f for _, f in staged] + [f for _, f in unstaged] + untracked
        warnings = _check_sensitive_files(all_files)
        if warnings:
            lines.append("🚨 **Advertencias:**")
            for w in warnings:
                lines.append(f"  {w}")

        # ── Resumen ───────────────────────────────────────────────────────
        total = len(staged) + len(unstaged) + len(untracked) + len(conflicts)
        summary = []
        if staged:
            summary.append(f"{len(staged)} staged")
        if unstaged:
            summary.append(f"{len(unstaged)} modificados")
        if untracked:
            summary.append(f"{len(untracked)} sin tracking")
        if conflicts:
            summary.append(f"{len(conflicts)} conflictos")

        if summary:
            lines.append(f"📊 Resumen: {', '.join(summary)} ({total} total)")

        return "\n".join(lines)


# ─── 2. GIT LOG TOOL ────────────────────────────────────────────────────────


class GitLogTool(BaseTool):
    """
    Muestra historial de commits con múltiples formatos de visualización,
    filtros por autor, fecha, ruta, y estadísticas.
    """

    name = "git_log"
    description = (
        "Muestra historial de commits con formatos: oneline, detailed, "
        "graph, stats. Filtros por autor, fecha, ruta, y mensaje."
    )
    category = "git"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "count": ToolParameter(
                name="count",
                type="integer",
                description="Número de commits a mostrar (default: 15)",
                required=False,
            ),
            "format": ToolParameter(
                name="format",
                type="string",
                description="Formato: oneline|detailed|graph|stats|authors (default: oneline)",
                required=False,
            ),
            "author": ToolParameter(
                name="author",
                type="string",
                description="Filtrar por autor (substring)",
                required=False,
            ),
            "since": ToolParameter(
                name="since",
                type="string",
                description="Desde fecha: '1 week ago', '2024-01-01', '3 days ago'",
                required=False,
            ),
            "until": ToolParameter(
                name="until",
                type="string",
                description="Hasta fecha",
                required=False,
            ),
            "path": ToolParameter(
                name="path",
                type="string",
                description="Filtrar por ruta de archivo",
                required=False,
            ),
            "search": ToolParameter(
                name="search",
                type="string",
                description="Buscar en mensajes de commit (grep)",
                required=False,
            ),
            "branch": ToolParameter(
                name="branch",
                type="string",
                description="Rama específica (default: actual)",
                required=False,
            ),
            "all_branches": ToolParameter(
                name="all_branches",
                type="boolean",
                description="Mostrar commits de todas las ramas (default: false)",
                required=False,
            ),
            "merges": ToolParameter(
                name="merges",
                type="string",
                description="Filtro de merges: only|no|all (default: all)",
                required=False,
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio del repositorio",
                required=False,
            ),
        }

    def execute(
        self,
        count: int = 15,
        format: str = "oneline",
        author: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        path: Optional[str] = None,
        search: Optional[str] = None,
        branch: Optional[str] = None,
        all_branches: bool = False,
        merges: str = "all",
        directory: Optional[str] = None,
        **kwargs,
    ) -> str:
        try:
            cwd = _require_git_repo(directory)
        except GitError as e:
            return f"❌ {e}"

        fmt = (format or "oneline").lower().strip()

        formatters = {
            "oneline":  self._log_oneline,
            "detailed": self._log_detailed,
            "graph":    self._log_graph,
            "stats":    self._log_stats,
            "authors":  self._log_authors,
        }

        formatter = formatters.get(fmt)
        if not formatter:
            return f"❌ Formato '{fmt}' no soportado. Opciones: {', '.join(formatters)}"

        try:
            return formatter(
                cwd=cwd, count=count, author=author, since=since,
                until=until, path=path, search=search, branch=branch,
                all_branches=all_branches, merges=merges,
            )
        except GitError as e:
            return f"❌ Error git: {e}"

    def _build_log_args(
        self,
        count: int,
        author: Optional[str],
        since: Optional[str],
        until: Optional[str],
        search: Optional[str],
        branch: Optional[str],
        all_branches: bool,
        merges: str,
        extra_args: Optional[List[str]] = None,
    ) -> List[str]:
        """Construye los argumentos comunes para git log."""
        args = ["log", f"-{count}"]

        if author:
            args.append(f"--author={author}")
        if since:
            args.append(f"--since={since}")
        if until:
            args.append(f"--until={until}")
        if search:
            args.extend(["--grep", search])
        if all_branches:
            args.append("--all")
        elif branch:
            args.append(branch)

        if merges == "no":
            args.append("--no-merges")
        elif merges == "only":
            args.append("--merges")

        if extra_args:
            args.extend(extra_args)

        return args

    def _log_oneline(self, cwd: str, path: Optional[str] = None, **kw) -> str:
        """Formato compacto de una línea por commit."""
        args = self._build_log_args(
            extra_args=[
                "--format=%h %C(auto)%d%C(reset) %s %C(dim)(%cr, %an)%C(reset)",
                "--abbrev-commit",
            ],
            **kw,
        )

        if path:
            args.extend(["--", path])

        result = _run_git(*args, cwd=cwd)

        branch = _current_branch(cwd)
        header = f"📜 **Git Log** — `{branch}`"
        if kw.get("author"):
            header += f" (autor: {kw['author']})"
        if kw.get("since"):
            header += f" (desde: {kw['since']})"

        if not result.output:
            return f"{header}\n\n  (sin commits)"

        # Parsear y re-formatear con emojis
        formatted_lines: List[str] = []
        for line in result.lines:
            formatted_lines.append(f"  {self._commit_icon(line)} {line}")

        return f"{header}\n\n" + "\n".join(formatted_lines)

    def _log_detailed(self, cwd: str, path: Optional[str] = None, **kw) -> str:
        """Formato detallado con stats por commit."""
        sep = "---COMMIT_SEP---"
        fmt = f"%h{sep}%an{sep}%ae{sep}%aI{sep}%s{sep}%b{sep}%D"
        args = self._build_log_args(
            extra_args=[f"--format={fmt}", "--stat"],
            **kw,
        )

        if path:
            args.extend(["--", path])

        result = _run_git(*args, cwd=cwd)

        lines = [f"📜 **Git Log (detallado)** — `{_current_branch(cwd)}`", ""]

        # Parsing simplificado: separar por líneas que contienen nuestro separador
        commit_chunks = result.output.split(sep)

        # Usar git log con formato simple para parseo confiable
        args2 = self._build_log_args(
            extra_args=["--format=%h|||%an|||%aI|||%s|||%D", "--stat=80"],
            **kw,
        )
        if path:
            args2.extend(["--", path])

        result2 = _run_git(*args2, cwd=cwd)

        current_commit: Optional[Dict[str, str]] = None
        stat_lines: List[str] = []

        for line in result2.stdout.splitlines():
            if "|||" in line:
                # Nueva entrada de commit: flush anterior
                if current_commit:
                    lines.extend(self._format_commit_detail(current_commit, stat_lines))
                    lines.append("")

                parts = line.split("|||")
                if len(parts) >= 4:
                    current_commit = {
                        "sha": parts[0].strip(),
                        "author": parts[1].strip(),
                        "date": parts[2].strip(),
                        "subject": parts[3].strip(),
                        "refs": parts[4].strip() if len(parts) > 4 else "",
                    }
                stat_lines = []
            elif current_commit and line.strip():
                stat_lines.append(line)

        # Último commit
        if current_commit:
            lines.extend(self._format_commit_detail(current_commit, stat_lines))

        return "\n".join(lines)

    def _log_graph(self, cwd: str, **kw) -> str:
        """Formato con grafo ASCII de ramas."""
        args = self._build_log_args(
            extra_args=[
                "--graph",
                "--format=%C(bold)%h%C(reset) %s %C(dim)(%cr)%C(reset)%C(auto)%d",
                "--abbrev-commit",
            ],
            **kw,
        )

        result = _run_git(*args, cwd=cwd)

        branch = _current_branch(cwd)
        return f"🌳 **Git Graph** — `{branch}`\n\n```\n{result.output}\n```"

    def _log_stats(self, cwd: str, **kw) -> str:
        """Estadísticas de commits: autores, frecuencia, archivos."""
        args = self._build_log_args(
            extra_args=["--format=%aI|||%an|||%ae|||%s", "--shortstat"],
            **kw,
        )

        result = _run_git(*args, cwd=cwd)

        authors: Counter = Counter()
        dates: Counter = Counter()
        total_insertions = 0
        total_deletions = 0
        commit_count = 0
        conventional: Counter = Counter()

        for line in result.stdout.splitlines():
            if "|||" in line:
                parts = line.split("|||")
                if len(parts) >= 3:
                    commit_count += 1
                    authors[parts[1].strip()] += 1

                    try:
                        date = parts[0].strip()[:10]
                        dates[date] += 1
                    except (ValueError, IndexError):
                        pass

                    # Conventional commit type
                    subject = parts[3].strip() if len(parts) > 3 else ""
                    cc_match = re.match(r"^(\w+)[\(:]", subject)
                    if cc_match:
                        conventional[cc_match.group(1).lower()] += 1

            elif "insertion" in line or "deletion" in line:
                ins = re.search(r"(\d+) insertion", line)
                dels = re.search(r"(\d+) deletion", line)
                if ins:
                    total_insertions += int(ins.group(1))
                if dels:
                    total_deletions += int(dels.group(1))

        # ── Formatear ─────────────────────────────────────────────────────
        lines = [
            f"📊 **Git Stats** — `{_current_branch(cwd)}`",
            "",
            f"  📝 Commits: {commit_count}",
            f"  👥 Autores: {len(authors)}",
            f"  ➕ Inserciones: {total_insertions:,}",
            f"  ➖ Eliminaciones: {total_deletions:,}",
            f"  📊 Neto: {total_insertions - total_deletions:+,}",
            "",
        ]

        # Top autores
        if authors:
            lines.append("  👥 **Autores:**")
            max_commits = authors.most_common(1)[0][1]
            bar_w = 25

            for author, count in authors.most_common(10):
                filled = int(count / max_commits * bar_w)
                bar = "█" * filled + "░" * (bar_w - filled)
                pct = count / commit_count * 100
                lines.append(f"    {author:>20s} {bar} {count} ({pct:.0f}%)")
            lines.append("")

        # Actividad por día
        if dates:
            lines.append("  📅 **Actividad reciente:**")
            sorted_dates = sorted(dates.items(), reverse=True)[:14]
            max_day = max(v for _, v in sorted_dates) if sorted_dates else 1

            for date, count in sorted_dates:
                bar = "█" * int(count / max_day * 20)
                lines.append(f"    {date} {bar} {count}")
            lines.append("")

        # Conventional commits
        if conventional:
            lines.append("  🏷️  **Tipos de commit:**")
            for ctype, count in conventional.most_common(10):
                emoji = {"feat": "✨", "fix": "🐛", "docs": "📝", "refactor": "♻️ ",
                         "test": "🧪", "chore": "🔧", "style": "💄", "perf": "⚡",
                         "ci": "🔄", "build": "📦"}.get(ctype, "📎")
                lines.append(f"    {emoji} {ctype}: {count}")

        return "\n".join(lines)

    def _log_authors(self, cwd: str, **kw) -> str:
        """Resumen por autor."""
        # Usar shortlog
        args = ["shortlog", "-sne", "--all"]
        if kw.get("since"):
            args.append(f"--since={kw['since']}")

        result = _run_git(*args, cwd=cwd)

        lines = [f"👥 **Autores** — `{_current_branch(cwd)}`", ""]

        total = 0
        entries: List[Tuple[int, str]] = []
        for line in result.lines:
            match = re.match(r"\s*(\d+)\s+(.+)", line)
            if match:
                count = int(match.group(1))
                author = match.group(2).strip()
                entries.append((count, author))
                total += count

        if not entries:
            return lines[0] + "\n\n  (sin autores)"

        max_count = entries[0][0]
        bar_w = 30

        for count, author in entries[:20]:
            filled = int(count / max_count * bar_w)
            bar = "█" * filled + "░" * (bar_w - filled)
            pct = count / total * 100
            lines.append(f"  {author:>30s}  {bar} {count:>5d} ({pct:.1f}%)")

        lines.append(f"\n  Total: {total} commits, {len(entries)} autores")
        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _commit_icon(message: str) -> str:
        """Asigna emoji basado en conventional commit o palabras clave."""
        msg = message.lower()
        patterns = {
            "feat": "✨", "fix": "🐛", "bug": "🐛",
            "docs": "📝", "doc": "📝",
            "refactor": "♻️ ", "style": "💄",
            "test": "🧪", "perf": "⚡",
            "chore": "🔧", "build": "📦",
            "ci": "🔄", "merge": "🔀",
            "revert": "⏪", "hotfix": "🚑",
            "wip": "🚧", "init": "🎉",
            "release": "🚀", "version": "🔖",
            "security": "🔒", "deps": "📌",
            "breaking": "💥", "remove": "🔥",
        }
        for keyword, emoji in patterns.items():
            if keyword in msg:
                return emoji
        return "●"

    @staticmethod
    def _format_commit_detail(
        commit: Dict[str, str], stat_lines: List[str],
    ) -> List[str]:
        """Formatea un commit individual con detalle."""
        lines = []
        sha = commit["sha"]
        author = commit["author"]
        date = _format_relative_date(commit["date"])
        subject = commit["subject"]
        refs = commit.get("refs", "")

        ref_str = f" ({refs})" if refs else ""
        lines.append(f"  ┌─ `{sha}`{ref_str}")
        lines.append(f"  │ {subject}")
        lines.append(f"  │ 👤 {author} — {date}")

        if stat_lines:
            # Última línea suele ser el resumen "X files changed..."
            summary = stat_lines[-1].strip() if stat_lines else ""
            if "changed" in summary:
                lines.append(f"  │ 📊 {summary}")
            file_stats = [s for s in stat_lines[:-1] if "|" in s]
            for fs in file_stats[:5]:
                lines.append(f"  │   {fs.strip()}")
            if len(file_stats) > 5:
                lines.append(f"  │   ... y {len(file_stats) - 5} archivos más")

        lines.append(f"  └{'─' * 50}")
        return lines


# ─── 3. GIT DIFF TOOL ───────────────────────────────────────────────────────


class GitDiffTool(BaseTool):
    """
    Muestra diferencias en el repositorio con estadísticas,
    filtros y múltiples formatos.
    """

    name = "git_diff"
    description = (
        "Muestra diferencias: staging vs working, commits, ramas. "
        "Con estadísticas, filtros por ruta y formatos configurables."
    )
    category = "git"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "target": ToolParameter(
                name="target",
                type="string",
                description=(
                    "Qué comparar: staged|unstaged|head|<commit>..<commit>|<branch>..<branch> "
                    "(default: unstaged)"
                ),
                required=False,
            ),
            "path": ToolParameter(
                name="path",
                type="string",
                description="Filtrar por ruta de archivo",
                required=False,
            ),
            "stat_only": ToolParameter(
                name="stat_only",
                type="boolean",
                description="Solo estadísticas (sin diff completo). Default: false",
                required=False,
            ),
            "name_only": ToolParameter(
                name="name_only",
                type="boolean",
                description="Solo nombres de archivos cambiados. Default: false",
                required=False,
            ),
            "context": ToolParameter(
                name="context",
                type="integer",
                description="Líneas de contexto (default: 3)",
                required=False,
            ),
            "ignore_whitespace": ToolParameter(
                name="ignore_whitespace",
                type="boolean",
                description="Ignorar cambios de whitespace. Default: false",
                required=False,
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio del repositorio",
                required=False,
            ),
        }

    def execute(
        self,
        target: str = "unstaged",
        path: Optional[str] = None,
        stat_only: bool = False,
        name_only: bool = False,
        context: int = 3,
        ignore_whitespace: bool = False,
        directory: Optional[str] = None,
        **kwargs,
    ) -> str:
        try:
            cwd = _require_git_repo(directory)
        except GitError as e:
            return f"❌ {e}"

        target = (target or "unstaged").strip()

        # ── Construir argumentos ──────────────────────────────────────────
        args = ["diff"]

        if target == "staged":
            args.append("--cached")
        elif target == "unstaged":
            pass  # default: working tree vs index
        elif target == "head":
            args.append("HEAD")
        elif ".." in target:
            args.append(target)
        else:
            args.append(target)

        if stat_only:
            args.append("--stat")
        elif name_only:
            args.append("--name-status")
        else:
            args.extend([f"-U{context}"])

        if ignore_whitespace:
            args.append("-w")

        if path:
            args.extend(["--", path])

        try:
            result = _run_git(*args, cwd=cwd, check=False)
        except GitError as e:
            return f"❌ {e}"

        if not result.output:
            return f"✅ Sin diferencias ({target})."

        # ── Estadísticas adicionales ──────────────────────────────────────
        stat_result = _run_git(
            "diff", *(args[1:] if not stat_only else []),
            "--stat", "--", *(path,) if path else (),
            cwd=cwd, check=False,
        )

        # Contar cambios
        added = sum(1 for l in result.output.splitlines() if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in result.output.splitlines() if l.startswith("-") and not l.startswith("---"))

        header = f"🔍 **Git Diff** — `{target}`"
        if path:
            header += f" (`{path}`)"

        stats_line = f"  ➕ {added} inserciones, ➖ {removed} eliminaciones"

        if stat_only or name_only:
            return f"{header}\n{stats_line}\n\n```\n{result.output}\n```"

        # Limitar output largo
        output = result.output
        truncated = ""
        max_len = 5000
        if len(output) > max_len:
            output = output[:max_len]
            truncated = f"\n\n⚠️  Diff truncado ({len(result.output):,} chars). Usa `stat_only=true` para resumen."

        return f"{header}\n{stats_line}\n\n```diff\n{output}\n```{truncated}"


# ─── 4. GIT COMMIT TOOL ─────────────────────────────────────────────────────


class GitCommitTool(BaseTool):
    """
    Realiza commits con validación de mensaje, conventional commits,
    staging selectivo y protecciones de seguridad.
    """

    name = "git_commit"
    description = (
        "Crea commits con validación de mensaje, conventional commits, "
        "staging selectivo, y verificación de archivos sensibles."
    )
    category = "git"

    # Conventional commit types válidos
    _CC_TYPES = {
        "feat", "fix", "docs", "style", "refactor", "perf",
        "test", "build", "ci", "chore", "revert",
    }

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "message": ToolParameter(
                name="message",
                type="string",
                description="Mensaje del commit",
                required=True,
            ),
            "files": ToolParameter(
                name="files",
                type="string",
                description="Archivos a incluir (coma-separados o '.' para todo). Default: solo staging",
                required=False,
            ),
            "type": ToolParameter(
                name="type",
                type="string",
                description="Tipo conventional commit: feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert",
                required=False,
            ),
            "scope": ToolParameter(
                name="scope",
                type="string",
                description="Scope del conventional commit (ej: 'api', 'auth')",
                required=False,
            ),
            "breaking": ToolParameter(
                name="breaking",
                type="boolean",
                description="Marcar como breaking change (default: false)",
                required=False,
            ),
            "body": ToolParameter(
                name="body",
                type="string",
                description="Cuerpo detallado del commit",
                required=False,
            ),
            "amend": ToolParameter(
                name="amend",
                type="boolean",
                description="Enmendar último commit (default: false)",
                required=False,
            ),
            "allow_empty": ToolParameter(
                name="allow_empty",
                type="boolean",
                description="Permitir commit vacío (default: false)",
                required=False,
            ),
            "dry_run": ToolParameter(
                name="dry_run",
                type="boolean",
                description="Simular sin ejecutar (default: false)",
                required=False,
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio del repositorio",
                required=False,
            ),
        }

    def execute(
        self,
        message: Optional[str] = None,
        files: Optional[str] = None,
        type: Optional[str] = None,
        scope: Optional[str] = None,
        breaking: bool = False,
        body: Optional[str] = None,
        amend: bool = False,
        allow_empty: bool = False,
        dry_run: bool = False,
        directory: Optional[str] = None,
        **kwargs,
    ) -> str:
        if not message and not amend:
            return "❌ Se requiere 'message' para el commit."

        try:
            cwd = _require_git_repo(directory)
        except GitError as e:
            return f"❌ {e}"

        # ── Construir mensaje de commit ───────────────────────────────────
        if type:
            type_lower = type.lower().strip()
            if type_lower not in self._CC_TYPES:
                return (
                    f"❌ Tipo '{type}' no es un conventional commit válido.\n"
                    f"   Opciones: {', '.join(sorted(self._CC_TYPES))}"
                )

            prefix = type_lower
            if scope:
                prefix += f"({scope})"
            if breaking:
                prefix += "!"

            full_message = f"{prefix}: {message}"
        else:
            full_message = message or ""

        if body:
            full_message += f"\n\n{body}"

        if breaking and body and "BREAKING CHANGE:" not in body:
            full_message += f"\n\nBREAKING CHANGE: {message}"

        # ── Validar mensaje ───────────────────────────────────────────────
        warnings: List[str] = []
        errors: List[str] = []

        first_line = full_message.split("\n")[0]
        if len(first_line) > 72:
            warnings.append(f"⚠️  Primera línea tiene {len(first_line)} chars (recomendado: ≤72)")
        if len(first_line) < 3:
            errors.append("❌ Mensaje demasiado corto")
        if first_line and first_line[0].isupper() and type:
            warnings.append("⚠️  Conventional commits usan minúscula al inicio")

        if errors:
            return "\n".join(errors)

        # ── Staging ───────────────────────────────────────────────────────
        staged_files: List[str] = []
        if files:
            file_list = [f.strip() for f in files.split(",") if f.strip()]

            if file_list == ["."]:
                if not dry_run:
                    _run_git("add", ".", cwd=cwd)
                staged_files = ["(todos)"]
            else:
                for f in file_list:
                    file_path = Path(cwd) / f if cwd != "." else Path(f)
                    if not file_path.exists() and not amend:
                        return f"❌ Archivo no encontrado: {f}"
                    if not dry_run:
                        _run_git("add", f, cwd=cwd)
                staged_files = file_list

            # Verificar archivos sensibles
            sens_warnings = _check_sensitive_files(file_list)
            if sens_warnings:
                warnings.extend(sens_warnings)
                warnings.append("   Usa .gitignore para excluir archivos sensibles.")

        # Verificar que hay algo para commitear
        if not amend and not allow_empty:
            if not _has_staged(cwd) and not staged_files:
                return (
                    "❌ No hay cambios en staging.\n"
                    "   Usa 'files' para agregar archivos, o haz `git add` primero."
                )

        # ── Dry run ───────────────────────────────────────────────────────
        if dry_run:
            lines = [
                "🧪 **Dry Run — Commit simulado**",
                "",
                f"  Mensaje: {first_line}",
            ]
            if body:
                lines.append(f"  Body: {body[:100]}...")
            if staged_files:
                lines.append(f"  Archivos: {', '.join(staged_files)}")
            if amend:
                lines.append("  Modo: --amend")
            if warnings:
                lines.append("")
                lines.extend(warnings)
            lines.append("\n  ℹ️  Usa dry_run=false para ejecutar.")
            return "\n".join(lines)

        # ── Ejecutar commit ───────────────────────────────────────────────
        commit_args = ["commit", "-m", full_message]
        if amend:
            commit_args.append("--amend")
        if allow_empty:
            commit_args.append("--allow-empty")

        try:
            result = _run_git(*commit_args, cwd=cwd)
        except GitError as e:
            return f"❌ Error en commit: {e}"

        # ── Obtener info del commit creado ────────────────────────────────
        new_sha = _run_git("rev-parse", "--short", "HEAD", cwd=cwd, check=False)
        sha = new_sha.output if new_sha.success else "?"

        branch = _current_branch(cwd)
        emoji = self._commit_emoji(type or "")

        lines = [
            f"{emoji} **Commit creado** — `{sha}` en `{branch}`",
            "",
            f"  {first_line}",
        ]

        if body:
            lines.append(f"  {body[:200]}")

        if warnings:
            lines.append("")
            lines.extend(warnings)

        # Stat del commit
        stat = _run_git("diff", "--stat", "HEAD~1..HEAD", cwd=cwd, check=False)
        if stat.success and stat.output:
            lines.append("")
            lines.append(f"  📊 {stat.lines[-1].strip()}" if stat.lines else "")

        return "\n".join(lines)

    @staticmethod
    def _commit_emoji(cc_type: str) -> str:
        """Emoji para el tipo de commit."""
        emojis = {
            "feat": "✨", "fix": "🐛", "docs": "📝", "style": "💄",
            "refactor": "♻️ ", "perf": "⚡", "test": "🧪", "build": "📦",
            "ci": "🔄", "chore": "🔧", "revert": "⏪",
        }
        return emojis.get(cc_type.lower(), "✅")


# ─── 5. GIT BRANCH TOOL ─────────────────────────────────────────────────────


class GitBranchTool(BaseTool):
    """
    Gestión de ramas: listar, crear, eliminar, renombrar,
    comparar y analizar.
    """

    name = "git_branch"
    description = (
        "Gestiona ramas: listar, crear, eliminar, renombrar, "
        "cambiar, comparar y analizar."
    )
    category = "git"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description=(
                    "Acción: list|create|delete|rename|switch|compare|info|cleanup "
                    "(default: list)"
                ),
                required=False,
            ),
            "name": ToolParameter(
                name="name",
                type="string",
                description="Nombre de la rama",
                required=False,
            ),
            "new_name": ToolParameter(
                name="new_name",
                type="string",
                description="Nuevo nombre (para rename)",
                required=False,
            ),
            "base": ToolParameter(
                name="base",
                type="string",
                description="Rama base para create/compare (default: HEAD)",
                required=False,
            ),
            "remote": ToolParameter(
                name="remote",
                type="boolean",
                description="Incluir ramas remotas (default: false)",
                required=False,
            ),
            "force": ToolParameter(
                name="force",
                type="boolean",
                description="Forzar operación (ej: delete rama no mergeada). Default: false",
                required=False,
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio del repositorio",
                required=False,
            ),
        }

    def execute(
        self,
        action: str = "list",
        name: Optional[str] = None,
        new_name: Optional[str] = None,
        base: Optional[str] = None,
        remote: bool = False,
        force: bool = False,
        directory: Optional[str] = None,
        **kwargs,
    ) -> str:
        try:
            cwd = _require_git_repo(directory)
        except GitError as e:
            return f"❌ {e}"

        action = (action or "list").lower().strip()

        actions = {
            "list":    self._list,
            "create":  self._create,
            "delete":  self._delete,
            "rename":  self._rename,
            "switch":  self._switch,
            "compare": self._compare,
            "info":    self._info,
            "cleanup": self._cleanup,
        }

        handler = actions.get(action)
        if not handler:
            return f"❌ Acción '{action}' no soportada. Opciones: {', '.join(actions)}"

        try:
            return handler(
                cwd=cwd, name=name, new_name=new_name,
                base=base, remote=remote, force=force,
            )
        except GitError as e:
            return f"❌ Error git: {e}"

    def _list(self, cwd: str, remote: bool, **kw) -> str:
        """Lista ramas con información de último commit."""
        args = ["branch", "-v", "--sort=-committerdate"]
        if remote:
            args.append("-a")

        result = _run_git(*args, cwd=cwd)
        current = _current_branch(cwd)

        lines = [f"🌿 **Ramas** (actual: `{current}`)", ""]

        for line in result.lines:
            line = line.strip()
            is_current = line.startswith("*")
            line = line.lstrip("* ").strip()

            # Parsear: nombre sha mensaje
            parts = line.split(None, 2)
            if len(parts) < 2:
                continue

            branch_name = parts[0]
            sha = parts[1] if len(parts) > 1 else ""
            msg = parts[2] if len(parts) > 2 else ""

            marker = "→ " if is_current else "  "
            protected = " 🔒" if branch_name in _PROTECTED_BRANCHES else ""
            remote_indicator = " 🌐" if branch_name.startswith("remotes/") else ""

            lines.append(
                f"  {marker}🌿 `{branch_name}`{protected}{remote_indicator}"
                f" — {sha} {msg[:60]}"
            )

        # Contar
        local_count = len([l for l in result.lines if not l.strip().startswith("remotes/")])
        lines.append(f"\n  📊 {local_count} rama(s) local(es)")

        return "\n".join(lines)

    def _create(self, cwd: str, name: Optional[str], base: Optional[str], **kw) -> str:
        """Crea una nueva rama."""
        if not name:
            return "❌ Se requiere 'name' para crear una rama."

        # Validar nombre
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]*$", name):
            return f"❌ Nombre de rama inválido: '{name}'"

        args = ["checkout", "-b", name]
        if base:
            args.append(base)

        _run_git(*args, cwd=cwd)
        return f"✅ Rama `{name}` creada y activada" + (f" (base: `{base}`)" if base else "")

    def _delete(self, cwd: str, name: Optional[str], force: bool, **kw) -> str:
        """Elimina una rama."""
        if not name:
            return "❌ Se requiere 'name' para eliminar."

        current = _current_branch(cwd)
        if name == current:
            return f"❌ No puedes eliminar la rama actual (`{name}`). Cambia a otra primero."

        if name in _PROTECTED_BRANCHES and not force:
            return (
                f"🔒 `{name}` es una rama protegida.\n"
                "   Usa force=true si realmente quieres eliminarla."
            )

        flag = "-D" if force else "-d"
        _run_git("branch", flag, name, cwd=cwd)
        return f"✅ Rama `{name}` eliminada" + (" (forzado)" if force else "")

    def _rename(self, cwd: str, name: Optional[str], new_name: Optional[str], **kw) -> str:
        """Renombra una rama."""
        if not new_name:
            return "❌ Se requiere 'new_name'."

        old = name or _current_branch(cwd)
        _run_git("branch", "-m", old, new_name, cwd=cwd)
        return f"✅ Rama renombrada: `{old}` → `{new_name}`"

    def _switch(self, cwd: str, name: Optional[str], **kw) -> str:
        """Cambia de rama."""
        if not name:
            return "❌ Se requiere 'name'."

        # Verificar cambios sin commitear
        if _has_unstaged(cwd) or _has_staged(cwd):
            return (
                f"⚠️  Tienes cambios sin commitear. Opciones:\n"
                f"  1. Commitea primero: `git commit`\n"
                f"  2. Guarda en stash: `git stash`\n"
                f"  3. Descarta cambios: `git checkout .`"
            )

        _run_git("checkout", name, cwd=cwd)
        return f"✅ Cambiado a rama `{name}`"

    def _compare(self, cwd: str, name: Optional[str], base: Optional[str], **kw) -> str:
        """Compara dos ramas."""
        if not name:
            name = _current_branch(cwd)

        base = base or "main"

        # Verificar que ambas existen
        for branch in (name, base):
            check = _run_git("rev-parse", "--verify", branch, cwd=cwd, check=False)
            if not check.success:
                return f"❌ Rama no encontrada: `{branch}`"

        # Commits en name que no están en base
        ahead = _run_git(
            "rev-list", "--count", f"{base}..{name}",
            cwd=cwd, check=False,
        )
        behind = _run_git(
            "rev-list", "--count", f"{name}..{base}",
            cwd=cwd, check=False,
        )

        ahead_n = int(ahead.output) if ahead.success else 0
        behind_n = int(behind.output) if behind.success else 0

        # Archivos diferentes
        diff_files = _run_git(
            "diff", "--name-status", f"{base}...{name}",
            cwd=cwd, check=False,
        )

        lines = [
            f"🔀 **Comparación: `{name}` vs `{base}`**",
            "",
            f"  ↑ {ahead_n} commits adelante",
            f"  ↓ {behind_n} commits detrás",
            "",
        ]

        if diff_files.success and diff_files.output:
            status_icons = {"M": "✏️ ", "A": "➕", "D": "🗑️ ", "R": "📛"}
            lines.append(f"  📁 **Archivos cambiados:**")
            for line in diff_files.lines[:20]:
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    status, filepath = parts
                    icon = status_icons.get(status[0], "❓")
                    lines.append(f"    {icon} {filepath}")
            if len(diff_files.lines) > 20:
                lines.append(f"    ... y {len(diff_files.lines) - 20} más")

        # Merge status
        merge_base = _run_git("merge-base", base, name, cwd=cwd, check=False)
        if merge_base.success:
            lines.append(f"\n  🔗 Merge base: `{merge_base.output[:8]}`")
            if ahead_n == 0:
                lines.append(f"  ✅ `{name}` está al día con `{base}`")
            elif behind_n == 0:
                lines.append(f"  ℹ️  Fast-forward merge posible")
            else:
                lines.append(f"  ⚠️  Se requiere merge (ambas ramas han divergido)")

        return "\n".join(lines)

    def _info(self, cwd: str, name: Optional[str], **kw) -> str:
        """Información detallada de una rama."""
        branch = name or _current_branch(cwd)

        # Último commit
        last = _run_git(
            "log", "-1", "--format=%H|||%an|||%aI|||%s", branch,
            cwd=cwd, check=False,
        )

        # Primer commit de la rama
        first = _run_git(
            "rev-list", "--max-parents=0", branch,
            cwd=cwd, check=False,
        )

        # Total commits
        count = _run_git(
            "rev-list", "--count", branch,
            cwd=cwd, check=False,
        )

        lines = [f"🌿 **Rama: `{branch}`**", ""]

        if last.success and "|||" in last.output:
            parts = last.output.split("|||")
            lines.append(f"  Último commit: `{parts[0][:8]}`")
            lines.append(f"  Autor: {parts[1]}")
            lines.append(f"  Fecha: {_format_relative_date(parts[2])}")
            lines.append(f"  Mensaje: {parts[3]}")

        if count.success:
            lines.append(f"  Total commits: {count.output}")

        # Protected?
        if branch in _PROTECTED_BRANCHES:
            lines.append(f"\n  🔒 Rama protegida")

        return "\n".join(lines)

    def _cleanup(self, cwd: str, force: bool, **kw) -> str:
        """Sugiere ramas que pueden ser eliminadas."""
        merged = _run_git("branch", "--merged", cwd=cwd, check=False)
        current = _current_branch(cwd)

        candidates: List[str] = []
        for line in merged.lines:
            branch = line.strip().lstrip("* ").strip()
            if branch == current:
                continue
            if branch in _PROTECTED_BRANCHES:
                continue
            if not branch:
                continue
            candidates.append(branch)

        if not candidates:
            return "✅ No hay ramas mergeadas para limpiar."

        if force:
            deleted = []
            for b in candidates:
                try:
                    _run_git("branch", "-d", b, cwd=cwd)
                    deleted.append(b)
                except GitError:
                    pass

            return (
                f"🧹 **Limpieza completada**\n\n"
                f"  Eliminadas: {len(deleted)} ramas\n"
                + "\n".join(f"    🗑️  `{b}`" for b in deleted)
            )

        lines = [
            f"🧹 **Ramas mergeadas** (candidatas para eliminar):",
            "",
        ]
        for b in candidates:
            lines.append(f"    🌿 `{b}`")

        lines.append(f"\n  Total: {len(candidates)} ramas")
        lines.append("  ℹ️  Usa force=true para eliminarlas.")

        return "\n".join(lines)


# ─── 6. GIT STASH TOOL ──────────────────────────────────────────────────────


class GitStashTool(BaseTool):
    """Gestiona el stash de Git."""

    name = "git_stash"
    description = (
        "Gestiona el stash: guardar, listar, aplicar, pop, drop, show."
    )
    category = "git"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description="Acción: save|list|apply|pop|drop|show|clear (default: save)",
                required=False,
            ),
            "message": ToolParameter(
                name="message",
                type="string",
                description="Mensaje para save",
                required=False,
            ),
            "index": ToolParameter(
                name="index",
                type="integer",
                description="Índice del stash (default: 0 = más reciente)",
                required=False,
            ),
            "include_untracked": ToolParameter(
                name="include_untracked",
                type="boolean",
                description="Incluir archivos sin tracking en save (default: false)",
                required=False,
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio del repositorio",
                required=False,
            ),
        }

    def execute(
        self,
        action: str = "save",
        message: Optional[str] = None,
        index: int = 0,
        include_untracked: bool = False,
        directory: Optional[str] = None,
        **kwargs,
    ) -> str:
        try:
            cwd = _require_git_repo(directory)
        except GitError as e:
            return f"❌ {e}"

        action = (action or "save").lower().strip()

        try:
            if action == "save":
                return self._save(cwd, message, include_untracked)
            elif action == "list":
                return self._list_stashes(cwd)
            elif action == "apply":
                return self._apply(cwd, index, keep=True)
            elif action == "pop":
                return self._apply(cwd, index, keep=False)
            elif action == "drop":
                return self._drop(cwd, index)
            elif action == "show":
                return self._show(cwd, index)
            elif action == "clear":
                return self._clear(cwd)
            else:
                return f"❌ Acción '{action}' no soportada. Opciones: save, list, apply, pop, drop, show, clear."
        except GitError as e:
            return f"❌ Error: {e}"

    def _save(self, cwd: str, message: Optional[str], untracked: bool) -> str:
        if not _has_staged(cwd) and not _has_unstaged(cwd) and not (untracked and _has_untracked(cwd)):
            return "ℹ️  No hay cambios para guardar en stash."

        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])
        if untracked:
            args.append("--include-untracked")

        _run_git(*args, cwd=cwd)
        msg_display = f" ({message})" if message else ""
        return f"📥 Cambios guardados en stash{msg_display}"

    def _list_stashes(self, cwd: str) -> str:
        result = _run_git("stash", "list", cwd=cwd, check=False)
        if not result.output:
            return "📥 Stash vacío — no hay entradas guardadas."

        lines = [f"📥 **Stash** ({len(result.lines)} entradas)", ""]
        for i, line in enumerate(result.lines):
            lines.append(f"  {i}: {line}")

        return "\n".join(lines)

    def _apply(self, cwd: str, index: int, keep: bool) -> str:
        ref = f"stash@{{{index}}}"
        action = "apply" if keep else "pop"
        _run_git("stash", action, ref, cwd=cwd)
        verb = "aplicado (mantenido)" if keep else "aplicado y eliminado"
        return f"✅ Stash {index} {verb}"

    def _drop(self, cwd: str, index: int) -> str:
        ref = f"stash@{{{index}}}"
        _run_git("stash", "drop", ref, cwd=cwd)
        return f"🗑️  Stash {index} eliminado"

    def _show(self, cwd: str, index: int) -> str:
        ref = f"stash@{{{index}}}"
        result = _run_git("stash", "show", "-p", "--stat", ref, cwd=cwd)
        output = result.output[:3000]
        truncated = "..." if len(result.output) > 3000 else ""
        return f"📋 **Stash {index}:**\n\n```diff\n{output}{truncated}\n```"

    def _clear(self, cwd: str) -> str:
        count_result = _run_git("stash", "list", cwd=cwd, check=False)
        count = len(count_result.lines) if count_result.success else 0

        if count == 0:
            return "ℹ️  Stash ya está vacío."

        _run_git("stash", "clear", cwd=cwd)
        return f"🗑️  Stash limpiado ({count} entradas eliminadas)"


# ─── 7. GIT REMOTE TOOL ─────────────────────────────────────────────────────


class GitRemoteTool(BaseTool):
    """
    Operaciones con remotos: push, pull, fetch, y gestión
    de repositorios remotos.
    """

    name = "git_remote"
    description = (
        "Operaciones con remotos: push, pull, fetch, list, add, remove."
    )
    category = "git"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description="Acción: push|pull|fetch|list|add|remove|prune (default: list)",
                required=False,
            ),
            "remote": ToolParameter(
                name="remote",
                type="string",
                description="Nombre del remoto (default: origin)",
                required=False,
            ),
            "branch": ToolParameter(
                name="branch",
                type="string",
                description="Rama específica",
                required=False,
            ),
            "url": ToolParameter(
                name="url",
                type="string",
                description="URL del remoto (para add)",
                required=False,
            ),
            "force": ToolParameter(
                name="force",
                type="boolean",
                description="Forzar push (default: false). PELIGROSO.",
                required=False,
            ),
            "tags": ToolParameter(
                name="tags",
                type="boolean",
                description="Incluir tags en push/fetch (default: false)",
                required=False,
            ),
            "set_upstream": ToolParameter(
                name="set_upstream",
                type="boolean",
                description="Establecer upstream en push (default: false)",
                required=False,
            ),
            "dry_run": ToolParameter(
                name="dry_run",
                type="boolean",
                description="Simular sin ejecutar (default: false)",
                required=False,
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio del repositorio",
                required=False,
            ),
        }

    def execute(
        self,
        action: str = "list",
        remote: str = "origin",
        branch: Optional[str] = None,
        url: Optional[str] = None,
        force: bool = False,
        tags: bool = False,
        set_upstream: bool = False,
        dry_run: bool = False,
        directory: Optional[str] = None,
        **kwargs,
    ) -> str:
        try:
            cwd = _require_git_repo(directory)
        except GitError as e:
            return f"❌ {e}"

        action = (action or "list").lower().strip()

        try:
            if action == "list":
                return self._list_remotes(cwd)
            elif action == "push":
                return self._push(cwd, remote, branch, force, tags, set_upstream, dry_run)
            elif action == "pull":
                return self._pull(cwd, remote, branch)
            elif action == "fetch":
                return self._fetch(cwd, remote, tags)
            elif action == "add":
                return self._add_remote(cwd, remote, url)
            elif action == "remove":
                return self._remove_remote(cwd, remote)
            elif action == "prune":
                return self._prune(cwd, remote)
            else:
                return f"❌ Acción '{action}' no soportada."
        except GitError as e:
            return f"❌ Error: {e}"

    def _list_remotes(self, cwd: str) -> str:
        result = _run_git("remote", "-v", cwd=cwd, check=False)
        if not result.output:
            return "📡 No hay remotos configurados."

        lines = ["📡 **Remotos:**", ""]

        seen: set = set()
        for line in result.lines:
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                url = parts[1]
                if name not in seen:
                    lines.append(f"  🌐 `{name}` → {url}")
                    seen.add(name)

        return "\n".join(lines)

    def _push(
        self, cwd: str, remote: str, branch: Optional[str],
        force: bool, tags: bool, set_upstream: bool, dry_run: bool,
    ) -> str:
        branch = branch or _current_branch(cwd)

        if branch in _PROTECTED_BRANCHES and force:
            return f"🔒 Push forzado a `{branch}` bloqueado (rama protegida)."

        args = ["push", remote, branch]
        if force:
            args.append("--force-with-lease")  # Más seguro que --force
        if tags:
            args.append("--tags")
        if set_upstream:
            args.append("--set-upstream")
        if dry_run:
            args.append("--dry-run")

        result = _run_git(*args, cwd=cwd, timeout=60)

        prefix = "🧪 Dry run: " if dry_run else ""
        force_warn = " ⚠️  (force-with-lease)" if force else ""

        output = result.output or result.error or "completado"
        return f"{prefix}⬆️  Push `{branch}` → `{remote}`{force_warn}\n\n```\n{output[:1000]}\n```"

    def _pull(self, cwd: str, remote: str, branch: Optional[str]) -> str:
        branch = branch or _current_branch(cwd)

        # Advertir si hay cambios locales
        if _has_unstaged(cwd) or _has_staged(cwd):
            return (
                "⚠️  Tienes cambios locales sin commitear.\n"
                "   Commitea o guarda en stash antes de hacer pull."
            )

        args = ["pull", remote, branch]
        result = _run_git(*args, cwd=cwd, timeout=60, check=False)

        if result.success:
            if "Already up to date" in result.output:
                return f"✅ `{branch}` ya está actualizada."
            return f"⬇️  Pull `{remote}/{branch}` exitoso\n\n```\n{result.output[:1000]}\n```"
        else:
            return f"❌ Error en pull:\n```\n{result.error[:500]}\n```"

    def _fetch(self, cwd: str, remote: str, tags: bool) -> str:
        args = ["fetch", remote, "--prune"]
        if tags:
            args.append("--tags")

        _run_git(*args, cwd=cwd, timeout=60)
        return f"🔄 Fetch de `{remote}` completado"

    def _add_remote(self, cwd: str, name: str, url: Optional[str]) -> str:
        if not url:
            return "❌ Se requiere 'url' para agregar un remoto."
        _run_git("remote", "add", name, url, cwd=cwd)
        return f"✅ Remoto `{name}` agregado → {url}"

    def _remove_remote(self, cwd: str, name: str) -> str:
        _run_git("remote", "remove", name, cwd=cwd)
        return f"✅ Remoto `{name}` eliminado"

    def _prune(self, cwd: str, remote: str) -> str:
        result = _run_git("remote", "prune", remote, cwd=cwd)
        return f"🧹 Ramas remotas eliminadas limpiadas de `{remote}`\n\n```\n{result.output or '(sin cambios)'}\n```"


# ─── 8. GIT TAG TOOL ────────────────────────────────────────────────────────


class GitTagTool(BaseTool):
    """Gestiona tags (etiquetas) de Git."""

    name = "git_tag"
    description = "Gestiona tags: listar, crear, eliminar y push."
    category = "git"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description="Acción: list|create|delete|push (default: list)",
                required=False,
            ),
            "name": ToolParameter(
                name="name",
                type="string",
                description="Nombre del tag (ej: 'v1.2.0')",
                required=False,
            ),
            "message": ToolParameter(
                name="message",
                type="string",
                description="Mensaje del tag anotado",
                required=False,
            ),
            "commit": ToolParameter(
                name="commit",
                type="string",
                description="Commit al cual apuntar (default: HEAD)",
                required=False,
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio del repositorio",
                required=False,
            ),
        }

    def execute(
        self,
        action: str = "list",
        name: Optional[str] = None,
        message: Optional[str] = None,
        commit: Optional[str] = None,
        directory: Optional[str] = None,
        **kwargs,
    ) -> str:
        try:
            cwd = _require_git_repo(directory)
        except GitError as e:
            return f"❌ {e}"

        action = (action or "list").lower().strip()

        try:
            if action == "list":
                return self._list_tags(cwd)
            elif action == "create":
                return self._create_tag(cwd, name, message, commit)
            elif action == "delete":
                return self._delete_tag(cwd, name)
            elif action == "push":
                return self._push_tags(cwd, name)
            else:
                return f"❌ Acción '{action}' no soportada."
        except GitError as e:
            return f"❌ Error: {e}"

    def _list_tags(self, cwd: str) -> str:
        result = _run_git(
            "tag", "-l", "--sort=-v:refname",
            "--format=%(refname:short)|||%(objecttype)|||%(creatordate:iso)|||%(subject)",
            cwd=cwd, check=False,
        )

        if not result.output:
            return "🏷️  No hay tags."

        lines = ["🏷️  **Tags:**", ""]

        for line in result.lines[:30]:
            parts = line.split("|||")
            tag_name = parts[0].strip() if parts else ""
            tag_type = parts[1].strip() if len(parts) > 1 else ""
            date = parts[2].strip()[:10] if len(parts) > 2 else ""
            subject = parts[3].strip() if len(parts) > 3 else ""

            type_icon = "📌" if tag_type == "tag" else "🏷️ "
            msg = f" — {subject}" if subject else ""
            lines.append(f"  {type_icon} `{tag_name}` ({date}){msg}")

        if len(result.lines) > 30:
            lines.append(f"\n  ... y {len(result.lines) - 30} más")

        return "\n".join(lines)

    def _create_tag(
        self, cwd: str, name: Optional[str],
        message: Optional[str], commit: Optional[str],
    ) -> str:
        if not name:
            return "❌ Se requiere 'name' para crear un tag."

        args = ["tag"]
        if message:
            args.extend(["-a", name, "-m", message])
        else:
            args.append(name)

        if commit:
            args.append(commit)

        _run_git(*args, cwd=cwd)
        tag_type = "anotado" if message else "ligero"
        target = f" en `{commit}`" if commit else ""
        return f"✅ Tag `{name}` creado ({tag_type}){target}"

    def _delete_tag(self, cwd: str, name: Optional[str]) -> str:
        if not name:
            return "❌ Se requiere 'name'."
        _run_git("tag", "-d", name, cwd=cwd)
        return f"🗑️  Tag `{name}` eliminado (local)"

    def _push_tags(self, cwd: str, name: Optional[str]) -> str:
        if name:
            _run_git("push", "origin", name, cwd=cwd, timeout=60)
            return f"⬆️  Tag `{name}` pushed a origin"
        else:
            _run_git("push", "origin", "--tags", cwd=cwd, timeout=60)
            return "⬆️  Todos los tags pushed a origin"