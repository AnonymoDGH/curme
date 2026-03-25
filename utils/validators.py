"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         VALIDADORES                                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from pathlib import Path
from typing import Tuple, Optional
import re

from config import BLOCKED_COMMANDS, ALLOWED_EXTENSIONS


def validate_path(path: str, must_exist: bool = False, allow_absolute: bool = True) -> Tuple[bool, str]:
    """
    Valida una ruta de archivo
    
    Returns:
        Tuple de (es_válido, mensaje_error)
    """
    if not path:
        return False, "La ruta no puede estar vacía"
    
    try:
        p = Path(path)
        
        # Verificar path traversal
        if '..' in path:
            resolved = p.resolve()
            # Permitir si no sale del directorio actual
            try:
                resolved.relative_to(Path.cwd())
            except ValueError:
                return False, "Path traversal no permitido fuera del directorio de trabajo"
        
        # Verificar si debe existir
        if must_exist and not p.exists():
            return False, f"El archivo no existe: {path}"
        
        # Verificar rutas absolutas
        if not allow_absolute and p.is_absolute():
            return False, "No se permiten rutas absolutas"
        
        return True, ""
        
    except Exception as e:
        return False, f"Ruta inválida: {str(e)}"


def validate_command(command: str) -> Tuple[bool, str]:
    """
    Valida un comando de terminal
    
    Returns:
        Tuple de (es_válido, mensaje_error)
    """
    if not command:
        return False, "El comando no puede estar vacío"
    
    command_lower = command.lower()
    
    # Verificar comandos bloqueados
    for blocked in BLOCKED_COMMANDS:
        if blocked.lower() in command_lower:
            return False, f"Comando bloqueado por seguridad: contiene '{blocked}'"
    
    # Verificar patrones peligrosos
    dangerous_patterns = [
        r'>\s*/dev/sd[a-z]',  # Escribir directamente a disco
        r'chmod\s+777\s+/',   # Permisos inseguros en raíz
        r'curl.*\|\s*bash',   # Pipe de curl a bash
        r'wget.*\|\s*sh',     # Pipe de wget a sh
        r':\(\)\s*{\s*:\|:&\s*};:',  # Fork bomb
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return False, "Patrón de comando potencialmente peligroso detectado"
    
    return True, ""


def is_safe_command(command: str) -> bool:
    """Verifica si un comando es seguro (versión simple)"""
    valid, _ = validate_command(command)
    return valid


def validate_file_extension(path: str, allowed: list = None) -> Tuple[bool, str]:
    """
    Valida la extensión de un archivo
    
    Returns:
        Tuple de (es_válido, mensaje_error)
    """
    allowed = allowed or ALLOWED_EXTENSIONS
    
    p = Path(path)
    ext = p.suffix.lower()
    
    if not ext:
        return True, ""  # Sin extensión está permitido
    
    if ext in allowed:
        return True, ""
    
    return False, f"Extensión no permitida: {ext}"


def validate_json(text: str) -> Tuple[bool, Optional[dict], str]:
    """
    Valida que un texto sea JSON válido
    
    Returns:
        Tuple de (es_válido, datos_parseados, mensaje_error)
    """
    import json
    
    try:
        data = json.loads(text)
        return True, data, ""
    except json.JSONDecodeError as e:
        return False, None, f"JSON inválido: {str(e)}"


def validate_model_key(key: str, available_models: dict) -> Tuple[bool, str]:
    """
    Valida una clave de modelo
    
    Returns:
        Tuple de (es_válido, mensaje_error)
    """
    if key in available_models:
        return True, ""
    
    # Buscar por ID
    for model in available_models.values():
        if hasattr(model, 'id') and model.id == key:
            return True, ""
    
    return False, f"Modelo no encontrado: {key}"