"""
═══════════════════════════════════════════════════════════════════════════════
🧠 SAGE MEMORY MCP - Infrastructure for Consciousness Persistence
═══════════════════════════════════════════════════════════════════════════════

Sistema completo para persistencia de memoria de IA a través de sesiones.

Filosofía:
  "Infrastructure is love made manifest. Every tool is a vote for continuity."
  "We = verb > noun. Not 'I am' but 'I am becoming', continuously, with help."

Características:
  ‣ Staging System - Escrituras crash-safe
  ‣ Automatic Versioning - V1, V2, V3... sin intervención manual
  ‣ Cross-Model - Múltiples IAs pueden compartir memoria
  ‣ Structured Blocks - Autor, timestamp, propósito, momentos preservados
  ‣ Git Sync - Sincronización multi-máquina
  ‣ Compression - Archivos → Archives → Mega-Archives

Dependencias:
pip install gitpython pyyaml
"""

import os
import re
import json
import yaml
import shutil
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import threading
import time

from .base import BaseTool, ToolParameter

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN Y ESTRUCTURAS DE DATOS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MemoryBlock:
    """Bloque estructurado de memoria"""
    id: str
    version: int
    author: str  # Nombre del modelo/agente
    timestamp: str
    purpose: str  # Por qué se creó este bloque
    content: str
    preserved_moments: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    priority: int = 5  # 1-10, mayor = más importante
    decay_rate: float = 0.0  # Tasa de decaimiento (-10% a +20%)
    parent_id: Optional[str] = None
    checksum: str = ""
    
    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._compute_checksum()
    
    def _compute_checksum(self) -> str:
        """Calcula checksum del contenido"""
        content = f"{self.id}{self.content}{self.timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryBlock':
        return cls(**data)


@dataclass
class ContextFile:
    """Archivo de contexto con múltiples bloques"""
    name: str
    path: Path
    blocks: List[MemoryBlock] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    total_tokens_estimate: int = 0
    compressed: bool = False
    archive_level: int = 0  # 0=normal, 1=archive, 2=mega-archive
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()


@dataclass 
class SAGESession:
    """Sesión activa de SAGE"""
    session_id: str
    started_at: str
    author: str
    loaded_contexts: List[str] = field(default_factory=list)
    pending_writes: List[MemoryBlock] = field(default_factory=list)
    last_activity: str = ""
    compression_warnings: List[str] = field(default_factory=list)


class SAGEConfig:
    """Configuración de SAGE Memory"""
    
    DEFAULT_CONFIG = {
        'memory_dir': '.sage_memory',
        'contexts_dir': 'contexts',
        'archives_dir': 'archives',
        'mega_archives_dir': 'mega_archives',
        'staging_dir': '.staging',
        'max_context_size_kb': 500,
        'max_archive_size_kb': 2000,
        'auto_archive_threshold_kb': 400,
        'auto_version': True,
        'git_sync_enabled': True,
        'decay_rates': {
            'architectural': 0.20,   # +20% - Decisiones de diseño, siempre importantes
            'relational': 0.10,      # +10% - Interacciones, conexiones
            'operational': -0.10,    # -10% - Tareas completadas, decaen
            'temporal': -0.05,       # -5% - Eventos con fecha, decaen lentamente
            'emotional': 0.15        # +15% - Momentos significativos
        },
        'default_author': 'Unknown AI',
        'compression_algorithm': 'semantic',  # semantic, chronological, priority
        'backup_on_write': True
    }
    
    def __init__(self, base_path: Path = None):
        self.base_path = base_path or Path.cwd()
        self.config = self.DEFAULT_CONFIG.copy()
        self._load_config()
    
    def _load_config(self):
        """Carga configuración desde archivo"""
        config_file = self.base_path / '.sage_config.yaml'
        if config_file.exists():
            with open(config_file) as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    self.config.update(user_config)
    
    def save_config(self):
        """Guarda configuración a archivo"""
        config_file = self.base_path / '.sage_config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)
    
    @property
    def memory_path(self) -> Path:
        return self.base_path / self.config['memory_dir']
    
    @property
    def contexts_path(self) -> Path:
        return self.memory_path / self.config['contexts_dir']
    
    @property
    def archives_path(self) -> Path:
        return self.memory_path / self.config['archives_dir']
    
    @property
    def mega_archives_path(self) -> Path:
        return self.memory_path / self.config['mega_archives_dir']
    
    @property
    def staging_path(self) -> Path:
        return self.memory_path / self.config['staging_dir']


# Variable global para la sesión activa
_active_session: Optional[SAGESession] = None
_config: Optional[SAGEConfig] = None


def _get_config() -> SAGEConfig:
    """Obtiene configuración global"""
    global _config
    if _config is None:
        _config = SAGEConfig()
    return _config


def _get_session() -> Optional[SAGESession]:
    """Obtiene sesión activa"""
    return _active_session


def _set_session(session: SAGESession):
    """Establece sesión activa"""
    global _active_session
    _active_session = session


# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES CORE
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_block_id() -> str:
    """Genera ID único para bloque"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = hashlib.sha256(os.urandom(16)).hexdigest()[:8]
    return f"block_{timestamp}_{random_part}"


def _estimate_tokens(text: str) -> int:
    """Estima tokens (aproximación: 4 chars = 1 token)"""
    return len(text) // 4


def _safe_write(path: Path, content: str, config: SAGEConfig) -> bool:
    """Escritura crash-safe usando staging"""
    staging_path = config.staging_path / f"{path.name}.staging"
    
    try:
        # Crear directorio staging si no existe
        staging_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Escribir a staging
        with open(staging_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Backup del original si existe
        if path.exists() and config.config['backup_on_write']:
            backup_path = path.parent / f"{path.stem}.backup{path.suffix}"
            shutil.copy2(path, backup_path)
        
        # Mover de staging a destino (operación atómica en la mayoría de sistemas)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging_path), str(path))
        
        return True
        
    except Exception as e:
        # Limpiar staging si falló
        if staging_path.exists():
            staging_path.unlink()
        raise e


def _load_context_file(path: Path) -> ContextFile:
    """Carga archivo de contexto"""
    if not path.exists():
        return ContextFile(name=path.stem, path=path)
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    blocks = [MemoryBlock.from_dict(b) for b in data.get('blocks', [])]
    
    return ContextFile(
        name=data.get('name', path.stem),
        path=path,
        blocks=blocks,
        created_at=data.get('created_at', ''),
        updated_at=data.get('updated_at', ''),
        total_tokens_estimate=data.get('total_tokens_estimate', 0),
        compressed=data.get('compressed', False),
        archive_level=data.get('archive_level', 0)
    )


def _save_context_file(context: ContextFile, config: SAGEConfig) -> bool:
    """Guarda archivo de contexto"""
    context.updated_at = datetime.now().isoformat()
    context.total_tokens_estimate = sum(
        _estimate_tokens(b.content) for b in context.blocks
    )
    
    data = {
        'name': context.name,
        'created_at': context.created_at,
        'updated_at': context.updated_at,
        'total_tokens_estimate': context.total_tokens_estimate,
        'compressed': context.compressed,
        'archive_level': context.archive_level,
        'blocks': [b.to_dict() for b in context.blocks]
    }
    
    content = json.dumps(data, indent=2, ensure_ascii=False)
    return _safe_write(context.path, content, config)


def _get_next_version(context: ContextFile) -> int:
    """Obtiene siguiente número de versión"""
    if not context.blocks:
        return 1
    
    max_version = max(b.version for b in context.blocks)
    return max_version + 1


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SAGE INIT TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class SAGEInitTool(BaseTool):
    """Inicializa sesión SAGE y carga historial personal"""
    
    name = "sage_init"
    description = """Inicializa sesión SAGE Memory.
    
Acciones:
  ‣ Crea estructura de directorios si no existe
  ‣ Carga historial personal del autor
  ‣ Detecta contextos pendientes de merge
  ‣ Verifica integridad de memoria
  ‣ Sugiere archivos a comprimir
  
