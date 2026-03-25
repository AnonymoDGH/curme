"""
NVIDIA CODE - Herramientas de Archivos (Versión Avanzada)
"""

import sys
import time
import shutil
import os
from pathlib import Path
from typing import Dict, Optional

from .base import BaseTool, ToolParameter

# Intentar importar colores, si falla usar dummy
try:
    # Hack para importar desde el directorio padre si es necesario
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(os.path.dirname(current_dir))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    
    from ui.colors import Colors
    C = Colors()
except ImportError:
    class Colors:
        NVIDIA_GREEN = ""
        BRIGHT_CYAN = ""
        BRIGHT_GREEN = ""
        BRIGHT_MAGENTA = ""
        BRIGHT_RED = ""
        YELLOW = ""
        DIM = ""
        RESET = ""
    C = Colors()


class ReadFileTool(BaseTool):
    """Lee el contenido de un archivo"""
    
    name = "read_file"
    description = "Lee el contenido completo de un archivo"
    category = "files"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(name="path", type="string", description="Ruta del archivo a leer", required=True)
        }
    
    def execute(self, **kwargs) -> str:
        path = kwargs.get('path', '')
        
        if not path:
            return "[x] Error: Se requiere el parametro 'path'"
        
        try:
            file_path = Path(path)
            if not file_path.exists():
                return f"[x] Archivo no encontrado: {path}"
            
            if not file_path.is_file():
                return f"[x] No es un archivo: {path}"
            
            # Mostrar progreso para archivos grandes
            file_size = file_path.stat().st_size
            
            if file_size > 50000:  # > 50KB
                print(f"{C.DIM}📖 Leyendo {path} ({file_size:,} bytes)...{C.RESET}")
            
            content = file_path.read_text(encoding='utf-8', errors='replace')
            lines = content.split('\n')
            
            result = f"📄 **{path}** ({len(lines)} líneas)\n```\n"
            for i, line in enumerate(lines[:100], 1):
                result += f"{i:4} │ {line}\n"
            if len(lines) > 100:
                result += f"... ({len(lines) - 100} líneas más)\n"
            result += "```"
            
            return result
        except Exception as e:
            return f"[x] Error leyendo archivo: {str(e)}"


