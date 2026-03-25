import time
import re
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
from .logger import logger
from .types import Skill, SkillPlugin

class SkillsManager:
    """Gestor de skills con soporte para plugins"""

    def __init__(self, tool_registry=None):
        self.tool_registry = tool_registry
        self.skills: Dict[str, Skill] = {}
        self._plugins: List[SkillPlugin] = []
        self._register_default_skills()

    def _register_default_skills(self):
        """Registra skills por defecto"""

        self.register_skill(Skill(
            name="switch_model",
            description="Cambia el modelo de IA activo",
            trigger_patterns=[
                r'cambiar?\s*(?:a\s*)?modelo\s*(\d+)',
                r'usa(?:r)?\s*(?:el\s*)?modelo\s*(\d+)',
                r'switch\s*(?:to\s*)?model\s*(\d+)',
                r'modelo\s*(\d+)',
            ],
            action=self._action_switch_model,
            category="system"
        ))

        self.register_skill(Skill(
            name="list_models",
            description="Lista todos los modelos disponibles",
            trigger_patterns=[
                r'lista\s*(?:de\s*)?modelos',
                r'modelos\s*disponibles',
                r'qu[eé]\s*modelos',
                r'ver\s*modelos',
                r'list\s*models',
                r'^modelos$',
            ],
            action=self._action_list_models,
            category="system"
        ))

        self.register_skill(Skill(
            name="autonomous_mode",
            description="Activa el modo autónomo con un objetivo",
            trigger_patterns=[
                r'modo\s*aut[oó]nomo',
                r'acti[vw]ar?\s*aut[oó]nomo',
                r'empieza?\s*a\s*trabajar',
                r'start\s*autonomous',
                r'auto\s*mode',
            ],
            action=self._action_autonomous,
            requires_confirmation=True,
            category="autonomy"
        ))

        self.register_skill(Skill(
            name="system_status",
            description="Muestra el estado del sistema",
            trigger_patterns=[
                r'estado\s*(?:del\s*)?sistema',
                r'^status$',
                r'^c[oó]mo\s*est[aá]s',
                r'qu[eé]\s*puedes\s*hacer',
                r'^help$',
                r'^ayuda$',
            ],
            action=self._action_status,
            category="system"
        ))

        self.register_skill(Skill(
            name="list_tools",
            description="Lista todas las herramientas disponibles",
            trigger_patterns=[
                r'lista\s*(?:de\s*)?herramientas',
                r'herramientas\s*disponibles',
                r'ver\s*herramientas',
                r'qu[eé]\s*herramientas',
                r'list\s*tools',
                r'^tools$',
                r'^herramientas$',
            ],
            action=self._action_list_tools,
            category="system"
        ))

        self.register_skill(Skill(
            name="clear_context",
            description="Limpia el contexto de conversación",
            trigger_patterns=[
                r'limpiar?\s*(?:el\s*)?contexto',
                r'nueva\s*conversaci[oó]n',
                r'clear\s*(?:context|chat)',
                r'reset\s*chat',
                r'^nuevo$',
                r'^clear$',
            ],
            action=self._action_clear_context,
            category="system"
        ))

        self.register_skill(Skill(
            name="model_health",
            description="Muestra estado de salud de los modelos",
            trigger_patterns=[
                r'salud\s*(?:de\s*)?(?:los\s*)?modelos',
                r'model\s*health',
                r'health\s*check',
                r'diagnostico',
            ],
            action=self._action_model_health,
            category="system"
        ))

    def register_skill(self, skill: Skill):
        """Registra un nuevo skill"""
        self.skills[skill.name] = skill
        logger.debug(f"Skill registered: {skill.name}")

    def register_plugin(self, plugin: SkillPlugin, agent: Any):
        """Registra un plugin de skills"""
        try:
            plugin.initialize(agent)
            for skill in plugin.skills:
                self.register_skill(skill)
            self._plugins.append(plugin)
            logger.info(f"Plugin loaded: {plugin.name} ({len(plugin.skills)} skills)")
        except Exception as e:
            logger.error(f"Error loading plugin {plugin.name}: {e}", exc_info=True)

    def match_skill(self, message: str) -> Optional[Tuple[Skill, Optional[re.Match]]]:
        """Busca si el mensaje coincide con algún skill. Retorna (skill, match)"""
        message_lower = message.lower().strip()

        for skill in self.skills.values():
            if not skill.enabled:
                continue

            if skill.cooldown_seconds > 0:
                if time.time() - skill._last_used < skill.cooldown_seconds:
                    continue

            for pattern in skill.trigger_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    skill._last_used = time.time()
                    return skill, match

        return None

    def get_skills_by_category(self) -> Dict[str, List[Skill]]:
        """Agrupa skills por categoría"""
        by_cat: Dict[str, List[Skill]] = defaultdict(list)
        for skill in self.skills.values():
            by_cat[skill.category].append(skill)
        return dict(by_cat)

    # === Acciones ===

    def _action_switch_model(self, message: str, context: Dict) -> str:
        match = re.search(r'(\d+)', message)
        if match:
            model_key = match.group(1)
            selector = context.get('model_selector')
            if selector:
                success, msg = selector.switch_model(model_key)
                if success:
                    agent = context.get('agent')
                    if agent and selector.current_model:
                        agent.current_model = selector.current_model
                return msg
        return "Especifica un número de modelo (ej: 'modelo 3')"

    def _action_list_models(self, message: str, context: Dict) -> str:
        # Nota: AVAILABLE_MODELS debe ser accesible. 
        # En el diseño original estaba en el scope global.
        # Aquí intentamos obtenerlo del contexto o importarlo si es constante.
        from .agent import AVAILABLE_MODELS
        
        if not AVAILABLE_MODELS:
            return "❌ No hay modelos disponibles"

        lines = ["📋 **MODELOS DISPONIBLES:**\n"]
        current = context.get('current_model')

        for key, model in AVAILABLE_MODELS.items():
            model_id = model.id if hasattr(model, 'id') else key
            thinking = "🧠" if hasattr(model, 'thinking') and model.thinking else "  "
            tools = "🔧" if hasattr(model, 'supports_tools') and model.supports_tools else "  "

            is_current = (
                current and hasattr(current, 'id') and current.id == model_id
            )
            marker = " ◄ ACTUAL" if is_current else ""

            specialty = getattr(model, 'specialty', '')
            name = getattr(model, 'name', model_id)

            lines.append(
                f"  `{key}` {thinking}{tools} **{name}**"
                f" - {specialty}{marker}"
            )

        lines.append("\n🧠 = Thinking | 🔧 = Tools")
        return "\n".join(lines)

    def _action_autonomous(self, message: str, context: Dict) -> str:
        return "__AUTONOMOUS_MODE__"

    def _action_status(self, message: str, context: Dict) -> str:
        current_model = context.get('current_model')
        model_name = (
            getattr(current_model, 'name', 'Unknown')
            if current_model else "No configurado"
        )

        tools_count = 0
        tools_by_cat: Dict[str, int] = {}
        if self.tool_registry:
            try:
                all_tools = self.tool_registry.get_all()
                tools_count = len(all_tools)
                for tool in all_tools:
                    cat = getattr(tool, 'category', 'other')
                    tools_by_cat[cat] = tools_by_cat.get(cat, 0) + 1
            except Exception:
                pass

        memory = context.get('memory')
        mem_stats = memory.get_stats() if memory else {}

        skills_by_cat = self.get_skills_by_category()
        skills_info = "\n".join([
            f"   • {cat}: {len(skills)}"
            for cat, skills in sorted(skills_by_cat.items())
        ])

        tools_info = "\n".join([
            f"   • {cat}: {count}"
            for cat, count in sorted(tools_by_cat.items())
        ]) if tools_by_cat else "   (ninguna)"

        has_thinking = (
            hasattr(current_model, 'thinking') and current_model.thinking
            if current_model else False
        )
        has_tools = (
            hasattr(current_model, 'supports_tools') and current_model.supports_tools
            if current_model else False
        )

        # Discord status fallback
        from .agent import DISCORD_AVAILABLE

        return f"""🦞 **OpenClaw v2.1 - Estado del Sistema**

📊 **Modelo actual:** {model_name}
🧠 **Thinking:** {'✅' if has_thinking else '❌'}
🔧 **Tools:** {'✅' if has_tools else '❌'}

💾 **Memoria:**
   • Canales: {mem_stats.get('total_channels', 0)}
   • Mensajes: {mem_stats.get('total_messages', 0)}
   • Almacenamiento: {mem_stats.get('storage_size_kb', 0):.1f} KB

🔌 **Canales:** Consola {'| Discord ✅' if DISCORD_AVAILABLE else '| Discord ❌'}

📝 **Skills por categoría:**
{skills_info}

📦 **Herramientas ({tools_count} total):**
{tools_info}

💬 **Comandos rápidos:**
   • `modelos` - Ver modelos
   • `herramientas` - Ver herramientas
   • `modelo N` - Cambiar modelo
   • `modo autónomo` - Activar autonomía
   • `clear` - Nueva conversación
   • `salud modelos` - Diagnóstico
"""

    def _action_list_tools(self, message: str, context: Dict) -> str:
        if not self.tool_registry:
            return "❌ Sistema de herramientas no disponible"

        try:
            tools = self.tool_registry.get_all()
        except Exception:
            return "❌ Error accediendo a herramientas"

        if not tools:
            return "📦 No hay herramientas registradas"

        by_category: Dict[str, list] = defaultdict(list)
        for tool in tools:
            cat = getattr(tool, 'category', 'other')
            by_category[cat].append(tool)

        lines = [f"🔧 **HERRAMIENTAS DISPONIBLES** ({len(tools)} total)\n"]

        for cat in sorted(by_category.keys()):
            cat_tools = by_category[cat]
            lines.append(f"\n**📁 {cat.upper()}** ({len(cat_tools)})")

            for tool in cat_tools[:10]:
                name = getattr(tool, 'name', '?')
                desc = getattr(tool, 'description', '')
                if len(desc) > 50:
                    desc = desc[:47] + "..."
                lines.append(f"   • `{name}` - {desc}")

            if len(cat_tools) > 10:
                lines.append(f"   _... y {len(cat_tools) - 10} más_")

        return "\n".join(lines)

    def _action_clear_context(self, message: str, context: Dict) -> str:
        memory = context.get('memory')
        channel_id = context.get('channel_id', 'console')

        if memory:
            memory.clear_channel(channel_id)
            return "🗑️ Contexto limpiado. ¡Nueva conversación!"
        return "❌ Error: memoria no disponible"

    def _action_model_health(self, message: str, context: Dict) -> str:
        selector = context.get('model_selector')
        if not selector:
            return "❌ Selector de modelos no disponible"

        health = selector.get_model_health()

        if not health:
            return "📊 No hay datos de uso de modelos aún"

        lines = ["📊 **SALUD DE MODELOS**\n"]

        for model_id, data in health.items():
            state_icon = {
                'closed': '🟢',
                'open': '🔴',
                'half_open': '🟡'
            }.get(data['circuit_state'], '⚪')

            sr = data['success_rate']
            sr_str = f"{sr:.0%}" if sr is not None else "N/A"

            lines.append(
                f"  {state_icon} `{model_id}`\n"
                f"     Éxito: {sr_str} | "
                f"Calls: {data['total_calls']} | "
                f"Avg: {data['avg_response_time']:.1f}s"
            )

            if data['last_error']:
                error_preview = str(data['last_error'])[:60]
                lines.append(f"     ⚠️ Último error: {error_preview}")

        return "\n".join(lines)
