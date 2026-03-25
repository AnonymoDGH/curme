"""
Screenshot Tool - Toma screenshots de sitios web y apps
Usa playwright si está disponible, fallback a requests + PIL
"""

import os
import time
import tempfile
from pathlib import Path
from typing import Dict
from .base import BaseTool, ToolParameter


SCREENSHOTS_DIR = Path(tempfile.gettempdir()) / "openclaw_screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


class ScreenshotWebTool(BaseTool):
    name = "screenshot_web"
    description = "Toma un screenshot de un sitio web y retorna la ruta del archivo de imagen"
    category = "media"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "url": ToolParameter(
                name="url",
                type="string",
                description="URL del sitio web para capturar",
                required=True
            ),
            "full_page": ToolParameter(
                name="full_page",
                type="string",
                description="Si capturar la página completa (true/false). Default: false",
                required=False,
                default="false"
            ),
            "wait_ms": ToolParameter(
                name="wait_ms",
                type="string",
                description="Milisegundos de espera antes de capturar (para JS). Default: 2000",
                required=False,
                default="2000"
            ),
            "width": ToolParameter(
                name="width",
                type="string",
                description="Ancho del viewport en px. Default: 1280",
                required=False,
                default="1280"
            ),
            "height": ToolParameter(
                name="height",
                type="string",
                description="Alto del viewport en px. Default: 800",
                required=False,
                default="800"
            )
        }

    def execute(self, url: str, full_page: str = "false", wait_ms: str = "2000",
                width: str = "1280", height: str = "800") -> str:
        full = str(full_page).lower() in ("true", "1", "yes", "sí")
        wait = int(wait_ms) if str(wait_ms).isdigit() else 2000
        w = int(width) if str(width).isdigit() else 1280
        h = int(height) if str(height).isdigit() else 800

        timestamp = int(time.time())
        filename = f"screenshot_{timestamp}.png"
        output_path = SCREENSHOTS_DIR / filename

        # Intentar con playwright (async → sync wrapper)
        try:
            return self._screenshot_playwright(url, output_path, full, wait, w, h)
        except Exception as e1:
            # Fallback: selenium
            try:
                return self._screenshot_selenium(url, output_path, w, h)
            except Exception as e2:
                # Último fallback: captura con requests + lxml render (no real screenshot)
                return f"❌ No se pudo tomar screenshot.\n  Playwright: {e1}\n  Selenium: {e2}\n\nInstala: `pip install playwright && playwright install chromium`"

    def _screenshot_playwright(self, url, output_path, full_page, wait_ms, width, height) -> str:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
            ])
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if wait_ms > 0:
                page.wait_for_timeout(wait_ms)
            page.screenshot(path=str(output_path), full_page=full_page)
            browser.close()

        size_kb = output_path.stat().st_size // 1024
        return f"📸 [FILE:{output_path}]\nScreenshot de {url}\nGuardado: {output_path.name} ({size_kb} KB)"

    def _screenshot_selenium(self, url, output_path, width, height) -> str:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument(f"--window-size={width},{height}")

        driver = webdriver.Chrome(options=opts)
        driver.get(url)
        time.sleep(2)
        driver.save_screenshot(str(output_path))
        driver.quit()

        size_kb = output_path.stat().st_size // 1024
        return f"📸 [FILE:{output_path}]\nScreenshot de {url}\nGuardado: {output_path.name} ({size_kb} KB)"


class SendMediaTool(BaseTool):
    """Tool que el agente usa para indicar que quiere enviar un archivo al usuario"""
    name = "send_media"
    description = "Envía un archivo (imagen, video, documento) al canal de Discord o consola"
    category = "media"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "file_path": ToolParameter(
                name="file_path",
                type="string",
                description="Ruta absoluta al archivo a enviar",
                required=True
            ),
            "caption": ToolParameter(
                name="caption",
                type="string",
                description="Texto/descripción que acompaña el archivo",
                required=False,
                default=""
            )
        }

    def execute(self, file_path: str, caption: str = "") -> str:
        path = Path(file_path)
        if not path.exists():
            return f"❌ Archivo no encontrado: {file_path}"

        size_kb = path.stat().st_size // 1024
        caption_part = f" — {caption}" if caption else ""
        return f"📎 [FILE:{path}]\n{path.name} ({size_kb} KB){caption_part}"


class ScreenshotLocalTool(BaseTool):
    """Toma screenshot de la pantalla actual del sistema"""
    name = "screenshot_screen"
    description = "Toma un screenshot de la pantalla actual del sistema operativo"
    category = "media"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "region": ToolParameter(
                name="region",
                type="string",
                description="Región a capturar: 'full' (pantalla completa) o 'x,y,w,h'. Default: full",
                required=False,
                default="full"
            )
        }

    def execute(self, region: str = "full") -> str:
        try:
            import pyautogui
            timestamp = int(time.time())
            output_path = SCREENSHOTS_DIR / f"screen_{timestamp}.png"

            if region == "full":
                screenshot = pyautogui.screenshot()
            else:
                try:
                    x, y, w, h = [int(v) for v in region.split(",")]
                    screenshot = pyautogui.screenshot(region=(x, y, w, h))
                except ValueError:
                    screenshot = pyautogui.screenshot()

            screenshot.save(str(output_path))
            size_kb = output_path.stat().st_size // 1024
            return f"📸 [FILE:{output_path}]\nScreenshot de pantalla guardado: {output_path.name} ({size_kb} KB)"

        except ImportError:
            return "❌ pyautogui no instalado. `pip install pyautogui pillow`"
        except Exception as e:
            return f"❌ Error tomando screenshot: {e}"
