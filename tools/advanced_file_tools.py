"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    HERRAMIENTAS DE ARCHIVOS AVANZADAS                          ║
║  Operaciones batch, monitoreo, encriptación y metadata de archivos             ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import hashlib
import base64
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

from .base import BaseTool, ToolParameter

# Intentar importar cryptography para encriptación
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# Intentar importar watchdog para monitoreo
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


class BatchFileOperationTool(BaseTool):
    """
    Ejecuta operaciones en múltiples archivos simultáneamente.
    
    Útil para:
    - Renombrar múltiples archivos con un patrón
    - Mover archivos que coincidan con un patrón a otro directorio
    - Eliminar archivos por patrón (*.pyc, *.log, etc.)
    - Copiar múltiples archivos
    - Cambiar extensiones masivamente
    
    Ejemplos de uso:
    - Renombrar todos los .txt a .md: action="rename", pattern="*.txt", replacement=".md"
    - Mover logs a backup: action="move", pattern="*.log", destination="backup/"
    - Eliminar archivos temporales: action="delete", pattern="*.tmp"
    """
    
    name = "batch_files"
    description = """Ejecuta operaciones en múltiples archivos a la vez.
    
Acciones disponibles:
- rename: Renombrar archivos (usa pattern y replacement)
- move: Mover archivos a otro directorio (usa pattern y destination)
- copy: Copiar archivos (usa pattern y destination)
- delete: Eliminar archivos (usa pattern)
- change_extension: Cambiar extensión (usa pattern y new_extension)

Ejemplos:
- Renombrar .txt a .md: action="rename", pattern="*.txt", replacement=".md"
- Mover logs: action="move", pattern="*.log", destination="logs/"
- Eliminar .pyc: action="delete", pattern="**/*.pyc"
"""
    category = "files"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description="Acción: rename, move, copy, delete, change_extension",
                required=True,
                enum=["rename", "move", "copy", "delete", "change_extension"]
            ),
            "pattern": ToolParameter(
                name="pattern",
                type="string",
                description="Patrón glob para seleccionar archivos (ej: *.txt, **/*.py)",
                required=True
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio donde buscar (default: actual)",
                required=False
            ),
            "destination": ToolParameter(
                name="destination",
                type="string",
                description="Directorio destino para move/copy",
                required=False
            ),
            "replacement": ToolParameter(
                name="replacement",
                type="string",
                description="Texto de reemplazo para rename",
                required=False
            ),
            "new_extension": ToolParameter(
                name="new_extension",
                type="string",
                description="Nueva extensión para change_extension (con punto: .md)",
                required=False
            ),
            "dry_run": ToolParameter(
                name="dry_run",
                type="boolean",
                description="Solo mostrar qué se haría sin ejecutar (default: True)",
                required=False
            )
        }
    
    def execute(
        self,
        action: str = None,
        pattern: str = None,
        directory: str = ".",
        destination: str = None,
        replacement: str = None,
        new_extension: str = None,
        dry_run: bool = True,
        **kwargs
    ) -> str:
        action = action or kwargs.get('action', '')
        pattern = pattern or kwargs.get('pattern', '')
        directory = directory or kwargs.get('directory', '.')
        destination = destination or kwargs.get('destination', '')
        replacement = replacement or kwargs.get('replacement', '')
        new_extension = new_extension or kwargs.get('new_extension', '')
        dry_run = dry_run if dry_run is not None else kwargs.get('dry_run', True)
        
        if not action or not pattern:
            return "❌ Se requiere 'action' y 'pattern'"
        
        base_path = Path(directory)
        if not base_path.exists():
            return f"❌ Directorio no existe: {directory}"
        
        # Encontrar archivos
        files = list(base_path.glob(pattern))
        
        if not files:
            return f"📂 No se encontraron archivos con patrón: {pattern}"
        
        results = []
        errors = []
        mode = "🔍 DRY RUN" if dry_run else "⚡ EJECUTANDO"
        
        results.append(f"{mode} - {action.upper()} en {len(files)} archivos\n")
        
        for file_path in files:
            try:
                if action == "delete":
                    if dry_run:
                        results.append(f"  🗑️ Eliminar: {file_path}")
                    else:
                        if file_path.is_file():
                            file_path.unlink()
                            results.append(f"  ✅ Eliminado: {file_path}")
                        elif file_path.is_dir():
                            shutil.rmtree(file_path)
                            results.append(f"  ✅ Eliminado (dir): {file_path}")
                
                elif action == "move":
                    if not destination:
                        return "❌ Se requiere 'destination' para move"
                    dest_path = Path(destination)
                    dest_path.mkdir(parents=True, exist_ok=True)
                    new_path = dest_path / file_path.name
                    
                    if dry_run:
                        results.append(f"  📦 Mover: {file_path} → {new_path}")
                    else:
                        shutil.move(str(file_path), str(new_path))
                        results.append(f"  ✅ Movido: {file_path} → {new_path}")
                
                elif action == "copy":
                    if not destination:
                        return "❌ Se requiere 'destination' para copy"
                    dest_path = Path(destination)
                    dest_path.mkdir(parents=True, exist_ok=True)
                    new_path = dest_path / file_path.name
                    
                    if dry_run:
                        results.append(f"  📋 Copiar: {file_path} → {new_path}")
                    else:
                        if file_path.is_file():
                            shutil.copy2(str(file_path), str(new_path))
                        else:
                            shutil.copytree(str(file_path), str(new_path))
                        results.append(f"  ✅ Copiado: {file_path} → {new_path}")
                
                elif action == "rename":
                    if not replacement:
                        return "❌ Se requiere 'replacement' para rename"
                    
                    old_name = file_path.name
                    # Reemplazar patrón en nombre
                    search_pattern = pattern.replace('*', '').replace('?', '')
                    new_name = old_name.replace(search_pattern, replacement)
                    new_path = file_path.parent / new_name
                    
                    if dry_run:
                        results.append(f"  ✏️ Renombrar: {old_name} → {new_name}")
                    else:
                        file_path.rename(new_path)
                        results.append(f"  ✅ Renombrado: {old_name} → {new_name}")
                
                elif action == "change_extension":
                    if not new_extension:
                        return "❌ Se requiere 'new_extension'"
                    
                    if not new_extension.startswith('.'):
                        new_extension = '.' + new_extension
                    
                    new_path = file_path.with_suffix(new_extension)
                    
                    if dry_run:
                        results.append(f"  🔄 Extensión: {file_path.name} → {new_path.name}")
                    else:
                        file_path.rename(new_path)
                        results.append(f"  ✅ Cambiado: {file_path.name} → {new_path.name}")
                
            except Exception as e:
                errors.append(f"  ❌ Error en {file_path}: {str(e)}")
        
        output = "\n".join(results)
        
        if errors:
            output += "\n\n**Errores:**\n" + "\n".join(errors)
        
        if dry_run:
            output += "\n\n💡 Usa dry_run=false para ejecutar los cambios"
        
        return output


