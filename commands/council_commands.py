"""
NVIDIA CODE - Comandos para el Modo Council
==============================================

Comandos para interactuar con el modo Council inspirado en llm-council.

Comandos disponibles:
    /council            - Activa el modo Council para la siguiente consulta
    /council-config     - Configura los modelos del consejo
    /council-models     - Muestra los modelos disponibles
    /council-last       - Muestra el resultado del último council
"""

import sys
from typing import Optional, List
from pathlib import Path

# Añadir directorio padre al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.council_agent import CouncilAgent, run_council_sync, CouncilResult
from core.api_client import NVIDIAAPIClient
from models.registry import ModelRegistry
from ui.colors import Colors
from config import HEAVY_AGENT_CONFIG

C = Colors()

# Almacenamiento del último resultado del council
_last_council_result: Optional[CouncilResult] = None


def cmd_council(query: str = "", **kwargs) -> str:
    """
    Activa el modo Council para la consulta actual.
    
    Uso:
        /council [opciones] [pregunta]
    
    Opciones:
        --models "model1,model2"  # Especificar modelos del consejo
        --chairman model_id       # Especificar modelo presidente
        --show-stages             # Mostrar todas las etapas
        --no-summary              # No mostrar resumen final
    """
    global _last_council_result
    
    # Parsear argumentos
    models = kwargs.get('models')
    chairman = kwargs.get('chairman')
    show_stages = kwargs.get('show_stages', False)
    no_summary = kwargs.get('no_summary', False)
    
    # Determinar la consulta
    if query:
        user_query = query
    else:
        user_query = kwargs.get('query', '')
    
    if not user_query:
        return f"""
{C.YELLOW}Modo Council{C.RESET}
{C.DIM}Uso: /council [opciones] "tu pregunta"{C.RESET}

Opciones:
  --models "model1,model2"    Modelos del consejo (default: configurados)
  --chairman model_id         Modelo presidente (default: z-ai/glm4.7)
  --show-stages               Mostrar todas las etapas
  --no-summary                No mostrar resumen final

Ejemplos:
  /council "¿Qué es un closure en Python?"
  /council --models "z-ai/glm4.7,nvidia/nemotron-3-nano" "¿Cómo funciona GC?"
"""
    
    # Configurar modelos
    council_models = None
    if models:
        council_models = [m.strip() for m in models.split(',')]
    
    chairman_model = chairman or HEAVY_AGENT_CONFIG.get("synthesizer_model", "z-ai/glm4.7")
    
    # Ejecutar council
    import asyncio
    
    try:
        api_client = NVIDIAAPIClient()
        
        council = CouncilAgent(
            council_models=council_models,
            chairman_model=chairman_model,
            api_client=api_client
        )
        
        result = asyncio.run(council.run_full_council(user_query))
        _last_council_result = result
        
        # Preparar respuesta
        response = result.stage3_result.final_response
        
        if not no_summary:
            response += f"\n\n{C.DIM}─ Consejo: {len(result.stage1_results)} modelos evaluados ─{C.RESET}"
        
        return response
        
    except Exception as e:
        return f"{C.RED}[!] Error en el modo Council: {e}{C.RESET}"


def cmd_council_config(**kwargs) -> str:
    """
    Configura los modelos del consejo.
    
    Uso:
        /council-config [opciones]
    
    Opciones:
        --set-models "model1,model2"   Establecer modelos del consejo
        --set-chairman model_id        Establecer modelo presidente
        --show                         Mostrar configuración actual
        --reset                        Restablecer a default
    """
    action = kwargs.get('action', 'show')
    
    if action == 'show':
        return _show_council_config()
    
    elif action == 'set-models':
        models = kwargs.get('models')
        if not models:
            return f"{C.RED}[!] Especifica los modelos: --set-models \"model1,model2\"{C.RESET}"
        
        # Validar modelos
        registry = ModelRegistry()
        model_ids = [m.strip() for m in models.split(',')]
        
        valid_models = []
        invalid_models = []
        
        for model_id in model_ids:
            if registry.get_model_by_id(model_id):
                valid_models.append(model_id)
            else:
                invalid_models.append(model_id)
        
        if invalid_models:
            return f"{C.RED}[!] Modelos inválidos: {', '.join(invalid_models)}{C.RESET}\n{C.DIM}Usa /council-models para ver disponibles{C.RESET}"
        
        # Actualizar configuración (en memoria para la sesión)
        HEAVY_AGENT_CONFIG["primary_models"] = valid_models
        
        return f"""
{C.GREEN}✓{C.RESET} Modelos del consejo actualizados:
{C.CYAN}{', '.join(valid_models)}{C.RESET}
"""
    
    elif action == 'set-chairman':
        chairman = kwargs.get('chairman')
        if not chairman:
            return f"{C.RED}[!] Especifica el modelo: --set-chairman model_id{C.RESET}"
        
        # Validar modelo
        registry = ModelRegistry()
        if not registry.get_model_by_id(chairman):
            return f"{C.RED}[!] Modelo inválido: {chairman}{C.RESET}\n{C.DIM}Usa /council-models para ver disponibles{C.RESET}"
        
        HEAVY_AGENT_CONFIG["synthesizer_model"] = chairman
        
        return f"""
{C.GREEN}✓{C.RESET} Modelo presidente actualizado:
{C.CYAN}{chairman}{C.RESET}
"""
    
    elif action == 'reset':
        from config import HEAVY_AGENT_CONFIG as default_config
        
        HEAVY_AGENT_CONFIG["primary_models"] = default_config.get("primary_models", ["z-ai/glm4.7"])
        HEAVY_AGENT_CONFIG["synthesizer_model"] = default_config.get("synthesizer_model", "z-ai/glm4.7")
        
        return f"""
{C.GREEN}✓{C.RESET} Configuración restablecida a valores default
"""
    
    else:
        return f"""
{C.YELLOW}Configuración del Consejo{C.RESET}
{C.DIM}Uso: /council-config [acción]{C.RESET}

Acciones:
  --show                      Mostrar configuración actual
  --set-models "m1,m2,m3"     Establecer modelos del consejo
  --set-chairman model_id     Establecer modelo presidente
  --reset                     Restablecer a default
"""


