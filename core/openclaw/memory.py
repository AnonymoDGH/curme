import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import deque
from .logger import logger

class OpenClawMemory:
    """Sistema de memoria persistente thread-safe con resumen automático"""

    MAX_MESSAGES_PER_CHANNEL = 100
    MAX_TOTAL_MESSAGES = 1000
    SUMMARY_THRESHOLD = 30

    def __init__(self, storage_path: str = "openclaw_memory.json"):
        self.storage_path = Path(storage_path)
        self._lock = threading.RLock()

        self.conversations: Dict[str, List[Dict]] = {}
        self.user_contexts: Dict[str, Dict] = {}
        self.global_memory: Dict[str, Any] = {}
        self.task_history: deque = deque(maxlen=200)
        self.summaries: Dict[str, str] = {}

        self._dirty = False
        self._save_timer: Optional[threading.Timer] = None

        self.load()

    def load(self):
        """Carga memoria desde archivo"""
        with self._lock:
            if self.storage_path.exists():
                try:
                    data = json.loads(
                        self.storage_path.read_text(encoding='utf-8')
                    )
                    self.conversations = data.get('conversations', {})
                    self.user_contexts = data.get('user_contexts', {})
                    self.global_memory = data.get('global_memory', {})
                    self.summaries = data.get('summaries', {})

                    history = data.get('task_history', [])
                    self.task_history = deque(history, maxlen=200)

                    logger.info(
                        f"Memory loaded: {sum(len(v) for v in self.conversations.values())} "
                        f"messages across {len(self.conversations)} channels"
                    )
                except json.JSONDecodeError as e:
                    logger.error(f"Corrupted memory file: {e}")
                    self._create_backup()
                except Exception as e:
                    logger.error(f"Error loading memory: {e}", exc_info=True)

    def _create_backup(self):
        """Crea backup del archivo de memoria corrupto"""
        if self.storage_path.exists():
            backup_path = self.storage_path.with_suffix(
                f'.backup_{int(time.time())}.json'
            )
            try:
                self.storage_path.rename(backup_path)
                logger.info(f"Corrupted memory backed up to: {backup_path}")
            except OSError:
                pass

    def save(self, force: bool = False):
        """Guarda memoria a archivo con debouncing"""
        with self._lock:
            self._dirty = True

        if force:
            self._do_save()
        else:
            if self._save_timer:
                self._save_timer.cancel()
            self._save_timer = threading.Timer(2.0, self._do_save)
            self._save_timer.daemon = True
            self._save_timer.start()

    def _do_save(self):
        """Realiza el guardado real"""
        with self._lock:
            if not self._dirty:
                return

            try:
                data = {
                    'conversations': self.conversations,
                    'user_contexts': self.user_contexts,
                    'global_memory': self.global_memory,
                    'summaries': self.summaries,
                    'task_history': list(self.task_history),
                    'saved_at': datetime.now().isoformat()
                }

                temp_path = self.storage_path.with_suffix('.tmp')
                temp_path.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False, default=str),
                    encoding='utf-8'
                )
                temp_path.replace(self.storage_path)

                self._dirty = False
                logger.debug("Memory saved successfully")

            except Exception as e:
                logger.error(f"Error saving memory: {e}", exc_info=True)

    def add_message(
        self,
        channel_id: str,
        role: str,
        content: str,
        model: str = "",
        metadata: Dict = None
    ):
        """Añade mensaje a la conversación (thread-safe)"""
        with self._lock:
            if channel_id not in self.conversations:
                self.conversations[channel_id] = []

            msg = {
                'role': role,
                'content': content,
                'model': model,
                'timestamp': datetime.now().isoformat()
            }
            if metadata:
                msg['metadata'] = metadata

            self.conversations[channel_id].append(msg)

            if len(self.conversations[channel_id]) > self.MAX_MESSAGES_PER_CHANNEL:
                self.conversations[channel_id] = (
                    self.conversations[channel_id][-self.MAX_MESSAGES_PER_CHANNEL:]
                )

        self.save()

    def get_context(
        self,
        channel_id: str,
        max_messages: int = 10,
        include_summary: bool = True
    ) -> List[Dict]:
        """Obtiene contexto de conversación con resumen opcional"""
        with self._lock:
            messages = []

            if include_summary and channel_id in self.summaries:
                messages.append({
                    'role': 'system',
                    'content': f"[Resumen de conversación anterior]: {self.summaries[channel_id]}"
                })

            if channel_id in self.conversations:
                recent = self.conversations[channel_id][-max_messages:]
                messages.extend([
                    {'role': m['role'], 'content': m['content']}
                    for m in recent
                ])

            return messages

    def set_summary(self, channel_id: str, summary: str):
        """Establece resumen de conversación"""
        with self._lock:
            self.summaries[channel_id] = summary
        self.save()

    def clear_channel(self, channel_id: str):
        """Limpia la conversación de un canal"""
        with self._lock:
            if channel_id in self.conversations:
                if len(self.conversations[channel_id]) > 5:
                    self.summaries[channel_id] = self._auto_summarize(
                        self.conversations[channel_id]
                    )
                del self.conversations[channel_id]
        self.save()

    def _auto_summarize(self, messages: List[Dict]) -> str:
        """Genera resumen automático simple de mensajes"""
        topics = set()
        for msg in messages:
            content = msg.get('content', '')
            words = content.split()[:5]
            if words:
                topics.add(' '.join(words))

        if topics:
            return f"Temas discutidos: {'; '.join(list(topics)[:5])}"
        return "Conversación previa sin temas claros"

    def set_user_preference(self, user_id: str, key: str, value: Any):
        with self._lock:
            if user_id not in self.user_contexts:
                self.user_contexts[user_id] = {}
            self.user_contexts[user_id][key] = value
        self.save()

    def get_user_preference(self, user_id: str, key: str, default=None) -> Any:
        with self._lock:
            return self.user_contexts.get(user_id, {}).get(key, default)

    def add_task_result(self, task: Dict):
        """Registra resultado de tarea"""
        with self._lock:
            self.task_history.append({
                **task,
                'recorded_at': datetime.now().isoformat()
            })
        self.save()

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de memoria"""
        with self._lock:
            total_messages = sum(
                len(msgs) for msgs in self.conversations.values()
            )
            return {
                'total_channels': len(self.conversations),
                'total_messages': total_messages,
                'total_users': len(self.user_contexts),
                'total_tasks': len(self.task_history),
                'summaries': len(self.summaries),
                'storage_size_kb': (
                    self.storage_path.stat().st_size / 1024
                    if self.storage_path.exists() else 0
                )
            }

    def shutdown(self):
        """Guarda todo y limpia timers"""
        if self._save_timer:
            self._save_timer.cancel()
        self._do_save()
