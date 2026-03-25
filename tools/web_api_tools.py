# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS WEB & API
# WebSocket, GraphQL, Documentación, CORS, SSL
# ═══════════════════════════════════════════════════════════════════════════════

import json
import re
import ssl
import socket
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

from .base import BaseTool, ToolParameter

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False


class WebSocketTestTool(BaseTool):
    # Prueba conexiones WebSocket enviando y recibiendo mensajes.
    #
    # Útil para:
    # - Probar endpoints WebSocket
    # - Debugging de conexiones en tiempo real
    # - Verificar formato de mensajes
    # - Testing de chat/notificaciones
    
    name = "websocket_test"
    description = """Prueba conexiones WebSocket.

Conecta a un endpoint WebSocket, envía mensaje y muestra respuesta.

Ejemplos:
- Conexión básica: url="ws://localhost:8000/ws"
- Con mensaje: url="ws://...", message="hello"
- Con headers: url="wss://...", headers={"Authorization": "Bearer token"}

Soporta ws:// y wss:// (seguro)
"""
    category = "web"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "url": ToolParameter(
                name="url",
                type="string",
                description="URL del WebSocket (ws:// o wss://)",
                required=True
            ),
            "message": ToolParameter(
                name="message",
                type="string",
                description="Mensaje a enviar (opcional)",
                required=False
            ),
            "headers": ToolParameter(
                name="headers",
                type="object",
                description="Headers adicionales (JSON)",
                required=False
            ),
            "timeout": ToolParameter(
                name="timeout",
                type="integer",
                description="Timeout en segundos (default: 10)",
                required=False
            ),
            "wait_messages": ToolParameter(
                name="wait_messages",
                type="integer",
                description="Número de mensajes a esperar (default: 1)",
                required=False
            )
        }
    
    def execute(
        self,
        url: str = None,
        message: str = None,
        headers: Dict = None,
        timeout: int = 10,
        wait_messages: int = 1,
        **kwargs
    ) -> str:
        url = url or kwargs.get('url', '')
        message = message or kwargs.get('message', None)
        headers = headers or kwargs.get('headers', {})
        timeout = timeout or kwargs.get('timeout', 10)
        wait_messages = wait_messages or kwargs.get('wait_messages', 1)
        
        if not url:
            return "❌ Se requiere 'url'"
        
        if not url.startswith(('ws://', 'wss://')):
            return "❌ URL debe comenzar con ws:// o wss://"
        
        if not HAS_WEBSOCKET:
            # Fallback sin librería websocket
            return self._test_ws_basic(url, message, timeout)
        
        return self._test_ws_full(url, message, headers, timeout, wait_messages)
    
    def _test_ws_basic(self, url: str, message: str, timeout: int) -> str:
        # Test básico sin librería websocket-client
        import socket
        import base64
        import hashlib
        import os
        
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == 'wss' else 80)
        path = parsed.path or '/'
        
        try:
            # Crear socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            if parsed.scheme == 'wss':
                import ssl
                context = ssl.create_default_context()
                sock = context.wrap_socket(sock, server_hostname=host)
            
            sock.connect((host, port))
            
            # Handshake WebSocket
            key = base64.b64encode(os.urandom(16)).decode()
            handshake = f"GET {path} HTTP/1.1\r\n"
            handshake += f"Host: {host}\r\n"
            handshake += "Upgrade: websocket\r\n"
            handshake += "Connection: Upgrade\r\n"
            handshake += f"Sec-WebSocket-Key: {key}\r\n"
            handshake += "Sec-WebSocket-Version: 13\r\n"
            handshake += "\r\n"
            
            sock.send(handshake.encode())
            response = sock.recv(1024).decode()
            
            if "101" in response:
                result = f"""✅ **WebSocket Conectado**

| Propiedad | Valor |
|-----------|-------|
| URL | {url} |
| Host | {host}:{port} |
| Estado | Conectado (101 Switching Protocols) |

```
{response[:300]}
```
"""
                if message:
                    result += f"\n⚠️ Para enviar mensajes, instala: `pip install websocket-client`"
                
                return result
            else:
                return f"❌ Handshake fallido:\n```\n{response[:500]}\n```"
            
        except socket.timeout:
            return f"❌ Timeout conectando a {url}"
        except Exception as e:
            return f"❌ Error: {str(e)}"
        finally:
            try:
                sock.close()
            except:
                pass
    
    def _test_ws_full(self, url: str, message: str, headers: Dict, timeout: int, wait_messages: int) -> str:
        import time
        
        received_messages = []
        connected = False
        error_msg = None
        
        def on_message(ws, msg):
            received_messages.append({
                'time': datetime.now().isoformat(),
                'data': msg[:500]
            })
        
        def on_error(ws, error):
            nonlocal error_msg
            error_msg = str(error)
        
        def on_open(ws):
            nonlocal connected
            connected = True
            if message:
                ws.send(message)
        
        def on_close(ws, close_status, close_msg):
            pass
        
        try:
            ws = websocket.WebSocketApp(
                url,
                header=headers,
                on_message=on_message,
                on_error=on_error,
                on_open=on_open,
                on_close=on_close
            )
            
            import threading
            wst = threading.Thread(target=lambda: ws.run_forever(ping_interval=5))
            wst.daemon = True
            wst.start()
            
            # Esperar conexión
            start = time.time()
            while not connected and time.time() - start < timeout:
                if error_msg:
                    break
                time.sleep(0.1)
            
            if error_msg:
                return f"❌ Error WebSocket: {error_msg}"
            
            if not connected:
                return f"❌ Timeout esperando conexión ({timeout}s)"
            
            # Esperar mensajes
            while len(received_messages) < wait_messages and time.time() - start < timeout:
                time.sleep(0.1)
            
            ws.close()
            
            output = f"""✅ **WebSocket Test**

| Propiedad | Valor |
|-----------|-------|
| URL | `{url}` |
| Estado | Conectado |
| Mensaje enviado | {message if message else '(ninguno)'} |
| Mensajes recibidos | {len(received_messages)} |

"""
            
            if received_messages:
                output += "**📩 Mensajes Recibidos:**\n\n"
                for i, msg in enumerate(received_messages[:5], 1):
                    output += f"**{i}.** `{msg['time']}`\n```json\n{msg['data']}\n```\n\n"
            
            return output
            
        except Exception as e:
            return f"❌ Error: {str(e)}"


