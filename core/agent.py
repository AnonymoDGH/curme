"""
NVIDIA CODE - Agente Principal (Versión Mejorada y Expandida)
=============================================================

Agente de programación avanzado con soporte para:
- Múltiples modelos de IA (NVIDIA, DeepSeek, Qwen, etc.)
- Sistema de herramientas extensible
- Modo Heavy Agent (colaboración multi-IA)
- Temas visuales personalizables
- Gestión avanzada de conversaciones
- Auto-modo para tareas complejas

Autor: NVIDIA Code Team
Versión: 2.0.0
"""

import os
import sys
import json
import time
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

# Imports internos
from config import MAX_TOOL_ITERATIONS, MAX_AUTO_TURNS
from models.registry import ModelRegistry, AVAILABLE_MODELS, ModelInfo
from tools import ToolRegistry
from .api_client import NVIDIAAPIClient, APIResponse
from .conversation import ConversationManager
from .heavy_agent import HeavyAgent
from .chat_storage import ChatStorage, ChatMetadata
from ui.colors import Colors
from ui.logo import print_logo, print_separator
from ui.markdown import render_markdown

# Sistema de temas (opcional)
try:
    from ui.themes import list_themes, set_theme, get_theme_manager, get_current_theme
    HAS_THEMES = True
except ImportError:
    HAS_THEMES = False

# Constantes de configuración
TOOL_BOX_WIDTH = 100
MAX_TOOLS_PER_ITERATION = 50
RESULT_PREVIEW_LENGTH = 500
MAX_LINE_LENGTH = 95
COMPACT_KEEP_MESSAGES = 4

# Inicializar colores
C = Colors()


class AgentState(Enum):
    """Estados posibles del agente"""
    IDLE = auto()
    PROCESSING = auto()
    WAITING_TOOLS = auto()
    ERROR = auto()
    HEAVY_MODE = auto()


class ToolExecutionStatus(Enum):
    """Estados de ejecución de herramientas"""
    PENDING = "⏳"
    SUCCESS = "✓"
    ERROR = "✗"
    SKIPPED = "⊘"


@dataclass
class ToolExecutionResult:
    """Resultado de la ejecución de una herramienta"""
    tool_name: str
    success: bool
    result: str
    elapsed_time: float
    error_message: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def status(self) -> ToolExecutionStatus:
        """Obtiene el estado de la ejecución"""
        if self.success:
            return ToolExecutionStatus.SUCCESS
        return ToolExecutionStatus.ERROR
    
    @property
    def result_preview(self) -> str:
        """Obtiene una vista previa del resultado"""
        if len(self.result) > RESULT_PREVIEW_LENGTH:
            return self.result[:RESULT_PREVIEW_LENGTH] + "..."
        return self.result


@dataclass
class CommandResult:
    """Resultado de la ejecución de un comando"""
    success: bool
    message: str = ""
    should_continue: bool = True
    data: Optional[Any] = None


class ToolDisplayManager:
    """Gestiona la visualización de herramientas en consola"""
    
    def __init__(self, width: int = TOOL_BOX_WIDTH):
        self.width = width
    
    def _get_theme_colors(self) -> Tuple[str, str, str]:
        """Obtiene colores del tema actual"""
        try:
            if HAS_THEMES:
                tm = get_theme_manager()
                primary = tm.rgb_to_ansi(tm.current_theme.primary)
                success = tm.rgb_to_ansi(tm.current_theme.success)
                error = tm.rgb_to_ansi(tm.current_theme.error)
                return primary, success, error
        except:
            pass
        return C.NVIDIA_GREEN, C.BRIGHT_GREEN, C.BRIGHT_RED
    
    def format_tool_name(self, name: str) -> str:
        """Formatea el nombre de la herramienta para mostrar"""
        return name.replace('_', ' ').title()
    
    def format_arguments(self, args: Dict[str, Any], max_args: int = 2) -> str:
        """Formatea los argumentos para mostrar"""
        if not args:
            return ""
        
        formatted = []
        for key, value in list(args.items())[:max_args]:
            str_value = str(value)
            if len(str_value) > 25:
                str_value = str_value[:22] + "..."
            formatted.append(f"{key}={str_value}")
        
        result = " ".join(formatted)
        if len(args) > max_args:
            result += "..."
        
        return f" {result}"
    
    def print_box_start(self):
        """Imprime el inicio de la caja"""
        print(f"\n{C.DIM}╭{'─' * self.width}╮{C.RESET}")
    
    def print_box_end(self):
        """Imprime el final de la caja"""
        print(f"{C.DIM}╰{'─' * self.width}╯{C.RESET}\n")
    
    def print_box_separator(self):
        """Imprime un separador dentro de la caja"""
        print(f"{C.DIM}├{'─' * self.width}┤{C.RESET}")
    
    def print_box_line(self, content: str, padding: bool = True):
        """Imprime una línea dentro de la caja"""
        # Calcular longitud visible (sin códigos ANSI)
        visible_length = len(re.sub(r'\x1b\[[0-9;]*m', '', content))
        remaining = max(0, self.width - visible_length - 2)
        
        if padding:
            print(f"{C.DIM}│{C.RESET} {content}{' ' * remaining}{C.DIM}│{C.RESET}")
        else:
            print(f"{C.DIM}│{C.RESET} {content}")
    
    def print_pending(self, tool_name: str, args: Dict[str, Any]):
        """Muestra herramienta en estado pendiente"""
        display_name = self.format_tool_name(tool_name)
        args_str = self.format_arguments(args)
        tool_line = f"{display_name}{args_str}"
        
        self.print_box_start()
        content = f"{C.DIM}⏳{C.RESET}  {C.BRIGHT_CYAN}{tool_line}{C.RESET}"
        print(f"{C.DIM}│{C.RESET} {content}", end='', flush=True)
    
    def print_success(self, tool_name: str, args: Dict[str, Any], 
                      elapsed: float, result_size: int):
        """Muestra herramienta completada con éxito"""
        display_name = self.format_tool_name(tool_name)
        args_str = self.format_arguments(args)
        tool_line = f"{display_name}{args_str}"
        
        size_str = f"{result_size:,}" if result_size > 1000 else str(result_size)
        status_text = f"({elapsed:.2f}s, {size_str} chars)"
        
        visible_len = len(tool_line) + len(status_text) + 6
        remaining = max(0, self.width - visible_len)
        
        print(f"\r{C.DIM}│{C.RESET} {C.BRIGHT_GREEN}✓{C.RESET}  {C.BRIGHT_CYAN}{tool_line}{C.RESET} "
              f"{C.DIM}{status_text}{C.RESET}{' ' * remaining}{C.DIM}│{C.RESET}")
    
    def print_error(self, tool_name: str, args: Dict[str, Any], error_msg: str):
        """Muestra herramienta con error"""
        display_name = self.format_tool_name(tool_name)
        args_str = self.format_arguments(args)
        tool_line = f"{display_name}{args_str}"
        
        # Truncar mensaje de error si es muy largo
        if len(error_msg) > 60:
            error_msg = error_msg[:57] + "..."
        
        visible_len = len(tool_line) + len(error_msg) + 8
        remaining = max(0, self.width - visible_len)
        
        print(f"\r{C.DIM}│{C.RESET} {C.BRIGHT_RED}✗{C.RESET}  {C.BRIGHT_CYAN}{tool_line}{C.RESET} "
              f"{C.BRIGHT_RED}{error_msg}{C.RESET}{' ' * remaining}{C.DIM}│{C.RESET}")
    
    def print_result_preview(self, result: str, max_lines: int = 8):
        """Muestra vista previa del resultado"""
        if len(result) < 100:
            return
        
        print(f"{C.DIM}│{C.RESET}")
        
        try:
            rendered = render_markdown(result)
            lines = rendered.split('\n')[:max_lines]
            
            for line in lines:
                if len(line) > MAX_LINE_LENGTH:
                    line = line[:MAX_LINE_LENGTH - 3] + "..."
                self.print_box_line(line, padding=False)
            
            if len(rendered.split('\n')) > max_lines:
                self.print_box_line(f"{C.DIM}... (ver más arriba){C.RESET}", padding=False)
                
        except Exception:
            # Fallback sin markdown
            lines = result.split('\n')[:max_lines]
            for line in lines:
                if len(line) > MAX_LINE_LENGTH:
                    line = line[:MAX_LINE_LENGTH - 3] + "..."
                self.print_box_line(f"{C.DIM}{line}{C.RESET}", padding=False)


