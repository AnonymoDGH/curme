"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    HERRAMIENTAS DE BÚSQUEDA AVANZADA                           ║
║  Búsqueda semántica, regex en archivos, símbolos y duplicados                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import re
import ast
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict
from difflib import SequenceMatcher

from .base import BaseTool, ToolParameter


class SemanticSearchTool(BaseTool):
    """
    Búsqueda inteligente por significado, no solo texto exacto.
    
    Útil para:
    - Encontrar funciones relacionadas con un concepto
    - Buscar código que haga algo específico aunque use diferentes palabras
    - Encontrar patrones de implementación
    
    Usa análisis de código y palabras clave relacionadas.
    """
    
    name = "semantic_search"
    description = """Búsqueda inteligente por significado en código.

A diferencia de búsqueda de texto, entiende conceptos:
- "validar email" → encuentra validate_email, check_email, is_valid_email
- "conexión base de datos" → encuentra db_connect, get_connection, database_pool
- "manejo de errores" → encuentra try/except, error handlers, exceptions

Ejemplo: query="función que valida emails", directory="src/"
"""
    category = "search"
    
    # Diccionario de sinónimos/conceptos relacionados
    CONCEPTS = {
        "validar": ["validate", "check", "verify", "is_valid", "assert", "ensure"],
        "email": ["email", "mail", "correo", "e-mail", "address"],
        "usuario": ["user", "usuario", "account", "profile", "member"],
        "conectar": ["connect", "connection", "conn", "link", "join"],
        "base de datos": ["database", "db", "sql", "query", "orm", "model"],
        "error": ["error", "exception", "fail", "catch", "try", "except", "raise"],
        "archivo": ["file", "archivo", "path", "read", "write", "open", "save"],
        "api": ["api", "endpoint", "route", "request", "response", "rest", "http"],
        "autenticación": ["auth", "login", "password", "token", "session", "jwt"],
        "cache": ["cache", "memo", "store", "redis", "memory"],
        "log": ["log", "logger", "logging", "debug", "info", "warning", "error"],
        "test": ["test", "spec", "assert", "mock", "fixture", "pytest", "unittest"],
        "config": ["config", "settings", "env", "environment", "options"],
        "crear": ["create", "new", "add", "insert", "build", "make", "generate"],
        "eliminar": ["delete", "remove", "drop", "destroy", "clear", "purge"],
        "actualizar": ["update", "modify", "change", "edit", "patch", "set"],
        "obtener": ["get", "fetch", "retrieve", "find", "query", "select", "load"],
        "enviar": ["send", "emit", "publish", "dispatch", "notify", "post"],
        "recibir": ["receive", "listen", "subscribe", "handle", "consume"],
    }
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "query": ToolParameter(
                name="query",
                type="string",
                description="Descripción de lo que buscas (lenguaje natural)",
                required=True
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio donde buscar (default: actual)",
                required=False
            ),
            "file_pattern": ToolParameter(
                name="file_pattern",
                type="string",
                description="Patrón de archivos (default: *.py)",
                required=False
            ),
            "max_results": ToolParameter(
                name="max_results",
                type="integer",
                description="Máximo de resultados (default: 20)",
                required=False
            )
        }
    
    def execute(
        self,
        query: str = None,
        directory: str = ".",
        file_pattern: str = "*.py",
        max_results: int = 20,
        **kwargs
    ) -> str:
        query = query or kwargs.get('query', '')
        directory = directory or kwargs.get('directory', '.')
        file_pattern = file_pattern or kwargs.get('file_pattern', '*.py')
        max_results = max_results or kwargs.get('max_results', 20)
        
        if not query:
            return "❌ Se requiere 'query'"
        
        base_path = Path(directory)
        if not base_path.exists():
            return f"❌ Directorio no existe: {directory}"
        
        # Expandir query a términos de búsqueda
        search_terms = self._expand_query(query.lower())
        
        results = []
        files_searched = 0
        
        for file_path in base_path.rglob(file_pattern):
            if not file_path.is_file():
                continue
            
            files_searched += 1
            
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                matches = self._find_semantic_matches(content, search_terms, file_path)
                results.extend(matches)
            except Exception:
                continue
        
        if not results:
            return f"""🔍 **Sin resultados para:** "{query}"

Términos buscados: {', '.join(search_terms[:10])}
Archivos analizados: {files_searched}

💡 Intenta con términos más específicos o diferentes patrones de archivo.
"""
        
        # Ordenar por relevancia
        results.sort(key=lambda x: x['score'], reverse=True)
        results = results[:max_results]
        
        output = f"""🧠 **Búsqueda Semántica:** "{query}"

Términos expandidos: {', '.join(search_terms[:8])}...
Archivos analizados: {files_searched}
Resultados: {len(results)}

---

"""
        
        for i, result in enumerate(results, 1):
            score_bar = '█' * int(result['score'] * 10) + '░' * (10 - int(result['score'] * 10))
            output += f"""**{i}. {result['file']}:{result['line']}** [{score_bar}] {result['score']:.0%}
```{file_pattern.replace('*.', '')}
{result['context']}
```
Coincidencias: {', '.join(result['matches'][:5])}

"""
        
        return output
    
    def _expand_query(self, query: str) -> List[str]:
        """Expande la query a términos de búsqueda relacionados"""
        terms = set()
        words = re.findall(r'\w+', query)
        
        for word in words:
            terms.add(word)
            # Buscar sinónimos
            for concept, synonyms in self.CONCEPTS.items():
                if word in concept or any(word in s for s in synonyms):
                    terms.update(synonyms)
        
        return list(terms)
    
    def _find_semantic_matches(
        self,
        content: str,
        search_terms: List[str],
        file_path: Path
    ) -> List[Dict]:
        results = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            
            # Calcular score basado en coincidencias
            matches = []
            for term in search_terms:
                if term in line_lower:
                    matches.append(term)
            
            if matches:
                score = len(matches) / len(search_terms)
                
                # Bonus por definiciones de función/clase
                if re.match(r'\s*(def|class|async def)\s+', line):
                    score *= 1.5
                
                # Bonus por imports
                if 'import' in line_lower:
                    score *= 0.5  # Menor relevancia para imports
                
                score = min(score, 1.0)
                
                if score >= 0.1:  # Umbral mínimo
                    # Contexto: línea actual y una antes/después
                    start = max(0, line_num - 2)
                    end = min(len(lines), line_num + 2)
                    context = '\n'.join(lines[start:end])
                    
                    results.append({
                        'file': str(file_path),
                        'line': line_num,
                        'context': context[:300],
                        'matches': matches,
                        'score': score
                    })
        
        return results


