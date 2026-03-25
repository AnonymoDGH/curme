"""
═══════════════════════════════════════════════════════════════════════════════
                      COMANDOS DE GESTIÓN DE CHATS
═══════════════════════════════════════════════════════════════════════════════

Extensiones de comandos para gestionar chats guardados.

Comandos:
- /chat list            - Listar todos los chats guardados
- /save chat [nombre]   - Guardar chat actual con nombre personalizado
- /resume chat [nombre] - Retomar chat guardado
- /delete chat [nombre] - Eliminar chat guardado
- /search chat [term]   - Buscar chats

"""

import os
from typing import TYPE_CHECKING

from ui.colors import Colors
from core.chat_storage import ChatStorage

C = Colors()

if TYPE_CHECKING:
    from core.agent import NVIDIACodeAgent


class ChatCommands:
    """Comandos extendidos para gestión de chats"""
    
    def __init__(self, agent: 'NVIDIACodeAgent'):
        self.agent = agent
    
    def cmd_chat_list(self, args: str) -> bool:
        """Lista todos los chats guardados"""
        chats = ChatStorage.list_chats()
        
        if not chats:
            print(f"\n{C.DIM}No hay chats guardados{C.RESET}\n")
            return True
        
        print(f"\n{C.NVIDIA_GREEN}Chats Guardados ({len(chats)}):{C.RESET}\n")
        print(f"{'Nombre':<30} {'Mensajes':<10} {'Modelo':<15} {'Creado':<20} {'Ultima modificacion'}")
        print("=" * 100)
        
        for chat in chats:
            name = chat.name[:28] + '..' if len(chat.name) > 30 else chat.name
            print(f"{name:<30} {chat.message_count:<10} {chat.model:<15} {chat.created_at_formatted:<20} {chat.last_modified_formatted}")
        
        print(f"\n{C.DIM}Uso: /resume chat <nombre> | /save chat <nombre> | /delete chat <nombre>{C.RESET}\n")
        return True
    
    def cmd_chat_save(self, args: str) -> bool:
        """Guarda el chat actual con un nombre personalizado"""
        name = args.strip()
        
        if not name:
            print(f"\n{C.RED}Error: Debes proporcionar un nombre para el chat{C.RESET}")
            print(f"{C.DIM}Uso: /save chat <nombre>{C.RESET}\n")
            return False
        
        # Guardar el chat
        success = ChatStorage.save_chat(
            name=name,
            messages=self.agent.conversation.messages,
            model_id=self.agent.current_model.id,
            working_directory=self.agent.working_directory,
            heavy_mode=self.agent.heavy_mode if hasattr(self.agent, 'heavy_mode') else False,
            stream_enabled=self.agent.stream if hasattr(self.agent, 'stream') else True
        )
        
        if success:
            print(f"\n{C.NVIDIA_GREEN}Chat guardado como: {name}{C.RESET}")
            print(f"{C.DIM}Mensajes: {len(self.agent.conversation.messages)}{C.RESET}\n")
            return True
        else:
            print(f"\n{C.RED}Error al guardar el chat{C.RESET}\n")
            return False
    
    def cmd_chat_resume(self, args: str) -> bool:
        """Retoma un chat guardado"""
        name = args.strip()
        
        if not name:
            print(f"\n{C.DIM}Usa '/chat list' para ver los chats disponibles{C.RESET}")
            print(f"{C.DIM}Uso: /resume chat <nombre>{C.RESET}\n")
            return False
        
        # Cargar el chat
        chat_data = ChatStorage.load_chat(name)
        
        if not chat_data:
            print(f"\n{C.RED}No se encontro el chat: {name}{C.RESET}\n")
            return False
        
        # Restaurar la conversacion
        self.agent.conversation.messages = chat_data.messages
        
        # Restaurar configuracion si esta disponible
        if chat_data.working_directory:
            try:
                os.chdir(chat_data.working_directory)
                self.agent.working_directory = chat_data.working_directory
            except:
                pass
        
        if hasattr(self.agent, 'heavy_mode'):
            self.agent.heavy_mode = chat_data.heavy_mode
        
        if hasattr(self.agent, 'stream'):
            self.agent.stream = chat_data.stream_enabled
        
        print(f"\n{C.NVIDIA_GREEN}Chat retomado: {name}{C.RESET}")
        print(f"{C.DIM}Mensajes: {len(chat_data.messages)} | Modelo: {chat_data.metadata.model}{C.RESET}")
        print(f"{C.DIM}Ultima modificacion: {chat_data.metadata.last_modified_formatted}{C.RESET}\n")
        
        return True
    
    def cmd_chat_delete(self, args: str) -> bool:
        """Elimina un chat guardado"""
        name = args.strip()
        
        if not name:
            print(f"\n{C.RED}Error: Debes proporcionar el nombre del chat a eliminar{C.RESET}")
            print(f"{C.DIM}Uso: /delete chat <nombre>{C.RESET}\n")
            return False
        
        # Confirmar eliminacion
        print(f"{C.RED}Estas seguro de eliminar el chat '{name}'? (s/n): {C.RESET}", end='')
        confirm = input().strip().lower()
        
        if confirm != 's' and confirm != 'y':
            print(f"\n{C.DIM}Eliminacion cancelada{C.RESET}\n")
            return True
        
        # Eliminar el chat
        success = ChatStorage.delete_chat(name)
        
        if success:
            print(f"\n{C.NVIDIA_GREEN}Chat eliminado: {name}{C.RESET}\n")
            return True
        else:
            print(f"\n{C.RED}No se encontro el chat: {name}{C.RESET}\n")
            return False
    
    def cmd_chat_search(self, args: str) -> bool:
        """Busca chats por nombre o descripcion"""
        query = args.strip()
        
        if not query:
            print(f"\n{C.RED}Error: Debes proporcionar un termino de busqueda{C.RESET}")
            print(f"{C.DIM}Uso: /search chat <termino>{C.RESET}\n")
            return False
        
        results = ChatStorage.search_chats(query)
        
        if not results:
            print(f"\n{C.DIM}No se encontraron chats que coincidan con: {query}{C.RESET}\n")
            return True
        
        print(f"\n{C.NVIDIA_GREEN}Resultados para '{query}' ({len(results)}):{C.RESET}\n")
        print(f"{'Nombre':<30} {'Mensajes':<10} {'Creado':<20}")
        print("=" * 70)
        
        for chat in results:
            name = chat.name[:28] + '..' if len(chat.name) > 30 else chat.name
            print(f"{name:<30} {chat.message_count:<10} {chat.created_at_formatted:<20}")
        
        print(f"\n{C.DIM}Usa '/resume chat <nombre>' para cargar{C.RESET}\n")
        return True


