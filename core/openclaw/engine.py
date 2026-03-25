import threading
import time
import json
import re
import traceback
from typing import (
    Dict, List, Optional, Any, Callable
)
from .logger import logger
from .types import AutonomousTask

# ============================================================================
# AUTONOMOUS MODE ENGINE
# ============================================================================

class AutonomousEngine:
    """Motor para ejecutar tareas de forma autónoma"""

    def __init__(self, agent: Any):
        self.agent = agent
        self._running = False
        self._current_task: Optional[AutonomousTask] = None
        self._cancel_event = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._running

    async def execute_task(
        self,
        objective: str,
        channel_id: str = "autonomous",
        on_step_complete: Callable = None
    ) -> AutonomousTask:
        """Ejecuta una tarea de forma autónoma"""
        task = AutonomousTask(
            objective=objective,
            max_steps=20
        )
        self._current_task = task
        self._running = True
        self._cancel_event.clear()

        task.status = "running"
        logger.info(f"Autonomous task started: {objective}")

        try:
            # Paso 1: Planificar
            plan = await self._plan_task(objective, channel_id)
            task.steps = plan

            if on_step_complete:
                on_step_complete("plan", plan)

            # Paso 2: Ejecutar cada paso
            for i, step in enumerate(task.steps):
                if self._cancel_event.is_set():
                    task.status = "cancelled"
                    break

                task.current_step = i

                result = await self._execute_step(step, task, channel_id)
                task.results.append({
                    'step': i,
                    'description': step,
                    'result': result,
                    'timestamp': time.time()
                })

                if on_step_complete:
                    on_step_complete("step", {
                        'step_num': i + 1,
                        'total': len(task.steps),
                        'description': step,
                        'result': result
                    })

                should_continue = await self._evaluate_progress(task, channel_id)
                if not should_continue:
                    break

            if task.status == "running":
                task.status = "completed"

        except Exception as e:
            task.status = "failed"
            task.results.append({
                'step': task.current_step,
                'error': str(e),
                'traceback': traceback.format_exc()
            })
            logger.error(f"Autonomous task failed: {e}", exc_info=True)

        finally:
            self._running = False
            self._current_task = None

            self.agent.memory.add_task_result({
                'objective': task.objective,
                'status': task.status,
                'steps_completed': task.current_step,
                'total_steps': len(task.steps),
                'duration': time.time() - task.created_at
            })

        return task

    async def _plan_task(self, objective: str, channel_id: str) -> List[str]:
        """Genera plan de pasos para la tarea"""
        planning_prompt = f"""Eres un planificador de tareas. Dado el siguiente objetivo,
genera una lista de pasos concretos y ejecutables para lograrlo.

OBJETIVO: {objective}

Responde SOLO con un JSON array de strings, cada uno siendo un paso.
Ejemplo: ["Paso 1: hacer X", "Paso 2: hacer Y"]
Máximo 10 pasos. Sé específico y práctico.
NO uses herramientas para planificar, solo genera el plan."""

        try:
            # Call to private method of agent - might need to be public or handled differently
            response = await self.agent._call_model(
                planning_prompt,
                [],
                channel_id,
                allow_tools=False  # No usar herramientas para planificar
            )

            # Extraer JSON del response
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                try:
                    steps = json.loads(json_match.group())
                    if isinstance(steps, list) and all(isinstance(s, str) for s in steps):
                        return steps[:10]
                except json.JSONDecodeError:
                    pass

            # Fallback: dividir por líneas
            lines = [
                line.strip()
                for line in response.split('\n')
                if line.strip() and not (line.strip().startswith('{') or line.strip().startswith('`'))
            ]
            # Simple cleanup for common LLM artifacts
            lines = [re.sub(r'^\d+[\.\-\)]\s*', '', l) for l in lines]
            return lines[:10] if lines else [objective]

        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return [objective]

    async def _execute_step(
        self,
        step: str,
        task: AutonomousTask,
        channel_id: str
    ) -> str:
        """Ejecuta un paso individual"""
        context_parts = [f"OBJETIVO GLOBAL: {task.objective}"]

        for prev in task.results[-3:]:
            context_parts.append(
                f"Paso anterior: {prev.get('description', 'N/A')}\n"
                f"Resultado: {str(prev.get('result', 'N/A'))[:200]}"
            )

        execution_prompt = f"""{chr(10).join(context_parts)}

PASO ACTUAL: {step}

Ejecuta este paso. Usa las herramientas disponibles si es necesario.
Sé conciso en tu respuesta."""

        return await self.agent._call_model(execution_prompt, [], channel_id)

    async def _evaluate_progress(
        self,
        task: AutonomousTask,
        channel_id: str
    ) -> bool:
        """Evalúa si la tarea debe continuar"""
        if task.current_step >= task.max_steps - 1:
            return False

        if task.current_step >= len(task.steps) - 1:
            return False

        if (task.current_step + 1) % 3 == 0 and task.results:
            last_results = [
                str(r.get('result', ''))[:100]
                for r in task.results[-3:]
            ]

            eval_prompt = f"""Evalúa si el progreso hacia el objetivo es adecuado.
Objetivo: {task.objective}
Últimos resultados: {json.dumps(last_results)}
Responde SOLO 'continuar' o 'detener'.
NO uses herramientas."""

            try:
                response = await self.agent._call_model(
                    eval_prompt, [], channel_id, allow_tools=False
                )
                return 'detener' not in response.lower()
            except Exception:
                return True

        return True

    def cancel(self):
        """Cancela la tarea actual"""
        self._cancel_event.set()
        logger.info("Autonomous task cancellation requested")
