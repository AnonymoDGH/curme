"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         HERRAMIENTAS DE ANÁLISIS                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import re
from typing import Dict, List
from .base import BaseTool, ToolParameter


class AnalyzeCodeTool(BaseTool):
    """Analiza código en busca de problemas y mejoras"""
    
    name = "analyze_code"
    description = "Analiza código fuente para encontrar problemas, sugerir mejoras y verificar buenas prácticas"
    category = "analysis"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "code": ToolParameter(
                name="code",
                type="string",
                description="Código fuente a analizar",
                required=True
            ),
            "language": ToolParameter(
                name="language",
                type="string",
                description="Lenguaje de programación",
                required=False,
                enum=["python", "javascript", "typescript", "java", "go", "rust", "auto"]
            )
        }
    
    def execute(self, code: str, language: str = "auto") -> str:
        # Detectar lenguaje si es auto
        if language == "auto":
            language = self._detect_language(code)
        
        lines = code.split('\n')
        issues = []
        suggestions = []
        metrics = {
            "lines": len(lines),
            "chars": len(code),
            "blank_lines": sum(1 for l in lines if not l.strip()),
            "comment_lines": 0,
            "functions": 0,
            "classes": 0,
        }
        
        # Análisis específico por lenguaje
        if language == "python":
            issues, suggestions, metrics = self._analyze_python(code, lines, metrics)
        elif language in ["javascript", "typescript"]:
            issues, suggestions, metrics = self._analyze_javascript(code, lines, metrics)
        else:
            issues, suggestions = self._analyze_generic(code, lines)
        
        # Construir reporte
        result = f"""📊 **Análisis de Código** ({language})

**📏 Métricas:**
  • Líneas totales: {metrics['lines']}
  • Líneas en blanco: {metrics['blank_lines']}
  • Líneas de comentario: {metrics.get('comment_lines', 'N/A')}
  • Funciones: {metrics.get('functions', 'N/A')}
  • Clases: {metrics.get('classes', 'N/A')}
  • Caracteres: {metrics['chars']:,}
"""
        
        if issues:
            result += f"\n**⚠️ Problemas encontrados ({len(issues)}):**\n"
            for issue in issues[:10]:
                result += f"  • {issue}\n"
            if len(issues) > 10:
                result += f"  ... y {len(issues) - 10} más\n"
        else:
            result += "\n**✅ No se encontraron problemas obvios**\n"
        
        if suggestions:
            result += f"\n**💡 Sugerencias ({len(suggestions)}):**\n"
            for suggestion in suggestions[:8]:
                result += f"  • {suggestion}\n"
        
        return result
    
    def _detect_language(self, code: str) -> str:
        """Detecta el lenguaje del código"""
        if "def " in code and ":" in code:
            return "python"
        if "function " in code or "const " in code or "let " in code:
            return "javascript"
        if "fn " in code and "->" in code:
            return "rust"
        if "func " in code and "package " in code:
            return "go"
        if "public class" in code or "private void" in code:
            return "java"
        return "python"  # Default
    
    def _analyze_python(self, code: str, lines: List[str], metrics: Dict) -> tuple:
        """Análisis específico para Python"""
        issues = []
        suggestions = []
        
        # Contar elementos
        metrics["functions"] = len(re.findall(r'def \w+', code))
        metrics["classes"] = len(re.findall(r'class \w+', code))
        metrics["comment_lines"] = sum(1 for l in lines if l.strip().startswith('#'))
        
        # Verificaciones
        if "import *" in code:
            issues.append("Evita `import *`, importa solo lo necesario")
        
        if re.search(r'except\s*:', code):
            issues.append("Evita `except:` genérico, captura excepciones específicas")
        
        if "print(" in code and "logging" not in code and metrics["functions"] > 2:
            suggestions.append("Considera usar `logging` en lugar de `print` para proyectos más grandes")
        
        if metrics["functions"] > 0:
            # Verificar docstrings
            funcs_without_docs = len(re.findall(r'def \w+[^:]+:\n\s*[^"\']', code))
            if funcs_without_docs > 0:
                suggestions.append(f"Añade docstrings a tus funciones ({funcs_without_docs} sin documentar)")
        
        if "def " in code and "-> " not in code:
            suggestions.append("Considera añadir type hints para mejor legibilidad")
        
        # Líneas muy largas
        long_lines = [(i+1, len(l)) for i, l in enumerate(lines) if len(l) > 100]
        if long_lines:
            issues.append(f"Hay {len(long_lines)} líneas con más de 100 caracteres")
        
        # Variables con nombres cortos
        short_vars = re.findall(r'\b([a-z])\s*=', code)
        if len(short_vars) > 3:
            suggestions.append("Usa nombres de variables más descriptivos")
        
        # TODO/FIXME
        todos = len(re.findall(r'#\s*(TODO|FIXME|XXX|HACK)', code, re.IGNORECASE))
        if todos > 0:
            issues.append(f"Hay {todos} comentarios TODO/FIXME pendientes")
        
        return issues, suggestions, metrics
    
    def _analyze_javascript(self, code: str, lines: List[str], metrics: Dict) -> tuple:
        """Análisis específico para JavaScript/TypeScript"""
        issues = []
        suggestions = []
        
        metrics["functions"] = len(re.findall(r'function \w+|const \w+ = (?:async )?\(', code))
        metrics["classes"] = len(re.findall(r'class \w+', code))
        metrics["comment_lines"] = sum(1 for l in lines if l.strip().startswith('//'))
        
        if "var " in code:
            issues.append("Usa `let` o `const` en lugar de `var`")
        
        if "== " in code and "=== " not in code:
            suggestions.append("Considera usar `===` en lugar de `==` para comparaciones estrictas")
        
        if "console.log" in code:
            suggestions.append("Recuerda eliminar `console.log` en producción")
        
        if "any" in code and ".ts" in code:
            issues.append("Evita usar `any` en TypeScript, define tipos específicos")
        
        return issues, suggestions, metrics
    
    def _analyze_generic(self, code: str, lines: List[str]) -> tuple:
        """Análisis genérico para cualquier lenguaje"""
        issues = []
        suggestions = []
        
        # Líneas muy largas
        long_lines = sum(1 for l in lines if len(l) > 120)
        if long_lines > 0:
            issues.append(f"{long_lines} líneas exceden 120 caracteres")
        
        # Espacios en blanco al final
        trailing = sum(1 for l in lines if l.endswith(' ') or l.endswith('\t'))
        if trailing > 0:
            suggestions.append(f"Elimina espacios en blanco al final de {trailing} líneas")
        
        return issues, suggestions


