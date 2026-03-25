"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     OPENCLAW - Agente Autónomo v2.1                          ║
║                                                                              ║
║  Refactorizado en múltiples archivos para mejor mantenimiento.               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import threading
import asyncio
import traceback
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Credenciales - deben estar en .env o variables de entorno
_DEFAULTS = {
    "NVIDIA_API_KEY":  "TU_NVIDIA_API_KEY_AQUI",
    "DISCORD_TOKEN":   "TU_DISCORD_TOKEN_AQUI",
}
for _k, _v in _DEFAULTS.items():
    if not os.environ.get(_k):
        os.environ[_k] = _v

# Importar componentes locales
from .logger import logger
from .types import (
    OpenClawState, ChannelType, TaskPriority,
    OpenClawMessage, OpenClawResponse, AutonomousTask,
    Skill, SkillPlugin
)
from .resilience import RateLimiter
from .parsers import ToolCallParser, ResponseSanitizer
from .memory import OpenClawMemory
from .selector import ModelSelector
from .skills import SkillsManager
from .engine import AutonomousEngine
from .metrics import MetricsCollector
from .discord_bot import DiscordBot, DISCORD_AVAILABLE

# ============================================================================
# IMPORTS CON FALLBACK ROBUSTO
# ============================================================================

_root_dir = Path(__file__).parent.parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

# Flags de disponibilidad y constantes globales
_HAS_CONFIG = False
_HAS_MODELS = False
_HAS_TOOLS = False
_HAS_UI = False

try:
    from config import API_KEY, API_BASE_URL, MAX_TOKENS
    _HAS_CONFIG = True
except ImportError:
    API_KEY = os.environ.get('NVIDIA_API_KEY') or os.environ.get('API_KEY')
    API_BASE_URL = os.environ.get(
        'API_BASE_URL',
        'https://integrate.api.nvidia.com/v1/chat/completions'
    )
    MAX_TOKENS = int(os.environ.get('MAX_TOKENS', '16384'))
    logger.warning("Config module not found, using environment variables")

try:
    from models.registry import ModelRegistry, AVAILABLE_MODELS, ModelInfo
    _HAS_MODELS = True
except ImportError:
    ModelRegistry = None
    AVAILABLE_MODELS = {}
    ModelInfo = None
    logger.warning("Models registry not found")

try:
    from tools import ToolRegistry
    from tools.base import BaseTool
    _HAS_TOOLS = True
except ImportError:
    ToolRegistry = None
    BaseTool = None
    logger.warning("Tools registry not found")

try:
    from ui.colors import Colors
    from ui.markdown import render_markdown
    _HAS_UI = True
except ImportError:
    class Colors:
        def __getattr__(self, name): return ""
    def render_markdown(text): return text
    logger.warning("UI module not found, using plain text")

C = Colors()

# ============================================================================
# OPENCLAW AGENT PRINCIPAL v2.1
# ============================================================================

