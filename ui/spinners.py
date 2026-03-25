"""
NVIDIA CODE - Spinners y Animaciones (Versión Mejorada)
Sistema avanzado de indicadores visuales para operaciones asíncronas
"""

import sys
import time
import threading
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
from .colors import Colors

C = Colors()


class SpinnerStyle(Enum):
    """Estilos de spinner disponibles"""
    DOTS = "dots"
    DOTS_SNAKE = "dots_snake"
    LINE = "line"
    PIPE = "pipe"
    ARROW = "arrow"
    BOUNCE = "bounce"
    BOX = "box"
    CIRCLE = "circle"
    SQUARE = "square"
    HAMBURGER = "hamburger"
    GROW = "grow"
    BALLOON = "balloon"
    FLIP = "flip"
    PULSE = "pulse"
    POINTS = "points"
    BRAILLE = "braille"
    NVIDIA = "nvidia"
    MATRIX = "matrix"
    BINARY = "binary"
    HEXADECIMAL = "hex"


@dataclass
class SpinnerConfig:
    """Configuración para un spinner"""
    frames: List[str]
    interval: float = 0.1
    color: str = ""
    success_symbol: str = "✓"
    error_symbol: str = "✗"
    warning_symbol: str = "⚠"
    info_symbol: str = "ℹ"


