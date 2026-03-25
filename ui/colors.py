"""
NVIDIA CODE - Colores y Estilos ANSI
"""


class Colors:
    """Colores ANSI para terminal con tema NVIDIA"""
    
    # Colores base
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Colores brillantes
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Colores NVIDIA (RGB personalizado)
    NVIDIA_GREEN = '\033[38;2;118;185;0m'
    NVIDIA_LIGHT_GREEN = '\033[38;2;150;210;50m'
    NVIDIA_DARK_GREEN = '\033[38;2;80;140;0m'
    NVIDIA_GRAY = '\033[38;2;102;102;102m'
    NVIDIA_DARK = '\033[38;2;30;30;30m'
    
    # Colores para Heavy Agent
    AGENT_1 = '\033[38;2;255;107;107m'  # Rojo coral (Kimi)
    AGENT_2 = '\033[38;2;78;205;196m'   # Turquesa (Nemotron)
    AGENT_3 = '\033[38;2;199;128;232m'  # Purpura (DeepSeek)
    SYNTHESIZER = '\033[38;2;255;217;102m'  # Dorado (Sintetizador)
    
    # Estilos
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    HIDDEN = '\033[8m'
    STRIKETHROUGH = '\033[9m'
    
    # Reset
    RESET = '\033[0m'
    RESET_BOLD = '\033[21m'
    RESET_DIM = '\033[22m'
    RESET_ITALIC = '\033[23m'
    RESET_UNDERLINE = '\033[24m'
    
    # Fondos
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'
    BG_NVIDIA_GREEN = '\033[48;2;118;185;0m'
    
    @classmethod
    def rgb(cls, r: int, g: int, b: int) -> str:
        """Genera color RGB personalizado"""
        return f'\033[38;2;{r};{g};{b}m'
    
    @classmethod
    def bg_rgb(cls, r: int, g: int, b: int) -> str:
        """Genera color de fondo RGB personalizado"""
        return f'\033[48;2;{r};{g};{b}m'
    
    @classmethod
    def success(cls, text: str) -> str:
        """Texto de exito"""
        return f"{cls.BRIGHT_GREEN}[+] {text}{cls.RESET}"
    
    @classmethod
    def error(cls, text: str) -> str:
        """Texto de error"""
        return f"{cls.BRIGHT_RED}[x] {text}{cls.RESET}"
    
    @classmethod
    def warning(cls, text: str) -> str:
        """Texto de advertencia"""
        return f"{cls.BRIGHT_YELLOW}[!] {text}{cls.RESET}"
    
    @classmethod
    def info(cls, text: str) -> str:
        """Texto informativo"""
        return f"{cls.BRIGHT_CYAN}[i] {text}{cls.RESET}"


# Instancia global
C = Colors()