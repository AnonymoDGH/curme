# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS DE TESTING AVANZADAS
# Cobertura de código y pruebas de carga
# ═══════════════════════════════════════════════════════════════════════════════

import subprocess
import time
import json
import re
import statistics
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .base import BaseTool, ToolParameter

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class CoverageReportTool(BaseTool):
    # Genera reportes de cobertura de código para tests.
    #
    # Útil para:
    # - Ver qué porcentaje del código está testeado
    # - Identificar archivos sin cobertura
    # - Generar reportes HTML visuales
    # - Tracking de calidad de tests
    
    name = "coverage_report"
    description = """Genera reporte de cobertura de tests.

Ejecuta tests con coverage y muestra:
- Porcentaje de cobertura por archivo
- Líneas cubiertas vs no cubiertas
- Reporte HTML opcional

Requiere: pip install coverage pytest

Ejemplos:
- Cobertura básica: (sin parámetros)
- Solo un módulo: source="src/mymodule"
- Generar HTML: html_report=true
"""
    category = "testing"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "source": ToolParameter(
                name="source",
                type="string",
                description="Directorio fuente a medir (default: .)",
                required=False
            ),
            "test_path": ToolParameter(
                name="test_path",
                type="string",
                description="Ruta de tests (default: tests/)",
                required=False
            ),
            "html_report": ToolParameter(
                name="html_report",
                type="boolean",
                description="Generar reporte HTML (default: false)",
                required=False
            ),
            "min_coverage": ToolParameter(
                name="min_coverage",
                type="integer",
                description="Cobertura mínima requerida en % (default: 0)",
                required=False
            ),
            "show_missing": ToolParameter(
                name="show_missing",
                type="boolean",
                description="Mostrar líneas no cubiertas (default: true)",
                required=False
            )
        }
    
    def execute(
        self,
        source: str = ".",
        test_path: str = "tests/",
        html_report: bool = False,
        min_coverage: int = 0,
        show_missing: bool = True,
        **kwargs
    ) -> str:
        source = source or kwargs.get('source', '.')
        test_path = test_path or kwargs.get('test_path', 'tests/')
        html_report = html_report or kwargs.get('html_report', False)
        min_coverage = min_coverage or kwargs.get('min_coverage', 0)
        show_missing = show_missing if show_missing is not None else kwargs.get('show_missing', True)
        
        # Verificar que coverage está instalado
        try:
            result = subprocess.run(
                ["coverage", "--version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return "❌ Coverage no instalado. Ejecuta: pip install coverage pytest"
        except FileNotFoundError:
            return "❌ Coverage no instalado. Ejecuta: pip install coverage pytest"
        except Exception as e:
            return f"❌ Error verificando coverage: {e}"
        
        output_parts = ["📊 **Reporte de Cobertura**\n"]
        
        # Ejecutar coverage
        try:
            # Limpiar datos anteriores
            subprocess.run(["coverage", "erase"], capture_output=True, timeout=30)
            
            # Ejecutar tests con coverage
            cmd = ["coverage", "run", f"--source={source}", "-m", "pytest", test_path, "-v"]
            output_parts.append(f"Ejecutando: `{' '.join(cmd)}`\n")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0 and "no tests ran" in result.stdout.lower():
                return f"⚠️ No se encontraron tests en {test_path}\n\n{result.stdout[:500]}"
            
            # Generar reporte
            report_cmd = ["coverage", "report"]
            if show_missing:
                report_cmd.append("--show-missing")
            
            report_result = subprocess.run(report_cmd, capture_output=True, text=True, timeout=60)
            
            if report_result.returncode == 0:
                output_parts.append("\n```")
                output_parts.append(report_result.stdout)
                output_parts.append("```\n")
                
                # Extraer porcentaje total
                total_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', report_result.stdout)
                if total_match:
                    total_coverage = int(total_match.group(1))
                    
                    if total_coverage >= 80:
                        status = "✅ Excelente"
                    elif total_coverage >= 60:
                        status = "🟡 Aceptable"
                    elif total_coverage >= 40:
                        status = "🟠 Bajo"
                    else:
                        status = "🔴 Crítico"
                    
                    output_parts.append(f"\n**Cobertura Total: {total_coverage}%** {status}\n")
                    
                    if min_coverage > 0 and total_coverage < min_coverage:
                        output_parts.append(f"\n❌ Cobertura por debajo del mínimo requerido ({min_coverage}%)")
            
            # Generar HTML si se solicitó
            if html_report:
                html_result = subprocess.run(
                    ["coverage", "html"],
                    capture_output=True, text=True, timeout=60
                )
                if html_result.returncode == 0:
                    output_parts.append("\n📁 Reporte HTML generado en: `htmlcov/index.html`")
            
            return "\n".join(output_parts)
            
        except subprocess.TimeoutExpired:
            return "❌ Timeout ejecutando tests (>5 minutos)"
        except Exception as e:
            return f"❌ Error: {str(e)}"


class LoadTestTool(BaseTool):
    # Ejecuta pruebas de carga contra URLs o APIs.
    #
    # Útil para:
    # - Medir rendimiento bajo carga
    # - Detectar cuellos de botella
    # - Verificar límites de concurrencia
    # - Benchmark de APIs
    
    name = "load_test"
    description = """Ejecuta pruebas de carga contra una URL.

Simula múltiples usuarios concurrentes y mide:
- Tiempo de respuesta (promedio, min, max, p95)
- Requests por segundo
- Tasa de errores
- Códigos de estado

Ejemplos:
- Test básico: url="http://localhost:8000/api/health"
- Con carga: url="...", users=50, duration=30
- POST con datos: url="...", method="POST", body='{"key": "value"}'
"""
    category = "testing"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "url": ToolParameter(
                name="url",
                type="string",
                description="URL a testear",
                required=True
            ),
            "users": ToolParameter(
                name="users",
                type="integer",
                description="Número de usuarios concurrentes (default: 10)",
                required=False
            ),
            "duration": ToolParameter(
                name="duration",
                type="integer",
                description="Duración en segundos (default: 10)",
                required=False
            ),
            "method": ToolParameter(
                name="method",
                type="string",
                description="Método HTTP (default: GET)",
                required=False,
                enum=["GET", "POST", "PUT", "DELETE", "PATCH"]
            ),
            "headers": ToolParameter(
                name="headers",
                type="object",
                description="Headers adicionales (JSON)",
                required=False
            ),
            "body": ToolParameter(
                name="body",
                type="string",
                description="Body para POST/PUT (JSON string)",
                required=False
            )
        }
    
    def execute(
        self,
        url: str = None,
        users: int = 10,
        duration: int = 10,
        method: str = "GET",
        headers: Dict = None,
        body: str = None,
        **kwargs
    ) -> str:
        url = url or kwargs.get('url', '')
        users = users or kwargs.get('users', 10)
        duration = min(duration or kwargs.get('duration', 10), 60)  # Max 60 segundos
        method = (method or kwargs.get('method', 'GET')).upper()
        headers = headers or kwargs.get('headers', {})
        body = body or kwargs.get('body', None)
        
        if not url:
            return "❌ Se requiere 'url'"
        
        if not HAS_REQUESTS:
            return "❌ Instala requests: pip install requests"
        
        # Parsear headers si es string
        if isinstance(headers, str):
            try:
                headers = json.loads(headers)
            except:
                headers = {}
        
        # Parsear body
        json_body = None
        if body:
            try:
                json_body = json.loads(body)
            except:
                pass
        
        print(f"🚀 Iniciando load test: {users} usuarios, {duration}s")
        print(f"   URL: {url}")
        print(f"   Método: {method}\n")
        
        # Resultados
        results = []
        errors = []
        status_codes = {}
        start_time = time.time()
        request_count = 0
        
        def make_request():
            nonlocal request_count
            try:
                req_start = time.time()
                
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_body if json_body else None,
                    data=body if not json_body and body else None,
                    timeout=30
                )
                
                req_duration = time.time() - req_start
                request_count += 1
                
                return {
                    'duration': req_duration,
                    'status': response.status_code,
                    'size': len(response.content),
                    'error': None
                }
            except Exception as e:
                return {
                    'duration': 0,
                    'status': 0,
                    'size': 0,
                    'error': str(e)[:50]
                }
        
        # Ejecutar load test
        with ThreadPoolExecutor(max_workers=users) as executor:
            futures = []
            
            while time.time() - start_time < duration:
                # Mantener N usuarios concurrentes
                while len([f for f in futures if not f.done()]) < users:
                    if time.time() - start_time >= duration:
                        break
                    futures.append(executor.submit(make_request))
                
                # Recolectar resultados completados
                for future in [f for f in futures if f.done()]:
                    try:
                        result = future.result()
                        if result['error']:
                            errors.append(result['error'])
                        else:
                            results.append(result)
                            status = result['status']
                            status_codes[status] = status_codes.get(status, 0) + 1
                    except:
                        pass
                    futures.remove(future)
                
                time.sleep(0.01)
            
            # Esperar los restantes
            for future in as_completed(futures, timeout=10):
                try:
                    result = future.result()
                    if result['error']:
                        errors.append(result['error'])
                    else:
                        results.append(result)
                        status = result['status']
                        status_codes[status] = status_codes.get(status, 0) + 1
                except:
                    pass
        
        actual_duration = time.time() - start_time
        
        # Calcular estadísticas
        if not results:
            return f"❌ No se completaron requests exitosos\n\nErrores ({len(errors)}):\n" + "\n".join(set(errors)[:5])
        
        durations = [r['duration'] * 1000 for r in results]  # En ms
        
        avg_time = statistics.mean(durations)
        min_time = min(durations)
        max_time = max(durations)
        p50 = statistics.median(durations)
        p95 = sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0]
        p99 = sorted(durations)[int(len(durations) * 0.99)] if len(durations) > 1 else durations[0]
        
        rps = len(results) / actual_duration
        error_rate = len(errors) / (len(results) + len(errors)) * 100 if errors else 0
        
        total_bytes = sum(r['size'] for r in results)
        
        # Status codes formateados
        status_str = " | ".join([f"{code}: {count}" for code, count in sorted(status_codes.items())])
        
        return f"""📊 **Resultados Load Test**

**🎯 Target:** `{url}`
**📋 Configuración:** {users} usuarios, {duration}s

---

**⏱️ Tiempos de Respuesta (ms):**
| Métrica | Valor |
|---------|-------|
| Promedio | {avg_time:.1f} ms |
| Mínimo | {min_time:.1f} ms |
| Máximo | {max_time:.1f} ms |
| P50 (mediana) | {p50:.1f} ms |
| P95 | {p95:.1f} ms |
| P99 | {p99:.1f} ms |

**📈 Rendimiento:**
| Métrica | Valor |
|---------|-------|
| Requests totales | {len(results) + len(errors)} |
| Requests exitosos | {len(results)} |
| Requests/segundo | {rps:.1f} |
| Datos transferidos | {total_bytes / 1024:.1f} KB |
| Tasa de error | {error_rate:.1f}% |

**📊 Códigos de Estado:**
{status_str}

**🏁 Evaluación:**
{self._evaluate_results(avg_time, error_rate, rps)}
"""
    
    def _evaluate_results(self, avg_time: float, error_rate: float, rps: float) -> str:
        evaluations = []
        
        if avg_time < 100:
            evaluations.append("✅ Tiempo de respuesta excelente (<100ms)")
        elif avg_time < 500:
            evaluations.append("🟡 Tiempo de respuesta aceptable (<500ms)")
        else:
            evaluations.append("🔴 Tiempo de respuesta alto (>500ms)")
        
        if error_rate == 0:
            evaluations.append("✅ Sin errores")
        elif error_rate < 1:
            evaluations.append("🟡 Tasa de error baja (<1%)")
        else:
            evaluations.append(f"🔴 Tasa de error alta ({error_rate:.1f}%)")
        
        if rps > 100:
            evaluations.append(f"✅ Alto throughput ({rps:.0f} req/s)")
        elif rps > 10:
            evaluations.append(f"🟡 Throughput moderado ({rps:.0f} req/s)")
        else:
            evaluations.append(f"🔴 Bajo throughput ({rps:.0f} req/s)")
        
        return "\n".join(evaluations)