class SpinnerFrames:
    """Frames predefinidos para diferentes estilos"""
    
    # Unicode spinners
    DOTS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    DOTS_SNAKE = ["⢀⠀", "⡀⠀", "⠄⠀", "⢂⠀", "⡂⠀", "⠅⠀", "⢃⠀", "⡃⠀", "⠍⠀", "⢋⠀", "⡋⠀", "⠍⠁", "⢋⠁", "⡋⠁", "⠍⠉", "⠋⠉", "⠋⠉", "⠉⠙", "⠉⠙", "⠉⠩", "⠈⢙", "⠈⡙", "⢈⠩", "⡀⢙", "⠄⡙", "⢂⠩", "⡂⢘", "⠅⡘", "⢃⠨", "⡃⢐", "⠍⡐", "⢋⠠", "⡋⢀", "⠍⡁", "⢋⠁", "⡋⠁", "⠍⠉", "⠋⠉", "⠋⠉", "⠉⠙", "⠉⠙", "⠉⠩", "⠈⢙", "⠈⡙", "⠈⠩", "⠀⢙", "⠀⡙", "⠀⠩", "⠀⢘", "⠀⡘", "⠀⠨", "⠀⢐", "⠀⡐", "⠀⠠", "⠀⢀", "⠀⡀"]
    LINE = ["-", "\\", "|", "/"]
    PIPE = ["┤", "┘", "┴", "└", "├", "┌", "┬", "┐"]
    ARROW = ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"]
    BOUNCE = ["⠁", "⠂", "⠄", "⡀", "⢀", "⠠", "⠐", "⠈"]
    BOX = ["◰", "◳", "◲", "◱"]
    CIRCLE = ["◐", "◓", "◑", "◒"]
    SQUARE = ["◘", "◙", "◚", "◛"]
    HAMBURGER = ["☱", "☲", "☴"]
    GROW = ["▁", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃"]
    BALLOON = [".", "o", "O", "°", "O", "o", "."]
    FLIP = ["_", "_", "_", "‾", "‾", "‾"]
    PULSE = ["◾", "◽", "▪", "▫", "▪", "◽"]
    POINTS = ["∙∙∙", "●∙∙", "∙●∙", "∙∙●", "∙∙∙"]
    
    # Braille patterns
    BRAILLE = ["⡿", "⣟", "⣯", "⣷", "⣾", "⣽", "⣻", "⢿", "⡿"]
    BRAILLE_DOTS = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
    BRAILLE_SNAKE = ["⠉⠉", "⠈⠙", "⠀⠹", "⠀⢸", "⠀⣰", "⢀⣠", "⣀⣀", "⣄⡀", "⣆⠀", "⡇⠀", "⠏⠀", "⠋⠁", "⠉⠉"]
    
    # ASCII fallback for Windows compatibility
    ASCII_DOTS = [".", "..", "...", "....", "...", ".."]
    ASCII_LINE = ["|", "/", "-", "\\"]
    ASCII_ARROW = ["<", "^", ">", "v"]
    ASCII_BOX = ["[=  ]", "[ = ]", "[  =]", "[ = ]"]
    ASCII_PROGRESS = ["[    ]", "[■   ]", "[■■  ]", "[■■■ ]", "[■■■■]", "[ ■■■]", "[  ■■]", "[   ■]"]
    
    # Special themes
    NVIDIA = ["N", "NV", "NVI", "NVID", "NVIDI", "NVIDIA", "VIDIA", "IDIA", "DIA", "IA", "A", ""]
    MATRIX = ["ﾊ", "ﾐ", "ﾋ", "ｰ", "ｳ", "ｼ", "ﾅ", "ﾓ", "ﾆ", "ｻ", "ﾜ", "ﾂ", "ｵ", "ﾘ", "ｱ", "ﾎ", "ﾃ", "ﾏ", "ｹ", "ﾒ"]
    BINARY = ["0000", "0001", "0010", "0011", "0100", "0101", "0110", "0111", "1000", "1001", "1010", "1011", "1100", "1101", "1110", "1111"]
    HEXADECIMAL = ["0x0", "0x1", "0x2", "0x3", "0x4", "0x5", "0x6", "0x7", "0x8", "0x9", "0xA", "0xB", "0xC", "0xD", "0xE", "0xF"]
    
    # Emoji spinners (puede no funcionar en todas las terminales)
    MOON = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]
    EARTH = ["🌍", "🌎", "🌏"]
    CLOCK = ["🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚", "🕛"]
    HEARTS = ["💛", "💙", "💜", "💚", "❤️"]
    WEATHER = ["☀️", "☁️", "⛅", "⛈️", "🌧️", "🌨️", "❄️", "🌨️", "🌧️", "⛈️", "⛅", "☁️"]
    
    @classmethod
    def get_frames(cls, style: SpinnerStyle) -> List[str]:
        """Obtiene los frames para un estilo específico"""
        mapping = {
            SpinnerStyle.DOTS: cls.DOTS,
            SpinnerStyle.DOTS_SNAKE: cls.DOTS_SNAKE,
            SpinnerStyle.LINE: cls.LINE,
            SpinnerStyle.PIPE: cls.PIPE,
            SpinnerStyle.ARROW: cls.ARROW,
            SpinnerStyle.BOUNCE: cls.BOUNCE,
            SpinnerStyle.BOX: cls.BOX,
            SpinnerStyle.CIRCLE: cls.CIRCLE,
            SpinnerStyle.SQUARE: cls.SQUARE,
            SpinnerStyle.HAMBURGER: cls.HAMBURGER,
            SpinnerStyle.GROW: cls.GROW,
            SpinnerStyle.BALLOON: cls.BALLOON,
            SpinnerStyle.FLIP: cls.FLIP,
            SpinnerStyle.PULSE: cls.PULSE,
            SpinnerStyle.POINTS: cls.POINTS,
            SpinnerStyle.BRAILLE: cls.BRAILLE,
            SpinnerStyle.NVIDIA: cls.NVIDIA,
            SpinnerStyle.MATRIX: cls.MATRIX,
            SpinnerStyle.BINARY: cls.BINARY,
            SpinnerStyle.HEXADECIMAL: cls.HEXADECIMAL,
        }
        return mapping.get(style, cls.DOTS)


