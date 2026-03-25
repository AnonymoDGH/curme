import time
import hashlib
from typing import (
    Dict, List, Optional, Any, Callable, Tuple,
    Protocol, runtime_checkable, Union
)
from dataclasses import dataclass, field
from enum import Enum, auto

# ============================================================================
# ESTADOS Y TIPOS MEJORADOS
# ============================================================================

class OpenClawState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING_INPUT = "waiting_input"
    ERROR = "error"
    AUTONOMOUS = "autonomous"
    SHUTTING_DOWN = "shutting_down"


class ChannelType(Enum):
    CONSOLE = "console"
    DISCORD = "discord"
    API = "api"


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class OpenClawMessage:
    """Mensaje entrante al agente"""
    content: str
    channel: ChannelType
    user_id: str = "console_user"
    channel_id: str = "default"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL

    @property
    def message_id(self) -> str:
        """ID único del mensaje"""
        raw = f"{self.channel_id}:{self.timestamp}:{self.content[:50]}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]


@dataclass
class OpenClawResponse:
    """Respuesta del agente"""
    content: str
    channel: ChannelType
    thinking: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)   # paths de archivos a enviar
    model_used: str = ""
    autonomous: bool = False
    elapsed_time: float = 0.0
    token_count: Optional[int] = None
    error: Optional[str] = None

    @property
    def is_error(self) -> bool:
        return self.error is not None


@dataclass
class AutonomousTask:
    """Tarea para el modo autónomo"""
    objective: str
    steps: List[str] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 20
    results: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed, cancelled
    created_at: float = field(default_factory=time.time)
    priority: TaskPriority = TaskPriority.NORMAL


@dataclass
class Skill:
    """Skill/Acción que el agente puede ejecutar"""
    name: str
    description: str
    trigger_patterns: List[str]
    action: Callable
    requires_confirmation: bool = False
    model_preference: Optional[str] = None
    category: str = "general"
    enabled: bool = True
    cooldown_seconds: float = 0.0
    _last_used: float = 0.0


# ============================================================================
# PLUGIN PROTOCOL
# ============================================================================

@runtime_checkable
class SkillPlugin(Protocol):
    """Protocolo para plugins de skills"""

    @property
    def name(self) -> str: ...

    @property
    def skills(self) -> List[Skill]: ...

    def initialize(self, agent: Any) -> None: ...
