"""
NVIDIA CODE - Herramientas de Sistema Avanzadas (Corregido)
"""

import subprocess
import os
import sys
import socket
import platform
from pathlib import Path
from typing import Dict
from datetime import datetime

from .base import BaseTool, ToolParameter


class SystemInfoTool(BaseTool):
    """Informacion del sistema"""
    
    name = "system_info"
    description = "Obtiene informacion detallada del sistema operativo, CPU, memoria, Python y entorno"
    category = "system"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "detailed": ToolParameter(
                name="detailed",
                type="boolean",
                description="Si es true, muestra información más detallada incluyendo variables de entorno",
                required=False
            )
        }
    
    def execute(self, detailed: bool = False, **kwargs) -> str:
        detailed = kwargs.get('detailed', detailed)
        
        info = {
            "OS": platform.system(),
            "Version": platform.version(),
            "Arquitectura": platform.machine(),
            "Procesador": platform.processor() or "No disponible",
            "Python": sys.version.split()[0],
            "Hostname": socket.gethostname(),
            "Usuario": os.getenv('USER') or os.getenv('USERNAME') or "Desconocido",
            "Directorio actual": os.getcwd(),
            "Home": str(Path.home()),
        }
        
        output = "💻 **Información del Sistema:**\n\n"
        for key, value in info.items():
            output += f"  **{key}:** {value}\n"
        
        if detailed:
            output += "\n📋 **Información Adicional:**\n\n"
            
            # Variables de entorno importantes
            env_vars = ['PATH', 'PYTHONPATH', 'VIRTUAL_ENV', 'CONDA_DEFAULT_ENV']
            for var in env_vars:
                val = os.getenv(var)
                if val:
                    # Truncar si es muy largo
                    if len(val) > 100:
                        val = val[:100] + "..."
                    output += f"  **{var}:** {val}\n"
            
            # Información de disco
            try:
                if platform.system() == "Windows":
                    import ctypes
                    free_bytes = ctypes.c_ulonglong(0)
                    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                        ctypes.c_wchar_p(os.getcwd()[:3]), 
                        None, None, 
                        ctypes.pointer(free_bytes)
                    )
                    free_gb = free_bytes.value / (1024**3)
                    output += f"  **Espacio libre:** {free_gb:.1f} GB\n"
            except:
                pass
        
        return output


class PortCheckTool(BaseTool):
    """Verifica puertos"""
    
    name = "port_check"
    description = "Verifica si un puerto esta abierto o en uso en el sistema"
    category = "system"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "port": ToolParameter(
                name="port",
                type="integer",
                description="Número de puerto a verificar (1-65535)",
                required=True
            ),
            "host": ToolParameter(
                name="host",
                type="string",
                description="Host a verificar (default: localhost)",
                required=False
            )
        }
    
    def execute(self, port: int = None, host: str = "localhost", **kwargs) -> str:
        port = port or kwargs.get('port', 0)
        host = host or kwargs.get('host', 'localhost')
        
        if not port:
            return "[x] Se requiere 'port'"
        
        if not isinstance(port, int):
            try:
                port = int(port)
            except:
                return "[x] 'port' debe ser un número entero"
        
        if port < 1 or port > 65535:
            return f"[x] Puerto inválido: {port}. Debe estar entre 1 y 65535"
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                return f"✅ Puerto {port} está **ABIERTO** en {host}"
            else:
                return f"❌ Puerto {port} está **CERRADO** en {host}"
        except socket.timeout:
            return f"⏰ Timeout verificando puerto {port} en {host}"
        except socket.gaierror:
            return f"[x] No se puede resolver el host: {host}"
        except socket.error as e:
            return f"[x] Error de socket: {e}"
        except Exception as e:
            return f"[x] Error verificando puerto: {e}"


class ProcessListTool(BaseTool):
    """Lista procesos del sistema"""
    
    name = "process_list"
    description = "Lista los procesos en ejecucion del sistema, opcionalmente filtrados por nombre"
    category = "system"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "filter": ToolParameter(
                name="filter",
                type="string",
                description="Filtrar procesos por nombre (ej: 'python', 'chrome')",
                required=False
            ),
            "limit": ToolParameter(
                name="limit",
                type="integer",
                description="Número máximo de procesos a mostrar (default: 30)",
                required=False
            )
        }
    
    def execute(self, filter: str = None, limit: int = 30, **kwargs) -> str:
        filter_name = filter or kwargs.get('filter', '')
        limit = limit or kwargs.get('limit', 30)
        
        try:
            if platform.system() == "Windows":
                cmd = "tasklist /FO CSV /NH"
            else:
                cmd = "ps aux --no-headers"
            
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            lines = result.stdout.strip().split('\n')
            
            # Filtrar si es necesario
            if filter_name:
                lines = [l for l in lines if filter_name.lower() in l.lower()]
            
            # Limitar cantidad
            lines = lines[:limit]
            
            if not lines:
                if filter_name:
                    return f"🔍 No se encontraron procesos con '{filter_name}'"
                return "📋 No se pudieron obtener procesos"
            
            output = f"📋 **Procesos"
            if filter_name:
                output += f" (filtro: '{filter_name}')"
            output += f"** ({len(lines)} mostrados):\n\n"
            output += "```\n"
            output += "\n".join(lines)
            output += "\n```"
            
            return output
            
        except subprocess.TimeoutExpired:
            return "[x] Timeout obteniendo lista de procesos"
        except Exception as e:
            return f"[x] Error: {e}"


