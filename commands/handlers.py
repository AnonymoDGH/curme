"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         MANEJADORES DE COMANDOS                                ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from typing import Callable, Dict, Optional
from dataclasses import dataclass


@dataclass
class Command:
    """Definición de un comando"""
    name: str
    aliases: list
    description: str
    handler: Callable
    usage: str = ""


class CommandHandler:
    """Registro y manejo de comandos"""
    
    def __init__(self):
        self.commands: Dict[str, Command] = {}
        self.aliases: Dict[str, str] = {}
    
    def register(self, command: Command):
        """Registra un comando"""
        self.commands[command.name] = command
        for alias in command.aliases:
            self.aliases[alias] = command.name
    
    def get(self, name: str) -> Optional[Command]:
        """Obtiene un comando por nombre o alias"""
        if name in self.commands:
            return self.commands[name]
        if name in self.aliases:
            return self.commands[self.aliases[name]]
        return None
    
    def execute(self, name: str, args: str, context: dict) -> bool:
        """Ejecuta un comando"""
        command = self.get(name)
        if command:
            command.handler(args, context)
            return True
        return False
    
    def list_all(self) -> list:
        """Lista todos los comandos"""
        return list(self.commands.values())