import threading
import time
import re
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from .logger import logger
from .resilience import CircuitBreaker

# ============================================================================
# SELECTOR DE MODELOS MEJORADO
# ============================================================================

class ModelSelector:
    """Selector inteligente con circuit breaker y aprendizaje"""

    TASK_MODEL_MAP = {
        'code': [
            'deepseek-ai/deepseek-v3.2',
            'z-ai/glm5',
            'qwen/qwen3.5-122b-a10b'
        ],
        'reasoning': [
            'z-ai/glm5',
            'moonshotai/kimi-k2.5',
            'qwen/qwen3.5-397b-a17b'
        ],
        'creative': [
            'minimaxai/minimax-m2',
            'z-ai/glm4.7'
        ],
        'search': [
            'deepseek-ai/deepseek-v3.2',
            'z-ai/glm4.7'
        ],
        'analysis': [
            'qwen/qwen3.5-397b-a17b',
            'z-ai/glm5'
        ],
        'general': [
            'z-ai/glm4.7',
            'minimaxai/minimax-m2'
        ],
        'fast': [
            'minimaxai/minimax-m2',
            'nvidia/nemotron-3-nano-30b-a3b'
        ],
        'math': [
            'qwen/qwen3.5-397b-a17b',
            'deepseek-ai/deepseek-v3.2'
        ],
    }

    TASK_KEYWORDS = {
        'code': [
            'código', 'code', 'función', 'function', 'script',
            'programar', 'debug', 'error', 'fix', 'implementar',
            'clase', 'class', 'python', 'javascript', 'html', 'css',
            'api', 'endpoint', 'database', 'sql', 'git', 'deploy',
            'refactor', 'test', 'unittest', 'bug'
        ],
        'reasoning': [
            'por qué', 'explicar', 'analizar', 'razonar', 'pensar',
            'comparar', 'decidir', 'evaluar', 'considerar', 'pros y contras',
            'ventajas', 'desventajas', 'diferencia entre', 'mejor opción'
        ],
        'creative': [
            'historia', 'crear', 'inventar', 'imaginar', 'escribir',
            'poema', 'story', 'creative', 'narrativa', 'cuento',
            'canción', 'guión', 'personaje', 'mundo'
        ],
        'search': [
            'buscar', 'encontrar', 'search', 'find', 'web',
            'internet', 'google', 'información sobre', 'qué es',
            'quién es', 'dónde', 'cuándo'
        ],
        'analysis': [
            'analizar', 'analysis', 'datos', 'data', 'estadísticas',
            'informe', 'report', 'revisar', 'métrica', 'tendencia',
            'gráfico', 'csv', 'excel'
        ],
        'math': [
            'calcular', 'ecuación', 'integral', 'derivada', 'matemática',
            'algebra', 'geometría', 'probabilidad', 'estadística',
            'fórmula', 'resolver'
        ],
        'fast': [
            'rápido', 'quick', 'simple', 'corto', 'brief',
            'resumen corto', 'en una línea', 'sí o no'
        ],
    }

    def __init__(self, registry=None):
        self.registry = registry
        self.current_model = None
        self._lock = threading.Lock()

        self.model_stats: Dict[str, Dict] = defaultdict(lambda: {
            'successes': 0,
            'failures': 0,
            'total_time': 0.0,
            'avg_response_time': 0.0,
            'last_error': None,
            'last_used': None
        })

        self.circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(failure_threshold=3, recovery_timeout=120.0)
        )

    def detect_task_type(self, message: str) -> str:
        """Detecta el tipo de tarea con scoring mejorado"""
        message_lower = message.lower()

        scores: Dict[str, float] = {}
        for task_type, keywords in self.TASK_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                if kw in message_lower:
                    if re.search(rf'\b{re.escape(kw)}\b', message_lower):
                        score += 2.0
                    else:
                        score += 1.0
            if score > 0:
                scores[task_type] = score

        if scores:
            normalized = {
                k: v / len(self.TASK_KEYWORDS[k])
                for k, v in scores.items()
            }
            return max(normalized, key=normalized.get)

        return 'general'

    def select_best_model(
        self,
        task_type: str,
        prefer_thinking: bool = False,
        exclude_models: List[str] = None
    ) -> Optional[Any]:
        """Selecciona el mejor modelo considerando circuit breakers"""
        exclude = set(exclude_models or [])
        recommended = self.TASK_MODEL_MAP.get(
            task_type, self.TASK_MODEL_MAP['general']
        )

        candidates = []
        for model_id in recommended:
            if model_id in exclude:
                continue

            if not self.registry:
                continue

            model = self.registry.get(model_id)
            if not model:
                continue

            cb = self.circuit_breakers[model_id]
            if not cb.can_execute():
                logger.debug(f"Model {model_id} circuit breaker is OPEN, skipping")
                continue

            if prefer_thinking and hasattr(model, 'thinking') and not model.thinking:
                continue

            stats = self.model_stats[model_id]
            total = stats['successes'] + stats['failures']
            success_rate = stats['successes'] / total if total > 0 else 0.5

            candidates.append((model, success_rate))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]

        # Fallback to any available if no candidates
        # Note: AVAILABLE_MODELS would need to be imported or passed if it's dynamic
        # For now, we assume the registry is the source of truth
        return None

    def get_fallback_model(
        self,
        failed_model_id: str,
        task_type: str
    ) -> Optional[Any]:
        """Obtiene modelo de fallback cuando uno falla"""
        return self.select_best_model(
            task_type,
            exclude_models=[failed_model_id]
        )

    def switch_model(self, model_key: str) -> Tuple[bool, str]:
        """Cambia al modelo especificado"""
        if not self.registry:
            return False, "Registry de modelos no disponible"

        model = self.registry.get(model_key)
        if model:
            with self._lock:
                self.current_model = model
            model_name = model.name if hasattr(model, 'name') else model_key
            return True, f"Modelo cambiado a: {model_name}"
        return False, f"Modelo no encontrado: {model_key}"

    def record_result(
        self,
        model_id: str,
        success: bool,
        elapsed_time: float,
        error: str = None
    ):
        """Registra resultado con circuit breaker"""
        with self._lock:
            stats = self.model_stats[model_id]
            if success:
                stats['successes'] += 1
                self.circuit_breakers[model_id].record_success()
            else:
                stats['failures'] += 1
                stats['last_error'] = error
                self.circuit_breakers[model_id].record_failure()

            stats['total_time'] += elapsed_time
            stats['last_used'] = time.time()
            total = stats['successes'] + stats['failures']
            if total > 0:
                stats['avg_response_time'] = stats['total_time'] / total

    def get_model_health(self) -> Dict[str, Dict]:
        """Obtiene estado de salud de todos los modelos"""
        health = {}
        for model_id, stats in self.model_stats.items():
            cb = self.circuit_breakers[model_id]
            total = stats['successes'] + stats['failures']
            health[model_id] = {
                'circuit_state': cb.state.value,
                'success_rate': (
                    stats['successes'] / total if total > 0 else None
                ),
                'avg_response_time': stats['avg_response_time'],
                'total_calls': total,
                'last_error': stats['last_error']
            }
        return health
