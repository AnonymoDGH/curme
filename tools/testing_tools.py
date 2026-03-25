# NVIDIA CODE - Herramientas de Testing

import subprocess
import os
import re
from pathlib import Path
from typing import Dict

from .base import BaseTool, ToolParameter


class TestRunTool(BaseTool):
    # Ejecuta tests
    
    name = "test_run"
    description = "Ejecuta tests del proyecto (pytest, jest, etc.)"
    category = "testing"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(name="path", type="string", description="Archivo o directorio de tests", required=False),
            "framework": ToolParameter(name="framework", type="string", description="Framework: pytest, jest, unittest", required=False, enum=["pytest", "jest", "unittest", "auto"]),
            "verbose": ToolParameter(name="verbose", type="boolean", description="Salida detallada", required=False)
        }
    
    def execute(self, path: str = None, framework: str = "auto", verbose: bool = True, **kwargs) -> str:
        path = path or kwargs.get('path', '')
        framework = framework or kwargs.get('framework', 'auto')
        verbose = verbose if verbose is not None else kwargs.get('verbose', True)
        
        # Auto-detectar framework
        if framework == "auto":
            if Path("package.json").exists():
                framework = "jest"
            else:
                framework = "pytest"
        
        # Construir comando
        if framework == "pytest":
            v_flag = '-v' if verbose else ''
            cmd = f"pytest {v_flag} {path}".strip()
        elif framework == "jest":
            cmd = f"npx jest {path}".strip()
        elif framework == "unittest":
            cmd = f"python -m unittest discover {path}".strip()
        else:
            return f"[x] Framework no soportado: {framework}"
        
        try:
            print(f"[*] Ejecutando: {cmd}\n")
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
            
            output = f"\n[TEST] Resultados ({framework}):\n\n"
            output += result.stdout[:3000] if result.stdout else "(sin salida)"
            
            if result.stderr and result.returncode != 0:
                output += f"\n\nErrores:\n{result.stderr[:1000]}"
            
            if result.returncode == 0:
                output += "\n\n[OK] Todos los tests pasaron"
            else:
                output += f"\n\n[FAIL] Tests fallidos (codigo: {result.returncode})"
            
            return output
            
        except subprocess.TimeoutExpired:
            return "[x] Timeout ejecutando tests"
        except Exception as e:
            return f"[x] Error: {e}"


