
"""
NVIDIA CODE - Herramientas Web Avanzadas
Sistema completo de web scraping, búsqueda y análisis
"""

import re
import json
import time
import hashlib
from typing import Dict, Optional, List, Any, Tuple
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote_plus, unquote
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import subprocess
import base64

from .base import BaseTool, ToolParameter

# Dependencias opcionales
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    import html2text
    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False


# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES Y HELPERS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CacheEntry:
    """Entrada de caché para URLs"""
    content: str
    timestamp: datetime
    headers: Dict[str, str] = field(default_factory=dict)
    status_code: int = 200


class WebCache:
    """Caché simple para evitar requests repetidos"""
    
    def __init__(self, max_age_minutes: int = 30, max_entries: int = 100):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_age = timedelta(minutes=max_age_minutes)
        self.max_entries = max_entries
    
    def _hash_key(self, url: str, method: str = "GET", data: str = None) -> str:
        """Genera clave única para caché"""
        key = f"{method}:{url}:{data or ''}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def get(self, url: str, method: str = "GET", data: str = None) -> Optional[CacheEntry]:
        """Obtiene entrada de caché si existe y no expiró"""
        key = self._hash_key(url, method, data)
        
        if key in self.cache:
            entry = self.cache[key]
            if datetime.now() - entry.timestamp < self.max_age:
                return entry
            else:
                del self.cache[key]
        
        return None
    
    def set(self, url: str, content: str, headers: Dict = None, 
            status_code: int = 200, method: str = "GET", data: str = None):
        """Guarda en caché"""
        # Limpiar si excede límite
        if len(self.cache) >= self.max_entries:
            oldest_key = min(self.cache, key=lambda k: self.cache[k].timestamp)
            del self.cache[oldest_key]
        
        key = self._hash_key(url, method, data)
        self.cache[key] = CacheEntry(
            content=content,
            timestamp=datetime.now(),
            headers=headers or {},
            status_code=status_code
        )
    
    def clear(self):
        """Limpia todo el caché"""
        self.cache.clear()


# Caché global
_web_cache = WebCache()


class RateLimiter:
    """Rate limiter simple por dominio"""
    
    def __init__(self, requests_per_second: float = 2.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request: Dict[str, float] = {}
    
    def wait(self, domain: str):
        """Espera si es necesario antes de hacer request"""
        now = time.time()
        
        if domain in self.last_request:
            elapsed = now - self.last_request[domain]
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
        
        self.last_request[domain] = time.time()


# Rate limiter global
_rate_limiter = RateLimiter()


def get_session() -> 'requests.Session':
    """Crea una sesión de requests con reintentos"""
    if not HAS_REQUESTS:
        return None
    
    session = requests.Session()
    
    # Configurar reintentos
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def clean_html_to_text(html: str) -> str:
    """Convierte HTML a texto limpio"""
    if HAS_HTML2TEXT:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_emphasis = False
        h.body_width = 0
        return h.handle(html)
    
    if HAS_BS4:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remover scripts y styles
        for tag in soup(['script', 'style', 'noscript', 'header', 'footer', 'nav']):
            tag.decompose()
        
        return soup.get_text(separator='\n', strip=True)
    
    # Fallback con regex
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'\s+', ' ', html).strip()
    
    # Decodificar entidades HTML
    entities = {
        '&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>',
        '&quot;': '"', '&#39;': "'", '&apos;': "'",
        '&copy;': '©', '&reg;': '®', '&trade;': '™',
        '&mdash;': '—', '&ndash;': '–', '&hellip;': '…',
    }
    for entity, char in entities.items():
        html = html.replace(entity, char)
    
    return html