class Spinner:
    """Spinner universal con múltiples estilos"""
    
    def __init__(
        self,
        message: str = "Loading",
        style: SpinnerStyle = SpinnerStyle.DOTS,
        color: str = None,
        show_elapsed: bool = True,
        custom_frames: List[str] = None,
        interval: float = None
    ):
        self.message = message
        self.style = style
        self.color = color or C.BRIGHT_CYAN
        self.show_elapsed = show_elapsed
        self.frames = custom_frames or SpinnerFrames.get_frames(style)
        self.interval = interval or self._get_default_interval(style)
        
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.frame_idx = 0
        self.start_time = 0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._final_message = ""
        self._final_color = ""
    
    def _get_default_interval(self, style: SpinnerStyle) -> float:
        """Obtiene el intervalo por defecto para cada estilo"""
        intervals = {
            SpinnerStyle.DOTS: 0.08,
            SpinnerStyle.DOTS_SNAKE: 0.06,
            SpinnerStyle.LINE: 0.13,
            SpinnerStyle.PIPE: 0.1,
            SpinnerStyle.ARROW: 0.12,
            SpinnerStyle.BOUNCE: 0.14,
            SpinnerStyle.BOX: 0.12,
            SpinnerStyle.CIRCLE: 0.13,
            SpinnerStyle.SQUARE: 0.15,
            SpinnerStyle.HAMBURGER: 0.2,
            SpinnerStyle.GROW: 0.12,
            SpinnerStyle.BALLOON: 0.14,
            SpinnerStyle.FLIP: 0.5,
            SpinnerStyle.PULSE: 0.2,
            SpinnerStyle.POINTS: 0.15,
            SpinnerStyle.BRAILLE: 0.08,
            SpinnerStyle.NVIDIA: 0.15,
            SpinnerStyle.MATRIX: 0.05,
            SpinnerStyle.BINARY: 0.1,
            SpinnerStyle.HEXADECIMAL: 0.1,
        }
        return intervals.get(style, 0.1)
    
    def _animate(self):
        """Animación del spinner"""
        while not self._stop_event.is_set():
            with self._lock:
                if not self.running:
                    break
                
                frame = self.frames[self.frame_idx % len(self.frames)]
                elapsed = ""
                
                if self.show_elapsed and self.start_time:
                    elapsed_time = time.time() - self.start_time
                    if elapsed_time >= 1:
                        elapsed = f" {C.DIM}({elapsed_time:.1f}s){C.RESET}"
                
                # Construir línea de salida
                output = f"\r{self.color}{frame}{C.RESET} {self.message}{elapsed}  "
                
                try:
                    sys.stdout.write(output)
                    sys.stdout.flush()
                except:
                    pass
                
                self.frame_idx += 1
            
            time.sleep(self.interval)
        
        # Limpiar y mostrar mensaje final si existe
        if self._final_message:
            try:
                sys.stdout.write(f"\r{self._final_color}{self._final_message}{C.RESET}\n")
                sys.stdout.flush()
            except:
                pass
        else:
            # Solo limpiar la línea
            try:
                sys.stdout.write("\r" + " " * 80 + "\r")
                sys.stdout.flush()
            except:
                pass
    
    def start(self):
        """Inicia el spinner"""
        with self._lock:
            if self.running:
                return
            self.running = True
            self.start_time = time.time()
            self._stop_event.clear()
            self.thread = threading.Thread(target=self._animate, daemon=True)
            self.thread.start()
        return self
    
    def stop(self, message: str = None, status: str = "success"):
        """Detiene el spinner con un mensaje final opcional"""
        with self._lock:
            self.running = False
        
        # Configurar mensaje final
        if message:
            symbols = {
                "success": (f"{C.BRIGHT_GREEN}✓{C.RESET}", C.GREEN),
                "error": (f"{C.BRIGHT_RED}✗{C.RESET}", C.RED),
                "warning": (f"{C.BRIGHT_YELLOW}⚠{C.RESET}", C.YELLOW),
                "info": (f"{C.BRIGHT_BLUE}ℹ{C.RESET}", C.BLUE),
            }
            symbol, color = symbols.get(status, ("", ""))
            self._final_message = f"{symbol} {message}"
            self._final_color = color
        
        # Señalar al thread que termine
        self._stop_event.set()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)
    
    def update(self, message: str):
        """Actualiza el mensaje del spinner mientras está corriendo"""
        with self._lock:
            self.message = message
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.stop(f"Error: {exc_type.__name__}", "error")
        else:
            self.stop()


class ThinkingSpinner(Spinner):
    """Spinner específico para cuando el modelo está pensando"""
    
    def __init__(self, message: str = None, **kwargs):  # ✅ Acepta cualquier argumento
        # Ignora color y otros kwargs
        super().__init__(
            message=message or "Pensando",
            style=SpinnerStyle.DOTS,
            color=C.BRIGHT_CYAN,  # Color fijo
            show_elapsed=True
        )


