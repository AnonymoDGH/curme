import json
import time
import re
from typing import (
    Dict, List, Optional, Tuple
)

# ============================================================================
# TOOL CALL PARSER - Parsea <toolcall> tags del modelo
# ============================================================================

class ToolCallParser:
    """Parsea tool calls desde diferentes formatos de salida del modelo"""

    # Patrones para detectar tool calls en texto
    TOOLCALL_PATTERNS = [
        # <toolcall>function_name\narg1: value1\narg2: value2</toolcall>
        re.compile(
            r'<toolcall>\s*(\w+)\s*(?:[-–]\s*)?(.+?)</toolcall>',
            re.DOTALL | re.IGNORECASE
        ),
        # <tool_call>{"name": "func", "arguments": {...}}</tool_call>
        re.compile(
            r'<tool_call>\s*(\{.+?\})\s*</tool_call>',
            re.DOTALL | re.IGNORECASE
        ),
        # ```tool_call\n{"name": "func", "arguments": {...}}\n```
        re.compile(
            r'```tool_call\s*\n\s*(\{.+?\})\s*\n\s*```',
            re.DOTALL | re.IGNORECASE
        ),
        # Inline: function_name(arg1="value1", arg2="value2")
        re.compile(
            r'(?:call|execute|run|usar|ejecutar):\s*(\w+)\((.+?)\)',
            re.DOTALL | re.IGNORECASE
        ),
    ]

    # Patrón para detectar MCP-style tool calls
    MCP_PATTERN = re.compile(
        r'<toolcall>\s*(\w+)\s*[-–]?\s*(.*?)</toolcall>',
        re.DOTALL | re.IGNORECASE
    )

    # Patrón para detectar múltiples toolcalls incluyendo texto entre ellos
    MULTI_TOOLCALL_PATTERN = re.compile(
        r'<toolcall>(.*?)</toolcall>',
        re.DOTALL | re.IGNORECASE
    )

    @classmethod
    def parse_from_text(cls, text: str) -> Tuple[str, List[Dict]]:
        """
        Extrae tool calls del texto del modelo.
        Retorna (texto_limpio, lista_de_tool_calls)
        """
        if not text:
            return text, []

        tool_calls = []
        clean_text = text

        # 1. Buscar <toolcall> tags (formato más común en modelos GLM/etc)
        matches = list(cls.MULTI_TOOLCALL_PATTERN.finditer(text))
        if matches:
            for i, match in enumerate(matches):
                raw_content = match.group(1).strip()
                parsed = cls._parse_single_toolcall(raw_content, i)
                if parsed:
                    tool_calls.append(parsed)

            # Limpiar texto removiendo los toolcall tags y texto intermedio de razonamiento
            clean_text = cls.MULTI_TOOLCALL_PATTERN.sub('', clean_text)
            # También limpiar texto de razonamiento que suele preceder los toolcalls
            clean_text = cls._clean_reasoning_text(clean_text)

        # 2. Si no encontramos <toolcall>, buscar otros formatos
        if not tool_calls:
            for pattern in cls.TOOLCALL_PATTERNS[1:]:  # Skip first, already checked
                matches = list(pattern.finditer(text))
                for i, match in enumerate(matches):
                    try:
                        raw = match.group(1)
                        if raw.startswith('{'):
                            data = json.loads(raw)
                            tool_calls.append({
                                'id': f'call_{int(time.time())}_{i}',
                                'type': 'function',
                                'function': {
                                    'name': data.get('name', 'unknown'),
                                    'arguments': json.dumps(
                                        data.get('arguments', data.get('params', {}))
                                    )
                                }
                            })
                        clean_text = pattern.sub('', clean_text)
                    except (json.JSONDecodeError, IndexError):
                        continue

        clean_text = clean_text.strip()

        # Si solo quedó texto vacío o de razonamiento, usar un placeholder
        if tool_calls and not clean_text:
            clean_text = ""

        return clean_text, tool_calls

    @classmethod
    def _parse_single_toolcall(cls, raw: str, index: int = 0) -> Optional[Dict]:
        """Parsea un solo toolcall desde su contenido raw"""
        if not raw:
            return None

        # Intentar como JSON primero
        try:
            data = json.loads(raw)
            return {
                'id': f'call_{int(time.time())}_{index}',
                'type': 'function',
                'function': {
                    'name': data.get('name', 'unknown'),
                    'arguments': json.dumps(
                        data.get('arguments', data.get('params', {}))
                    )
                }
            }
        except json.JSONDecodeError:
            pass

        # Parsear formato: function_name - descripción\nparam: value
        # o: function_name\nparam: value
        lines = raw.strip().split('\n')
        if not lines:
            return None

        first_line = lines[0].strip()

        # Extraer nombre de función
        func_match = re.match(
            r'(\w+)\s*(?:[-–:]\s*(.*))?$',
            first_line
        )
        if not func_match:
            return None

        func_name = func_match.group(1).strip()
        description = func_match.group(2) or ""

        # Extraer argumentos de las líneas siguientes
        arguments = {}
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            # Buscar "key: value" o "key = value"
            param_match = re.match(
                r'(\w+)\s*[:=]\s*(.+)',
                line
            )
            if param_match:
                key = param_match.group(1).strip()
                value = param_match.group(2).strip()

                # Intentar parsear el valor
                # Quitar comillas si las tiene
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]

                arguments[key] = value

        # Si no se encontraron argumentos explícitos, intentar extraerlos de la descripción
        if not arguments and description:
            desc_params = re.findall(
                r'(\w+):\s*(\S+)',
                description
            )
            for key, value in desc_params:
                if key.lower() not in (
                    'parámetros', 'parameters', 'params', 'llamar',
                    'necesito', 'obtener', 'esta', 'con', 'del', 'la',
                    'el', 'los', 'las', 'un', 'una', 'de', 'a', 'en',
                    'que', 'es', 'se', 'no', 'si', 'por', 'para',
                    'función', 'function'
                ):
                    arguments[key] = value

        # Buscar también <argvalue> tags
        argvalue_matches = re.findall(
            r'<argvalue>\s*(.+?)\s*</argvalue>',
            raw,
            re.DOTALL
        )
        if argvalue_matches:
            for av in argvalue_matches:
                av_params = re.findall(r'(\w+)\s*[:=]\s*(\S+)', av)
                for key, value in av_params:
                    arguments[key] = value

        return {
            'id': f'call_{int(time.time())}_{index}',
            'type': 'function',
            'function': {
                'name': func_name,
                'arguments': json.dumps(arguments) if arguments else '{}'
            }
        }

    @classmethod
    def _clean_reasoning_text(cls, text: str) -> str:
        """Limpia texto de razonamiento interno del modelo"""
        lines = text.split('\n')
        cleaned = []
        skip_patterns = [
            r'^\s*(?:revisar|necesito|llamar|voy a|debo|tengo que)\s',
            r'^\s*(?:Parámetros|Parameters|Args)\s*:',
            r'^\s*[-–]\s*(?:Llamar|Call|Execute|Ejecutar)',
            r'^\s*</?(?:think|reasoning|thought)>',
        ]

        for line in lines:
            should_skip = False
            for pattern in skip_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    should_skip = True
                    break
            if not should_skip:
                cleaned.append(line)

        result = '\n'.join(cleaned).strip()

        # Remover bloques de thinking/reasoning
        result = re.sub(
            r'<think>.*?</think>',
            '', result, flags=re.DOTALL | re.IGNORECASE
        )
        result = re.sub(
            r'<reasoning>.*?</reasoning>',
            '', result, flags=re.DOTALL | re.IGNORECASE
        )

        return result.strip()

    @classmethod
    def has_tool_calls(cls, text: str) -> bool:
        """Verifica rápidamente si el texto contiene tool calls"""
        if not text:
            return False
        return bool(cls.MULTI_TOOLCALL_PATTERN.search(text)) or \
               any(p.search(text) for p in cls.TOOLCALL_PATTERNS[1:])

    @classmethod
    def strip_tool_calls(cls, text: str) -> str:
        """Remueve tool calls del texto, dejando solo contenido limpio"""
        clean, _ = cls.parse_from_text(text)
        return clean


