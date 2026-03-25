"""
NVIDIA CODE - Herramientas de Terminal (Interruptibles)
Sistema robusto de ejecución de comandos con seguridad, streaming y control de procesos
"""

import subprocess
import os
import re
import signal
import sys
import time
import shlex
import shutil
import threading
import queue
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from .base import BaseTool, ToolParameter


# ─────────────────────────────────────────────────────────────────────
#  Constantes y Configuración de Seguridad
# ─────────────────────────────────────────────────────────────────────

class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class BlockedPattern:
    """Patrón de comando bloqueado con contexto."""
    pattern: str
    reason: str
    level: RiskLevel
    is_regex: bool = False


# Patrones bloqueados organizados por severidad
BLOCKED_PATTERNS: List[BlockedPattern] = [
    # ── Crítico: Destrucción del sistema
    BlockedPattern("rm -rf /",       "Eliminación recursiva de raíz",          RiskLevel.CRITICAL),
    BlockedPattern("rm -rf /*",      "Eliminación recursiva de raíz",          RiskLevel.CRITICAL),
    BlockedPattern("rm -rf ~",       "Eliminación del directorio home",        RiskLevel.CRITICAL),
    BlockedPattern("mkfs",           "Formateo de disco",                      RiskLevel.CRITICAL),
    BlockedPattern("dd if=/dev",     "Escritura directa a disco",             RiskLevel.CRITICAL),
    BlockedPattern(":(){",           "Fork bomb",                              RiskLevel.CRITICAL),
    BlockedPattern(":(){ :|:& };:",  "Fork bomb",                              RiskLevel.CRITICAL),
    BlockedPattern("> /dev/sda",     "Escritura directa a dispositivo",       RiskLevel.CRITICAL),
    BlockedPattern("chmod -R 777 /", "Permisos inseguros en raíz",            RiskLevel.CRITICAL),
    BlockedPattern("chown -R",       "Cambio masivo de propietario en raíz",  RiskLevel.CRITICAL, False),

    # ── Alto: Modificaciones peligrosas del sistema
    BlockedPattern("shutdown",       "Apagado del sistema",                   RiskLevel.HIGH),
    BlockedPattern("reboot",         "Reinicio del sistema",                  RiskLevel.HIGH),
    BlockedPattern("init 0",         "Apagado del sistema",                   RiskLevel.HIGH),
    BlockedPattern("halt",           "Detención del sistema",                 RiskLevel.HIGH),
    BlockedPattern("poweroff",       "Apagado del sistema",                   RiskLevel.HIGH),
    BlockedPattern("systemctl stop", "Detención de servicios del sistema",    RiskLevel.HIGH),

    # ── Medio: Operaciones de red sospechosas
    BlockedPattern(
        r"curl\s+.*\|\s*(ba)?sh",
        "Ejecución remota de scripts",
        RiskLevel.MEDIUM,
        is_regex=True,
    ),
    BlockedPattern(
        r"wget\s+.*\|\s*(ba)?sh",
        "Ejecución remota de scripts",
        RiskLevel.MEDIUM,
        is_regex=True,
    ),
]

# Extensiones de comandos considerados seguros (no requieren confirmación)
SAFE_COMMANDS: Set[str] = {
    "ls", "dir", "cat", "head", "tail", "wc", "echo", "pwd", "date",
    "whoami", "hostname", "uname", "env", "printenv", "which", "where",
    "file", "stat", "du", "df",  "free", "uptime", "id",
    "find", "grep", "awk", "sed", "sort", "uniq", "cut", "tr",
    "diff", "comm", "tee", "xargs",
    "python", "python3", "node", "npm", "npx", "yarn", "pnpm",
    "pip", "pip3", "cargo", "go", "ruby", "java", "javac",
    "git", "gh",
    "docker", "docker-compose",
    "make", "cmake", "gcc", "g++", "clang",
    "code", "vim", "nano",
    "tree", "bat", "rg", "fd", "fzf", "jq", "yq",
    "curl", "wget", "ssh", "scp", "rsync",
    "zip", "unzip", "tar", "gzip", "gunzip",
    "clear", "reset", "tput",
    "cd", "mkdir", "touch", "cp", "mv", "ln",
}

# Tamaño máximo de salida capturada (bytes)
MAX_STDOUT_CAPTURE = 8_000
MAX_STDERR_CAPTURE = 4_000
DEFAULT_TIMEOUT = 120