def extract_json_from_html(html: str) -> List[Dict]:
    """Extrae datos JSON embebidos en HTML (JSON-LD, scripts, etc.)"""
    json_data = []
    
    # JSON-LD
    json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    for match in re.finditer(json_ld_pattern, html, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(match.group(1))
            json_data.append({"type": "json-ld", "data": data})
        except:
            pass
    
    # Next.js __NEXT_DATA__
    next_pattern = r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>'
    for match in re.finditer(next_pattern, html, re.DOTALL):
        try:
            data = json.loads(match.group(1))
            json_data.append({"type": "next-data", "data": data})
        except:
            pass
    
    # Nuxt.js __NUXT__
    nuxt_pattern = r'window\.__NUXT__\s*=\s*(\{.*?\});?\s*</script>'
    for match in re.finditer(nuxt_pattern, html, re.DOTALL):
        try:
            # Nuxt usa JS, no JSON puro, intentar extraer
            data = match.group(1)
            json_data.append({"type": "nuxt-data", "data": data[:500]})
        except:
            pass
    
    # Buscar objetos JSON en scripts
    script_pattern = r'<script[^>]*>(.*?)</script>'
    for match in re.finditer(script_pattern, html, re.DOTALL):
        script = match.group(1)
        
        # Buscar asignaciones de objetos
        obj_pattern = r'(?:var|let|const)\s+(\w+)\s*=\s*(\{[^;]+\});'
        for obj_match in re.finditer(obj_pattern, script):
            try:
                var_name = obj_match.group(1)
                obj_str = obj_match.group(2)
                # Intentar parsear (puede fallar si no es JSON válido)
                if '"' in obj_str or "'" in obj_str:
                    data = json.loads(obj_str.replace("'", '"'))
                    json_data.append({"type": "script-var", "name": var_name, "data": data})
            except:
                pass
    
    return json_data


def extract_links(html: str, base_url: str) -> List[Dict[str, str]]:
    """Extrae todos los enlaces de una página"""
    links = []
    
    if HAS_BS4:
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            
            # Convertir a URL absoluta
            full_url = urljoin(base_url, href)
            
            links.append({
                "text": text[:100] if text else "",
                "url": full_url,
                "original_href": href
            })
    else:
        # Fallback con regex
        pattern = r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>([^<]*)</a>'
        for match in re.finditer(pattern, html, re.IGNORECASE):
            href, text = match.groups()
            full_url = urljoin(base_url, href)
            links.append({
                "text": text.strip()[:100],
                "url": full_url,
                "original_href": href
            })
    
    return links


def extract_meta_info(html: str) -> Dict[str, str]:
    """Extrae meta información de la página"""
    meta = {}
    
    # Title
    title_match = re.search(r'<title[^>]*>([^<]*)</title>', html, re.IGNORECASE)
    if title_match:
        meta['title'] = title_match.group(1).strip()
    
    # Meta tags
    meta_pattern = r'<meta[^>]*(?:name|property)=["\']([^"\']*)["\'][^>]*content=["\']([^"\']*)["\'][^>]*>'
    for match in re.finditer(meta_pattern, html, re.IGNORECASE):
        name, content = match.groups()
        meta[name.lower()] = content
    
    # También buscar el formato inverso (content primero)
    meta_pattern2 = r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*(?:name|property)=["\']([^"\']*)["\'][^>]*>'
    for match in re.finditer(meta_pattern2, html, re.IGNORECASE):
        content, name = match.groups()
        meta[name.lower()] = content
    
    return meta


# ══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS PRINCIPALES
# ══════════════════════════════════════════════════════════════════════════════

class WebScrapeTool(BaseTool):
    """Extrae contenido de páginas web con capacidades avanzadas"""
    
    name = "web_scrape"
    description = """Extrae contenido de páginas web. Puede obtener texto, links, datos JSON embebidos, y meta información.
    Soporta JavaScript rendering con Playwright si está instalado.
    Modos: 'text' (por defecto), 'full' (todo), 'links', 'json', 'raw'"""
    category = "web"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "url": ToolParameter(
                name="url", 
                type="string", 
                description="URL de la página a scrapear", 
                required=True
            ),
            "mode": ToolParameter(
                name="mode", 
                type="string", 
                description="Modo: 'text', 'full', 'links', 'json', 'raw', 'api'",
                required=False,
                enum=["text", "full", "links", "json", "raw", "api"]
            ),
            "selector": ToolParameter(
                name="selector", 
                type="string", 
                description="Selector CSS para extraer solo esa parte (requiere BeautifulSoup)",
                required=False
            ),
            "use_js": ToolParameter(
                name="use_js", 
                type="boolean", 
                description="Usar navegador para JavaScript (requiere Playwright)",
                required=False
            ),
            "wait_for": ToolParameter(
                name="wait_for", 
                type="string", 
                description="Selector CSS a esperar si use_js=true",
                required=False
            ),
            "max_length": ToolParameter(
                name="max_length",
                type="integer",
                description="Longitud máxima del contenido (default: 15000)",
                required=False
            ),
            "use_cache": ToolParameter(
                name="use_cache",
                type="boolean",
                description="Usar caché para evitar requests repetidos (default: true)",
                required=False
            )
        }
    
    def _fetch_with_requests(self, url: str, headers: Dict = None) -> Tuple[str, int, Dict]:
        """Fetch usando requests"""
        if not HAS_REQUESTS:
            raise Exception("requests no está instalado")
        
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        if headers:
            default_headers.update(headers)
        
        session = get_session()
        response = session.get(url, headers=default_headers, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        return response.text, response.status_code, dict(response.headers)
    
    def _fetch_with_playwright(self, url: str, wait_for: str = None, timeout: int = 30000) -> str:
        """Fetch usando Playwright para JavaScript"""
        if not HAS_PLAYWRIGHT:
            raise Exception("Playwright no está instalado. Instala con: pip install playwright && playwright install chromium")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = context.new_page()
            
            try:
                page.goto(url, wait_until='networkidle', timeout=timeout)
                
                if wait_for:
                    page.wait_for_selector(wait_for, timeout=timeout)
                
                # Scroll para cargar lazy content
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
                
                html = page.content()
                
            finally:
                browser.close()
            
            return html
    
    def _extract_with_selector(self, html: str, selector: str) -> str:
        """Extrae contenido usando selector CSS"""
        if not HAS_BS4:
            return f"[!] BeautifulSoup requerido para selectores CSS. Instalalo con: pip install beautifulsoup4"
        
        soup = BeautifulSoup(html, 'html.parser')
        elements = soup.select(selector)
        
        if not elements:
            return f"[!] No se encontraron elementos con selector: {selector}"
        
        texts = []
        for el in elements:
            texts.append(el.get_text(separator='\n', strip=True))
        
        return '\n\n---\n\n'.join(texts)
    
    def execute(self, url: str = None, mode: str = "text", selector: str = None,
                use_js: bool = False, wait_for: str = None, max_length: int = 15000,
                use_cache: bool = True, **kwargs) -> str:
        
        # Manejar kwargs para compatibilidad
        url = url or kwargs.get('url', '')
        mode = mode or kwargs.get('mode', 'text')
        selector = selector or kwargs.get('selector')
        use_js = use_js or kwargs.get('use_js', False)
        wait_for = wait_for or kwargs.get('wait_for')
        max_length = max_length or kwargs.get('max_length', 15000)
        use_cache = use_cache if use_cache is not None else kwargs.get('use_cache', True)
        
        if not url:
            return "[x] Se requiere 'url'"
        
        # Validar URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        parsed = urlparse(url)
        domain = parsed.netloc
        
        try:
            # Verificar caché
            if use_cache and not use_js:
                cached = _web_cache.get(url)
                if cached:
                    html = cached.content
                    from_cache = True
                else:
                    from_cache = False
            else:
                from_cache = False
            
            if not from_cache:
                # Rate limiting
                _rate_limiter.wait(domain)
                
                # Fetch contenido
                if use_js:
                    if not HAS_PLAYWRIGHT:
                        return """[x] Playwright no instalado. Para sitios con JavaScript, instala:
```bash
pip install playwright
playwright install chromium
```

Alternativamente, usa mode='api' para intentar encontrar la API del sitio."""
                    
                    html = self._fetch_with_playwright(url, wait_for)
                    status_code = 200
                    headers = {}
                else:
                    html, status_code, headers = self._fetch_with_requests(url)
                
                # Guardar en caché
                if use_cache:
                    _web_cache.set(url, html, headers, status_code)
            
            # Procesar según modo
            result_parts = [f"🌐 **{url}**"]
            
            if from_cache:
                result_parts.append(f"📦 *(desde caché)*\n")
            else:
                result_parts.append("")
            
            # Aplicar selector si existe
            if selector:
                content = self._extract_with_selector(html, selector)
                result_parts.append(f"**Selector:** `{selector}`\n")
                result_parts.append(content)
                
            elif mode == "raw":
                # HTML sin procesar
                if len(html) > max_length:
                    html = html[:max_length] + "\n... (truncado)"
                result_parts.append(f"```html\n{html}\n```")
                
            elif mode == "links":
                # Solo enlaces
                links = extract_links(html, url)
                result_parts.append(f"**Enlaces encontrados:** {len(links)}\n")
                
                for i, link in enumerate(links[:50], 1):
                    if link['text']:
                        result_parts.append(f"{i}. [{link['text']}]({link['url']})")
                    else:
                        result_parts.append(f"{i}. {link['url']}")
                
                if len(links) > 50:
                    result_parts.append(f"\n... y {len(links) - 50} enlaces más")
                    
            elif mode == "json":
                # Datos JSON embebidos
                json_data = extract_json_from_html(html)
                
                if not json_data:
                    result_parts.append("*No se encontraron datos JSON embebidos*")
                else:
                    result_parts.append(f"**Datos JSON encontrados:** {len(json_data)}\n")
                    
                    for i, item in enumerate(json_data, 1):
                        result_parts.append(f"### {i}. Tipo: {item['type']}")
                        data_str = json.dumps(item['data'], indent=2, ensure_ascii=False)
                        if len(data_str) > 2000:
                            data_str = data_str[:2000] + "\n... (truncado)"
                        result_parts.append(f"```json\n{data_str}\n```")
                        
            elif mode == "api":
                # Intentar descubrir API
                result_parts.append("**🔍 Buscando APIs y datos estructurados...**\n")
                
                # Buscar endpoints API en el HTML
                api_patterns = [
                    r'["\']([^"\']*api[^"\']*)["\']',
                    r'fetch\(["\']([^"\']+)["\']',
                    r'axios\.[a-z]+\(["\']([^"\']+)["\']',
                    r'\.get\(["\']([^"\']+)["\']',
                    r'\.post\(["\']([^"\']+)["\']',
                    r'endpoint["\s:]+["\']([^"\']+)["\']',
                    r'url["\s:]+["\']([^"\']+)["\']',
                ]
                
                found_apis = set()
                for pattern in api_patterns:
                    for match in re.finditer(pattern, html, re.IGNORECASE):
                        endpoint = match.group(1)
                        if endpoint.startswith('/') or 'api' in endpoint.lower():
                            full_url = urljoin(url, endpoint)
                            found_apis.add(full_url)
                
                if found_apis:
                    result_parts.append("**Posibles endpoints API:**")
                    for api_url in list(found_apis)[:20]:
                        result_parts.append(f"• `{api_url}`")
                
                # JSON embebido
                json_data = extract_json_from_html(html)
                if json_data:
                    result_parts.append(f"\n**Datos JSON embebidos:** {len(json_data)}")
                    for item in json_data[:3]:
                        data_str = json.dumps(item['data'], indent=2, ensure_ascii=False)
                        if len(data_str) > 1000:
                            data_str = data_str[:1000] + "..."
                        result_parts.append(f"\n*{item['type']}:*\n```json\n{data_str}\n```")
                
            elif mode == "full":
                # Todo: meta, texto, links
                meta = extract_meta_info(html)
                text = clean_html_to_text(html)
                links = extract_links(html, url)
                
                # Meta información
                if meta:
                    result_parts.append("### 📋 Meta Información")
                    for key, value in list(meta.items())[:10]:
                        result_parts.append(f"• **{key}:** {value[:100]}")
                    result_parts.append("")
                
                # Contenido principal
                result_parts.append("### 📄 Contenido")
                if len(text) > max_length:
                    text = text[:max_length] + "\n\n... (truncado)"
                result_parts.append(text)
                
                # Links relevantes
                result_parts.append(f"\n### 🔗 Enlaces ({len(links)} encontrados)")
                for link in links[:20]:
                    if link['text']:
                        result_parts.append(f"• [{link['text'][:50]}]({link['url']})")
                
            else:  # mode == "text" (default)
                # Solo texto limpio
                text = clean_html_to_text(html)
                
                if len(text) > max_length:
                    text = text[:max_length] + "\n\n... (contenido truncado, usa max_length mayor si necesitas más)"
                
                result_parts.append(text)
            
            return '\n'.join(result_parts)
            
        except Exception as e:
            error_msg = str(e)
            
            # Sugerencias útiles según el error
            suggestions = []
            
            if "SSLError" in error_msg or "SSL" in error_msg:
                suggestions.append("Intenta con http:// en lugar de https://")
            
            if "Timeout" in error_msg:
                suggestions.append("El sitio es lento, intenta de nuevo")
            
            if "403" in error_msg or "Forbidden" in error_msg:
                suggestions.append("El sitio bloquea bots, usa use_js=true para Playwright")
            
            if "404" in error_msg:
                suggestions.append("Página no encontrada, verifica la URL")
            
            if "Connection" in error_msg:
                suggestions.append("Error de conexión, verifica tu internet")
            
            result = f"[x] Error scrapeando {url}: {error_msg}"
            
            if suggestions:
                result += "\n\n💡 **Sugerencias:**\n"
                for s in suggestions:
                    result += f"• {s}\n"
            
            return result


class WebSearchTool(BaseTool):
    """Búsqueda web avanzada con múltiples motores"""
    
    name = "web_search"
    description = """Busca información en internet. Soporta múltiples motores:
    - duckduckgo (default): Sin tracking, buenos resultados
    - google: Requiere scraping, puede bloquearse
    - bing: Alternativa estable
    - brave: Motor de búsqueda privado
    
    También puede buscar en sitios específicos con 'site:example.com query'"""
    category = "web"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "query": ToolParameter(
                name="query", 
                type="string", 
                description="Término de búsqueda. Usa 'site:domain.com' para buscar en sitio específico",
                required=True
            ),
            "engine": ToolParameter(
                name="engine",
                type="string",
                description="Motor de búsqueda: duckduckgo, google, bing, brave",
                required=False,
                enum=["duckduckgo", "google", "bing", "brave"]
            ),
            "num_results": ToolParameter(
                name="num_results", 
                type="integer", 
                description="Número de resultados (default: 10, max: 30)",
                required=False
            ),
            "fetch_content": ToolParameter(
                name="fetch_content",
                type="boolean",
                description="Si true, también descarga el contenido de cada resultado",
                required=False
            ),
            "region": ToolParameter(
                name="region",
                type="string",
                description="Región para resultados (ej: 'es-ES', 'en-US')",
                required=False
            )
        }
    
    def _search_duckduckgo(self, query: str, num_results: int) -> List[Dict]:
        """Búsqueda en DuckDuckGo"""
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        }
        
        session = get_session()
        response = session.get(url, headers=headers, timeout=15)
        html = response.text
        
        results = []
        
        if HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            
            for result in soup.select('.result'):
                title_el = result.select_one('.result__title a')
                snippet_el = result.select_one('.result__snippet')
                
                if title_el:
                    href = title_el.get('href', '')
                    
                    # DuckDuckGo redirige, extraer URL real
                    if 'uddg=' in href:
                        actual_url = re.search(r'uddg=([^&]*)', href)
                        if actual_url:
                            href = unquote(actual_url.group(1))
                    
                    results.append({
                        'title': title_el.get_text(strip=True),
                        'url': href,
                        'snippet': snippet_el.get_text(strip=True) if snippet_el else ''
                    })
                    
                    if len(results) >= num_results:
                        break
        else:
            # Fallback con regex
            pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
            for match in re.finditer(pattern, html):
                href, title = match.groups()
                
                if 'uddg=' in href:
                    actual_url = re.search(r'uddg=([^&]*)', href)
                    if actual_url:
                        href = unquote(actual_url.group(1))
                
                results.append({
                    'title': title.strip(),
                    'url': href,
                    'snippet': ''
                })
                
                if len(results) >= num_results:
                    break
        
        return results
    
    def _search_bing(self, query: str, num_results: int) -> List[Dict]:
        """Búsqueda en Bing"""
        url = f"https://www.bing.com/search?q={quote_plus(query)}&count={num_results}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        session = get_session()
        response = session.get(url, headers=headers, timeout=15)
        html = response.text
        
        results = []
        
        if HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            
            for item in soup.select('.b_algo'):
                title_el = item.select_one('h2 a')
                snippet_el = item.select_one('.b_caption p')
                
                if title_el:
                    results.append({
                        'title': title_el.get_text(strip=True),
                        'url': title_el.get('href', ''),
                        'snippet': snippet_el.get_text(strip=True) if snippet_el else ''
                    })
                    
                    if len(results) >= num_results:
                        break
        
        return results
    
    def _search_brave(self, query: str, num_results: int) -> List[Dict]:
        """Búsqueda en Brave Search"""
        url = f"https://search.brave.com/search?q={quote_plus(query)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        session = get_session()
        response = session.get(url, headers=headers, timeout=15)
        html = response.text
        
        results = []
        
        if HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            
            for item in soup.select('.snippet'):
                title_el = item.select_one('.title')
                url_el = item.select_one('a')
                snippet_el = item.select_one('.snippet-description')
                
                if title_el and url_el:
                    results.append({
                        'title': title_el.get_text(strip=True),
                        'url': url_el.get('href', ''),
                        'snippet': snippet_el.get_text(strip=True) if snippet_el else ''
                    })
                    
                    if len(results) >= num_results:
                        break
        
        return results
    
    def execute(self, query: str = None, engine: str = "duckduckgo", 
                num_results: int = 10, fetch_content: bool = False,
                region: str = None, **kwargs) -> str:
        
        query = query or kwargs.get('query', '')
        engine = engine or kwargs.get('engine', 'duckduckgo')
        num_results = min(num_results or kwargs.get('num_results', 10), 30)
        fetch_content = fetch_content or kwargs.get('fetch_content', False)
        
        if not query:
            return "[x] Se requiere 'query'"
        
        if not HAS_REQUESTS:
            return "[x] Instala requests: pip install requests"
        
        try:
            # Rate limiting
            _rate_limiter.wait(f"{engine}.search")
            
            # Ejecutar búsqueda
            search_methods = {
                'duckduckgo': self._search_duckduckgo,
                'bing': self._search_bing,
                'brave': self._search_brave,
            }
            
            search_fn = search_methods.get(engine, self._search_duckduckgo)
            results = search_fn(query, num_results)
            
            if not results:
                return f"🔍 Sin resultados para: **{query}**\n\n💡 Intenta con otros términos o motor de búsqueda"
            
            # Formatear output
            output_parts = [f"🔍 **Resultados para '{query}'** ({engine})\n"]
            
            for i, r in enumerate(results, 1):
                output_parts.append(f"### {i}. {r['title']}")
                output_parts.append(f"🔗 {r['url']}")
                
                if r.get('snippet'):
                    output_parts.append(f"_{r['snippet']}_")
                
                output_parts.append("")
            
            # Opcionalmente, descargar contenido de cada resultado
            if fetch_content:
                output_parts.append("\n---\n## 📄 Contenido de los resultados\n")
                
                scraper = WebScrapeTool()
                
                for i, r in enumerate(results[:5], 1):  # Limitar a 5 para no abusar
                    output_parts.append(f"### Resultado {i}: {r['title']}")
                    
                    try:
                        content = scraper.execute(url=r['url'], mode='text', max_length=3000)
                        output_parts.append(content)
                    except Exception as e:
                        output_parts.append(f"*Error obteniendo contenido: {e}*")
                    
                    output_parts.append("\n---\n")
            
            return '\n'.join(output_parts)
            
        except Exception as e:
            return f"[x] Error buscando: {e}"