class WriteFileTool(BaseTool):
    """Escribe contenido en un archivo con progreso visual"""
    
    name = "write_file"
    description = "Crea o sobrescribe un archivo con el contenido proporcionado"
    category = "files"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(name="path", type="string", description="Ruta del archivo", required=True),
            "content": ToolParameter(name="content", type="string", description="Contenido a escribir", required=True)
        }
    
    def execute(self, **kwargs) -> str:
        path = kwargs.get('path', '')
        content = kwargs.get('content', '')
        
        if not path:
            return "[x] Error: Se requiere el parametro 'path'"
        if content is None:
            return "[x] Error: Se requiere el parametro 'content'"
        
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            existed = file_path.exists()
            lines = content.split('\n')
            total_chars = len(content)
            total_lines = len(lines)
            
            # Para archivos grandes, mostrar progreso
            if total_chars > 5000 or total_lines > 100:
                print(f"\n{C.BRIGHT_CYAN}📝 Escribiendo: {file_path.name}{C.RESET}")
                print(f"{C.DIM}   📊 {total_lines} líneas, {total_chars:,} caracteres{C.RESET}")
                
                # Barra de progreso
                bar_width = 40
                chunk_size = max(1, total_lines // 20)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    for i, line in enumerate(lines):
                        f.write(line)
                        if i < total_lines - 1:
                            f.write('\n')
                        
                        # Actualizar progreso
                        if (i + 1) % chunk_size == 0 or i == total_lines - 1:
                            progress = (i + 1) / total_lines
                            filled = int(bar_width * progress)
                            bar = f"{C.NVIDIA_GREEN}{'█' * filled}{C.DIM}{'░' * (bar_width - filled)}{C.RESET}"
                            
                            sys.stdout.write(f"\r   {bar} {progress*100:5.1f}% │ L{i+1} ")
                            sys.stdout.flush()
                
                print(f"\n{C.BRIGHT_GREEN}   ✅ Completado{C.RESET}\n")
            else:
                # Archivo pequeño
                file_path.write_text(content, encoding='utf-8')
            
            action = "actualizado" if existed else "creado"
            return f"✅ Archivo {action}: {path}\n   📊 {total_lines} líneas, {total_chars:,} caracteres"
            
        except Exception as e:
            return f"[x] Error escribiendo archivo: {str(e)}"


class WriteFileStreamTool(BaseTool):
    """Escribe archivo mostrando contenido en tiempo real"""
    
    name = "write_file_stream"
    description = "Escribe un archivo mostrando el contenido mientras se escribe (efecto visual)"
    category = "files"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(name="path", type="string", description="Ruta del archivo", required=True),
            "content": ToolParameter(name="content", type="string", description="Contenido a escribir", required=True)
        }
    
    def execute(self, **kwargs) -> str:
        path = kwargs.get('path', '')
        content = kwargs.get('content', '')
        
        if not path:
            return "[x] Error: Se requiere 'path'"
        if content is None:
            return "[x] Error: Se requiere 'content'"
        
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            lines = content.split('\n')
            total_lines = len(lines)
            total_chars = len(content)
            
            # Header visual
            print(f"\n{C.NVIDIA_GREEN}╭─ 📝 Escribiendo: {file_path.name} {'─' * (35 - len(file_path.name) if len(file_path.name) < 35 else 0)}╮{C.RESET}")
            print(f"{C.NVIDIA_GREEN}│{C.RESET} {C.DIM}📊 {total_lines} líneas, {total_chars:,} caracteres{C.RESET}")
            print(f"{C.NVIDIA_GREEN}├{'─' * 50}┤{C.RESET}")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                for i, line in enumerate(lines):
                    f.write(line)
                    if i < total_lines - 1:
                        f.write('\n')
                    
                    # Mostrar linea
                    line_num = f"{i+1:4}"
                    display_line = line[:70] + "..." if len(line) > 70 else line
                    display_line = display_line.replace('\t', '  ')
                    
                    # Highlight simple
                    display_line = self._highlight_line(display_line, file_path.suffix)
                    
                    print(f"{C.NVIDIA_GREEN}│{C.RESET}{C.DIM}{line_num}│{C.RESET} {display_line}")
                    
                    # Efecto visual (solo primeras 50 lineas para no tardar mucho)
                    if i < 50:
                        time.sleep(0.005)
            
            print(f"{C.NVIDIA_GREEN}╰{'─' * 50}╯{C.RESET}")
            print(f"{C.BRIGHT_GREEN}✅ Archivo guardado exitosamente{C.RESET}\n")
            
            return f"✅ Archivo creado con stream: {path}"
            
        except Exception as e:
            return f"[x] Error: {str(e)}"
    
    def _highlight_line(self, line: str, ext: str) -> str:
        """Aplica highlighting básico"""
        import re
        if ext in ['.py']:
            keywords = ['def', 'class', 'import', 'from', 'return', 'if', 'else', 'elif',
                       'for', 'while', 'try', 'except', 'with', 'as', 'True', 'False', 'None']
            for kw in keywords:
                line = re.sub(rf'\b({kw})\b', f'{C.BRIGHT_MAGENTA}\\1{C.RESET}', line)
            line = re.sub(r'(\"[^\"]*\"|\'[^\']*\')', f'{C.BRIGHT_GREEN}\\1{C.RESET}', line)
            line = re.sub(r'(#.*)$', f'{C.DIM}\\1{C.RESET}', line)
        elif ext in ['.js', '.ts']:
            keywords = ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'class', 'import', 'export']
            for kw in keywords:
                line = re.sub(rf'\b({kw})\b', f'{C.BRIGHT_MAGENTA}\\1{C.RESET}', line)
            line = re.sub(r'(\"[^\"]*\"|\'[^\']*\'|`[^`]*`)', f'{C.BRIGHT_GREEN}\\1{C.RESET}', line)
            line = re.sub(r'(//.*$)', f'{C.DIM}\\1{C.RESET}', line)
        return line