# ─────────────────────────────────────────────────────────────────────
#  Helpers de colores (importación segura)
# ─────────────────────────────────────────────────────────────────────

def _load_colors():
    """Carga colores de forma segura con fallback."""
    try:
        from ui.colors import Colors
        return Colors()
    except ImportError:
        class _Stub:
            def __getattr__(self, _):
                return ""
        return _Stub()


# ─────────────────────────────────────────────────────────────────────
#  Resultado de ejecución
# ─────────────────────────────────────────────────────────────────────

@dataclass
class CommandResult:
    """Resultado estructurado de la ejecución de un comando."""
    command: str
    return_code: int = -1
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    interrupted: bool = False
    timed_out: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.return_code == 0 and not self.interrupted and not self.timed_out

    def to_markdown(self) -> str:
        """Formatea el resultado como markdown para el modelo."""
        parts: List[str] = []

        if self.interrupted:
            parts.append("🛑 **Comando cancelado por el usuario**")
        elif self.timed_out:
            parts.append(f"⏱️ **Timeout tras {self.duration:.1f}s**")
        elif self.error:
            parts.append(f"❌ **Error:** {self.error}")

        if self.stdout:
            trimmed = self.stdout.strip()[:MAX_STDOUT_CAPTURE]
            was_trimmed = len(self.stdout.strip()) > MAX_STDOUT_CAPTURE
            parts.append(f"📤 **STDOUT:**\n```\n{trimmed}\n```")
            if was_trimmed:
                parts.append(f"_{len(self.stdout) - MAX_STDOUT_CAPTURE} bytes truncados_")

        if self.stderr:
            trimmed = self.stderr.strip()[:MAX_STDERR_CAPTURE]
            parts.append(f"📥 **STDERR:**\n```\n{trimmed}\n```")

        icon = "✅" if self.success else "⚠️"
        parts.append(f"\n{icon} **Código:** {self.return_code}  ⏱ {self.duration:.2f}s")

        return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────
#  Motor de Seguridad
# ─────────────────────────────────────────────────────────────────────

class CommandGuard:
    """Valida comandos contra patrones peligrosos."""

    def __init__(self, extra_blocked: List[BlockedPattern] = None):
        self.patterns = list(BLOCKED_PATTERNS)
        if extra_blocked:
            self.patterns.extend(extra_blocked)

    def check(self, command: str) -> Tuple[bool, Optional[BlockedPattern]]:
        """
        Retorna (is_safe, matched_pattern).
        Si is_safe es False, matched_pattern contiene el patrón que coincidió.
        """
        cmd_lower = command.lower().strip()

        for bp in self.patterns:
            if bp.is_regex:
                if re.search(bp.pattern, cmd_lower):
                    return False, bp
            else:
                if bp.pattern in cmd_lower:
                    return False, bp

        return True, None

    def get_risk_level(self, command: str) -> RiskLevel:
        """Evalúa el nivel de riesgo de un comando."""
        is_safe, pattern = self.check(command)
        if not is_safe and pattern:
            return pattern.level

        base_cmd = command.strip().split()[0] if command.strip() else ""
        base_cmd = os.path.basename(base_cmd)

        if base_cmd in SAFE_COMMANDS:
            return RiskLevel.SAFE

        # Heurísticas adicionales
        if any(op in command for op in ["|", "&&", "||", ";", "`", "$("]):
            return RiskLevel.LOW
        if "sudo" in command:
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    @staticmethod
    def extract_base_command(command: str) -> str:
        """Extrae el comando base (primer token) de forma segura."""
        stripped = command.strip()
        if not stripped:
            return ""
        # Ignorar prefijos comunes
        for prefix in ("sudo", "nohup", "nice", "time", "env"):
            if stripped.startswith(prefix + " "):
                stripped = stripped[len(prefix):].strip()
        return stripped.split()[0] if stripped else ""


# ─────────────────────────────────────────────────────────────────────
#  Lector de salida en streaming (hilo separado)
# ─────────────────────────────────────────────────────────────────────