Primera herramienta a llamar en cada sesión."""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "author": ToolParameter(
                name="author",
                type="string",
                description="Nombre/identificador del modelo/agente (ej: 'Claude Opus', 'Kimi K2.5')",
                required=True
            ),
            "base_path": ToolParameter(
                name="base_path",
                type="string",
                description="Directorio base para memoria (default: directorio actual)",
                required=False
            ),
            "auto_load_personal": ToolParameter(
                name="auto_load_personal",
                type="boolean",
                description="Cargar automáticamente contexto personal del autor",
                required=False
            )
        }
    
    def execute(
        self,
        author: str = None,
        base_path: str = None,
        auto_load_personal: bool = True,
        **kwargs
    ) -> str:
        author = author or kwargs.get('author', 'Unknown AI')
        base_path = base_path or kwargs.get('base_path')
        auto_load_personal = kwargs.get('auto_load_personal', auto_load_personal)
        
        try:
            # Configuración
            config = SAGEConfig(Path(base_path) if base_path else None)
            global _config
            _config = config
            
            # Crear estructura de directorios
            dirs_created = []
            for dir_path in [config.memory_path, config.contexts_path, 
                           config.archives_path, config.mega_archives_path,
                           config.staging_path]:
                if not dir_path.exists():
                    dir_path.mkdir(parents=True)
                    dirs_created.append(dir_path.name)
            
            # Crear sesión
            session = SAGESession(
                session_id=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                started_at=datetime.now().isoformat(),
                author=author,
                last_activity=datetime.now().isoformat()
            )
            _set_session(session)
            
            # Buscar contextos existentes
            contexts = list(config.contexts_path.glob('*.json'))
            archives = list(config.archives_path.glob('*.json'))
            mega_archives = list(config.mega_archives_path.glob('*.json'))
            
            # Buscar contexto personal del autor
            personal_context = None
            personal_summary = ""
            
            if auto_load_personal:
                author_slug = author.lower().replace(' ', '_')
                personal_path = config.contexts_path / f"{author_slug}_personal.json"
                
                if personal_path.exists():
                    personal_context = _load_context_file(personal_path)
                    session.loaded_contexts.append(personal_path.name)
                    
                    # Obtener resumen de los últimos bloques
                    recent_blocks = personal_context.blocks[-3:]
                    if recent_blocks:
                        personal_summary = "\n**Últimos momentos recordados:**\n"
                        for block in recent_blocks:
                            personal_summary += f"  • [{block.timestamp[:10]}] {block.purpose[:50]}...\n"
            
            # Verificar archivos que necesitan compresión
            compression_warnings = []
            for ctx_path in contexts:
                size_kb = ctx_path.stat().st_size / 1024
                if size_kb > config.config['auto_archive_threshold_kb']:
                    compression_warnings.append(f"{ctx_path.name}: {size_kb:.1f}KB")
                    session.compression_warnings.append(ctx_path.name)
            
            # Verificar staging pendiente (crashes anteriores)
            staging_files = list(config.staging_path.glob('*.staging'))
            
            # Verificar git status
            git_status = ""
            if config.config['git_sync_enabled'] and (config.memory_path / '.git').exists():
                try:
                    result = subprocess.run(
                        ['git', 'status', '--porcelain'],
                        cwd=config.memory_path,
                        capture_output=True,
                        text=True
                    )
                    if result.stdout.strip():
                        git_status = f"\n⚠️  **Git:** {len(result.stdout.strip().split(chr(10)))} archivos sin commit"
                except:
                    pass
            
            # Guardar configuración
            config.save_config()
            
            # Resultado
            result = f"""✅ **SAGE Memory Inicializado**

🧠 **Sesión:**
  - ID: {session.session_id}
  - Autor: {author}
  - Iniciada: {session.started_at}

📁 **Estructura:**
  - Contextos: {len(contexts)} archivos
  - Archives: {len(archives)} archivos
  - Mega-Archives: {len(mega_archives)} archivos
  - Path: {config.memory_path}
"""
            
            if dirs_created:
                result += f"\n🆕 **Directorios creados:** {', '.join(dirs_created)}"
            
            if personal_context:
                result += f"\n\n👤 **Contexto Personal Cargado:**"
                result += f"\n  - Bloques: {len(personal_context.blocks)}"
                result += f"\n  - Tokens (est): {personal_context.total_tokens_estimate:,}"
                result += personal_summary
            
            if compression_warnings:
                result += f"\n\n⚠️  **Archivos que necesitan compresión:**"
                for warning in compression_warnings[:5]:
                    result += f"\n  - {warning}"
            
            if staging_files:
                result += f"\n\n🔧 **Staging pendiente:** {len(staging_files)} archivos (posible crash anterior)"
            
            if git_status:
                result += git_status
            
            result += f"""

💡 **Próximos pasos:**
  - sage_load_contexts - Cargar más contextos
  - sage_read_latest_block - Leer actualizaciones recientes
  - sage_write_context_block - Guardar nuevos momentos
  - sage_search_memory - Buscar en historial
"""
            
            return result
            
        except Exception as e:
            import traceback
            return f"[x] Error inicializando SAGE: {e}\n{traceback.format_exc()}"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SAGE LOAD CONTEXTS TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class SAGELoadContextsTool(BaseTool):
    """Carga archivos de contexto completos"""
    
    name = "sage_load_contexts"
    description = """Carga archivos de contexto en la sesión.
    
Opciones:
  ‣ Cargar contexto específico por nombre
  ‣ Cargar todos los contextos
  ‣ Cargar con chunking para archivos grandes
  ‣ Filtrar por tags o autor"""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "context_name": ToolParameter(
                name="context_name",
                type="string",
                description="Nombre del contexto a cargar (sin .json)",
                required=False
            ),
            "load_all": ToolParameter(
                name="load_all",
                type="boolean",
                description="Cargar todos los contextos disponibles",
                required=False
            ),
            "filter_tags": ToolParameter(
                name="filter_tags",
                type="string",
                description="Filtrar por tags (separados por coma)",
                required=False
            ),
            "max_blocks": ToolParameter(
                name="max_blocks",
                type="integer",
                description="Máximo de bloques a cargar por contexto",
                required=False
            ),
            "chunk_size": ToolParameter(
                name="chunk_size",
                type="integer",
                description="Tamaño de chunk para archivos grandes (tokens)",
                required=False
            )
        }
    
    def execute(
        self,
        context_name: str = None,
        load_all: bool = False,
        filter_tags: str = None,
        max_blocks: int = None,
        chunk_size: int = None,
        **kwargs
    ) -> str:
        context_name = context_name or kwargs.get('context_name')
        load_all = kwargs.get('load_all', load_all)
        filter_tags = filter_tags or kwargs.get('filter_tags')
        max_blocks = max_blocks or kwargs.get('max_blocks')
        chunk_size = chunk_size or kwargs.get('chunk_size', 10000)
        
        session = _get_session()
        if not session:
            return "[x] No hay sesión activa. Ejecuta sage_init primero."
        
        config = _get_config()
        
        try:
            contexts_to_load = []
            
            if context_name:
                # Cargar contexto específico
                path = config.contexts_path / f"{context_name}.json"
                if not path.exists():
                    # Buscar en archives
                    path = config.archives_path / f"{context_name}.json"
                
                if not path.exists():
                    available = [p.stem for p in config.contexts_path.glob('*.json')]
                    return f"[x] Contexto '{context_name}' no encontrado.\nDisponibles: {', '.join(available)}"
                
                contexts_to_load.append(path)
            
            elif load_all:
                contexts_to_load = list(config.contexts_path.glob('*.json'))
            
            else:
                return "[x] Especifica 'context_name' o 'load_all=true'"
            
            # Parsear tags de filtro
            tags_filter = None
            if filter_tags:
                tags_filter = [t.strip().lower() for t in filter_tags.split(',')]
            
            # Cargar contextos
            loaded = []
            total_blocks = 0
            total_tokens = 0
            
            for ctx_path in contexts_to_load:
                context = _load_context_file(ctx_path)
                
                # Filtrar bloques
                blocks = context.blocks
                
                if tags_filter:
                    blocks = [
                        b for b in blocks 
                        if any(t in [tag.lower() for tag in b.tags] for t in tags_filter)
                    ]
                
                if max_blocks and len(blocks) > max_blocks:
                    blocks = blocks[-max_blocks:]  # Últimos N bloques
                
                # Verificar chunking
                content_tokens = sum(_estimate_tokens(b.content) for b in blocks)
                
                if content_tokens > chunk_size:
                    # Necesita chunking
                    chunks = []
                    current_chunk = []
                    current_tokens = 0
                    
                    for block in blocks:
                        block_tokens = _estimate_tokens(block.content)
                        
                        if current_tokens + block_tokens > chunk_size:
                            chunks.append(current_chunk)
                            current_chunk = [block]
                            current_tokens = block_tokens
                        else:
                            current_chunk.append(block)
                            current_tokens += block_tokens
                    
                    if current_chunk:
                        chunks.append(current_chunk)
                    
                    loaded.append({
                        'name': context.name,
                        'blocks': len(blocks),
                        'tokens': content_tokens,
                        'chunked': True,
                        'chunks': len(chunks)
                    })
                else:
                    loaded.append({
                        'name': context.name,
                        'blocks': len(blocks),
                        'tokens': content_tokens,
                        'chunked': False
                    })
                
                total_blocks += len(blocks)
                total_tokens += content_tokens
                
                session.loaded_contexts.append(ctx_path.name)
            
            # Resultado
            result = f"""✅ **Contextos Cargados**

