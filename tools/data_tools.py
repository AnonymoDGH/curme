# tools/data_tools.py
"""NVIDIA CODE - Herramientas de Datos"""

import json
import csv
import re
from typing import Dict, List
from pathlib import Path
from .base import BaseTool, ToolParameter


class JsonProcessTool(BaseTool):
    """Procesa archivos JSON"""
    
    name = "json_process"
    description = "Lee, valida, formatea o extrae datos de JSON"
    category = "data"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(name="action", type="string", description="read, validate, format, query", required=True, enum=["read", "validate", "format", "query"]),
            "input": ToolParameter(name="input", type="string", description="Archivo o JSON string", required=True),
            "query": ToolParameter(name="query", type="string", description="JSONPath query (para action=query)", required=False)
        }
    
    def execute(self, action: str = None, input: str = None, query: str = None, **kwargs) -> str:
        action = action or kwargs.get('action', 'read')
        input_data = input or kwargs.get('input', '')
        
        if not input_data:
            return "[x] Se requiere 'input'"
        
        # Cargar JSON
        try:
            if Path(input_data).exists():
                data = json.loads(Path(input_data).read_text())
            else:
                data = json.loads(input_data)
        except json.JSONDecodeError as e:
            return f"[x] JSON inválido: {e}"
        except Exception as e:
            return f"[x] Error: {e}"
        
        if action == "validate":
            return "✅ JSON válido"
        elif action == "format":
            return f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"
        elif action == "read":
            preview = json.dumps(data, indent=2, ensure_ascii=False)
            if len(preview) > 2000:
                preview = preview[:2000] + "\n... (truncado)"
            return f"📋 JSON:\n```json\n{preview}\n```"
        elif action == "query" and query:
            # Query simple por keys
            keys = query.split('.')
            result = data
            for k in keys:
                if isinstance(result, dict) and k in result:
                    result = result[k]
                elif isinstance(result, list) and k.isdigit():
                    result = result[int(k)]
                else:
                    return f"[x] Key no encontrada: {k}"
            return f"📋 Resultado: {json.dumps(result, indent=2, ensure_ascii=False)}"
        
        return "[x] Acción no válida"


class CsvProcessTool(BaseTool):
    """Procesa archivos CSV"""
    
    name = "csv_process"
    description = "Lee y analiza archivos CSV"
    category = "data"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "file": ToolParameter(name="file", type="string", description="Archivo CSV", required=True),
            "action": ToolParameter(name="action", type="string", description="read, stats, head", required=False, enum=["read", "stats", "head"])
        }
    
    def execute(self, file: str = None, action: str = "head", **kwargs) -> str:
        file = file or kwargs.get('file', '')
        action = action or kwargs.get('action', 'head')
        
        if not file or not Path(file).exists():
            return f"[x] Archivo no encontrado: {file}"
        
        try:
            with open(file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            if action == "stats":
                return f"""📊 **CSV Stats: {file}**
- Filas: {len(rows)}
- Columnas: {len(rows[0].keys()) if rows else 0}
- Headers: {', '.join(rows[0].keys()) if rows else 'N/A'}"""
            
            elif action == "head":
                output = f"📋 **{file}** (primeras 10 filas)\n\n"
                headers = list(rows[0].keys()) if rows else []
                output += " | ".join(headers) + "\n"
                output += "-|-".join(["-" * len(h) for h in headers]) + "\n"
                for row in rows[:10]:
                    output += " | ".join([str(row.get(h, ''))[:20] for h in headers]) + "\n"
                return output
            
            else:
                return f"📋 CSV con {len(rows)} filas"
                
        except Exception as e:
            return f"[x] Error: {e}"


class RegexTool(BaseTool):
    """Operaciones con expresiones regulares"""
    
    name = "regex"
    description = "Busca, extrae o reemplaza usando regex"
    category = "data"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "pattern": ToolParameter(name="pattern", type="string", description="Patrón regex", required=True),
            "text": ToolParameter(name="text", type="string", description="Texto a procesar", required=True),
            "action": ToolParameter(name="action", type="string", description="find, replace, split", required=False, enum=["find", "replace", "split"]),
            "replacement": ToolParameter(name="replacement", type="string", description="Texto de reemplazo", required=False)
        }
    
    def execute(self, pattern: str = None, text: str = None, action: str = "find", replacement: str = "", **kwargs) -> str:
        pattern = pattern or kwargs.get('pattern', '')
        text = text or kwargs.get('text', '')
        action = action or kwargs.get('action', 'find')
        replacement = replacement or kwargs.get('replacement', '')
        
        if not pattern or not text:
            return "[x] Se requiere 'pattern' y 'text'"
        
        try:
            if action == "find":
                matches = re.findall(pattern, text)
                if matches:
                    return f"🔍 **{len(matches)} coincidencias:**\n" + "\n".join([f"  • {m}" for m in matches[:20]])
                return "🔍 Sin coincidencias"
            
            elif action == "replace":
                result = re.sub(pattern, replacement, text)
                return f"✅ Resultado:\n{result[:1000]}"
            
            elif action == "split":
                parts = re.split(pattern, text)
                return f"📋 **{len(parts)} partes:**\n" + "\n".join([f"  {i}: {p[:50]}" for i, p in enumerate(parts[:10])])
            
        except re.error as e:
            return f"[x] Regex inválido: {e}"


class TextTransformTool(BaseTool):
    """Transforma texto"""
    
    name = "text_transform"
    description = "Transforma texto (upper, lower, title, reverse, etc.)"
    category = "data"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "text": ToolParameter(name="text", type="string", description="Texto a transformar", required=True),
            "transform": ToolParameter(name="transform", type="string", description="Transformación", required=True, enum=["upper", "lower", "title", "reverse", "strip", "slug"])
        }
    
    def execute(self, text: str = None, transform: str = None, **kwargs) -> str:
        text = text or kwargs.get('text', '')
        transform = transform or kwargs.get('transform', '')
        
        if not text:
            return "[x] Se requiere 'text'"
        
        transforms = {
            "upper": text.upper(),
            "lower": text.lower(),
            "title": text.title(),
            "reverse": text[::-1],
            "strip": text.strip(),
            "slug": re.sub(r'[^\w\s-]', '', text.lower()).replace(' ', '-')
        }
        
        result = transforms.get(transform, text)
        return f"✅ {transform}: {result}"