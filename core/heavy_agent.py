# NVIDIA CODE - Heavy Agent v4.0 - ULTRA COLLABORATIVE
# Sistema con Peer Review, Knowledge Graph, Debate y Paralelización

import sys
import time
import re
import json
import asyncio
import hashlib
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from queue import Queue
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import random

from config import HEAVY_AGENT_CONFIG
from models.registry import ModelRegistry, ModelInfo
from tools import ToolRegistry
from ui.colors import Colors
from ui.markdown import render_markdown

C = Colors()


def safe_print(text: str):
    try:
        print(text)
    except UnicodeEncodeError:
        replacements = {
            '╭': '+', '╮': '+', '╰': '+', '╯': '+',
            '│': '|', '─': '-', '═': '=', '┌': '+', '┐': '+', '└': '+', '┘': '+',
            '🔧': '[T]', '🤖': '[A]', '🧠': '[B]', '💡': '[I]', '⚡': '[>]',
            '✅': '[OK]', '❌': '[X]', '📊': '[G]', '✨': '[*]', '🔥': '[!]',
            '🔍': '[S]', '📋': '[L]', '🎯': '[T]', '✓': '[v]', '┏': '+',
            '┃': '|', '┗': '+', '━': '-', '❓': '[?]', '🔄': '[R]',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        print(text.encode('ascii', 'replace').decode('ascii'))


# ============================================================================
# MESSAGE BUS - COMUNICACIÓN INTER-AGENTE
# ============================================================================

@dataclass
class AgentMessage:
    sender: str
    msg_type: str
    content: str
    target: str
    timestamp: float = field(default_factory=time.time)


class AgentMessageBus:
    def __init__(self):
        self.messages = Queue()
        self.lock = Lock()
        self.history = []
    
    def publish(self, sender_id: str, msg_type: str, content: str, target: str = "all"):
        msg = AgentMessage(sender_id, msg_type, content, target)
        with self.lock:
            self.messages.put(msg)
            self.history.append(msg)
    
    def subscribe(self, agent_id: str) -> List[AgentMessage]:
        msgs = []
        temp_queue = Queue()
        
        with self.lock:
            while not self.messages.empty():
                msg = self.messages.get()
                if (msg.target == "all" or msg.target == agent_id) and msg.sender != agent_id:
                    msgs.append(msg)
                temp_queue.put(msg)
            
            while not temp_queue.empty():
                self.messages.put(temp_queue.get())
        
        return msgs
    
    def get_history_for(self, agent_id: str) -> List[AgentMessage]:
        return [m for m in self.history if m.sender != agent_id and (m.target == "all" or m.target == agent_id)]


# ============================================================================
# KNOWLEDGE GRAPH - MEMORIA ESTRUCTURADA
# ============================================================================

@dataclass
class Fact:
    entity: str
    attribute: str
    value: str
    confidence: float
    source: str
    timestamp: float = field(default_factory=time.time)


class KnowledgeGraph:
    def __init__(self):
        self.facts: Dict[str, List[Fact]] = defaultdict(list)
        self.lock = Lock()
    
    def add_fact(self, entity: str, attribute: str, value: str, confidence: float, source: str):
        fact = Fact(entity, attribute, value, confidence, source)
        with self.lock:
            self.facts[entity].append(fact)
    
    def query(self, entity: str) -> List[Dict]:
        with self.lock:
            facts = self.facts.get(entity, [])
            return [
                {
                    "attribute": f.attribute,
                    "value": f.value,
                    "confidence": f.confidence,
                    "source": f.source
                }
                for f in facts
            ]
    
    def conflict_check(self, entity: str, attribute: str) -> List[Dict]:
        conflicts = []
        values = defaultdict(list)
        
        with self.lock:
            for fact in self.facts.get(entity, []):
                if fact.attribute == attribute:
                    values[fact.value].append({
                        "confidence": fact.confidence,
                        "source": fact.source
                    })
        
        if len(values) > 1:
            conflicts.append({
                "entity": entity,
                "attribute": attribute,
                "conflicting_values": dict(values)
            })
        
        return conflicts
    
    def get_summary(self) -> str:
        with self.lock:
            total = sum(len(facts) for facts in self.facts.values())
            entities = len(self.facts)
            return f"{total} hechos sobre {entities} entidades"


# ============================================================================
# MÉTRICAS Y TELEMETRÍA
# ============================================================================

@dataclass
class AgentMetrics:
    tokens_used: int = 0
    tools_executed: int = 0
    cache_hits: int = 0
    duration: float = 0
    retries: int = 0
    peer_reviews: int = 0
    debates: int = 0
    
    def add_tokens(self, count: int):
        self.tokens_used += count
    
    def add_tool(self, cached: bool = False):
        self.tools_executed += 1
        if cached:
            self.cache_hits += 1
    
    def efficiency(self) -> float:
        if self.tools_executed == 0:
            return 100.0
        return (self.cache_hits / self.tools_executed) * 100


# ============================================================================
# DATACLASSES MEJORADOS
# ============================================================================

@dataclass
class ToolResult:
    tool_name: str
    arguments: Dict
    result: str
    executed_by: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SpecializedQuestion:
    question: str
    agent_type: str
    focus: str
    priority: int = 5
    dependencies: List[str] = field(default_factory=list)


@dataclass
class AgentResponse:
    agent_id: str
    agent_name: str
    agent_type: str
    model_id: str
    question: str
    content: str
    tools_used: List[ToolResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    color: str = ""
    confidence: int = 50
    uncertainties: List[str] = field(default_factory=list)
    peer_reviewed: bool = False
    review_score: int = 0


@dataclass
class Proposal:
    agent: str
    proposal: str
    votes: List[Dict] = field(default_factory=list)
    total_confidence: float = 0


# ============================================================================
# SHARED CONTEXT CON CACHE LOCAL
# ============================================================================

class SharedContext:
    MAX_CACHE_SIZE = 1000  # Límite de entradas en cache
    MAX_FILE_CACHE = 500   # Límite de archivos en cache
    
    def __init__(self):
        self.tool_results: List[ToolResult] = []
        self.files_read: Dict[str, str] = {}
        self.directories_listed: Dict[str, str] = {}
        self.commands_executed: List[Dict] = []
        self.searches_done: List[Dict] = []
        self.cache: Dict[str, str] = {}
        self.cache_access_order: List[str] = []  # Para LRU eviction
    
    def _make_cache_key(self, tool_name: str, arguments: Dict) -> str:
        """Crea una clave de cache más segura usando hashlib"""
        args_str = json.dumps(arguments, sort_keys=True)
        hash_obj = hashlib.md5(f"{tool_name}:{args_str}".encode())
        return f"{tool_name}:{hash_obj.hexdigest()}"
    
    def _evict_cache_if_needed(self):
        """Elimina entradas antiguas del cache si excede el límite (LRU)"""
        if len(self.cache) <= self.MAX_CACHE_SIZE:
            return
        
        # Eliminar las entradas más antiguas (LRU)
        to_remove = len(self.cache) - self.MAX_CACHE_SIZE + 100  # Eliminar 100 extras
        for key in self.cache_access_order[:to_remove]:
            if key in self.cache:
                del self.cache[key]
        self.cache_access_order = self.cache_access_order[to_remove:]
    
    def add_tool_result(self, result: ToolResult):
        self.tool_results.append(result)
        
        cache_key = self._make_cache_key(result.tool_name, result.arguments)
        
        # Evict si es necesario
        if cache_key not in self.cache:
            self._evict_cache_if_needed()
        
        self.cache[cache_key] = result.result
        # Actualizar orden de acceso (mover al final si ya existe)
        if cache_key in self.cache_access_order:
            self.cache_access_order.remove(cache_key)
        self.cache_access_order.append(cache_key)
        
        if result.tool_name == "read_file":
            path = result.arguments.get("path", "")
            if path:
                # Limitar tamaño del cache de archivos
                if len(self.files_read) >= self.MAX_FILE_CACHE:
                    # Eliminar el más antiguo (FIFO)
                    oldest = next(iter(self.files_read))
                    del self.files_read[oldest]
                self.files_read[path] = result.result
        elif result.tool_name == "list_directory":
            path = result.arguments.get("path", ".")
            self.directories_listed[path] = result.result
        elif result.tool_name == "execute_command":
            self.commands_executed.append({
                "command": result.arguments.get("command", ""),
                "result": result.result,
                "by": result.executed_by
            })
        elif result.tool_name in ["search_files", "search_in_files"]:
            self.searches_done.append({
                "query": result.arguments.get("query", result.arguments.get("pattern", "")),
                "result": result.result,
                "by": result.executed_by
            })
    
    def is_already_done(self, tool_name: str, arguments: Dict) -> Tuple[bool, Optional[str]]:
        cache_key = self._make_cache_key(tool_name, arguments)
        if cache_key in self.cache:
            # Actualizar orden de acceso (mover al final)
            if cache_key in self.cache_access_order:
                self.cache_access_order.remove(cache_key)
            self.cache_access_order.append(cache_key)
            return True, self.cache[cache_key]
        
        if tool_name == "read_file":
            path = arguments.get("path", "")
            if path in self.files_read:
                return True, self.files_read[path]
        elif tool_name == "list_directory":
            path = arguments.get("path", ".")
            if path in self.directories_listed:
                return True, self.directories_listed[path]
        
        return False, None
    
    def get_summary(self) -> str:
        parts = []
        if self.files_read:
            files_list = ', '.join(list(self.files_read.keys())[:5])
            parts.append(f"📄 Archivos: {files_list}")
        if self.directories_listed:
            dirs_list = ', '.join(list(self.directories_listed.keys())[:3])
            parts.append(f"📁 Dirs: {dirs_list}")
        if self.commands_executed:
            parts.append(f"⚡ Cmds: {len(self.commands_executed)}")
        return '\n'.join(parts) if parts else "(Sin contexto)"


# ============================================================================
# HEAVY AGENT V4.0 - ULTRA COLLABORATIVE
# ============================================================================

class HeavyAgent:
    
    AGENT_TYPES = {
        "research": {
            "icon": "🔍",
            "name": "Investigador",
            "color": C.AGENT_1,
            "description": "Investiga y recopila",
            "categories": ["search", "web", "http", "files", "docs", "media"]
        },
        "analysis": {
            "icon": "📊",
            "name": "Analista",
            "color": C.AGENT_2,
            "description": "Analiza patrones",
            "categories": ["analysis", "data", "ml", "database"]
        },
        "alternatives": {
            "icon": "💡",
            "name": "Creativo",
            "color": C.AGENT_3,
            "description": "Propone alternativas",
            "categories": ["codegen", "project", "execution", "diff", "memory"]
        },
        "verification": {
            "icon": "✓",
            "name": "Verificador",
            "color": C.BRIGHT_CYAN,
            "description": "Valida soluciones",
            "categories": ["testing", "security", "git", "terminal", "system"]
        }
    }
    
    MAX_TOOL_ITERATIONS = 5
    MAX_RETRIES = 3
    
    def __init__(self, api_client=None):
        if api_client is None:
            from .api_client import NVIDIAAPIClient
            api_client = NVIDIAAPIClient()
        
        self.api_client = api_client
        self.registry = ModelRegistry()
        self.config = HEAVY_AGENT_CONFIG
        
        self.primary_models = self._load_primary_models()
        self.synthesizer = self._load_synthesizer()
        
        self.shared_context = SharedContext()
        self.message_bus = AgentMessageBus()
        self.knowledge_graph = KnowledgeGraph()
        self.metrics = AgentMetrics()
        
        self.start_time = None
        self.questions: List[SpecializedQuestion] = []
        self.responses: List[AgentResponse] = []
    
    def _load_primary_models(self) -> List[ModelInfo]:
        model_ids = self.config.get("primary_models", [])
        models = []
        for model_id in model_ids:
            model = self.registry.get(model_id)
            if model:
                models.append(model)
        
        if not models:
            defaults = [self.registry.get("1"), self.registry.get("2"),
                       self.registry.get("4"), self.registry.get("6")]
            models = [m for m in defaults if m][:4]
        
        while len(models) < 4:
            if models:
                models.append(models[0])
            else:
                models.append(self.registry.get("1"))
        
        return models[:4]
    
    def _load_synthesizer(self) -> ModelInfo:
        synth_id = self.config.get("synthesizer_model", "minimaxai/minimax-m2")
        return self.registry.get(synth_id) or self.registry.get("1")
    
    def process(self, prompt: str, context: str = "", history: List[Dict] = None) -> str:
        self.start_time = time.time()
        self.shared_context = SharedContext()
        self.message_bus = AgentMessageBus()
        self.knowledge_graph = KnowledgeGraph()
        self.metrics = AgentMetrics()
        self.questions = []
        self.responses = []
        
        if not self.primary_models:
            return "[Error] No hay modelos configurados"
        
        self._print_header()
        
        # FASE 1: Generar preguntas
        self._print_phase("1", "GENERACIÓN DE PREGUNTAS", "🎯")
        questions = self._generate_questions(prompt)
        
        if not questions:
            return "[Error] No se pudieron generar preguntas"
        
        self.questions = questions
        
        # FASE 2: Investigación paralela con iteraciones
        self._print_phase("2", "INVESTIGACIÓN COLABORATIVA", "🔄")
        responses = self._execute_agents_iterative(prompt, questions, max_rounds=2)
        
        if not responses:
            return "[Error] No se obtuvieron respuestas"
        
        self.responses = responses
        
        # FASE 3: Peer Review
        self._print_phase("3", "PEER REVIEW", "🔍")
        responses = self._peer_review_all(responses)
        
        # FASE 4: Calibración de confianza
        self._print_phase("4", "CALIBRACIÓN DE CONFIANZA", "📊")
        responses = self._calibrate_confidence(responses)
        
        # FASE 5: Síntesis con debate
        self._print_phase("5", "SÍNTESIS CON DEBATE", "✨")
        final_response = self._synthesize_with_debate(prompt, responses, debate_rounds=1)
        
        self.metrics.duration = time.time() - self.start_time
        self._print_footer()
        
        return final_response
    
    def _print_header(self):
        line1 = f"\n{C.BRIGHT_MAGENTA}╔══════════════════════════════════════════════════════════════════╗{C.RESET}"
        line2 = f"{C.BRIGHT_MAGENTA}║         🔥 HEAVY AGENT v4.0 - ULTRA COLLABORATIVE 🔥             ║{C.RESET}"
        line3 = f"{C.BRIGHT_MAGENTA}╠══════════════════════════════════════════════════════════════════╣{C.RESET}"
        
        safe_print(line1)
        safe_print(line2)
        safe_print(line3)
        
        for i, (agent_type, info) in enumerate(self.AGENT_TYPES.items()):
            model = self.primary_models[i] if i < len(self.primary_models) else self.primary_models[0]
            line = f"{C.BRIGHT_MAGENTA}║{C.RESET}  {info['color']}{info['icon']} {info['name']:12}{C.RESET} │ {model.name:20} │ {info['description'][:20]} {C.BRIGHT_MAGENTA}║{C.RESET}"
            safe_print(line)
        
        line4 = f"{C.BRIGHT_MAGENTA}╠══════════════════════════════════════════════════════════════════╣{C.RESET}"
        line5 = f"{C.BRIGHT_MAGENTA}║  {C.SYNTHESIZER}✨ Sintetizador: {self.synthesizer.name:48}{C.BRIGHT_MAGENTA}║{C.RESET}"
        line6 = f"{C.BRIGHT_MAGENTA}╚══════════════════════════════════════════════════════════════════╝{C.RESET}"
        
        safe_print(line4)
        safe_print(line5)
        safe_print(line6)
        safe_print("")
    
    def _print_phase(self, num: str, title: str, icon: str):
        line1 = f"\n{C.BRIGHT_CYAN}┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓{C.RESET}"
        line2 = f"{C.BRIGHT_CYAN}┃  {icon} FASE {num}: {title:52} ┃{C.RESET}"
        line3 = f"{C.BRIGHT_CYAN}┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛{C.RESET}"
        
        safe_print(line1)
        safe_print(line2)
        safe_print(line3)
        safe_print("")
    
    def _print_footer(self):
        elapsed = self.metrics.duration
        efficiency = self.metrics.efficiency()
        
        line1 = f"\n{C.BRIGHT_GREEN}╔══════════════════════════════════════════════════════════════════╗{C.RESET}"
        line2 = f"{C.BRIGHT_GREEN}║                 ✅ HEAVY AGENT v4.0 COMPLETADO                    ║{C.RESET}"
        line3 = f"{C.BRIGHT_GREEN}╠══════════════════════════════════════════════════════════════════╣{C.RESET}"
        
        stats1 = f"Preguntas: {len(self.questions)} │ Agentes: {len(self.responses)} │ Tools: {self.metrics.tools_executed}"
        line4 = f"{C.BRIGHT_GREEN}║  {stats1:64} ║{C.RESET}"
        
        stats2 = f"Cache: {self.metrics.cache_hits}/{self.metrics.tools_executed} ({efficiency:.0f}%) │ Reviews: {self.metrics.peer_reviews} │ Debates: {self.metrics.debates}"
        line5 = f"{C.BRIGHT_GREEN}║  {stats2:64} ║{C.RESET}"
        
        stats3 = f"Conocimiento: {self.knowledge_graph.get_summary()}"
        line6 = f"{C.BRIGHT_GREEN}║  {stats3:64} ║{C.RESET}"
        
        stats4 = f"Tiempo: {elapsed:.1f}s │ Retries: {self.metrics.retries}"
        line7 = f"{C.BRIGHT_GREEN}║  {stats4:64} ║{C.RESET}"
        
        line8 = f"{C.BRIGHT_GREEN}╚══════════════════════════════════════════════════════════════════╝{C.RESET}"
        
        safe_print(line1)
        safe_print(line2)
        safe_print(line3)
        safe_print(line4)
        safe_print(line5)
        safe_print(line6)
        safe_print(line7)
        safe_print(line8)
        safe_print("")
    
    # ========================================================================
    # GENERACIÓN DE PREGUNTAS
    # ========================================================================
    
    def _generate_questions(self, user_prompt: str) -> List[SpecializedQuestion]:
        safe_print(f"{C.DIM}Generando preguntas especializadas...{C.RESET}\n")
        
        prompt_lines = [
            "Genera EXACTAMENTE 4 preguntas especializadas.",
            "",
            "SOLICITUD:",
            user_prompt,
            "",
            "JSON:",
            "```json",
            "[",
            '  {"type": "research", "question": "...", "focus": "...", "priority": 1-10},',
            '  {"type": "analysis", "question": "...", "focus": "...", "priority": 1-10},',
            '  {"type": "alternatives", "question": "...", "focus": "...", "priority": 1-10},',
            '  {"type": "verification", "question": "...", "focus": "...", "priority": 1-10}',
            "]",
            "```"
        ]
        
        question_prompt = '\n'.join(prompt_lines)
        model = self.primary_models[0]
        
        response = self._execute_with_retry(
            lambda: self._stream_simple(model, question_prompt, C.BRIGHT_YELLOW, "🎯 Question Agent")
        )
        
        try:
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                questions_data = json.loads(json_match.group())
                
                questions = []
                for q in questions_data:
                    questions.append(SpecializedQuestion(
                        question=q.get("question", ""),
                        agent_type=q.get("type", "research"),
                        focus=q.get("focus", ""),
                        priority=q.get("priority", 5)
                    ))
                
                safe_print(f"\n{C.BRIGHT_GREEN}✅ Preguntas generadas:{C.RESET}\n")
                for i, q in enumerate(questions, 1):
                    info = self.AGENT_TYPES.get(q.agent_type, self.AGENT_TYPES["research"])
                    preview = q.question[:60] + "..." if len(q.question) > 60 else q.question
                    safe_print(f"  {info['icon']} {info['name']} (P{q.priority}): {preview}")
                
                return questions
        except Exception as e:
            safe_print(f"{C.RED}Error: {e}{C.RESET}")
        
        return [
            SpecializedQuestion("¿Qué información necesitamos?", "research", "Investigación", 8),
            SpecializedQuestion("¿Cómo analizamos?", "analysis", "Análisis", 7),
            SpecializedQuestion("¿Qué alternativas?", "alternatives", "Alternativas", 6),
            SpecializedQuestion("¿Cómo verificamos?", "verification", "Verificación", 5),
        ]
    
    # ========================================================================
    # EJECUCIÓN ITERATIVA PARALELA
    # ========================================================================
    
    def _execute_agents_iterative(
        self,
        original_prompt: str,
        questions: List[SpecializedQuestion],
        max_rounds: int = 2
    ) -> List[AgentResponse]:
        
        responses = []
        
        for round_num in range(max_rounds):
            safe_print(f"\n{C.BRIGHT_CYAN}🔄 Ronda {round_num + 1}/{max_rounds}{C.RESET}\n")
            
            # Ejecución paralela
            round_responses = self._execute_agents_parallel(original_prompt, questions, responses)
            
            # Extraer conocimiento
            for resp in round_responses:
                self._extract_knowledge(resp)
            
            # Verificar conflictos
            conflicts = self.knowledge_graph.conflict_check(original_prompt[:50], "solution")
            if conflicts:
                safe_print(f"{C.YELLOW}⚠️ Conflictos detectados: {len(conflicts)}{C.RESET}")
            
            if round_num == 0:
                responses = round_responses
            else:
                # Actualizar solo si hay cambios significativos
                for old, new in zip(responses, round_responses):
                    if self._is_significantly_different(old.content, new.content):
                        safe_print(f"{C.GREEN}✓ {old.agent_name} mejoró su respuesta{C.RESET}")
                        old.content = new.content
                        old.tools_used.extend(new.tools_used)
        
        return responses
    
    def _execute_agents_parallel(
        self,
        original_prompt: str,
        questions: List[SpecializedQuestion],
        previous_responses: List[AgentResponse]
    ) -> List[AgentResponse]:
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            for i, question in enumerate(questions):
                model = self.primary_models[i] if i < len(self.primary_models) else self.primary_models[0]
                agent_type = question.agent_type
                info = self.AGENT_TYPES.get(agent_type, self.AGENT_TYPES["research"])
                
                future = executor.submit(
                    self._execute_single_agent,
                    agent_id=f"agent_{agent_type}",
                    model=model,
                    agent_type=agent_type,
                    info=info,
                    original_prompt=original_prompt,
                    question=question,
                    other_responses=previous_responses
                )
                futures.append(future)
            
            responses = []
            for future, q in zip(futures, questions):
                try:
                    response = future.result(timeout=180)
                    responses.append(response)
                except TimeoutError:
                    safe_print(f"{C.RED}Timeout en agente {q.agent_type}{C.RESET}")
                except Exception as e:
                    safe_print(f"{C.RED}Error en agente {q.agent_type}: {e}{C.RESET}")
            
            return responses
    
    def _execute_single_agent(
        self,
        agent_id: str,
        model: ModelInfo,
        agent_type: str,
        info: Dict,
        original_prompt: str,
        question: SpecializedQuestion,
        other_responses: List[AgentResponse]
    ) -> AgentResponse:
        
        color = info['color']
        icon = info['icon']
        name = info['name']
        
        header_fill = max(1, 40 - len(name) - len(model.name))
        header = f"\n{color}╭─ {icon} {name} ({model.name}) {'─' * header_fill}╮{C.RESET}"
        safe_print(header)
        
        question_preview = question.question[:55] + "..." if len(question.question) > 55 else question.question
        safe_print(f"{color}│{C.RESET} {C.DIM}Pregunta: {question_preview}{C.RESET}")
        safe_print(f"{color}│{C.RESET}")
        
        # Construir prompt con contexto
        agent_prompt = self._build_enhanced_agent_prompt(
            original_prompt=original_prompt,
            question=question,
            agent_type=agent_type,
            other_responses=other_responses
        )
        
        # Ejecutar con tools y retry
        content, tools_used = self._execute_with_retry(
            lambda: self._execute_with_tools_streaming(
                model=model,
                prompt=agent_prompt,
                agent_id=agent_id,
                color=color,
                categories=info.get("categories")
            )
        )
        
        safe_print(f"{color}│{C.RESET}")
        tools_info = f" │ 🔧 {len(tools_used)} tools" if tools_used else ""
        fill_len = max(1, 58 - len(tools_info))
        safe_print(f"{color}╰{'─' * fill_len}{tools_info}╯{C.RESET}")
        
        # Publicar en message bus
        self.message_bus.publish(agent_id, "response", content[:200])
        
        return AgentResponse(
            agent_id=agent_id,
            agent_name=f"{name} ({model.name})",
            agent_type=agent_type,
            model_id=model.id,
            question=question.question,
            content=content,
            tools_used=tools_used,
            color=color
        )
    
    def _build_enhanced_agent_prompt(
        self,
        original_prompt: str,
        question: SpecializedQuestion,
        agent_type: str,
        other_responses: List[AgentResponse]
    ) -> str:
        
        info = self.AGENT_TYPES.get(agent_type, self.AGENT_TYPES["research"])
        
        lines = [
            f"Eres {info['name']} ({info['icon']}).",
            f"Rol: {info['description']}",
            "",
            "═" * 60,
            "SOLICITUD:",
            "═" * 60,
            original_prompt,
            "",
            "═" * 60,
            "TU PREGUNTA:",
            "═" * 60,
            question.question,
            f"Enfoque: {question.focus}",
            ""
        ]
        
        # Contexto compartido
        context_summary = self.shared_context.get_summary()
        if context_summary != "(Sin contexto)":
            lines.extend([
                "═" * 60,
                "📂 CONTEXTO (NO repetir):",
                "═" * 60,
                context_summary,
                ""
            ])
        
        # Knowledge graph
        kg_data = self.knowledge_graph.query(original_prompt[:50])
        if kg_data:
            lines.extend([
                "═" * 60,
                "🧠 CONOCIMIENTO ACUMULADO:",
                "═" * 60,
                json.dumps(kg_data[:5], indent=2),
                ""
            ])
        
        # Conflictos
        conflicts = self.knowledge_graph.conflict_check(original_prompt[:50], "solution")
        if conflicts:
            lines.extend([
                "═" * 60,
                "⚠️ CONFLICTOS DETECTADOS:",
                "═" * 60,
                json.dumps(conflicts, indent=2),
                ""
            ])
        
        # Otros agentes
        if other_responses:
            lines.extend([
                "═" * 60,
                "💬 OTROS EXPERTOS:",
                "═" * 60,
                ""
            ])
            
            for resp in other_responses:
                resp_info = self.AGENT_TYPES.get(resp.agent_type, {})
                content_preview = resp.content[:800]
                lines.extend([
                    f"{resp_info.get('icon', '🤖')} {resp_info.get('name', 'Experto')}:",
                    content_preview,
                    "─" * 60,
                    ""
                ])
        
        # Instrucciones específicas
        specific = {
            "research": [
                "TU TAREA:",
                "1. USA herramientas",
                "2. Recopila información",
                "3. Documenta hallazgos",
            ],
            "analysis": [
                "TU TAREA:",
                "1. Analiza datos",
                "2. Identifica patrones",
                "3. Proporciona insights",
            ],
            "alternatives": [
                "TU TAREA:",
                "1. Propón alternativas",
                "2. Piensa creativamente",
                "3. Sugiere mejoras",
            ],
            "verification": [
                "TU TAREA:",
                "1. Valida soluciones",
                "2. Identifica problemas",
                "3. Verifica funcionamiento",
            ]
        }
        
        lines.extend(specific.get(agent_type, specific["research"]))
        
        lines.extend([
            "",
            "REGLAS:",
            f"- Max {self.MAX_TOOL_ITERATIONS} tools",
            "- Código COMPLETO",
            "- NO repetir info",
            "- Max 600 palabras"
        ])
        
        return '\n'.join(lines)
    
    # ========================================================================
    # TOOLS CON STREAMING
    # ========================================================================
    
    def _execute_with_tools_streaming(
        self,
        model: ModelInfo,
        prompt: str,
        agent_id: str,
        color: str,
        categories: Optional[List[str]] = None
    ) -> Tuple[str, List[ToolResult]]:
        
        tools_used = []
        full_content = ""
        
        system = "Eres un experto. Revisa contexto compartido antes de usar tools."
        tools = ToolRegistry.to_openai_format(categories=categories) if model.supports_tools else None
        
        for iteration in range(self.MAX_TOOL_ITERATIONS):
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ]
            
            if full_content:
                messages.append({"role": "assistant", "content": full_content})
                messages.append({"role": "user", "content": "Continúa."})
            
            response = self._stream_with_tools(model, messages, tools, color)
            
            content = response.get("content", "")
            tool_calls = response.get("tool_calls", [])
            
            full_content += content
            
            if not tool_calls:
                break
            
            for tc in tool_calls:
                tool_name = tc.get('function', {}).get('name', '')
                if not tool_name:
                    continue
                
                try:
                    args_str = tc.get('function', {}).get('arguments', '{}')
                    tool_args = json.loads(args_str) if args_str else {}
                except json.JSONDecodeError as e:
                    safe_print(f"{color}│{C.RESET} {C.RED}[Error] JSON inválido en {tool_name}: {str(e)[:50]}{C.RESET}")
                    tool_args = {}
                except Exception as e:
                    safe_print(f"{color}│{C.RESET} {C.RED}[Error] Parseando argumentos de {tool_name}: {str(e)[:50]}{C.RESET}")
                    tool_args = {}
                
                already_done, cached = self.shared_context.is_already_done(tool_name, tool_args)
                
                if already_done:
                    safe_print(f"{color}│{C.RESET} {C.YELLOW}🔄 {tool_name} (cache){C.RESET}")
                    result = cached
                    self.metrics.add_tool(cached=True)
                else:
                    safe_print(f"{color}│{C.RESET} {C.BRIGHT_YELLOW}🔧 {tool_name}{C.RESET}")
                    
                    # Validar que la herramienta existe
                    if not ToolRegistry.has_tool(tool_name):
                        error_msg = f"[Error] Herramienta '{tool_name}' no encontrada"
                        safe_print(f"{color}│{C.RESET} {C.RED}{error_msg}{C.RESET}")
                        result = error_msg
                    else:
                        try:
                            result = ToolRegistry.execute(tool_name, **tool_args)
                            if not isinstance(result, str):
                                result = str(result)
                        except Exception as e:
                            error_msg = f"[Error] Ejecutando {tool_name}: {type(e).__name__}: {str(e)[:150]}"
                            safe_print(f"{color}│{C.RESET} {C.RED}{error_msg}{C.RESET}")
                            result = error_msg
                    
                    preview = result[:120].replace('\n', ' ')
                    if len(result) > 120:
                        preview += "..."
                    safe_print(f"{color}│{C.RESET}   {C.DIM}{preview}{C.RESET}")
                    
                    tool_result = ToolResult(
                        tool_name=tool_name,
                        arguments=tool_args,
                        result=result,
                        executed_by=agent_id
                    )
                    self.shared_context.add_tool_result(tool_result)
                    tools_used.append(tool_result)
                    self.metrics.add_tool(cached=False)
                
                result_preview = result[:800]
                prompt += f"\n\nResultado {tool_name}:\n{result_preview}"
        
        return full_content, tools_used
    
    def _stream_with_tools(
        self,
        model: ModelInfo,
        messages: List[Dict],
        tools: List[Dict],
        color: str
    ) -> Dict:
        import requests
        from config import API_KEY, API_BASE_URL
        
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        payload = {
            "model": model.id,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": model.temperature or 0.7,
            "stream": True
        }
        
        if tools and model.supports_tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        if model.extra_body:
            payload.update(model.extra_body)
        elif model.thinking:
            key = "enable_thinking" if model.thinking_key == "enable_thinking" else "thinking"
            payload["chat_template_kwargs"] = {key: True}
        
        full_content = ""
        tool_calls = []
        buffer = ""
        
        try:
            response = requests.post(
                API_BASE_URL, headers=headers, json=payload,
                stream=True, timeout=120
            )
            
            if response.status_code != 200:
                safe_print(f"{color}│{C.RESET} {C.RED}[HTTP {response.status_code}]{C.RESET}")
                return {"content": "", "tool_calls": []}
            
            for line in response.iter_lines():
                if not line:
                    continue
                
                try:
                    line_str = line.decode('utf-8')
                except:
                    continue
                
                if not line_str.startswith('data: '):
                    continue
                
                data = line_str[6:]
                if data == '[DONE]':
                    break
                
                try:
                    chunk = json.loads(data)
                except:
                    continue
                
                choices = chunk.get('choices', [])
                if not choices:
                    continue
                
                delta = choices[0].get('delta', {})
                
                content = delta.get('content', '')
                if content:
                    content = content.replace('<think>', '').replace('</think>', '')
                    full_content += content
                    buffer += content
                    
                    # Render por oraciones
                    while '. ' in buffer or '.\n' in buffer:
                        if '. ' in buffer:
                            sentence, buffer = buffer.split('. ', 1)
                            sentence += '. '
                        else:
                            sentence, buffer = buffer.split('.\n', 1)
                            sentence += '.\n'
                        
                        try:
                            rendered = render_markdown(sentence.strip())
                            sys.stdout.write(f"{color}│{C.RESET} {rendered} ")
                        except:
                            sys.stdout.write(f"{color}│{C.RESET} {sentence}")
                        sys.stdout.flush()
                
                tc_delta = delta.get('tool_calls', [])
                if tc_delta:
                    for tc in tc_delta:
                        idx = tc.get('index', 0)
                        while len(tool_calls) <= idx:
                            tool_calls.append({
                                'id': '', 'type': 'function',
                                'function': {'name': '', 'arguments': ''}
                            })
                        if tc.get('id'):
                            tool_calls[idx]['id'] = tc['id']
                        func = tc.get('function', {})
                        if func.get('name'):
                            tool_calls[idx]['function']['name'] = func['name']
                        if func.get('arguments'):
                            tool_calls[idx]['function']['arguments'] += func['arguments']
            
            if buffer.strip():
                try:
                    rendered = render_markdown(buffer.strip())
                    sys.stdout.write(f"{color}│{C.RESET} {rendered}")
                except:
                    sys.stdout.write(f"{color}│{C.RESET} {buffer}")
                sys.stdout.flush()
            
            print()
            
            valid_tools = [tc for tc in tool_calls if tc.get('id') and tc.get('function', {}).get('name')]
            return {"content": full_content, "tool_calls": valid_tools}
            
        except Exception as e:
            safe_print(f"{color}│{C.RESET} {C.RED}Error: {str(e)[:50]}{C.RESET}")
            return {"content": "", "tool_calls": []}
    
    def _stream_simple(self, model: ModelInfo, prompt: str, color: str, header: str) -> str:
        import requests
        from config import API_KEY, API_BASE_URL
        
        header_fill = max(1, 55 - len(header))
        safe_print(f"\n{color}╭─ {header} {'─' * header_fill}╮{C.RESET}")
        
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        payload = {
            "model": model.id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2048,
            "temperature": 0.7,
            "stream": True
        }
        
        if model.extra_body:
            payload.update(model.extra_body)
        elif model.thinking:
            key = "enable_thinking" if model.thinking_key == "enable_thinking" else "thinking"
            payload["chat_template_kwargs"] = {key: True}
        
        full_content = ""
        buffer = ""
        
        try:
            response = requests.post(
                API_BASE_URL, headers=headers, json=payload,
                stream=True, timeout=60
            )
            
            if response.status_code != 200:
                safe_print(f"{color}│{C.RESET} {C.RED}[HTTP {response.status_code}]{C.RESET}")
                safe_print(f"{color}╰{'─' * 60}╯{C.RESET}")
                return ""
            
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    line_str = line.decode('utf-8')
                except:
                    continue
                
                if not line_str.startswith('data: '):
                    continue
                
                data = line_str[6:]
                if data == '[DONE]':
                    break
                
                try:
                    chunk = json.loads(data)
                except:
                    continue
                
                content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                if content:
                    content = content.replace('<think>', '').replace('</think>', '')
                    full_content += content
                    buffer += content
                    
                    while '. ' in buffer:
                        sentence, buffer = buffer.split('. ', 1)
                        sentence += '. '
                        sys.stdout.write(f"{color}│{C.RESET} {sentence}")
                        sys.stdout.flush()
            
            if buffer.strip():
                sys.stdout.write(f"{color}│{C.RESET} {buffer}")
                sys.stdout.flush()
            
            print()
            safe_print(f"{color}╰{'─' * 60}╯{C.RESET}")
            
            return full_content
            
        except Exception as e:
            safe_print(f"{color}│{C.RESET} {C.RED}Error: {e}{C.RESET}")
            safe_print(f"{color}╰{'─' * 60}╯{C.RESET}")
            return ""
    
    # ========================================================================
    # PEER REVIEW
    # ========================================================================
    
    def _peer_review_all(self, responses: List[AgentResponse]) -> List[AgentResponse]:
        for i, response in enumerate(responses):
            if len(responses) < 2:
                break
            
            # Elegir reviewer aleatorio
            others = [r for r in responses if r.agent_id != response.agent_id]
            if not others:
                continue
            
            reviewer = random.choice(others)
            
            safe_print(f"{C.YELLOW}🔍 {reviewer.agent_name} revisa a {response.agent_name}{C.RESET}")
            
            review_prompt = f"""
            Revisa esta respuesta:
            
            PREGUNTA: {response.question}
            RESPUESTA: {response.content[:800]}
            
            Tu análisis: {reviewer.content[:400]}
            
            JSON: {{"score": 0-10, "errors": [...], "missing": [...], "suggestions": [...]}}
            """
            
            review = self._execute_with_retry(
                lambda: self._call_simple(self.registry.get(reviewer.model_id), review_prompt)
            )
            
            try:
                review_data = json.loads(re.search(r'\{.*\}', review, re.DOTALL).group())
                score = review_data.get("score", 7)
                response.review_score = score
                response.peer_reviewed = True
                self.metrics.peer_reviews += 1
                
                safe_print(f"  Score: {score}/10")
                
                if score < 7:
                    safe_print(f"{C.YELLOW}  Mejorando respuesta...{C.RESET}")
                    
                    revision_prompt = f"""
                    Tu respuesta:
                    {response.content}
                    
                    Feedback:
                    - Errores: {review_data.get("errors", [])}
                    - Faltante: {review_data.get("missing", [])}
                    - Sugerencias: {review_data.get("suggestions", [])}
                    
                    Mejora tu respuesta.
                    """
                    
                    revised = self._execute_with_retry(
                        lambda: self._call_simple(
                            self.registry.get(response.model_id),
                            revision_prompt
                        )
                    )
                    
                    response.content = revised
                    safe_print(f"{C.GREEN}  ✓ Respuesta mejorada{C.RESET}")
            except:
                pass
        
        return responses
    
    # ========================================================================
    # CALIBRACIÓN DE CONFIANZA
    # ========================================================================
    
    def _calibrate_confidence(self, responses: List[AgentResponse]) -> List[AgentResponse]:
        for response in responses:
            calibration_prompt = f"""
            Tu respuesta:
            {response.content[:600]}
            
            Otros:
            {self._summarize_others(responses, response.agent_id)}
            
            JSON: {{"confidence": 0-100, "uncertainties": [...]}}
            """
            
            calibration = self._execute_with_retry(
                lambda: self._call_simple(
                    self.registry.get(response.model_id),
                    calibration_prompt
                )
            )
            
            try:
                cal_data = json.loads(re.search(r'\{.*\}', calibration, re.DOTALL).group())
                response.confidence = cal_data.get("confidence", 50)
                response.uncertainties = cal_data.get("uncertainties", [])
                
                safe_print(f"{response.agent_name}: {response.confidence}% confianza")
            except:
                response.confidence = 50
        
        return responses
    
    # ========================================================================
    # SÍNTESIS CON DEBATE
    # ========================================================================
    
    def _synthesize_with_debate(
        self,
        original_prompt: str,
        responses: List[AgentResponse],
        debate_rounds: int = 1
    ) -> str:
        
        # Generar propuestas
        safe_print(f"{C.DIM}Generando propuestas...{C.RESET}\n")
        proposals = []
        
        for response in responses:
            proposal_prompt = f"""
            Tu análisis:
            {response.content[:600]}
            
            Otros:
            {self._summarize_others(responses, response.agent_id)}
            
            Propón UNA solución final (max 200 palabras).
            """
            
            proposal_text = self._execute_with_retry(
                lambda: self._call_simple(
                    self.registry.get(response.model_id),
                    proposal_prompt
                )
            )
            
            proposals.append(Proposal(
                agent=response.agent_name,
                proposal=proposal_text
            ))
        
        # Votación
        safe_print(f"{C.DIM}Votando propuestas...{C.RESET}\n")
        for _ in range(debate_rounds):
            self.metrics.debates += 1
            
            for prop in proposals:
                for response in responses:
                    if response.agent_name == prop.agent:
                        continue
                    
                    vote_prompt = f"""
                    Propuesta de {prop.agent}:
                    {prop.proposal}
                    
                    JSON: {{"vote": "for/against", "confidence": 0-100, "reasoning": "..."}}
                    """
                    
                    vote_response = self._execute_with_retry(
                        lambda: self._call_simple(
                            self.registry.get(response.model_id),
                            vote_prompt
                        )
                    )
                    
                    try:
                        vote_data = json.loads(re.search(r'\{.*\}', vote_response, re.DOTALL).group())
                        prop.votes.append({
                            "agent": response.agent_name,
                            "vote": vote_data.get("vote", "for"),
                            "confidence": vote_data.get("confidence", 50),
                            "reasoning": vote_data.get("reasoning", "")
                        })
                    except:
                        pass
        
        # Calcular mejor propuesta
        for prop in proposals:
            prop.total_confidence = sum(
                v["confidence"] for v in prop.votes if v["vote"] == "for"
            )
        
        best_proposal = max(proposals, key=lambda p: p.total_confidence) if proposals else None
        
        if not best_proposal:
            return "[Error] No hay propuestas"
        
        safe_print(f"\n{C.BRIGHT_GREEN}🏆 Propuesta ganadora: {best_proposal.agent}{C.RESET}")
        safe_print(f"   Confianza total: {best_proposal.total_confidence:.0f}\n")
        
        # Síntesis final
        final_prompt = f"""
        Propuesta ganadora de {best_proposal.agent}:
        {best_proposal.proposal}
        
        Votos a favor ({len([v for v in best_proposal.votes if v['vote'] == 'for'])}/{len(best_proposal.votes)}):
        {json.dumps([v['reasoning'] for v in best_proposal.votes if v['vote'] == 'for'][:3], indent=2)}
        
        Genera respuesta FINAL COMPLETA para:
        {original_prompt}
        
        Incluye código completo si es necesario.
        """
        
        return self._stream_simple(
            self.synthesizer,
            final_prompt,
            C.SYNTHESIZER,
            f"✨ Síntesis ({self.synthesizer.name})"
        )
    
    # ========================================================================
    # KNOWLEDGE GRAPH HELPERS
    # ========================================================================
    
    def _extract_knowledge(self, response: AgentResponse):
        extract_prompt = f"""
        Extrae hechos de:
        {response.content[:500]}
        
        JSON: [{{"entity": "...", "attribute": "...", "value": "...", "confidence": 0-100}}, ...]
        Max 5 hechos.
        """
        
        facts_json = self._call_simple(self.primary_models[0], extract_prompt)
        
        try:
            facts = json.loads(re.search(r'\[.*\]', facts_json, re.DOTALL).group())
            for fact in facts[:5]:
                self.knowledge_graph.add_fact(
                    fact.get("entity", "unknown"),
                    fact.get("attribute", "info"),
                    fact.get("value", ""),
                    fact.get("confidence", 50) / 100,
                    response.agent_id
                )
        except:
            pass
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def _execute_with_retry(self, func, max_retries: int = None):
        if max_retries is None:
            max_retries = self.MAX_RETRIES
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                self.metrics.retries += 1
                wait = 2 ** attempt
                safe_print(f"{C.YELLOW}Retry {attempt+1}/{max_retries} en {wait}s...{C.RESET}")
                time.sleep(wait)
    
    def _call_simple(self, model: ModelInfo, prompt: str) -> str:
        import requests
        from config import API_KEY, API_BASE_URL
        
        payload = {
            "model": model.id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.7
        }
        
        response = requests.post(
            API_BASE_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=60
        )
        
        return response.json()['choices'][0]['message']['content']
    
    def _summarize_others(self, responses: List[AgentResponse], exclude_id: str) -> str:
        summaries = []
        for r in responses:
            if r.agent_id != exclude_id:
                summary = r.content[:200] + "..."
                summaries.append(f"{r.agent_name}: {summary}")
        return "\n".join(summaries)
    
    def _is_significantly_different(self, old: str, new: str) -> bool:
        old_words = set(old.lower().split())
        new_words = set(new.lower().split())
        
        if not old_words or not new_words:
            return True
        
        jaccard = len(old_words & new_words) / len(old_words | new_words)
        return jaccard < 0.7
    
    def reload_config(self):
        from config import HEAVY_AGENT_CONFIG
        self.config = HEAVY_AGENT_CONFIG
        self.primary_models = self._load_primary_models()
        self.synthesizer = self._load_synthesizer()
        safe_print(f"{C.GREEN}Config recargada{C.RESET}")