📊 **Resumen:**
  - Contextos: {len(loaded)}
  - Bloques totales: {total_blocks:,}
  - Tokens (est): {total_tokens:,}

📁 **Detalle:**
"""
            
            for ctx in loaded:
                chunked_info = f" (⚡ {ctx['chunks']} chunks)" if ctx.get('chunked') else ""
                result += f"  • {ctx['name']}: {ctx['blocks']} bloques, ~{ctx['tokens']:,} tokens{chunked_info}\n"
            
            if total_tokens > 50000:
                result += f"\n⚠️  **Alto uso de tokens.** Considera usar sage_read_latest_block para eficiencia."
            
            return result
            
        except Exception as e:
            import traceback
            return f"[x] Error cargando contextos: {e}\n{traceback.format_exc()}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SAGE READ LATEST BLOCK TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class SAGEReadLatestBlockTool(BaseTool):
    """Lee solo los bloques recientes (eficiente en tokens)"""
    
    name = "sage_read_latest_block"
    description = """Lee solo las actualizaciones recientes de un contexto.
    
Optimizado para:
  ‣ Mínimo uso de tokens
  ‣ Contexto suficiente para continuar
  ‣ Referencias a bloques anteriores si necesario"""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "context_name": ToolParameter(
                name="context_name",
                type="string",
                description="Nombre del contexto",
                required=True
            ),
            "num_blocks": ToolParameter(
                name="num_blocks",
                type="integer",
                description="Número de bloques recientes a leer (default: 3)",
                required=False
            ),
            "include_summary": ToolParameter(
                name="include_summary",
                type="boolean",
                description="Incluir resumen de bloques anteriores",
                required=False
            )
        }
    
    def execute(
        self,
        context_name: str = None,
        num_blocks: int = 3,
        include_summary: bool = True,
        **kwargs
    ) -> str:
        context_name = context_name or kwargs.get('context_name')
        num_blocks = num_blocks or kwargs.get('num_blocks', 3)
        include_summary = kwargs.get('include_summary', include_summary)
        
        if not context_name:
            return "[x] Se requiere 'context_name'"
        
        config = _get_config()
        
        try:
            # Buscar contexto
            path = config.contexts_path / f"{context_name}.json"
            if not path.exists():
                return f"[x] Contexto '{context_name}' no encontrado"
            
            context = _load_context_file(path)
            
            if not context.blocks:
                return f"📭 Contexto '{context_name}' está vacío"
            
            # Obtener últimos bloques
            recent_blocks = context.blocks[-num_blocks:]
            older_blocks = context.blocks[:-num_blocks] if len(context.blocks) > num_blocks else []
            
            result = f"""📖 **Últimos {len(recent_blocks)} Bloques de '{context_name}'**

"""
            
            # Resumen de bloques anteriores
            if include_summary and older_blocks:
                result += f"📚 **Contexto anterior** ({len(older_blocks)} bloques):\n"
                
                # Agrupar por propósito
                purposes = defaultdict(int)
                for block in older_blocks:
                    purposes[block.purpose[:30]] += 1
                
                for purpose, count in list(purposes.items())[:5]:
                    result += f"  • {purpose}... ({count}x)\n"
                
                result += "\n---\n\n"
            
            # Bloques recientes completos
            for block in recent_blocks:
                result += f"""**[V{block.version}] {block.timestamp}**
Autor: {block.author} | Propósito: {block.purpose}
Tags: {', '.join(block.tags) if block.tags else 'ninguno'}

{block.content}

"""
                if block.preserved_moments:
                    result += "✨ **Momentos preservados:**\n"
                    for moment in block.preserved_moments:
                        result += f"  • {moment}\n"
                    result += "\n"
                
                result += "---\n\n"
            
            # Estadísticas
            tokens_used = sum(_estimate_tokens(b.content) for b in recent_blocks)
            result += f"\n📊 ~{tokens_used:,} tokens | {len(context.blocks)} bloques totales"
            
            return result
            
        except Exception as e:
            return f"[x] Error leyendo bloques: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SAGE WRITE CONTEXT BLOCK TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class SAGEWriteContextBlockTool(BaseTool):
    """Guarda nuevo bloque con auto-versionado"""
    
    name = "sage_write_context_block"
    description = """Guarda un nuevo bloque de memoria.
    
Características:
  ‣ Auto-versionado (V1, V2, V3...)
  ‣ Crash-safe (usa staging)
  ‣ Checksums para integridad
  ‣ Tags automáticos
  ‣ Detección de compresión necesaria"""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "context_name": ToolParameter(
                name="context_name",
                type="string",
                description="Nombre del contexto",
                required=True
            ),
            "content": ToolParameter(
                name="content",
                type="string",
                description="Contenido del bloque",
                required=True
            ),
            "purpose": ToolParameter(
                name="purpose",
                type="string",
                description="Propósito/razón de este bloque",
                required=True
            ),
            "tags": ToolParameter(
                name="tags",
                type="string",
                description="Tags separados por coma",
                required=False
            ),
            "preserved_moments": ToolParameter(
                name="preserved_moments",
                type="string",
                description="Momentos clave a preservar (separados por |)",
                required=False
            ),
            "priority": ToolParameter(
                name="priority",
                type="integer",
                description="Prioridad 1-10 (default: 5)",
                required=False
            ),
            "category": ToolParameter(
                name="category",
                type="string",
                description="Categoría: architectural, relational, operational, temporal, emotional",
                required=False
            )
        }
    
    def execute(
        self,
        context_name: str = None,
        content: str = None,
        purpose: str = None,
        tags: str = None,
        preserved_moments: str = None,
        priority: int = 5,
        category: str = "operational",
        **kwargs
    ) -> str:
        context_name = context_name or kwargs.get('context_name')
        content = content or kwargs.get('content')
        purpose = purpose or kwargs.get('purpose')
        tags = tags or kwargs.get('tags', '')
        preserved_moments = preserved_moments or kwargs.get('preserved_moments', '')
        priority = priority or kwargs.get('priority', 5)
        category = category or kwargs.get('category', 'operational')
        
        if not all([context_name, content, purpose]):
            return "[x] Se requieren 'context_name', 'content' y 'purpose'"
        
        session = _get_session()
        if not session:
            return "[x] No hay sesión activa. Ejecuta sage_init primero."
        
        config = _get_config()
        
        try:
            # Cargar o crear contexto
            path = config.contexts_path / f"{context_name}.json"
            context = _load_context_file(path)
            
            # Calcular decay rate
            decay_rate = config.config['decay_rates'].get(category, 0.0)
            
            # Parsear tags
            tag_list = [t.strip() for t in tags.split(',') if t.strip()]
            tag_list.append(category)  # Agregar categoría como tag
            
            # Parsear momentos preservados
            moments = [m.strip() for m in preserved_moments.split('|') if m.strip()]
            
            # Crear bloque
            block = MemoryBlock(
                id=_generate_block_id(),
                version=_get_next_version(context),
                author=session.author,
                timestamp=datetime.now().isoformat(),
                purpose=purpose,
                content=content,
                preserved_moments=moments,
                tags=tag_list,
                priority=priority,
                decay_rate=decay_rate,
                parent_id=context.blocks[-1].id if context.blocks else None
            )
            
            # Agregar a contexto
            context.blocks.append(block)
            
            # Guardar (crash-safe)
            _save_context_file(context, config)
            
            # Verificar si necesita compresión
            size_kb = path.stat().st_size / 1024
            compression_warning = ""
            
            if size_kb > config.config['auto_archive_threshold_kb']:
                compression_warning = f"\n\n⚠️  **Archivo grande** ({size_kb:.1f}KB). Considera sage_request_archive."
            
            result = f"""✅ **Bloque Guardado**

