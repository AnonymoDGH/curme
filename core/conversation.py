"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         GESTOR DE CONVERSACIONES                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict

from config import SESSIONS_DIR


@dataclass
class Message:
    """Representa un mensaje en la conversación"""
    role: str  # user, assistant, system, tool
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # Para mensajes de herramientas
    
    def to_api_format(self) -> Dict:
        """Convierte a formato de API"""
        msg = {"role": self.role, "content": self.content}
        
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        
        return msg


class ConversationManager:
    """Gestiona el historial de conversación"""
    
    MAX_MESSAGES = 500  # Límite máximo de mensajes
    AUTO_COMPACT_THRESHOLD = 400  # Auto-compactar cuando llegue a este número
    MAX_MESSAGE_LENGTH = 100000  # Límite de caracteres por mensaje
    
    def __init__(self, session_id: str = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.messages: List[Message] = []
        self.metadata: Dict = {
            "created": datetime.now().isoformat(),
            "model": None,
            "working_directory": None
        }
    
    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: List[Dict] = None,
        tool_call_id: str = None,
        name: str = None
    ) -> Message:
        """Añade un mensaje a la conversación"""
        
        # Limitar tamaño de contenido
        if len(content) > self.MAX_MESSAGE_LENGTH:
            content = content[:self.MAX_MESSAGE_LENGTH] + f"\n\n[Contenido truncado: {len(content) - self.MAX_MESSAGE_LENGTH} caracteres restantes]"
        
        message = Message(
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            name=name
        )
        
        # Verificar límite antes de agregar
        if len(self.messages) >= self.MAX_MESSAGES:
            # Auto-compactar manteniendo los más importantes
            self._auto_compact()
        
        self.messages.append(message)
        
        # Auto-compactar si se acerca al límite
        if len(self.messages) >= self.AUTO_COMPACT_THRESHOLD:
            self._auto_compact()
        
        return message
    
    def _auto_compact(self):
        """Compactación inteligente: mantiene system, últimos mensajes y mensajes con tool_calls"""
        if len(self.messages) <= self.AUTO_COMPACT_THRESHOLD:
            return
        
        # Separar mensajes importantes
        important = []
        recent = []
        
        # Mantener últimos 50 mensajes
        recent = self.messages[-50:]
        
        # Mantener mensajes con tool_calls (importantes para contexto)
        important = [m for m in self.messages[:-50] if m.tool_calls]
        
        # Mantener algunos mensajes del usuario al inicio para contexto
        user_messages = [m for m in self.messages[:-50] if m.role == "user"][:10]
        
        # Combinar: importantes + user iniciales + recientes
        self.messages = important[:20] + user_messages + recent
    
    def add_user_message(self, content: str) -> Message:
        """Añade mensaje del usuario"""
        return self.add_message("user", content)
    
    def add_assistant_message(self, content: str, tool_calls: List[Dict] = None) -> Message:
        """Añade mensaje del asistente"""
        return self.add_message("assistant", content, tool_calls=tool_calls)
    
    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> Message:
        """Añade resultado de herramienta"""
        return self.add_message("tool", content, tool_call_id=tool_call_id, name=name)
    
    def get_api_messages(self, include_system: str = None) -> List[Dict]:
        """Obtiene mensajes en formato de API"""
        messages = []
        
        if include_system:
            messages.append({"role": "system", "content": include_system})
        
        for msg in self.messages:
            messages.append(msg.to_api_format())
        
        return messages
    
    def get_last_n(self, n: int) -> List[Message]:
        """Obtiene los últimos N mensajes"""
        return self.messages[-n:]
    
    def clear(self):
        """Limpia la conversación"""
        self.messages = []
    
    def compact(self, keep_last: int = 4):
        """Compacta la conversación manteniendo los últimos N mensajes"""
        if len(self.messages) > keep_last:
            # Mantener system messages si existen
            system_msgs = [m for m in self.messages if m.role == "system"]
            recent_msgs = self.messages[-keep_last:]
            self.messages = system_msgs + recent_msgs
    
    def save(self, filename: str = None) -> str:
        """Guarda la conversación en un archivo"""
        filename = filename or f"session_{self.session_id}.json"
        filepath = SESSIONS_DIR / filename
        
        data = {
            "session_id": self.session_id,
            "metadata": self.metadata,
            "messages": [asdict(m) for m in self.messages]
        }
        
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return str(filepath)
    
    def load(self, filename: str) -> bool:
        """Carga una conversación desde archivo"""
        filepath = Path(filename)
        if not filepath.exists():
            filepath = SESSIONS_DIR / filename
        
        if not filepath.exists():
            return False
        
        try:
            data = json.loads(filepath.read_text())
            self.session_id = data.get("session_id", self.session_id)
            self.metadata = data.get("metadata", {})
            self.messages = [
                Message(**m) for m in data.get("messages", [])
            ]
            return True
        except Exception:
            return False
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas de la conversación"""
        user_msgs = sum(1 for m in self.messages if m.role == "user")
        assistant_msgs = sum(1 for m in self.messages if m.role == "assistant")
        tool_msgs = sum(1 for m in self.messages if m.role == "tool")
        
        total_chars = sum(len(m.content) for m in self.messages)
        
        return {
            "total_messages": len(self.messages),
            "user_messages": user_msgs,
            "assistant_messages": assistant_msgs,
            "tool_messages": tool_msgs,
            "total_characters": total_chars,
            "session_id": self.session_id
        }
    
    def __len__(self) -> int:
        return len(self.messages)
    
    def __iter__(self):
        return iter(self.messages)