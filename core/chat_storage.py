"""
═══════════════════════════════════════════════════════════════════════════════
                      GESTIÓN DE ALMACENAMIENTO DE CHATS
═══════════════════════════════════════════════════════════════════════════════

Módulo para guardar, cargar y gestionar conversaciones/sesiones de chat.

Comandos:
- /history              - Listar todos los chats guardados
- /save chat [nombre]   - Guardar chat actual con nombre personalizado
- /resume chat [nombre] - Retomar chat guardado
- /delete chat [nombre] - Eliminar chat guardado

"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# Directorio de almacenamiento de chats
CHATS_DIR = Path("chats")

# Asegurar que el directorio existe
CHATS_DIR.mkdir(exist_ok=True)


@dataclass
class ChatMetadata:
    """Metadatos de un chat guardado"""
    name: str
    filename: str
    created_at: str
    last_modified: str
    message_count: int
    model: str
    description: Optional[str] = None
    
    @property
    def created_at_formatted(self) -> str:
        """Fecha de creación formateada"""
        try:
            dt = datetime.fromisoformat(self.created_at)
            return dt.strftime("%d/%m/%Y %H:%M")
        except:
            return self.created_at
    
    @property
    def last_modified_formatted(self) -> str:
        """Fecha de última modificación formateada"""
        try:
            dt = datetime.fromisoformat(self.last_modified)
            return dt.strftime("%d/%m/%Y %H:%M")
        except:
            return self.last_modified


@dataclass
class ChatData:
    """Datos completos de un chat"""
    metadata: ChatMetadata
    messages: List[Dict[str, Any]]
    working_directory: Optional[str] = None
    heavy_mode: bool = False
    stream_enabled: bool = True


class ChatStorage:
    """Gestiona el almacenamiento y recuperación de chats"""
    
    @staticmethod
    def _get_chat_filename(name: str) -> str:
        """Genera un nombre de archivo seguro a partir del nombre del chat"""
        # Reemplazar caracteres no alfanuméricos con guiones bajos
        safe_name = "".join(c if c.isalnum() or c in '_-' else '_' for c in name)
        return f"{safe_name}.json"
    
    @staticmethod
    def _get_filepath(name: str) -> Path:
        """Obtiene la ruta completa del archivo del chat"""
        filename = ChatStorage._get_chat_filename(name)
        return CHATS_DIR / filename
    
    @staticmethod
    def save_chat(
        name: str,
        messages: List[Dict[str, Any]],
        model_id: str,
        working_directory: Optional[str] = None,
        heavy_mode: bool = False,
        stream_enabled: bool = True,
        description: Optional[str] = None
    ) -> bool:
        """
        Guarda un chat con el nombre especificado.
        
        Args:
            name: Nombre del chat
            messages: Lista de mensajes de la conversación
            model_id: ID del modelo utilizado
            working_directory: Directorio de trabajo (opcional)
            heavy_mode: Si el modo Heavy Agent estaba activado
            stream_enabled: Si el streaming estaba habilitado
            description: Descripción opcional del chat
            
        Returns:
            True si se guardó correctamente
        """
        try:
            filepath = ChatStorage._get_filepath(name)
            
            # Verificar si existe para preservar fecha de creación
            existing_created_at = None
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    existing_created_at = existing_data.get('metadata', {}).get('created_at')
            
            now = datetime.now().isoformat()
            
            metadata = ChatMetadata(
                name=name,
                filename=filepath.name,
                created_at=existing_created_at or now,
                last_modified=now,
                message_count=len(messages),
                model=model_id,
                description=description
            )
            
            chat_data = ChatData(
                metadata=metadata,
                messages=messages,
                working_directory=working_directory,
                heavy_mode=heavy_mode,
                stream_enabled=stream_enabled
            )
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(chat_data.__dict__, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Error al guardar chat: {e}")
            return False
    
    @staticmethod
    def load_chat(name: str) -> Optional[ChatData]:
        """
        Carga un chat por su nombre.
        
        Args:
            name: Nombre del chat a cargar
            
        Returns:
            ChatData si se encontró, None en caso contrario
        """
        try:
            filepath = ChatStorage._get_filepath(name)
            
            if not filepath.exists():
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstruir objetos desde diccionarios
            metadata_dict = data.get('metadata', {})
            metadata = ChatMetadata(**metadata_dict)
            
            chat_data = ChatData(
                metadata=metadata,
                messages=data.get('messages', []),
                working_directory=data.get('working_directory'),
                heavy_mode=data.get('heavy_mode', False),
                stream_enabled=data.get('stream_enabled', True)
            )
            
            return chat_data
            
        except Exception as e:
            print(f"Error al cargar chat: {e}")
            return None
    
    @staticmethod
    def list_chats() -> List[ChatMetadata]:
        """
        Lista todos los chats guardados.
        
        Returns:
            Lista de metadatos de chats ordenados por fecha de modificación
        """
        chats = []
        
        try:
            for filepath in CHATS_DIR.glob("*.json"):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    metadata_dict = data.get('metadata', {})
                    metadata = ChatMetadata(**metadata_dict)
                    chats.append(metadata)
                    
                except Exception as e:
                    print(f"Error leyendo {filepath.name}: {e}")
                    continue
            
            # Ordenar por última modificación (más recientes primero)
            chats.sort(key=lambda x: x.last_modified, reverse=True)
            
        except Exception as e:
            print(f"Error listando chats: {e}")
        
        return chats
    
    @staticmethod
    def delete_chat(name: str) -> bool:
        """
        Elimina un chat guardado.
        
        Args:
            name: Nombre del chat a eliminar
            
        Returns:
            True si se eliminó correctamente
        """
        try:
            filepath = ChatStorage._get_filepath(name)
            
            if not filepath.exists():
                return False
            
            os.remove(filepath)
            return True
            
        except Exception as e:
            print(f"Error al eliminar chat: {e}")
            return False
    
    @staticmethod
    def rename_chat(old_name: str, new_name: str) -> bool:
        """
        Renombra un chat.
        
        Args:
            old_name: Nombre actual del chat
            new_name: Nuevo nombre del chat
            
        Returns:
            True si se renombró correctamente
        """
        try:
            old_filepath = ChatStorage._get_filepath(old_name)
            new_filepath = ChatStorage._get_filepath(new_name)
            
            if not old_filepath.exists():
                return False
            
            if new_filepath.exists():
                print(f"Ya existe un chat con el nombre '{new_name}'")
                return False
            
            # Cargar datos para actualizar el nombre en metadatos
            with open(old_filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Actualizar metadatos
            data['metadata']['name'] = new_name
            data['metadata']['filename'] = new_filepath.name
            data['metadata']['last_modified'] = datetime.now().isoformat()
            
            # Guardar con nuevo nombre
            with open(new_filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Eliminar archivo antiguo
            os.remove(old_filepath)
            
            return True
            
        except Exception as e:
            print(f"Error al renombrar chat: {e}")
            return False
    
    @staticmethod
    def search_chats(query: str) -> List[ChatMetadata]:
        """
        Busca chats por nombre o descripción.
        
        Args:
            query: Término de búsqueda
            
        Returns:
            Lista de chats que coinciden con la búsqueda
        """
        all_chats = ChatStorage.list_chats()
        query_lower = query.lower()
        
        results = []
        for chat in all_chats:
            if (query_lower in chat.name.lower() or 
                (chat.description and query_lower in chat.description.lower())):
                results.append(chat)
        
        return results
    
    @staticmethod
    def get_chat_count() -> int:
        """Retorna el número de chats guardados"""
        try:
            return len(list(CHATS_DIR.glob("*.json")))
        except:
            return 0
    
    @staticmethod
    def export_chat(name: str, export_path: str, format: str = 'json') -> bool:
        """
        Exporta un chat a diferentes formatos.
        
        Args:
            name: Nombre del chat a exportar
            export_path: Ruta de salida
            format: Formato de exportación ('json', 'txt', 'md')
            
        Returns:
            True si se exportó correctamente
        """
        try:
            chat_data = ChatStorage.load_chat(name)
            if not chat_data:
                return False
            
            export_path = Path(export_path)
            
            if format == 'json':
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(chat_data.__dict__, f, indent=2, ensure_ascii=False)
            
            elif format == 'txt':
                with open(export_path, 'w', encoding='utf-8') as f:
                    f.write(f"Chat: {chat_data.metadata.name}\n")
                    f.write(f"Modelo: {chat_data.metadata.model}\n")
                    f.write(f"Fecha: {chat_data.metadata.last_modified_formatted}\n")
                    f.write(f"Mensajes: {chat_data.metadata.message_count}\n")
                    f.write("=" * 80 + "\n\n")
                    
                    for msg in chat_data.messages:
                        role = msg.get('role', 'unknown').upper()
                        content = msg.get('content', '')
                        f.write(f"[{role}]\n{content}\n\n")
            
            elif format == 'md':
                with open(export_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {chat_data.metadata.name}\n\n")
                    f.write(f"**Modelo:** {chat_data.metadata.model}\n\n")
                    f.write(f"**Fecha:** {chat_data.metadata.last_modified_formatted}\n\n")
                    f.write(f"**Mensajes:** {chat_data.metadata.message_count}\n\n")
                    f.write("---\n\n")
                    
                    for msg in chat_data.messages:
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        
                        if role == 'user':
                            f.write(f"## 👤 Usuario\n\n")
                        elif role == 'assistant':
                            f.write(f"## 🤖 Asistente\n\n")
                        elif role == 'tool':
                            f.write(f"## 🛠️ Herramienta\n\n")
                        
                        f.write(f"{content}\n\n")
            
            return True
            
        except Exception as e:
            print(f"Error al exportar chat: {e}")
            return False