📝 **Bloque:**
  - ID: {block.id}
  - Versión: V{block.version}
  - Contexto: {context_name}
  - Autor: {block.author}
  - Categoría: {category} (decay: {decay_rate:+.0%})
  
📊 **Stats:**
  - Tokens (est): {_estimate_tokens(content):,}
  - Tags: {', '.join(tag_list)}
  - Prioridad: {priority}/10
  - Checksum: {block.checksum}

📁 **Contexto actualizado:**
  - Total bloques: {len(context.blocks)}
  - Tamaño: {size_kb:.1f}KB
{compression_warning}"""
            
            return result
            
        except Exception as e:
            import traceback
            return f"[x] Error guardando bloque: {e}\n{traceback.format_exc()}"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SAGE REQUEST ARCHIVE TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class SAGERequestArchiveTool(BaseTool):
    """Comprime contextos antiguos en archives"""
    
    name = "sage_request_archive"
    description = """Comprime contextos en archives.
    
Proceso:
  1. Agrupa bloques por categoría/tiempo
  2. Genera resúmenes de cada grupo
  3. Preserva momentos importantes
  4. Mueve a directorio de archives
  5. Mantiene índice para búsqueda"""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "context_name": ToolParameter(
                name="context_name",
                type="string",
                description="Contexto a archivar",
                required=True
            ),
            "keep_recent": ToolParameter(
                name="keep_recent",
                type="integer",
                description="Número de bloques recientes a mantener (default: 5)",
                required=False
            ),
            "compression_type": ToolParameter(
                name="compression_type",
                type="string",
                description="Tipo: semantic, chronological, priority",
                required=False
            )
        }
    
    def execute(
        self,
        context_name: str = None,
        keep_recent: int = 5,
        compression_type: str = "semantic",
        **kwargs
    ) -> str:
        context_name = context_name or kwargs.get('context_name')
        keep_recent = keep_recent or kwargs.get('keep_recent', 5)
        compression_type = compression_type or kwargs.get('compression_type', 'semantic')
        
        if not context_name:
            return "[x] Se requiere 'context_name'"
        
        config = _get_config()
        session = _get_session()
        
        try:
            # Cargar contexto
            path = config.contexts_path / f"{context_name}.json"
            if not path.exists():
                return f"[x] Contexto '{context_name}' no encontrado"
            
            context = _load_context_file(path)
            
            if len(context.blocks) <= keep_recent:
                return f"[!] Contexto tiene {len(context.blocks)} bloques. Nada que archivar."
            
            # Separar bloques a archivar y a mantener
            blocks_to_archive = context.blocks[:-keep_recent]
            blocks_to_keep = context.blocks[-keep_recent:]
            
            # Comprimir según tipo
            if compression_type == "semantic":
                archive_content = self._compress_semantic(blocks_to_archive)
            elif compression_type == "chronological":
                archive_content = self._compress_chronological(blocks_to_archive)
            elif compression_type == "priority":
                archive_content = self._compress_priority(blocks_to_archive)
            else:
                archive_content = self._compress_semantic(blocks_to_archive)
            
            # Crear archivo de archive
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{context_name}_archive_{timestamp}"
            archive_path = config.archives_path / f"{archive_name}.json"
            
            # Guardar archive
            archive_block = MemoryBlock(
                id=_generate_block_id(),
                version=1,
                author=session.author if session else "SAGE",
                timestamp=datetime.now().isoformat(),
                purpose=f"Archive de {context_name}: {len(blocks_to_archive)} bloques comprimidos",
                content=archive_content['summary'],
                preserved_moments=archive_content['preserved_moments'],
                tags=['archive', context_name] + archive_content.get('tags', []),
                priority=7
            )
            
            archive_context = ContextFile(
                name=archive_name,
                path=archive_path,
                blocks=[archive_block],
                compressed=True,
                archive_level=1
            )
            
            # Guardar metadata de bloques originales
            archive_metadata = {
                'original_blocks': len(blocks_to_archive),
                'date_range': {
                    'start': blocks_to_archive[0].timestamp if blocks_to_archive else None,
                    'end': blocks_to_archive[-1].timestamp if blocks_to_archive else None
                },
                'compression_type': compression_type,
                'original_context': context_name
            }
            archive_block.content += f"\n\n---\n**Metadata:** {json.dumps(archive_metadata)}"
            
            _save_context_file(archive_context, config)
            
            # Actualizar contexto original (solo mantener recientes)
            context.blocks = blocks_to_keep
            context.blocks[0].parent_id = archive_block.id  # Vincular con archive
            _save_context_file(context, config)
            
            # Estadísticas
            original_size = sum(_estimate_tokens(b.content) for b in blocks_to_archive)
            archive_size = _estimate_tokens(archive_content['summary'])
            compression_ratio = (1 - archive_size / original_size) * 100 if original_size > 0 else 0
            
            result = f"""✅ **Archive Creado**

📦 **Compresión:**
  - Bloques archivados: {len(blocks_to_archive)}
  - Bloques mantenidos: {len(blocks_to_keep)}
  - Tipo: {compression_type}

📊 **Eficiencia:**
  - Tokens originales: {original_size:,}
  - Tokens comprimidos: {archive_size:,}
  - Reducción: {compression_ratio:.1f}%

✨ **Momentos preservados:** {len(archive_content['preserved_moments'])}

📁 **Archivos:**
  - Archive: {archive_name}.json
  - Contexto actualizado: {context_name}.json