class TestGenerateTool(BaseTool):
    # Genera tests automaticamente
    
    name = "test_generate"
    description = "Genera estructura de tests para un archivo"
    category = "testing"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(name="path", type="string", description="Archivo para generar tests", required=True),
            "framework": ToolParameter(name="framework", type="string", description="Framework: pytest, jest", required=False, enum=["pytest", "jest"])
        }
    
    def execute(self, path: str = None, framework: str = "pytest", **kwargs) -> str:
        path = path or kwargs.get('path', '')
        framework = framework or kwargs.get('framework', 'pytest')
        
        if not path:
            return "[x] Se requiere 'path'"
        
        file_path = Path(path)
        if not file_path.exists():
            return f"[x] Archivo no encontrado: {path}"
        
        try:
            code = file_path.read_text(encoding='utf-8')
        except Exception as e:
            return f"[x] Error leyendo archivo: {e}"
        
        # Extraer funciones y clases
        functions = re.findall(r'def (\w+)\s*\(', code)
        classes = re.findall(r'class (\w+)', code)
        
        # Filtrar funciones privadas
        functions = [f for f in functions if not f.startswith('_')]
        
        if framework == "pytest":
            lines = []
            lines.append(f"# Tests para {file_path.name}")
            lines.append("")
            lines.append("import pytest")
            lines.append(f"from {file_path.stem} import *")
            lines.append("")
            lines.append("")
            
            for func in functions:
                lines.append(f"def test_{func}():")
                lines.append(f"    # Test para {func}")
                lines.append("    # TODO: Implementar")
                lines.append("    assert True")
                lines.append("")
                lines.append("")
            
            for cls in classes:
                lines.append(f"class Test{cls}:")
                lines.append(f"    # Tests para {cls}")
                lines.append("")
                lines.append("    def test_init(self):")
                lines.append("        # TODO: Implementar")
                lines.append("        assert True")
                lines.append("")
                lines.append("")
            
            test_code = "\n".join(lines)
            test_file = f"test_{file_path.stem}.py"
        
        elif framework == "jest":
            lines = []
            lines.append(f"// Tests para {file_path.name}")
            lines.append("")
            
            funcs_import = ", ".join(functions[:5]) if functions else "example"
            lines.append(f"const {{ {funcs_import} }} = require('./{file_path.stem}');")
            lines.append("")
            
            for func in functions[:10]:
                lines.append(f"describe('{func}', () => {{")
                lines.append("    test('deberia funcionar', () => {")
                lines.append("        // TODO: Implementar")
                lines.append("        expect(true).toBe(true);")
                lines.append("    });")
                lines.append("});")
                lines.append("")
            
            test_code = "\n".join(lines)
            test_file = f"{file_path.stem}.test.js"
        
        else:
            return f"[x] Framework no soportado: {framework}"
        
        result = f"[TEST] Tests generados para {path}\n\n"
        result += f"Archivo sugerido: {test_file}\n"
        result += f"Funciones: {len(functions)}\n"
        result += f"Clases: {len(classes)}\n\n"
        result += f"```\n{test_code}\n```"
        
        return result


class LintCheckTool(BaseTool):
    # Verifica estilo de codigo
    
    name = "lint_check"
    description = "Verifica estilo y errores de codigo con linters"
    category = "testing"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(name="path", type="string", description="Archivo o directorio", required=True),
            "linter": ToolParameter(name="linter", type="string", description="Linter a usar", required=False, enum=["flake8", "pylint", "eslint", "auto"])
        }
    
    def execute(self, path: str = None, linter: str = "auto", **kwargs) -> str:
        path = path or kwargs.get('path', '')
        linter = linter or kwargs.get('linter', 'auto')
        
        if not path:
            return "[x] Se requiere 'path'"
        
        file_path = Path(path)
        
        # Auto-detectar linter
        if linter == "auto":
            if file_path.suffix == '.py':
                linter = "flake8"
            elif file_path.suffix in ['.js', '.ts']:
                linter = "eslint"
            elif file_path.is_dir():
                if list(file_path.glob('*.py')):
                    linter = "flake8"
                elif list(file_path.glob('*.js')):
                    linter = "eslint"
                else:
                    linter = "flake8"
            else:
                linter = "flake8"
        
        # Construir comando
        if linter == "flake8":
            cmd = f"flake8 {path} --max-line-length=100"
        elif linter == "pylint":
            cmd = f"pylint {path} --max-line-length=100"
        elif linter == "eslint":
            cmd = f"npx eslint {path}"
        else:
            return f"[x] Linter no soportado: {linter}"
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            
            stdout = result.stdout.strip() if result.stdout else ""
            stderr = result.stderr.strip() if result.stderr else ""
            
            if not stdout and not stderr:
                return f"[OK] {linter}: Sin problemas en {path}"
            
            output = f"[LINT] Resultados de {linter}:\n\n"
            
            if stdout:
                output += stdout[:2000]
            
            if stderr and result.returncode != 0:
                output += f"\n{stderr[:500]}"
            
            # Contar problemas
            if stdout:
                lines = [l for l in stdout.split('\n') if l.strip()]
                output += f"\n\n[INFO] {len(lines)} problemas encontrados"
            
            return output
            
        except FileNotFoundError:
            return f"[x] {linter} no instalado"
        except subprocess.TimeoutExpired:
            return "[x] Timeout"
        except Exception as e:
            return f"[x] Error: {e}"