class EnvManageTool(BaseTool):
    """Gestiona variables de entorno"""
    
    name = "env_manage"
    description = "Lee, establece o lista variables de entorno del sistema"
    category = "system"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description="Acción a realizar: get (obtener una variable), set (establecer), list (listar todas), file (leer .env)",
                required=True,
                enum=["get", "set", "list", "file"]
            ),
            "key": ToolParameter(
                name="key",
                type="string",
                description="Nombre de la variable de entorno (requerido para get/set)",
                required=False
            ),
            "value": ToolParameter(
                name="value",
                type="string",
                description="Valor a establecer (solo para action=set)",
                required=False
            )
        }
    
    def execute(self, action: str = None, key: str = None, value: str = None, **kwargs) -> str:
        action = action or kwargs.get('action', '')
        key = key or kwargs.get('key', '')
        value = value if value is not None else kwargs.get('value', '')
        
        if not action:
            return "[x] Se requiere 'action' (get, set, list, file)"
        
        action = action.lower()
        
        if action == "get":
            if not key:
                return "[x] Se requiere 'key' para obtener una variable"
            val = os.environ.get(key)
            if val:
                # Truncar si es muy largo
                display_val = val if len(val) <= 200 else val[:200] + "..."
                return f"🔑 **{key}** = `{display_val}`"
            return f"❌ Variable no encontrada: {key}"
        
        elif action == "set":
            if not key:
                return "[x] Se requiere 'key' para establecer una variable"
            os.environ[key] = value or ""
            return f"✅ Variable establecida: **{key}** = `{value}`"
        
        elif action == "list":
            env_vars = dict(os.environ)
            output = "🔐 **Variables de Entorno:**\n\n"
            
            # Variables importantes primero
            important = ['PATH', 'HOME', 'USER', 'USERNAME', 'SHELL', 
                        'PYTHONPATH', 'VIRTUAL_ENV', 'CONDA_DEFAULT_ENV',
                        'JAVA_HOME', 'NODE_PATH', 'GOPATH']
            
            shown = 0
            for k in important:
                if k in env_vars and shown < 15:
                    v = env_vars[k]
                    if len(v) > 60:
                        v = v[:60] + "..."
                    output += f"  **{k}:** `{v}`\n"
                    shown += 1
            
            # Mostrar algunas más
            for k in sorted(env_vars.keys()):
                if k not in important and shown < 25:
                    v = env_vars[k]
                    if len(v) > 60:
                        v = v[:60] + "..."
                    output += f"  **{k}:** `{v}`\n"
                    shown += 1
            
            if len(env_vars) > shown:
                output += f"\n  ... y {len(env_vars) - shown} variables más"
            
            return output
        
        elif action == "file":
            # Buscar archivo .env
            env_files = [".env", ".env.local", ".env.development"]
            
            for env_file in env_files:
                env_path = Path(env_file)
                if env_path.exists():
                    try:
                        content = env_path.read_text(encoding='utf-8')
                        # Ocultar valores sensibles
                        lines = []
                        for line in content.split('\n'):
                            if '=' in line and not line.strip().startswith('#'):
                                key_part = line.split('=')[0]
                                if any(s in key_part.upper() for s in ['SECRET', 'PASSWORD', 'KEY', 'TOKEN']):
                                    lines.append(f"{key_part}=****")
                                else:
                                    lines.append(line)
                            else:
                                lines.append(line)
                        
                        return f"📄 **{env_file}:**\n```\n{chr(10).join(lines)}\n```"
                    except Exception as e:
                        return f"[x] Error leyendo {env_file}: {e}"
            
            return "❌ No se encontró archivo .env en el directorio actual"
        
        else:
            return f"[x] Acción no soportada: {action}. Usa: get, set, list, file"