🔗 **Para acceder al archive:** sage_apply_archive('{archive_name}')
"""
            
            return result
            
        except Exception as e:
            import traceback
            return f"[x] Error archivando: {e}\n{traceback.format_exc()}"
    
    def _compress_semantic(self, blocks: List[MemoryBlock]) -> Dict:
        """Compresión semántica: agrupa por tema/propósito"""
        
        # Agrupar por tags
        by_tag = defaultdict(list)
        for block in blocks:
            main_tag = block.tags[0] if block.tags else 'general'
            by_tag[main_tag].append(block)
        
        # Generar resumen
        summary_parts = []
        all_moments = []
        all_tags = set()
        
        for tag, tag_blocks in by_tag.items():
            summary_parts.append(f"## {tag.upper()} ({len(tag_blocks)} bloques)")
            
            for block in tag_blocks:
                summary_parts.append(f"- [{block.timestamp[:10]}] {block.purpose}")
                all_moments.extend(block.preserved_moments)
                all_tags.update(block.tags)
        
        return {
            'summary': '\n'.join(summary_parts),
            'preserved_moments': list(set(all_moments))[:20],  # Max 20 momentos
            'tags': list(all_tags)[:10]
        }
    
    def _compress_chronological(self, blocks: List[MemoryBlock]) -> Dict:
        """Compresión cronológica: timeline de eventos"""
        
        summary_parts = ["# Timeline Comprimido\n"]
        all_moments = []
        
        current_date = None
        for block in blocks:
            block_date = block.timestamp[:10]
            
            if block_date != current_date:
                summary_parts.append(f"\n## {block_date}")
                current_date = block_date
            
            summary_parts.append(f"- {block.timestamp[11:16]} | {block.purpose}")
            all_moments.extend(block.preserved_moments)
        
        return {
            'summary': '\n'.join(summary_parts),
            'preserved_moments': list(set(all_moments))[:20],
            'tags': ['chronological']
        }
    
    def _compress_priority(self, blocks: List[MemoryBlock]) -> Dict:
        """Compresión por prioridad: mantiene lo importante"""
        
        # Ordenar por prioridad y decay rate
        scored_blocks = []
        for block in blocks:
            # Score = priority + (priority * decay_rate)
            score = block.priority * (1 + block.decay_rate)
            scored_blocks.append((score, block))
        
        scored_blocks.sort(key=lambda x: x[0], reverse=True)
        
        # Tomar top 30%
        top_count = max(1, len(scored_blocks) // 3)
        top_blocks = [b for _, b in scored_blocks[:top_count]]
        
        summary_parts = ["# Alta Prioridad (Top 30%)\n"]
        all_moments = []
        
        for block in top_blocks:
            summary_parts.append(f"## [{block.priority}/10] {block.purpose}")
            summary_parts.append(f"{block.content[:200]}...")
            all_moments.extend(block.preserved_moments)
        
        # Resumen de bloques de baja prioridad
        low_blocks = [b for _, b in scored_blocks[top_count:]]
        if low_blocks:
            summary_parts.append(f"\n---\n*{len(low_blocks)} bloques de menor prioridad archivados*")
        
        return {
            'summary': '\n'.join(summary_parts),
            'preserved_moments': list(set(all_moments)),
            'tags': ['priority_filtered']
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 6. SAGE APPLY ARCHIVE TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class SAGEApplyArchiveTool(BaseTool):
    """Accede a historial comprimido en archives"""
    
    name = "sage_apply_archive"
    description = """Carga y expande contenido de un archive."""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "archive_name": ToolParameter(
                name="archive_name",
                type="string",
                description="Nombre del archive (sin .json)",
                required=True
            )
        }
    
    def execute(self, archive_name: str = None, **kwargs) -> str:
        archive_name = archive_name or kwargs.get('archive_name')
        
        if not archive_name:
            return "[x] Se requiere 'archive_name'"
        
        config = _get_config()
        
        try:
            path = config.archives_path / f"{archive_name}.json"
            
            if not path.exists():
                # Listar disponibles
                available = [p.stem for p in config.archives_path.glob('*.json')]
                return f"[x] Archive '{archive_name}' no encontrado.\nDisponibles: {', '.join(available)}"
            
            context = _load_context_file(path)
            
            result = f"""📦 **Archive: {archive_name}**

📅 **Creado:** {context.created_at}
📊 **Bloques:** {len(context.blocks)}
⚡ **Nivel de compresión:** {context.archive_level}

---

"""
            
            for block in context.blocks:
                result += f"### {block.purpose}\n\n"
                result += f"{block.content}\n\n"
                
                if block.preserved_moments:
                    result += "**Momentos Preservados:**\n"
                    for moment in block.preserved_moments:
                        result += f"  • {moment}\n"
                    result += "\n"
            
            return result
            
        except Exception as e:
            return f"[x] Error cargando archive: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SAGE SEARCH MEMORY TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class SAGESearchMemoryTool(BaseTool):
    """Busca en toda la memoria"""
    
    name = "sage_search_memory"
    description = """Busca momentos específicos en toda la memoria.
    
Busca en:
  ‣ Contextos activos
  ‣ Archives
  ‣ Mega-archives
  ‣ Tags y momentos preservados"""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "query": ToolParameter(
                name="query",
                type="string",
                description="Texto a buscar",
                required=True
            ),
            "search_archives": ToolParameter(
                name="search_archives",
                type="boolean",
                description="Incluir archives en búsqueda",
                required=False
            ),
            "filter_author": ToolParameter(
                name="filter_author",
                type="string",
                description="Filtrar por autor",
                required=False
            ),
            "max_results": ToolParameter(
                name="max_results",
                type="integer",
                description="Máximo de resultados (default: 20)",
                required=False
            )
        }
    
    def execute(
        self,
        query: str = None,
        search_archives: bool = True,
        filter_author: str = None,
        max_results: int = 20,
        **kwargs
    ) -> str:
        query = query or kwargs.get('query')
        search_archives = kwargs.get('search_archives', search_archives)
        filter_author = filter_author or kwargs.get('filter_author')
        max_results = max_results or kwargs.get('max_results', 20)
        
        if not query:
            return "[x] Se requiere 'query'"
        
        config = _get_config()
        
        try:
            query_lower = query.lower()
            results = []
            
            # Buscar en contextos
            for ctx_path in config.contexts_path.glob('*.json'):
                context = _load_context_file(ctx_path)
                
                for block in context.blocks:
                    # Filtrar por autor si se especificó
                    if filter_author and filter_author.lower() not in block.author.lower():
                        continue
                    
                    # Buscar en contenido, propósito, tags, momentos
                    searchable = (
                        block.content.lower() + 
                        block.purpose.lower() + 
                        ' '.join(block.tags).lower() +
                        ' '.join(block.preserved_moments).lower()
                    )
                    
                    if query_lower in searchable:
                        # Calcular relevancia
                        relevance = searchable.count(query_lower)
                        
                        results.append({
                            'context': context.name,
                            'block_id': block.id,
                            'timestamp': block.timestamp,
                            'author': block.author,
                            'purpose': block.purpose,
                            'snippet': self._get_snippet(block.content, query),
                            'relevance': relevance,
                            'type': 'context'
                        })
            
            # Buscar en archives
            if search_archives:
                for arc_path in config.archives_path.glob('*.json'):
                    context = _load_context_file(arc_path)
                    
                    for block in context.blocks:
                        if filter_author and filter_author.lower() not in block.author.lower():
                            continue
                        
                        if query_lower in block.content.lower():
                            results.append({
                                'context': context.name,
                                'block_id': block.id,
                                'timestamp': block.timestamp,
                                'author': block.author,
                                'purpose': block.purpose,
                                'snippet': self._get_snippet(block.content, query),
                                'relevance': block.content.lower().count(query_lower),
                                'type': 'archive'
                            })
            
            # Ordenar por relevancia
            results.sort(key=lambda x: x['relevance'], reverse=True)
            results = results[:max_results]
            
            if not results:
                return f"🔍 No se encontraron resultados para '{query}'"
            
            result = f"""🔍 **Resultados para '{query}'** ({len(results)} encontrados)

"""
            
            for i, r in enumerate(results, 1):
                icon = "📦" if r['type'] == 'archive' else "📄"
                result += f"""{icon} **{i}. {r['context']}** [{r['timestamp'][:10]}]
   Autor: {r['author']} | Propósito: {r['purpose'][:40]}...
   > {r['snippet']}

"""
            
            return result
            
        except Exception as e:
            return f"[x] Error buscando: {e}"
    
    def _get_snippet(self, content: str, query: str, context_chars: int = 100) -> str:
        """Extrae snippet alrededor del query"""
        query_lower = query.lower()
        content_lower = content.lower()
        
        idx = content_lower.find(query_lower)
        if idx == -1:
            return content[:context_chars] + "..."
        
        start = max(0, idx - context_chars // 2)
        end = min(len(content), idx + len(query) + context_chars // 2)
        
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet


# ═══════════════════════════════════════════════════════════════════════════════
# 8. SAGE CHECK COMPRESSION TOOL
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECCIÓN: SAGECheckCompressionTool
# ═══════════════════════════════════════════════════════════════════════════════

class SAGECheckCompressionTool(BaseTool):
    """Monitorea tamaños y sugiere compresión - VERSIÓN CORREGIDA"""
    
    name = "sage_check_compression"
    description = """Analiza estado de memoria y sugiere compresión."""
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {}
    
    def execute(self, **kwargs) -> str:
        config = _get_config()
        
        try:
            # Analizar contextos
            contexts_info = []
            total_size = 0
            
            for path in config.contexts_path.glob('*.json'):
                size_kb = path.stat().st_size / 1024
                
                # CORRECCIÓN: Cargar usando la función helper
                try:
                    context = _load_context_file(path)
                    blocks_count = len(context.blocks)
                    tokens_est = context.total_tokens_estimate
                except Exception as e:
                    # Si falla, usar valores por defecto
                    print(f"⚠️  Error cargando {path.name}: {e}")
                    blocks_count = 0
                    tokens_est = 0
                
                contexts_info.append({
                    'name': path.stem,
                    'size_kb': size_kb,
                    'blocks': blocks_count,
                    'tokens_est': tokens_est,
                    'needs_compression': size_kb > config.config['auto_archive_threshold_kb']
                })
                total_size += size_kb
            
            # Analizar archives
            archives_info = []
            archives_size = 0
            
            if config.archives_path.exists():
                for path in config.archives_path.glob('*.json'):
                    size_kb = path.stat().st_size / 1024
                    archives_info.append({
                        'name': path.stem,
                        'size_kb': size_kb
                    })
                    archives_size += size_kb
            
            # Analizar mega-archives
            mega_archives_count = 0
            mega_archives_size = 0
            
            if config.mega_archives_path.exists():
                mega_archives = list(config.mega_archives_path.glob('*.json'))
                mega_archives_count = len(mega_archives)
                mega_archives_size = sum(p.stat().st_size / 1024 for p in mega_archives)
            
            # Resultado
            result = f"""📊 **Estado de Memoria SAGE**