class FileWatcherTool(BaseTool):
    """
    Monitorea cambios en archivos y directorios en tiempo real.
    
    Útil para:
    - Detectar archivos creados, modificados o eliminados
    - Monitorear logs en tiempo real
    - Observar cambios en código durante desarrollo
    - Vigilar directorios por cambios sospechosos
    
    Ejemplo: Monitorear src/ por 10 segundos para ver cambios
    """
    
    name = "file_watch"
    description = """Monitorea cambios en archivos/directorios durante un tiempo especificado.
    
Detecta:
- Archivos creados
- Archivos modificados
- Archivos eliminados
- Archivos movidos

Ejemplo: path="src/", duration=10 → Observa cambios por 10 segundos
Útil para detectar qué archivos cambian durante una operación."""
    category = "files"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(
                name="path",
                type="string",
                description="Directorio a monitorear",
                required=True
            ),
            "duration": ToolParameter(
                name="duration",
                type="integer",
                description="Duración en segundos (default: 10, max: 60)",
                required=False
            ),
            "pattern": ToolParameter(
                name="pattern",
                type="string",
                description="Patrón de archivos a observar (ej: *.py)",
                required=False
            )
        }
    
    def execute(self, path: str = None, duration: int = 10, pattern: str = None, **kwargs) -> str:
        path = path or kwargs.get('path', '.')
        duration = min(duration or kwargs.get('duration', 10), 60)  # Max 60 segundos
        pattern = pattern or kwargs.get('pattern', '*')
        
        watch_path = Path(path)
        if not watch_path.exists():
            return f"❌ Directorio no existe: {path}"
        
        if not HAS_WATCHDOG:
            # Fallback sin watchdog: comparar estado antes/después
            return self._simple_watch(watch_path, duration, pattern)
        
        return self._watchdog_watch(watch_path, duration, pattern)
    
    def _simple_watch(self, path: Path, duration: int, pattern: str) -> str:
        """Monitoreo simple sin dependencias externas"""
        
        def get_state(p: Path) -> Dict:
            state = {}
            for f in p.rglob(pattern):
                try:
                    stat = f.stat()
                    state[str(f)] = {
                        'mtime': stat.st_mtime,
                        'size': stat.st_size
                    }
                except:
                    pass
            return state
        
        print(f"👁️ Monitoreando {path} por {duration} segundos...")
        print(f"   Patrón: {pattern}")
        
        before = get_state(path)
        time.sleep(duration)
        after = get_state(path)
        
        changes = []
        
        # Nuevos archivos
        for f in set(after.keys()) - set(before.keys()):
            changes.append(f"  ➕ Creado: {f}")
        
        # Eliminados
        for f in set(before.keys()) - set(after.keys()):
            changes.append(f"  ➖ Eliminado: {f}")
        
        # Modificados
        for f in set(before.keys()) & set(after.keys()):
            if before[f]['mtime'] != after[f]['mtime']:
                changes.append(f"  ✏️ Modificado: {f}")
        
        if changes:
            return f"📊 **Cambios detectados en {duration}s:**\n\n" + "\n".join(changes)
        else:
            return f"✅ Sin cambios detectados en {duration} segundos"
    
    def _watchdog_watch(self, path: Path, duration: int, pattern: str) -> str:
        """Monitoreo con watchdog (más preciso)"""
        import fnmatch
        
        events = []
        
        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if fnmatch.fnmatch(event.src_path, f"*{pattern.replace('*', '')}*") or pattern == '*':
                    events.append(f"  ➕ Creado: {event.src_path}")
            
            def on_deleted(self, event):
                if fnmatch.fnmatch(event.src_path, f"*{pattern.replace('*', '')}*") or pattern == '*':
                    events.append(f"  ➖ Eliminado: {event.src_path}")
            
            def on_modified(self, event):
                if not event.is_directory:
                    if fnmatch.fnmatch(event.src_path, f"*{pattern.replace('*', '')}*") or pattern == '*':
                        events.append(f"  ✏️ Modificado: {event.src_path}")
            
            def on_moved(self, event):
                events.append(f"  📦 Movido: {event.src_path} → {event.dest_path}")
        
        observer = Observer()
        observer.schedule(Handler(), str(path), recursive=True)
        observer.start()
        
        print(f"👁️ Monitoreando {path} por {duration} segundos...")
        
        try:
            time.sleep(duration)
        finally:
            observer.stop()
            observer.join()
        
        if events:
            # Eliminar duplicados manteniendo orden
            unique_events = list(dict.fromkeys(events))
            return f"📊 **Cambios detectados en {duration}s:**\n\n" + "\n".join(unique_events[:50])
        else:
            return f"✅ Sin cambios detectados en {duration} segundos"