class OpenClawAgent:
    """Agente OpenClaw v2.1 - Autónomo, robusto y extensible"""

    VERSION = "2.1.0"

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

        # Componentes principales
        self.registry = ModelRegistry() if ModelRegistry else None
        self.tool_registry = ToolRegistry() if ToolRegistry else None
        self.model_selector = ModelSelector(self.registry)
        self.memory = OpenClawMemory(
            self.config.get('memory_path', 'openclaw_memory.json')
        )
        self.skills = SkillsManager(self.tool_registry)
        self.metrics = MetricsCollector()
        self.autonomous_engine = AutonomousEngine(self)

        # Parsers y sanitizers
        self.tool_call_parser = ToolCallParser()
        self.response_sanitizer = ResponseSanitizer()

        # Estado
        self._state_lock = threading.Lock()
        self._state = OpenClawState.IDLE
        self.current_model: Optional[Any] = None
        self.current_channel: ChannelType = ChannelType.CONSOLE

        # Event loop dedicado para async
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_thread: Optional[threading.Thread] = None

        # Rate limiter global
        self.rate_limiter = RateLimiter(
            max_calls=self.config.get('rate_limit', 60),
            window_seconds=60.0
        )

        # Discord
        self.discord_bot: Optional[DiscordBot] = None

        # Thread pool
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.get('max_workers', 4),
            thread_name_prefix="openclaw-worker"
        )

        # API Client lazy
        self._api_client = None

        # Running flag
        self._running = False

        # Inicializar
        self._init_default_model()
        self._start_async_loop()

    @property
    def state(self) -> OpenClawState:
        with self._state_lock:
            return self._state

    @state.setter
    def state(self, value: OpenClawState):
        with self._state_lock:
            old = self._state
            self._state = value
            if old != value:
                logger.debug(f"State: {old.value} -> {value.value}")
                self.metrics.set_gauge('state', hash(value.value))

    def _init_default_model(self):
        """Inicializa el modelo por defecto"""
        if not AVAILABLE_MODELS:
            logger.warning("No models available")
            return

        for key, model in AVAILABLE_MODELS.items():
            has_thinking = hasattr(model, 'thinking') and model.thinking
            has_tools = hasattr(model, 'supports_tools') and model.supports_tools
            if has_thinking and has_tools:
                self.current_model = model
                self.model_selector.current_model = model
                return

        for key, model in AVAILABLE_MODELS.items():
            if hasattr(model, 'thinking') and model.thinking:
                self.current_model = model
                self.model_selector.current_model = model
                return

        first_model = list(AVAILABLE_MODELS.values())[0]
        self.current_model = first_model
        self.model_selector.current_model = first_model

    def _start_async_loop(self):
        """Inicia un event loop dedicado en un thread separado"""
        def _run_loop():
            self._async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._async_loop)
            self._async_loop.run_forever()

        self._async_thread = threading.Thread(
            target=_run_loop, daemon=True, name="openclaw-async"
        )
        self._async_thread.start()

        timeout = time.time() + 5.0
        while self._async_loop is None and time.time() < timeout:
            time.sleep(0.01)

    def _run_coroutine(self, coro) -> Any:
        """Ejecuta una coroutine en el event loop dedicado"""
        if self._async_loop is None or self._async_loop.is_closed():
            self._start_async_loop()

        future = asyncio.run_coroutine_threadsafe(coro, self._async_loop)
        return future.result(timeout=300)

    def _get_api_client(self):
        """Obtiene cliente API (lazy init)"""
        if self._api_client is None:
            try:
                from core.api_client import NVIDIAAPIClient
                self._api_client = NVIDIAAPIClient(use_markdown=True)
            except ImportError:
                logger.error("NVIDIAAPIClient not available")
                raise RuntimeError("API client not available")
        return self._api_client

    def _show_tool_execution(self, tool_name: str, args: Dict, result: str = None, status: str = "running"):
        icons = {"running": f"{C.BRIGHT_YELLOW}⏳{C.RESET}", "success": f"{C.BRIGHT_GREEN}✅{C.RESET}", "error": f"{C.BRIGHT_RED}❌{C.RESET}"}
        icon = icons.get(status, "⏳")
        print(f"{C.DIM}  ├─{C.RESET} {icon} {C.BRIGHT_CYAN}{tool_name}{C.RESET}")
        if args:
            display_args = {k: (repr(v)[:37] + "..." if len(repr(v)) > 40 else repr(v)) for k, v in list(args.items())[:3]}
            if display_args:
                print(f"{C.DIM}  │  Args: {' | '.join([f'{k}={v}' for k, v in display_args.items()])}{C.RESET}")
        if result and status != "running":
            preview = result[:120].replace("\n", " ↵ ") + ("..." if len(result) > 120 else "")
            print(f"{C.DIM}  │  → {preview}{C.RESET}")

    def _execute_tool(self, tool_name: str, args: Dict) -> str:
        self.state = OpenClawState.EXECUTING
        self._show_tool_execution(tool_name, args, status="running")
        self.metrics.increment('tools_executed')
        try:
            with self.metrics.timer(f'tool.{tool_name}'):
                if not self.tool_registry: raise RuntimeError("Tool registry not available")
                tool = self.tool_registry.get(tool_name)
                if not tool:
                    normalized = tool_name.lower().replace('-', '_')
                    tool = self.tool_registry.get(normalized)
                    if not tool:
                        try:
                            for t in self.tool_registry.get_all():
                                if t.name.lower().replace('-', '_') == normalized or normalized in t.name.lower():
                                    tool = t; break
                        except Exception: pass
                    if not tool: raise ValueError(f"Tool not found: {tool_name}")
                result = tool.execute(**args)
            self._show_tool_execution(tool_name, args, str(result), status="success")
            self.metrics.increment('tools_succeeded')
            return str(result) if result is not None else "OK"
        except Exception as e:
            msg = f"Error in {tool_name}: {str(e)}"
            self._show_tool_execution(tool_name, args, msg, status="error")
            self.metrics.increment('tools_failed'); logger.error(msg, exc_info=True)
            return msg

    def _process_tool_calls(self, tool_calls: List[Dict]) -> List[Dict]:
        results = []
        if tool_calls:
            print(f"{C.DIM}  │{C.RESET}\n{C.BRIGHT_MAGENTA}  🔧 EJECUTANDO {len(tool_calls)} HERRAMIENTA(S):{C.RESET}\n{C.DIM}  │{C.RESET}")
        for tc in tool_calls:
            func = tc.get('function', {})
            name = func.get('name', 'unknown')
            args_str = func.get('arguments', '{}')
            try: args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError: args = {}
            results.append({'tool_call_id': tc.get('id', f'call_{int(time.time())}'), 'name': name, 'result': self._execute_tool(name, args)})
        if tool_calls: print(f"{C.DIM}  └──────────────────{C.RESET}")
        return results

    def start(self, discord_token: str = None, discord_channels: List[str] = None):
        self._print_banner()
        # Siempre intenta iniciar Discord - lee token del env (ya hardcodeado) si no se pasó
        token = discord_token or os.environ.get('DISCORD_TOKEN')
        if token and DISCORD_AVAILABLE:
            self._init_discord(token, discord_channels)
        elif not DISCORD_AVAILABLE:
            print(f"  ⚠️  discord.py no instalado, canal Discord desactivado")
        self._running = True
        self._run_console()

    def _print_banner(self):
        m_name = getattr(self.current_model, 'name', 'N/A') if self.current_model else 'N/A'
        t_count = len(self.tool_registry.get_all()) if self.tool_registry else 0
        print(f"\n{C.NVIDIA_GREEN}╔══════════════════════════════════════════════════════════════╗{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.BRIGHT_WHITE}           🦞 OPENCLAW - Agente Autónomo v{self.VERSION}              {C.NVIDIA_GREEN}║{C.RESET}")
        print(f"{C.NVIDIA_GREEN}╠══════════════════════════════════════════════════════════════╣{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} 🧠 Modelo:    {C.BRIGHT_CYAN}{m_name}{C.RESET}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} 💭 Thinking:  {'✅' if getattr(self.current_model, 'thinking', False) else '❌'}")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} 🔧 Tools:     {'✅' if getattr(self.current_model, 'supports_tools', False) else '❌'} ({t_count} disponibles)")
        print(f"{C.NVIDIA_GREEN}║{C.RESET} 💾 Memoria:   ✅ ({self.memory.get_stats()['total_messages']} mensajes)")
        print(f"{C.NVIDIA_GREEN}╠══════════════════════════════════════════════════════════════╣{C.RESET}")
        chans = [f"{C.BRIGHT_WHITE}Consola{C.RESET}"] + ([f"{C.BRIGHT_MAGENTA}Discord{C.RESET}"] if DISCORD_AVAILABLE else [])
        print(f"{C.NVIDIA_GREEN}║{C.RESET} 🔌 Canales:   {' | '.join(chans)}\n{C.NVIDIA_GREEN}║{C.RESET}\n{C.NVIDIA_GREEN}║{C.RESET} 💬 Escribe {C.BRIGHT_WHITE}'ayuda'{C.RESET} para ver comandos\n{C.NVIDIA_GREEN}╚══════════════════════════════════════════════════════════════╝{C.RESET}\n")

    def _init_discord(self, token: str = None, channels: List[str] = None):
        token = token or os.environ.get('DISCORD_TOKEN')
        if not token:
            print("  ⚠️  DISCORD_TOKEN no encontrado, Discord desactivado")
            return
        self.discord_bot = DiscordBot(self, token, channels)
        if self.discord_bot.is_available():
            self.discord_bot.run_in_thread()
            print(f"{C.BRIGHT_MAGENTA}  [Discord] Bot iniciando con token ...{token[-8:]}{C.RESET}")


    def _run_console(self):
        print(f"{C.DIM}  Ctrl+C para salir{C.RESET}\n")
        auto_wait = False
        try:
            while self._running:
                try:
                    prompt = f"{C.BRIGHT_YELLOW}┌─🦞 Objetivo" if auto_wait else f"{C.NVIDIA_GREEN}┌─{C.BRIGHT_WHITE}Tú"
                    user_input = input(f"{prompt}{C.NVIDIA_GREEN}──▶ {C.RESET}")
                    if not user_input.strip(): continue
                    if user_input.strip().lower() in ('exit', 'quit', 'salir', 'q'): break
                    if auto_wait:
                        if user_input.strip().lower() in ('cancelar', 'cancel', 'parar', 'stop', 'no'):
                            auto_wait = False; self.state = OpenClawState.IDLE; continue
                        auto_wait = False
                        print(f"\n{C.BRIGHT_CYAN}🦞 Iniciando tarea autónoma...{C.RESET}\n")
                        task = self._run_coroutine(self.run_autonomous_task(user_input.strip()))
                        print(f"\n{C.BRIGHT_GREEN}✅ Tarea completada: {task.status}{C.RESET}")
                        continue
                    msg = OpenClawMessage(content=user_input, channel=ChannelType.CONSOLE, user_id="console_user", channel_id="console")
                    resp = self._process_message_sync(msg)
                    if resp.autonomous: auto_wait = True
                    self._display_response(resp)
                except EOFError: break
                except KeyboardInterrupt:
                    if auto_wait: auto_wait = False; self.state = OpenClawState.IDLE; continue
                    break
        finally: self.shutdown()

    def _process_message_sync(self, message: OpenClawMessage) -> OpenClawResponse:
        return self._run_coroutine(self._process_message_async_internal(message))

    async def _process_message_async_internal(self, message: OpenClawMessage) -> OpenClawResponse:
        start_time = time.time(); self.state = OpenClawState.THINKING; self.metrics.increment('messages_received')
        self.memory.add_message(message.channel_id, 'user', message.content, metadata={'user_id': message.user_id})
        try:
            skill_res = self.skills.match_skill(message.content)
            if skill_res:
                skill, _ = skill_res
                res = skill.action(message.content, {'model_selector': self.model_selector, 'current_model': self.current_model, 'memory': self.memory, 'channel_id': message.channel_id, 'agent': self})
                if res == "__AUTONOMOUS_MODE__": return await self._handle_autonomous_request(message)
                resp = OpenClawResponse(content=res, channel=message.channel, elapsed_time=time.time() - start_time)
                self.memory.add_message(message.channel_id, 'assistant', res); self.metrics.increment('skills_executed'); self.state = OpenClawState.IDLE
                return resp
            task_type = self.model_selector.detect_task_type(message.content)
            if not self.current_model: self.current_model = self.model_selector.select_best_model(task_type)
            if not self.current_model: return OpenClawResponse(content="❌ No hay modelos disponibles", channel=message.channel, error="No models available")
            ctx = self.memory.get_context(message.channel_id)
            res_content, collected_files = await self._call_model_with_retry(message.content, ctx, message.channel_id, task_type)
            clean, think = ResponseSanitizer.extract_thinking(res_content)
            resp = OpenClawResponse(content=clean, channel=message.channel, thinking=think, model_used=getattr(self.current_model, 'id', ''), elapsed_time=time.time() - start_time, files=collected_files)
            self.memory.add_message(message.channel_id, 'assistant', clean, getattr(self.current_model, 'id', ''))
            self.metrics.increment('messages_responded'); self.metrics.record_timing('response_time', resp.elapsed_time); self.state = OpenClawState.IDLE
            return resp
        except Exception as e:
            self.state = OpenClawState.ERROR; logger.error(f"Error: {e}", exc_info=True); self.metrics.increment('errors')
            return OpenClawResponse(content=f"❌ Error: {e}", channel=message.channel, error=str(e), elapsed_time=time.time() - start_time)

    async def _handle_autonomous_request(self, message: OpenClawMessage) -> OpenClawResponse:
        self.state = OpenClawState.AUTONOMOUS
        return OpenClawResponse(content="🦞 **Modo Autónomo Activado**\n\nEstoy listo para trabajar.\n\n📝 **¿Cuál es tu objetivo?**", channel=message.channel, autonomous=True)

    async def run_autonomous_task(self, objective: str, channel_id: str = "autonomous") -> AutonomousTask:
        def on_step(evt, data):
            if evt == "plan":
                print(f"\n{C.BRIGHT_CYAN}📋 PLAN:{C.RESET}")
                for i, s in enumerate(data, 1): print(f"{C.DIM}  {i}. {s}{C.RESET}")
                print()
            elif evt == "step":
                print(f"{C.BRIGHT_GREEN}✅ Paso {data['step_num']}/{data['total']}: {data['description']}{C.RESET}")
                print(f"{C.DIM}   → {str(data['result'])[:200]}{C.RESET}\n")
        return await self.autonomous_engine.execute_task(objective, channel_id, on_step_complete=on_step)

    async def _call_model_with_retry(self, message: str, context: List[Dict], channel_id: str, task_type: str = 'general', max_retries: int = 2) -> tuple:
        last_err, tried = None, set()
        for attempt in range(max_retries + 1):
            if not self.current_model: return "❌ No hay modelo", []
            mid = getattr(self.current_model, 'id', 'unknown'); tried.add(mid)
            try: return await self._call_model(message, context, channel_id)
            except Exception as e:
                last_err = e; self.model_selector.record_result(mid, False, 0, str(e))
                if attempt < max_retries:
                    fallback = self.model_selector.get_fallback_model(mid, task_type)
                    if fallback and getattr(fallback, 'id', 'unknown') not in tried:
                        self.current_model = fallback; print(f"{C.BRIGHT_YELLOW}  ⚠️ Cambiando a fallback: {getattr(fallback, 'name', fallback.id)}{C.RESET}"); continue
        raise RuntimeError(f"Falla total: {last_err}")

    async def _call_model(self, message: str, context: List[Dict], channel_id: str = "default", allow_tools: bool = True) -> tuple:
        """Retorna (texto_final, lista_de_archivos)"""
        if not self.current_model: return "No hay modelo", []
        if not self.rate_limiter.acquire(timeout=10.0): return "⏳ Rate limit", []
        client = self._get_api_client(); mid = getattr(self.current_model, 'id', 'unknown')
        msgs = self._build_messages(message, context)
        it, max_it, final_content = 0, 5, ""
        collected_files = []  # archivos recolectados de tool results
        import re as _re
        _file_re = _re.compile(r'\[FILE:([^\]]+)\]')
        while it < max_it:
            it += 1; tools = self.tool_registry.to_openai_format() if (allow_tools and getattr(self.current_model, 'supports_tools', False) and self.tool_registry) else None
            print(f"{C.DIM}  │{C.RESET}\n{C.BRIGHT_CYAN}  🧠 {'Pensando' if it==1 else 'Procesando'} con {getattr(self.current_model, 'name', mid)}...{C.RESET}")
            st = time.time()
            try:
                resp = client.chat(messages=msgs, model=self.current_model, tools=tools, stream=True, max_tokens=MAX_TOKENS, temperature=getattr(self.current_model, 'temperature', 0.6))
                self.model_selector.record_result(mid, True, time.time() - st); self.metrics.record_timing('model_call', time.time()-st)
                cont = getattr(resp, 'content', '') or ''
                clean, think = ResponseSanitizer.extract_thinking(cont)
                if think: cont = clean
                t_calls = getattr(resp, 'tool_calls', []) or []
                text_t_calls = []
                if cont and ToolCallParser.has_tool_calls(cont): cont, text_t_calls = ToolCallParser.parse_from_text(cont)
                all_t_calls = []
                for tc in t_calls: all_t_calls.append(tc if isinstance(tc, dict) else {'id': getattr(tc, 'id', f'c_{int(time.time())}'), 'type': 'function', 'function': {'name': getattr(getattr(tc, 'function', tc), 'name', 'unknown'), 'arguments': getattr(getattr(tc, 'function', tc), 'arguments', '{}')}})
                all_t_calls.extend(text_t_calls)
                if all_t_calls:
                    ass_msg = {"role": "assistant", "content": cont or ""}
                    if t_calls: ass_msg['tool_calls'] = all_t_calls[:len(t_calls)]
                    msgs.append(ass_msg)
                    for tr in self._process_tool_calls(all_t_calls):
                        result_str = str(tr['result'])[:4000]
                        # Extraer [FILE:...] tags de resultados de tools
                        for fpath in _file_re.findall(result_str):
                            collected_files.append(fpath.strip())
                        msgs.append({"role": "tool", "tool_call_id": tr['tool_call_id'], "name": tr['name'], "content": result_str})
                    continue
                final_content = cont; break
            except Exception as e: self.model_selector.record_result(mid, False, time.time()-st, str(e)); raise
        return ResponseSanitizer.sanitize(final_content), collected_files

    def _build_messages(self, message: str, context: List[Dict]) -> List[Dict]:
        tools_names = [getattr(t, 'name', '?') for t in self.tool_registry.get_all()[:20]] if self.tool_registry else []
        sys_p = f"Eres OpenClaw.\nModelo: {getattr(self.current_model, 'name', 'N/A')}\nTools: {len(tools_names)} {', '.join(tools_names)}\n- Responde directo.\n- Usa Markdown."
        return [{"role": "system", "content": sys_p}] + [{"role": m.get('role', 'user'), "content": m.get('content', '')} for m in context if m.get('content')] + [{"role": "user", "content": message}]

    def _display_response(self, resp: OpenClawResponse):
        print(f"\n{C.NVIDIA_GREEN}┌─{C.BRIGHT_CYAN}OpenClaw{C.NVIDIA_GREEN}──▶{C.RESET}")
        if resp.thinking: print(f"{C.NVIDIA_GREEN}│{C.RESET} {C.DIM}💭 [{resp.thinking[:150]}...]{C.RESET}\n{C.NVIDIA_GREEN}│{C.RESET}")
        for line in render_markdown(resp.content or "_[Sin respuesta]_").split('\n'): print(f"{C.NVIDIA_GREEN}│{C.RESET} {line}")
        print(f"{C.NVIDIA_GREEN}├────────────────────────────────────────────────{C.RESET}")
        for p in [f"🧠 {resp.model_used}", f"⏱️ {resp.elapsed_time:.1f}s", f"🔧 {', '.join(resp.tools_used[:5])}", f"📊 {self.rate_limiter.remaining} req"]: print(f"{C.NVIDIA_GREEN}│{C.DIM} {p}{C.RESET}")
        print(f"{C.NVIDIA_GREEN}└────────────────────────────────────────────────{C.RESET}\n")

    def switch_model(self, key: str) -> Tuple[bool, str]:
        s, m = self.model_selector.switch_model(key)
        if s: self.current_model = self.model_selector.current_model
        return s, m

    def register_plugin(self, plugin: SkillPlugin): self.skills.register_plugin(plugin, self)

    def stop(self):
        """Alias para shutdown"""
        self.shutdown()

    def shutdown(self):
        if self.state == OpenClawState.SHUTTING_DOWN: return
        self.state = OpenClawState.SHUTTING_DOWN; logger.info("Shutting down..."); self._running = False
        if self.autonomous_engine.is_running: self.autonomous_engine.cancel()
        self.memory.shutdown(); self._executor.shutdown(wait=False)
        if self._async_loop: self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        print(f"{C.DIM}[OpenClaw] Apagado ✅{C.RESET}")

def create_openclaw(config: Dict = None) -> OpenClawAgent: return OpenClawAgent(config)
def run_openclaw(token=None, channels=None, config=None): agent = OpenClawAgent(config); agent.start(token, channels)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(); p.add_argument('--discord-token'); p.add_argument('--model'); p.add_argument('--rate-limit', type=int, default=60)
    args = p.parse_args(); run_openclaw(args.discord_token, config={'rate_limit': args.rate_limit})