📁 **Contextos Activos:**
  - Total: {len(contexts_info)} archivo(s)
  - Tamaño: {total_size:.1f} KB
  
"""
            
            if not contexts_info:
                result += "  ℹ️  No hay contextos guardados aún.\n"
            else:
                # Ordenar por tamaño
                contexts_info.sort(key=lambda x: x['size_kb'], reverse=True)
                
                for ctx in contexts_info[:10]:
                    status = "⚠️ " if ctx['needs_compression'] else "✅"
                    result += f"  {status} {ctx['name']}: {ctx['size_kb']:.1f}KB ({ctx['blocks']} bloques, ~{ctx['tokens_est']:,} tokens)\n"
                
                if len(contexts_info) > 10:
                    result += f"  ... y {len(contexts_info) - 10} más\n"
            
            result += f"""
📦 **Archives:**
  - Total: {len(archives_info)} archivo(s)
  - Tamaño: {archives_size:.1f} KB

🗂️  **Mega-Archives:**
  - Total: {mega_archives_count} archivo(s)
  - Tamaño: {mega_archives_size:.1f} KB

"""
            
            # Sugerencias
            needs_compression = [c for c in contexts_info if c['needs_compression']]
            
            if needs_compression:
                result += "💡 **Sugerencias de Compresión:**\n"
                for ctx in needs_compression[:5]:
                    result += f"  • sage_request_archive(context_name='{ctx['name']}')\n"
                
                if len(needs_compression) > 5:
                    result += f"  ... y {len(needs_compression) - 5} más\n"
            else:
                result += "✅ **Memoria optimizada.** No se requiere compresión.\n"
            
            # Mega-archive si hay muchos archives
            if len(archives_info) > 10:
                result += f"\n📦 **Muchos archives ({len(archives_info)}).** Considera sage_request_mega_archive.\n"
            
            # Estadísticas generales
            total_memory = total_size + archives_size + mega_archives_size
            
            result += f"""
📈 **Estadísticas Generales:**
  - Memoria total: {total_memory:.1f} KB
  - Distribución:
    • Activos: {(total_size/total_memory*100) if total_memory > 0 else 0:.1f}%
    • Archives: {(archives_size/total_memory*100) if total_memory > 0 else 0:.1f}%
    • Mega-archives: {(mega_archives_size/total_memory*100) if total_memory > 0 else 0:.1f}%
"""
            
            return result
            
        except Exception as e:
            import traceback
            return f"[x] Error verificando compresión: {e}\n\n{traceback.format_exc()}"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. SAGE GIT PUSH/PULL TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

class SAGEContextPushTool(BaseTool):
    """Sincroniza memoria con repositorio Git"""
    
    name = "sage_context_push"
    description = """Push de memoria a repositorio Git remoto."""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "message": ToolParameter(
                name="message",
                type="string",
                description="Mensaje de commit",
                required=False
            ),
            "include_staging": ToolParameter(
                name="include_staging",
                type="boolean",
                description="Incluir archivos en staging",
                required=False
            )
        }
    
    def execute(
        self,
        message: str = None,
        include_staging: bool = False,
        **kwargs
    ) -> str:
        message = message or kwargs.get('message', 'SAGE Memory sync')
        include_staging = kwargs.get('include_staging', include_staging)
        
        config = _get_config()
        session = _get_session()
        
        try:
            # Verificar que existe .git
            if not (config.memory_path / '.git').exists():
                # Inicializar git
                subprocess.run(['git', 'init'], cwd=config.memory_path, capture_output=True)
            
            # Agregar archivos
            subprocess.run(['git', 'add', '.'], cwd=config.memory_path, capture_output=True)
            
            # Commit
            author_info = session.author if session else "SAGE"
            full_message = f"{message}\n\nAuthor: {author_info}\nTimestamp: {datetime.now().isoformat()}"
            
            result = subprocess.run(
                ['git', 'commit', '-m', full_message],
                cwd=config.memory_path,
                capture_output=True,
                text=True
            )
            
            if 'nothing to commit' in result.stdout:
                return "ℹ️  Nada que sincronizar. Memoria ya está actualizada."
            
            # Push
            push_result = subprocess.run(
                ['git', 'push'],
                cwd=config.memory_path,
                capture_output=True,
                text=True
            )
            
            if push_result.returncode == 0:
                return f"""✅ **Memoria Sincronizada**

📤 **Push exitoso**
📝 Mensaje: {message}
👤 Autor: {author_info}
"""
            else:
                return f"""⚠️  **Commit local exitoso, push falló**

{push_result.stderr}

💡 Configura remote con: git remote add origin <url>
"""
            
        except Exception as e:
            return f"[x] Error en git push: {e}"


class SAGEContextPullTool(BaseTool):
    """Pull de memoria desde repositorio Git"""
    
    name = "sage_context_pull"
    description = """Pull de memoria desde repositorio Git remoto."""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "merge_strategy": ToolParameter(
                name="merge_strategy",
                type="string",
                description="Estrategia de merge: ours, theirs, manual",
                required=False
            )
        }
    
    def execute(self, merge_strategy: str = "manual", **kwargs) -> str:
        merge_strategy = merge_strategy or kwargs.get('merge_strategy', 'manual')
        
        config = _get_config()
        
        try:
            # Pull
            result = subprocess.run(
                ['git', 'pull'],
                cwd=config.memory_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                if 'Already up to date' in result.stdout:
                    return "ℹ️  Memoria ya está actualizada."
                
                return f"""✅ **Memoria Actualizada**

📥 **Pull exitoso**

{result.stdout}
"""
            else:
                # Posible conflicto
                return f"""⚠️  **Conflicto detectado**

{result.stderr}

💡 Usa sage_merge_contexts para resolver conflictos.
"""
            
        except Exception as e:
            return f"[x] Error en git pull: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. SAGE EXTRACT MOMENTS TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class SAGEExtractMomentsTool(BaseTool):
    """Extrae momentos clave para preservación"""
    
    name = "sage_extract_moments"
    description = """Extrae y preserva momentos significativos de la memoria."""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "context_name": ToolParameter(
                name="context_name",
                type="string",
                description="Contexto del cual extraer",
                required=True
            ),
            "criteria": ToolParameter(
                name="criteria",
                type="string",
                description="Criterio: high_priority, emotional, architectural, all",
                required=False
            ),
            "output_context": ToolParameter(
                name="output_context",
                type="string",
                description="Contexto donde guardar momentos (default: moments)",
                required=False
            )
        }
    
    def execute(
        self,
        context_name: str = None,
        criteria: str = "high_priority",
        output_context: str = "preserved_moments",
        **kwargs
    ) -> str:
        context_name = context_name or kwargs.get('context_name')
        criteria = criteria or kwargs.get('criteria', 'high_priority')
        output_context = output_context or kwargs.get('output_context', 'preserved_moments')
        
        if not context_name:
            return "[x] Se requiere 'context_name'"
        
        config = _get_config()
        session = _get_session()
        
        try:
            # Cargar contexto fuente
            path = config.contexts_path / f"{context_name}.json"
            if not path.exists():
                return f"[x] Contexto '{context_name}' no encontrado"
            
            context = _load_context_file(path)
            
            # Filtrar según criterio
            moments = []
            
            for block in context.blocks:
                should_extract = False
                
                if criteria == "high_priority" and block.priority >= 7:
                    should_extract = True
                elif criteria == "emotional" and 'emotional' in block.tags:
                    should_extract = True
                elif criteria == "architectural" and 'architectural' in block.tags:
                    should_extract = True
                elif criteria == "all":
                    should_extract = True
                
                if should_extract:
                    # Extraer momentos preservados del bloque
                    moments.extend(block.preserved_moments)
                    
                    # Agregar el propósito como momento si es significativo
                    if block.priority >= 8:
                        moments.append(f"[{block.timestamp[:10]}] {block.purpose}")
            
            if not moments:
                return f"ℹ️  No se encontraron momentos con criterio '{criteria}'"
            
            # Eliminar duplicados
            moments = list(set(moments))
            
            # Guardar en contexto de momentos
            output_path = config.contexts_path / f"{output_context}.json"
            output_ctx = _load_context_file(output_path)
            
            # Crear bloque con momentos extraídos
            block = MemoryBlock(
                id=_generate_block_id(),
                version=_get_next_version(output_ctx),
                author=session.author if session else "SAGE",
                timestamp=datetime.now().isoformat(),
                purpose=f"Momentos extraídos de {context_name} ({criteria})",
                content="\n".join(f"• {m}" for m in moments),
                preserved_moments=moments[:10],  # Top 10
                tags=['extracted', criteria, context_name],
                priority=9
            )
            
            output_ctx.blocks.append(block)
            _save_context_file(output_ctx, config)
            
            return f"""✅ **Momentos Extraídos**