class RegexSearchInFilesTool(BaseTool):
    """
    Búsqueda con expresiones regulares en múltiples archivos.
    
    Útil para:
    - Encontrar patrones complejos en código
    - Buscar números de teléfono, emails, IPs
    - Encontrar TODO/FIXME con formato específico
    - Validar formatos de datos
    """
    
    name = "regex_search_files"
    description = """Busca patrones regex en múltiples archivos.

Muestra coincidencias con contexto y número de línea.

Ejemplos:
- Buscar TODOs: pattern=r'TODO:?\s*(.+)'
- Buscar emails: pattern=r'[\w.-]+@[\w.-]+\.\w+'
- Buscar IPs: pattern=r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
- Buscar prints debug: pattern=r'print\(.*(debug|test).*\)'

Flags disponibles: i=ignorecase, m=multiline, s=dotall
"""
    category = "search"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "pattern": ToolParameter(
                name="pattern",
                type="string",
                description="Patrón de expresión regular",
                required=True
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio donde buscar",
                required=False
            ),
            "file_pattern": ToolParameter(
                name="file_pattern",
                type="string",
                description="Patrón de archivos (ej: *.py, *.js)",
                required=False
            ),
            "flags": ToolParameter(
                name="flags",
                type="string",
                description="Flags regex: i=ignorecase, m=multiline, s=dotall",
                required=False
            ),
            "context_lines": ToolParameter(
                name="context_lines",
                type="integer",
                description="Líneas de contexto alrededor de cada match",
                required=False
            ),
            "max_results": ToolParameter(
                name="max_results",
                type="integer",
                description="Máximo de resultados",
                required=False
            )
        }
    
    def execute(
        self,
        pattern: str = None,
        directory: str = ".",
        file_pattern: str = "*",
        flags: str = "",
        context_lines: int = 1,
        max_results: int = 50,
        **kwargs
    ) -> str:
        pattern = pattern or kwargs.get('pattern', '')
        directory = directory or kwargs.get('directory', '.')
        file_pattern = file_pattern or kwargs.get('file_pattern', '*')
        flags = flags or kwargs.get('flags', '')
        context_lines = context_lines or kwargs.get('context_lines', 1)
        max_results = max_results or kwargs.get('max_results', 50)
        
        if not pattern:
            return "❌ Se requiere 'pattern'"
        
        # Parsear flags
        re_flags = 0
        if 'i' in flags.lower():
            re_flags |= re.IGNORECASE
        if 'm' in flags.lower():
            re_flags |= re.MULTILINE
        if 's' in flags.lower():
            re_flags |= re.DOTALL
        
        try:
            regex = re.compile(pattern, re_flags)
        except re.error as e:
            return f"❌ Regex inválido: {e}"
        
        base_path = Path(directory)
        if not base_path.exists():
            return f"❌ Directorio no existe: {directory}"
        
        results = []
        files_with_matches = set()
        total_matches = 0
        
        for file_path in base_path.rglob(file_pattern):
            if not file_path.is_file():
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')
                
                for line_num, line in enumerate(lines, 1):
                    for match in regex.finditer(line):
                        total_matches += 1
                        files_with_matches.add(str(file_path))
                        
                        if len(results) < max_results:
                            # Obtener contexto
                            start = max(0, line_num - context_lines - 1)
                            end = min(len(lines), line_num + context_lines)
                            context = lines[start:end]
                            
                            results.append({
                                'file': str(file_path),
                                'line': line_num,
                                'match': match.group(),
                                'groups': match.groups() if match.groups() else None,
                                'context': context,
                                'context_start': start + 1
                            })
            except Exception:
                continue
        
        if not results:
            return f"""🔍 **Sin coincidencias para:** `{pattern}`

Patrón: `{pattern}`
Directorio: {directory}
Archivos: {file_pattern}
"""
        
        output = f"""🔍 **Búsqueda Regex**

Patrón: `{pattern}`
Coincidencias: {total_matches} en {len(files_with_matches)} archivos
Mostrando: {len(results)} resultados

---

"""
        
        for result in results:
            output += f"**{result['file']}:{result['line']}**\n"
            output += f"Match: `{result['match'][:80]}`"
            if result['groups']:
                output += f" | Grupos: {result['groups']}"
            output += "\n```\n"
            
            for i, ctx_line in enumerate(result['context']):
                line_num = result['context_start'] + i
                marker = "→ " if line_num == result['line'] else "  "
                output += f"{line_num:4}{marker}{ctx_line}\n"
            
            output += "```\n\n"
        
        if total_matches > max_results:
            output += f"\n⚠️ Mostrando {max_results} de {total_matches} coincidencias"
        
        return output