class APIRequestTool(BaseTool):
    """Realiza requests HTTP a APIs"""
    
    name = "http_request"
    description = """Realiza requests HTTP a cualquier API o endpoint.
    Soporta GET, POST, PUT, DELETE, PATCH.
    Puede enviar JSON, form data, headers personalizados."""
    category = "web"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "url": ToolParameter(
                name="url",
                type="string",
                description="URL del endpoint API",
                required=True
            ),
            "method": ToolParameter(
                name="method",
                type="string",
                description="Método HTTP",
                required=False,
                enum=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
            ),
            "headers": ToolParameter(
                name="headers",
                type="object",
                description="Headers HTTP como objeto JSON",
                required=False
            ),
            "data": ToolParameter(
                name="data",
                type="object",
                description="Datos para POST/PUT como objeto JSON",
                required=False
            ),
            "params": ToolParameter(
                name="params",
                type="object",
                description="Query parameters como objeto",
                required=False
            ),
            "auth": ToolParameter(
                name="auth",
                type="string",
                description="Token Bearer o 'user:pass' para Basic Auth",
                required=False
            ),
            "timeout": ToolParameter(
                name="timeout",
                type="integer",
                description="Timeout en segundos (default: 30)",
                required=False
            )
        }
    
    def execute(self, url: str = None, method: str = "GET", headers: Dict = None,
                data: Any = None, params: Dict = None, auth: str = None,
                timeout: int = 30, **kwargs) -> str:
        
        url = url or kwargs.get('url', '')
        method = (method or kwargs.get('method', 'GET')).upper()
        headers = headers or kwargs.get('headers', {})
        data = data or kwargs.get('data')
        params = params or kwargs.get('params', {})
        auth = auth or kwargs.get('auth')
        timeout = timeout or kwargs.get('timeout', 30)
        
        if not url:
            return "[x] Se requiere 'url'"
        
        if not HAS_REQUESTS:
            return "[x] Instala requests: pip install requests"
        
        try:
            # Preparar headers
            final_headers = {
                'User-Agent': 'NVIDIA-Code-Agent/1.0',
                'Accept': 'application/json, text/plain, */*',
            }
            
            if headers:
                if isinstance(headers, str):
                    headers = json.loads(headers)
                final_headers.update(headers)
            
            # Autenticación
            if auth:
                if ':' in auth:
                    # Basic auth
                    import base64
                    credentials = base64.b64encode(auth.encode()).decode()
                    final_headers['Authorization'] = f'Basic {credentials}'
                else:
                    # Bearer token
                    final_headers['Authorization'] = f'Bearer {auth}'
            
            # Preparar data
            json_data = None
            form_data = None
            
            if data:
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except:
                        pass
                
                if isinstance(data, dict):
                    json_data = data
                    final_headers.setdefault('Content-Type', 'application/json')
                else:
                    form_data = data
            
            # Hacer request
            session = get_session()
            
            response = session.request(
                method=method,
                url=url,
                headers=final_headers,
                json=json_data,
                data=form_data,
                params=params,
                timeout=timeout,
                allow_redirects=True
            )
            
            # Formatear respuesta
            output_parts = [
                f"📡 **{method} {url}**",
                f"**Status:** {response.status_code} {response.reason}",
                ""
            ]
            
            # Headers de respuesta relevantes
            important_headers = ['content-type', 'content-length', 'x-ratelimit-remaining', 'x-request-id']
            resp_headers = {k: v for k, v in response.headers.items() if k.lower() in important_headers}
            
            if resp_headers:
                output_parts.append("**Headers:**")
                for k, v in resp_headers.items():
                    output_parts.append(f"• {k}: {v}")
                output_parts.append("")
            
            # Cuerpo de la respuesta
            content_type = response.headers.get('content-type', '')
            
            if 'application/json' in content_type:
                try:
                    json_response = response.json()
                    json_str = json.dumps(json_response, indent=2, ensure_ascii=False)
                    
                    if len(json_str) > 10000:
                        json_str = json_str[:10000] + "\n... (truncado)"
                    
                    output_parts.append(f"**Response (JSON):**\n```json\n{json_str}\n```")
                except:
                    output_parts.append(f"**Response:**\n```\n{response.text[:5000]}\n```")
            else:
                text = response.text
                if len(text) > 5000:
                    text = text[:5000] + "\n... (truncado)"
                output_parts.append(f"**Response:**\n```\n{text}\n```")
            
            return '\n'.join(output_parts)
            
        except requests.exceptions.HTTPError as e:
            return f"[x] Error HTTP {e.response.status_code}: {e.response.text[:500]}"
        except Exception as e:
            return f"[x] Error: {e}"


