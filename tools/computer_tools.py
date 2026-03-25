"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║         COMPUTER USE - Versión Local (Sin dependencias cloud)                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝
pip install mss pyautogui Pillow pyperclip
"""
import sys
import time
import subprocess
import os
import json
import re
from typing import Dict
from .base import BaseTool, ToolParameter

# Imports seguros
try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False


def _check_deps():
    missing = []
    if not HAS_MSS: missing.append("mss")
    if not HAS_PYAUTOGUI: missing.append("pyautogui")
    if not HAS_PIL: missing.append("Pillow")
    return f"[x] Instala: pip install {' '.join(missing)}" if missing else ""


def _get_screen_size():
    """Obtiene tamaño de pantalla"""
    if HAS_PYAUTOGUI:
        return pyautogui.size()
    return (1920, 1080)


def _parse_instruction(instruction: str) -> dict:
    """
    Parsea instrucción en lenguaje natural y devuelve acción.
    Esta función reemplaza a ShowUI cuando no hay API disponible.
    """
    instruction = instruction.lower().strip()
    screen_w, screen_h = _get_screen_size()
    
    # Detectar CLICK
    if "click" in instruction or "clic" in instruction or "pulsa" in instruction:
        # Posiciones conocidas para Windows
        positions = {
            # Taskbar (barra inferior)
            "start": (25, screen_h - 25),
            "inicio": (25, screen_h - 25),
            "windows": (25, screen_h - 25),
            
            # Navegadores en taskbar (posiciones aproximadas)
            "chrome": (70, screen_h - 25),
            "firefox": (110, screen_h - 25),
            "edge": (150, screen_h - 25),
            "browser": (70, screen_h - 25),
            "navegador": (70, screen_h - 25),
            
            # Barra de búsqueda (típica posición)
            "search": (screen_w // 2, 60),
            "buscar": (screen_w // 2, 60),
            "barra": (screen_w // 2, 60),
            "url": (screen_w // 2, 60),
            "address": (screen_w // 2, 60),
            
            # Botones comunes
            "close": (screen_w - 25, 15),
            "cerrar": (screen_w - 25, 15),
            "x button": (screen_w - 25, 15),
            "minimize": (screen_w - 75, 15),
            "minimizar": (screen_w - 75, 15),
            "maximize": (screen_w - 50, 15),
            "maximizar": (screen_w - 50, 15),
            
            # Centro de pantalla
            "center": (screen_w // 2, screen_h // 2),
            "centro": (screen_w // 2, screen_h // 2),
            "middle": (screen_w // 2, screen_h // 2),
            
            # Desktop icons (esquina superior izquierda)
            "desktop": (50, 50),
            "escritorio": (50, 50),
            "icon": (50, 50),
            "icono": (50, 50),
        }
        
        for key, pos in positions.items():
            if key in instruction:
                return {"action": "CLICK", "value": None, "position": pos, "absolute": True}
        
        # Si no encuentra posición conocida, click en centro
        return {"action": "CLICK", "value": None, "position": (screen_w // 2, screen_h // 2), "absolute": True}
    
    # Detectar DOUBLE CLICK
    if "double" in instruction or "doble" in instruction:
        return {"action": "DOUBLE_CLICK", "value": None, "position": (screen_w // 2, screen_h // 2), "absolute": True}
    
    # Detectar RIGHT CLICK
    if "right" in instruction or "derecho" in instruction:
        return {"action": "RIGHT_CLICK", "value": None, "position": (screen_w // 2, screen_h // 2), "absolute": True}
    
    # Detectar INPUT/TYPE
    if "type" in instruction or "write" in instruction or "escribe" in instruction or "input" in instruction:
        # Extraer texto entre comillas
        match = re.search(r"['\"](.+?)['\"]", instruction)
        if match:
            text = match.group(1)
        else:
            # Intentar extraer después de "type" o "write"
            for keyword in ["type ", "write ", "escribe ", "input "]:
                if keyword in instruction:
                    text = instruction.split(keyword, 1)[1].strip()
                    break
            else:
                text = ""
        
        return {"action": "INPUT", "value": text, "position": None, "absolute": True}
    
    # Detectar ENTER
    if "enter" in instruction or "intro" in instruction or "submit" in instruction:
        return {"action": "ENTER", "value": None, "position": None}
    
    # Detectar SCROLL
    if "scroll" in instruction or "desplaza" in instruction:
        direction = "down" if ("down" in instruction or "abajo" in instruction) else "up"
        return {"action": "SCROLL", "value": direction, "position": None}
    
    # Detectar HOTKEY
    if "ctrl+" in instruction or "alt+" in instruction or "win+" in instruction:
        match = re.search(r"(ctrl\+\w+|alt\+\w+|win\+\w+)", instruction)
        if match:
            return {"action": "HOTKEY", "value": match.group(1), "position": None}
    
    # Detectar OPEN/LAUNCH
    if "open" in instruction or "abre" in instruction or "launch" in instruction or "ejecuta" in instruction:
        apps = {
            "notepad": "notepad.exe",
            "bloc": "notepad.exe",
            "chrome": "chrome",
            "firefox": "firefox",
            "edge": "msedge",
            "explorer": "explorer.exe",
            "explorador": "explorer.exe",
            "cmd": "cmd.exe",
            "terminal": "cmd.exe",
            "calculator": "calc.exe",
            "calculadora": "calc.exe",
        }
        for key, app in apps.items():
            if key in instruction:
                return {"action": "LAUNCH", "value": app, "position": None}
        
        # Intentar extraer nombre de app
        for keyword in ["open ", "abre ", "launch ", "ejecuta "]:
            if keyword in instruction:
                app = instruction.split(keyword, 1)[1].strip()
                return {"action": "LAUNCH", "value": app, "position": None}
    
    # Default: no reconocido
    return {"action": "UNKNOWN", "value": instruction, "position": None}


def _execute_action(action: dict) -> str:
    """Ejecuta la acción en el sistema"""
    act_type = action.get("action", "").upper()
    value = action.get("value")
    pos = action.get("position")
    
    screen_w, screen_h = _get_screen_size()
    
    if act_type == "ERROR":
        return f"[x] {action.get('error', 'Unknown error')}"
    
    if act_type == "DONE":
        return "[✓] Tarea completada"
    
    if act_type == "UNKNOWN":
        return f"[?] No entendí: {value}. Usa: click on X, type 'text', scroll down, press enter, open app"
    
    if act_type == "CLICK" and pos:
        x, y = pos if action.get("absolute") else (int(pos[0] * screen_w), int(pos[1] * screen_h))
        pyautogui.moveTo(x, y, duration=0.2)
        pyautogui.click()
        return f"[✓] Click en ({x}, {y})"
    
    if act_type == "DOUBLE_CLICK" and pos:
        x, y = pos if action.get("absolute") else (int(pos[0] * screen_w), int(pos[1] * screen_h))
        pyautogui.moveTo(x, y, duration=0.2)
        pyautogui.doubleClick()
        return f"[✓] Doble click en ({x}, {y})"
    
    if act_type == "RIGHT_CLICK" and pos:
        x, y = pos if action.get("absolute") else (int(pos[0] * screen_w), int(pos[1] * screen_h))
        pyautogui.moveTo(x, y, duration=0.2)
        pyautogui.rightClick()
        return f"[✓] Click derecho en ({x}, {y})"
    
    if act_type == "INPUT":
        text = value or ""
        if HAS_CLIPBOARD and text:
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
        elif text:
            pyautogui.write(text, interval=0.02)
        return f"[✓] Escrito: '{text[:30]}'" if len(str(text)) > 30 else f"[✓] Escrito: '{text}'"
    
    if act_type == "ENTER":
        pyautogui.press('enter')
        return "[✓] Enter"
    
    if act_type == "SCROLL":
        direction = (value or "down").lower()
        amount = -5 if direction == "down" else 5
        pyautogui.scroll(amount * 100)
        return f"[✓] Scroll {direction}"
    
    if act_type == "HOTKEY" and value:
        keys = [k.strip() for k in value.lower().split('+')]
        pyautogui.hotkey(*keys)
        return f"[✓] Hotkey: {value}"
    
    if act_type == "LAUNCH" and value:
        try:
            if sys.platform == 'win32':
                os.startfile(value)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', '-a', value])
            else:
                subprocess.Popen(['xdg-open', value])
            time.sleep(1)
            return f"[✓] Abierto: {value}"
        except Exception as e:
            return f"[x] Error abriendo {value}: {e}"
    
    return f"[?] Acción no ejecutada: {act_type}"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

class ComputerActionTool(BaseTool):
    name = "computer_action"
    description = """Ejecuta acciones en el computador.
    
