# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS GIT AVANZADAS
# Blame, Stats, Conflict Resolver, Bisect
# ═══════════════════════════════════════════════════════════════════════════════

import subprocess
import re
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

from .base import BaseTool, ToolParameter


def run_git(args: List[str], cwd: str = None, timeout: int = 30) -> tuple:
    # Ejecuta comando git y retorna (success, stdout, stderr)
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except FileNotFoundError:
        return False, "", "Git no instalado"
    except Exception as e:
        return False, "", str(e)


class GitBlameTool(BaseTool):
    # Muestra quién modificó cada línea de un archivo y cuándo.
    #
    # Útil para:
    # - Encontrar autor de un cambio específico
    # - Ver historial de una línea problemática
    # - Entender evolución del código
    
    name = "git_blame"
    description = """Muestra quién modificó cada línea de un archivo.

Información por línea:
- Commit hash
- Autor
- Fecha
- Contenido

Ejemplos:
- Archivo completo: file="src/app.py"
- Línea específica: file="app.py", line=42
- Rango de líneas: file="app.py", start_line=10, end_line=20
"""
    category = "git"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "file": ToolParameter(
                name="file",
                type="string",
                description="Archivo a analizar",
                required=True
            ),
            "line": ToolParameter(
                name="line",
                type="integer",
                description="Línea específica (opcional)",
                required=False
            ),
            "start_line": ToolParameter(
                name="start_line",
                type="integer",
                description="Línea inicial del rango",
                required=False
            ),
            "end_line": ToolParameter(
                name="end_line",
                type="integer",
                description="Línea final del rango",
                required=False
            ),
            "show_email": ToolParameter(
                name="show_email",
                type="boolean",
                description="Mostrar email del autor (default: false)",
                required=False
            )
        }
    
    def execute(
        self,
        file: str = None,
        line: int = None,
        start_line: int = None,
        end_line: int = None,
        show_email: bool = False,
        **kwargs
    ) -> str:
        file = file or kwargs.get('file', '')
        line = line or kwargs.get('line', None)
        start_line = start_line or kwargs.get('start_line', None)
        end_line = end_line or kwargs.get('end_line', None)
        show_email = show_email or kwargs.get('show_email', False)
        
        if not file:
            return "❌ Se requiere 'file'"
        
        if not Path(file).exists():
            return f"❌ Archivo no existe: {file}"
        
        # Construir comando
        args = ["blame", "--line-porcelain"]
        
        if show_email:
            args.append("-e")
        
        # Rango de líneas
        if line:
            args.extend(["-L", f"{line},{line}"])
        elif start_line and end_line:
            args.extend(["-L", f"{start_line},{end_line}"])
        elif start_line:
            args.extend(["-L", f"{start_line},+20"])
        
        args.append(file)
        
        success, stdout, stderr = run_git(args)
        
        if not success:
            return f"❌ Error git blame: {stderr}"
        
        # Parsear salida porcelain
        blame_data = self._parse_porcelain(stdout)
        
        if not blame_data:
            return f"⚠️ No hay datos de blame para {file}"
        
        # Formatear salida
        output = f"""📜 **Git Blame: {file}**

"""
        
        if line:
            output += f"**Línea {line}:**\n\n"
        elif start_line:
            output += f"**Líneas {start_line}-{end_line or start_line + 20}:**\n\n"
        
        output += "| Línea | Autor | Fecha | Commit | Código |\n"
        output += "|-------|-------|-------|--------|--------|\n"
        
        for entry in blame_data[:50]:
            code_preview = entry['line'][:30].replace('|', '\\|')
            output += f"| {entry['line_num']} | {entry['author'][:15]} | {entry['date']} | `{entry['commit'][:7]}` | `{code_preview}` |\n"
        
        if len(blame_data) > 50:
            output += f"\n⚠️ Mostrando 50 de {len(blame_data)} líneas"
        
        # Estadísticas
        authors = defaultdict(int)
        for entry in blame_data:
            authors[entry['author']] += 1
        
        output += "\n\n**📊 Contribuciones:**\n"
        for author, count in sorted(authors.items(), key=lambda x: -x[1])[:5]:
            pct = count / len(blame_data) * 100
            output += f"- {author}: {count} líneas ({pct:.1f}%)\n"
        
        return output
    
    def _parse_porcelain(self, output: str) -> List[Dict]:
        entries = []
        lines = output.split('\n')
        
        current = {}
        line_num = 0
        
        for line in lines:
            if line.startswith('\t'):
                # Línea de código
                current['line'] = line[1:]
                current['line_num'] = line_num
                entries.append(current)
                current = {}
            elif ' ' in line:
                parts = line.split(' ', 1)
                key = parts[0]
                value = parts[1] if len(parts) > 1 else ''
                
                if len(key) == 40 and all(c in '0123456789abcdef' for c in key):
                    # Nuevo commit
                    current = {'commit': key}
                    line_num = int(value.split()[1]) if value else 0
                elif key == 'author':
                    current['author'] = value
                elif key == 'author-time':
                    try:
                        dt = datetime.fromtimestamp(int(value))
                        current['date'] = dt.strftime('%Y-%m-%d')
                    except:
                        current['date'] = value
                elif key == 'author-mail':
                    current['email'] = value.strip('<>')
        
        return entries