def _show_council_config() -> str:
    """Muestra la configuración actual del consejo"""
    council_models = HEAVY_AGENT_CONFIG.get("primary_models", [])
    chairman_model = HEAVY_AGENT_CONFIG.get("synthesizer_model", "")
    
    registry = ModelRegistry()
    
    # Obtener nombres de modelos
    council_names = []
    for model_id in council_models:
        model_info = registry.get_model_by_id(model_id)
        if model_info:
            council_names.append(f"{model_info.name} ({model_id})")
        else:
            council_names.append(f"Unknown ({model_id})")
    
    chairman_info = registry.get_model_by_id(chairman_model)
    chairman_name = chairman_info.name if chairman_info else "Unknown"
    
    output = f"""
{C.CYAN}╔══════════════════════════════════════════════════════════════╗
║                    COUNCIL CONFIGURACIÓN                         ║
╚══════════════════════════════════════════════════════════════╝{C.RESET}

{C.WHITE}Modelos del Consejo:{C.RESET}
"""
    
    for i, name in enumerate(council_names, 1):
        output += f"  {C.CYAN}{i}.{C.RESET} {name}\n"
    
    output += f"""
{C.WHITE}Modelo Presidente:{C.RESET}
  🏛️  {chairman_name} ({chairman_model})

{C.WHITE}Configuración:{C.RESET}
  • Rondas mínimas: {HEAVY_AGENT_CONFIG.get("min_rounds", 1)}
  • Rondas máximas: {HEAVY_AGENT_CONFIG.get("max_rounds", 2)}
  • Umbral de consenso: {HEAVY_AGENT_CONFIG.get("consensus_threshold", 0.70)}
  • Tokens debate: {HEAVY_AGENT_CONFIG.get("debate_max_tokens", 4096)}
  • Tokens síntesis: {HEAVY_AGENT_CONFIG.get("synthesis_max_tokens", 8192)}
  • Timeout: {HEAVY_AGENT_CONFIG.get("request_timeout", 120)}s

{C.DIM}Usa /council-models para ver todos los modelos disponibles{C.RESET}
{C.DIM}Usa /council-config --set-models para cambiar{C.RESET}
"""
    
    return output


def cmd_council_models(**kwargs) -> str:
    """
    Muestra los modelos disponibles para el consejo.
    
    Uso:
        /council-models
    """
    registry = ModelRegistry()
    models = registry.list_models()
    
    output = f"""
{C.CYAN}╔══════════════════════════════════════════════════════════════╗
║                   MODELOS DISPONIBLES                           ║
╚══════════════════════════════════════════════════════════════╝{C.RESET}

{C.WHITE}Modelos Recomendados para Consejo:{C.RESET}
"""
    
    # Modelos recomendados (con thinking)
    recommended = []
    for key, model in models.items():
        if model.thinking and model.supports_tools:
            recommended.append((key, model))
    
    for key, model in recommended[:6]:
        tier_colors = {"standard": C.WHITE, "premium": C.GREEN, "ultra": C.MAGENTA}
        tier_color = tier_colors.get(model.tier, C.WHITE)
        
        output += f"""
  {C.CYAN}{key}.{C.RESET} {C.BOLD}{model.name}{C.RESET}
     {C.DIM}ID:{C.RESET} {model.id}
     {C.DIM}Especialidad:{C.RESET} {model.specialty}
     {C.DIM}Tier:{C.RESET} {tier_color}{model.tier}{C.RESET}
     {C.DIM}Max Tokens:{C.RESET} {model.max_tokens}
"""
    
    output += f"""
{C.WHITE}Todos los Modelos:{C.RESET}
"""
    
    for key, model in models.items():
        output += f"  {C.CYAN}{key}.{C.RESET} {model.name} [{model.tier}]\n"
    
    output += f"""
{C.DIM}Usa /council-config --set-models "model1,model2" para configurar{C.RESET}
"""
    
    return output