class EnhancedFileDiffTool(BaseTool):
    """
    Comparación avanzada de archivos con múltiples formatos de salida.
    
    Útil para:
    - Comparar versiones de código
    - Ver cambios entre archivos de configuración
    - Comparar con versiones de Git
    - Generar parches aplicables
    
    Soporta comparación side-by-side, unificada, y estadísticas.
    """
    
    name = "file_diff_advanced"
    description = """Compara archivos con opciones avanzadas de visualización.

Formatos:
- unified: Diff unificado estándar (default)
- side_by_side: Comparación lado a lado
- stats: Solo estadísticas de cambios
- html: Genera HTML con colores
- patch: Formato parche aplicable

Ejemplos:
- Comparar dos archivos: file1="old.py", file2="new.py"
- Con Git: file1="current.py", file2="git:HEAD~1:current.py"
- Estadísticas: format="stats"
"""
    category = "files"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "file1": ToolParameter(
                name="file1",
                type="string",
                description="Primer archivo o 'git:ref:path' para versión de Git",
                required=True
            ),
            "file2": ToolParameter(
                name="file2",
                type="string",
                description="Segundo archivo o 'git:ref:path' para versión de Git",
                required=True
            ),
            "format": ToolParameter(
                name="format",
                type="string",
                description="Formato: unified, side_by_side, stats, html, patch",
                required=False,
                enum=["unified", "side_by_side", "stats", "html", "patch"]
            ),
            "context_lines": ToolParameter(
                name="context_lines",
                type="integer",
                description="Líneas de contexto (default: 3)",
                required=False
            ),
            "ignore_whitespace": ToolParameter(
                name="ignore_whitespace",
                type="boolean",
                description="Ignorar diferencias de espacios en blanco",
                required=False
            )
        }
    
    def execute(
        self,
        file1: str = None,
        file2: str = None,
        format: str = "unified",
        context_lines: int = 3,
        ignore_whitespace: bool = False,
        **kwargs
    ) -> str:
        import difflib
        import subprocess
        
        file1 = file1 or kwargs.get('file1', '')
        file2 = file2 or kwargs.get('file2', '')
        format = format or kwargs.get('format', 'unified')
        context_lines = context_lines or kwargs.get('context_lines', 3)
        ignore_whitespace = ignore_whitespace or kwargs.get('ignore_whitespace', False)
        
        if not file1 or not file2:
            return "❌ Se requieren 'file1' y 'file2'"
        
        # Obtener contenido
        try:
            content1 = self._get_content(file1)
            content2 = self._get_content(file2)
        except Exception as e:
            return f"❌ Error leyendo archivos: {e}"
        
        if ignore_whitespace:
            content1 = [line.strip() for line in content1]
            content2 = [line.strip() for line in content2]
        
        # Generar diff según formato
        if format == "unified":
            diff = difflib.unified_diff(
                content1, content2,
                fromfile=file1, tofile=file2,
                lineterm='', n=context_lines
            )
            return self._format_unified(list(diff))
        
        elif format == "side_by_side":
            return self._format_side_by_side(content1, content2, file1, file2)
        
        elif format == "stats":
            return self._format_stats(content1, content2, file1, file2)
        
        elif format == "html":
            differ = difflib.HtmlDiff()
            html = differ.make_file(content1, content2, file1, file2, context=True, numlines=context_lines)
            # Guardar HTML
            output_file = Path("diff_output.html")
            output_file.write_text(html)
            return f"✅ HTML generado: {output_file.absolute()}\n\n" + self._format_stats(content1, content2, file1, file2)
        
        elif format == "patch":
            diff = difflib.unified_diff(
                content1, content2,
                fromfile=f"a/{file1}", tofile=f"b/{file2}",
                lineterm=''
            )
            patch_content = '\n'.join(diff)
            return f"```patch\n{patch_content}\n```\n\n💡 Aplica con: `patch -p1 < archivo.patch`"
        
        return "❌ Formato no soportado"
    
    def _get_content(self, file_spec: str) -> List[str]:
        """Obtiene contenido de archivo o desde Git"""
        import subprocess
        
        if file_spec.startswith("git:"):
            # Formato: git:ref:path
            parts = file_spec.split(":", 2)
            if len(parts) != 3:
                raise ValueError("Formato Git inválido. Usa: git:ref:path")
            ref = parts[1]
            path = parts[2]
            
            result = subprocess.run(
                ["git", "show", f"{ref}:{path}"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                raise ValueError(f"Error Git: {result.stderr}")
            return result.stdout.splitlines()
        else:
            path = Path(file_spec)
            if not path.exists():
                raise FileNotFoundError(f"Archivo no existe: {file_spec}")
            return path.read_text().splitlines()
    
    def _format_unified(self, diff_lines: List[str]) -> str:
        if not diff_lines:
            return "✅ Los archivos son idénticos"
        
        output = []
        for line in diff_lines:
            if line.startswith('+++') or line.startswith('---'):
                output.append(f"**{line}**")
            elif line.startswith('+'):
                output.append(f"🟢 {line}")
            elif line.startswith('-'):
                output.append(f"🔴 {line}")
            elif line.startswith('@@'):
                output.append(f"📍 {line}")
            else:
                output.append(f"   {line}")
        
        return "```diff\n" + '\n'.join(output[:100]) + "\n```"
    
    def _format_side_by_side(self, content1: List[str], content2: List[str], name1: str, name2: str) -> str:
        import difflib
        
        matcher = difflib.SequenceMatcher(None, content1, content2)
        
        output = [f"{'─' * 35} {name1[:30]:^30} │ {name2[:30]:^30} {'─' * 35}"]
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                for line1, line2 in zip(content1[i1:i2], content2[j1:j2]):
                    output.append(f"  {line1[:35]:35} │ {line2[:35]:35}")
            elif tag == 'replace':
                for line1 in content1[i1:i2]:
                    output.append(f"🔴{line1[:35]:35} │")
                for line2 in content2[j1:j2]:
                    output.append(f"  {' ':35} │🟢{line2[:35]}")
            elif tag == 'delete':
                for line1 in content1[i1:i2]:
                    output.append(f"🔴{line1[:35]:35} │")
            elif tag == 'insert':
                for line2 in content2[j1:j2]:
                    output.append(f"  {' ':35} │🟢{line2[:35]}")
        
        return '\n'.join(output[:80])
    
    def _format_stats(self, content1: List[str], content2: List[str], name1: str, name2: str) -> str:
        import difflib
        
        matcher = difflib.SequenceMatcher(None, content1, content2)
        
        added = 0
        removed = 0
        changed = 0
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'insert':
                added += j2 - j1
            elif tag == 'delete':
                removed += i2 - i1
            elif tag == 'replace':
                changed += max(i2 - i1, j2 - j1)
        
        ratio = matcher.ratio()
        
        return f"""📊 **Estadísticas de Diferencias**

| Métrica | Valor |
|---------|-------|
| Archivo 1 | {name1} ({len(content1)} líneas) |
| Archivo 2 | {name2} ({len(content2)} líneas) |
| Líneas añadidas | +{added} 🟢 |
| Líneas eliminadas | -{removed} 🔴 |
| Líneas cambiadas | ~{changed} 🟡 |
| Similitud | {ratio*100:.1f}% |
"""


class FileEncryptTool(BaseTool):
    """
    Encripta y desencripta archivos usando AES-256.
    
    Útil para:
    - Proteger archivos sensibles (.env, credenciales)
    - Encriptar backups antes de subir a cloud
    - Compartir archivos de forma segura
    
    Usa encriptación Fernet (AES-128-CBC) con derivación de clave PBKDF2.
    """
    
    name = "file_encrypt"
    description = """Encripta o desencripta archivos con contraseña.

Acciones:
- encrypt: Encripta archivo → genera archivo.enc
- decrypt: Desencripta archivo.enc → genera archivo original

Usa AES con derivación de clave segura (PBKDF2).
⚠️ Guarda la contraseña de forma segura, no se puede recuperar.

Ejemplos:
- Encriptar: action="encrypt", path="secrets.txt", password="..."
- Desencriptar: action="decrypt", path="secrets.txt.enc", password="..."
"""
    category = "security"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description="encrypt o decrypt",
                required=True,
                enum=["encrypt", "decrypt"]
            ),
            "path": ToolParameter(
                name="path",
                type="string",
                description="Ruta del archivo",
                required=True
            ),
            "password": ToolParameter(
                name="password",
                type="string",
                description="Contraseña para encriptar/desencriptar",
                required=True
            ),
            "output": ToolParameter(
                name="output",
                type="string",
                description="Archivo de salida (opcional)",
                required=False
            )
        }
    
    def execute(
        self,
        action: str = None,
        path: str = None,
        password: str = None,
        output: str = None,
        **kwargs
    ) -> str:
        action = action or kwargs.get('action', '')
        path = path or kwargs.get('path', '')
        password = password or kwargs.get('password', '')
        output = output or kwargs.get('output', '')
        
        if not HAS_CRYPTO:
            return "❌ Instala cryptography: `pip install cryptography`"
        
        if not action or not path or not password:
            return "❌ Se requieren 'action', 'path' y 'password'"
        
        file_path = Path(path)
        if not file_path.exists():
            return f"❌ Archivo no existe: {path}"
        
        # Derivar clave de contraseña
        salt = b'nvidia_code_salt_v1'  # En producción usar salt aleatorio
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        fernet = Fernet(key)
        
        try:
            if action == "encrypt":
                data = file_path.read_bytes()
                encrypted = fernet.encrypt(data)
                
                output_path = Path(output) if output else file_path.with_suffix(file_path.suffix + '.enc')
                output_path.write_bytes(encrypted)
                
                original_size = len(data)
                encrypted_size = len(encrypted)
                
                return f"""🔐 **Archivo Encriptado**

| Propiedad | Valor |
|-----------|-------|
| Original | {path} ({original_size:,} bytes) |
| Encriptado | {output_path} ({encrypted_size:,} bytes) |
| Algoritmo | AES-256 (Fernet) |

⚠️ **Guarda la contraseña de forma segura**
💡 Para desencriptar: action="decrypt", path="{output_path}", password="..."
"""
            
            elif action == "decrypt":
                encrypted_data = file_path.read_bytes()
                
                try:
                    decrypted = fernet.decrypt(encrypted_data)
                except Exception:
                    return "❌ Error al desencriptar. ¿Contraseña incorrecta?"
                
                # Determinar nombre de salida
                if output:
                    output_path = Path(output)
                elif path.endswith('.enc'):
                    output_path = Path(path[:-4])  # Quitar .enc
                else:
                    output_path = file_path.with_suffix('.decrypted')
                
                output_path.write_bytes(decrypted)
                
                return f"""🔓 **Archivo Desencriptado**

| Propiedad | Valor |
|-----------|-------|
| Encriptado | {path} |
| Desencriptado | {output_path} ({len(decrypted):,} bytes) |

✅ Archivo restaurado correctamente
"""
            
            else:
                return f"❌ Acción no válida: {action}"
        
        except Exception as e:
            return f"❌ Error: {str(e)}"