class ToolSpinner(Spinner):
    """Spinner para ejecución de herramientas"""
    
    def __init__(self, tool_name: str):
        super().__init__(
            message=f"Ejecutando {tool_name}",
            style=SpinnerStyle.CIRCLE,
            color=C.BRIGHT_YELLOW,
            show_elapsed=True
        )
    
    def complete(self, success: bool = True):
        """Marca la herramienta como completada"""
        if success:
            self.stop(f"{self.message.replace('Ejecutando', 'Completado')}", "success")
        else:
            self.stop(f"{self.message.replace('Ejecutando', 'Error en')}", "error")


class StreamingIndicator:
    """Indicador animado para streaming de respuestas"""
    
    def __init__(self, style: str = "wave"):
        self.style = style
        self.active = False
        self.thread = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self.animations = {
            "wave": ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"],
            "dots": ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
            "pulse": ["░", "▒", "▓", "█", "▓", "▒"],
            "flow": ["◉", "○", "◎", "○"],
            "typing": ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█", "▉", "▊", "▋", "▌", "▍", "▎"],
        }
        self.frame_idx = 0
    
    def _animate(self):
        """Animación del indicador"""
        frames = self.animations.get(self.style, self.animations["wave"])
        
        while not self._stop_event.is_set():
            with self._lock:
                if not self.active:
                    break
                
                frame = frames[self.frame_idx % len(frames)]
                try:
                    sys.stdout.write(f"\r{C.BRIGHT_CYAN}Streaming {frame}{C.RESET} ")
                    sys.stdout.flush()
                except:
                    pass
                
                self.frame_idx += 1
            
            time.sleep(0.1)
        
        # Limpiar al finalizar
        try:
            sys.stdout.write("\r" + " " * 20 + "\r")
            sys.stdout.flush()
        except:
            pass
    
    def start(self):
        """Inicia el indicador"""
        with self._lock:
            if self.active:
                return
            self.active = True
            self._stop_event.clear()
            self.thread = threading.Thread(target=self._animate, daemon=True)
            self.thread.start()
    
    def stop(self):
        """Detiene el indicador"""
        with self._lock:
            self.active = False
        
        self._stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.3)
    
    def pulse(self):
        """Pulso simple (para backward compatibility)"""
        if not self.active:
            self.start()