class GraphQLQueryTool(BaseTool):
    # Ejecuta consultas GraphQL contra un endpoint.
    #
    # Útil para:
    # - Probar APIs GraphQL
    # - Debugging de queries y mutations
    # - Explorar esquemas
    
    name = "graphql_query"
    description = """Ejecuta consultas GraphQL.

Soporta queries, mutations y variables.

Ejemplos:
- Query simple: endpoint="https://api.example.com/graphql", query="{ users { id name } }"
- Con variables: query="query($id: ID!) { user(id: $id) { name } }", variables={"id": "123"}
- Mutation: query="mutation { createUser(name: \"John\") { id } }"
"""
    category = "web"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "endpoint": ToolParameter(
                name="endpoint",
                type="string",
                description="URL del endpoint GraphQL",
                required=True
            ),
            "query": ToolParameter(
                name="query",
                type="string",
                description="Query o mutation GraphQL",
                required=True
            ),
            "variables": ToolParameter(
                name="variables",
                type="object",
                description="Variables para la query (JSON)",
                required=False
            ),
            "headers": ToolParameter(
                name="headers",
                type="object",
                description="Headers adicionales",
                required=False
            ),
            "operation_name": ToolParameter(
                name="operation_name",
                type="string",
                description="Nombre de la operación (si hay múltiples)",
                required=False
            )
        }
    
    def execute(
        self,
        endpoint: str = None,
        query: str = None,
        variables: Dict = None,
        headers: Dict = None,
        operation_name: str = None,
        **kwargs
    ) -> str:
        endpoint = endpoint or kwargs.get('endpoint', '')
        query = query or kwargs.get('query', '')
        variables = variables or kwargs.get('variables', {})
        headers = headers or kwargs.get('headers', {})
        operation_name = operation_name or kwargs.get('operation_name', None)
        
        if not endpoint or not query:
            return "❌ Se requieren 'endpoint' y 'query'"
        
        if not HAS_REQUESTS:
            return "❌ Instala requests: pip install requests"
        
        # Parsear variables si es string
        if isinstance(variables, str):
            try:
                variables = json.loads(variables)
            except:
                variables = {}
        
        # Construir payload
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name
        
        # Headers por defecto
        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        default_headers.update(headers)
        
        try:
            import time
            start = time.time()
            
            response = requests.post(
                endpoint,
                json=payload,
                headers=default_headers,
                timeout=30
            )
            
            elapsed = time.time() - start
            
            # Parsear respuesta
            try:
                data = response.json()
            except:
                return f"❌ Respuesta no es JSON válido:\n```\n{response.text[:500]}\n```"
            
            # Verificar errores GraphQL
            errors = data.get('errors', [])
            result_data = data.get('data', {})
            
            output = f"""📊 **GraphQL Response**

| Propiedad | Valor |
|-----------|-------|
| Endpoint | `{endpoint}` |
| Status | {response.status_code} |
| Tiempo | {elapsed*1000:.0f}ms |
| Errores | {len(errors)} |

"""
            
            if errors:
                output += "**❌ Errores:**\n```json\n"
                output += json.dumps(errors, indent=2)[:1000]
                output += "\n```\n\n"
            
            if result_data:
                output += "**📦 Data:**\n```json\n"
                output += json.dumps(result_data, indent=2, default=str)[:2000]
                output += "\n```"
            
            return output
            
        except requests.exceptions.Timeout:
            return "❌ Timeout (30s)"
        except Exception as e:
            return f"❌ Error: {str(e)}"