class GitStatsTool(BaseTool):
    # Genera estadísticas del repositorio Git.
    #
    # Muestra commits por autor, archivos más modificados, actividad, etc.
    
    name = "git_stats"
    description = """Genera estadísticas del repositorio Git.

Muestra:
- Commits por autor
- Archivos más modificados
- Actividad por día/mes
- Líneas añadidas/eliminadas
- Branches y tags

Ejemplo: (sin parámetros para stats completas)
"""
    category = "git"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "since": ToolParameter(
                name="since",
                type="string",
                description="Desde fecha (ej: '1 month ago', '2023-01-01')",
                required=False
            ),
            "author": ToolParameter(
                name="author",
                type="string",
                description="Filtrar por autor",
                required=False
            ),
            "path": ToolParameter(
                name="path",
                type="string",
                description="Filtrar por directorio/archivo",
                required=False
            )
        }
    
    def execute(
        self,
        since: str = None,
        author: str = None,
        path: str = None,
        **kwargs
    ) -> str:
        since = since or kwargs.get('since', None)
        author = author or kwargs.get('author', None)
        path = path or kwargs.get('path', None)
        
        # Verificar que es un repo git
        success, _, _ = run_git(["rev-parse", "--git-dir"])
        if not success:
            return "❌ No es un repositorio Git"
        
        output = "📊 **Estadísticas Git**\n\n"
        
        # Info general
        success, stdout, _ = run_git(["rev-list", "--count", "HEAD"])
        total_commits = stdout.strip() if success else "?"
        
        success, stdout, _ = run_git(["branch", "--list"])
        branches = len([b for b in stdout.split('\n') if b.strip()]) if success else 0
        
        success, stdout, _ = run_git(["tag", "--list"])
        tags = len([t for t in stdout.split('\n') if t.strip()]) if success else 0
        
        success, stdout, _ = run_git(["remote", "-v"])
        remotes = len(set(re.findall(r'^(\w+)', stdout, re.MULTILINE))) if success else 0
        
        output += f"""**📋 Resumen:**
| Métrica | Valor |
|---------|-------|
| Total commits | {total_commits} |
| Branches | {branches} |
| Tags | {tags} |
| Remotes | {remotes} |

"""
        
        # Commits por autor
        log_args = ["shortlog", "-sn", "--no-merges", "HEAD"]
        if since:
            log_args.extend(["--since", since])
        if author:
            log_args.extend(["--author", author])
        if path:
            log_args.extend(["--", path])
        
        success, stdout, _ = run_git(log_args)
        
        if success and stdout.strip():
            output += "**👥 Commits por Autor:**\n\n"
            output += "| Commits | Autor |\n"
            output += "|---------|-------|\n"
            
            for line in stdout.strip().split('\n')[:10]:
                match = re.match(r'\s*(\d+)\s+(.+)', line)
                if match:
                    count, name = match.groups()
                    output += f"| {count} | {name} |\n"
            
            output += "\n"
        
        # Archivos más modificados
        log_args = ["log", "--pretty=format:", "--name-only", "--no-merges", "-100"]
        if since:
            log_args.extend(["--since", since])
        if path:
            log_args.extend(["--", path])
        
        success, stdout, _ = run_git(log_args)
        
        if success and stdout.strip():
            file_counts = defaultdict(int)
            for line in stdout.split('\n'):
                if line.strip():
                    file_counts[line.strip()] += 1
            
            top_files = sorted(file_counts.items(), key=lambda x: -x[1])[:10]
            
            output += "**📁 Archivos Más Modificados:**\n\n"
            output += "| Cambios | Archivo |\n"
            output += "|---------|--------|\n"
            
            for file_path, count in top_files:
                output += f"| {count} | `{file_path[:50]}` |\n"
            
            output += "\n"
        
        # Actividad reciente
        success, stdout, _ = run_git([
            "log", "--format=%ad", "--date=short", "-100"
        ])
        
        if success and stdout.strip():
            dates = defaultdict(int)
            for line in stdout.strip().split('\n'):
                if line:
                    dates[line] += 1
            
            # Últimos 7 días con commits
            recent = sorted(dates.items(), reverse=True)[:7]
            
            output += "**📅 Actividad Reciente:**\n\n"
            
            max_commits = max(d[1] for d in recent) if recent else 1
            
            for date, count in recent:
                bar_len = int(count / max_commits * 20)
                bar = '█' * bar_len
                output += f"  {date} {bar} {count}\n"
            
            output += "\n"
        
        # Líneas de código (si no es muy pesado)
        if not path:
            success, stdout, _ = run_git([
                "log", "--pretty=format:", "--numstat", "--no-merges", "-50"
            ])
            
            if success and stdout.strip():
                added = 0
                deleted = 0
                
                for line in stdout.strip().split('\n'):
                    match = re.match(r'(\d+)\s+(\d+)', line)
                    if match:
                        added += int(match.group(1))
                        deleted += int(match.group(2))
                
                output += f"""**📈 Cambios (últimos 50 commits):**
| Tipo | Líneas |
|------|--------|
| ➕ Añadidas | +{added:,} |
| ➖ Eliminadas | -{deleted:,} |
| Δ Neto | {added - deleted:+,} |
"""
        
        return output


