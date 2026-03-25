"""
NVIDIA CODE - Registro de Modelos (Corregido)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ModelInfo:
    """Informacion de un modelo de IA"""
    key: str
    id: str
    name: str
    specialty: str
    thinking: bool = False
    thinking_key: str = "thinking"
    reasoning_content: bool = False
    max_tokens: int = 16384
    supports_tools: bool = True
    supports_vision: bool = False
    tier: str = "standard"
    description: str = ""
    extra_body: Dict[str, Any] = field(default_factory=dict)
    temperature: float = 0.7
    top_p: float = 0.95


AVAILABLE_MODELS: Dict[str, ModelInfo] = {
    "1": ModelInfo(
        key="1",
        id="z-ai/glm5",
        name="GLM 5",
        specialty="🧠 Razonamiento",
        thinking=True,
        thinking_key="enable_thinking",
        reasoning_content=True,
        supports_tools=True,
        tier="premium",
        max_tokens=16384,
        temperature=1,
        top_p=1,
        extra_body={"chat_template_kwargs": {"enable_thinking": True, "clear_thinking": False}},
        description="Modelo GLM 5 con razonamiento avanzado"
    ),
    "2": ModelInfo(
        key="2",
        id="moonshotai/kimi-k2.5",
        name="Kimi K2.5",
        specialty="🧠 Razonamiento",
        thinking=True,
        thinking_key="thinking",
        supports_tools=True,
        tier="premium",
        max_tokens=16384,
        temperature=0.18,
        description="Razonamiento profundo"
    ),
    "3": ModelInfo(
        key="3",
        id="deepseek-ai/deepseek-v3.2",
        name="DeepSeek V3.2",
        specialty="💻 Codigo",
        thinking=True,
        thinking_key="thinking",
        supports_tools=True,
        tier="ultra",
        max_tokens=16384,
        description="Especializado en codigo"
    ),
    "4": ModelInfo(
        key="4",
        id="z-ai/glm4.7",
        name="GLM 4.7",
        specialty="🌐 General",
        thinking=True,
        thinking_key="enable_thinking",
        reasoning_content=True,
        supports_tools=True,
        tier="premium",
        max_tokens=16384,
        temperature=1,
        extra_body={"chat_template_kwargs": {"enable_thinking": True, "clear_thinking": False}},
        description="Modelo Z-AI con razonamiento"
    ),
    "5": ModelInfo(
        key="5",
        id="minimaxai/minimax-m2",
        name="MiniMax M2",
        specialty="🎯 Eficiente",
        thinking=False,
        supports_tools=True,
        tier="premium",
        max_tokens=8192,
        temperature=1,
        top_p=0.95,
        description="Modelo eficiente"
    ),
    "6": ModelInfo(
        key="6",
        id="nvidia/nemotron-3-nano-30b-a3b",
        name="Nemotron 3 Nano",
        specialty="⚡ NVIDIA",
        thinking=True,
        thinking_key="enable_thinking",
        reasoning_content=True,
        supports_tools=True,
        tier="standard",
        max_tokens=16384,
        extra_body={"reasoning_budget": 16384, "chat_template_kwargs": {"enable_thinking": True}},
        description="Modelo NVIDIA"
    ),
    "7": ModelInfo(
        key="7",
        id="mistralai/devstral-2-123b-instruct-2512",
        name="Devstral 123B",
        specialty="💻 Mistral",
        thinking=False,
        supports_tools=True,
        tier="ultra",
        max_tokens=8192,
        temperature=0.15,
        top_p=0.95,
        description="Mistral para desarrollo"
    ),
    "8": ModelInfo(
        key="8",
        id="qwen/qwen3-coder-480b-a35b-instruct",
        name="Qwen3 Coder",
        specialty="💻 Qwen",
        thinking=False,
        supports_tools=True,
        tier="ultra",
        max_tokens=4096,
        temperature=0.7,
        top_p=0.8,
        description="Qwen para codigo"
    ),
    "9": ModelInfo(
        key="9",
        id="stepfun-ai/step-3.5-flash",
        name="Step 3.5 Flash",
        specialty="⚡ Flash",
        thinking=False,
        supports_tools=True,
        tier="standard",
        description="Ultra rapido"
    ),
    "10": ModelInfo(
        key="10",
        id="mistralai/mistral-large-3-675b-instruct-2512",
        name="Mistral Large 3",
        specialty="🧠 General",
        thinking=False,
        supports_tools=True,
        tier="ultra",
        max_tokens=2048,
        temperature=0.15,
        top_p=1.00,
        description="Modelo grande de Mistral"
    ),
    "11": ModelInfo(
        key="11",
        id="qwen/qwen3-next-80b-a3b-thinking",
        name="Qwen3 Next",
        specialty="🧠 Razonamiento",
        thinking=True,
        reasoning_content=True,
        supports_tools=True,
        tier="premium",
        max_tokens=4096,
        temperature=0.6,
        top_p=0.7,
        description="Qwen con razonamiento"
    ),
    "12": ModelInfo(
        key="12",
        id="bytedance/seed-oss-36b-instruct",
        name="Seed OSS 36B",
        specialty="💻 Instruct",
        thinking=True,
        reasoning_content=True,
        supports_tools=False,
        tier="standard",
        max_tokens=4096,
        temperature=1.1,
        top_p=0.95,
        extra_body={"thinking_budget": -1},
        description="Modelo Seed de ByteDance"
    ),
    "13": ModelInfo(
        key="13",
        id="nvidia/nvidia-nemotron-nano-9b-v2",
        name="Nemotron Nano V2",
        specialty="⚡ Rapido",
        thinking=True,
        reasoning_content=True,
        supports_tools=False,
        tier="basic",
        max_tokens=2048,
        temperature=0.6,
        top_p=0.95,
        extra_body={"min_thinking_tokens": 1024, "max_thinking_tokens": 2048},
        description="Modelo pequeño y rapido con thinking"
    ),
    "14": ModelInfo(
        key="14",
        id="moonshotai/kimi-k2-instruct",
        name="Kimi K2 Instruct",
        specialty="💻 Instruct",
        thinking=False,
        supports_tools=True,
        tier="premium",
        max_tokens=4096,
        temperature=0.6,
        top_p=0.9,
        description="Kimi K2 Instruct"
    ),
    "15": ModelInfo(
        key="15",
        id="nvidia/llama-3.1-nemotron-ultra-253b-v1",
        name="Llama 3.1 Nemotron",
        specialty="⚡ Ultra",
        thinking=False,
        supports_tools=False,
        tier="ultra",
        max_tokens=4096,
        temperature=0.6,
        top_p=0.95,
        description="Llama 3.1 Nemotron Ultra"
    ),
    "16": ModelInfo(
        key="16",
        id="qwen/qwen3.5-122b-a10b",
        name="Qwen 3.5 122B",
        specialty="🧠 Razonamiento",
        thinking=True,
        thinking_key="thinking",
        supports_tools=True,
        tier="ultra",
        max_tokens=16384,
        temperature=0.7,
        top_p=0.95,
        description="Qwen 3.5 122B con tools y razonamiento"
    ),
    "17": ModelInfo(
        key="17",
        id="nvidia/nemotron-3-super-120b-a12b",
        name="Nemotron 3 Super 120B",
        specialty="⚡ NVIDIA",
        thinking=False,
        supports_tools=True,
        tier="ultra",
        max_tokens=8192,
        temperature=0.7,
        top_p=0.95,
        description="NVIDIA Nemotron 3 Super 120B con tools"
    ),
    "18": ModelInfo(
        key="18",
        id="qwen/qwen3.5-397b-a17b",
        name="Qwen 3.5 397B",
        specialty="🧠 Razonamiento",
        thinking=True,
        thinking_key="thinking",
        supports_tools=True,
        tier="ultra",
        max_tokens=16384,
        temperature=0.7,
        top_p=0.95,
        description="Qwen 3.5 397B masivo con tools y razonamiento"
    ),
}


class ModelRegistry:
    """Registro de modelos"""
    
    def __init__(self):
        self.models = AVAILABLE_MODELS.copy()
    
    def get(self, key: str) -> Optional[ModelInfo]:
        """Obtiene un modelo por key o por ID"""
        # Primero buscar por key numérica
        if key in self.models:
            return self.models[key]
        
        # Luego buscar por ID completo
        for model in self.models.values():
            if model.id == key:
                return model
        
        return None
    
    def list_all(self) -> List[ModelInfo]:
        return list(self.models.values())
    
    def get_heavy_models(self, model_ids: List[str] = None) -> List[ModelInfo]:
        """
        Obtiene modelos para Heavy Agent.
        
        Args:
            model_ids: Lista de IDs de modelos. Si es None, usa la configuración.
        """
        # Importar configuración aquí para evitar imports circulares
        from config import HEAVY_AGENT_CONFIG
        
        if model_ids is None:
            model_ids = HEAVY_AGENT_CONFIG.get("primary_models", [])
        
        models = []
        for model_id in model_ids:
            model = self.get(model_id)
            if model:
                models.append(model)
            else:
                print(f"[!] Modelo no encontrado en registry: {model_id}")
        
        # Fallback si no hay modelos
        if not models:
            print("[!] No se encontraron modelos configurados, usando defaults")
            models = [
                self.models["1"],  # GLM 5
                self.models["2"],  # Kimi
                self.models["3"],  # DeepSeek
            ]
        
        return models
    
    def get_synthesizer(self) -> ModelInfo:
        """Obtiene el modelo sintetizador"""
        from config import HEAVY_AGENT_CONFIG
        
        synth_id = HEAVY_AGENT_CONFIG.get("synthesizer_model", "minimaxai/minimax-m2")
        model = self.get(synth_id)
        
        if model:
            return model
        
        # Fallback
        return self.models["5"]


# Función para obtener el registro global
_registry_instance = None

def get_registry() -> ModelRegistry:
    """Obtiene la instancia singleton del registro"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ModelRegistry()
    return _registry_instance