class DiskUsageTool(BaseTool):
    """Uso de disco"""
    
    name = "disk_usage"
    description = "Muestra el uso de disco de un directorio, incluyendo tamaño total y distribución por tipo de archivo"
    category = "system"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(
                name="path",
                type="string",
                description="Directorio a analizar (default: directorio actual)",
                required=False
            ),
            "depth": ToolParameter(
                name="depth",
                type="integer",
                description="Profundidad máxima de análisis (default: sin límite)",
                required=False
            )
        }
    
    def execute(self, path: str = ".", depth: int = None, **kwargs) -> str:
        path = path or kwargs.get('path', '.')
        depth = depth or kwargs.get('depth', None)
        
        try:
            dir_path = Path(path)
            if not dir_path.exists():
                return f"[x] No existe: {path}"
            
            if not dir_path.is_dir():
                # Si es un archivo, mostrar su tamaño
                size = dir_path.stat().st_size
                return f"📄 **{path}**: {self._fmt_size(size)}"
            
            # Calcular tamaño
            total_size = 0
            file_count = 0
            dir_count = 0
            sizes_by_ext = {}
            errors = 0
            
            try:
                items = list(dir_path.rglob('*'))
            except PermissionError:
                return f"[x] Sin permisos para acceder a: {path}"
            
            for item in items:
                try:
                    if item.is_file():
                        size = item.stat().st_size
                        total_size += size
                        file_count += 1
                        
                        ext = item.suffix.lower() or '(sin extensión)'
                        sizes_by_ext[ext] = sizes_by_ext.get(ext, 0) + size
                    elif item.is_dir():
                        dir_count += 1
                except (PermissionError, OSError):
                    errors += 1
            
            output = f"""📊 **Uso de disco: {path}**

📁 Directorios: {dir_count:,}
📄 Archivos: {file_count:,}
💾 Tamaño total: {self._fmt_size(total_size)}
"""
            
            if errors > 0:
                output += f"⚠️ Errores de acceso: {errors}\n"
            
            output += "\n**Por extensión:**\n"
            
            sorted_ext = sorted(sizes_by_ext.items(), key=lambda x: -x[1])[:10]
            for ext, size in sorted_ext:
                pct = (size / total_size * 100) if total_size > 0 else 0
                bar_len = int(pct / 5)
                bar = '█' * bar_len + '░' * (20 - bar_len)
                output += f"  {ext:12} {bar} {self._fmt_size(size):>10} ({pct:.1f}%)\n"
            
            if len(sizes_by_ext) > 10:
                output += f"\n  ... y {len(sizes_by_ext) - 10} tipos más"
            
            return output
            
        except Exception as e:
            return f"[x] Error: {e}"
    
    def _fmt_size(self, bytes_size: int) -> str:
        """Formatea bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"


class KillProcessTool(BaseTool):
    """Termina un proceso"""
    
    name = "kill_process"
    description = "Termina un proceso por nombre o PID"
    category = "system"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "target": ToolParameter(
                name="target",
                type="string",
                description="Nombre del proceso o PID a terminar",
                required=True
            ),
            "force": ToolParameter(
                name="force",
                type="boolean",
                description="Forzar terminación (kill -9)",
                required=False
            )
        }
    
    def execute(self, target: str = None, force: bool = False, **kwargs) -> str:
        target = target or kwargs.get('target', '')
        force = force or kwargs.get('force', False)
        
        if not target:
            return "[x] Se requiere 'target' (nombre o PID del proceso)"
        
        try:
            if platform.system() == "Windows":
                if target.isdigit():
                    cmd = f"taskkill /PID {target}"
                else:
                    cmd = f"taskkill /IM {target}"
                if force:
                    cmd += " /F"
            else:
                signal = "-9" if force else "-15"
                if target.isdigit():
                    cmd = f"kill {signal} {target}"
                else:
                    cmd = f"pkill {signal} {target}"
            
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode == 0:
                return f"✅ Proceso terminado: {target}"
            else:
                error = result.stderr.strip() or result.stdout.strip()
                return f"❌ No se pudo terminar: {target}\n{error}"
                
        except subprocess.TimeoutExpired:
            return f"[x] Timeout intentando terminar: {target}"
        except Exception as e:
            return f"[x] Error: {e}"


class NetworkInfoTool(BaseTool):
    """Información de red"""
    
    name = "network_info"
    description = "Muestra información de red: IP, conexiones activas, etc."
    category = "system"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "show_connections": ToolParameter(
                name="show_connections",
                type="boolean",
                description="Mostrar conexiones activas",
                required=False
            )
        }
    
    def execute(self, show_connections: bool = False, **kwargs) -> str:
        show_connections = kwargs.get('show_connections', show_connections)
        
        output = "🌐 **Información de Red:**\n\n"
        
        try:
            # Hostname
            hostname = socket.gethostname()
            output += f"  **Hostname:** {hostname}\n"
            
            # IP local
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                output += f"  **IP Local:** {local_ip}\n"
            except:
                output += "  **IP Local:** No disponible\n"
            
            # IPs del hostname
            try:
                ips = socket.gethostbyname_ex(hostname)[2]
                if ips:
                    output += f"  **IPs asociadas:** {', '.join(ips)}\n"
            except:
                pass
            
            if show_connections:
                output += "\n**Conexiones activas:**\n```\n"
                
                if platform.system() == "Windows":
                    cmd = "netstat -an | findstr ESTABLISHED"
                else:
                    cmd = "netstat -an | grep ESTABLISHED | head -20"
                
                try:
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, 
                        text=True, timeout=5
                    )
                    connections = result.stdout.strip()
                    if connections:
                        output += connections[:1500]
                    else:
                        output += "(Sin conexiones activas)"
                except:
                    output += "(No se pudieron obtener conexiones)"
                
                output += "\n```"
            
            return output
            
        except Exception as e:
            return f"[x] Error: {e}"