class FileMetadataTool(BaseTool):
    """
    Obtiene metadata detallada de archivos.
    
    Útil para:
    - Ver información completa de archivos (tamaño, fechas, permisos)
    - Calcular hashes para verificar integridad
    - Ver EXIF de imágenes
    - Analizar tipos MIME
    - Detectar archivos binarios vs texto
    """
    
    name = "file_metadata"
    description = """Obtiene información detallada de un archivo.

Muestra:
- Tamaño, fechas de creación/modificación
- Permisos y propietario
- Tipo MIME
- Hash SHA256 (para verificar integridad)
- Si es binario o texto
- EXIF para imágenes (si está disponible)

Ejemplo: path="document.pdf"
"""
    category = "files"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(
                name="path",
                type="string",
                description="Ruta del archivo",
                required=True
            ),
            "calculate_hash": ToolParameter(
                name="calculate_hash",
                type="boolean",
                description="Calcular hash SHA256 (puede ser lento para archivos grandes)",
                required=False
            )
        }
    
    def execute(self, path: str = None, calculate_hash: bool = True, **kwargs) -> str:
        import mimetypes
        import stat
        
        path = path or kwargs.get('path', '')
        calculate_hash = calculate_hash if calculate_hash is not None else kwargs.get('calculate_hash', True)
        
        if not path:
            return "❌ Se requiere 'path'"
        
        file_path = Path(path)
        if not file_path.exists():
            return f"❌ Archivo no existe: {path}"
        
        try:
            stat_info = file_path.stat()
            
            # Información básica
            size = stat_info.st_size
            created = datetime.fromtimestamp(stat_info.st_ctime)
            modified = datetime.fromtimestamp(stat_info.st_mtime)
            accessed = datetime.fromtimestamp(stat_info.st_atime)
            
            # Formatear tamaño
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    size_str = f"{size:.1f} {unit}"
                    break
                size /= 1024
            else:
                size_str = f"{size:.1f} TB"
            
            # Permisos
            mode = stat_info.st_mode
            perms = stat.filemode(mode)
            
            # Tipo MIME
            mime_type, _ = mimetypes.guess_type(str(file_path))
            mime_type = mime_type or "application/octet-stream"
            
            # ¿Es binario?
            is_binary = self._is_binary(file_path)
            
            # Hash
            hash_value = "No calculado"
            if calculate_hash and stat_info.st_size < 100 * 1024 * 1024:  # Max 100MB
                hash_value = self._calculate_hash(file_path)
            elif stat_info.st_size >= 100 * 1024 * 1024:
                hash_value = "Archivo muy grande (>100MB)"
            
            output = f"""📋 **Metadata: {file_path.name}**

**📁 Información General:**
| Propiedad | Valor |
|-----------|-------|
| Ruta completa | `{file_path.absolute()}` |
| Tamaño | {size_str} ({stat_info.st_size:,} bytes) |
| Tipo MIME | {mime_type} |
| Es binario | {'Sí' if is_binary else 'No (texto)'} |

**📅 Fechas:**
| Evento | Fecha |
|--------|-------|
| Creado | {created.strftime('%Y-%m-%d %H:%M:%S')} |
| Modificado | {modified.strftime('%Y-%m-%d %H:%M:%S')} |
| Accedido | {accessed.strftime('%Y-%m-%d %H:%M:%S')} |

**🔒 Permisos:**
| Propiedad | Valor |
|-----------|-------|
| Modo | {perms} ({oct(mode)[-3:]}) |
| Legible | {'✅' if os.access(file_path, os.R_OK) else '❌'} |
| Escribible | {'✅' if os.access(file_path, os.W_OK) else '❌'} |
| Ejecutable | {'✅' if os.access(file_path, os.X_OK) else '❌'} |

**🔐 Integridad:**
| Hash | Valor |
|------|-------|
| SHA256 | `{hash_value}` |
"""
            
            # Info adicional para imágenes
            if mime_type and mime_type.startswith('image/'):
                exif_info = self._get_image_info(file_path)
                if exif_info:
                    output += f"\n**🖼️ Información de Imagen:**\n{exif_info}"
            
            return output
            
        except Exception as e:
            return f"❌ Error obteniendo metadata: {str(e)}"
    
    def _is_binary(self, path: Path) -> bool:
        """Detecta si un archivo es binario"""
        try:
            with open(path, 'rb') as f:
                chunk = f.read(8192)
                if b'\x00' in chunk:
                    return True
                # Verificar caracteres no imprimibles
                text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
                return bool(chunk.translate(None, text_chars))
        except:
            return True
    
    def _calculate_hash(self, path: Path) -> str:
        """Calcula hash SHA256"""
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _get_image_info(self, path: Path) -> str:
        """Obtiene información de imagen (dimensiones, etc.)"""
        try:
            from PIL import Image
            with Image.open(path) as img:
                return f"""| Dimensiones | {img.width} x {img.height} px |
| Formato | {img.format} |
| Modo | {img.mode} |
"""
        except ImportError:
            return "| Info | Instala Pillow para ver detalles de imagen |"
        except Exception:
            return ""