class GitConflictResolverTool(BaseTool):
    # Ayuda a resolver conflictos de merge en Git.
    #
    # Lista archivos en conflicto y proporciona opciones de resolución.
    
    name = "git_resolve_conflicts"
    description = """Ayuda a resolver conflictos de merge en Git.

Acciones:
- list: Listar archivos en conflicto
- show: Mostrar conflictos en un archivo
- ours: Resolver usando versión local (nuestra)
- theirs: Resolver usando versión remota (de ellos)
- mark_resolved: Marcar archivo como resuelto

Ejemplos:
- Ver conflictos: action="list"
- Ver detalles: action="show", file="app.py"
- Usar nuestra versión: action="ours", file="app.py"
"""
    category = "git"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description="Acción: list, show, ours, theirs, mark_resolved",
                required=True,
                enum=["list", "show", "ours", "theirs", "mark_resolved"]
            ),
            "file": ToolParameter(
                name="file",
                type="string",
                description="Archivo específico (para show/ours/theirs/mark_resolved)",
                required=False
            )
        }
    
    def execute(
        self,
        action: str = None,
        file: str = None,
        **kwargs
    ) -> str:
        action = action or kwargs.get('action', '')
        file = file or kwargs.get('file', None)
        
        if not action:
            return "❌ Se requiere 'action'"
        
        if action == "list":
            return self._list_conflicts()
        elif action == "show":
            if not file:
                return "❌ Se requiere 'file' para mostrar conflictos"
            return self._show_conflicts(file)
        elif action == "ours":
            if not file:
                return "❌ Se requiere 'file'"
            return self._resolve_ours(file)
        elif action == "theirs":
            if not file:
                return "❌ Se requiere 'file'"
            return self._resolve_theirs(file)
        elif action == "mark_resolved":
            if not file:
                return "❌ Se requiere 'file'"
            return self._mark_resolved(file)
        else:
            return f"❌ Acción no válida: {action}"
    
    def _list_conflicts(self) -> str:
        success, stdout, stderr = run_git(["diff", "--name-only", "--diff-filter=U"])
        
        if not success:
            return f"❌ Error: {stderr}"
        
        files = [f.strip() for f in stdout.strip().split('\n') if f.strip()]
        
        if not files:
            return "✅ **No hay conflictos pendientes**"
        
        output = f"""⚠️ **Archivos en Conflicto: {len(files)}**

| # | Archivo |
|---|---------|
"""
        
        for i, f in enumerate(files, 1):
            output += f"| {i} | `{f}` |\n"
        
        output += """
**Opciones de resolución:**
- `action="show", file="..."` - Ver conflictos
- `action="ours", file="..."` - Usar versión local
- `action="theirs", file="..."` - Usar versión remota
- `action="mark_resolved", file="..."` - Marcar como resuelto
"""
        
        return output
    
    def _show_conflicts(self, file: str) -> str:
        if not Path(file).exists():
            return f"❌ Archivo no existe: {file}"
        
        try:
            content = Path(file).read_text()
        except Exception as e:
            return f"❌ Error leyendo archivo: {e}"
        
        # Buscar marcadores de conflicto
        conflicts = []
        lines = content.split('\n')
        in_conflict = False
        current = {'start': 0, 'ours': [], 'theirs': [], 'end': 0}
        section = None
        
        for i, line in enumerate(lines):
            if line.startswith('<<<<<<<'):
                in_conflict = True
                current = {'start': i + 1, 'ours': [], 'theirs': [], 'marker': line}
                section = 'ours'
            elif line.startswith('=======') and in_conflict:
                section = 'theirs'
            elif line.startswith('>>>>>>>') and in_conflict:
                current['end'] = i + 1
                current['end_marker'] = line
                conflicts.append(current)
                in_conflict = False
                section = None
            elif in_conflict:
                if section == 'ours':
                    current['ours'].append(line)
                elif section == 'theirs':
                    current['theirs'].append(line)
        
        if not conflicts:
            return f"✅ No hay conflictos en {file}"
        
        output = f"""⚠️ **Conflictos en {file}: {len(conflicts)}**

"""
        
        for i, conf in enumerate(conflicts, 1):
            output += f"""### Conflicto #{i} (líneas {conf['start']}-{conf['end']})

**◀️ OURS (versión local):**
```
{chr(10).join(conf['ours'][:10])}
```

**▶️ THEIRS (versión remota):**
```
{chr(10).join(conf['theirs'][:10])}
```

---

"""
        
        return output
    
    def _resolve_ours(self, file: str) -> str:
        success, _, stderr = run_git(["checkout", "--ours", file])
        
        if not success:
            return f"❌ Error: {stderr}"
        
        # Stage el archivo
        run_git(["add", file])
        
        return f"""✅ **Conflicto resuelto usando OURS**

Archivo: `{file}`
Versión usada: Local (nuestra)

💡 Ejecuta `git commit` para completar el merge.
"""
    
    def _resolve_theirs(self, file: str) -> str:
        success, _, stderr = run_git(["checkout", "--theirs", file])
        
        if not success:
            return f"❌ Error: {stderr}"
        
        run_git(["add", file])
        
        return f"""✅ **Conflicto resuelto usando THEIRS**

Archivo: `{file}`
Versión usada: Remota (de ellos)

💡 Ejecuta `git commit` para completar el merge.
"""
    
    def _mark_resolved(self, file: str) -> str:
        success, _, stderr = run_git(["add", file])
        
        if not success:
            return f"❌ Error: {stderr}"
        
        return f"""✅ **Archivo marcado como resuelto**

Archivo: `{file}`

💡 Ejecuta `git commit` para completar el merge.
"""


