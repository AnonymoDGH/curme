"""
NVIDIA CODE - Sistema de Memoria Persistente
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import hashlib

from .base import BaseTool, ToolParameter


class MemoryStore:
    """Almacenamiento de memoria persistente"""
    
    def __init__(self, memory_dir: str = None):
        self.memory_dir = Path(memory_dir or ".nvidia_code_memory")
        self.memory_dir.mkdir(exist_ok=True)
        self.memory_file = self.memory_dir / "memory.json"
        self.memories = self._load()
    
    def _load(self) -> Dict:
        if self.memory_file.exists():
            try:
                return json.loads(self.memory_file.read_text())
            except:
                pass
        return {"items": [], "index": {}}
    
    def _save(self):
        self.memory_file.write_text(json.dumps(self.memories, indent=2, ensure_ascii=False))
    
    def store(self, key: str, value: str, category: str = "general", tags: List[str] = None) -> str:
        """Guarda un recuerdo"""
        memory_id = hashlib.md5(f"{key}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
        
        item = {
            "id": memory_id,
            "key": key,
            "value": value,
            "category": category,
            "tags": tags or [],
            "created": datetime.now().isoformat(),
            "accessed": 0
        }
        
        self.memories["items"].append(item)
        self.memories["index"][key.lower()] = memory_id
        self._save()
        
        return memory_id
    
    def recall(self, key: str) -> Optional[Dict]:
        """Recupera un recuerdo por clave"""
        key_lower = key.lower()
        
        # Buscar exacto
        if key_lower in self.memories["index"]:
            mem_id = self.memories["index"][key_lower]
            for item in self.memories["items"]:
                if item["id"] == mem_id:
                    item["accessed"] += 1
                    self._save()
                    return item
        
        # Buscar parcial
        for item in self.memories["items"]:
            if key_lower in item["key"].lower() or key_lower in item["value"].lower():
                item["accessed"] += 1
                self._save()
                return item
        
        return None
    
    def search(self, query: str, category: str = None, limit: int = 10) -> List[Dict]:
        """Busca en memorias"""
        results = []
        query_lower = query.lower()
        
        for item in self.memories["items"]:
            score = 0
            
            if query_lower in item["key"].lower():
                score += 3
            if query_lower in item["value"].lower():
                score += 2
            if query_lower in " ".join(item.get("tags", [])).lower():
                score += 1
            
            if category and item["category"] != category:
                continue
            
            if score > 0:
                results.append((score, item))
        
        results.sort(key=lambda x: (-x[0], -x[1]["accessed"]))
        return [r[1] for r in results[:limit]]
    
    def list_all(self, category: str = None) -> List[Dict]:
        """Lista todas las memorias"""
        if category:
            return [m for m in self.memories["items"] if m["category"] == category]
        return self.memories["items"]
    
    def delete(self, key: str) -> bool:
        """Elimina un recuerdo"""
        key_lower = key.lower()
        
        for i, item in enumerate(self.memories["items"]):
            if item["key"].lower() == key_lower or item["id"] == key:
                self.memories["items"].pop(i)
                if key_lower in self.memories["index"]:
                    del self.memories["index"][key_lower]
                self._save()
                return True
        
        return False


# Instancia global
_memory = None

def get_memory() -> MemoryStore:
    global _memory
    if _memory is None:
        _memory = MemoryStore()
    return _memory


class MemoryStoreTool(BaseTool):
    """Guarda informacion en memoria"""
    
    name = "memory_store"
    description = "Guarda informacion importante para recordar despues. Usa para contexto, decisiones, aprendizajes."
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "key": ToolParameter(name="key", type="string", description="Clave/nombre del recuerdo", required=True),
            "value": ToolParameter(name="value", type="string", description="Contenido a recordar", required=True),
            "category": ToolParameter(name="category", type="string", description="Categoria: context, decision, learning, note", required=False),
            "tags": ToolParameter(name="tags", type="array", description="Etiquetas para busqueda", required=False)
        }
    
    def execute(self, key: str = None, value: str = None, category: str = "general", tags: list = None, **kwargs) -> str:
        key = key or kwargs.get('key', '')
        value = value or kwargs.get('value', '')
        category = category or kwargs.get('category', 'general')
        tags = tags or kwargs.get('tags', [])
        
        if not key or not value:
            return "[x] Se requiere 'key' y 'value'"
        
        memory = get_memory()
        mem_id = memory.store(key, value, category, tags)
        
        return f"✅ Guardado en memoria: [{mem_id}] {key}"


class MemoryRecallTool(BaseTool):
    """Recupera informacion de memoria"""
    
    name = "memory_recall"
    description = "Recupera informacion guardada previamente en memoria"
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "key": ToolParameter(name="key", type="string", description="Clave o termino a buscar", required=True)
        }
    
    def execute(self, key: str = None, **kwargs) -> str:
        key = key or kwargs.get('key', '')
        
        if not key:
            return "[x] Se requiere 'key'"
        
        memory = get_memory()
        item = memory.recall(key)
        
        if item:
            return f"""📝 **Recuerdo encontrado:**
**Clave:** {item['key']}
**Categoria:** {item['category']}
**Guardado:** {item['created']}
**Accesos:** {item['accessed']}

**Contenido:**
{item['value']}
"""
        else:
            return f"[x] No encontrado: {key}"


class MemorySearchTool(BaseTool):
    """Busca en memoria"""
    
    name = "memory_search"
    description = "Busca en todas las memorias guardadas"
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "query": ToolParameter(name="query", type="string", description="Termino de busqueda", required=True),
            "category": ToolParameter(name="category", type="string", description="Filtrar por categoria", required=False)
        }
    
    def execute(self, query: str = None, category: str = None, **kwargs) -> str:
        query = query or kwargs.get('query', '')
        category = category or kwargs.get('category', None)
        
        if not query:
            return "[x] Se requiere 'query'"
        
        memory = get_memory()
        results = memory.search(query, category)
        
        if not results:
            return f"🔍 Sin resultados para: {query}"
        
        output = f"🔍 **{len(results)} resultados para '{query}':**\n\n"
        
        for item in results:
            preview = item['value'][:100] + "..." if len(item['value']) > 100 else item['value']
            output += f"• **[{item['id']}] {item['key']}** ({item['category']})\n  {preview}\n\n"
        
        return output


class MemoryListTool(BaseTool):
    """Lista todas las memorias"""
    
    name = "memory_list"
    description = "Lista todas las memorias guardadas"
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "category": ToolParameter(name="category", type="string", description="Filtrar por categoria", required=False)
        }
    
    def execute(self, category: str = None, **kwargs) -> str:
        category = category or kwargs.get('category', None)
        
        memory = get_memory()
        items = memory.list_all(category)
        
        if not items:
            return "📭 Memoria vacia"
        
        output = f"📚 **Memorias ({len(items)}):**\n\n"
        
        for item in items[-20:]:
            output += f"• [{item['id']}] **{item['key']}** ({item['category']})\n"
        
        if len(items) > 20:
            output += f"\n... y {len(items) - 20} mas"
        
        return output