def cmd_council_last(**kwargs) -> str:
    """
    Muestra el resultado del último council ejecutado.
    
    Uso:
        /council-last [opciones]
    
    Opciones:
        --stage1      Mostrar respuestas individuales
        --stage2      Mostrar rankings
        --ranking     Mostrar rankings agregados
        --full        Mostrar todo
    """
    global _last_council_result
    
    if _last_council_result is None:
        return f"{C.YELLOW}[!] No hay resultados del council recientes{C.RESET}"
    
    show_stage1 = kwargs.get('stage1', False)
    show_stage2 = kwargs.get('stage2', False)
    show_ranking = kwargs.get('ranking', False)
    show_full = kwargs.get('full', False)
    
    output = f"""
{C.CYAN}╔══════════════════════════════════════════════════════════════╗
║                   ÚLTIMO COUNCIL                                 ║
╚══════════════════════════════════════════════════════════════╝{C.RESET}

{C.WHITE}Metadatos:{C.RESET}
  • Tiempo total: {_last_council_result.metadata.total_time:.2f}s
  • Stage 1 (respuestas): {_last_council_result.metadata.stage1_time:.2f}s
  • Stage 2 (rankings): {_last_council_result.metadata.stage2_time:.2f}s
  • Stage 3 (síntesis): {_last_council_result.metadata.stage3_time:.2f}s
"""
    
    if show_ranking or show_full:
        output += f"""
{C.WHITE}Rankings Agregados (Consenso):{C.RESET}
"""
        for i, item in enumerate(_last_council_result.metadata.aggregate_rankings, 1):
            # Encontrar nombre del modelo
            model_name = item['model']
            for r in _last_council_result.stage1_results:
                if r.model_id == item['model']:
                    model_name = r.model_name
                    break
            
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            output += f"  {medal} {model_name} (avg: {item['average_rank']}, votes: {item['rankings_count']})\n"
    
    if show_stage1 or show_full:
        output += f"""
{C.WHITE}Respuestas Individuales (Stage 1):{C.RESET}
"""
        for result in _last_council_result.stage1_results:
            if result.response:
                output += f"\n{C.GREEN}▸ {result.model_name}{C.RESET}\n"
                output += f"{C.DIM}{result.response[:300]}...{C.RESET}\n"
    
    if show_stage2 or show_full:
        output += f"""
{C.WHITE}Rankings Peer-to-Peer (Stage 2):{C.RESET}
"""
        for result in _last_council_result.stage2_results:
            output += f"\n{C.BLUE}▸ {result.model_name}{C.RESET}\n"
            output += f"{C.DIM}Ranking: {' → '.join(result.parsed_ranking[:5])}{C.RESET}\n"
    
    output += f"""
{C.WHITE}Respuesta Final (Presidente):{C.RESET}
{_last_council_result.stage3_result.final_response}
"""
    
    return output


# ============================================================================
# REGISTRO DE COMANDOS
# ============================================================================

COUNCIL_COMMANDS = {
    'council': cmd_council,
    'council-config': cmd_council_config,
    'council-models': cmd_council_models,
    'council-last': cmd_council_last,
}


# ============================================================================
# HELP
# ============================================================================

def council_help() -> str:
    """Muestra la ayuda de comandos del consejo"""
    return f"""
{C.CYAN}╔══════════════════════════════════════════════════════════════╗
║              COUNCIL MODE - AYUDA DE COMANDOS                   ║
╚══════════════════════════════════════════════════════════════╝{C.RESET}

{C.WHITE}Comandos Disponibles:{C.RESET}

  {C.CYAN}/council{C.RESET} [opciones] "pregunta"
      Activa el modo Council para la consulta actual.
      --models "m1,m2,m3"    Especificar modelos del consejo
      --chairman model_id    Especificar modelo presidente
      --show-stages          Mostrar todas las etapas
      --no-summary           No mostrar resumen final

  {C.CYAN}/council-config{C.RESET} [acción]
      Configura los modelos del consejo.
      --show                  Mostrar configuración actual
      --set-models "m1,m2,m3" Establecer modelos del consejo
      --set-chairman model_id Establecer modelo presidente
      --reset                 Restablecer a default

  {C.CYAN}/council-models{C.RESET}
      Muestra los modelos disponibles para el consejo.

  {C.CYAN}/council-last{C.RESET} [opciones]
      Muestra el resultado del último council ejecutado.
      --stage1      Mostrar respuestas individuales
      --stage2      Mostrar rankings
      --ranking     Mostrar rankings agregados
      --full        Mostrar todo

{C.WHITE}Ejemplos:{C.RESET}
  /council "¿Qué es un closure en Python?"
  /council --models "z-ai/glm4.7,nvidia/nemotron" "¿Cómo funciona GC?"
  /council-config --show
  /council-config --set-models "z-ai/glm4.7,minimaxai/minimax-m2"
  /council-models
  /council-last --ranking

{C.WHITE}Información:{C.RESET}
  El modo Council implementa un sistema de deliberación en 3 etapas:
  1. Recopilación de respuestas individuales (paralelo)
  2. Peer review anónimo (cada modelo evalúa respuestas de otros)
  3. Síntesis final por el Presidente

  Inspirado en llm-council de Andrej Karpathy.
"""
