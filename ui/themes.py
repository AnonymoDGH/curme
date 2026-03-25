"""
NVIDIA CODE - Sistema de Temas
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import json
from pathlib import Path


@dataclass
class Theme:
    """Definición de un tema"""
    name: str
    description: str
    
    # Colores principales (RGB tuples)
    primary: Tuple[int, int, int]
    secondary: Tuple[int, int, int]
    accent: Tuple[int, int, int]
    
    # Colores de gradiente
    gradient_start: Tuple[int, int, int]
    gradient_end: Tuple[int, int, int]
    
    # Colores de agentes (para Heavy Mode)
    agent_1: Tuple[int, int, int]
    agent_2: Tuple[int, int, int]
    agent_3: Tuple[int, int, int]
    synthesizer: Tuple[int, int, int]
    
    # Colores de UI
    success: Tuple[int, int, int]
    error: Tuple[int, int, int]
    warning: Tuple[int, int, int]
    info: Tuple[int, int, int]
    dim: Tuple[int, int, int]
    
    # Estilo del logo
    logo_style: str  # 'full', 'eye', 'eye_compact', 'eye_mini', 'minimal'
    
    # Caracteres para separadores
    separator_char: str


# ═══════════════════════════════════════════════════════════════════════════════
# TEMAS PREDEFINIDOS
# ═══════════════════════════════════════════════════════════════════════════════

THEMES: Dict[str, Theme] = {
    "nvidia": Theme(
        name="NVIDIA Classic",
        description="El tema clásico verde NVIDIA",
        primary=(118, 185, 0),
        secondary=(150, 220, 30),
        accent=(0, 255, 200),
        gradient_start=(180, 255, 50),
        gradient_end=(76, 140, 0),
        agent_1=(255, 107, 107),
        agent_2=(78, 205, 196),
        agent_3=(199, 128, 232),
        synthesizer=(255, 217, 102),
        success=(50, 255, 50),
        error=(255, 80, 80),
        warning=(255, 200, 50),
        info=(80, 200, 255),
        dim=(128, 128, 128),
        logo_style="full",
        separator_char="═",
    ),
    
    "cyberpunk": Theme(
        name="Cyberpunk 2077",
        description="Neón futurista cyan y magenta",
        primary=(0, 255, 255),
        secondary=(255, 0, 255),
        accent=(255, 255, 0),
        gradient_start=(0, 255, 255),
        gradient_end=(255, 0, 255),
        agent_1=(255, 0, 128),
        agent_2=(0, 255, 255),
        agent_3=(255, 255, 0),
        synthesizer=(255, 100, 255),
        success=(0, 255, 128),
        error=(255, 0, 100),
        warning=(255, 200, 0),
        info=(0, 200, 255),
        dim=(100, 100, 120),
        logo_style="full",
        separator_char="━",
    ),
    
    "fire": Theme(
        name="Fire",
        description="Gradiente de fuego ardiente",
        primary=(255, 100, 0),
        secondary=(255, 200, 0),
        accent=(255, 50, 50),
        gradient_start=(255, 50, 0),
        gradient_end=(255, 220, 0),
        agent_1=(255, 80, 0),
        agent_2=(255, 150, 0),
        agent_3=(255, 200, 50),
        synthesizer=(255, 255, 100),
        success=(100, 255, 100),
        error=(255, 50, 50),
        warning=(255, 200, 0),
        info=(255, 150, 50),
        dim=(150, 100, 50),
        logo_style="full",
        separator_char="─",
    ),
    
    "ice": Theme(
        name="Ice",
        description="Frío y elegante azul hielo",
        primary=(100, 200, 255),
        secondary=(200, 240, 255),
        accent=(150, 150, 255),
        gradient_start=(200, 240, 255),
        gradient_end=(50, 100, 200),
        agent_1=(100, 150, 255),
        agent_2=(150, 200, 255),
        agent_3=(200, 220, 255),
        synthesizer=(220, 240, 255),
        success=(100, 255, 200),
        error=(255, 100, 150),
        warning=(255, 220, 100),
        info=(100, 200, 255),
        dim=(100, 120, 140),
        logo_style="full",
        separator_char="─",
    ),
    
    "matrix": Theme(
        name="Matrix",
        description="El clásico verde Matrix",
        primary=(0, 255, 65),
        secondary=(0, 200, 50),
        accent=(150, 255, 150),
        gradient_start=(0, 255, 100),
        gradient_end=(0, 100, 0),
        agent_1=(0, 255, 100),
        agent_2=(0, 200, 80),
        agent_3=(0, 150, 60),
        synthesizer=(100, 255, 150),
        success=(0, 255, 0),
        error=(255, 0, 0),
        warning=(200, 200, 0),
        info=(0, 200, 100),
        dim=(0, 80, 0),
        logo_style="eye_compact",
        separator_char="░",
    ),
    
    "gold": Theme(
        name="Gold Premium",
        description="Elegante dorado premium",
        primary=(255, 215, 0),
        secondary=(255, 180, 0),
        accent=(255, 240, 150),
        gradient_start=(255, 240, 100),
        gradient_end=(200, 150, 0),
        agent_1=(255, 200, 50),
        agent_2=(255, 220, 100),
        agent_3=(255, 180, 0),
        synthesizer=(255, 255, 200),
        success=(200, 255, 100),
        error=(255, 100, 100),
        warning=(255, 200, 0),
        info=(255, 220, 100),
        dim=(150, 120, 50),
        logo_style="full",
        separator_char="═",
    ),
    
    "purple": Theme(
        name="Purple Haze",
        description="Misterioso púrpura profundo",
        primary=(147, 112, 219),
        secondary=(186, 85, 211),
        accent=(255, 150, 255),
        gradient_start=(200, 150, 255),
        gradient_end=(100, 50, 150),
        agent_1=(255, 100, 255),
        agent_2=(200, 100, 255),
        agent_3=(150, 100, 200),
        synthesizer=(255, 200, 255),
        success=(150, 255, 150),
        error=(255, 100, 150),
        warning=(255, 200, 150),
        info=(200, 150, 255),
        dim=(100, 80, 120),
        logo_style="full",
        separator_char="─",
    ),
    
    "ocean": Theme(
        name="Ocean Deep",
        description="Profundidades del océano",
        primary=(0, 150, 200),
        secondary=(0, 200, 200),
        accent=(100, 255, 255),
        gradient_start=(0, 200, 255),
        gradient_end=(0, 50, 100),
        agent_1=(0, 200, 200),
        agent_2=(0, 150, 200),
        agent_3=(0, 100, 150),
        synthesizer=(100, 255, 255),
        success=(0, 255, 150),
        error=(255, 100, 100),
        warning=(255, 200, 0),
        info=(0, 200, 255),
        dim=(50, 80, 100),
        logo_style="eye_compact",
        separator_char="~",
    ),
    
    "sunset": Theme(
        name="Sunset",
        description="Atardecer cálido",
        primary=(255, 100, 50),
        secondary=(255, 150, 100),
        accent=(255, 200, 150),
        gradient_start=(255, 200, 100),
        gradient_end=(200, 50, 100),
        agent_1=(255, 150, 50),
        agent_2=(255, 100, 100),
        agent_3=(255, 50, 100),
        synthesizer=(255, 220, 180),
        success=(150, 255, 100),
        error=(255, 50, 50),
        warning=(255, 200, 50),
        info=(255, 150, 100),
        dim=(150, 100, 80),
        logo_style="full",
        separator_char="─",
    ),
    
    "midnight": Theme(
        name="Midnight",
        description="Oscuro y minimalista",
        primary=(150, 150, 200),
        secondary=(100, 100, 150),
        accent=(200, 200, 255),
        gradient_start=(180, 180, 220),
        gradient_end=(50, 50, 80),
        agent_1=(150, 150, 200),
        agent_2=(120, 120, 180),
        agent_3=(100, 100, 150),
        synthesizer=(200, 200, 255),
        success=(100, 200, 100),
        error=(200, 80, 80),
        warning=(200, 180, 80),
        info=(100, 150, 200),
        dim=(80, 80, 100),
        logo_style="minimal",
        separator_char="─",
    ),
    
    "rainbow": Theme(
        name="Rainbow",
        description="Todos los colores del arcoíris",
        primary=(255, 100, 100),
        secondary=(100, 255, 100),
        accent=(100, 100, 255),
        gradient_start=(255, 0, 0),
        gradient_end=(0, 0, 255),
        agent_1=(255, 100, 100),
        agent_2=(100, 255, 100),
        agent_3=(100, 100, 255),
        synthesizer=(255, 255, 100),
        success=(0, 255, 0),
        error=(255, 0, 0),
        warning=(255, 255, 0),
        info=(0, 255, 255),
        dim=(128, 128, 128),
        logo_style="full",
        separator_char="═",
    ),
    
    "hacker": Theme(
        name="Hacker",
        description="Terminal hacker clásica",
        primary=(0, 255, 0),
        secondary=(0, 200, 0),
        accent=(100, 255, 100),
        gradient_start=(0, 255, 0),
        gradient_end=(0, 150, 0),
        agent_1=(0, 255, 0),
        agent_2=(0, 200, 0),
        agent_3=(0, 150, 0),
        synthesizer=(100, 255, 100),
        success=(0, 255, 0),
        error=(255, 0, 0),
        warning=(255, 255, 0),
        info=(0, 255, 0),
        dim=(0, 100, 0),
        logo_style="eye_mini",
        separator_char="=",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# GESTOR DE TEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class ThemeManager:
    """Gestor de temas"""
    
    def __init__(self):
        self.current_theme_name = "nvidia"
        self.current_theme = THEMES["nvidia"]
        self.config_file = Path(".nvidia_code_theme")
        self._load_saved_theme()
    
    def _load_saved_theme(self):
        """Carga el tema guardado si existe"""
        if self.config_file.exists():
            try:
                theme_name = self.config_file.read_text().strip()
                if theme_name in THEMES:
                    self.current_theme_name = theme_name
                    self.current_theme = THEMES[theme_name]
            except:
                pass
    
    def _save_theme(self):
        """Guarda el tema actual"""
        try:
            self.config_file.write_text(self.current_theme_name)
        except:
            pass
    
    def set_theme(self, theme_name: str) -> bool:
        """Cambia el tema actual"""
        theme_name = theme_name.lower()
        if theme_name in THEMES:
            self.current_theme_name = theme_name
            self.current_theme = THEMES[theme_name]
            self._save_theme()
            return True
        return False
    
    def get_theme(self) -> Theme:
        """Obtiene el tema actual"""
        return self.current_theme
    
    def list_themes(self) -> Dict[str, Theme]:
        """Lista todos los temas disponibles"""
        return THEMES
    
    def get_color(self, color_name: str) -> Tuple[int, int, int]:
        """Obtiene un color del tema actual"""
        return getattr(self.current_theme, color_name, (255, 255, 255))
    
    def rgb_to_ansi(self, rgb: Tuple[int, int, int]) -> str:
        """Convierte RGB a código ANSI"""
        return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"
    
    def get_ansi(self, color_name: str) -> str:
        """Obtiene código ANSI de un color del tema"""
        rgb = self.get_color(color_name)
        return self.rgb_to_ansi(rgb)


# Instancia global
_theme_manager = ThemeManager()


def get_theme_manager() -> ThemeManager:
    """Obtiene el gestor de temas global"""
    return _theme_manager


def get_current_theme() -> Theme:
    """Obtiene el tema actual"""
    return _theme_manager.get_theme()


def set_theme(name: str) -> bool:
    """Cambia el tema"""
    return _theme_manager.set_theme(name)


def list_themes() -> Dict[str, Theme]:
    """Lista los temas disponibles"""
    return _theme_manager.list_themes()