class ProgressBar:
    """Barra de progreso visual"""
    
    def __init__(
        self,
        total: int,
        message: str = "Progress",
        width: int = 40,
        style: str = "blocks",
        show_percentage: bool = True,
        show_time: bool = True
    ):
        self.total = total
        self.current = 0
        self.message = message
        self.width = width
        self.style = style
        self.show_percentage = show_percentage
        self.show_time = show_time
        self.start_time = time.time()
        
        self.styles = {
            "blocks": ("█", "░"),
            "lines": ("━", "─"),
            "dots": ("●", "○"),
            "arrows": ("▶", "▷"),
            "squares": ("■", "□"),
            "shades": ("█", "▓", "▒", "░"),
        }
    
    def update(self, current: int = None, increment: int = 1, message: str = None):
        """Actualiza el progreso"""
        if current is not None:
            self.current = current
        else:
            self.current += increment
        
        if message:
            self.message = message
        
        self._render()
    
    def _render(self):
        """Renderiza la barra de progreso"""
        if self.total <= 0:
            return
        
        # Calcular progreso
        progress = min(1.0, self.current / self.total)
        filled_width = int(progress * self.width)
        
        # Obtener caracteres según estilo
        if self.style == "shades":
            filled_char = self.styles["shades"][0]
            partial_char = self.styles["shades"][2]
            empty_char = self.styles["shades"][3]
            
            # Agregar caracter parcial si no está completo
            partial_width = int((progress * self.width % 1) * 4)
            if partial_width and filled_width < self.width:
                bar = filled_char * filled_width
                if partial_width == 1:
                    bar += self.styles["shades"][3]
                elif partial_width == 2:
                    bar += self.styles["shades"][2]
                else:
                    bar += self.styles["shades"][1]
                bar += empty_char * (self.width - filled_width - 1)
            else:
                bar = filled_char * filled_width + empty_char * (self.width - filled_width)
        else:
            filled_char, empty_char = self.styles.get(self.style, self.styles["blocks"])
            bar = filled_char * filled_width + empty_char * (self.width - filled_width)
        
        # Construir salida
        output = f"\r{C.DIM}{self.message}:{C.RESET} "
        output += f"{C.BRIGHT_CYAN}[{bar}]{C.RESET}"
        
        if self.show_percentage:
            output += f" {C.BRIGHT_WHITE}{progress*100:5.1f}%{C.RESET}"
        
        if self.show_time:
            elapsed = time.time() - self.start_time
            if progress > 0 and progress < 1:
                eta = (elapsed / progress) * (1 - progress)
                output += f" {C.DIM}ETA: {self._format_time(eta)}{C.RESET}"
            elif progress >= 1:
                output += f" {C.GREEN}✓ {self._format_time(elapsed)}{C.RESET}"
        
        output += "  "  # Padding para limpiar caracteres residuales
        
        try:
            sys.stdout.write(output)
            sys.stdout.flush()
        except:
            pass
        
        if progress >= 1:
            print()  # Nueva línea al completar
    
    def _format_time(self, seconds: float) -> str:
        """Formatea tiempo en formato humano"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"
    
    def complete(self, message: str = None):
        """Marca como completado"""
        self.current = self.total
        if message:
            self.message = message
        self._render()


class MultiSpinner:
    """Maneja múltiples spinners simultáneos"""
    
    def __init__(self):
        self.spinners: Dict[str, Spinner] = {}
        self.active_count = 0
        self._lock = threading.Lock()
    
    def add(self, key: str, message: str, style: SpinnerStyle = SpinnerStyle.DOTS) -> Spinner:
        """Agrega un nuevo spinner"""
        with self._lock:
            if key in self.spinners:
                self.spinners[key].stop()
            
            spinner = Spinner(message, style)
            self.spinners[key] = spinner
            return spinner
    
    def start(self, key: str):
        """Inicia un spinner específico"""
        with self._lock:
            if key in self.spinners:
                self.spinners[key].start()
                self.active_count += 1
    
    def stop(self, key: str, message: str = None, status: str = "success"):
        """Detiene un spinner específico"""
        with self._lock:
            if key in self.spinners:
                self.spinners[key].stop(message, status)
                self.active_count -= 1
    
    def stop_all(self):
        """Detiene todos los spinners"""
        with self._lock:
            for spinner in self.spinners.values():
                spinner.stop()
            self.active_count = 0
            self.spinners.clear()


# Funciones de conveniencia
def with_spinner(message: str = "Processing", style: SpinnerStyle = SpinnerStyle.DOTS):
    """Decorador para agregar spinner a una función"""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            with Spinner(message, style):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def thinking(message: str = "Thinking"):
    """Context manager para mostrar que el modelo está pensando"""
    return ThinkingSpinner(message)


def loading_tool(tool_name: str):
    """Context manager para mostrar carga de herramienta"""
    return ToolSpinner(tool_name)


# Ejemplos de uso
if __name__ == "__main__":
    import random
    
    # Demo de diferentes estilos
    print("=== DEMO DE SPINNERS ===\n")
    
    styles_to_demo = [
        SpinnerStyle.DOTS,
        SpinnerStyle.LINE,
        SpinnerStyle.CIRCLE,
        SpinnerStyle.NVIDIA,
        SpinnerStyle.BRAILLE,
        SpinnerStyle.GROW,
    ]
    
    for style in styles_to_demo:
        spinner = Spinner(f"Probando {style.value}", style)
        spinner.start()
        time.sleep(2)
        spinner.stop(f"Completado {style.value}", "success")
        time.sleep(0.5)
    
    # Demo de barra de progreso
    print("\n=== DEMO DE PROGRESS BAR ===\n")
    
    progress = ProgressBar(100, "Descargando")
    for i in range(101):
        progress.update(i)
        time.sleep(0.02)
    
    print("\nDemo completado!")