class GitBisectTool(BaseTool):
    # Usa git bisect para encontrar el commit que introdujo un bug.
    #
    # Búsqueda binaria automática en el historial.
    
    name = "git_bisect"
    description = """Usa git bisect para encontrar commit problemático.

Búsqueda binaria en el historial para encontrar
el commit que introdujo un bug.

Acciones:
- start: Iniciar bisect con good/bad commits
- good: Marcar commit actual como bueno
- bad: Marcar commit actual como malo
- skip: Saltar commit actual
- reset: Terminar bisect
- status: Ver estado actual
- run: Bisect automático con comando de test

Ejemplo:
- Iniciar: action="start", good="v1.0", bad="HEAD"
- Luego probar y marcar: action="good" o action="bad"
"""
    category = "git"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description="Acción: start, good, bad, skip, reset, status, run",
                required=True,
                enum=["start", "good", "bad", "skip", "reset", "status", "run"]
            ),
            "good": ToolParameter(
                name="good",
                type="string",
                description="Commit bueno conocido (para start)",
                required=False
            ),
            "bad": ToolParameter(
                name="bad",
                type="string",
                description="Commit malo conocido (para start)",
                required=False
            ),
            "test_command": ToolParameter(
                name="test_command",
                type="string",
                description="Comando de test para bisect automático (para run)",
                required=False
            )
        }
    
    def execute(
        self,
        action: str = None,
        good: str = None,
        bad: str = None,
        test_command: str = None,
        **kwargs
    ) -> str:
        action = action or kwargs.get('action', '')
        good = good or kwargs.get('good', None)
        bad = bad or kwargs.get('bad', None)
        test_command = test_command or kwargs.get('test_command', None)
        
        if not action:
            return "❌ Se requiere 'action'"
        
        if action == "start":
            if not good or not bad:
                return "❌ Se requieren 'good' y 'bad' para iniciar"
            return self._start_bisect(good, bad)
        
        elif action == "good":
            return self._mark_good()
        
        elif action == "bad":
            return self._mark_bad()
        
        elif action == "skip":
            return self._skip()
        
        elif action == "reset":
            return self._reset()
        
        elif action == "status":
            return self._status()
        
        elif action == "run":
            if not test_command:
                return "❌ Se requiere 'test_command' para bisect automático"
            return self._run_auto(test_command)
        
        return f"❌ Acción no válida: {action}"
    
    def _start_bisect(self, good: str, bad: str) -> str:
        # Iniciar bisect
        success, _, stderr = run_git(["bisect", "start"])
        if not success:
            return f"❌ Error iniciando bisect: {stderr}"
        
        # Marcar bad
        success, _, stderr = run_git(["bisect", "bad", bad])
        if not success:
            run_git(["bisect", "reset"])
            return f"❌ Error marcando bad: {stderr}"
        
        # Marcar good
        success, stdout, stderr = run_git(["bisect", "good", good])
        if not success:
            run_git(["bisect", "reset"])
            return f"❌ Error marcando good: {stderr}"
        
        # Obtener info del commit actual
        success, commit_info, _ = run_git(["log", "-1", "--oneline"])
        
        return f"""🔍 **Git Bisect Iniciado**

| Propiedad | Valor |
|-----------|-------|
| Commit bueno | `{good}` |
| Commit malo | `{bad}` |
| Commit actual | `{commit_info.strip() if success else '?'}` |

**Próximos pasos:**
1. Prueba si el bug existe en este commit
2. Ejecuta `action="good"` si funciona
3. Ejecuta `action="bad"` si tiene el bug
4. Repite hasta encontrar el culpable

{stdout}
"""
    
    def _mark_good(self) -> str:
        success, stdout, stderr = run_git(["bisect", "good"])
        
        if not success:
            return f"❌ Error: {stderr}"
        
        if "is the first bad commit" in stdout:
            return f"""🎯 **¡Encontrado!**

{stdout}

Ejecuta `action="reset"` para terminar.
"""
        
        success, commit_info, _ = run_git(["log", "-1", "--oneline"])
        
        return f"""✅ **Marcado como GOOD**

Commit actual: `{commit_info.strip() if success else '?'}`

{stdout}

Prueba este commit y marca como good/bad.
"""
    
    def _mark_bad(self) -> str:
        success, stdout, stderr = run_git(["bisect", "bad"])
        
        if not success:
            return f"❌ Error: {stderr}"
        
        if "is the first bad commit" in stdout:
            return f"""🎯 **¡Encontrado el commit problemático!**

{stdout}

Ejecuta `action="reset"` para terminar.
"""
        
        success, commit_info, _ = run_git(["log", "-1", "--oneline"])
        
        return f"""❌ **Marcado como BAD**

Commit actual: `{commit_info.strip() if success else '?'}`

{stdout}

Prueba este commit y marca como good/bad.
"""
    
    def _skip(self) -> str:
        success, stdout, stderr = run_git(["bisect", "skip"])
        
        if not success:
            return f"❌ Error: {stderr}"
        
        return f"""⏭️ **Commit saltado**

{stdout}
"""
    
    def _reset(self) -> str:
        success, stdout, stderr = run_git(["bisect", "reset"])
        
        if not success:
            return f"❌ Error: {stderr}"
        
        return f"""🔄 **Bisect terminado**

{stdout}

Repositorio restaurado al estado original.
"""
    
    def _status(self) -> str:
        success, stdout, stderr = run_git(["bisect", "log"])
        
        if not success:
            return "ℹ️ No hay bisect en progreso"
        
        return f"""📊 **Estado de Bisect**

```
{stdout}
```
"""
    
    def _run_auto(self, test_command: str) -> str:
        success, stdout, stderr = run_git(["bisect", "run"] + test_command.split(), timeout=300)
        
        if not success:
            return f"❌ Error en bisect automático: {stderr}"
        
        return f"""🤖 **Bisect Automático Completado**

```
{stdout[:2000]}
```

{stderr if stderr else ''}
"""
