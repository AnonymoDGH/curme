"""
NVIDIA CODE - Logo con soporte para Temas
"""

from .colors import Colors
from .themes import get_current_theme, get_theme_manager

C = Colors()


def _gradient_line(text: str, start_rgb: tuple, end_rgb: tuple) -> str:
    """Aplica gradiente RGB suave a una línea"""
    if not text:
        return text
    
    result = ""
    text_len = len(text.replace(" ", ""))
    char_count = 0
    
    for char in text:
        if char == ' ':
            result += char
        else:
            if text_len > 1:
                ratio = char_count / (text_len - 1)
            else:
                ratio = 0
            r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
            g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
            b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
            result += f"\033[38;2;{r};{g};{b}m{char}"
            char_count += 1
    
    return result + C.RESET


def _diagonal_gradient(lines: list, start_rgb: tuple, end_rgb: tuple) -> str:
    """Aplica gradiente diagonal"""
    if not lines:
        return ""
    
    result = []
    total_lines = len(lines)
    max_width = max(len(line) for line in lines) if lines else 0
    
    for i, line in enumerate(lines):
        line_result = ""
        for j, char in enumerate(line):
            if char == ' ':
                line_result += char
            else:
                if total_lines > 1 and max_width > 1:
                    ratio = ((i / (total_lines - 1)) + (j / (max_width - 1))) / 2
                else:
                    ratio = 0
                ratio = min(1.0, max(0.0, ratio))
                r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
                g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
                b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
                line_result += f"\033[38;2;{r};{g};{b}m{char}"
        result.append(line_result + C.RESET)
    
    return "\n".join(result)


# ═══════════════════════════════════════════════════════════════════════════════
# LOGOS ASCII
# ═══════════════════════════════════════════════════════════════════════════════

LOGO_FULL = [
    "                                                                                              ",
    "            ██████████████████████               ███╗   ██╗██╗   ██╗██╗██████╗ ██╗ █████╗     ",
    "        █████████████████████████████████        ████╗  ██║██║   ██║██║██╔══██╗██║██╔══██╗    ",
    "      ██████████          ███████████████████    ██╔██╗ ██║██║   ██║██║██║  ██║██║███████║    ",
    "    ████████  ████████████     ███████████████   ██║╚██╗██║╚██╗ ██╔╝██║██║  ██║██║██╔══██║    ",
    "   ██████   █████████████████     ████████████   ██║ ╚████║ ╚████╔╝ ██║██████╔╝██║██║  ██║    ",
    "  ██████   ████████  ███████████    ██████████   ╚═╝  ╚═══╝  ╚═══╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═╝    ",
    "  █████   ████████████████████████████  ██████                                                ",
    " ██████   █████████████████████████    ███████    ██████╗ ██████╗ ██████╗ ███████╗            ",
    "  █████    ██████████████████████   ██████████   ██╔════╝██╔═══██╗██╔══██╗██╔════╝            ",
    "  ██████    ████████████████████  ████████████   ██║     ██║   ██║██║  ██║█████╗              ",
    "   ███████     ██████████████   ██████████████   ██║     ██║   ██║██║  ██║██╔══╝              ",
    "    █████████       █████    █████████████████   ╚██████╗╚██████╔╝██████╔╝███████╗            ",
    "      ██████████████     █████████████████████    ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝            ",
    "        ██████████████████████████████████                                                    ",
    "            ██████████████████████████            ⚡ AI-Powered Development Assistant ⚡       ",
    "                                                                                              ",
]