class ThinkDeeplyTool(BaseTool):
    """Herramienta de razonamiento profundo"""
    
    name = "think_deeply"
    description = "Activa un proceso de razonamiento estructurado para analizar un problema complejo"
    category = "analysis"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "problem": ToolParameter(
                name="problem",
                type="string",
                description="Descripción del problema a analizar",
                required=True
            ),
            "aspects": ToolParameter(
                name="aspects",
                type="array",
                description="Aspectos específicos a considerar",
                required=False
            ),
            "constraints": ToolParameter(
                name="constraints",
                type="array",
                description="Restricciones o limitaciones",
                required=False
            )
        }
    
    def execute(self, problem: str, aspects: List[str] = None, constraints: List[str] = None) -> str:
        result = f"""🧠 **Análisis Profundo**

═══════════════════════════════════════════════════════════════════════

📋 **Problema:**
{problem}

"""
        
        if constraints:
            result += "🚧 **Restricciones:**\n"
            for c in constraints:
                result += f"  • {c}\n"
            result += "\n"
        
        result += """🔍 **Marco de Análisis:**

1️⃣ **Comprensión del Problema:**
   - ¿Cuál es el objetivo principal?
   - ¿Cuáles son los inputs y outputs esperados?
   - ¿Qué casos edge existen?

2️⃣ **Descomposición:**
   - ¿Se puede dividir en subproblemas?
   - ¿Hay patrones reconocibles?
   - ¿Qué dependencias existen?

3️⃣ **Estrategias de Solución:**
   - Fuerza bruta (baseline)
   - Optimizaciones posibles
   - Algoritmos conocidos aplicables

4️⃣ **Evaluación:**
   - Complejidad temporal esperada
   - Complejidad espacial
   - Trade-offs

"""
        
        if aspects:
            result += "📌 **Aspectos Específicos a Considerar:**\n"
            for aspect in aspects:
                result += f"  • {aspect}\n"
        
        result += """
═══════════════════════════════════════════════════════════════════════

💡 **Recomendación:** Usa esta estructura para guiar tu razonamiento.
   Considera consultar múltiples perspectivas con `/heavy` para problemas complejos.
"""
        
        return result