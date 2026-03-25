"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         HERRAMIENTAS DE IA - v2.0                              ║
║                    Consulta múltiples modelos con robustez                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import requests
import time
import json
import re
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass
from datetime import datetime

from .base import BaseTool, ToolParameter
from config import API_KEY, API_BASE_URL
from models.registry import AVAILABLE_MODELS, ModelRegistry


# ═══════════════════════════════════════════════════════════════════════════════
# CLASES DE UTILIDAD
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AIResponse:
    """Estructura de respuesta de IA"""
    success: bool
    model_name: str
    model_key: str
    content: Optional[str] = None
    error: Optional[str] = None
    response_time: float = 0.0
    tokens_used: int = 0
    
    def to_formatted_string(self) -> str:
        """Convierte a string formateado"""
        if self.success and self.content:
            header = f"🤖 **{self.model_name}**"
            if self.response_time > 0:
                header += f" ⏱️ {self.response_time:.1f}s"
            if self.tokens_used > 0:
                header += f" 📝 {self.tokens_used} tokens"
            
            return f"{header}\n\n{self.content}"
        else:
            return f"❌ **{self.model_name}**: {self.error or 'Error desconocido'}"


class AIRequestValidator:
    """Validador de solicitudes de IA"""
    
    @staticmethod
    def validate_api_config() -> Tuple[bool, Optional[str]]:
        """Valida la configuración de API"""
        if not API_KEY:
            return False, "API_KEY no configurada en config.py"
        
        if not API_BASE_URL:
            return False, "API_BASE_URL no configurada en config.py"
        
        if not API_KEY.strip():
            return False, "API_KEY está vacía"
        
        if not API_BASE_URL.startswith(('http://', 'https://')):
            return False, f"API_BASE_URL inválida: {API_BASE_URL}"
        
        return True, None
    
    @staticmethod
    def validate_prompt(prompt: str) -> Tuple[bool, Optional[str]]:
        """Valida el prompt"""
        if not prompt:
            return False, "Prompt vacío"
        
        if len(prompt.strip()) < 2:
            return False, "Prompt demasiado corto"
        
        if len(prompt) > 100000:
            return False, "Prompt demasiado largo (máx 100k caracteres)"
        
        return True, None


class ResponseProcessor:
    """Procesador de respuestas de IA"""
    
    @staticmethod
    def clean_thinking_tags(text: str) -> str:
        """Limpia tags de pensamiento"""
        if not text:
            return text
        
        # Patrones comunes de tags de pensamiento
        patterns = [
            r'<think>.*?</think>',
            r'<thinking>.*?</thinking>',
            r'<thought>.*?</thought>',
            r'<internal>.*?</internal>',
            r'\[\[.*?\]\]',  # Tags estilo [[pensamiento]]
        ]
        
        cleaned = text
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        
        # Limpiar espacios extra
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned if cleaned else text
    
    @staticmethod
    def extract_response_content(data: Dict[str, Any]) -> Tuple[Optional[str], Optional[int]]:
        """Extrae contenido de la respuesta de API"""
        # Intentar diferentes estructuras de respuesta
        content = None
        tokens = 0
        
        # Estructura estándar OpenAI
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            
            # Obtener contenido
            if "message" in choice and "content" in choice["message"]:
                content = choice["message"]["content"]
            elif "text" in choice:
                content = choice["text"]
            
            # Obtener tokens
            if "usage" in data:
                tokens = data["usage"].get("total_tokens", 0)
        
        # Estructura alternativa
        elif "response" in data:
            content = data["response"]
        elif "output" in data:
            content = data["output"]
        elif "text" in data:
            content = data["text"]
        
        return content, tokens


# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTA PRINCIPAL: ConsultAITool
# ═══════════════════════════════════════════════════════════════════════════════