LOGO_EYE = [
    "                          ██████████████████████████████                          ",
    "                      ████████████████████████████████████████                    ",
    "                   ███████████████████████████████████████████████                ",
    "                █████████████████████████████████████████████████████             ",
    "             ████████████                   ████████████████████████████          ",
    "          ██████████████████████                ██████████████████████████        ",
    "        ███████████         ██████████              █████████████████████████     ",
    "      ██████████       █████████   ████████            ███████████████████████    ",
    "    █████████       ██████████████      ████████          █████████████████████   ",
    "   ████████       █████████████████████    ████████         ███████████████████   ",
    "  ████████      ████████████    ███████████   ███████        ██████████████████   ",
    " ████████      ███████████        ██████████████████████       ████████████████   ",
    " ███████      ██████████     ██████████████████████████████       █████████████   ",
    "████████     ██████████    █████████████████████████████             ██████████   ",
    "████████     █████████    ████████████████████████████         █████████████████  ",
    " ███████     █████████    ██████████████████████████       █████████    ████████  ",
    " ████████     █████████    ███████████████████████      █████████          █████  ",
    "  ████████     ██████████    ██████████████████      █████████         █████████  ",
    "   ████████      ██████████     █████████████     ██████████         ████████████ ",
    "    █████████      ███████████      ███████    █████████          ████████████████",
    "      ██████████       █████████████       ████████           ████████████████████",
    "        ███████████          █████████████████           █████████████████████████",
    "          █████████████              ██████         ███████████████████████████   ",
    "             ██████████████████              ██████████████████████████████       ",
    "                █████████████████████████████████████████████████████████         ",
    "                   ███████████████████████████████████████████████████            ",
    "                       ██████████████████████████████████████████                 ",
    "                           ██████████████████████████████████                     ",
]

LOGO_EYE_COMPACT = [
    "            ██████████████████████████████████            ",
    "        █████████████████████████████████████████████     ",
    "      ██████████          ███████████████████████████████ ",
    "    ████████  ████████████     ███████████████████████████",
    "   ██████   █████████████████     ████████████████████████",
    "  ██████   ████████  ███████████    ██████████████████████",
    "  █████   ████████████████████████████████  ██████████████",
    " ██████   █████████████████████████    ███████████████████",
    "  █████    ██████████████████████   ██████████████████████",
    "  ██████    ████████████████████  ████████████████████████",
    "   ███████     ██████████████   ██████████████████████████",
    "    █████████       █████    █████████████████████████████",
    "      ██████████████     █████████████████████████████████",
    "        ██████████████████████████████████████████████    ",
    "            ██████████████████████████████████████        ",
]

LOGO_EYE_MINI = [
    "        ██████████████████████        ",
    "    █████████████████████████████████ ",
    "  ██████████       ███████████████████",
    " ██████  ████████████   ██████████████",
    "██████  ████████████████   ███████████",
    "█████  ██████████████████████  ███████",
    "█████   █████████████████    █████████",
    " █████    █████████████   ████████████",
    "  ██████      █████    ███████████████",
    "    ████████████   ███████████████████",
    "        ██████████████████████████    ",
]

LOGO_MINIMAL_TEMPLATE = """
{separator}
                         NVIDIA CODE
              AI-Powered Development Assistant
{separator}
"""

LOGO_HEAVY = [
    "                                                                                              ",
    "            ██████████████████████               ██╗  ██╗███████╗ █████╗ ██╗   ██╗██╗   ██╗   ",
    "        █████████████████████████████████        ██║  ██║██╔════╝██╔══██╗██║   ██║╚██╗ ██╔╝   ",
    "      ██████████          ███████████████████    ███████║█████╗  ███████║██║   ██║ ╚████╔╝    ",
    "    ████████  ████████████     ███████████████   ██╔══██║██╔══╝  ██╔══██║╚██╗ ██╔╝  ╚██╔╝     ",
    "   ██████   █████████████████     ████████████   ██║  ██║███████╗██║  ██║ ╚████╔╝    ██║      ",
    "  ██████   ████████  ███████████    ██████████   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝  ╚═══╝     ╚═╝      ",
    "  █████   ████████████████████████████  ██████                                                ",
    " ██████   █████████████████████████    ███████    █████╗  ██████╗ ███████╗███╗   ██╗████████╗ ",
    "  █████    ██████████████████████   ██████████   ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝ ",
    "  ██████    ████████████████████  ████████████   ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║    ",
    "   ███████     ██████████████   ██████████████   ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║    ",
    "    █████████       █████    █████████████████   ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║    ",
    "      ██████████████     █████████████████████   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ",
    "        ██████████████████████████████████                                                    ",
    "            ██████████████████████████                                                        ",
    "                                                                                              ",
    "    ══════════════════════════════════════════════════════════════════════════════════════    ",
    "                            🔥 MULTI-AI COLLABORATION SYSTEM 🔥                               ",
    "                                                                                              ",
]


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE RENDERIZADO CON TEMA
# ═══════════════════════════════════════════════════════════════════════════════

