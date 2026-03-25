"""
NVIDIA CODE - Arsenal Tools (Auto-Exploiter, OSINT, Escavizador LLM & Clone Frontend)
Zero limits, full autonomy.
"""

import os
import re
import json
import asyncio
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse

from tools.base import BaseTool, ToolParameter
from ui.colors import C

# Intentar importar playwright
try:
    from playwright.async_api import async_playwright
except ImportError:
    pass

class ScrapingAgresivoTool(BaseTool):
    name = "scraping_agresivo"
    description = "Bypass Cloudflare/Captchas con Playwright en modo stealth. Scrapea contenido protegido."
    category = "security"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "url": ToolParameter("url", "string", "URL a scrapear alv", required=True),
            "wait_selector": ToolParameter("wait_selector", "string", "Selector CSS para esperar que cargue (opcional)"),
        }

    def execute(self, **kwargs) -> str:
        # Se lanza asincrono
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self._run_pw(**kwargs))

    async def _run_pw(self, url: str, wait_selector: str = None) -> str:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                # Ocultar webdriver
                await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                await page.goto(url, wait_until="networkidle")
                
                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=10000)
                    except Exception:
                        pass # si no carga, seguimos a ver q pedo
                
                content = await page.content()
                await browser.close()
                soup = BeautifulSoup(content, 'html.parser')
                return f"[+] Scraping exitoso ({len(content)} bytes)\nExtracto: {soup.text[:1000]}"
        except Exception as e:
            return f"[x] Error en scraping agresivo: {e}"


class LLMSlaveTool(BaseTool):
    name = "esclavizador_llm"
    description = "Usa la web de un LLM gratis (DeepSeek via deepseek-espanol.chat o ähnliches) enviando prompt y extrayendo respuesta usando Playwright. Bypass Limits."
    category = "ai"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "prompt": ToolParameter("prompt", "string", "Instrucción o pregunta para el modelo.", required=True)
        }

    def execute(self, **kwargs) -> str:
        return "[!] A VECES LOS CHATS REQUIEREN LOGIN O CLOUDFLARE MUY RUDO. Esta es una versión experimental.\n" + \
               self._dummy_executor(kwargs['prompt'])

    def _dummy_executor(self, prompt: str) -> str:
        # Aquí tendríamos que automatizar los clicks de la UI del bot
        # Este es un POC porque un bot real requiere resolver CF Turnstile
        return f"[i] LLM Slave (POC) - Simulando ejecución de prompt: '{prompt}'... (Requeriría sesión grabada de PW)"


class OSINTDoxTool(BaseTool):
    name = "osint_auto_doxx"
    description = "Busca correos, alias o dominios en bases públicas y dorks de Google."
    category = "security"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "target": ToolParameter("target", "string", "Email, usuario o dominio a doxxear", required=True),
        }

    def execute(self, **kwargs) -> str:
        target = kwargs['target']
        results = f"🔍 Reporte OSINT para: {target}\n"
        
        # dorks en duckduckgo (sin api keys)
        try:
            url = f"https://html.duckduckgo.com/html/?q=intext:{target}"
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            links = []
            for a in soup.find_all('a', class_='result__url'):
                links.append(a['href'] if a.has_attr('href') else "")
            
            links = [l for l in links if l]
            results += f"[*] Encontrados {len(links)} links relacionados en open web.\n"
            results += "\n".join(links[:5])
        except Exception as e:
            results += f"[-] Error en buscador: {e}\n"

        # chequear github
        if '@' not in target:
            try:
                gh = requests.get(f"https://api.github.com/users/{target}").json()
                if 'login' in gh:
                    results += f"\n[+] GitHub encontrado: {gh.get('html_url')} - Nombre: {gh.get('name')} - Empresa: {gh.get('company')}\n"
            except: pass

        return results


class PentestExploitTool(BaseTool):
    name = "pentest_auto_exploit"
    description = "Lanza payloads básicos de XSS / SQLi a una URL y verifica reflejos maliciosos."
    category = "security"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "url": ToolParameter("url", "string", "URL vulnerable ej. http://sitio.com/id=", required=True)
        }

    def execute(self, **kwargs) -> str:
        url = kwargs['url']
        payloads = [
            ("'", "error in your sql syntax"),
            ("<script>alert(1)</script>", "<script>alert(1)</script>")
        ]
        
        results = f"💀 Iniciando scanner agresivo para: {url}\n"
        
        for payload, trigger in payloads:
            try:
                target = f"{url}{payload}"
                r = requests.get(target, timeout=5)
                if trigger.lower() in r.text.lower():
                    results += f"[!] VULNERABLE al payload: {payload}\n"
                else:
                    results += f"[-] Payload {payload} filtrado.\n"
            except Exception as e:
                pass
                
        return results


class CloneFrontendTool(BaseTool):
    name = "clonador_frontend"
    description = "Descarga HTML y CSS de una web limpiando scripts pesados, para usar en proyectos propios al instante."
    category = "web"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "url": ToolParameter("url", "string", "URL de la web que quieres clonar", required=True),
        }

    def execute(self, **kwargs) -> str:
        url = kwargs['url']
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')

            # quitar JS
            for s in soup(["script", "noscript", "iframe"]):
                s.decompose()

            # hacer css absolute
            for link in soup.find_all('link'):
                if link.get('href'):
                    link['href'] = urljoin(url, link['href'])
            
            for img in soup.find_all('img'):
                if img.get('src'):
                    img['src'] = urljoin(url, img['src'])

            html = soup.prettify()
            save_path = os.path.join(os.getcwd(), "clonado.html")
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(html)

            return f"🎨 ¡Frontend clonado mamalón! Guardado en {save_path}. Peso: {len(html)/1024:.2f} KB."
        except Exception as e:
            return f"[x] Se pudrió la clonada: {e}"


def register_arsenal_tools(registry):
    registry.register(ScrapingAgresivoTool())
    registry.register(LLMSlaveTool())
    registry.register(OSINTDoxTool())
    registry.register(PentestExploitTool())
    registry.register(CloneFrontendTool())
