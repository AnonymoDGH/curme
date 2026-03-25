# tools/http_tools.py
"""
NVIDIA CODE - Cliente HTTP y API Tester
"""

import json
import time
from typing import Dict, Any
from urllib.parse import urljoin

from .base import BaseTool, ToolParameter

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class HTTPRequestTool(BaseTool):
    """Realiza peticiones HTTP"""
    
    name = "http_request"
    description = "Realiza peticiones HTTP (GET, POST, PUT, DELETE) a APIs"
    category = "http"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "url": ToolParameter(name="url", type="string", description="URL del endpoint", required=True),
            "method": ToolParameter(name="method", type="string", description="Método HTTP", required=False, enum=["GET", "POST", "PUT", "DELETE", "PATCH"]),
            "headers": ToolParameter(name="headers", type="object", description="Headers como JSON", required=False),
            "body": ToolParameter(name="body", type="string", description="Body de la petición (JSON)", required=False),
            "timeout": ToolParameter(name="timeout", type="integer", description="Timeout en segundos", required=False)
        }
    
    def execute(self, url: str = None, method: str = "GET", headers: Dict = None, body: str = None, timeout: int = 30, **kwargs) -> str:
        url = url or kwargs.get('url', '')
        method = (method or kwargs.get('method', 'GET')).upper()
        headers = headers or kwargs.get('headers', {})
        body = body or kwargs.get('body', None)
        timeout = timeout or kwargs.get('timeout', 30)
        
        if not HAS_REQUESTS:
            return "[x] Módulo 'requests' no instalado. Ejecuta: pip install requests"
        
        if not url:
            return "[x] Se requiere 'url'"
        
        from ui.colors import Colors
        C = Colors()
        
        # Preparar headers
        if isinstance(headers, str):
            try:
                headers = json.loads(headers)
            except:
                headers = {}
        
        # Preparar body
        json_body = None
        if body:
            try:
                json_body = json.loads(body)
            except:
                pass
        
        print(f"{C.BRIGHT_CYAN}🌐 {method} {url}{C.RESET}")
        
        start_time = time.time()
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=json_body if json_body else None,
                data=body if not json_body and body else None,
                timeout=timeout
            )
            
            elapsed = time.time() - start_time
            
            # Formatear respuesta
            output = f"""
{C.NVIDIA_GREEN}╭─ HTTP Response {'─' * 35}╮{C.RESET}
{C.NVIDIA_GREEN}│{C.RESET} Status: {self._status_color(response.status_code)}{response.status_code} {response.reason}{C.RESET}
{C.NVIDIA_GREEN}│{C.RESET} Time:   {elapsed*1000:.0f}ms
{C.NVIDIA_GREEN}│{C.RESET} Size:   {len(response.content):,} bytes
{C.NVIDIA_GREEN}├─ Headers {'─' * 40}┤{C.RESET}"""
            
            for key, value in list(response.headers.items())[:8]:
                output += f"\n{C.NVIDIA_GREEN}│{C.RESET} {C.DIM}{key}: {value[:40]}{C.RESET}"
            
            output += f"\n{C.NVIDIA_GREEN}├─ Body {'─' * 43}┤{C.RESET}"
            
            # Intentar formatear como JSON
            try:
                json_response = response.json()
                formatted = json.dumps(json_response, indent=2, ensure_ascii=False)
                for line in formatted.split('\n')[:30]:
                    output += f"\n{C.NVIDIA_GREEN}│{C.RESET} {line}"
                if len(formatted.split('\n')) > 30:
                    output += f"\n{C.NVIDIA_GREEN}│{C.RESET} {C.DIM}... (truncado){C.RESET}"
            except:
                text = response.text[:1000]
                for line in text.split('\n')[:20]:
                    output += f"\n{C.NVIDIA_GREEN}│{C.RESET} {line[:60]}"
            
            output += f"\n{C.NVIDIA_GREEN}╰{'─' * 50}╯{C.RESET}"
            
            return output
            
        except requests.exceptions.Timeout:
            return f"[x] Timeout después de {timeout}s"
        except requests.exceptions.ConnectionError as e:
            return f"[x] Error de conexión: {e}"
        except Exception as e:
            return f"[x] Error: {e}"
    
    def _status_color(self, code: int) -> str:
        from ui.colors import Colors
        C = Colors()
        if code < 300:
            return C.BRIGHT_GREEN
        elif code < 400:
            return C.BRIGHT_YELLOW
        elif code < 500:
            return C.BRIGHT_RED
        else:
            return C.RED