Ejemplos:
- "click on Chrome" - click en Chrome en taskbar
- "click on start" - click en botón inicio
- "click on search bar" - click en barra de búsqueda
- "type 'hello world'" - escribe texto
- "scroll down" - scroll hacia abajo
- "press enter" - presiona enter
- "open notepad" - abre aplicación

Posiciones conocidas: start, chrome, firefox, edge, search, close, minimize, center"""
    category = "computer"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "instruction": ToolParameter(
                name="instruction",
                type="string",
                description="Qué hacer: 'click on X', 'type text', 'scroll down', etc.",
                required=True
            )
        }
    
    def execute(self, instruction: str = None, **kwargs) -> str:
        instruction = instruction or kwargs.get("instruction", "")
        
        deps_error = _check_deps()
        if deps_error:
            return deps_error
        
        if not instruction:
            return "[x] Se requiere instrucción"
        
        try:
            print(f"🎯 Parseando: '{instruction}'")
            action = _parse_instruction(instruction)
            print(f"📋 Acción: {action}")
            
            result = _execute_action(action)
            return f"{result}"
            
        except Exception as e:
            return f"[x] Error: {str(e)}"


class ComputerMultiStepTool(BaseTool):
    name = "computer_task"
    description = """Ejecuta tarea multi-paso.
