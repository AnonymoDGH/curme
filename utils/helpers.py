"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         FUNCIONES AUXILIARES                                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from pathlib import Path
from typing import Optional
import re


def format_size(size_bytes: int) -> str:
    """Formatea tamaño de bytes a formato legible"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def get_file_icon(path: Path) -> str:
    """Retorna un emoji según el tipo de archivo"""
    if path.is_dir():
        return "📁"
    
    ext = path.suffix.lower()
    icons = {
        # Lenguajes de programación
        '.py': '🐍',
        '.js': '📜',
        '.ts': '📘',
        '.jsx': '⚛️',
        '.tsx': '⚛️',
        '.java': '☕',
        '.c': '©️',
        '.cpp': '➕',
        '.h': '📎',
        '.hpp': '📎',
        '.cs': '🎯',
        '.go': '🔵',
        '.rs': '🦀',
        '.rb': '💎',
        '.php': '🐘',
        '.swift': '🍎',
        '.kt': '🟣',
        '.scala': '🔴',
        '.r': '📊',
        '.lua': '🌙',
        '.pl': '🐪',
        '.sh': '⚡',
        '.bash': '⚡',
        '.zsh': '⚡',
        '.fish': '🐟',
        '.ps1': '💠',
        '.bat': '🦇',
        '.cmd': '🦇',
        
        # Web
        '.html': '🌐',
        '.htm': '🌐',
        '.css': '🎨',
        '.scss': '🎨',
        '.sass': '🎨',
        '.less': '🎨',
        '.vue': '💚',
        '.svelte': '🧡',
        
        # Data
        '.json': '📋',
        '.xml': '📰',
        '.yaml': '⚙️',
        '.yml': '⚙️',
        '.toml': '⚙️',
        '.ini': '⚙️',
        '.cfg': '⚙️',
        '.conf': '⚙️',
        '.env': '🔐',
        '.csv': '📊',
        '.tsv': '📊',
        
        # Documentos
        '.md': '📝',
        '.markdown': '📝',
        '.txt': '📄',
        '.rtf': '📄',
        '.pdf': '📕',
        '.doc': '📘',
        '.docx': '📘',
        '.xls': '📗',
        '.xlsx': '📗',
        '.ppt': '📙',
        '.pptx': '📙',
        
        # Imágenes
        '.jpg': '🖼️',
        '.jpeg': '🖼️',
        '.png': '🖼️',
        '.gif': '🖼️',
        '.bmp': '🖼️',
        '.svg': '🎨',
        '.ico': '🔷',
        '.webp': '🖼️',
        
        # Audio/Video
        '.mp3': '🎵',
        '.wav': '🎵',
        '.ogg': '🎵',
        '.mp4': '🎬',
        '.avi': '🎬',
        '.mkv': '🎬',
        '.mov': '🎬',
        
        # Archivos comprimidos
        '.zip': '📦',
        '.tar': '📦',
        '.gz': '📦',
        '.rar': '📦',
        '.7z': '📦',
        
        # Bases de datos
        '.sql': '🗃️',
        '.db': '🗄️',
        '.sqlite': '🗄️',
        '.sqlite3': '🗄️',
        
        # Otros
        '.log': '📋',
        '.lock': '🔒',
        '.gitignore': '🙈',
        '.dockerignore': '🐳',
        '.dockerfile': '🐳',
        '.exe': '⚙️',
        '.dll': '⚙️',
        '.so': '⚙️',
        '.dylib': '⚙️',
    }
    
    return icons.get(ext, '📄')


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Trunca una cadena si excede el máximo"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_code_blocks(text: str) -> list:
    """Extrae bloques de código de un texto markdown"""
    pattern = r'```(\w+)?\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    return [(lang or 'text', code.strip()) for lang, code in matches]


def clean_thinking_tags(text: str) -> str:
    """Elimina tags de pensamiento de una respuesta"""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()


def highlight_matches(text: str, query: str, color_start: str = '\033[43m', color_end: str = '\033[0m') -> str:
    """Resalta coincidencias en un texto"""
    if not query:
        return text
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f"{color_start}{m.group()}{color_end}", text)


def parse_key_value(text: str, separator: str = "=") -> dict:
    """Parsea texto en formato clave=valor"""
    result = {}
    for line in text.strip().split('\n'):
        if separator in line:
            key, value = line.split(separator, 1)
            result[key.strip()] = value.strip()
    return result


def slugify(text: str) -> str:
    """Convierte texto a slug (URL-friendly)"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')