class _StreamReader(threading.Thread):
    """Lee un stream línea a línea en un hilo separado."""

    def __init__(self, stream, output_queue: queue.Queue, tag: str = "stdout"):
        super().__init__(daemon=True)
        self.stream = stream
        self.queue = output_queue
        self.tag = tag
        self.lines: List[str] = []

    def run(self):
        try:
            for line in iter(self.stream.readline, ''):
                if not line:
                    break
                self.lines.append(line)
                self.queue.put((self.tag, line))
        except (ValueError, OSError):
            pass
        finally:
            try:
                self.stream.close()
            except Exception:
                pass

    def get_output(self) -> str:
        return ''.join(self.lines)


# ─────────────────────────────────────────────────────────────────────
#  ExecuteCommandTool
# ─────────────────────────────────────────────────────────────────────

class ExecuteCommandTool(BaseTool):
    """
    Ejecuta comandos en la terminal con:
    - Salida en streaming (tiempo real)
    - Interrupción limpia con Ctrl+C
    - Validación de seguridad
    - Timeout configurable
    - Resultado estructurado
    """

    name = "execute_command"
    description = "Ejecuta un comando en la terminal del sistema"
    category = "terminal"

    def __init__(self):
        self.guard = CommandGuard()
        self._active_process: Optional[subprocess.Popen] = None

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "command": ToolParameter(
                name="command",
                type="string",
                description="Comando a ejecutar en la terminal",
                required=True,
            ),
            "timeout": ToolParameter(
                name="timeout",
                type="integer",
                description=f"Timeout en segundos (default: {DEFAULT_TIMEOUT})",
                required=False,
            ),
            "cwd": ToolParameter(
                name="cwd",
                type="string",
                description="Directorio de trabajo (default: directorio actual)",
                required=False,
            ),
        }

    # ── Punto de entrada principal ───────────────────────────────────

    def execute(
        self,
        command: str = None,
        timeout: int = DEFAULT_TIMEOUT,
        cwd: str = None,
        **kwargs,
    ) -> str:
        command = command or kwargs.get("command", "")
        if not command or not command.strip():
            return "❌ Se requiere un comando para ejecutar."

        command = command.strip()
        C = _load_colors()

        # ── 1. Validación de seguridad
        is_safe, blocked = self.guard.check(command)
        if not is_safe:
            level_color = {
                RiskLevel.CRITICAL: getattr(C, 'BRIGHT_RED', ''),
                RiskLevel.HIGH:     getattr(C, 'RED', ''),
                RiskLevel.MEDIUM:   getattr(C, 'YELLOW', ''),
            }.get(blocked.level, getattr(C, 'RED', ''))

            return (
                f"🚫 **Comando bloqueado** [{blocked.level.value.upper()}]\n"
                f"**Razón:** {blocked.reason}\n"
                f"**Patrón:** `{blocked.pattern}`"
            )

        # ── 2. Resolver directorio de trabajo
        work_dir = self._resolve_cwd(cwd)
        if work_dir is None:
            return f"❌ Directorio no encontrado: `{cwd}`"

        # ── 3. Mostrar cabecera
        risk = self.guard.get_risk_level(command)
        self._print_header(command, work_dir, risk, timeout, C)

        # ── 4. Ejecutar
        result = self._run(command, timeout, work_dir, C)

        # ── 5. Mostrar resumen
        self._print_footer(result, C)

        return result.to_markdown()

    # ── Ejecución con streaming ──────────────────────────────────────

    def _run(self, command: str, timeout: int, cwd: str, C) -> CommandResult:
        """Ejecuta el comando con salida en streaming y soporte de interrupción."""
        result = CommandResult(command=command)
        start_time = time.monotonic()

        # Kwargs para Popen
        popen_kwargs = dict(
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            bufsize=1,
            universal_newlines=True,
        )

        # En Unix, usar grupo de procesos para matar todos los hijos
        if sys.platform != 'win32':
            popen_kwargs['preexec_fn'] = os.setsid

        try:
            process = subprocess.Popen(command, **popen_kwargs)
            self._active_process = process

            # Crear hilos de lectura para stdout y stderr
            output_queue: queue.Queue = queue.Queue()

            stdout_reader = _StreamReader(process.stdout, output_queue, "stdout")
            stderr_reader = _StreamReader(process.stderr, output_queue, "stderr")

            stdout_reader.start()
            stderr_reader.start()

            # Leer y mostrar salida en tiempo real
            deadline = time.monotonic() + timeout

            while process.poll() is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._kill_process(process, C)
                    result.timed_out = True
                    result.duration = time.monotonic() - start_time
                    result.stdout = stdout_reader.get_output()
                    result.stderr = stderr_reader.get_output()
                    return result

                try:
                    tag, line = output_queue.get(timeout=0.1)
                    self._print_stream_line(tag, line, C)
                except queue.Empty:
                    continue

            # Proceso terminó — vaciar cola restante
            stdout_reader.join(timeout=2)
            stderr_reader.join(timeout=2)

            while not output_queue.empty():
                try:
                    tag, line = output_queue.get_nowait()
                    self._print_stream_line(tag, line, C)
                except queue.Empty:
                    break

            result.return_code = process.returncode
            result.stdout = stdout_reader.get_output()
            result.stderr = stderr_reader.get_output()
            result.duration = time.monotonic() - start_time

        except KeyboardInterrupt:
            result.interrupted = True
            result.duration = time.monotonic() - start_time
            self._handle_interrupt(process, C)
            result.stdout = stdout_reader.get_output() if 'stdout_reader' in dir() else ""
            result.stderr = stderr_reader.get_output() if 'stderr_reader' in dir() else ""

        except FileNotFoundError:
            result.error = f"Comando no encontrado: `{self._extract_base(command)}`"
            result.duration = time.monotonic() - start_time

        except PermissionError:
            result.error = "Permiso denegado para ejecutar el comando"
            result.duration = time.monotonic() - start_time

        except Exception as e:
            result.error = str(e)
            result.duration = time.monotonic() - start_time

        finally:
            self._active_process = None

        return result

    # ── Manejo de procesos ───────────────────────────────────────────

    def _kill_process(self, process: subprocess.Popen, C):
        """Mata el proceso y todos sus hijos."""
        reset = getattr(C, 'RESET', '')
        red = getattr(C, 'RED', '')
        print(f"\n{red}⏱️  Timeout — terminando proceso...{reset}")

        try:
            if sys.platform == 'win32':
                subprocess.run(
                    f"taskkill /F /T /PID {process.pid}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                # Matar todo el grupo de procesos
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                # Dar 2 segundos de gracia, luego SIGKILL
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        finally:
            try:
                process.kill()
            except Exception:
                pass

    def _handle_interrupt(self, process: subprocess.Popen, C):
        """Maneja Ctrl+C: mata proceso hijo limpiamente."""
        reset = getattr(C, 'RESET', '')
        red = getattr(C, 'RED', '')
        dim = getattr(C, 'DIM', '')

        print(f"\n\n{red}🛑 Interrumpiendo comando...{reset}")

        try:
            if sys.platform == 'win32':
                subprocess.run(
                    f"taskkill /F /T /PID {process.pid}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                pgid = os.getpgid(process.pid)
                os.killpg(pgid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        finally:
            try:
                process.kill()
            except Exception:
                pass

        print(f"{dim}   Proceso terminado.{reset}\n")

    # ── Impresión formateada ─────────────────────────────────────────

    def _print_header(self, command: str, cwd: str, risk: RiskLevel, timeout: int, C):
        """Imprime la cabecera antes de ejecutar."""
        reset = getattr(C, 'RESET', '')
        bold = getattr(C, 'BOLD', '')
        dim = getattr(C, 'DIM', '')
        cyan = getattr(C, 'BRIGHT_CYAN', '')
        yellow = getattr(C, 'YELLOW', '')
        red = getattr(C, 'RED', '')
        green = getattr(C, 'NVIDIA_GREEN', getattr(C, 'GREEN', ''))

        # Icono y color del nivel de riesgo
        risk_display = {
            RiskLevel.SAFE:     (green,   "●"),
            RiskLevel.LOW:      (green,   "●"),
            RiskLevel.MEDIUM:   (yellow,  "▲"),
            RiskLevel.HIGH:     (red,     "▲"),
            RiskLevel.CRITICAL: (red,     "◆"),
        }
        risk_color, risk_icon = risk_display.get(risk, (dim, "●"))

        # Ancho de terminal
        try:
            tw = shutil.get_terminal_size((80, 24)).columns
        except Exception:
            tw = 80
        w = min(90, tw - 2)

        print()
        print(f"  {cyan}⚡{reset} {bold}Ejecutando comando{reset}  {risk_color}{risk_icon} {risk.value}{reset}")
        print(f"  {dim}{'─' * (w - 4)}{reset}")
        print(f"  {dim}${reset} {bold}{command}{reset}")

        # Mostrar directorio si no es el actual
        if cwd != os.getcwd():
            print(f"  {dim}📂 {cwd}{reset}")

        print(f"  {dim}⏱  timeout: {timeout}s{reset}")
        print(f"  {red}Ctrl+C{reset}{dim} para detener{reset}")
        print(f"  {dim}{'─' * (w - 4)}{reset}")
        print()

    def _print_stream_line(self, tag: str, line: str, C):
        """Imprime una línea de salida en streaming."""
        dim = getattr(C, 'DIM', '')
        reset = getattr(C, 'RESET', '')
        red = getattr(C, 'RED', '')

        text = line.rstrip('\n\r')

        if tag == "stderr":
            # Stderr en rojo tenue
            print(f"  {red}{dim}│{reset} {red}{text}{reset}")
        else:
            print(f"  {dim}│{reset} {text}")

    def _print_footer(self, result: CommandResult, C):
        """Imprime el pie con resumen del resultado."""
        reset = getattr(C, 'RESET', '')
        bold = getattr(C, 'BOLD', '')
        dim = getattr(C, 'DIM', '')
        green = getattr(C, 'BRIGHT_GREEN', '')
        red = getattr(C, 'BRIGHT_RED', '')
        yellow = getattr(C, 'BRIGHT_YELLOW', '')
        cyan = getattr(C, 'BRIGHT_CYAN', '')

        try:
            tw = shutil.get_terminal_size((80, 24)).columns
        except Exception:
            tw = 80
        w = min(90, tw - 2)

        print()
        print(f"  {dim}{'─' * (w - 4)}{reset}")

        if result.interrupted:
            print(f"  {red}🛑 Cancelado{reset}  {dim}⏱ {result.duration:.2f}s{reset}")
        elif result.timed_out:
            print(f"  {yellow}⏱️  Timeout{reset}  {dim}tras {result.duration:.1f}s{reset}")
        elif result.error:
            print(f"  {red}❌ Error:{reset} {result.error}")
        elif result.success:
            print(f"  {green}✔ Completado{reset}  {dim}código: {result.return_code}  ⏱ {result.duration:.2f}s{reset}")
        else:
            print(f"  {yellow}⚠ Finalizó{reset}  {dim}código: {result.return_code}  ⏱ {result.duration:.2f}s{reset}")

        print()

    # ── Utilidades ───────────────────────────────────────────────────

    @staticmethod
    def _resolve_cwd(cwd: Optional[str]) -> Optional[str]:
        """Resuelve y valida el directorio de trabajo."""
        if cwd is None:
            return os.getcwd()

        resolved = os.path.abspath(os.path.expanduser(cwd))
        if os.path.isdir(resolved):
            return resolved
        return None

    @staticmethod
    def _extract_base(command: str) -> str:
        """Extrae el nombre base del comando."""
        parts = command.strip().split()
        return parts[0] if parts else command


# ─────────────────────────────────────────────────────────────────────
#  ReadCommandOutputTool — Lee la salida de un comando sin streaming
# ─────────────────────────────────────────────────────────────────────

class ReadCommandOutputTool(BaseTool):
    """
    Ejecuta un comando silencioso y retorna su salida.
    Ideal para capturar datos sin mostrar en pantalla.
    """

    name = "read_command_output"
    description = "Ejecuta un comando y retorna su salida sin imprimir en pantalla"
    category = "terminal"

    def __init__(self):
        self.guard = CommandGuard()

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "command": ToolParameter(
                name="command",
                type="string",
                description="Comando a ejecutar",
                required=True,
            ),
            "timeout": ToolParameter(
                name="timeout",
                type="integer",
                description="Timeout en segundos (default: 30)",
                required=False,
            ),
            "cwd": ToolParameter(
                name="cwd",
                type="string",
                description="Directorio de trabajo",
                required=False,
            ),
        }

    def execute(self, command: str = None, timeout: int = 30, cwd: str = None, **kwargs) -> str:
        command = command or kwargs.get("command", "")
        if not command or not command.strip():
            return "❌ Se requiere un comando."

        is_safe, blocked = self.guard.check(command)
        if not is_safe:
            return f"🚫 Comando bloqueado: {blocked.reason}"

        work_dir = os.path.abspath(os.path.expanduser(cwd)) if cwd else os.getcwd()
        if not os.path.isdir(work_dir):
            return f"❌ Directorio no encontrado: `{cwd}`"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=work_dir,
            )

            parts: List[str] = []
            if result.stdout:
                parts.append(result.stdout.strip()[:MAX_STDOUT_CAPTURE])
            if result.stderr:
                parts.append(f"[stderr] {result.stderr.strip()[:MAX_STDERR_CAPTURE]}")

            output = "\n".join(parts) if parts else "(sin salida)"
            icon = "✅" if result.returncode == 0 else "⚠️"
            return f"{output}\n\n{icon} Código: {result.returncode}"

        except subprocess.TimeoutExpired:
            return f"⏱️ Timeout tras {timeout}s"
        except Exception as e:
            return f"❌ Error: {e}"


# ─────────────────────────────────────────────────────────────────────
#  CommandExistsTool — Verifica si un comando está disponible
# ─────────────────────────────────────────────────────────────────────

class CommandExistsTool(BaseTool):
    """Verifica si un comando/programa está instalado en el sistema."""

    name = "command_exists"
    description = "Verifica si un comando está disponible en el PATH del sistema"
    category = "terminal"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "command": ToolParameter(
                name="command",
                type="string",
                description="Nombre del comando a verificar",
                required=True,
            ),
        }

    def execute(self, command: str = None, **kwargs) -> str:
        command = command or kwargs.get("command", "")
        if not command:
            return "❌ Se requiere un nombre de comando."

        path = shutil.which(command)
        if path:
            return f"✅ `{command}` encontrado en: `{path}`"
        return f"❌ `{command}` no está instalado o no se encuentra en el PATH."