Ejemplo: "open chrome, click search bar, type 'weather', press enter" """
    category = "computer"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "task": ToolParameter(
                name="task",
                type="string",
                description="Tarea con pasos separados por coma",
                required=True
            )
        }
    
    def execute(self, task: str = None, **kwargs) -> str:
        task = task or kwargs.get("task", "")
        
        deps_error = _check_deps()
        if deps_error:
            return deps_error
        
        if not task:
            return "[x] Se requiere tarea"
        
        # Separar por comas o "then" o "y"
        steps = re.split(r',|\bthen\b|\by luego\b|\bafter\b', task)
        steps = [s.strip() for s in steps if s.strip()]
        
        results = []
        for i, step in enumerate(steps):
            print(f"\n── Paso {i+1}/{len(steps)}: {step} ──")
            action = _parse_instruction(step)
            result = _execute_action(action)
            results.append(f"{i+1}. {result}")
            time.sleep(0.5)
        
        return "[✓] Tarea completada:\n" + "\n".join(results)


# Tools directas (sin cambios)
class DirectClickTool(BaseTool):
    name = "direct_click"
    description = "Click en coordenadas exactas (x, y)."
    category = "computer"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "x": ToolParameter(name="x", type="integer", description="Coordenada X", required=True),
            "y": ToolParameter(name="y", type="integer", description="Coordenada Y", required=True),
            "button": ToolParameter(name="button", type="string", description="left/right/double", required=False)
        }
    
    def execute(self, x=None, y=None, button="left", **kwargs) -> str:
        if not HAS_PYAUTOGUI:
            return "[x] Instala pyautogui"
        x, y = int(kwargs.get("x", x)), int(kwargs.get("y", y))
        button = kwargs.get("button", "left")
        pyautogui.moveTo(x, y, duration=0.2)
        {"double": pyautogui.doubleClick, "right": pyautogui.rightClick}.get(button, pyautogui.click)()
        return f"[✓] {button} click ({x}, {y})"


class DirectTypeTool(BaseTool):
    name = "direct_type"
    description = "Escribe texto donde está el cursor."
    category = "computer"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "text": ToolParameter(name="text", type="string", description="Texto", required=True),
            "enter": ToolParameter(name="enter", type="boolean", description="Enter al final", required=False)
        }
    
    def execute(self, text="", enter=False, **kwargs) -> str:
        if not HAS_PYAUTOGUI:
            return "[x] Instala pyautogui"
        text, enter = kwargs.get("text", text), kwargs.get("enter", enter)
        if HAS_CLIPBOARD:
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
        else:
            pyautogui.write(text)
        if enter:
            pyautogui.press('enter')
        return f"[✓] '{text[:30]}'"


class DirectKeyTool(BaseTool):
    name = "direct_key"
    description = "Presiona tecla: 'enter', 'ctrl+c', 'alt+tab', 'win'"
    category = "computer"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {"key": ToolParameter(name="key", type="string", description="Tecla", required=True)}
    
    def execute(self, key="", **kwargs) -> str:
        if not HAS_PYAUTOGUI:
            return "[x] Instala pyautogui"
        key = kwargs.get("key", key).lower()
        pyautogui.hotkey(*key.split('+')) if '+' in key else pyautogui.press(key)
        return f"[✓] {key}"


class RunCommandTool(BaseTool):
    name = "run_command"
    description = "Ejecuta comando en terminal."
    category = "computer"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {"command": ToolParameter(name="command", type="string", description="Comando", required=True)}
    
    def execute(self, command="", **kwargs) -> str:
        command = kwargs.get("command", command)
        try:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return f"[{r.returncode}]\n{(r.stdout+r.stderr)[:1000]}"
        except Exception as e:
            return f"[x] {e}"


class LaunchAppTool(BaseTool):
    name = "launch_app"
    description = "Abre aplicación: notepad, chrome, calc, explorer, etc."
    category = "computer"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {"app": ToolParameter(name="app", type="string", description="App", required=True)}
    
    def execute(self, app="", **kwargs) -> str:
        app = kwargs.get("app", app)
        try:
            if sys.platform == 'win32':
                os.startfile(app)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', '-a', app])
            else:
                subprocess.Popen(['xdg-open', app])
            time.sleep(1.5)
            return f"[✓] {app}"
        except Exception as e:
            return f"[x] {e}"


class WaitTool(BaseTool):
    name = "wait"
    description = "Espera N segundos."
    category = "computer"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {"seconds": ToolParameter(name="seconds", type="number", description="Segundos", required=True)}
    
    def execute(self, seconds=1, **kwargs) -> str:
        time.sleep(float(kwargs.get("seconds", seconds)))
        return f"[✓] {seconds}s"