class CommandHandler:
    """Manejador de comandos del agente"""
    
    def __init__(self, agent: 'NVIDIACodeAgent'):
        self.agent = agent
        self._commands: Dict[str, Callable] = {}
        self._aliases: Dict[str, str] = {}
        self._register_commands()
    
    def _register_commands(self):
        """Registra todos los comandos disponibles"""
        # Comandos principales
        self.register('/help', self._cmd_help, ['/h'], "Mostrar esta ayuda")
        self.register('/exit', self._cmd_exit, ['/quit', '/q'], "Salir del agente")
        self.register('/clear', self._cmd_clear, ['/cls'], "Limpiar pantalla")
        
        # Gestión de modelos
        self.register('/model', self._cmd_model, ['/m'], "Cambiar modelo actual")
        self.register('/models', self._cmd_list_models, [], "Listar modelos disponibles")
        self.register('/test', self._cmd_test, [], "Probar conexión con modelo")
        
        # Modos y configuración
        self.register('/heavy', self._cmd_heavy, [], "Activar/desactivar Heavy Agent")
        self.register('/auto', self._cmd_auto, [], "Activar/desactivar modo automático")
        self.register('/stream', self._cmd_stream, [], "Activar/desactivar streaming")
        
        # Conversación
        self.register('/reset', self._cmd_reset, [], "Reiniciar conversación")
        self.register('/compact', self._cmd_compact, [], "Compactar historial")
        self.register('/history', self._cmd_history, ['/hist'], "Ver historial")
        self.register('/save', self._cmd_save, [], "Guardar conversación")
        self.register('/load', self._cmd_load, [], "Cargar conversación")
        
        # Gestión de chats
        self.register('/chat list', self._cmd_chat_list, ['/history', '/chats'], "Listar chats guardados")
        self.register('/save chat', self._cmd_chat_save, [], "Guardar chat con nombre")
        self.register('/resume chat', self._cmd_chat_resume, ['/load chat'], "Retomar chat guardado")
        self.register('/delete chat', self._cmd_chat_delete, [], "Eliminar chat guardado")
        self.register('/search chat', self._cmd_chat_search, [], "Buscar chats")
        
        # Sistema
        self.register('/status', self._cmd_status, ['/info'], "Ver estado del agente")
        self.register('/cd', self._cmd_cd, [], "Cambiar directorio de trabajo")
        self.register('/pwd', self._cmd_pwd, [], "Mostrar directorio actual")
        self.register('/ls', self._cmd_ls, ['/dir'], "Listar archivos")
        
        # Herramientas
        self.register('/tools', self._cmd_tools, [], "Ver herramientas disponibles")
        self.register('/tool', self._cmd_tool_info, [], "Info de una herramienta")
        
        # UI/Temas
        self.register('/themes', self._cmd_themes, ['/theme'], "Gestionar temas")
        self.register('/logo', self._cmd_logo, [], "Cambiar estilo de logo")
        self.register('/colors', self._cmd_colors, [], "Mostrar paleta de colores")
        
        # Debug/Desarrollo
        self.register('/debug', self._cmd_debug, [], "Modo debug")
        self.register('/stats', self._cmd_stats, [], "Estadísticas detalladas")
        self.register('/version', self._cmd_version, ['/v'], "Mostrar versión")
    
    def register(self, command: str, handler: Callable, 
                 aliases: List[str] = None, description: str = ""):
        """Registra un comando con sus aliases"""
        self._commands[command] = {
            'handler': handler,
            'description': description,
            'aliases': aliases or []
        }
        
        # Registrar aliases
        for alias in (aliases or []):
            self._aliases[alias] = command
    
    def execute(self, command_str: str) -> CommandResult:
        """Ejecuta un comando"""
        parts = command_str.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Resolver alias
        if cmd in self._aliases:
            cmd = self._aliases[cmd]
        
        # Buscar y ejecutar comando
        if cmd in self._commands:
            try:
                return self._commands[cmd]['handler'](args)
            except Exception as e:
                return CommandResult(
                    success=False,
                    message=f"Error ejecutando comando: {e}"
                )
        
        return CommandResult(
            success=False,
            message=f"Comando no reconocido: {cmd}. Usa /help para ver comandos."
        )
    
    def get_commands_list(self) -> List[Tuple[str, str, List[str]]]:
        """Obtiene lista de comandos para mostrar"""
        result = []
        for cmd, info in self._commands.items():
            result.append((cmd, info['description'], info['aliases']))
        return sorted(result, key=lambda x: x[0])
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMANDOS DE AYUDA Y NAVEGACIÓN
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _cmd_help(self, args: str) -> CommandResult:
        """Muestra ayuda detallada"""
        if args:
            # Ayuda específica de un comando
            cmd = args if args.startswith('/') else f'/{args}'
            if cmd in self._aliases:
                cmd = self._aliases[cmd]
            
            if cmd in self._commands:
                info = self._commands[cmd]
                print(f"\n{C.NVIDIA_GREEN}═══ {cmd} ═══{C.RESET}")
                print(f"{C.DIM}Descripción:{C.RESET} {info['description']}")
                if info['aliases']:
                    print(f"{C.DIM}Aliases:{C.RESET} {', '.join(info['aliases'])}")
                print()
                return CommandResult(success=True)
            else:
                return CommandResult(success=False, message=f"Comando no encontrado: {cmd}")
        
        # Ayuda general
        width = 60
        print(f"\n{C.NVIDIA_GREEN}╔{'═' * width}╗{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.BOLD}{C.BRIGHT_WHITE}📚 COMANDOS DISPONIBLES{C.RESET}{' ' * (width - 25)}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}╠{'═' * width}╣{C.RESET}")
        
        # Agrupar comandos por categoría
        categories = {
            'General': ['/help', '/exit', '/clear', '/version'],
            'Modelos': ['/model', '/models', '/test'],
            'Modos': ['/heavy', '/auto', '/stream'],
            'Conversación': ['/reset', '/compact', '/history', '/save', '/load'],
            'Sistema': ['/status', '/cd', '/pwd', '/ls'],
            'Herramientas': ['/tools', '/tool'],
            'Visual': ['/themes', '/logo', '/colors'],
            'Debug': ['/debug', '/stats']
        }
        
        for category, cmds in categories.items():
            print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.BRIGHT_YELLOW}▸ {category}{C.RESET}{' ' * (width - len(category) - 4)}{C.NVIDIA_GREEN}║{C.RESET}")
            
            for cmd in cmds:
                if cmd in self._commands:
                    info = self._commands[cmd]
                    aliases = f" ({', '.join(info['aliases'])})" if info['aliases'] else ""
                    desc = info['description'][:35]
                    line = f"  {C.BRIGHT_CYAN}{cmd:12}{C.RESET}{C.DIM}{aliases:10}{C.RESET} {desc}"
                    visible_len = len(cmd) + len(aliases) + len(desc) + 14
                    padding = max(0, width - visible_len)
                    print(f"{C.NVIDIA_GREEN}║{C.RESET}{line}{' ' * padding}{C.NVIDIA_GREEN}║{C.RESET}")
            
            print(f"{C.NVIDIA_GREEN}║{C.RESET}{' ' * width}{C.NVIDIA_GREEN}║{C.RESET}")
        
        print(f"{C.NVIDIA_GREEN}╠{'═' * width}╣{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.DIM}💡 Usa /help <comando> para más detalles{C.RESET}{' ' * 17}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}╚{'═' * width}╝{C.RESET}\n")
        
        return CommandResult(success=True)
    
    def _cmd_exit(self, args: str) -> CommandResult:
        """Sale del agente"""
        print(f"\n{C.NVIDIA_GREEN}╔{'═' * 40}╗{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.BOLD}👋 ¡Hasta luego!{C.RESET}{' ' * 21}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.DIM}Gracias por usar NVIDIA Code{C.RESET}{' ' * 9}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}╚{'═' * 40}╝{C.RESET}\n")
        sys.exit(0)
    
    def _cmd_clear(self, args: str) -> CommandResult:
        """Limpia la pantalla"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print_logo()
        return CommandResult(success=True, message="Pantalla limpiada")
    
    def _cmd_version(self, args: str) -> CommandResult:
        """Muestra la versión"""
        print(f"\n{C.NVIDIA_GREEN}NVIDIA Code{C.RESET} v2.0.0")
        print(f"{C.DIM}Python {sys.version.split()[0]} | {sys.platform}{C.RESET}\n")
        return CommandResult(success=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMANDOS DE MODELOS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _cmd_model(self, args: str) -> CommandResult:
        """Cambia el modelo actual"""
        if not args:
            return self._cmd_list_models("")
        
        model = self.agent.registry.get(args.strip())
        if model:
            self.agent.current_model = model
            self.agent.system_prompt = self.agent._build_system_prompt()
            
            print(f"\n{C.BRIGHT_GREEN}✅ Modelo cambiado:{C.RESET}")
            print(f"   {C.BRIGHT_CYAN}{model.name}{C.RESET} {model.specialty}")
            
            # Mostrar capacidades
            capabilities = []
            if model.supports_tools:
                capabilities.append(f"{C.BRIGHT_GREEN}🔧 Herramientas{C.RESET}")
            if model.thinking:
                capabilities.append(f"{C.BRIGHT_MAGENTA}🧠 Thinking{C.RESET}")
            
            if capabilities:
                print(f"   {' | '.join(capabilities)}")
            elif not model.supports_tools:
                print(f"   {C.BRIGHT_YELLOW}⚠️  Sin soporte de herramientas{C.RESET}")
            
            print()
            return CommandResult(success=True)
        
        return CommandResult(
            success=False,
            message=f"Modelo no válido: {args}. Usa /models para ver la lista."
        )
    
    def _cmd_list_models(self, args: str) -> CommandResult:
        """Lista todos los modelos disponibles"""
        print(f"\n{C.NVIDIA_GREEN}╔{'═' * 70}╗{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.BOLD}{C.BRIGHT_WHITE}🤖 MODELOS DISPONIBLES{C.RESET}{' ' * 47}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}╠{'═' * 70}╣{C.RESET}")
        
        for key, model in AVAILABLE_MODELS.items():
            current = " ◄" if model.id == self.agent.current_model.id else ""
            thinking = "🧠" if model.thinking else "  "
            tools = "🔧" if model.supports_tools else "  "
            
            name_display = f"{model.name[:25]:<25}"
            specialty_display = f"{model.specialty[:20]:<20}"
            
            line = f"  {C.BRIGHT_CYAN}{key:3}{C.RESET} [{thinking}{tools}] {name_display} {C.DIM}{specialty_display}{C.RESET}{C.GREEN}{current}{C.RESET}"
            visible_len = 3 + 6 + 25 + 20 + len(current)
            padding = max(0, 68 - visible_len)
            
            print(f"{C.NVIDIA_GREEN}║{C.RESET}{line}{' ' * padding}{C.NVIDIA_GREEN}║{C.RESET}")
        
        print(f"{C.NVIDIA_GREEN}╠{'═' * 70}╣{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.DIM}🧠 = Thinking Mode  🔧 = Herramientas  |  Usa: /model <número>{C.RESET}{' ' * 4}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}╚{'═' * 70}╝{C.RESET}\n")
        
        return CommandResult(success=True)
    
    def _cmd_test(self, args: str) -> CommandResult:
        """Prueba la conexión con el modelo"""
        model = self.agent.current_model
        print(f"\n{C.DIM}🔍 Probando conexión con {model.name}...{C.RESET}")
        
        start = time.time()
        result = self.agent.api_client.test_connection(model)
        elapsed = time.time() - start
        
        if result.get("success"):
            print(f"{C.BRIGHT_GREEN}✅ Conexión exitosa{C.RESET}")
            print(f"   {C.DIM}Tiempo de respuesta: {elapsed:.2f}s{C.RESET}")
            print(f"   {C.DIM}Modelo: {model.id}{C.RESET}\n")
            return CommandResult(success=True)
        else:
            print(f"{C.BRIGHT_RED}❌ Error de conexión{C.RESET}")
            print(f"   {C.DIM}{result.get('error', 'Error desconocido')}{C.RESET}\n")
            return CommandResult(success=False, message=result.get('error', ''))
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMANDOS DE MODOS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _cmd_heavy(self, args: str) -> CommandResult:
        """Activa/desactiva el modo Heavy Agent"""
        self.agent.heavy_mode = not self.agent.heavy_mode
        
        if self.agent.heavy_mode:
            print(f"\n{C.BRIGHT_MAGENTA}🔥 Heavy Agent ACTIVADO{C.RESET}")
            print(f"   {C.DIM}Modo colaborativo multi-IA habilitado{C.RESET}")
            print(f"   {C.DIM}Las respuestas pueden tardar más pero serán más precisas{C.RESET}\n")
        else:
            print(f"\n{C.DIM}⚡ Heavy Agent DESACTIVADO{C.RESET}")
            print(f"   {C.DIM}Modo estándar restaurado{C.RESET}\n")
        
        return CommandResult(success=True)
    
    def _cmd_auto(self, args: str) -> CommandResult:
        """Activa/desactiva el modo automático"""
        self.agent.auto_mode = not self.agent.auto_mode
        
        status = "ACTIVADO" if self.agent.auto_mode else "DESACTIVADO"
        icon = "🤖" if self.agent.auto_mode else "👤"
        color = C.BRIGHT_GREEN if self.agent.auto_mode else C.DIM
        
        print(f"\n{color}{icon} Modo Automático {status}{C.RESET}")
        if self.agent.auto_mode:
            print(f"   {C.DIM}El agente ejecutará herramientas sin confirmación{C.RESET}\n")
        else:
            print(f"   {C.DIM}Se pedirá confirmación para operaciones sensibles{C.RESET}\n")
        
        return CommandResult(success=True)
    
    def _cmd_stream(self, args: str) -> CommandResult:
        """Activa/desactiva el streaming"""
        self.agent.stream = not self.agent.stream
        
        status = "ACTIVADO" if self.agent.stream else "DESACTIVADO"
        print(f"\n{C.BRIGHT_CYAN}📡 Streaming {status}{C.RESET}\n")
        
        return CommandResult(success=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMANDOS DE CONVERSACIÓN
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _cmd_reset(self, args: str) -> CommandResult:
        """Reinicia la conversación"""
        msg_count = len(self.agent.conversation)
        self.agent.conversation.clear()
        
        print(f"\n{C.BRIGHT_GREEN}✅ Conversación reiniciada{C.RESET}")
        print(f"   {C.DIM}{msg_count} mensajes eliminados{C.RESET}\n")
        
        return CommandResult(success=True)
    
    def _cmd_compact(self, args: str) -> CommandResult:
        """Compacta el historial de conversación"""
        keep = int(args) if args.isdigit() else COMPACT_KEEP_MESSAGES
        before = len(self.agent.conversation)
        
        self.agent.conversation.compact(keep_last=keep)
        after = len(self.agent.conversation)
        
        print(f"\n{C.BRIGHT_GREEN}✅ Historial compactado{C.RESET}")
        print(f"   {C.DIM}{before} → {after} mensajes (guardados últimos {keep}){C.RESET}\n")
        
        return CommandResult(success=True)
    
    def _cmd_history(self, args: str) -> CommandResult:
        """Muestra el historial de la conversación"""
        messages = self.agent.conversation.messages
        
        if not messages:
            print(f"\n{C.DIM}No hay mensajes en el historial{C.RESET}\n")
            return CommandResult(success=True)
        
        limit = int(args) if args.isdigit() else 10
        messages_to_show = messages[-limit:]
        
        print(f"\n{C.NVIDIA_GREEN}═══ Historial ({len(messages)} mensajes, mostrando {len(messages_to_show)}) ═══{C.RESET}\n")
        
        for i, msg in enumerate(messages_to_show):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:100]
            
            if role == 'user':
                icon = "👤"
                color = C.BRIGHT_CYAN
            elif role == 'assistant':
                icon = "🤖"
                color = C.BRIGHT_GREEN
            elif role == 'tool':
                icon = "🔧"
                color = C.BRIGHT_YELLOW
            else:
                icon = "❓"
                color = C.DIM
            
            print(f"{color}{icon} [{role:9}]{C.RESET} {content}{'...' if len(msg.get('content', '')) > 100 else ''}")
        
        print()
        return CommandResult(success=True)
    
    def _cmd_save(self, args: str) -> CommandResult:
        """Guarda la conversación en un archivo"""
        filename = args.strip() or f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        if not filename.endswith('.json'):
            filename += '.json'
        
        try:
            data = {
                'model': self.agent.current_model.id,
                'timestamp': datetime.now().isoformat(),
                'messages': self.agent.conversation.messages
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"\n{C.BRIGHT_GREEN}✅ Conversación guardada en: {filename}{C.RESET}\n")
            return CommandResult(success=True)
            
        except Exception as e:
            return CommandResult(success=False, message=f"Error al guardar: {e}")
    
    def _cmd_load(self, args: str) -> CommandResult:
        """Carga una conversación desde archivo"""
        filename = args.strip()
        
        if not filename:
            # Listar archivos disponibles
            json_files = list(Path('.').glob('conversation_*.json'))
            if json_files:
                print(f"\n{C.NVIDIA_GREEN}Archivos disponibles:{C.RESET}")
                for f in sorted(json_files)[-5:]:
                    print(f"  • {f.name}")
                print(f"\n{C.DIM}Uso: /load <archivo>{C.RESET}\n")
            else:
                print(f"\n{C.DIM}No hay conversaciones guardadas{C.RESET}\n")
            return CommandResult(success=True)
        
        if not filename.endswith('.json'):
            filename += '.json'
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.agent.conversation.messages = data.get('messages', [])
            
            print(f"\n{C.BRIGHT_GREEN}✅ Conversación cargada: {filename}{C.RESET}")
            print(f"   {C.DIM}{len(self.agent.conversation)} mensajes{C.RESET}\n")
            return CommandResult(success=True)
            
        except FileNotFoundError:
            return CommandResult(success=False, message=f"Archivo no encontrado: {filename}")
        except json.JSONDecodeError as e:
            return CommandResult(success=False, message=f"Error de formato JSON: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GESTIÓN DE CHATS (ChatStorage)
    # ═══════════════════════════════════════════════════════════════════════════

    def _cmd_chat_list(self, args: str) -> CommandResult:
        """Lista los chats guardados"""
        chats = ChatStorage.list_chats()
        
        if not chats:
            print(f"\n{C.DIM}No hay chats guardados.{C.RESET}\n")
            return CommandResult(success=True)
        
        print(f"\n{C.NVIDIA_GREEN}╔{'═' * 70}╗{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.BOLD}{C.BRIGHT_WHITE}📂 CHATS GUARDADOS ({len(chats)}){C.RESET}{' ' * 47}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}╠{'═' * 70}╣{C.RESET}")
        
        for i, chat in enumerate(chats):
            name = chat.name[:25]
            date = chat.last_modified_formatted
            msgs = f"{chat.message_count} msgs"
            model = chat.model[:15]
            
            line = f"  {C.BRIGHT_CYAN}{name:<25}{C.RESET} {C.DIM}{date:<18}{C.RESET} {C.BRIGHT_GREEN}{msgs:<10}{C.RESET} {C.DIM}{model}{C.RESET}"
            visible_len = 25 + 18 + 10 + len(model) + 6
            padding = max(0, 68 - visible_len)
            
            print(f"{C.NVIDIA_GREEN}║{C.RESET}{line}{' ' * padding}{C.NVIDIA_GREEN}║{C.RESET}")
        
        print(f"{C.NVIDIA_GREEN}╠{'═' * 70}╣{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.DIM}Usa /resume chat <nombre> para cargar un chat{C.RESET}{' ' * 21}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}╚{'═' * 70}╝{C.RESET}\n")
        
        return CommandResult(success=True)

    def _cmd_chat_save(self, args: str) -> CommandResult:
        """Guarda el chat actual"""
        name = args.strip()
        if not name:
            name = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Convertir mensajes a diccionarios para serialización JSON
        from dataclasses import asdict
        messages_dict = [asdict(m) for m in self.agent.conversation.messages]
            
        success = ChatStorage.save_chat(
            name=name,
            messages=messages_dict,
            model_id=self.agent.current_model.id,
            working_directory=str(self.agent.working_directory),
            heavy_mode=self.agent.heavy_mode,
            stream_enabled=self.agent.stream
        )
        
        if success:
            print(f"\n{C.BRIGHT_GREEN}✅ Chat guardado como: {C.BRIGHT_WHITE}{name}{C.RESET}\n")
            return CommandResult(success=True)
        else:
            return CommandResult(success=False, message="Error al guardar el chat")

    def _cmd_chat_resume(self, args: str) -> CommandResult:
        """Retoma un chat guardado"""
        name = args.strip()
        if not name:
            return CommandResult(success=False, message="Debes especificar el nombre del chat: /resume chat <nombre>")
            
        chat_data = ChatStorage.load_chat(name)
        if not chat_data:
            # Intentar búsqueda por aproximación si no existe exacto
            matches = ChatStorage.search_chats(name)
            if matches:
                name = matches[0].name
                chat_data = ChatStorage.load_chat(name)
            
        if chat_data:
            # Convertir de nuevo a objetos Message
            from .conversation import Message
            messages = []
            for m_dict in chat_data.messages:
                # Filtrar campos que no pertenecen a Message si es necesario
                messages.append(Message(**m_dict))
                
            self.agent.conversation.messages = messages
            self.agent.heavy_mode = chat_data.heavy_mode
            self.agent.stream = chat_data.stream_enabled
            
            # Intentar cambiar de directorio si existe
            if chat_data.working_directory:
                try:
                    os.chdir(chat_data.working_directory)
                    self.agent.working_directory = Path(chat_data.working_directory)
                except:
                    pass
            
            print(f"\n{C.BRIGHT_GREEN}✅ Chat '{name}' cargado correctamente{C.RESET}")
            print(f"   {C.DIM}{len(messages)} mensajes restaurados{C.RESET}\n")
            return CommandResult(success=True)
        else:
            return CommandResult(success=False, message=f"No se encontró el chat: {name}")

    def _cmd_chat_delete(self, args: str) -> CommandResult:
        """Elimina un chat guardado"""
        name = args.strip()
        if not name:
            return CommandResult(success=False, message="Especifica el nombre del chat a eliminar")
            
        if ChatStorage.delete_chat(name):
            print(f"\n{C.BRIGHT_GREEN}✅ Chat '{name}' eliminado{C.RESET}\n")
            return CommandResult(success=True)
        else:
            return CommandResult(success=False, message=f"No se pudo eliminar el chat: {name}")

    def _cmd_chat_search(self, args: str) -> CommandResult:
        """Busca chats guardados"""
        query = args.strip()
        if not query:
            return CommandResult(success=False, message="Especifica un término de búsqueda")
            
        results = ChatStorage.search_chats(query)
        if not results:
            print(f"\n{C.DIM}No se encontraron chats que coincidan con '{query}'{C.RESET}\n")
            return CommandResult(success=True)
            
        print(f"\n{C.NVIDIA_GREEN}🔍 Resultados para '{query}':{C.RESET}")
        for chat in results:
            print(f"  • {C.BRIGHT_CYAN}{chat.name:25}{C.RESET} {C.DIM}{chat.last_modified_formatted}{C.RESET}")
        print()
        return CommandResult(success=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # COMANDOS DE SISTEMA
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _cmd_status(self, args: str) -> CommandResult:
        """Muestra el estado completo del agente"""
        stats = self.agent.conversation.get_stats()
        width = 55
        
        print(f"\n{C.NVIDIA_GREEN}╔{'═' * width}╗{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.BOLD}{C.BRIGHT_WHITE}📊 ESTADO DEL AGENTE{C.RESET}{' ' * (width - 22)}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}╠{'═' * width}╣{C.RESET}")
        
        # Modelo
        model_line = f"🤖 Modelo: {C.BRIGHT_CYAN}{self.agent.current_model.name}{C.RESET}"
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {model_line}{' ' * 20}{C.NVIDIA_GREEN}║{C.RESET}")
        
        # Especialidad
        spec_line = f"   {C.DIM}{self.agent.current_model.specialty}{C.RESET}"
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {spec_line}{' ' * (width - len(self.agent.current_model.specialty) - 5)}{C.NVIDIA_GREEN}║{C.RESET}")
        
        print(f"{C.NVIDIA_GREEN}╟{'─' * width}╢{C.RESET}")
        
        # Modos
        heavy_status = f"{C.BRIGHT_MAGENTA}🔥 Sí{C.RESET}" if self.agent.heavy_mode else f"{C.DIM}⚡ No{C.RESET}"
        auto_status = f"{C.BRIGHT_GREEN}🤖 Sí{C.RESET}" if self.agent.auto_mode else f"{C.DIM}👤 No{C.RESET}"
        stream_status = f"{C.BRIGHT_CYAN}📡 Sí{C.RESET}" if self.agent.stream else f"{C.DIM}📡 No{C.RESET}"
        
        print(f"{C.NVIDIA_GREEN}║{C.RESET} Heavy Mode: {heavy_status}{' ' * 30}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} Auto Mode:  {auto_status}{' ' * 30}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} Streaming:  {stream_status}{' ' * 30}{C.NVIDIA_GREEN}║{C.RESET}")
        
        print(f"{C.NVIDIA_GREEN}╟{'─' * width}╢{C.RESET}")
        
        # Estadísticas
        total = stats.get('total_messages', 0)
        user = stats.get('user_messages', 0)
        assistant = stats.get('assistant_messages', 0)
        
        print(f"{C.NVIDIA_GREEN}║{C.RESET} 💬 Mensajes: {total} (👤 {user} | 🤖 {assistant}){' ' * 15}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} 📂 Directorio: {C.DIM}{str(self.agent.working_directory)[:35]}{C.RESET}{' ' * 5}{C.NVIDIA_GREEN}║{C.RESET}")
        
        print(f"{C.NVIDIA_GREEN}╚{'═' * width}╝{C.RESET}\n")
        
        return CommandResult(success=True)
    
    def _cmd_cd(self, args: str) -> CommandResult:
        """Cambia el directorio de trabajo"""
        try:
            path = Path(args or str(Path.home())).expanduser().resolve()
            
            if path.is_dir():
                self.agent.working_directory = path
                os.chdir(path)
                self.agent.system_prompt = self.agent._build_system_prompt()
                
                print(f"\n{C.BRIGHT_GREEN}📂 Directorio cambiado:{C.RESET}")
                print(f"   {C.BRIGHT_WHITE}{path}{C.RESET}\n")
                return CommandResult(success=True)
            else:
                return CommandResult(success=False, message=f"No es un directorio: {args}")
                
        except Exception as e:
            return CommandResult(success=False, message=f"Error: {e}")
    
    def _cmd_pwd(self, args: str) -> CommandResult:
        """Muestra el directorio actual"""
        print(f"\n{C.BRIGHT_GREEN}📂 Directorio actual:{C.RESET}")
        print(f"   {C.BRIGHT_WHITE}{self.agent.working_directory}{C.RESET}\n")
        return CommandResult(success=True)
    
    def _cmd_ls(self, args: str) -> CommandResult:
        """Lista archivos del directorio"""
        path = Path(args) if args else self.agent.working_directory
        
        try:
            items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            
            print(f"\n{C.NVIDIA_GREEN}📂 {path}{C.RESET}\n")
            
            dirs = []
            files = []
            
            for item in items[:50]:  # Limitar a 50 items
                if item.is_dir():
                    dirs.append(f"  {C.BRIGHT_BLUE}📁 {item.name}/{C.RESET}")
                else:
                    size = item.stat().st_size
                    size_str = self._format_size(size)
                    files.append(f"  {C.DIM}📄 {item.name} ({size_str}){C.RESET}")
            
            for d in dirs:
                print(d)
            for f in files:
                print(f)
            
            if len(items) > 50:
                print(f"\n  {C.DIM}... y {len(items) - 50} más{C.RESET}")
            
            print()
            return CommandResult(success=True)
            
        except PermissionError:
            return CommandResult(success=False, message="Permiso denegado")
        except Exception as e:
            return CommandResult(success=False, message=str(e))
    
    def _format_size(self, size: int) -> str:
        """Formatea tamaño de archivo"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}" if unit != 'B' else f"{size}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMANDOS DE HERRAMIENTAS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _cmd_tools(self, args: str) -> CommandResult:
        """Lista todas las herramientas disponibles"""
        tools = ToolRegistry.list_names()
        
        print(f"\n{C.NVIDIA_GREEN}╔{'═' * 50}╗{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.BOLD}{C.BRIGHT_WHITE}🔧 HERRAMIENTAS ({len(tools)}){C.RESET}{' ' * (30 - len(str(len(tools))))}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}╠{'═' * 50}╣{C.RESET}")
        
        for name in sorted(tools):
            tool = ToolRegistry.get(name)
            desc = ""
            if tool and hasattr(tool, 'description'):
                desc = tool.description[:30]
            
            line = f"  {C.BRIGHT_CYAN}{name:20}{C.RESET} {C.DIM}{desc}{C.RESET}"
            print(f"{C.NVIDIA_GREEN}║{C.RESET}{line}{' ' * (48 - len(name) - len(desc))}{C.NVIDIA_GREEN}║{C.RESET}")
        
        print(f"{C.NVIDIA_GREEN}╠{'═' * 50}╣{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} {C.DIM}Usa /tool <nombre> para más info{C.RESET}{' ' * 15}{C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}╚{'═' * 50}╝{C.RESET}\n")
        
        return CommandResult(success=True)
    
    def _cmd_tool_info(self, args: str) -> CommandResult:
        """Muestra información detallada de una herramienta"""
        if not args:
            return CommandResult(success=False, message="Especifica una herramienta: /tool <nombre>")
        
        tool_name = args.strip()
        tool = ToolRegistry.get(tool_name)
        
        if not tool:
            return CommandResult(success=False, message=f"Herramienta no encontrada: {tool_name}")
        
        print(f"\n{C.NVIDIA_GREEN}═══ {tool_name} ═══{C.RESET}")
        
        if hasattr(tool, 'description'):
            print(f"{C.DIM}Descripción:{C.RESET} {tool.description}")
        
        if hasattr(tool, 'parameters'):
            print(f"\n{C.BRIGHT_CYAN}Parámetros:{C.RESET}")
            for param_name, param_info in tool.parameters.items():
                required = "✓" if param_info.required else "○"
                print(f"  {required} {C.BRIGHT_WHITE}{param_name}{C.RESET}: {param_info.type} - {param_info.description}")
        
        print()
        return CommandResult(success=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMANDOS DE UI/TEMAS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _cmd_themes(self, args: str) -> CommandResult:
        """Gestiona los temas visuales"""
        if not HAS_THEMES:
            print(f"\n{C.YELLOW}⚠️  Sistema de temas no disponible{C.RESET}")
            print(f"   {C.DIM}Asegúrate de tener ui/themes.py{C.RESET}\n")
            return CommandResult(success=True)
        
        if not args:
            print(f"\n{C.NVIDIA_GREEN}🎨 TEMAS DISPONIBLES{C.RESET}\n")
            
            themes = list_themes()
            tm = get_theme_manager()
            
            for name, theme in themes.items():
                color = tm.rgb_to_ansi(theme.primary)
                marker = f" {C.GREEN}◄ actual{C.RESET}" if name == tm.current_theme_name else ""
                print(f"  {color}■{C.RESET} {name:12} {C.DIM}{theme.description}{C.RESET}{marker}")
            
            print(f"\n{C.DIM}Uso: /themes <nombre>{C.RESET}\n")
            return CommandResult(success=True)
        
        theme_name = args.strip().lower()
        if set_theme(theme_name):
            os.system('cls' if os.name == 'nt' else 'clear')
            print_logo()
            print(f"{C.BRIGHT_GREEN}✅ Tema cambiado: {theme_name}{C.RESET}\n")
            return CommandResult(success=True)
        
        return CommandResult(success=False, message=f"Tema no encontrado: {theme_name}")
    
    def _cmd_logo(self, args: str) -> CommandResult:
        """Cambia el estilo del logo"""
        styles = ['default', 'eye', 'minimal', 'heavy', 'cyber']
        
        if not args:
            print(f"\n{C.NVIDIA_GREEN}🖼️  ESTILOS DE LOGO{C.RESET}\n")
            for s in styles:
                print(f"  • {s}")
            print(f"\n{C.DIM}Uso: /logo <estilo>{C.RESET}\n")
            return CommandResult(success=True)
        
        style = args.strip().lower()
        if style in styles:
            os.system('cls' if os.name == 'nt' else 'clear')
            print_logo(style)
            return CommandResult(success=True)
        
        return CommandResult(success=False, message=f"Estilo no válido: {style}")
    
    def _cmd_colors(self, args: str) -> CommandResult:
        """Muestra la paleta de colores actual"""
        print(f"\n{C.NVIDIA_GREEN}🎨 PALETA DE COLORES{C.RESET}\n")
        
        colors = [
            ('NVIDIA Green', C.NVIDIA_GREEN),
            ('Bright Green', C.BRIGHT_GREEN),
            ('Bright Cyan', C.BRIGHT_CYAN),
            ('Bright Yellow', C.BRIGHT_YELLOW),
            ('Bright Magenta', C.BRIGHT_MAGENTA),
            ('Bright Red', C.BRIGHT_RED),
            ('Bright White', C.BRIGHT_WHITE),
            ('Dim', C.DIM),
        ]
        
        for name, color in colors:
            print(f"  {color}████{C.RESET} {name}")
        
        print()
        return CommandResult(success=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMANDOS DE DEBUG
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _cmd_debug(self, args: str) -> CommandResult:
        """Activa/desactiva el modo debug"""
        # Por implementar: toggle debug mode
        print(f"\n{C.DIM}🔧 Modo debug: no implementado aún{C.RESET}\n")
        return CommandResult(success=True)
    
    def _cmd_stats(self, args: str) -> CommandResult:
        """Muestra estadísticas detalladas"""
        stats = self.agent.conversation.get_stats()
        
        print(f"\n{C.NVIDIA_GREEN}═══ ESTADÍSTICAS DETALLADAS ═══{C.RESET}\n")
        
        print(f"  {C.BRIGHT_CYAN}Conversación:{C.RESET}")
        print(f"    • Total mensajes: {stats.get('total_messages', 0)}")
        print(f"    • Mensajes usuario: {stats.get('user_messages', 0)}")
        print(f"    • Mensajes asistente: {stats.get('assistant_messages', 0)}")
        print(f"    • Llamadas a herramientas: {stats.get('tool_calls', 0)}")
        
        print(f"\n  {C.BRIGHT_CYAN}Sesión:{C.RESET}")
        print(f"    • Modelo: {self.agent.current_model.name}")
        print(f"    • Directorio: {self.agent.working_directory}")
        print(f"    • Heavy Mode: {'Sí' if self.agent.heavy_mode else 'No'}")
        
        print()
        return CommandResult(success=True)


class NVIDIACodeAgent:
    """
    Agente de programación principal de NVIDIA Code.
    
    Características:
    - Soporte multi-modelo (NVIDIA, DeepSeek, Qwen, etc.)
    - Sistema de herramientas extensible
    - Modo Heavy Agent para tareas complejas
    - Gestión avanzada de conversaciones
    - Temas visuales personalizables
    """
    
    def __init__(
        self,
        initial_model: str = "1",
        working_directory: str = None,
        stream: bool = True,
        heavy_mode: bool = False,
        auto_mode: bool = False
    ):
        """
        Inicializa el agente.
        
        Args:
            initial_model: ID o número del modelo inicial
            working_directory: Directorio de trabajo (default: cwd)
            stream: Habilitar streaming de respuestas
            heavy_mode: Habilitar modo Heavy Agent
            auto_mode: Habilitar modo automático
        """
        # Componentes principales
        self.api_client = NVIDIAAPIClient()
        self.registry = ModelRegistry()
        self.conversation = ConversationManager()
        self.heavy_agent = HeavyAgent(self.api_client)
        self.tool_display = ToolDisplayManager()
        
        # Configuración
        self.current_model = self.registry.get(initial_model) or self.registry.get("1")
        self.working_directory = Path(working_directory or os.getcwd()).resolve()
        self.stream = stream
        self.heavy_mode = heavy_mode
        self.auto_mode = auto_mode
        
        # Estado
        self.state = AgentState.IDLE
        self._session_start = datetime.now()
        
        # Inicializar manejador de comandos
        self.command_handler = CommandHandler(self)
        
        # Cambiar al directorio de trabajo
        os.chdir(self.working_directory)
        
        # Construir system prompt
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """
        Construye el prompt del sistema con instrucciones detalladas.
        
        Returns:
            String con el prompt del sistema
        """
        tools_list = ", ".join(sorted(ToolRegistry.list_names())[:15])
        
        return f"""Eres NVIDIA Code, un agente de programación experto y asistente técnico avanzado.

═══════════════════════════════════════════════════════════════════════════════
INFORMACIÓN DEL SISTEMA
═══════════════════════════════════════════════════════════════════════════════
• Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• Directorio de trabajo: {self.working_directory}
• Sistema operativo: {sys.platform}
• Python: {sys.version.split()[0]}
• Modelo actual: {self.current_model.name}
• Herramientas disponibles: {tools_list}

═══════════════════════════════════════════════════════════════════════════════
REGLAS Y DIRECTIVAS
═══════════════════════════════════════════════════════════════════════════════
1. CÓDIGO COMPLETO: Siempre muestra código completo y funcional.
   - NUNCA uses "..." o "// resto del código"
   - NUNCA omitas partes importantes
   - Si el código es muy largo, divídelo en secciones claras

2. USO DE HERRAMIENTAS: Úsalas activamente para:
   - Leer/escribir archivos
   - Ejecutar comandos
   - Buscar en la web
   - Analizar el sistema

3. RESPUESTAS OBLIGATORIAS:
   - SIEMPRE analiza y explica los resultados de las herramientas
   - NUNCA te quedes sin responder después de usar una herramienta
   - Si una herramienta falla, explica el error y sugiere alternativas

4. FORMATO:
   - Responde en español
   - Usa markdown para formatear
   - Sé conciso pero completo
   - Incluye ejemplos cuando sea útil

5. SEGURIDAD:
   - Advierte sobre operaciones peligrosas
   - Pide confirmación para eliminar archivos
   - No ejecutes código malicioso

═══════════════════════════════════════════════════════════════════════════════
FLUJO DE TRABAJO
═══════════════════════════════════════════════════════════════════════════════
1. Analiza la solicitud del usuario
2. Si necesitas información: usa las herramientas apropiadas
3. Procesa los resultados de las herramientas
4. Proporciona una respuesta clara y útil
5. Sugiere siguientes pasos si es apropiado
"""
    
    def chat(self, user_input: str) -> str:
        """
        Procesa un mensaje del usuario y genera una respuesta.
        
        Args:
            user_input: Mensaje del usuario
            
        Returns:
            Respuesta del agente
        """
        # Cambiar estado
        self.state = AgentState.PROCESSING
        
        # Modo Heavy Agent
        if self.heavy_mode:
            self.state = AgentState.HEAVY_MODE
            response = self.heavy_agent.process(
                user_input,
                self.system_prompt,
                self.conversation.get_api_messages()
            )
            self.state = AgentState.IDLE
            return response
        
        # Agregar mensaje del usuario
        self.conversation.add_user_message(user_input)
        
        # Preparar herramientas si el modelo las soporta
        tools = None
        if self.current_model.supports_tools:
            tools = ToolRegistry.to_openai_format()
        
        # Variables de control del loop
        iteration = 0
        final_response = ""
        tool_was_used = False
        last_tool_results: List[ToolExecutionResult] = []
        
        # Loop principal de procesamiento
        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1
            
            # Obtener mensajes para la API
            messages = self.conversation.get_api_messages(self.system_prompt)
            
            # Llamar a la API
            try:
                response = self.api_client.chat(
                    messages=messages,
                    model=self.current_model,
                    tools=tools,
                    stream=self.stream
                )
            except Exception as e:
                error_msg = self._format_error(e)
                print(f"{C.RED}{error_msg}{C.RESET}")
                self.conversation.add_assistant_message(error_msg)
                self.state = AgentState.ERROR
                return error_msg
            
            # Verificar errores en la respuesta
            if response.content and response.content.startswith("[Error]"):
                self.conversation.add_assistant_message(response.content)
                self.state = AgentState.ERROR
                return response.content
            
            # Procesar llamadas a herramientas
            if response.tool_calls:
                tool_was_used = True
                self.state = AgentState.WAITING_TOOLS
                
                # Limitar herramientas por iteración
                tool_calls = response.tool_calls[:MAX_TOOLS_PER_ITERATION]
                
                if len(response.tool_calls) > MAX_TOOLS_PER_ITERATION:
                    print(f"{C.YELLOW}⚠️  Limitando a {MAX_TOOLS_PER_ITERATION} herramientas{C.RESET}")
                
                # Registrar mensaje con tool calls
                self.conversation.add_assistant_message(
                    response.content or "",
                    tool_calls=tool_calls
                )
                
                # Ejecutar cada herramienta
                for tc in tool_calls:
                    result = self._execute_tool_call(tc)
                    last_tool_results.append(result)
                
                # Continuar el loop para procesar resultados
                continue
            
            # Sin tool calls - procesar respuesta normal
            else:
                # Fix para modelos que no responden después de tools
                if tool_was_used and not response.content:
                    final_response = self._handle_empty_response(last_tool_results)
                else:
                    final_response = response.content or ""
                
                if final_response:
                    self.conversation.add_assistant_message(final_response)
                
                break
        
        # Fallback si salió del loop sin respuesta
        if not final_response and tool_was_used:
            final_response = self._generate_fallback_response(last_tool_results)
            self.conversation.add_assistant_message(final_response)
        
        self.state = AgentState.IDLE
        return final_response
    
    def _execute_tool_call(self, tool_call: Dict[str, Any]) -> ToolExecutionResult:
        """
        Ejecuta una llamada a herramienta.
        
        Args:
            tool_call: Diccionario con la información de la llamada
            
        Returns:
            ToolExecutionResult con el resultado
        """
        tool_name = tool_call.get('function', {}).get('name', '')
        tool_id = tool_call.get('id', f'call_{tool_name}')
        
        if not tool_name:
            return ToolExecutionResult(
                tool_name="unknown",
                success=False,
                result="",
                elapsed_time=0,
                error_message="Nombre de herramienta vacío"
            )
        
        # Parsear argumentos
        try:
            args_str = tool_call.get('function', {}).get('arguments', '{}')
            tool_args = json.loads(args_str) if args_str else {}
        except json.JSONDecodeError as e:
            error_msg = f"JSON inválido: {str(e)[:50]}"
            self.tool_display.print_box_start()
            self.tool_display.print_error(tool_name, {}, error_msg)
            self.tool_display.print_box_end()
            
            self.conversation.add_tool_result(
                tool_call_id=tool_id,
                name=tool_name,
                content=f"[Error] {error_msg}"
            )
            
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                result="",
                elapsed_time=0,
                error_message=error_msg,
                arguments={}
            )
        
        # Verificar que la herramienta existe
        if not ToolRegistry.has_tool(tool_name):
            error_msg = f"Herramienta no encontrada: {tool_name}"
            self.tool_display.print_box_start()
            self.tool_display.print_error(tool_name, tool_args, error_msg)
            self.tool_display.print_box_end()
            
            self.conversation.add_tool_result(
                tool_call_id=tool_id,
                name=tool_name,
                content=f"[Error] {error_msg}"
            )
            
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                result="",
                elapsed_time=0,
                error_message=error_msg,
                arguments=tool_args
            )
        
        # Validar parámetros
        tool = ToolRegistry.get(tool_name)
        if tool and hasattr(tool, 'validate_params'):
            if not tool.validate_params(**tool_args):
                missing = [p for p, param in tool.parameters.items() 
                          if param.required and p not in tool_args]
                error_msg = f"Faltan parámetros: {', '.join(missing)}"
                
                self.tool_display.print_box_start()
                self.tool_display.print_error(tool_name, tool_args, error_msg)
                self.tool_display.print_box_end()
                
                self.conversation.add_tool_result(
                    tool_call_id=tool_id,
                    name=tool_name,
                    content=f"[Error] {error_msg}"
                )
                
                return ToolExecutionResult(
                    tool_name=tool_name,
                    success=False,
                    result="",
                    elapsed_time=0,
                    error_message=error_msg,
                    arguments=tool_args
                )
        
        # Mostrar estado pendiente
        self.tool_display.print_pending(tool_name, tool_args)
        
        # Ejecutar herramienta
        start_time = time.time()
        
        try:
            tool_result = ToolRegistry.execute(tool_name, **tool_args)
            elapsed = time.time() - start_time
            
            # Asegurar que el resultado es string
            if not isinstance(tool_result, str):
                tool_result = str(tool_result)
            
            # Verificar si hubo error en la ejecución
            is_error = tool_result.startswith("[x]") or tool_result.startswith("[Error]")
            
            if is_error:
                error_preview = tool_result.replace("[x]", "").replace("[Error]", "").strip()[:60]
                self.tool_display.print_error(tool_name, tool_args, error_preview)
                self.tool_display.print_box_end()
                
                result = ToolExecutionResult(
                    tool_name=tool_name,
                    success=False,
                    result=tool_result,
                    elapsed_time=elapsed,
                    error_message=error_preview,
                    arguments=tool_args
                )
            else:
                result_size = len(tool_result)
                self.tool_display.print_success(tool_name, tool_args, elapsed, result_size)
                
                # Mostrar preview si es largo
                if result_size > 200:
                    self.tool_display.print_result_preview(tool_result)
                
                self.tool_display.print_box_end()
                
                result = ToolExecutionResult(
                    tool_name=tool_name,
                    success=True,
                    result=tool_result,
                    elapsed_time=elapsed,
                    arguments=tool_args
                )
            
        except TypeError as e:
            elapsed = time.time() - start_time
            error_msg = str(e)[:60]
            self.tool_display.print_error(tool_name, tool_args, error_msg)
            self.tool_display.print_box_end()
            
            result = ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                result="",
                elapsed_time=elapsed,
                error_message=error_msg,
                arguments=tool_args
            )
            tool_result = f"[Error] {error_msg}"
            
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = f"{type(e).__name__}: {str(e)[:50]}"
            self.tool_display.print_error(tool_name, tool_args, error_msg)
            self.tool_display.print_box_end()
            
            result = ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                result="",
                elapsed_time=elapsed,
                error_message=error_msg,
                arguments=tool_args
            )
            tool_result = f"[Error] {error_msg}"
        
        # Agregar resultado a la conversación
        self.conversation.add_tool_result(
            tool_call_id=tool_id,
            name=tool_name,
            content=tool_result if 'tool_result' in locals() else result.result
        )
        
        return result
    
    def _handle_empty_response(self, tool_results: List[ToolExecutionResult]) -> str:
        """
        Maneja el caso cuando el modelo no responde después de usar tools.
        
        Args:
            tool_results: Lista de resultados de herramientas
            
        Returns:
            Respuesta generada
        """
        print(f"{C.DIM}(Analizando resultados...){C.RESET}")
        
        # Pedir continuación al modelo
        self.conversation.add_user_message(
            "Analiza los resultados de las herramientas y proporciona tu respuesta al usuario."
        )
        
        try:
            continuation = self.api_client.chat(
                messages=self.conversation.get_api_messages(self.system_prompt),
                model=self.current_model,
                tools=None,  # Sin herramientas para forzar respuesta de texto
                stream=self.stream
            )
            
            if continuation.content and not continuation.content.startswith("[Error]"):
                return continuation.content
            else:
                return self._generate_fallback_response(tool_results)
                
        except Exception as e:
            print(f"{C.RED}Error obteniendo continuación: {e}{C.RESET}")
            return self._generate_fallback_response(tool_results)
    
    def _generate_fallback_response(self, tool_results: List[ToolExecutionResult]) -> str:
        """
        Genera una respuesta de fallback cuando el modelo falla.
        
        Args:
            tool_results: Lista de resultados de herramientas
            
        Returns:
            Respuesta formateada
        """
        if not tool_results:
            return "He procesado tu solicitud."
        
        response_parts = ["📊 **Resultados obtenidos:**\n"]
        
        for result in tool_results:
            status = "✅" if result.success else "❌"
            response_parts.append(f"\n**{status} {result.tool_name}:**")
            
            if result.success:
                preview = result.result_preview
                response_parts.append(f"```\n{preview}\n```")
            else:
                response_parts.append(f"*Error: {result.error_message}*")
        
        response_parts.append("\n¿Qué te gustaría que analice o haga con esta información?")
        
        return "\n".join(response_parts)
    
    def _format_error(self, error: Exception) -> str:
        """Formatea un error para mostrar al usuario"""
        error_type = type(error).__name__
        error_msg = str(error)[:200]
        return f"[Error] {error_type}: {error_msg}"
    
    def run(self):
        """
        Ejecuta el agente en modo interactivo.
        
        Este método inicia el loop principal de interacción con el usuario.
        """
        # Limpiar pantalla y mostrar logo
        os.system('cls' if os.name == 'nt' else 'clear')
        print_logo()
        self._print_welcome()
        
        # Loop principal
        while True:
            try:
                prompt = self._build_prompt()
                user_input = input(prompt).strip()
                
                if not user_input:
                    continue
                
                # Comandos de continuación
                if user_input.lower() in ['continua', 'continúa', 'continue', 'sigue', 'c']:
                    user_input = "Continúa con tu respuesta anterior."
                
                # Procesar comandos
                if user_input.startswith('/'):
                    result = self.command_handler.execute(user_input)
                    if not result.success and result.message:
                        print(f"{C.RED}{result.message}{C.RESET}")
                    continue
                
                # Procesar mensaje normal
                self.chat(user_input)
                
            except KeyboardInterrupt:
                print(f"\n{C.YELLOW}Usa /exit para salir{C.RESET}")
            except EOFError:
                break
            except Exception as e:
                print(f"{C.RED}Error inesperado: {e}{C.RESET}")
    
    def _build_prompt(self) -> str:
        """Construye el prompt de entrada"""
        # Obtener color del tema
        prompt_color = C.NVIDIA_GREEN
        if HAS_THEMES:
            try:
                tm = get_theme_manager()
                prompt_color = tm.rgb_to_ansi(tm.current_theme.primary)
            except:
                pass
        
        # Indicadores de modo
        mode_indicators = []
        if self.heavy_mode:
            mode_indicators.append(f"{C.BRIGHT_MAGENTA}🔥{C.RESET}")
        if self.auto_mode:
            mode_indicators.append(f"{C.BRIGHT_GREEN}🤖{C.RESET}")
        
        mode_str = " " + " ".join(mode_indicators) if mode_indicators else ""
        
        # Nombre del modelo
        model_display = f"{C.BOLD}{self.current_model.name}{C.RESET}"
        
        # Construir prompt en dos líneas
        line1 = f"\n{prompt_color}┌─{C.RESET} {model_display}{mode_str} {prompt_color}─{C.RESET}"
        line2 = f"{prompt_color}└─>{C.RESET} "
        
        return f"{line1}\n{line2}"
    
    def _print_welcome(self):
        """Muestra mensaje de bienvenida"""
        # Obtener colores del tema
        try:
            if HAS_THEMES:
                theme = get_current_theme()
                tm = get_theme_manager()
                primary = tm.rgb_to_ansi(theme.primary)
            else:
                primary = C.NVIDIA_GREEN
        except:
            primary = C.NVIDIA_GREEN
        
        width = 68
        
        print(f"\n{primary}╔{'═' * width}╗{C.RESET}")
        
        # Directorio
        dir_str = str(self.working_directory)
        if len(dir_str) > 50:
            dir_str = "..." + dir_str[-47:]
        dir_line = f"📂 Directorio: {C.BRIGHT_WHITE}{dir_str}{C.RESET}"
        print(f"{primary}║{C.RESET} {dir_line}{' ' * (width - len(dir_str) - 16)}{primary}║{C.RESET}")
        
        # Modelo
        model_str = f"{self.current_model.name} {self.current_model.specialty}"
        if len(model_str) > 50:
            model_str = model_str[:47] + "..."
        model_line = f"🤖 Modelo: {C.BRIGHT_CYAN}{self.current_model.name}{C.RESET} {self.current_model.specialty}"
        padding = width - len(self.current_model.name) - len(self.current_model.specialty) - 13
        print(f"{primary}║{C.RESET} {model_line}{' ' * max(0, padding)}{primary}║{C.RESET}")
        
        # Modo Heavy si está activo
        if self.heavy_mode:
            heavy_line = f"🔥 Modo: {C.BRIGHT_MAGENTA}Heavy Agent (Multi-IA){C.RESET}"
            print(f"{primary}║{C.RESET} {heavy_line}{' ' * 32}{primary}║{C.RESET}")
        
        # Tip
        tip_line = f"{C.DIM}💡 /help para comandos | /themes para temas{C.RESET}"
        print(f"{primary}║{C.RESET} {tip_line}{' ' * 23}{primary}║{C.RESET}")
        
        print(f"{primary}╚{'═' * width}╝{C.RESET}\n")
    
    def __len__(self) -> int:
        """Retorna el número de mensajes en la conversación"""
        return len(self.conversation)
    
    def __repr__(self) -> str:
        """Representación del agente"""
        return (f"NVIDIACodeAgent(model={self.current_model.name}, "
                f"messages={len(self)}, heavy={self.heavy_mode})")


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE UTILIDAD
# ═══════════════════════════════════════════════════════════════════════════════