# Diccionario de comandos disponibles para registro
CHAT_COMMANDS = {
    '/chat list': {
        'handler': 'cmd_chat_list',
        'aliases': ['/chats', '/history'],
        'description': 'Listar todos los chats guardados'
    },
    '/save chat': {
        'handler': 'cmd_chat_save',
        'aliases': [],
        'description': 'Guardar chat actual con nombre personalizado'
    },
    '/resume chat': {
        'handler': 'cmd_chat_resume',
        'aliases': ['/load chat'],
        'description': 'Retomar chat guardado'
    },
    '/delete chat': {
        'handler': 'cmd_chat_delete',
        'aliases': [],
        'description': 'Eliminar chat guardado'
    },
    '/search chat': {
        'handler': 'cmd_chat_search',
        'aliases': [],
        'description': 'Buscar chats por nombre'
    }
}


def register_chat_commands(agent: 'NVIDIACodeAgent', command_handler):
    """
    Registra los comandos de chat en el CommandHandler del agente.
    
    Args:
        agent: Instancia del agente
        command_handler: Instancia del CommandHandler
    """
    chat_commands = ChatCommands(agent)
    
    for command_name, config in CHAT_COMMANDS.items():
        handler_method = getattr(chat_commands, config['handler'])
        command_handler.register(
            command_name,
            handler_method,
            config['aliases'],
            config['description']
        )
    
    print(f"\n{C.NVIDIA_GREEN}Comandos de chat registrados:{C.RESET}")
    for cmd in CHAT_COMMANDS:
        print(f"  {C.DIM}{cmd}{C.RESET}")
    print()