class APIDocGeneratorTool(BaseTool):
    # Genera documentación de API desde código Python.
    #
    # Analiza decoradores de FastAPI/Flask y genera OpenAPI/Swagger.
    
    name = "generate_api_docs"
    description = """Genera documentación de API desde código fuente.

Analiza código Python y extrae:
- Endpoints (rutas)
- Métodos HTTP
- Parámetros
- Modelos de datos

Soporta FastAPI y Flask.

Ejemplo: path="app/main.py", format="openapi"
Salida: Genera archivo swagger.json o markdown
"""
    category = "web"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(
                name="path",
                type="string",
                description="Archivo o directorio a analizar",
                required=True
            ),
            "format": ToolParameter(
                name="format",
                type="string",
                description="Formato: openapi, markdown, html",
                required=False,
                enum=["openapi", "markdown", "html"]
            ),
            "output": ToolParameter(
                name="output",
                type="string",
                description="Archivo de salida (opcional)",
                required=False
            ),
            "title": ToolParameter(
                name="title",
                type="string",
                description="Título de la API",
                required=False
            )
        }
    
    def execute(
        self,
        path: str = None,
        format: str = "markdown",
        output: str = None,
        title: str = "API Documentation",
        **kwargs
    ) -> str:
        path = path or kwargs.get('path', '')
        format = format or kwargs.get('format', 'markdown')
        output = output or kwargs.get('output', None)
        title = title or kwargs.get('title', 'API Documentation')
        
        if not path:
            return "❌ Se requieren 'path'"
        
        file_path = Path(path)
        if not file_path.exists():
            return f"❌ Archivo no existe: {path}"
        
        # Extraer endpoints
        endpoints = self._extract_endpoints(file_path)
        
        if not endpoints:
            return f"⚠️ No se encontraron endpoints en {path}"
        
        # Generar documentación
        if format == "openapi":
            doc = self._generate_openapi(endpoints, title)
            content = json.dumps(doc, indent=2)
            ext = ".json"
        elif format == "html":
            content = self._generate_html(endpoints, title)
            ext = ".html"
        else:
            content = self._generate_markdown(endpoints, title)
            ext = ".md"
        
        # Guardar si se especificó output
        if output:
            output_path = Path(output)
        else:
            output_path = file_path.with_suffix(ext)
        
        output_path.write_text(content)
        
        return f"""✅ **Documentación Generada**

| Propiedad | Valor |
|-----------|-------|
| Fuente | {path} |
| Endpoints | {len(endpoints)} |
| Formato | {format} |
| Salida | {output_path} |

**Endpoints encontrados:**
{self._list_endpoints(endpoints)}
"""
    
    def _extract_endpoints(self, path: Path) -> List[Dict]:
        endpoints = []
        
        if path.is_file():
            files = [path]
        else:
            files = list(path.rglob("*.py"))
        
        for file in files:
            try:
                content = file.read_text()
                
                # FastAPI patterns
                fastapi_pattern = r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
                for match in re.finditer(fastapi_pattern, content, re.IGNORECASE):
                    method, route = match.groups()
                    
                    # Buscar función después del decorador
                    func_match = re.search(
                        rf'{re.escape(match.group())}\s*\)\s*(?:async\s+)?def\s+(\w+)\s*\([^)]*\)',
                        content
                    )
                    func_name = func_match.group(1) if func_match else "unknown"
                    
                    # Buscar docstring
                    docstring = ""
                    if func_match:
                        doc_match = re.search(
                            rf'def\s+{func_name}\s*\([^)]*\)\s*(?:->.*?)?\s*:\s*(?:#[^\n]*)?\s*["\']{{3}}([^"\']+)',
                            content
                        )
                        if doc_match:
                            docstring = doc_match.group(1).strip()
                    
                    endpoints.append({
                        'method': method.upper(),
                        'route': route,
                        'function': func_name,
                        'description': docstring,
                        'file': str(file)
                    })
                
                # Flask patterns
                flask_pattern = r'@(?:app|bp|blueprint)\.(route)\s*\(\s*["\']([^"\']+)["\'](?:.*?methods\s*=\s*\[([^\]]+)\])?'
                for match in re.finditer(flask_pattern, content, re.IGNORECASE):
                    _, route, methods = match.groups()
                    methods = methods or '"GET"'
                    
                    for method in re.findall(r'["\'](\w+)["\']', methods):
                        endpoints.append({
                            'method': method.upper(),
                            'route': route,
                            'function': 'flask_handler',
                            'description': '',
                            'file': str(file)
                        })
                
            except Exception:
                continue
        
        return endpoints
    
    def _generate_markdown(self, endpoints: List[Dict], title: str) -> str:
        md = f"# {title}\n\n"
        md += f"Generated: {datetime.now().isoformat()}\n\n"
        md += "## Endpoints\n\n"
        
        # Agrupar por método
        by_method = {}
        for ep in endpoints:
            method = ep['method']
            if method not in by_method:
                by_method[method] = []
            by_method[method].append(ep)
        
        for method in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
            if method in by_method:
                md += f"### {method}\n\n"
                for ep in by_method[method]:
                    md += f"#### `{ep['route']}`\n\n"
                    if ep['description']:
                        md += f"{ep['description']}\n\n"
                    md += f"- **Function:** `{ep['function']}`\n"
                    md += f"- **File:** `{ep['file']}`\n\n"
        
        return md
    
    def _generate_openapi(self, endpoints: List[Dict], title: str) -> Dict:
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": title,
                "version": "1.0.0",
                "generated": datetime.now().isoformat()
            },
            "paths": {}
        }
        
        for ep in endpoints:
            route = ep['route']
            method = ep['method'].lower()
            
            if route not in spec['paths']:
                spec['paths'][route] = {}
            
            spec['paths'][route][method] = {
                "summary": ep['function'],
                "description": ep['description'],
                "responses": {
                    "200": {"description": "Success"}
                }
            }
        
        return spec
    
    def _generate_html(self, endpoints: List[Dict], title: str) -> str:
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .endpoint {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .get {{ border-left: 4px solid #61affe; }}
        .post {{ border-left: 4px solid #49cc90; }}
        .put {{ border-left: 4px solid #fca130; }}
        .delete {{ border-left: 4px solid #f93e3e; }}
        .method {{ font-weight: bold; padding: 5px 10px; border-radius: 3px; color: white; }}
        .method.get {{ background: #61affe; }}
        .method.post {{ background: #49cc90; }}
        .method.put {{ background: #fca130; }}
        .method.delete {{ background: #f93e3e; }}
        .route {{ font-family: monospace; font-size: 16px; margin-left: 10px; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p>Generated: {datetime.now().isoformat()}</p>
"""
        
        for ep in endpoints:
            method = ep['method'].lower()
            html += f"""
    <div class="endpoint {method}">
        <span class="method {method}">{ep['method']}</span>
        <span class="route">{ep['route']}</span>
        <p>{ep['description'] or ep['function']}</p>
    </div>
"""
        
        html += "</body></html>"
        return html
    
    def _list_endpoints(self, endpoints: List[Dict]) -> str:
        lines = []
        for ep in endpoints[:15]:
            lines.append(f"  {ep['method']:6} `{ep['route']}`")
        if len(endpoints) > 15:
            lines.append(f"  ... y {len(endpoints) - 15} más")
        return "\n".join(lines)


class CORSTestTool(BaseTool):
    # Prueba configuración CORS de una API.
    #
    # Verifica headers Access-Control-Allow-* para debugging de CORS.
    
    name = "test_cors"
    description = """Prueba configuración CORS de una URL.

Realiza preflight request (OPTIONS) y verifica:
- Access-Control-Allow-Origin
- Access-Control-Allow-Methods
- Access-Control-Allow-Headers
- Access-Control-Allow-Credentials

Útil para debuggear errores de CORS en desarrollo.

Ejemplo: url="https://api.example.com", origin="http://localhost:3000"
"""
    category = "web"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "url": ToolParameter(
                name="url",
                type="string",
                description="URL a probar",
                required=True
            ),
            "origin": ToolParameter(
                name="origin",
                type="string",
                description="Origin a simular (default: http://localhost:3000)",
                required=False
            ),
            "method": ToolParameter(
                name="method",
                type="string",
                description="Método a probar (default: GET)",
                required=False
            ),
            "headers": ToolParameter(
                name="headers",
                type="string",
                description="Headers a solicitar (comma-separated)",
                required=False
            )
        }
    
    def execute(
        self,
        url: str = None,
        origin: str = "http://localhost:3000",
        method: str = "GET",
        headers: str = "Content-Type, Authorization",
        **kwargs
    ) -> str:
        url = url or kwargs.get('url', '')
        origin = origin or kwargs.get('origin', 'http://localhost:3000')
        method = method or kwargs.get('method', 'GET')
        headers = headers or kwargs.get('headers', 'Content-Type, Authorization')
        
        if not url:
            return "❌ Se requiere 'url'"
        
        if not HAS_REQUESTS:
            return "❌ Instala requests: pip install requests"
        
        try:
            # Preflight request (OPTIONS)
            preflight_headers = {
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": headers
            }
            
            response = requests.options(url, headers=preflight_headers, timeout=10)
            
            # Extraer headers CORS
            cors_headers = {
                "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin", "❌ No presente"),
                "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods", "❌ No presente"),
                "Access-Control-Allow-Headers": response.headers.get("Access-Control-Allow-Headers", "❌ No presente"),
                "Access-Control-Allow-Credentials": response.headers.get("Access-Control-Allow-Credentials", "❌ No presente"),
                "Access-Control-Max-Age": response.headers.get("Access-Control-Max-Age", "No especificado"),
                "Access-Control-Expose-Headers": response.headers.get("Access-Control-Expose-Headers", "No especificado")
            }
            
            # Evaluar
            origin_ok = cors_headers["Access-Control-Allow-Origin"] in [origin, "*"]
            methods_ok = method in cors_headers.get("Access-Control-Allow-Methods", "")
            
            status = "✅ CORS Configurado" if origin_ok else "❌ CORS Bloqueado"
            
            output = f"""🌐 **CORS Test**

| Propiedad | Valor |
|-----------|-------|
| URL | `{url}` |
| Origin Probado | `{origin}` |
| Método Probado | `{method}` |
| Status HTTP | {response.status_code} |
| **Resultado** | **{status}** |

**Headers CORS:**

| Header | Valor |
|--------|-------|
"""
            for header, value in cors_headers.items():
                is_ok = "✅" if "❌" not in str(value) and value != "No especificado" else ""
                output += f"| {header} | {value} {is_ok} |\n"
            
            # Diagnóstico
            output += "\n**📋 Diagnóstico:**\n"
            
            if not origin_ok:
                output += f"- ❌ Origin `{origin}` no está permitido\n"
                output += f"  💡 El servidor debe incluir `Access-Control-Allow-Origin: {origin}` o `*`\n"
            else:
                output += f"- ✅ Origin `{origin}` permitido\n"
            
            if not methods_ok:
                output += f"- ❌ Método `{method}` no está en Allow-Methods\n"
            else:
                output += f"- ✅ Método `{method}` permitido\n"
            
            return output
            
        except requests.exceptions.Timeout:
            return "❌ Timeout"
        except Exception as e:
            return f"❌ Error: {str(e)}"


class SSLCertificateTool(BaseTool):
    # Obtiene información detallada de certificados SSL.
    #
    # Útil para verificar validez, emisor, expiración de certificados.
    
    name = "ssl_info"
    description = """Obtiene información de certificado SSL de un dominio.

Muestra:
- Validez del certificado
- Fecha de expiración
- Emisor (CA)
- Dominio y SANs
- Cadena de certificados

Ejemplo: domain="google.com"
Útil para verificar que los certificados están bien configurados.
"""
    category = "web"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "domain": ToolParameter(
                name="domain",
                type="string",
                description="Dominio a verificar",
                required=True
            ),
            "port": ToolParameter(
                name="port",
                type="integer",
                description="Puerto (default: 443)",
                required=False
            ),
            "check_chain": ToolParameter(
                name="check_chain",
                type="boolean",
                description="Verificar cadena completa (default: true)",
                required=False
            )
        }
    
    def execute(
        self,
        domain: str = None,
        port: int = 443,
        check_chain: bool = True,
        **kwargs
    ) -> str:
        domain = domain or kwargs.get('domain', '')
        port = port or kwargs.get('port', 443)
        check_chain = check_chain if check_chain is not None else kwargs.get('check_chain', True)
        
        if not domain:
            return "❌ Se requiere 'domain'"
        
        # Limpiar dominio
        domain = domain.replace('https://', '').replace('http://', '').split('/')[0]
        
        try:
            import ssl
            import socket
            from datetime import datetime
            
            context = ssl.create_default_context()
            
            with socket.create_connection((domain, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
            
            # Parsear fechas
            not_before = datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
            not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            
            days_left = (not_after - datetime.now()).days
            
            # Estado de expiración
            if days_left < 0:
                expiry_status = f"❌ EXPIRADO hace {-days_left} días"
            elif days_left < 30:
                expiry_status = f"⚠️ Expira en {days_left} días"
            else:
                expiry_status = f"✅ Válido ({days_left} días restantes)"
            
            # Subject y issuer
            subject = dict(x[0] for x in cert['subject'])
            issuer = dict(x[0] for x in cert['issuer'])
            
            # SANs
            sans = []
            for san_type, san_value in cert.get('subjectAltName', []):
                sans.append(san_value)
            
            output = f"""🔒 **Certificado SSL: {domain}**

**📋 Estado:**
| Propiedad | Valor |
|-----------|-------|
| Dominio | {subject.get('commonName', 'N/A')} |
| Estado | {expiry_status} |
| Versión TLS | {version} |
| Cipher | {cipher[0] if cipher else 'N/A'} |

**📅 Validez:**
| Fecha | Valor |
|-------|-------|
| Desde | {not_before.strftime('%Y-%m-%d %H:%M:%S')} |
| Hasta | {not_after.strftime('%Y-%m-%d %H:%M:%S')} |
| Días restantes | {days_left} |

**🏢 Emisor (CA):**
| Campo | Valor |
|-------|-------|
| Organización | {issuer.get('organizationName', 'N/A')} |
| Common Name | {issuer.get('commonName', 'N/A')} |
| País | {issuer.get('countryName', 'N/A')} |

**🌐 Subject Alternative Names (SANs):**
"""
            
            for san in sans[:10]:
                output += f"- {san}\n"
            
            if len(sans) > 10:
                output += f"- ... y {len(sans) - 10} más\n"
            
            # Verificar si el certificado es válido para el dominio
            if domain in sans or subject.get('commonName') == domain:
                output += f"\n✅ Certificado válido para `{domain}`"
            else:
                output += f"\n⚠️ El dominio `{domain}` podría no coincidir con el certificado"
            
            return output
            
        except ssl.SSLError as e:
            return f"❌ Error SSL: {str(e)}"
        except socket.timeout:
            return f"❌ Timeout conectando a {domain}:{port}"
        except socket.gaierror:
            return f"❌ No se puede resolver el dominio: {domain}"
        except Exception as e:
            return f"❌ Error: {str(e)}"