class DownloadFileTool(BaseTool):
    """Descarga archivos de URLs"""
    
    name = "download_file"
    description = "Descarga un archivo desde una URL y lo guarda localmente"
    category = "web"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "url": ToolParameter(
                name="url",
                type="string",
                description="URL del archivo a descargar",
                required=True
            ),
            "save_as": ToolParameter(
                name="save_as",
                type="string",
                description="Nombre/ruta para guardar el archivo",
                required=False
            ),
            "show_progress": ToolParameter(
                name="show_progress",
                type="boolean",
                description="Mostrar progreso de descarga",
                required=False
            )
        }
    
    def execute(self, url: str = None, save_as: str = None, 
                show_progress: bool = True, **kwargs) -> str:
        
        url = url or kwargs.get('url', '')
        save_as = save_as or kwargs.get('save_as')
        
        if not url:
            return "[x] Se requiere 'url'"
        
        if not HAS_REQUESTS:
            return "[x] Instala requests: pip install requests"
        
        try:
            # Determinar nombre de archivo
            if not save_as:
                parsed = urlparse(url)
                filename = Path(parsed.path).name
                
                if not filename or '.' not in filename:
                    filename = "downloaded_file"
                
                save_as = filename
            
            # Crear directorio si no existe
            save_path = Path(save_as)
            if save_path.parent and not save_path.parent.exists():
                save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Descargar
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, stream=True, headers=headers, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(save_as, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
            
            # Formatear tamaño
            if downloaded < 1024:
                size_str = f"{downloaded} B"
            elif downloaded < 1024 * 1024:
                size_str = f"{downloaded / 1024:.1f} KB"
            else:
                size_str = f"{downloaded / (1024 * 1024):.2f} MB"
            
            return f"""✅ **Archivo descargado**

• **Archivo:** {save_as}
• **Tamaño:** {size_str}
• **Origen:** {url}
"""
            
        except Exception as e:
            return f"[x] Error descargando: {e}"


class GitHubAPITool(BaseTool):
    """Interactúa con GitHub API"""
    
    name = "github_api"
    description = """Obtiene información de repositorios GitHub.
    Acciones disponibles: info, readme, issues, releases, contents, search, user, commits"""
    category = "web"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "repo": ToolParameter(
                name="repo",
                type="string",
                description="Repositorio (formato: owner/repo) o usuario para action=user",
                required=True
            ),
            "action": ToolParameter(
                name="action",
                type="string",
                description="Acción a realizar",
                required=False,
                enum=["info", "readme", "issues", "releases", "contents", "search", "user", "commits", "tree"]
            ),
            "path": ToolParameter(
                name="path",
                type="string",
                description="Ruta para contents/tree (ej: 'src/main.py')",
                required=False
            ),
            "branch": ToolParameter(
                name="branch",
                type="string",
                description="Rama (default: main/master)",
                required=False
            )
        }
    
    def execute(self, repo: str = None, action: str = "info", 
                path: str = None, branch: str = None, **kwargs) -> str:
        
        repo = repo or kwargs.get('repo', '')
        action = action or kwargs.get('action', 'info')
        path = path or kwargs.get('path', '')
        branch = branch or kwargs.get('branch', '')
        
        if not repo:
            return "[x] Se requiere 'repo' (formato: owner/repo)"
        
        if not HAS_REQUESTS:
            return "[x] Instala requests: pip install requests"
        
        try:
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'NVIDIA-Code-Agent'
            }
            
            # Token de GitHub si existe en el entorno
            import os
            gh_token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
            if gh_token:
                headers['Authorization'] = f'token {gh_token}'
            
            base_url = f"https://api.github.com/repos/{repo}"
            session = get_session()
            
            if action == "info":
                response = session.get(base_url, headers=headers, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                return f"""📦 **{data['full_name']}**

{data.get('description', 'Sin descripción')}

| Métrica | Valor |
|---------|-------|
| ⭐ Stars | {data['stargazers_count']:,} |
| 🍴 Forks | {data['forks_count']:,} |
| 👁️ Watchers | {data['watchers_count']:,} |
| 🐛 Issues | {data['open_issues_count']:,} |
| 💻 Lenguaje | {data.get('language', 'N/A')} |
| 📅 Creado | {data['created_at'][:10]} |
| 🔄 Actualizado | {data['updated_at'][:10]} |

🔗 **URL:** {data['html_url']}
📄 **Licencia:** {data.get('license', {}).get('name', 'No especificada')}

**Topics:** {', '.join(data.get('topics', [])) or 'Ninguno'}
"""
            
            elif action == "readme":
                response = session.get(f"{base_url}/readme", headers=headers, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                content = base64.b64decode(data['content']).decode('utf-8')
                
                if len(content) > 8000:
                    content = content[:8000] + "\n\n... (README truncado)"
                
                return f"📄 **README de {repo}**\n\n{content}"
            
            elif action == "contents" or action == "tree":
                url = f"{base_url}/contents/{path}"
                if branch:
                    url += f"?ref={branch}"
                
                response = session.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                if isinstance(data, list):
                    # Es un directorio
                    output = [f"📁 **Contenido de {repo}/{path or ''}**\n"]
                    
                    # Separar directorios y archivos
                    dirs = [x for x in data if x['type'] == 'dir']
                    files = [x for x in data if x['type'] == 'file']
                    
                    for d in sorted(dirs, key=lambda x: x['name']):
                        output.append(f"📁 {d['name']}/")
                    
                    for f in sorted(files, key=lambda x: x['name']):
                        size = f"{f['size']:,} bytes" if f['size'] < 1024 else f"{f['size']/1024:.1f} KB"
                        output.append(f"📄 {f['name']} ({size})")
                    
                    return '\n'.join(output)
                else:
                    # Es un archivo
                    if data.get('encoding') == 'base64':
                        content = base64.b64decode(data['content']).decode('utf-8')
                        
                        if len(content) > 10000:
                            content = content[:10000] + "\n\n... (archivo truncado)"
                        
                        # Detectar lenguaje para syntax highlighting
                        ext = Path(data['name']).suffix.lstrip('.')
                        
                        return f"📄 **{data['path']}** ({data['size']:,} bytes)\n\n```{ext}\n{content}\n```"
                    else:
                        return f"📄 **{data['path']}** - Archivo binario ({data['size']:,} bytes)\n🔗 {data['download_url']}"
            
            elif action == "issues":
                response = session.get(
                    f"{base_url}/issues?state=open&per_page=15&sort=updated",
                    headers=headers, timeout=15
                )
                response.raise_for_status()
                issues = response.json()
                
                if not issues:
                    return f"✅ No hay issues abiertos en **{repo}**"
                
                output = [f"🐛 **Issues abiertos en {repo}** ({len(issues)} mostrados)\n"]
                
                for issue in issues:
                    labels = ' '.join([f"`{l['name']}`" for l in issue.get('labels', [])[:3]])
                    comments = f"💬 {issue['comments']}" if issue['comments'] else ""
                    output.append(f"• **#{issue['number']}** {issue['title']}")
                    output.append(f"  {labels} {comments} - {issue['updated_at'][:10]}")
                
                return '\n'.join(output)
            
            elif action == "releases":
                response = session.get(f"{base_url}/releases?per_page=10", headers=headers, timeout=15)
                response.raise_for_status()
                releases = response.json()
                
                if not releases:
                    return f"📦 No hay releases en **{repo}**"
                
                output = [f"📦 **Releases de {repo}**\n"]
                
                for rel in releases:
                    output.append(f"### {rel['tag_name']} - {rel.get('name', 'Sin nombre')}")
                    output.append(f"📅 {rel['published_at'][:10]} | 👤 {rel['author']['login']}")
                    
                    if rel.get('body'):
                        body = rel['body'][:500]
                        if len(rel['body']) > 500:
                            body += "..."
                        output.append(f"_{body}_")
                    
                    output.append("")
                
                return '\n'.join(output)
            
            elif action == "commits":
                url = f"{base_url}/commits?per_page=15"
                if branch:
                    url += f"&sha={branch}"
                
                response = session.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                commits = response.json()
                
                output = [f"📝 **Últimos commits en {repo}**\n"]
                
                for c in commits:
                    sha = c['sha'][:7]
                    msg = c['commit']['message'].split('\n')[0][:60]
                    author = c['commit']['author']['name']
                    date = c['commit']['author']['date'][:10]
                    output.append(f"• `{sha}` {msg}")
                    output.append(f"  _{author}_ - {date}")
                
                return '\n'.join(output)
            
            elif action == "user":
                response = session.get(f"https://api.github.com/users/{repo}", headers=headers, timeout=15)
                response.raise_for_status()
                user = response.json()
                
                return f"""👤 **{user['login']}** ({user.get('name', 'Sin nombre')})

{user.get('bio', 'Sin bio')}

| Métrica | Valor |
|---------|-------|
| 📦 Repos | {user['public_repos']} |
| 👥 Seguidores | {user['followers']:,} |
| 👣 Siguiendo | {user['following']:,} |
| 🏢 Empresa | {user.get('company', 'N/A')} |
| 📍 Ubicación | {user.get('location', 'N/A')} |

🔗 {user['html_url']}
"""
            
            elif action == "search":
                response = session.get(
                    f"https://api.github.com/search/repositories?q={quote_plus(repo)}&sort=stars&per_page=10",
                    headers=headers, timeout=15
                )
                response.raise_for_status()
                results = response.json()
                
                output = [f"🔍 **Búsqueda: {repo}** ({results['total_count']:,} resultados)\n"]
                
                for r in results['items']:
                    output.append(f"### ⭐ {r['stargazers_count']:,} | {r['full_name']}")
                    output.append(f"{r.get('description', 'Sin descripción')[:100]}")
                    output.append(f"💻 {r.get('language', 'N/A')} | 🍴 {r['forks_count']:,}")
                    output.append("")
                
                return '\n'.join(output)
            
            else:
                return f"[x] Acción no soportada: {action}"
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return f"[x] No encontrado: {repo}"
            elif e.response.status_code == 403:
                return f"[x] Rate limit excedido. Configura GITHUB_TOKEN para más requests"
            return f"[x] Error HTTP {e.response.status_code}: {e.response.text[:200]}"
        except Exception as e:
            return f"[x] Error: {e}"


class ClearWebCacheTool(BaseTool):
    """Limpia la caché web"""
    
    name = "clear_web_cache"
    description = "Limpia la caché de páginas web descargadas"
    category = "web"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {}
    
    def execute(self, **kwargs) -> str:
        entries = len(_web_cache.cache)
        _web_cache.clear()
        return f"✅ Caché limpiada ({entries} entradas eliminadas)"


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE HERRAMIENTAS
# ══════════════════════════════════════════════════════════════════════════════

# Para importar desde tools/__init__.py
WEB_TOOLS = [
    WebScrapeTool,
    WebSearchTool,
    APIRequestTool,
    DownloadFileTool,
    GitHubAPITool,
    ClearWebCacheTool,
]