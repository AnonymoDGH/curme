"""
NVIDIA CODE - Cliente API NVIDIA (COMPLETO Y CORREGIDO)
"""

import requests
import json
import time
import sys
import os
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from config import API_KEY, API_BASE_URL, MAX_TOKENS, TEMPERATURE, TOP_P
from models.registry import ModelInfo
from ui.colors import Colors
from ui.markdown import render_markdown
from ui.spinners import ThinkingSpinner

C = Colors()


def safe_print(text: str):
    """Imprime texto de forma segura en Windows"""
    try:
        print(text)
    except UnicodeEncodeError:
        replacements = {
            '╭': '+', '╮': '+', '╰': '+', '╯': '+',
            '│': '|', '─': '-', '═': '=',
            '├': '+', '┤': '+', '┌': '+', '┐': '+', '└': '+', '┘': '+',
            '●': '*', '✓': '[OK]', '✗': '[X]', '✅': '[OK]', '❌': '[X]',
            '🧠': '[B]', '💻': '[C]', '🚀': '[R]', '🔥': '[!]',
            '📄': '[F]', '📁': '[D]', '📝': '[E]', '⚡': '[>]',
            '🌐': '[W]', '🎯': '[T]', '✨': '[*]', '💭': '[T]',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        try:
            print(text.encode('ascii', 'replace').decode('ascii'))
        except:
            print(text.encode('ascii', 'ignore').decode('ascii'))


def clear_line():
    """Limpia la línea actual"""
    try:
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
    except:
        pass


@dataclass
class APIResponse:
    """Respuesta de la API"""
    content: str
    tool_calls: Optional[List[Dict]] = None
    thinking: Optional[str] = None
    reasoning: Optional[str] = None
    finish_reason: str = "stop"


class NVIDIAAPIClient:
    """Cliente para la API de NVIDIA"""
    
    def __init__(self, api_key: str = None, use_markdown: bool = True):
        self.api_key = api_key or API_KEY
        self.base_url = API_BASE_URL
        self.use_markdown = use_markdown
        
        # Verificar API key al iniciar
        if not self.api_key:
            safe_print(f"{C.RED}[!] API KEY no configurada{C.RESET}")
        elif not self.api_key.startswith("nvapi-"):
            safe_print(f"{C.YELLOW}[!] API KEY no parece válida (debe empezar con nvapi-){C.RESET}")
    
    def _get_timeout(self) -> int:
        """Obtiene el timeout desde la configuración"""
        try:
            from config import HEAVY_AGENT_CONFIG
            return HEAVY_AGENT_CONFIG.get("request_timeout", 120)
        except:
            return 120
    
    def _make_request(self, payload: Dict, stream: bool = False) -> requests.Response:
        """Realiza la petición HTTP"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        if stream:
            headers["Accept"] = "text/event-stream"
        
        return requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            stream=stream,
            timeout=self._get_timeout()
        )
    
    def chat(
        self,
        messages: List[Dict],
        model: ModelInfo,
        tools: List[Dict] = None,
        stream: bool = True,
        max_tokens: int = None,
        temperature: float = None,
    ) -> APIResponse:
        """Envia solicitud de chat"""
        
        # Validaciones
        if not self.api_key:
            return APIResponse(content="[Error] API KEY no configurada. Configura NVIDIA_API_KEY")
        
        if not model:
            return APIResponse(content="[Error] Modelo no especificado")
        
        payload = {
            "model": model.id,
            "messages": messages,
            "max_tokens": max_tokens or model.max_tokens or MAX_TOKENS,
            "temperature": temperature or model.temperature or TEMPERATURE,
            "top_p": model.top_p or TOP_P,
            "stream": stream,
        }
        
        if tools and model.supports_tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        if model.extra_body:
            for key, value in model.extra_body.items():
                payload[key] = value
        elif model.thinking:
            if model.thinking_key == "enable_thinking":
                payload["chat_template_kwargs"] = {"enable_thinking": True}
            else:
                payload["chat_template_kwargs"] = {"thinking": True}
        
        try:
            response = self._make_request(payload, stream=stream)
            
            # Verificar código de estado
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_body = response.text[:300]
                    if error_body:
                        error_msg += f": {error_body}"
                except:
                    pass
                return APIResponse(content=f"[Error] {error_msg}")
            
            if stream:
                return self._process_stream(response, model)
            else:
                return self._process_response(response.json(), model)
                
        except requests.exceptions.Timeout:
            return APIResponse(content=f"[Error] Timeout - El servidor no respondio en {self._get_timeout()}s")
        except requests.exceptions.ConnectionError:
            return APIResponse(content="[Error] Sin conexion - Verifica tu internet")
        except requests.exceptions.RequestException as e:
            return APIResponse(content=f"[Error] Peticion fallida: {str(e)[:100]}")
        except Exception as e:
            return APIResponse(content=f"[Error] {type(e).__name__}: {str(e)[:100]}")
    
    def _process_stream(self, response, model: ModelInfo) -> APIResponse:
        """Procesa respuesta en streaming"""
        full_content = ""
        tool_calls = []
        thinking_content = ""
        reasoning_content = ""
        in_thinking = False
        in_reasoning = False
        header_printed = False
        buffer = ""
        active_spinner = None
        
        try:
            for line in response.iter_lines():
                if not line:
                    continue
                
                try:
                    line_str = line.decode('utf-8')
                except UnicodeDecodeError:
                    # Intentar con diferentes encodings
                    try:
                        line_str = line.decode('latin-1')
                    except:
                        continue
                
                if not line_str.startswith('data: '):
                    continue
                
                data = line_str[6:]
                if data == '[DONE]':
                    break
                
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                
                choices = chunk.get('choices')
                if not choices or len(choices) == 0:
                    continue
                
                delta = choices[0].get('delta', {})
                if not delta:
                    continue
                
                # REASONING CONTENT (GLM, Nemotron)
                if model.reasoning_content:
                    reasoning = delta.get('reasoning_content')
                    if reasoning:
                        if not in_reasoning:
                            in_reasoning = True
                            if active_spinner:
                                active_spinner.stop()
                                clear_line()
                            active_spinner = ThinkingSpinner(
                                message=f"{model.name} razonando",
                                color=C.BRIGHT_MAGENTA
                            )
                            active_spinner.start()
                        reasoning_content += reasoning
                        continue
                    else:
                        if in_reasoning and active_spinner:
                            active_spinner.stop()
                            active_spinner = None
                            clear_line()
                            in_reasoning = False
                
                # CONTENIDO NORMAL
                content = delta.get('content')
                if content:
                    # Detectar thinking tags
                    if '<think>' in content:
                        in_thinking = True
                        if active_spinner:
                            active_spinner.stop()
                            clear_line()
                        active_spinner = ThinkingSpinner(
                            message=f"{model.name} pensando",
                            color=C.BRIGHT_MAGENTA
                        )
                        active_spinner.start()
                        content = content.replace('<think>', '')
                    
                    if '</think>' in content:
                        in_thinking = False
                        if active_spinner:
                            active_spinner.stop()
                            active_spinner = None
                            clear_line()
                        content = content.replace('</think>', '')
                    
                    if in_thinking:
                        thinking_content += content
                        continue
                    
                    # Asegurar que spinner está detenido
                    if active_spinner:
                        active_spinner.stop()
                        active_spinner = None
                        clear_line()
                    
                    # Imprimir header solo una vez
                    if not header_printed and content.strip():
                        header_printed = True
                        header_len = max(1, 40 - len(model.name))
                        safe_print(f"\n{C.NVIDIA_GREEN}╭─ {model.name} {model.specialty} {'─' * header_len}╮{C.RESET}")
                        safe_print(f"{C.NVIDIA_GREEN}│{C.RESET}")
                    
                    full_content += content
                    buffer += content
                    
                    # Renderizar líneas completas
                    if '\n' in buffer:
                        lines = buffer.split('\n')
                        for ln in lines[:-1]:
                            self._print_content_line(ln)
                        buffer = lines[-1]
                
                # TOOL CALLS
                tc_delta = delta.get('tool_calls')
                if tc_delta and isinstance(tc_delta, list):
                    for tc in tc_delta:
                        if not isinstance(tc, dict):
                            continue
                        
                        idx = tc.get('index', 0)
                        
                        while len(tool_calls) <= idx:
                            tool_calls.append({
                                'id': '',
                                'type': 'function',
                                'function': {'name': '', 'arguments': ''}
                            })
                        
                        if tc.get('id'):
                            tool_calls[idx]['id'] = tc['id']
                        
                        func = tc.get('function', {})
                        if isinstance(func, dict):
                            if func.get('name'):
                                tool_calls[idx]['function']['name'] = func['name']
                            if func.get('arguments'):
                                tool_calls[idx]['function']['arguments'] += func['arguments']
            
            # FINALIZACIÓN
            if active_spinner:
                active_spinner.stop()
                clear_line()
            
            # Renderizar buffer restante
            if buffer.strip() and header_printed:
                for ln in buffer.split('\n'):
                    if ln.strip():
                        self._print_content_line(ln)
            
            # Footer
            if header_printed:
                safe_print(f"{C.NVIDIA_GREEN}│{C.RESET}")
                safe_print(f"{C.NVIDIA_GREEN}╰{'─' * 50}╯{C.RESET}\n")
            
            # Si no hubo contenido, mostrar mensaje
            if not full_content and not tool_calls:
                return APIResponse(content="[Error] El modelo no genero respuesta")
            
        except requests.exceptions.Timeout:
            if active_spinner:
                active_spinner.stop()
                clear_line()
            error_msg = f"[Error] Timeout en streaming después de {self._get_timeout()}s"
            safe_print(f"\n{C.RED}{error_msg}{C.RESET}")
            if full_content:
                return APIResponse(content=full_content)
            return APIResponse(content=error_msg)
        except requests.exceptions.ConnectionError:
            if active_spinner:
                active_spinner.stop()
                clear_line()
            error_msg = "[Error] Pérdida de conexión durante streaming"
            safe_print(f"\n{C.RED}{error_msg}{C.RESET}")
            if full_content:
                return APIResponse(content=full_content)
            return APIResponse(content=error_msg)
        except Exception as e:
            if active_spinner:
                active_spinner.stop()
                clear_line()
            error_msg = f"[Error en streaming] {type(e).__name__}: {str(e)[:200]}"
            safe_print(f"\n{C.RED}{error_msg}{C.RESET}")
            if full_content:
                return APIResponse(content=full_content)
            return APIResponse(content=error_msg)
        
        valid_tool_calls = [
            tc for tc in tool_calls 
            if tc.get('id') and tc.get('function', {}).get('name')
        ]
        
        return APIResponse(
            content=full_content,
            tool_calls=valid_tool_calls if valid_tool_calls else None,
            thinking=thinking_content if thinking_content else None,
            reasoning=reasoning_content if reasoning_content else None
        )
    
    def _print_content_line(self, line: str):
        """Imprime una línea de contenido con formato"""
        if self.use_markdown and line.strip():
            try:
                rendered = render_markdown(line)
                safe_print(f"{C.NVIDIA_GREEN}│{C.RESET} {rendered}")
            except:
                safe_print(f"{C.NVIDIA_GREEN}│{C.RESET} {line}")
        elif line.strip():
            safe_print(f"{C.NVIDIA_GREEN}│{C.RESET} {line}")
        else:
            safe_print(f"{C.NVIDIA_GREEN}│{C.RESET}")
    
    def _process_response(self, data: Dict, model: ModelInfo) -> APIResponse:
        """Procesa respuesta sin streaming"""
        try:
            if not data:
                return APIResponse(content="[Error] Respuesta JSON vacia")
            
            # Verificar si hay error en la respuesta
            if 'error' in data:
                error_info = data['error']
                if isinstance(error_info, dict):
                    msg = error_info.get('message', str(error_info))
                else:
                    msg = str(error_info)
                return APIResponse(content=f"[Error API] {msg[:200]}")
            
            choices = data.get('choices', [])
            if not choices or len(choices) == 0:
                return APIResponse(content="[Error] Respuesta sin choices")
            
            message = choices[0].get('message', {})
            content = message.get('content', '')
            tool_calls = message.get('tool_calls')
            
            if content and '<think>' in content:
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            if tool_calls and isinstance(tool_calls, list):
                valid_tc = [
                    tc for tc in tool_calls 
                    if isinstance(tc, dict) and tc.get('id') and tc.get('function', {}).get('name')
                ]
                tool_calls = valid_tc if valid_tc else None
            else:
                tool_calls = None
            
            if not content and not tool_calls:
                return APIResponse(content="[Error] Respuesta sin contenido")
            
            return APIResponse(
                content=content or "",
                tool_calls=tool_calls,
                finish_reason=choices[0].get('finish_reason', 'stop')
            )
        except Exception as e:
            return APIResponse(content=f"[Error] Procesando respuesta: {str(e)}")
    
    def chat_simple(
        self,
        prompt: str,
        model: ModelInfo,
        system: str = None,
        max_tokens: int = 4096
    ) -> str:
        """Chat simple sin streaming - retorna string"""
        
        # Validaciones
        if not prompt:
            return "[Error] Prompt vacio"
        if not model:
            return "[Error] Modelo no especificado"
        if not self.api_key:
            return "[Error] API KEY no configurada"
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model.id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": model.temperature or TEMPERATURE,
            "top_p": model.top_p or TOP_P,
            "stream": False
        }
        
        if model.extra_body:
            for key, value in model.extra_body.items():
                payload[key] = value
        elif model.thinking:
            if model.thinking_key == "enable_thinking":
                payload["chat_template_kwargs"] = {"enable_thinking": True}
            else:
                payload["chat_template_kwargs"] = {"thinking": True}
        
        timeout = self._get_timeout()
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            # Verificar código de estado ANTES de parsear JSON
            if response.status_code != 200:
                error_detail = ""
                try:
                    error_detail = response.text[:200]
                except:
                    pass
                return f"[Error HTTP {response.status_code}] {error_detail}"
            
            # Parsear JSON
            try:
                data = response.json()
            except json.JSONDecodeError:
                return "[Error] Respuesta no es JSON valido"
            
            if not data:
                return "[Error] Respuesta vacia"
            
            # Verificar error en respuesta
            if 'error' in data:
                error_info = data['error']
                if isinstance(error_info, dict):
                    return f"[Error API] {error_info.get('message', str(error_info))[:150]}"
                return f"[Error API] {str(error_info)[:150]}"
            
            choices = data.get('choices', [])
            if not choices:
                return "[Error] Sin choices en respuesta"
            
            content = choices[0].get('message', {}).get('content', '')
            
            if not content:
                return "[Error] Contenido vacio"
            
            # Limpiar thinking tags
            if '<think>' in content:
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            return content if content else "[Error] Sin contenido despues de limpiar"
            
        except requests.exceptions.Timeout:
            return f"[Error] Timeout ({timeout}s) - Servidor no responde"
        except requests.exceptions.ConnectionError:
            return "[Error] Sin conexion a internet"
        except requests.exceptions.RequestException as e:
            return f"[Error] Request fallido: {str(e)[:80]}"
        except Exception as e:
            return f"[Error] {type(e).__name__}: {str(e)[:80]}"
    
    def test_connection(self, model: ModelInfo = None) -> Dict[str, Any]:
        """Prueba la conexión con un modelo"""
        if model is None:
            from models.registry import get_model
            model = get_model("1")
        
        if not model:
            return {"success": False, "error": "Modelo no encontrado"}
        
        start_time = time.time()
        result = self.chat_simple(
            prompt="Responde unicamente con la palabra: FUNCIONANDO",
            model=model,
            max_tokens=50
        )
        elapsed = time.time() - start_time
        
        # Verificar si es error
        is_error = result.startswith("[Error")
        
        return {
            "success": not is_error,
            "model": model.name,
            "model_id": model.id,
            "response": result[:150],
            "time_seconds": round(elapsed, 2),
            "error": result if is_error else None
        }