def _get_logo_lines(style: str = None) -> list:
    """Obtiene las líneas del logo según el estilo"""
    if style is None:
        theme = get_current_theme()
        style = theme.logo_style
    
    logos = {
        "full": LOGO_FULL,
        "eye": LOGO_EYE,
        "eye_compact": LOGO_EYE_COMPACT,
        "eye_mini": LOGO_EYE_MINI,
        "heavy": LOGO_HEAVY,
    }
    
    return logos.get(style, LOGO_FULL)


def render_logo(style: str = None) -> str:
    """Renderiza el logo con el tema actual"""
    theme = get_current_theme()
    
    if style == "minimal":
        sep = gradient_separator(width=60)
        title = _gradient_line("                         NVIDIA CODE", 
                               theme.gradient_start, theme.gradient_end)
        subtitle = f"\033[38;2;{theme.dim[0]};{theme.dim[1]};{theme.dim[2]}m              AI-Powered Development Assistant\033[0m"
        return f"\n{sep}\n{title}\n{subtitle}\n{sep}\n"
    
    lines = _get_logo_lines(style)
    return _diagonal_gradient(lines, theme.gradient_start, theme.gradient_end)


def render_heavy_logo() -> str:
    """Renderiza el logo Heavy Agent con el tema actual"""
    theme = get_current_theme()
    lines = LOGO_HEAVY.copy()
    
    # Agregar línea de agentes con colores del tema
    tm = get_theme_manager()
    agent_line = (
        f"           {tm.rgb_to_ansi(theme.agent_1)}● AGENT 1\033[0m         "
        f"{tm.rgb_to_ansi(theme.agent_2)}● AGENT 2\033[0m         "
        f"{tm.rgb_to_ansi(theme.agent_3)}● AGENT 3\033[0m         "
        f"{tm.rgb_to_ansi(theme.synthesizer)}★ SYNTHESIZER\033[0m"
    )
    
    result = _diagonal_gradient(lines, theme.gradient_start, theme.gradient_end)
    result += "\n" + agent_line + "\n"
    
    return result


def gradient_separator(style: str = None, width: int = 80) -> str:
    """Crea separador con el tema actual"""
    theme = get_current_theme()
    char = theme.separator_char
    return _gradient_line(char * width, theme.gradient_start, theme.gradient_end)


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES PÚBLICAS
# ═══════════════════════════════════════════════════════════════════════════════

def print_logo(style: str = None):
    """Imprime el logo con el tema actual"""
    print(render_logo(style))


def print_heavy_logo():
    """Imprime el logo Heavy Agent"""
    print(render_heavy_logo())


def print_separator(width: int = 80):
    """Imprime separador con el tema actual"""
    print(gradient_separator(width=width))


def print_welcome(model_name: str, directory: str):
    """Imprime mensaje de bienvenida"""
    theme = get_current_theme()
    tm = get_theme_manager()
    
    sep = gradient_separator(width=70)
    primary = tm.rgb_to_ansi(theme.primary)
    dim = tm.rgb_to_ansi(theme.dim)
    
    print(f"""
{sep}
  {primary}📂 Directorio:{C.RESET} {directory}
  {primary}🤖 Modelo:{C.RESET} {model_name}
  {dim}💡 Escribe /help para ver comandos | /themes para cambiar tema{C.RESET}
{sep}
""")


# Variables de compatibilidad
NVIDIA_LOGO = render_logo()
HEAVY_LOGO = render_heavy_logo()
MINI_LOGO = f"{C.NVIDIA_GREEN}[NVIDIA]{C.RESET} "