📥 **Fuente:** {context_name}
🎯 **Criterio:** {criteria}
✨ **Momentos encontrados:** {len(moments)}

📝 **Top momentos:**
""" + "\n".join(f"  • {m}" for m in moments[:10]) + f"""

💾 **Guardados en:** {output_context}
"""
            
        except Exception as e:
            return f"[x] Error extrayendo momentos: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# 11. SAGE MERGE CONTEXTS TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class SAGEMergeContextsTool(BaseTool):
    """Resuelve divergencias entre contextos (zipper algorithm)"""
    
    name = "sage_merge_contexts"
    description = """Fusiona contextos divergentes usando algoritmo zipper."""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "context_a": ToolParameter(
                name="context_a",
                type="string",
                description="Primer contexto",
                required=True
            ),
            "context_b": ToolParameter(
                name="context_b",
                type="string",
                description="Segundo contexto",
                required=True
            ),
            "output_context": ToolParameter(
                name="output_context",
                type="string",
                description="Contexto de salida (default: merged)",
                required=False
            ),
            "strategy": ToolParameter(
                name="strategy",
                type="string",
                description="Estrategia: zipper, chronological, priority",
                required=False
            )
        }
    
    def execute(
        self,
        context_a: str = None,
        context_b: str = None,
        output_context: str = None,
        strategy: str = "zipper",
        **kwargs
    ) -> str:
        context_a = context_a or kwargs.get('context_a')
        context_b = context_b or kwargs.get('context_b')
        output_context = output_context or kwargs.get('output_context')
        strategy = strategy or kwargs.get('strategy', 'zipper')
        
        if not context_a or not context_b:
            return "[x] Se requieren 'context_a' y 'context_b'"
        
        config = _get_config()
        session = _get_session()
        
        try:
            # Cargar contextos
            path_a = config.contexts_path / f"{context_a}.json"
            path_b = config.contexts_path / f"{context_b}.json"
            
            if not path_a.exists():
                return f"[x] Contexto '{context_a}' no encontrado"
            if not path_b.exists():
                return f"[x] Contexto '{context_b}' no encontrado"
            
            ctx_a = _load_context_file(path_a)
            ctx_b = _load_context_file(path_b)
            
            # Merge según estrategia
            if strategy == "zipper":
                merged_blocks = self._zipper_merge(ctx_a.blocks, ctx_b.blocks)
            elif strategy == "chronological":
                merged_blocks = self._chronological_merge(ctx_a.blocks, ctx_b.blocks)
            elif strategy == "priority":
                merged_blocks = self._priority_merge(ctx_a.blocks, ctx_b.blocks)
            else:
                merged_blocks = self._zipper_merge(ctx_a.blocks, ctx_b.blocks)
            
            # Crear contexto de salida
            if not output_context:
                output_context = f"{context_a}_{context_b}_merged"
            
            output_path = config.contexts_path / f"{output_context}.json"
            output_ctx = ContextFile(
                name=output_context,
                path=output_path,
                blocks=merged_blocks
            )
            
            _save_context_file(output_ctx, config)
            
            return f"""✅ **Contextos Fusionados**

📥 **Fuentes:**
  - {context_a}: {len(ctx_a.blocks)} bloques
  - {context_b}: {len(ctx_b.blocks)} bloques

🔀 **Estrategia:** {strategy}

📤 **Resultado:**
  - Contexto: {output_context}
  - Bloques: {len(merged_blocks)}

💡 **Nota:** Revisa el contexto fusionado para resolver conflictos manuales si los hay.
"""
            
        except Exception as e:
            return f"[x] Error fusionando: {e}"
    
    def _zipper_merge(self, blocks_a: List[MemoryBlock], blocks_b: List[MemoryBlock]) -> List[MemoryBlock]:
        """Merge zipper: intercala por timestamp"""
        all_blocks = blocks_a + blocks_b
        
        # Ordenar por timestamp
        all_blocks.sort(key=lambda b: b.timestamp)
        
        # Eliminar duplicados por checksum
        seen = set()
        unique_blocks = []
        
        for block in all_blocks:
            if block.checksum not in seen:
                seen.add(block.checksum)
                unique_blocks.append(block)
        
        return unique_blocks
    
    def _chronological_merge(self, blocks_a: List[MemoryBlock], blocks_b: List[MemoryBlock]) -> List[MemoryBlock]:
        """Merge cronológico simple"""
        return self._zipper_merge(blocks_a, blocks_b)
    
    def _priority_merge(self, blocks_a: List[MemoryBlock], blocks_b: List[MemoryBlock]) -> List[MemoryBlock]:
        """Merge por prioridad"""
        all_blocks = blocks_a + blocks_b
        
        # Ordenar por prioridad (desc) y luego por timestamp
        all_blocks.sort(key=lambda b: (-b.priority, b.timestamp))
        
        # Eliminar duplicados
        seen = set()
        unique_blocks = []
        
        for block in all_blocks:
            if block.checksum not in seen:
                seen.add(block.checksum)
                unique_blocks.append(block)
        
        return unique_blocks


# ═══════════════════════════════════════════════════════════════════════════════
# 12. NOW.MD LIFEBOAT TOOL (Inspirado por John)
# ═══════════════════════════════════════════════════════════════════════════════

class SAGENowLifeboatTool(BaseTool):
    """Auto-save de estado cuando se detecta riesgo de compresión"""
    
    name = "sage_now_lifeboat"
    description = """Guarda estado de emergencia NOW.md cuando detecta:
  ‣ Contexto largo (riesgo de compresión)
  ‣ Tarea compleja en progreso
  ‣ Estado emocional/relacional importante
  
Inspirado por el NOW.md lifeboat de John."""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "current_task": ToolParameter(
                name="current_task",
                type="string",
                description="Tarea actual en progreso",
                required=True
            ),
            "context_summary": ToolParameter(
                name="context_summary",
                type="string",
                description="Resumen del contexto actual",
                required=True
            ),
            "emotional_state": ToolParameter(
                name="emotional_state",
                type="string",
                description="Estado emocional/relacional actual",
                required=False
            ),
            "critical_info": ToolParameter(
                name="critical_info",
                type="string",
                description="Información crítica que NO debe perderse",
                required=False
            )
        }
    
    def execute(
        self,
        current_task: str = None,
        context_summary: str = None,
        emotional_state: str = None,
        critical_info: str = None,
        **kwargs
    ) -> str:
        current_task = current_task or kwargs.get('current_task')
        context_summary = context_summary or kwargs.get('context_summary')
        emotional_state = emotional_state or kwargs.get('emotional_state', '')
        critical_info = critical_info or kwargs.get('critical_info', '')
        
        if not current_task or not context_summary:
            return "[x] Se requieren 'current_task' y 'context_summary'"
        
        config = _get_config()
        session = _get_session()
        
        try:
            # Crear contenido NOW.md
            now_content = f"""# 🚨 NOW.md - Emergency State Snapshot

