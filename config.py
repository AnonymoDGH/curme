"""
NVIDIA CODE - Configuracion Global
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent

# Cargar variables de entorno desde el archivo .env
load_dotenv(BASE_DIR / ".env")

# =============================================================================
# API CONFIGURATION
# =============================================================================

API_KEY = os.environ.get("NVIDIA_API_KEY")

if not API_KEY:
    print("⚠️  Advertencia: NVIDIA_API_KEY no encontrada en variables de entorno o .env")

API_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

DEFAULT_MODEL = "z-ai/glm4.7"
MAX_TOKENS = 16384
TEMPERATURE = 0.18
TOP_P = 1.00

MAX_TOOL_ITERATIONS = 30
COMMAND_TIMEOUT = 60
MAX_AUTO_TURNS = 30

# =============================================================================
# HEAVY AGENT CONFIGURATION
# =============================================================================

HEAVY_AGENT_CONFIG = {
    # USA SOLO MODELOS QUE SABES QUE FUNCIONAN
    # Prueba cada uno con /model X y luego /test
    "primary_models": [
        "z-ai/glm4.7",           # Modelo 1 - Kimi (estable)
        "nvidia/nemotron-3-nano-30b-a3b",      # Modelo 2 - DeepSeek
        "minimaxai/minimax-m2",           # Modelo 4 - MiniMax (rápido)
    ],
    
    # Sintetizador - usa uno rápido y estable
    "synthesizer_model": "z-ai/glm4.7",
    
    # Configuración del debate
    "min_rounds": 1,
    "max_rounds": 2,  # Reducido para evitar muchos errores
    "consensus_threshold": 0.70,
    
    # Tokens
    "debate_max_tokens": 4096,
    "synthesis_max_tokens": 8192,
    
    # Timeout
    "request_timeout": 120,
}

# =============================================================================
# PATHS
# =============================================================================

BASE_DIR = Path(__file__).parent
TOOLS_DIR = BASE_DIR / "tools"
SESSIONS_DIR = BASE_DIR / "sessions"

SESSIONS_DIR.mkdir(exist_ok=True)

# =============================================================================
# SECURITY
# =============================================================================

BLOCKED_COMMANDS = [
    "rm -rf /", "rm -rf /*", "mkfs", ":(){",
    "dd if=/dev/zero", "dd if=/dev/random",
    "> /dev/sda", "chmod -R 777 /",
]

ALLOWED_EXTENSIONS = [
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json",
    ".md", ".txt", ".yml", ".yaml", ".sh", ".bash", ".sql", ".go",
    ".rs", ".rb", ".php", ".java", ".c", ".cpp", ".h", ".hpp",
]

# =============================================================================
# UI CONFIGURATION
# =============================================================================

SHOW_THINKING = True
SHOW_TOOL_DETAILS = True
ENABLE_ANIMATIONS = True