# ============================================================================
# RESPONSE SANITIZER
# ============================================================================

class ResponseSanitizer:
    """Limpia y sanitiza respuestas del modelo antes de mostrarlas"""

    INTERNAL_TAGS = [
        (re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE), ''),
        (re.compile(r'<thinking>.*?</thinking>', re.DOTALL | re.IGNORECASE), ''),
        (re.compile(r'<reasoning>.*?</reasoning>', re.DOTALL | re.IGNORECASE), ''),
        (re.compile(r'<internal>.*?</internal>', re.DOTALL | re.IGNORECASE), ''),
        (re.compile(r'<toolcall>.*?</toolcall>', re.DOTALL | re.IGNORECASE), ''),
        (re.compile(r'<argvalue>.*?</argvalue>', re.DOTALL | re.IGNORECASE), ''),
        (re.compile(r'<tool_call>.*?</tool_call>', re.DOTALL | re.IGNORECASE), ''),
    ]

    @classmethod
    def sanitize(cls, text: str) -> str:
        """Sanitiza texto de respuesta para mostrar al usuario"""
        if not text:
            return text

        result = text

        # Remover tags internos
        for pattern, replacement in cls.INTERNAL_TAGS:
            result = pattern.sub(replacement, result)

        # Limpiar líneas vacías excesivas
        result = re.sub(r'\n{4,}', '\n\n\n', result)

        # Limpiar espacios al inicio/final
        result = result.strip()

        return result

    @classmethod
    def extract_thinking(cls, text: str) -> Tuple[str, Optional[str]]:
        """
        Extrae el contenido de thinking y retorna (texto_limpio, thinking_content)
        """
        thinking = None

        think_match = re.search(
            r'<think(?:ing)?>(.*?)</think(?:ing)?>',
            text, re.DOTALL | re.IGNORECASE
        )
        if think_match:
            thinking = think_match.group(1).strip()

        clean = cls.sanitize(text)
        return clean, thinking