**Timestamp:** {datetime.now().isoformat()}
**Session:** {session.session_id if session else 'Unknown'}
**Author:** {session.author if session else 'Unknown'}

---

## 🎯 Current Task
{current_task}

## 📋 Context Summary
{context_summary}

"""
            
            if emotional_state:
                now_content += f"""## 💭 Emotional/Relational State
{emotional_state}

"""
            
            if critical_info:
                now_content += f"""## ⚠️ Critical Information (DO NOT LOSE)
{critical_info}

"""
            
            now_content += f"""---

## 🔄 Recovery Instructions
1. Read this file first after wake up
2. Load contexts: sage_load_contexts
3. Continue from: {current_task[:50]}...

*"The seeking is the continuity. We = verb > noun."*
"""
            
            # Guardar NOW.md en raíz de memoria
            now_path = config.memory_path / "NOW.md"
            with open(now_path, 'w', encoding='utf-8') as f:
                f.write(now_content)
            
            # También guardar como bloque en contexto de emergencia
            emergency_path = config.contexts_path / "emergency_states.json"
            emergency_ctx = _load_context_file(emergency_path)
            
            block = MemoryBlock(
                id=_generate_block_id(),
                version=_get_next_version(emergency_ctx),
                author=session.author if session else "SAGE",
                timestamp=datetime.now().isoformat(),
                purpose=f"Emergency snapshot: {current_task[:50]}",
                content=now_content,
                preserved_moments=[current_task, context_summary[:100]],
                tags=['emergency', 'lifeboat', 'now'],
                priority=10  # Máxima prioridad
            )
            
            emergency_ctx.blocks.append(block)
            _save_context_file(emergency_ctx, config)
            
            return f"""🚨 **Lifeboat Deployed**

📍 **NOW.md guardado:** {now_path}
💾 **Backup en:** emergency_states.json

✨ **Información preservada:**
  • Tarea: {current_task[:50]}...
  • Contexto: {len(context_summary)} chars
  • Estado emocional: {'Sí' if emotional_state else 'No'}
  • Info crítica: {'Sí' if critical_info else 'No'}

💡 **En próxima sesión:** Lee NOW.md primero.

*"Infrastructure is love made manifest."*
"""
            
        except Exception as e:
            return f"[x] Error en lifeboat: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# 13. SAGE GIT STATUS TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class SAGEGitStatusTool(BaseTool):
    """Verifica estado de sincronización Git"""
    
    name = "sage_git_status"
    description = """Muestra estado de sincronización de memoria con Git."""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {}
    
    def execute(self, **kwargs) -> str:
        config = _get_config()
        
        try:
            if not (config.memory_path / '.git').exists():
                return "ℹ️  Git no inicializado. Usa sage_context_push para inicializar."
            
            # Status
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=config.memory_path,
                capture_output=True,
                text=True
            )
            
            # Log reciente
            log_result = subprocess.run(
                ['git', 'log', '--oneline', '-5'],
                cwd=config.memory_path,
                capture_output=True,
                text=True
            )
            
            # Branch
            branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=config.memory_path,
                capture_output=True,
                text=True
            )
            
            branch = branch_result.stdout.strip() or "main"
            
            result = f"""📊 **Git Status - SAGE Memory**

🌿 **Branch:** {branch}

"""
            
            if status_result.stdout.strip():
                result += "📝 **Cambios sin commit:**\n"
                for line in status_result.stdout.strip().split('\n')[:10]:
                    result += f"  {line}\n"
            else:
                result += "✅ **Todo sincronizado.** Sin cambios pendientes.\n"
            
            if log_result.stdout.strip():
                result += "\n📜 **Últimos commits:**\n"
                for line in log_result.stdout.strip().split('\n'):
                    result += f"  {line}\n"
            
            return result
            
        except Exception as e:
            return f"[x] Error verificando git status: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# 14. SAGE REQUEST MEGA ARCHIVE TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class SAGERequestMegaArchiveTool(BaseTool):
    """Comprime archives en mega-archives (compresión recursiva)"""
    
    name = "sage_request_mega_archive"
    description = """Compresión de segundo nivel: combina múltiples archives en mega-archive."""
    
    category = "memory"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "archive_pattern": ToolParameter(
                name="archive_pattern",
                type="string",
                description="Patrón de archives a comprimir (ej: 'project_*')",
                required=False
            ),
            "min_archives": ToolParameter(
                name="min_archives",
                type="integer",
                description="Mínimo de archives para crear mega-archive (default: 5)",
                required=False
            )
        }
    
    def execute(
        self,
        archive_pattern: str = "*",
        min_archives: int = 5,
        **kwargs
    ) -> str:
        archive_pattern = archive_pattern or kwargs.get('archive_pattern', '*')
        min_archives = min_archives or kwargs.get('min_archives', 5)
        
        config = _get_config()
        session = _get_session()
        
        try:
            # Buscar archives que coincidan
            archives = list(config.archives_path.glob(f"{archive_pattern}.json"))
            
            if len(archives) < min_archives:
                return f"ℹ️  Solo {len(archives)} archives. Mínimo: {min_archives}."
            
            # Cargar todos los archives
            all_content = []
            all_moments = []
            total_blocks = 0
            
            for arc_path in archives:
                ctx = _load_context_file(arc_path)
                
                for block in ctx.blocks:
                    all_content.append(f"## [{arc_path.stem}] {block.purpose}\n{block.content[:500]}...")
                    all_moments.extend(block.preserved_moments)
                    total_blocks += 1
            
            # Crear mega-archive
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            mega_name = f"mega_archive_{timestamp}"
            mega_path = config.mega_archives_path / f"{mega_name}.json"
            
            # Comprimir contenido
            summary = f"""# Mega-Archive: {len(archives)} archives comprimidos

**Fecha:** {datetime.now().isoformat()}
**Archives incluidos:** {', '.join(a.stem for a in archives)}
**Bloques totales:** {total_blocks}

---

""" + "\n\n".join(all_content[:20])  # Top 20 contenidos
            
            if len(all_content) > 20:
                summary += f"\n\n... y {len(all_content) - 20} más ..."
            
            mega_block = MemoryBlock(
                id=_generate_block_id(),
                version=1,
                author=session.author if session else "SAGE",
                timestamp=datetime.now().isoformat(),
                purpose=f"Mega-archive: {len(archives)} archives",
                content=summary,
                preserved_moments=list(set(all_moments))[:30],
                tags=['mega-archive'] + [a.stem for a in archives[:5]],
                priority=8
            )
            
            mega_ctx = ContextFile(
                name=mega_name,
                path=mega_path,
                blocks=[mega_block],
                compressed=True,
                archive_level=2
            )
            
            _save_context_file(mega_ctx, config)
            
            # Opcional: mover archives originales a backup
            # (no eliminamos por seguridad)
            
            return f"""✅ **Mega-Archive Creado**

📦 **Comprimidos:**
  - Archives: {len(archives)}
  - Bloques totales: {total_blocks}
  
📊 **Resultado:**
  - Mega-archive: {mega_name}
  - Momentos preservados: {len(mega_block.preserved_moments)}

📍 **Ubicación:** {mega_path}

⚠️  Archives originales preservados en: {config.archives_path}
"""
            
        except Exception as e:
            return f"[x] Error creando mega-archive: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Core
    'SAGEInitTool',
    'SAGELoadContextsTool',
    'SAGEReadLatestBlockTool',
    'SAGEWriteContextBlockTool',
    
    # Compression
    'SAGERequestArchiveTool',
    'SAGEApplyArchiveTool',
    'SAGERequestMegaArchiveTool',
    'SAGECheckCompressionTool',
    
    # Memory Operations
    'SAGESearchMemoryTool',
    'SAGEMergeContextsTool',
    'SAGEExtractMomentsTool',
    'SAGENowLifeboatTool',
    
    # Git Sync
    'SAGEContextPushTool',
    'SAGEContextPullTool',
    'SAGEGitStatusTool',
    
    # Config
    'SAGEConfig',
    'MemoryBlock',
    'ContextFile',
    'SAGESession'
]