def create_agent(
    model: str = "1",
    directory: str = None,
    heavy: bool = False
) -> NVIDIACodeAgent:
    """
    Factory function para crear un agente con configuración personalizada.
    
    Args:
        model: ID o número del modelo
        directory: Directorio de trabajo
        heavy: Activar modo Heavy Agent
        
    Returns:
        Instancia de NVIDIACodeAgent configurada
    """
    return NVIDIACodeAgent(
        initial_model=model,
        working_directory=directory,
        heavy_mode=heavy
    )


def quick_chat(message: str, model: str = "1") -> str:
    """
    Función rápida para enviar un mensaje y obtener respuesta.
    
    Args:
        message: Mensaje a enviar
        model: Modelo a usar
        
    Returns:
        Respuesta del modelo
    """
    agent = NVIDIACodeAgent(initial_model=model, stream=False)
    return agent.chat(message)


# ═══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NVIDIA Code Agent")
    parser.add_argument("-m", "--model", default="1", help="Modelo inicial")
    parser.add_argument("-d", "--directory", default=None, help="Directorio de trabajo")
    parser.add_argument("--heavy", action="store_true", help="Activar Heavy Agent")
    parser.add_argument("--no-stream", action="store_true", help="Desactivar streaming")
    
    args = parser.parse_args()
    
    agent = NVIDIACodeAgent(
        initial_model=args.model,
        working_directory=args.directory,
        stream=not args.no_stream,
        heavy_mode=args.heavy
    )
    
    agent.run()