class EditFileTool(BaseTool):
    """Edita un archivo reemplazando texto"""
    
    name = "edit_file"
    description = "Edita un archivo reemplazando texto especifico"
    category = "files"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(name="path", type="string", description="Ruta del archivo", required=True),
            "old_text": ToolParameter(name="old_text", type="string", description="Texto a reemplazar", required=True),
            "new_text": ToolParameter(name="new_text", type="string", description="Nuevo texto", required=True)
        }
    
    def execute(self, **kwargs) -> str:
        path = kwargs.get('path', '')
        old_text = kwargs.get('old_text', '')
        new_text = kwargs.get('new_text', '')
        
        if not path:
            return "[x] Error: Se requiere 'path'"
        if not old_text:
            return "[x] Error: Se requiere 'old_text'"
        
        try:
            file_path = Path(path)
            if not file_path.exists():
                return f"[x] Archivo no encontrado: {path}"
            
            print(f"{C.DIM}📝 Editando {path}...{C.RESET}")
            
            content = file_path.read_text(encoding='utf-8')
            
            if old_text not in content:
                # Intento de búsqueda flexible (ignorando espacios en blanco)
                import re
                escaped_old = re.escape(old_text).replace(r'\ ', r'\s+')
                match = re.search(escaped_old, content)
                if not match:
                    return f"[x] Texto no encontrado en {path}"
                old_text = match.group(0)
            
            count = content.count(old_text)
            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content, encoding='utf-8')
            
            # Mostrar diff visual
            print(f"{C.RED}  - {old_text[:50]}{'...' if len(old_text) > 50 else ''}{C.RESET}")
            print(f"{C.GREEN}  + {new_text[:50]}{'...' if len(new_text) > 50 else ''}{C.RESET}")
            
            result = f"✅ Archivo editado: {path}"
            if count > 1:
                result += f"\n   ℹ️ Había {count} ocurrencias, se reemplazó la primera"
            
            return result
        except Exception as e:
            return f"[x] Error: {str(e)}"


class DeleteFileTool(BaseTool):
    """Elimina un archivo o directorio"""
    
    name = "delete_file"
    description = "Elimina un archivo o directorio"
    category = "files"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(name="path", type="string", description="Ruta a eliminar", required=True),
            "recursive": ToolParameter(name="recursive", type="boolean", description="Eliminar recursivamente", required=False)
        }
    
    def execute(self, **kwargs) -> str:
        path = kwargs.get('path', '')
        recursive = kwargs.get('recursive', False)
        
        if not path:
            return "[x] Error: Se requiere 'path'"
        
        try:
            file_path = Path(path)
            if not file_path.exists():
                return f"[x] No existe: {path}"
            
            if file_path.is_dir():
                if recursive:
                    file_count = sum(1 for _ in file_path.rglob('*') if _.is_file())
                    print(f"{C.YELLOW}🗑️ Eliminando directorio con {file_count} archivos...{C.RESET}")
                    shutil.rmtree(file_path)
                else:
                    file_path.rmdir()
            else:
                file_path.unlink()
            
            return f"✅ Eliminado: {path}"
        except Exception as e:
            return f"[x] Error: {str(e)}"


class AppendFileTool(BaseTool):
    """Añade contenido al final de un archivo"""
    
    name = "append_file"
    description = "Añade contenido al final de un archivo existente"
    category = "files"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(name="path", type="string", description="Ruta del archivo", required=True),
            "content": ToolParameter(name="content", type="string", description="Contenido a añadir", required=True)
        }
    
    def execute(self, **kwargs) -> str:
        path = kwargs.get('path', '')
        content = kwargs.get('content', '')
        
        if not path:
            return "[x] Se requiere 'path'"
        if not content:
            return "[x] Se requiere 'content'"
        
        try:
            file_path = Path(path)
            
            print(f"{C.DIM}📎 Añadiendo a {path}...{C.RESET}")
            
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(content)
            
            lines_added = len(content.split('\n'))
            return f"✅ Añadido a {path}: {lines_added} líneas, {len(content)} caracteres"
        except Exception as e:
            return f"[x] Error: {str(e)}"