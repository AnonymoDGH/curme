#!/usr/bin/env python3
"""
OpenClaw Launcher - Inicia el agente autónomo
"""

import sys
import os

# Añadir directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.openclaw import OpenClawAgent, run_openclaw

def main():
    """Punto de entrada principal"""
    
    # Banner
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🦞 OPENCLAW - Agente Autónomo                              ║
║   ───────────────────────────────────                        ║
║   100% Autónomo | Multi-canal | Auto-modelado                ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Verificar token de Discord (opcional)
    discord_token = os.environ.get('DISCORD_TOKEN')
    discord_channels = os.environ.get('DISCORD_CHANNELS', '').split(',') if os.environ.get('DISCORD_CHANNELS') else None
    
    # Crear agente
    agent = OpenClawAgent()
    
    # Iniciar
    try:
        agent.start(
            discord_token=discord_token,
            discord_channels=discord_channels
        )
    except KeyboardInterrupt:
        print("\n\n👋 ¡Hasta luego!")
        agent.stop()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