# ─────────────────────────────────────────────────────────────────────
#  GetEnvironmentTool — Información del entorno
# ─────────────────────────────────────────────────────────────────────

class GetEnvironmentTool(BaseTool):
    """Obtiene información sobre el entorno del sistema."""

    name = "get_environment"
    description = "Obtiene información del entorno: OS, shell, Python, variables, etc."
    category = "terminal"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "info": ToolParameter(
                name="info",
                type="string",
                description="Tipo de info: 'os', 'python', 'shell', 'path', 'vars', 'all'",
                required=False,
            ),
        }

    def execute(self, info: str = "all", **kwargs) -> str:
        info = (info or kwargs.get("info", "all")).lower()
        parts: List[str] = []

        if info in ("os", "all"):
            parts.append("**🖥️ Sistema Operativo:**")
            parts.append(f"- Plataforma: `{sys.platform}`")
            parts.append(f"- OS: `{os.name}`")
            import platform
            parts.append(f"- Sistema: `{platform.system()} {platform.release()}`")
            parts.append(f"- Arquitectura: `{platform.machine()}`")
            parts.append(f"- CWD: `{os.getcwd()}`")

        if info in ("python", "all"):
            parts.append("\n**🐍 Python:**")
            parts.append(f"- Versión: `{sys.version.split()[0]}`")
            parts.append(f"- Ejecutable: `{sys.executable}`")
            parts.append(f"- Prefix: `{sys.prefix}`")

        if info in ("shell", "all"):
            shell = os.environ.get("SHELL", os.environ.get("COMSPEC", "desconocido"))
            parts.append(f"\n**🐚 Shell:** `{shell}`")
            term = os.environ.get("TERM", os.environ.get("WT_SESSION", "desconocido"))
            parts.append(f"**Terminal:** `{term}`")

        if info in ("path", "all"):
            path_dirs = os.environ.get("PATH", "").split(os.pathsep)[:10]
            parts.append("\n**📂 PATH** (primeros 10):")
            for d in path_dirs:
                exists = "✅" if os.path.isdir(d) else "❌"
                parts.append(f"- {exists} `{d}`")

        if info == "vars":
            parts.append("**🔑 Variables de entorno:**")
            for key in sorted(os.environ.keys())[:30]:
                val = os.environ[key]
                if len(val) > 80:
                    val = val[:77] + "..."
                parts.append(f"- `{key}` = `{val}`")

        return "\n".join(parts) if parts else "❌ Tipo de info no reconocido. Usa: os, python, shell, path, vars, all"