class CodeSymbolSearchTool(BaseTool):
    """
    Busca símbolos de código: funciones, clases, variables, imports.
    
    Útil para:
    - Encontrar dónde se define una función
    - Ver todos los usos de una clase
    - Encontrar imports de un módulo
    - Navegar código desconocido
    """
    
    name = "search_symbol"
    description = """Busca definiciones y usos de símbolos de código.

Tipos de símbolos:
- function: Definiciones de funciones (def, async def)
- class: Definiciones de clases
- variable: Asignaciones de variables
- import: Imports del símbolo
- all: Buscar en todos los tipos

Ejemplo: name="UserModel", type="class"
Ejemplo: name="get_user", type="function"
"""
    category = "search"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "name": ToolParameter(
                name="name",
                type="string",
                description="Nombre del símbolo a buscar",
                required=True
            ),
            "symbol_type": ToolParameter(
                name="symbol_type",
                type="string",
                description="Tipo: function, class, variable, import, all",
                required=False,
                enum=["function", "class", "variable", "import", "all"]
            ),
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio donde buscar",
                required=False
            ),
            "include_usages": ToolParameter(
                name="include_usages",
                type="boolean",
                description="Incluir usos además de definiciones",
                required=False
            )
        }
    
    def execute(
        self,
        name: str = None,
        symbol_type: str = "all",
        directory: str = ".",
        include_usages: bool = True,
        **kwargs
    ) -> str:
        name = name or kwargs.get('name', '')
        symbol_type = symbol_type or kwargs.get('symbol_type', 'all')
        directory = directory or kwargs.get('directory', '.')
        include_usages = include_usages if include_usages is not None else kwargs.get('include_usages', True)
        
        if not name:
            return "❌ Se requiere 'name'"
        
        base_path = Path(directory)
        if not base_path.exists():
            return f"❌ Directorio no existe: {directory}"
        
        definitions = []
        usages = []
        imports = []
        
        for file_path in base_path.rglob("*.py"):
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')
                
                for line_num, line in enumerate(lines, 1):
                    stripped = line.strip()
                    
                    # Definiciones de función
                    if symbol_type in ['function', 'all']:
                        if re.match(rf'(async\s+)?def\s+{re.escape(name)}\s*\(', stripped):
                            definitions.append({
                                'file': str(file_path),
                                'line': line_num,
                                'type': 'function',
                                'code': stripped[:100]
                            })
                    
                    # Definiciones de clase
                    if symbol_type in ['class', 'all']:
                        if re.match(rf'class\s+{re.escape(name)}\s*[:\(]', stripped):
                            definitions.append({
                                'file': str(file_path),
                                'line': line_num,
                                'type': 'class',
                                'code': stripped[:100]
                            })
                    
                    # Asignaciones de variable
                    if symbol_type in ['variable', 'all']:
                        if re.match(rf'^{re.escape(name)}\s*=', stripped):
                            definitions.append({
                                'file': str(file_path),
                                'line': line_num,
                                'type': 'variable',
                                'code': stripped[:100]
                            })
                    
                    # Imports
                    if symbol_type in ['import', 'all']:
                        if f'import {name}' in stripped or f'from' in stripped and name in stripped:
                            imports.append({
                                'file': str(file_path),
                                'line': line_num,
                                'code': stripped[:100]
                            })
                    
                    # Usos
                    if include_usages and name in line:
                        # Evitar contar definiciones como usos
                        is_definition = any(
                            d['file'] == str(file_path) and d['line'] == line_num
                            for d in definitions
                        )
                        is_import = any(
                            i['file'] == str(file_path) and i['line'] == line_num
                            for i in imports
                        )
                        
                        if not is_definition and not is_import:
                            usages.append({
                                'file': str(file_path),
                                'line': line_num,
                                'code': stripped[:100]
                            })
            except Exception:
                continue
        
        # Construir output
        output = f"""🔍 **Símbolo: `{name}`**

"""
        
        if definitions:
            output += f"**📝 Definiciones ({len(definitions)}):**\n\n"
            for d in definitions[:10]:
                output += f"  {d['type']:10} {d['file']}:{d['line']}\n"
                output += f"             `{d['code']}`\n\n"
        else:
            output += "**📝 Definiciones:** Ninguna encontrada\n\n"
        
        if imports:
            output += f"**📦 Imports ({len(imports)}):**\n\n"
            for i in imports[:10]:
                output += f"  {i['file']}:{i['line']}\n"
                output += f"  `{i['code']}`\n\n"
        
        if include_usages and usages:
            output += f"**🔗 Usos ({len(usages)}):**\n\n"
            for u in usages[:15]:
                output += f"  {u['file']}:{u['line']}: `{u['code'][:60]}...`\n"
        
        if not definitions and not imports and not usages:
            output += "❌ No se encontró el símbolo en ningún archivo\n"
        
        return output


