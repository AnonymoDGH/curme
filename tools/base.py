# NVIDIA CODE - Clase Base de Herramientas

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ToolParameter:
    # Definicion de un parametro de herramienta
    name: str = ""
    type: str = "string"
    description: str = ""
    required: bool = False
    enum: Optional[List[str]] = None
    default: Any = None


class BaseTool(ABC):
    # Clase base para todas las herramientas
    
    name: str = ""
    description: str = ""
    category: str = "general"
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, ToolParameter]:
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> str:
        pass
    
    def validate_params(self, **kwargs) -> bool:
        for param_name, param in self.parameters.items():
            if param.required and param_name not in kwargs:
                return False
        return True
    
    def to_openai_format(self) -> Dict:
        properties = {}
        required = []
        
        for param_name, param in self.parameters.items():
            prop = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param_name] = prop
            
            if param.required:
                required.append(param_name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    
    def __repr__(self) -> str:
        return f"<Tool: {self.name}>"


class ToolRegistry:
    # Registro global de herramientas
    
    _tools: Dict[str, BaseTool] = {}
    _openai_format_cache: Optional[List[Dict]] = None
    _last_tool_count: int = 0
    
    @classmethod
    def register(cls, tool: BaseTool):
        cls._tools[tool.name] = tool
        # Invalidar cache cuando se registra nueva herramienta
        cls._openai_format_cache = None
        cls._last_tool_count = len(cls._tools)
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseTool]:
        return cls._tools.get(name)
    
    @classmethod
    def get_all(cls) -> List[BaseTool]:
        return list(cls._tools.values())
    
    @classmethod
    def get_by_category(cls, category: str) -> List[BaseTool]:
        return [t for t in cls._tools.values() if t.category == category]
    
    @classmethod
    def execute(cls, tool_name: str, **kwargs) -> str:
        tool = cls.get(tool_name)
        if not tool:
            return f"[x] Herramienta no encontrada: {tool_name}"
        
        try:
            # Pasar todos los kwargs directamente
            return tool.execute(**kwargs)
        except TypeError as e:
            # Si hay error de argumentos, intentar de otra forma
            error_msg = str(e)
            return f"[x] Error de argumentos en {tool_name}: {error_msg}"
        except Exception as e:
            return f"[x] Error ejecutando {tool_name}: {str(e)}"
    
    @classmethod
    def to_openai_format(cls, categories: Optional[List[str]] = None) -> List[Dict]:
        """Retorna herramientas en formato OpenAI con cache"""
        if categories is not None:
            return [tool.to_openai_format() for tool in cls._tools.values() if tool.category in categories]
            
        # Verificar si el cache es válido
        current_count = len(cls._tools)
        if (cls._openai_format_cache is not None and 
            cls._last_tool_count == current_count):
            return cls._openai_format_cache
        
        # Regenerar cache
        cls._openai_format_cache = [tool.to_openai_format() for tool in cls._tools.values()]
        cls._last_tool_count = current_count
        return cls._openai_format_cache
    
    @classmethod
    def list_names(cls) -> List[str]:
        return list(cls._tools.keys())
    
    @classmethod
    def has_tool(cls, name: str) -> bool:
        """Verifica si una herramienta está registrada"""
        return name in cls._tools