class ConsultAITool(BaseTool):
    """Consulta otro modelo de IA con manejo robusto de errores"""
    
    name = "consult_ai"
    description = "Consulta otro modelo de IA para obtener una perspectiva diferente o especializada"
    category = "ai"
    
    def __init__(self):
        super().__init__()
        self.validator = AIRequestValidator()
        self.processor = ResponseProcessor()
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "model_key": ToolParameter(
                name="model_key",
                type="string",
                description="Clave del modelo (1-18) o ID completo del modelo",
                required=True
            ),
            "prompt": ToolParameter(
                name="prompt",
                type="string",
                description="Pregunta o tarea para el modelo",
                required=True
            ),
            "context": ToolParameter(
                name="context",
                type="string",
                description="Contexto adicional para la consulta",
                required=False
            ),
            "max_tokens": ToolParameter(
                name="max_tokens",
                type="integer",
                description="Máximo de tokens en la respuesta (default: 4096)",
                required=False
            ),
            "temperature": ToolParameter(
                name="temperature",
                type="number",
                description="Creatividad de la respuesta (0.0-2.0, default: 0.7)",
                required=False
            ),
            "retry_on_error": ToolParameter(
                name="retry_on_error",
                type="boolean",
                description="Reintentar si hay error (default: True)",
                required=False
            )
        }
    
    def execute(
        self, 
        model_key: str, 
        prompt: str, 
        context: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        retry_on_error: bool = True,
        **kwargs
    ) -> str:
        """Ejecuta consulta a modelo de IA"""
        
        # Validar configuración
        valid, error = self.validator.validate_api_config()
        if not valid:
            return f"❌ Error de configuración: {error}"
        
        # Validar prompt
        valid, error = self.validator.validate_prompt(prompt)
        if not valid:
            return f"❌ Prompt inválido: {error}"
        
        # Obtener modelo
        registry = ModelRegistry()
        model = registry.get(model_key)
        
        if not model:
            available = "\n".join([f"  {k}: {v.name}" for k, v in AVAILABLE_MODELS.items()])
            return f"❌ Modelo no encontrado: {model_key}\n\nModelos disponibles:\n{available}"
        
        # Intentar consulta (con retry opcional)
        max_attempts = 2 if retry_on_error else 1
        
        for attempt in range(1, max_attempts + 1):
            result = self._query_model(
                model=model,
                prompt=prompt,
                context=context,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            if result.success:
                return result.to_formatted_string()
            
            # Si es el último intento, devolver error
            if attempt == max_attempts:
                return result.to_formatted_string()
            
            # Esperar antes de reintentar
            time.sleep(1)
        
        return "❌ Error inesperado en consulta"
    
    def _query_model(
        self,
        model,
        prompt: str,
        context: str,
        max_tokens: int,
        temperature: float
    ) -> AIResponse:
        """Realiza la consulta al modelo"""
        
        start_time = time.time()
        
        try:
            # Construir mensajes
            messages = []
            if context:
                messages.append({"role": "system", "content": context})
            messages.append({"role": "user", "content": prompt})
            
            # Headers
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "NVIDIA-Code/2.0"
            }
            
            # Payload
            payload = {
                "model": model.id,
                "messages": messages,
                "max_tokens": min(max_tokens, 8192),  # Límite máximo
                "temperature": max(0.0, min(2.0, temperature))  # Clamp entre 0 y 2
            }
            
            # Añadir opciones específicas del modelo
            if model.thinking:
                payload["chat_template_kwargs"] = {"thinking": True}
            
            # Timeout adaptativo basado en max_tokens
            timeout = max(30, min(300, max_tokens // 20))
            
            # Realizar solicitud
            response = requests.post(
                API_BASE_URL,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            # Procesar respuesta
            data = response.json()
            content, tokens = self.processor.extract_response_content(data)
            
            if not content:
                return AIResponse(
                    success=False,
                    model_name=model.name,
                    model_key=str(model.key),
                    error="Respuesta vacía del modelo"
                )
            
            # Limpiar contenido
            content = self.processor.clean_thinking_tags(content)
            
            if not content.strip():
                return AIResponse(
                    success=False,
                    model_name=model.name,
                    model_key=str(model.key),
                    error="Respuesta vacía después de limpieza"
                )
            
            # Añadir especialidad del modelo si existe
            if model.specialty:
                content = f"{model.specialty}\n\n{content}"
            
            return AIResponse(
                success=True,
                model_name=model.name,
                model_key=str(model.key),
                content=content,
                response_time=time.time() - start_time,
                tokens_used=tokens
            )
            
        except requests.exceptions.Timeout:
            return AIResponse(
                success=False,
                model_name=model.name,
                model_key=str(model.key),
                error=f"Timeout después de {timeout}s"
            )
        
        except requests.exceptions.HTTPError as e:
            error_msg = self._format_http_error(e)
            return AIResponse(
                success=False,
                model_name=model.name,
                model_key=str(model.key),
                error=error_msg
            )
        
        except requests.exceptions.ConnectionError:
            return AIResponse(
                success=False,
                model_name=model.name,
                model_key=str(model.key),
                error="Error de conexión. Verifica tu internet"
            )
        
        except json.JSONDecodeError:
            return AIResponse(
                success=False,
                model_name=model.name,
                model_key=str(model.key),
                error="Respuesta no es JSON válido"
            )
        
        except Exception as e:
            return AIResponse(
                success=False,
                model_name=model.name,
                model_key=str(model.key),
                error=f"Error: {str(e)[:200]}"
            )
    
    def _format_http_error(self, error: requests.exceptions.HTTPError) -> str:
        """Formatea errores HTTP de manera legible"""
        if not error.response:
            return "Error HTTP sin respuesta"
        
        status = error.response.status_code
        
        error_messages = {
            400: "Solicitud inválida",
            401: "API_KEY inválida o expirada",
            403: "Acceso denegado a este modelo",
            404: "Modelo no encontrado en la API",
            429: "Límite de rate excedido. Espera un momento",
            500: "Error interno del servidor",
            502: "Gateway error",
            503: "Servicio no disponible"
        }
        
        base_msg = error_messages.get(status, f"Error HTTP {status}")
        
        # Intentar obtener detalles del error
        try:
            error_data = error.response.json()
            if "error" in error_data:
                if isinstance(error_data["error"], dict):
                    detail = error_data["error"].get("message", "")
                else:
                    detail = str(error_data["error"])
                
                if detail:
                    base_msg += f": {detail[:100]}"
        except:
            pass
        
        return base_msg


# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTA MÚLTIPLE: MultiAIConsultTool
# ═══════════════════════════════════════════════════════════════════════════════

class MultiAIConsultTool(BaseTool):
    """Consulta múltiples modelos de IA simultáneamente con comparación"""
    
    name = "consult_multiple_ai"
    description = "Consulta múltiples modelos de IA y compara sus respuestas"
    category = "ai"
    
    def __init__(self):
        super().__init__()
        self.consult_tool = ConsultAITool()
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "prompt": ToolParameter(
                name="prompt",
                type="string",
                description="Pregunta o tarea para los modelos",
                required=True
            ),
            "models": ToolParameter(
                name="models",
                type="array",
                description="Lista de claves de modelos a consultar (default: top 3)",
                required=False
            ),
            "context": ToolParameter(
                name="context",
                type="string",
                description="Contexto adicional para todos los modelos",
                required=False
            ),
            "compare_mode": ToolParameter(
                name="compare_mode",
                type="string",
                description="Modo de comparación: full, summary, consensus",
                required=False,
                enum=["full", "summary", "consensus"]
            )
        }
    
    def execute(
        self,
        prompt: str,
        models: List[str] = None,
        context: str = "",
        compare_mode: str = "full",
        **kwargs
    ) -> str:
        """Ejecuta consultas múltiples"""
        
        # Validar prompt
        validator = AIRequestValidator()
        valid, error = validator.validate_prompt(prompt)
        if not valid:
            return f"❌ Prompt inválido: {error}"
        
        # Modelos por defecto
        if not models:
            models = ["1", "2", "4"]  # Kimi, DeepSeek, Nemotron
        
        # Limitar cantidad de modelos
        if len(models) > 5:
            models = models[:5]
            note = "\n⚠️ Limitado a 5 modelos para evitar sobrecarga\n"
        else:
            note = ""
        
        # Ejecutar consultas en paralelo
        results = self._parallel_query(prompt, models, context)
        
        # Formatear según modo
        if compare_mode == "summary":
            output = self._format_summary(prompt, results)
        elif compare_mode == "consensus":
            output = self._format_consensus(prompt, results)
        else:
            output = self._format_full(prompt, results)
        
        return note + output
    
    def _parallel_query(
        self,
        prompt: str,
        models: List[str],
        context: str
    ) -> List[AIResponse]:
        """Ejecuta consultas en paralelo"""
        
        results = []
        registry = ModelRegistry()
        
        def query_single(model_key: str) -> AIResponse:
            """Consulta un modelo individual"""
            model = registry.get(model_key)
            if not model:
                return AIResponse(
                    success=False,
                    model_name=f"Modelo {model_key}",
                    model_key=model_key,
                    error="Modelo no encontrado"
                )
            
            return self.consult_tool._query_model(
                model=model,
                prompt=prompt,
                context=context,
                max_tokens=2048,  # Reducido para múltiples consultas
                temperature=0.7
            )
        
        # Ejecutar en paralelo con timeout global
        with ThreadPoolExecutor(max_workers=min(3, len(models))) as executor:
            futures = {executor.submit(query_single, m): m for m in models}
            
            for future in as_completed(futures, timeout=60):
                try:
                    result = future.result()
                    results.append(result)
                except TimeoutError:
                    model_key = futures[future]
                    results.append(AIResponse(
                        success=False,
                        model_name=f"Modelo {model_key}",
                        model_key=model_key,
                        error="Timeout"
                    ))
                except Exception as e:
                    model_key = futures[future]
                    results.append(AIResponse(
                        success=False,
                        model_name=f"Modelo {model_key}",
                        model_key=model_key,
                        error=str(e)[:100]
                    ))
        
        return results
    
    def _format_full(self, prompt: str, results: List[AIResponse]) -> str:
        """Formato completo con todas las respuestas"""
        
        output = "🔄 **Consulta Multi-IA**\n\n"
        output += f"📝 **Prompt:** {prompt[:200]}{'...' if len(prompt) > 200 else ''}\n\n"
        
        # Estadísticas
        successful = sum(1 for r in results if r.success)
        total_time = sum(r.response_time for r in results)
        
        output += f"📊 **Estadísticas:** {successful}/{len(results)} exitosas"
        if total_time > 0:
            output += f" | ⏱️ {total_time:.1f}s total"
        output += "\n\n"
        
        output += "═" * 60 + "\n\n"
        
        # Respuestas individuales
        for result in results:
            output += result.to_formatted_string()
            output += "\n\n" + "─" * 60 + "\n\n"
        
        return output
    
    def _format_summary(self, prompt: str, results: List[AIResponse]) -> str:
        """Formato resumido con respuestas principales"""
        
        output = "📋 **Resumen Multi-IA**\n\n"
        output += f"**Prompt:** {prompt[:100]}...\n\n"
        
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        if successful:
            output += f"✅ **Respuestas exitosas ({len(successful)}):**\n\n"
            for result in successful:
                # Solo primeras líneas
                content_preview = result.content[:300] if result.content else ""
                if len(result.content or "") > 300:
                    content_preview += "..."
                
                output += f"**{result.model_name}:**\n{content_preview}\n\n"
        
        if failed:
            output += f"\n❌ **Fallos ({len(failed)}):**\n"
            for result in failed:
                output += f"• {result.model_name}: {result.error}\n"
        
        return output
    
    def _format_consensus(self, prompt: str, results: List[AIResponse]) -> str:
        """Formato de consenso identificando puntos comunes"""
        
        output = "🤝 **Análisis de Consenso Multi-IA**\n\n"
        output += f"**Prompt:** {prompt[:100]}...\n\n"
        
        successful = [r for r in results if r.success and r.content]
        
        if len(successful) < 2:
            return output + "⚠️ Se necesitan al menos 2 respuestas exitosas para consenso\n"
        
        # Análisis simple de palabras clave comunes
        all_contents = " ".join(r.content.lower() for r in successful)
        
        # Palabras clave (excluyendo palabras comunes)
        stop_words = {'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'por', 
                     'con', 'no', 'una', 'su', 'para', 'the', 'and', 'of', 'to', 
                     'in', 'is', 'it', 'that', 'for', 'on', 'with', 'as'}
        
        words = re.findall(r'\b\w{4,}\b', all_contents)
        word_freq = {}
        for word in words:
            if word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Top palabras comunes
        top_words = sorted(word_freq.items(), key=lambda x: -x[1])[:10]
        
        output += "**🔑 Temas comunes identificados:**\n"
        for word, freq in top_words:
            if freq > 1:  # Solo palabras que aparecen múltiples veces
                output += f"• {word.capitalize()} (mencionado {freq} veces)\n"
        
        output += f"\n**📊 Modelos consultados:** {', '.join(r.model_name for r in successful)}\n"
        
        # Mostrar snippet de cada respuesta
        output += "\n**📝 Extractos de respuestas:**\n\n"
        for result in successful:
            snippet = result.content[:150] + "..."
            output += f"_{result.model_name}_: {snippet}\n\n"
        
        return output


# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTA DE COMPARACIÓN: CompareModelsPerformanceTool
# ═══════════════════════════════════════════════════════════════════════════════

class CompareModelsPerformanceTool(BaseTool):
    """Compara el rendimiento de diferentes modelos con el mismo prompt"""
    
    name = "compare_models"
    description = "Compara velocidad y calidad de respuesta de múltiples modelos"
    category = "ai"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "prompt": ToolParameter(
                name="prompt",
                type="string",
                description="Prompt de prueba para todos los modelos",
                required=True
            ),
            "models": ToolParameter(
                name="models",
                type="array",
                description="Lista de modelos a comparar (default: todos rápidos)",
                required=False
            )
        }
    
    def execute(self, prompt: str, models: List[str] = None, **kwargs) -> str:
        """Ejecuta comparación de rendimiento"""
        
        if not models:
            # Modelos rápidos por defecto
            models = ["1", "2", "3", "5", "6"]
        
        multi_tool = MultiAIConsultTool()
        results = multi_tool._parallel_query(prompt, models, "")
        
        output = "📊 **Comparación de Modelos**\n\n"
        output += f"**Prompt de prueba:** {prompt[:100]}...\n\n"
        
        # Tabla de resultados
        output += "| Modelo | Estado | Tiempo | Tokens | Calidad |\n"
        output += "|--------|--------|--------|--------|----------|\n"
        
        for r in sorted(results, key=lambda x: x.response_time):
            status = "✅" if r.success else "❌"
            time_str = f"{r.response_time:.1f}s" if r.response_time > 0 else "N/A"
            tokens = str(r.tokens_used) if r.tokens_used > 0 else "N/A"
            
            # Estimación simple de calidad basada en longitud
            if r.success and r.content:
                quality = len(r.content)
                if quality > 1000:
                    quality_str = "⭐⭐⭐"
                elif quality > 500:
                    quality_str = "⭐⭐"
                else:
                    quality_str = "⭐"
            else:
                quality_str = "N/A"
            
            output += f"| {r.model_name[:15]:15} | {status:^6} | {time_str:>6} | {tokens:>6} | {quality_str:^8} |\n"
        
        # Ganadores
        successful = [r for r in results if r.success]
        if successful:
            fastest = min(successful, key=lambda x: x.response_time)
            output += f"\n🏆 **Más rápido:** {fastest.model_name} ({fastest.response_time:.1f}s)\n"
            
            if any(r.content for r in successful if r.content):
                longest = max(successful, key=lambda x: len(x.content or ""))
                output += f"📝 **Respuesta más detallada:** {longest.model_name} ({len(longest.content)} caracteres)\n"
        
        return output