class DuplicateCodeFinderTool(BaseTool):
    """
    Detecta código duplicado o muy similar entre archivos.
    
    Útil para:
    - Identificar código que debería ser refactorizado
    - Encontrar copy-paste accidental
    - Reducir deuda técnica
    - Preparar refactorizaciones
    """
    
    name = "find_duplicates"
    description = """Detecta código duplicado o similar entre archivos.

Encuentra:
- Bloques de código idénticos
- Código muy similar (configurable por umbral)
- Funciones duplicadas

Ejemplo: threshold=0.8 → Detecta código con 80%+ similitud
Útil para identificar código que necesita refactoring.
"""
    category = "analysis"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "directory": ToolParameter(
                name="directory",
                type="string",
                description="Directorio a analizar",
                required=False
            ),
            "file_pattern": ToolParameter(
                name="file_pattern",
                type="string",
                description="Patrón de archivos (default: *.py)",
                required=False
            ),
            "threshold": ToolParameter(
                name="threshold",
                type="number",
                description="Umbral de similitud 0.0-1.0 (default: 0.8)",
                required=False
            ),
            "min_lines": ToolParameter(
                name="min_lines",
                type="integer",
                description="Mínimo de líneas para considerar duplicado (default: 5)",
                required=False
            )
        }
    
    def execute(
        self,
        directory: str = ".",
        file_pattern: str = "*.py",
        threshold: float = 0.8,
        min_lines: int = 5,
        **kwargs
    ) -> str:
        directory = directory or kwargs.get('directory', '.')
        file_pattern = file_pattern or kwargs.get('file_pattern', '*.py')
        threshold = threshold or kwargs.get('threshold', 0.8)
        min_lines = min_lines or kwargs.get('min_lines', 5)
        
        base_path = Path(directory)
        if not base_path.exists():
            return f"❌ Directorio no existe: {directory}"
        
        # Extraer bloques de código de todos los archivos
        blocks = []
        
        for file_path in base_path.rglob(file_pattern):
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                file_blocks = self._extract_blocks(content, str(file_path), min_lines)
                blocks.extend(file_blocks)
            except Exception:
                continue
        
        if not blocks:
            return f"📂 No se encontraron bloques de código en {directory}"
        
        # Encontrar duplicados
        duplicates = self._find_similar_blocks(blocks, threshold)
        
        if not duplicates:
            return f"""✅ **No se encontraron duplicados significativos**

Archivos analizados: {len(list(base_path.rglob(file_pattern)))}
Bloques de código: {len(blocks)}
Umbral de similitud: {threshold*100:.0f}%
"""
        
        output = f"""🔍 **Análisis de Código Duplicado**

Umbral: {threshold*100:.0f}% similitud
Duplicados encontrados: {len(duplicates)}

---

"""
        
        for i, dup in enumerate(duplicates[:10], 1):
            output += f"""**Duplicado #{i}** - {dup['similarity']*100:.0f}% similitud

📄 **Ubicación 1:** `{dup['file1']}` (líneas {dup['start1']}-{dup['end1']})
📄 **Ubicación 2:** `{dup['file2']}` (líneas {dup['start2']}-{dup['end2']})

```python
{dup['preview'][:300]}{'...' if len(dup['preview']) > 300 else ''}
```

---

"""
        
        if len(duplicates) > 10:
            output += f"\n⚠️ Mostrando 10 de {len(duplicates)} duplicados encontrados"
        
        # Estadísticas
        total_dup_lines = sum(d['end1'] - d['start1'] + 1 for d in duplicates)
        output += f"""

📊 **Resumen:**
- Grupos de duplicados: {len(duplicates)}
- Líneas duplicadas aprox: {total_dup_lines}
- 💡 Considera extraer el código común a funciones/módulos compartidos
"""
        
        return output
    
    def _extract_blocks(self, content: str, file_path: str, min_lines: int) -> List[Dict]:
        """Extrae bloques de código significativos"""
        blocks = []
        lines = content.split('\n')
        
        # Extraer funciones y clases
        current_block = []
        current_start = 0
        in_block = False
        indent_level = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if re.match(r'(def|class|async def)\s+\w+', stripped):
                if current_block and len(current_block) >= min_lines:
                    blocks.append({
                        'file': file_path,
                        'start': current_start,
                        'end': i,
                        'content': '\n'.join(current_block),
                        'normalized': self._normalize_code('\n'.join(current_block))
                    })
                
                current_block = [line]
                current_start = i + 1
                in_block = True
                # Calcular indentación esperada
                indent_level = len(line) - len(line.lstrip())
            elif in_block:
                if stripped and not stripped.startswith('#'):
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent <= indent_level and stripped:
                        # Fin del bloque
                        if len(current_block) >= min_lines:
                            blocks.append({
                                'file': file_path,
                                'start': current_start,
                                'end': i,
                                'content': '\n'.join(current_block),
                                'normalized': self._normalize_code('\n'.join(current_block))
                            })
                        current_block = []
                        in_block = False
                    else:
                        current_block.append(line)
                else:
                    current_block.append(line)
        
        # Último bloque
        if current_block and len(current_block) >= min_lines:
            blocks.append({
                'file': file_path,
                'start': current_start,
                'end': len(lines),
                'content': '\n'.join(current_block),
                'normalized': self._normalize_code('\n'.join(current_block))
            })
        
        return blocks
    
    def _normalize_code(self, code: str) -> str:
        """Normaliza código para comparación (elimina nombres variables, espacios extra)"""
        # Eliminar comentarios
        code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        # Normalizar strings
        code = re.sub(r'["\'][^"\']*["\']', '""', code)
        # Normalizar números
        code = re.sub(r'\b\d+\b', '0', code)
        # Eliminar espacios extra
        code = re.sub(r'\s+', ' ', code)
        return code.strip().lower()
    
    def _find_similar_blocks(self, blocks: List[Dict], threshold: float) -> List[Dict]:
        """Encuentra bloques similares"""
        duplicates = []
        seen = set()
        
        for i, block1 in enumerate(blocks):
            for j, block2 in enumerate(blocks[i+1:], i+1):
                # Evitar comparar mismo archivo y mismas líneas
                if block1['file'] == block2['file']:
                    if abs(block1['start'] - block2['start']) < 5:
                        continue
                
                key = (block1['file'], block1['start'], block2['file'], block2['start'])
                if key in seen:
                    continue
                
                similarity = SequenceMatcher(
                    None,
                    block1['normalized'],
                    block2['normalized']
                ).ratio()
                
                if similarity >= threshold:
                    seen.add(key)
                    duplicates.append({
                        'file1': block1['file'],
                        'start1': block1['start'],
                        'end1': block1['end'],
                        'file2': block2['file'],
                        'start2': block2['start'],
                        'end2': block2['end'],
                        'similarity': similarity,
                        'preview': block1['content']
                    })
        
        # Ordenar por similitud
        duplicates.sort(key=lambda x: x['similarity'], reverse=True)
        return duplicates