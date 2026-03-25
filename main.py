#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                           NVIDIA CODE v2.0                                     ║
║                    Agente de Programación Inteligente                          ║
║                                                                                 ║
║  Uso:                                                                           ║
║    python main.py              - Modo interactivo                              ║
║    python main.py --heavy      - Iniciar en modo Heavy Agent                   ║
║    python main.py -h           - Ayuda                                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import argparse
from pathlib import Path

# Asegurar que el directorio raíz está en el path
sys.path.insert(0, str(Path(__file__).parent))

from core.agent import NVIDIACodeAgent
from ui.logo import print_logo
from ui.colors import Colors

C = Colors()


def parse_arguments():
    """Parsea argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(
        description="NVIDIA Code - Agente de Programación Inteligente",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py                    Modo interactivo normal
  python main.py --heavy            Iniciar con Heavy Agent activado
  python main.py --model 3          Usar modelo específico
  python main.py --workdir /path    Establecer directorio de trabajo
        """
    )
    
    parser.add_argument(
        "--heavy", "-H",
        action="store_true",
        help="Activar modo Heavy Agent (colaboración multi-IA)"
    )
    
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="1",
        help="Modelo a usar (1-11 o ID completo)"
    )
    
    parser.add_argument(
        "--workdir", "-w",
        type=str,
        default=None,
        help="Directorio de trabajo inicial"
    )
    
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Desactivar streaming de respuestas"
    )
    
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="NVIDIA Code v2.0"
    )
    
    return parser.parse_args()


def main():
    """Punto de entrada principal"""
    args = parse_arguments()
    
    try:
        # Crear agente
        agent = NVIDIACodeAgent(
            initial_model=args.model,
            working_directory=args.workdir,
            stream=not args.no_stream,
            heavy_mode=args.heavy
        )
        
        # Mostrar logo
        print_logo()
        
        if args.heavy:
            print(f"{C.BRIGHT_MAGENTA}🔥 MODO HEAVY AGENT ACTIVADO 🔥{C.RESET}")
            print(f"{C.DIM}Colaboración multi-IA con los 3 mejores modelos{C.RESET}\n")
        
        # Ejecutar
        agent.run()
        
    except KeyboardInterrupt:
        print(f"\n{C.NVIDIA_GREEN}👋 ¡Hasta luego!{C.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"{C.RED}❌ Error fatal: {e}{C.RESET}")
        if "--debug" in sys.argv:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()