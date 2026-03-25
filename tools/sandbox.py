"""
NVIDIA CODE - Sandbox de Ejecucion Segura
"""

import subprocess
import tempfile
import os
import sys
import ast
import traceback
from pathlib import Path
from typing import Dict, Tuple, Optional
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
import threading

from .base import BaseTool, ToolParameter


class CodeSandbox:
    """Ejecuta codigo de forma segura con limites"""
    
    BLOCKED_IMPORTS = [
        'os.system', 'subprocess', 'shutil.rmtree', 
        'eval', 'exec', '__import__'
    ]
    
    def __init__(self, timeout: int = 10, max_output: int = 50000):
        self.timeout = timeout
        self.max_output = max_output
    
    def analyze_code(self, code: str) -> Tuple[bool, str]:
        """Analiza codigo buscando operaciones peligrosas"""
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in ['subprocess', 'shutil']:
                            return False, f"Import bloqueado: {alias.name}"
                
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if hasattr(node.func.value, 'id'):
                            full_name = f"{node.func.value.id}.{node.func.attr}"
                            if full_name in self.BLOCKED_IMPORTS:
                                return False, f"Llamada bloqueada: {full_name}"
            
            return True, "OK"
        except SyntaxError as e:
            return False, f"Error de sintaxis: {e}"
    
    def execute_in_subprocess(self, code: str, language: str = "python") -> Dict:
        """Ejecuta codigo en subproceso aislado"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            if language == "python":
                file_path = Path(tmpdir) / "code.py"
                file_path.write_text(code, encoding='utf-8')
                cmd = [sys.executable, str(file_path)]
            elif language == "node":
                file_path = Path(tmpdir) / "code.js"
                file_path.write_text(code, encoding='utf-8')
                cmd = ["node", str(file_path)]
            elif language == "bash":
                file_path = Path(tmpdir) / "code.sh"
                file_path.write_text(code, encoding='utf-8')
                cmd = ["bash", str(file_path)]
            else:
                return {"success": False, "error": f"Lenguaje no soportado: {language}"}
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=tmpdir
                )
                
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout[:self.max_output],
                    "stderr": result.stderr[:self.max_output],
                    "return_code": result.returncode,
                    "error": None if result.returncode == 0 else result.stderr
                }
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": f"Timeout: {self.timeout}s",
                    "stdout": "",
                    "stderr": ""
                }
            except FileNotFoundError:
                return {
                    "success": False,
                    "error": f"Interprete no encontrado para {language}",
                    "stdout": "",
                    "stderr": ""
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "stdout": "",
                    "stderr": ""
                }


class RunCodeTool(BaseTool):
    """Ejecuta codigo en sandbox"""
    
    name = "run_code"
    description = "Ejecuta codigo Python/JavaScript/Bash de forma segura y retorna el resultado"
    category = "execution"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "code": ToolParameter(
                name="code",
                type="string",
                description="Codigo a ejecutar",
                required=True
            ),
            "language": ToolParameter(
                name="language",
                type="string",
                description="Lenguaje: python, node, bash",
                required=False,
                enum=["python", "node", "bash"]
            ),
            "timeout": ToolParameter(
                name="timeout",
                type="integer",
                description="Timeout en segundos (default: 10)",
                required=False
            )
        }
    
    def execute(self, code: str = None, language: str = "python", timeout: int = 10, **kwargs) -> str:
        code = code or kwargs.get('code', '')
        language = language or kwargs.get('language', 'python')
        timeout = timeout or kwargs.get('timeout', 10)
        
        if not code:
            return "[x] Se requiere 'code'"
        
        # Import aqui para evitar circular
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from ui.colors import Colors
        C = Colors()
        
        sandbox = CodeSandbox(timeout=timeout)
        
        print(f"\n{C.BRIGHT_CYAN}▶ Ejecutando {language}...{C.RESET}")
        
        result = sandbox.execute_in_subprocess(code, language)
        
        # Construir output
        lines = []
        lines.append(f"\n{C.NVIDIA_GREEN}╭─ Resultado de Ejecucion {'─' * 25}╮{C.RESET}")
        
        if result["success"]:
            lines.append(f"{C.NVIDIA_GREEN}│{C.RESET} {C.BRIGHT_GREEN}✓ Exito{C.RESET}")
        else:
            lines.append(f"{C.NVIDIA_GREEN}│{C.RESET} {C.BRIGHT_RED}✗ Error{C.RESET}")
        
        if result.get("stdout"):
            lines.append(f"{C.NVIDIA_GREEN}├─ STDOUT {'─' * 40}┤{C.RESET}")
            for line in result["stdout"].split('\n')[:30]:
                lines.append(f"{C.NVIDIA_GREEN}│{C.RESET} {line}")
        
        if result.get("stderr"):
            lines.append(f"{C.NVIDIA_GREEN}├─ STDERR {'─' * 40}┤{C.RESET}")
            for line in result["stderr"].split('\n')[:15]:
                lines.append(f"{C.NVIDIA_GREEN}│{C.RESET} {C.RED}{line}{C.RESET}")
        
        if result.get("error") and not result["success"]:
            lines.append(f"{C.NVIDIA_GREEN}├─ Error {'─' * 41}┤{C.RESET}")
            error_text = str(result['error'])[:500]
            lines.append(f"{C.NVIDIA_GREEN}│{C.RESET} {C.RED}{error_text}{C.RESET}")
        
        lines.append(f"{C.NVIDIA_GREEN}╰{'─' * 50}╯{C.RESET}")
        
        return '\n'.join(lines)


class RunFileAndFixTool(BaseTool):
    """Ejecuta un archivo y si falla, muestra info para arreglarlo"""
    
    name = "run_and_fix"
    description = "Ejecuta un archivo, detecta errores y muestra informacion para corregirlos"
    category = "execution"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(
                name="path",
                type="string",
                description="Ruta del archivo a ejecutar",
                required=True
            )
        }
    
    def execute(self, path: str = None, **kwargs) -> str:
        path = path or kwargs.get('path', '')
        
        if not path:
            return "[x] Se requiere 'path'"
        
        file_path = Path(path)
        if not file_path.exists():
            return f"[x] Archivo no encontrado: {path}"
        
        # Detectar lenguaje
        lang_map = {'.py': 'python', '.js': 'node', '.sh': 'bash'}
        language = lang_map.get(file_path.suffix, 'python')
        
        try:
            code = file_path.read_text(encoding='utf-8')
        except Exception as e:
            return f"[x] Error leyendo archivo: {e}"
        
        sandbox = CodeSandbox(timeout=15)
        result = sandbox.execute_in_subprocess(code, language)
        
        if result["success"]:
            output = f"✅ {path} ejecutado exitosamente\n\n"
            if result.get("stdout"):
                output += f"Output:\n```\n{result['stdout'][:2000]}\n```"
            return output
        else:
            error_info = result.get("stderr", "") or result.get("error", "")
            
            # Limitar longitud del codigo mostrado
            code_preview = code
            if len(code) > 1500:
                code_preview = code[:1500] + "\n... (truncado)"
            
            output = f"❌ Error ejecutando {path}\n\n"
            output += f"**Error:**\n```\n{error_info[:1000]}\n```\n\n"
            output += f"**Codigo:**\n```{language}\n{code_preview}\n```\n\n"
            output += "Analiza el error y proporciona una correccion."
            
            return output