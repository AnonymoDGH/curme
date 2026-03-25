"""
═══════════════════════════════════════════════════════════════════════════════
🎨 MEDIA PROCESSING TOOLS - Professional Edition
═══════════════════════════════════════════════════════════════════════════════

Herramientas avanzadas para procesamiento de medios:
- Compresión de imágenes con optimización inteligente
- Generación de thumbnails de video
- Manipulación de PDFs (merge/split)
- Transcripción de audio con Whisper
- Generación de códigos QR personalizados
- OCR para extracción de texto

Dependencias:
pip install Pillow opencv-python PyPDF2 qrcode[pil] pytesseract openai-whisper
"""

import os
import io
import base64
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .base import BaseTool, ToolParameter

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS CONDICIONALES
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from PIL import Image, ImageOps, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from PyPDF2 import PdfReader, PdfWriter, PdfMerger
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer, CircleModuleDrawer
    from qrcode.image.styles.colormasks import SolidFillColorMask
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False


# ═══════════════════════════════════════════════════════════════════════════════
# 1. IMAGE COMPRESS TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class ImageCompressTool(BaseTool):
    """Comprime imágenes optimizando calidad y tamaño"""
    
    name = "image_compress"
    description = """Comprime imágenes manteniendo calidad óptima.
    
Características:
  ‣ Soporta JPEG, PNG, WebP
  ‣ Balance inteligente calidad/tamaño
  ‣ Remueve metadatos EXIF
  ‣ Progressive loading (JPEG)
  ‣ Optimización de paleta (PNG)
  ‣ Redimensionamiento opcional
  
Modos de compresión:
  - light: Compresión ligera (90% calidad)
  - medium: Balance (75% calidad) 
  - heavy: Máxima compresión (60% calidad)
  - custom: Calidad personalizada"""
    
    category = "media"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "input_path": ToolParameter(
                name="input_path",
                type="string",
                description="Ruta de imagen a comprimir",
                required=True
            ),
            "output_path": ToolParameter(
                name="output_path",
                type="string",
                description="Ruta de salida (opcional, auto-genera si no se especifica)",
                required=False
            ),
            "mode": ToolParameter(
                name="mode",
                type="string",
                description="Modo de compresión: light, medium, heavy, custom",
                required=False,
                enum=["light", "medium", "heavy", "custom"]
            ),
            "quality": ToolParameter(
                name="quality",
                type="integer",
                description="Calidad 1-100 (solo para mode=custom)",
                required=False
            ),
            "max_width": ToolParameter(
                name="max_width",
                type="integer",
                description="Ancho máximo (redimensiona si excede)",
                required=False
            ),
            "max_height": ToolParameter(
                name="max_height",
                type="integer",
                description="Alto máximo (redimensiona si excede)",
                required=False
            ),
            "format": ToolParameter(
                name="format",
                type="string",
                description="Formato de salida: jpeg, png, webp (auto si no se especifica)",
                required=False,
                enum=["jpeg", "png", "webp"]
            ),
            "remove_metadata": ToolParameter(
                name="remove_metadata",
                type="boolean",
                description="Remover metadatos EXIF (default: true)",
                required=False
            )
        }
    
    def execute(
        self, 
        input_path: str = None,
        output_path: str = None,
        mode: str = "medium",
        quality: int = None,
        max_width: int = None,
        max_height: int = None,
        format: str = None,
        remove_metadata: bool = True,
        **kwargs
    ) -> str:
        if not HAS_PIL:
            return "[x] Instala: pip install Pillow"
        
        # Obtener parámetros
        input_path = input_path or kwargs.get('input_path')
        output_path = output_path or kwargs.get('output_path')
        mode = mode or kwargs.get('mode', 'medium')
        quality = quality or kwargs.get('quality')
        max_width = max_width or kwargs.get('max_width')
        max_height = max_height or kwargs.get('max_height')
        format = format or kwargs.get('format')
        remove_metadata = kwargs.get('remove_metadata', remove_metadata)
        
        if not input_path:
            return "[x] Se requiere 'input_path'"
        
        input_file = Path(input_path)
        if not input_file.exists():
            return f"[x] No existe: {input_path}"
        
        try:
            # Abrir imagen
            img = Image.open(input_file)
            original_format = img.format
            original_size = input_file.stat().st_size
            width, height = img.size
            
            # Convertir RGBA a RGB si es necesario para JPEG
            if img.mode in ('RGBA', 'LA', 'P'):
                if format == 'jpeg' or (not format and original_format == 'JPEG'):
                    # Crear fondo blanco
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
            
            # Redimensionar si es necesario
            if max_width or max_height:
                img = self._resize_image(img, max_width, max_height)
                width, height = img.size
            
            # Determinar calidad según modo
            quality_map = {
                'light': 90,
                'medium': 75,
                'heavy': 60
            }
            
            if mode == 'custom':
                if not quality:
                    return "[x] Se requiere 'quality' para mode=custom"
                compress_quality = max(1, min(100, quality))
            else:
                compress_quality = quality_map.get(mode, 75)
            
            # Determinar formato de salida
            if not format:
                format = original_format.lower() if original_format else 'jpeg'
            
            # Generar nombre de salida si no se especificó
            if not output_path:
                stem = input_file.stem
                suffix = f"_compressed_{mode}"
                output_path = input_file.parent / f"{stem}{suffix}.{format}"
            
            output_file = Path(output_path)
            
            # Remover metadatos si se solicita
            if remove_metadata:
                # Crear nueva imagen sin metadatos
                data = list(img.getdata())
                img_no_exif = Image.new(img.mode, img.size)
                img_no_exif.putdata(data)
                img = img_no_exif
            
            # Guardar según formato
            save_kwargs = {}
            
            if format == 'jpeg':
                save_kwargs = {
                    'quality': compress_quality,
                    'optimize': True,
                    'progressive': True
                }
            elif format == 'png':
                save_kwargs = {
                    'optimize': True,
                    'compress_level': 9
                }
                # Para PNG, quality afecta la reducción de colores
                if compress_quality < 90:
                    img = img.convert('P', palette=Image.ADAPTIVE, colors=256)
            elif format == 'webp':
                save_kwargs = {
                    'quality': compress_quality,
                    'method': 6  # Mejor compresión
                }
            
            img.save(output_file, format=format.upper(), **save_kwargs)
            
            # Estadísticas
            output_size = output_file.stat().st_size
            reduction = ((original_size - output_size) / original_size) * 100
            
            result = f"""✅ **Imagen Comprimida**

📁 **Entrada:** {input_file.name}
  └─ Tamaño: {self._format_bytes(original_size)}
  └─ Dimensiones: {img.size[0]}x{img.size[1]}

💾 **Salida:** {output_file.name}
  └─ Tamaño: {self._format_bytes(output_size)}
  └─ Formato: {format.upper()}
  └─ Calidad: {compress_quality}%
  
📊 **Reducción:** {reduction:.1f}% ({self._format_bytes(original_size - output_size)} ahorrados)
📍 **Ruta:** {output_file.absolute()}"""
            
            return result
            
        except Exception as e:
            return f"[x] Error comprimiendo imagen: {e}"
    
    def _resize_image(self, img: Image.Image, max_width: int = None, max_height: int = None) -> Image.Image:
        """Redimensiona imagen manteniendo aspect ratio"""
        width, height = img.size
        
        if max_width and width > max_width:
            ratio = max_width / width
            new_width = max_width
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            width, height = new_width, new_height
        
        if max_height and height > max_height:
            ratio = max_height / height
            new_height = max_height
            new_width = int(width * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return img
    
    def _format_bytes(self, bytes_size: int) -> str:
        """Formatea bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. VIDEO THUMBNAIL TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class VideoThumbnailTool(BaseTool):
    """Genera thumbnails de videos"""
    
    name = "video_thumbnail"
    description = """Extrae frames de video para crear thumbnails.
    
Características:
  ‣ Extracción en timestamp específico
  ‣ Múltiples thumbnails (grid)
  ‣ Redimensionamiento automático
  ‣ Formatos: JPEG, PNG, WebP
  
Modos:
  - single: Un frame en timestamp específico
  - multiple: Varios frames espaciados
  - grid: Composición de múltiples frames"""
    
    category = "media"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "video_path": ToolParameter(
                name="video_path",
                type="string",
                description="Ruta del video",
                required=True
            ),
            "output_path": ToolParameter(
                name="output_path",
                type="string",
                description="Ruta de salida para thumbnail(s)",
                required=False
            ),
            "timestamp": ToolParameter(
                name="timestamp",
                type="number",
                description="Timestamp en segundos (para mode=single)",
                required=False
            ),
            "mode": ToolParameter(
                name="mode",
                type="string",
                description="Modo: single, multiple, grid",
                required=False,
                enum=["single", "multiple", "grid"]
            ),
            "count": ToolParameter(
                name="count",
                type="integer",
                description="Número de thumbnails (para mode=multiple/grid)",
                required=False
            ),
            "width": ToolParameter(
                name="width",
                type="integer",
                description="Ancho del thumbnail",
                required=False
            ),
            "height": ToolParameter(
                name="height",
                type="integer",
                description="Alto del thumbnail",
                required=False
            )
        }
    
    def execute(
        self,
        video_path: str = None,
        output_path: str = None,
        timestamp: float = None,
        mode: str = "single",
        count: int = 4,
        width: int = None,
        height: int = None,
        **kwargs
    ) -> str:
        if not HAS_CV2:
            return "[x] Instala: pip install opencv-python"
        
        if not HAS_PIL:
            return "[x] Instala: pip install Pillow"
        
        # Obtener parámetros
        video_path = video_path or kwargs.get('video_path')
        output_path = output_path or kwargs.get('output_path')
        timestamp = timestamp or kwargs.get('timestamp', 0)
        mode = mode or kwargs.get('mode', 'single')
        count = count or kwargs.get('count', 4)
        width = width or kwargs.get('width')
        height = height or kwargs.get('height')
        
        if not video_path:
            return "[x] Se requiere 'video_path'"
        
        video_file = Path(video_path)
        if not video_file.exists():
            return f"[x] No existe: {video_path}"
        
        try:
            # Abrir video
            cap = cv2.VideoCapture(str(video_file))
            
            if not cap.isOpened():
                return f"[x] No se pudo abrir video: {video_path}"
            
            # Obtener info del video
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if mode == "single":
                return self._extract_single_frame(
                    cap, video_file, output_path, timestamp, 
                    fps, duration, width, height
                )
            
            elif mode == "multiple":
                return self._extract_multiple_frames(
                    cap, video_file, output_path, count,
                    duration, fps, width, height
                )
            
            elif mode == "grid":
                return self._extract_grid(
                    cap, video_file, output_path, count,
                    duration, fps, video_width, video_height, width, height
                )
            
            else:
                return f"[x] Modo no soportado: {mode}"
            
        except Exception as e:
            return f"[x] Error procesando video: {e}"
        finally:
            if 'cap' in locals():
                cap.release()
    
    def _extract_single_frame(
        self, cap, video_file, output_path, timestamp, 
        fps, duration, width, height
    ) -> str:
        """Extrae un solo frame"""
        
        # Validar timestamp
        if timestamp > duration:
            timestamp = duration / 2
        
        # Ir al frame
        frame_number = int(timestamp * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        
        ret, frame = cap.read()
        if not ret:
            return f"[x] No se pudo leer frame en {timestamp}s"
        
        # Convertir BGR a RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        
        # Redimensionar si se especificó
        if width or height:
            img = self._resize_with_aspect(img, width, height)
        
        # Generar nombre de salida
        if not output_path:
            output_path = video_file.parent / f"{video_file.stem}_thumb_{int(timestamp)}s.jpg"
        
        output_file = Path(output_path)
        img.save(output_file, 'JPEG', quality=90, optimize=True)
        
        return f"""✅ **Thumbnail Generado**

🎬 **Video:** {video_file.name}
⏱️  **Timestamp:** {timestamp:.1f}s / {duration:.1f}s
📐 **Dimensiones:** {img.size[0]}x{img.size[1]}
📍 **Guardado:** {output_file.absolute()}"""
    
    def _extract_multiple_frames(
        self, cap, video_file, output_path, count,
        duration, fps, width, height
    ) -> str:
        """Extrae múltiples frames espaciados"""
        
        interval = duration / (count + 1)
        output_files = []
        
        for i in range(1, count + 1):
            timestamp = interval * i
            frame_number = int(timestamp * fps)
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            
            if width or height:
                img = self._resize_with_aspect(img, width, height)
            
            # Generar nombre
            if output_path:
                base = Path(output_path).stem
                ext = Path(output_path).suffix or '.jpg'
                output_file = Path(output_path).parent / f"{base}_{i}{ext}"
            else:
                output_file = video_file.parent / f"{video_file.stem}_thumb_{i}.jpg"
            
            img.save(output_file, 'JPEG', quality=90, optimize=True)
            output_files.append(output_file.name)
        
        return f"""✅ **Thumbnails Generados**

🎬 **Video:** {video_file.name}
📊 **Cantidad:** {len(output_files)} frames
⏱️  **Duración:** {duration:.1f}s

**Archivos:**
""" + "\n".join(f"  {i+1}. {name}" for i, name in enumerate(output_files))
    
    def _extract_grid(
        self, cap, video_file, output_path, count,
        duration, fps, video_width, video_height, width, height
    ) -> str:
        """Crea grid de thumbnails"""
        
        # Calcular disposición del grid (2x2, 3x2, etc)
        cols = int(count ** 0.5)
        rows = (count + cols - 1) // cols
        
        # Tamaño de cada thumbnail en el grid
        thumb_width = width or (video_width // cols)
        thumb_height = height or (video_height // rows)
        
        # Crear canvas
        grid_width = thumb_width * cols
        grid_height = thumb_height * rows
        grid = Image.new('RGB', (grid_width, grid_height), (0, 0, 0))
        
        interval = duration / (count + 1)
        
        for i in range(count):
            timestamp = interval * (i + 1)
            frame_number = int(timestamp * fps)
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img = img.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
            
            # Posición en el grid
            row = i // cols
            col = i % cols
            x = col * thumb_width
            y = row * thumb_height
            
            grid.paste(img, (x, y))
        
        # Guardar grid
        if not output_path:
            output_path = video_file.parent / f"{video_file.stem}_grid.jpg"
        
        output_file = Path(output_path)
        grid.save(output_file, 'JPEG', quality=90, optimize=True)
        
        return f"""✅ **Grid de Thumbnails Generado**

🎬 **Video:** {video_file.name}
📐 **Grid:** {cols}x{rows} ({count} frames)
📏 **Dimensiones:** {grid_width}x{grid_height}
📍 **Guardado:** {output_file.absolute()}"""
    
    def _resize_with_aspect(self, img: Image.Image, width: int = None, height: int = None) -> Image.Image:
        """Redimensiona manteniendo aspect ratio"""
        orig_width, orig_height = img.size
        
        if width and height:
            return img.resize((width, height), Image.Resampling.LANCZOS)
        
        if width:
            ratio = width / orig_width
            new_height = int(orig_height * ratio)
            return img.resize((width, new_height), Image.Resampling.LANCZOS)
        
        if height:
            ratio = height / orig_height
            new_width = int(orig_width * ratio)
            return img.resize((new_width, height), Image.Resampling.LANCZOS)
        
        return img


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PDF MERGE/SPLIT TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class PDFMergeSplitTool(BaseTool):
    """Une o divide archivos PDF"""
    
    name = "pdf_merge_split"
    description = """Manipula archivos PDF: merge, split, extract.
    
Operaciones:
  ‣ merge: Combinar múltiples PDFs
  ‣ split: Dividir PDF en páginas individuales
  ‣ extract: Extraer rango de páginas
  ‣ info: Obtener información del PDF"""
    
    category = "media"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "operation": ToolParameter(
                name="operation",
                type="string",
                description="Operación: merge, split, extract, info",
                required=True,
                enum=["merge", "split", "extract", "info"]
            ),
            "input_path": ToolParameter(
                name="input_path",
                type="string",
                description="Ruta del PDF (o lista separada por comas para merge)",
                required=True
            ),
            "output_path": ToolParameter(
                name="output_path",
                type="string",
                description="Ruta de salida",
                required=False
            ),
            "pages": ToolParameter(
                name="pages",
                type="string",
                description="Rango de páginas: '1-5' o '1,3,5' (para extract)",
                required=False
            )
        }
    
    def execute(
        self,
        operation: str = None,
        input_path: str = None,
        output_path: str = None,
        pages: str = None,
        **kwargs
    ) -> str:
        if not HAS_PYPDF:
            return "[x] Instala: pip install PyPDF2"
        
        operation = operation or kwargs.get('operation')
        input_path = input_path or kwargs.get('input_path')
        output_path = output_path or kwargs.get('output_path')
        pages = pages or kwargs.get('pages')
        
        if not operation:
            return "[x] Se requiere 'operation'"
        
        if not input_path:
            return "[x] Se requiere 'input_path'"
        
        try:
            if operation == "merge":
                return self._merge_pdfs(input_path, output_path)
            
            elif operation == "split":
                return self._split_pdf(input_path, output_path)
            
            elif operation == "extract":
                return self._extract_pages(input_path, output_path, pages)
            
            elif operation == "info":
                return self._pdf_info(input_path)
            
            else:
                return f"[x] Operación no soportada: {operation}"
                
        except Exception as e:
            return f"[x] Error procesando PDF: {e}"
    
    def _merge_pdfs(self, input_paths: str, output_path: str = None) -> str:
        """Combina múltiples PDFs"""
        
        # Parsear rutas (separadas por coma)
        paths = [p.strip() for p in input_paths.split(',')]
        
        # Validar que existan
        pdf_files = []
        for path in paths:
            pdf_file = Path(path)
            if not pdf_file.exists():
                return f"[x] No existe: {path}"
            pdf_files.append(pdf_file)
        
        if len(pdf_files) < 2:
            return "[x] Se requieren al menos 2 PDFs para merge"
        
        # Crear merger
        merger = PdfMerger()
        
        total_pages = 0
        for pdf_file in pdf_files:
            reader = PdfReader(pdf_file)
            total_pages += len(reader.pages)
            merger.append(pdf_file)
        
        # Generar nombre de salida
        if not output_path:
            output_path = pdf_files[0].parent / "merged_output.pdf"
        
        output_file = Path(output_path)
        
        # Guardar
        with open(output_file, 'wb') as f:
            merger.write(f)
        
        merger.close()
        
        file_size = output_file.stat().st_size
        
        return f"""✅ **PDFs Combinados**

📄 **Archivos fusionados:** {len(pdf_files)}
""" + "\n".join(f"  {i+1}. {f.name}" for i, f in enumerate(pdf_files)) + f"""

📊 **Total páginas:** {total_pages}
💾 **Tamaño:** {self._format_bytes(file_size)}
📍 **Guardado:** {output_file.absolute()}"""
    
    def _split_pdf(self, input_path: str, output_path: str = None) -> str:
        """Divide PDF en páginas individuales"""
        
        pdf_file = Path(input_path)
        if not pdf_file.exists():
            return f"[x] No existe: {input_path}"
        
        reader = PdfReader(pdf_file)
        total_pages = len(reader.pages)
        
        # Directorio de salida
        if output_path:
            output_dir = Path(output_path)
        else:
            output_dir = pdf_file.parent / f"{pdf_file.stem}_split"
        
        output_dir.mkdir(exist_ok=True)
        
        # Dividir cada página
        output_files = []
        for i, page in enumerate(reader.pages, 1):
            writer = PdfWriter()
            writer.add_page(page)
            
            output_file = output_dir / f"page_{i:03d}.pdf"
            
            with open(output_file, 'wb') as f:
                writer.write(f)
            
            output_files.append(output_file.name)
        
        return f"""✅ **PDF Dividido**

📄 **Archivo:** {pdf_file.name}
📊 **Páginas:** {total_pages}
📁 **Directorio:** {output_dir.absolute()}

**Archivos generados:**
""" + "\n".join(f"  {i+1}. {name}" for i, name in enumerate(output_files[:10])) + (
    f"\n  ... y {len(output_files) - 10} más" if len(output_files) > 10 else ""
)
    
    def _extract_pages(self, input_path: str, output_path: str = None, pages: str = None) -> str:
        """Extrae páginas específicas"""
        
        pdf_file = Path(input_path)
        if not pdf_file.exists():
            return f"[x] No existe: {input_path}"
        
        if not pages:
            return "[x] Se requiere 'pages' para extract (ej: '1-5' o '1,3,5')"
        
        reader = PdfReader(pdf_file)
        total_pages = len(reader.pages)
        
        # Parsear páginas
        page_numbers = self._parse_page_range(pages, total_pages)
        
        if not page_numbers:
            return f"[x] Rango de páginas inválido: {pages}"
        
        # Crear PDF con páginas seleccionadas
        writer = PdfWriter()
        
        for page_num in sorted(page_numbers):
            if 0 <= page_num < total_pages:
                writer.add_page(reader.pages[page_num])
        
        # Generar nombre de salida
        if not output_path:
            output_path = pdf_file.parent / f"{pdf_file.stem}_extracted.pdf"
        
        output_file = Path(output_path)
        
        with open(output_file, 'wb') as f:
            writer.write(f)
        
        file_size = output_file.stat().st_size
        
        return f"""✅ **Páginas Extraídas**

📄 **Original:** {pdf_file.name} ({total_pages} páginas)
📑 **Extraídas:** {len(page_numbers)} páginas
📋 **Rango:** {pages}
💾 **Tamaño:** {self._format_bytes(file_size)}
📍 **Guardado:** {output_file.absolute()}"""
    
    def _pdf_info(self, input_path: str) -> str:
        """Obtiene información del PDF"""
        
        pdf_file = Path(input_path)
        if not pdf_file.exists():
            return f"[x] No existe: {input_path}"
        
        reader = PdfReader(pdf_file)
        
        # Información básica
        num_pages = len(reader.pages)
        file_size = pdf_file.stat().st_size
        
        # Metadata
        metadata = reader.metadata
        
        info = f"""📄 **Información del PDF**

**Archivo:** {pdf_file.name}
**Ruta:** {pdf_file.absolute()}
**Páginas:** {num_pages}
**Tamaño:** {self._format_bytes(file_size)}
"""
        
        if metadata:
            info += "\n**Metadatos:**\n"
            
            fields = {
                '/Title': 'Título',
                '/Author': 'Autor',
                '/Subject': 'Asunto',
                '/Creator': 'Creador',
                '/Producer': 'Productor',
                '/CreationDate': 'Fecha creación',
                '/ModDate': 'Fecha modificación'
            }
            
            for key, label in fields.items():
                if key in metadata and metadata[key]:
                    value = str(metadata[key])
                    # Limpiar formato de fecha
                    if 'Date' in key and value.startswith('D:'):
                        value = value[2:16]  # Simplificar
                    info += f"  **{label}:** {value}\n"
        
        # Info de primera página
        first_page = reader.pages[0]
        if hasattr(first_page, 'mediabox'):
            box = first_page.mediabox
            width = float(box.width) / 72  # Convertir a pulgadas
            height = float(box.height) / 72
            info += f"\n**Dimensiones:** {width:.2f}\" x {height:.2f}\" (primera página)"
        
        return info
    
    def _parse_page_range(self, pages_str: str, total_pages: int) -> List[int]:
        """Parsea rango de páginas: '1-5' o '1,3,5'"""
        page_numbers = set()
        
        parts = pages_str.split(',')
        
        for part in parts:
            part = part.strip()
            
            if '-' in part:
                # Rango: '1-5'
                try:
                    start, end = part.split('-')
                    start = int(start.strip()) - 1  # 0-indexed
                    end = int(end.strip())  # Inclusive
                    page_numbers.update(range(start, end))
                except:
                    continue
            else:
                # Página individual
                try:
                    page_num = int(part) - 1  # 0-indexed
                    if 0 <= page_num < total_pages:
                        page_numbers.add(page_num)
                except:
                    continue
        
        return list(page_numbers)
    
    def _format_bytes(self, bytes_size: int) -> str:
        """Formatea bytes"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. AUDIO TRANSCRIBE TOOL (Whisper)
# ═══════════════════════════════════════════════════════════════════════════════

class AudioTranscribeTool(BaseTool):
    """Transcribe audio a texto usando Whisper"""
    
    name = "audio_transcribe"
    description = """Transcribe audio a texto usando OpenAI Whisper.
    
Características:
  ‣ Múltiples idiomas
  ‣ Modelos: tiny, base, small, medium, large
  ‣ Timestamps opcionales
  ‣ Formatos: MP3, WAV, M4A, etc.
  
Modelos:
  - tiny: Rápido, menos preciso
  - base: Balance velocidad/precisión
  - small: Buena precisión
  - medium: Alta precisión
  - large: Máxima precisión (lento)"""
    
    category = "media"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "audio_path": ToolParameter(
                name="audio_path",
                type="string",
                description="Ruta del archivo de audio",
                required=True
            ),
            "model": ToolParameter(
                name="model",
                type="string",
                description="Modelo Whisper: tiny, base, small, medium, large",
                required=False,
                enum=["tiny", "base", "small", "medium", "large"]
            ),
            "language": ToolParameter(
                name="language",
                type="string",
                description="Código de idioma (ej: es, en) - auto si no se especifica",
                required=False
            ),
            "output_path": ToolParameter(
                name="output_path",
                type="string",
                description="Ruta para guardar transcripción (opcional)",
                required=False
            ),
            "timestamps": ToolParameter(
                name="timestamps",
                type="boolean",
                description="Incluir timestamps en transcripción",
                required=False
            )
        }
    
    def execute(
        self,
        audio_path: str = None,
        model: str = "base",
        language: str = None,
        output_path: str = None,
        timestamps: bool = False,
        **kwargs
    ) -> str:
        if not HAS_WHISPER:
            return "[x] Instala: pip install openai-whisper"
        
        audio_path = audio_path or kwargs.get('audio_path')
        model = model or kwargs.get('model', 'base')
        language = language or kwargs.get('language')
        output_path = output_path or kwargs.get('output_path')
        timestamps = kwargs.get('timestamps', timestamps)
        
        if not audio_path:
            return "[x] Se requiere 'audio_path'"
        
        audio_file = Path(audio_path)
        if not audio_file.exists():
            return f"[x] No existe: {audio_path}"
        
        try:
            # Cargar modelo
            print(f"⏳ Cargando modelo Whisper '{model}'...")
            model_obj = whisper.load_model(model)
            
            # Transcribir
            print(f"🎤 Transcribiendo: {audio_file.name}")
            
            transcribe_options = {}
            if language:
                transcribe_options['language'] = language
            
            result = model_obj.transcribe(str(audio_file), **transcribe_options)
            
            # Formatear resultado
            text = result['text'].strip()
            detected_language = result.get('language', 'unknown')
            
            output = f"""✅ **Audio Transcrito**

🎤 **Archivo:** {audio_file.name}
🤖 **Modelo:** {model}
🌐 **Idioma:** {detected_language}
📝 **Caracteres:** {len(text)}

**Transcripción:**
{text}
"""
            
            # Agregar timestamps si se solicitaron
            if timestamps and 'segments' in result:
                output += "\n\n**Timestamps:**\n"
                for segment in result['segments'][:10]:  # Primeros 10
                    start = segment['start']
                    end = segment['end']
                    seg_text = segment['text'].strip()
                    output += f"[{start:.1f}s - {end:.1f}s] {seg_text}\n"
                
                if len(result['segments']) > 10:
                    output += f"... y {len(result['segments']) - 10} segmentos más"
            
            # Guardar si se especificó
            if output_path:
                output_file = Path(output_path)
                
                # Guardar texto plano
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(text)
                    
                    if timestamps and 'segments' in result:
                        f.write("\n\n--- TIMESTAMPS ---\n\n")
                        for segment in result['segments']:
                            start = segment['start']
                            end = segment['end']
                            seg_text = segment['text'].strip()
                            f.write(f"[{start:.1f}s - {end:.1f}s] {seg_text}\n")
                
                output += f"\n\n📁 **Guardado en:** {output_file.absolute()}"
            
            return output
            
        except Exception as e:
            return f"[x] Error transcribiendo audio: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. QR GENERATOR TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class QRGeneratorTool(BaseTool):
    """Genera códigos QR personalizados"""
    
    name = "qr_generator"
    description = """Genera códigos QR con personalización avanzada.
    
Características:
  ‣ URL, texto, vCard, WiFi
  ‣ Colores personalizados
  ‣ Logo/imagen central
  ‣ Estilos: square, rounded, circle
  ‣ Corrección de errores configurable"""
    
    category = "media"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "data": ToolParameter(
                name="data",
                type="string",
                description="Contenido del QR (URL, texto, etc.)",
                required=True
            ),
            "output_path": ToolParameter(
                name="output_path",
                type="string",
                description="Ruta de salida para imagen QR",
                required=False
            ),
            "size": ToolParameter(
                name="size",
                type="integer",
                description="Tamaño en píxeles (default: 300)",
                required=False
            ),
            "error_correction": ToolParameter(
                name="error_correction",
                type="string",
                description="Nivel: L (7%), M (15%), Q (25%), H (30%)",
                required=False,
                enum=["L", "M", "Q", "H"]
            ),
            "fill_color": ToolParameter(
                name="fill_color",
                type="string",
                description="Color de relleno (ej: 'black', '#000000')",
                required=False
            ),
            "back_color": ToolParameter(
                name="back_color",
                type="string",
                description="Color de fondo (ej: 'white', '#FFFFFF')",
                required=False
            ),
            "style": ToolParameter(
                name="style",
                type="string",
                description="Estilo de módulos: square, rounded, circle",
                required=False,
                enum=["square", "rounded", "circle"]
            )
        }
    
    def execute(
        self,
        data: str = None,
        output_path: str = None,
        size: int = 300,
        error_correction: str = "M",
        fill_color: str = "black",
        back_color: str = "white",
        style: str = "square",
        **kwargs
    ) -> str:
        if not HAS_QRCODE:
            return "[x] Instala: pip install 'qrcode[pil]'"
        
        data = data or kwargs.get('data')
        output_path = output_path or kwargs.get('output_path')
        size = size or kwargs.get('size', 300)
        error_correction = error_correction or kwargs.get('error_correction', 'M')
        fill_color = fill_color or kwargs.get('fill_color', 'black')
        back_color = back_color or kwargs.get('back_color', 'white')
        style = style or kwargs.get('style', 'square')
        
        if not data:
            return "[x] Se requiere 'data' (contenido del QR)"
        
        try:
            # Mapear nivel de corrección de errores
            error_levels = {
                'L': qrcode.constants.ERROR_CORRECT_L,
                'M': qrcode.constants.ERROR_CORRECT_M,
                'Q': qrcode.constants.ERROR_CORRECT_Q,
                'H': qrcode.constants.ERROR_CORRECT_H
            }
            
            error_level = error_levels.get(error_correction.upper(), qrcode.constants.ERROR_CORRECT_M)
            
            # Crear QR
            qr = qrcode.QRCode(
                version=None,  # Auto
                error_correction=error_level,
                box_size=10,
                border=4
            )
            
            qr.add_data(data)
            qr.make(fit=True)
            
            # Aplicar estilo
            if style == "rounded":
                module_drawer = RoundedModuleDrawer()
            elif style == "circle":
                module_drawer = CircleModuleDrawer()
            else:
                module_drawer = None
            
            # Generar imagen
            if module_drawer:
                img = qr.make_image(
                    image_factory=StyledPilImage,
                    module_drawer=module_drawer,
                    color_mask=SolidFillColorMask(
                        back_color=back_color,
                        front_color=fill_color
                    )
                )
            else:
                img = qr.make_image(fill_color=fill_color, back_color=back_color)
            
            # Redimensionar al tamaño solicitado
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Generar nombre de salida
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"qr_{timestamp}.png"
            
            output_file = Path(output_path)
            img.save(output_file)
            
            file_size = output_file.stat().st_size
            data_preview = data if len(data) <= 50 else data[:50] + "..."
            
            return f"""✅ **Código QR Generado**

📊 **Contenido:** {data_preview}
📐 **Dimensiones:** {size}x{size}
🎨 **Estilo:** {style}
🔧 **Corrección:** {error_correction} ({['7%', '15%', '25%', '30%'][['L','M','Q','H'].index(error_correction.upper())]} errores)
🎨 **Colores:** {fill_color} / {back_color}
💾 **Tamaño:** {self._format_bytes(file_size)}
📍 **Guardado:** {output_file.absolute()}"""
            
        except Exception as e:
            return f"[x] Error generando QR: {e}"
    
    def _format_bytes(self, bytes_size: int) -> str:
        """Formatea bytes"""
        for unit in ['B', 'KB', 'MB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} GB"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. OCR EXTRACT TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class OCRExtractTool(BaseTool):
    """Extrae texto de imágenes usando OCR"""
    
    name = "ocr_extract"
    description = """Extrae texto de imágenes usando Tesseract OCR.
    
Características:
  ‣ Múltiples idiomas
  ‣ Detección de layout
  ‣ Preservar formato
  ‣ Filtros de mejora de imagen
  
Idiomas comunes:
  - eng: Inglés
  - spa: Español
  - fra: Francés
  - deu: Alemán
  - Por: Portugués"""
    
    category = "media"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "image_path": ToolParameter(
                name="image_path",
                type="string",
                description="Ruta de la imagen",
                required=True
            ),
            "language": ToolParameter(
                name="language",
                type="string",
                description="Código de idioma (ej: eng, spa, eng+spa)",
                required=False
            ),
            "output_path": ToolParameter(
                name="output_path",
                type="string",
                description="Ruta para guardar texto extraído",
                required=False
            ),
            "preprocess": ToolParameter(
                name="preprocess",
                type="boolean",
                description="Aplicar preprocesamiento de imagen para mejor OCR",
                required=False
            )
        }
    
    def execute(
        self,
        image_path: str = None,
        language: str = "eng",
        output_path: str = None,
        preprocess: bool = True,
        **kwargs
    ) -> str:
        if not HAS_TESSERACT:
            return "[x] Instala: pip install pytesseract\nY descarga Tesseract-OCR: https://github.com/tesseract-ocr/tesseract"
        
        if not HAS_PIL:
            return "[x] Instala: pip install Pillow"
        
        image_path = image_path or kwargs.get('image_path')
        language = language or kwargs.get('language', 'eng')
        output_path = output_path or kwargs.get('output_path')
        preprocess = kwargs.get('preprocess', preprocess)
        
        if not image_path:
            return "[x] Se requiere 'image_path'"
        
        image_file = Path(image_path)
        if not image_file.exists():
            return f"[x] No existe: {image_path}"
        
        try:
            # Abrir imagen
            img = Image.open(image_file)
            
            # Preprocesar si se solicitó
            if preprocess:
                img = self._preprocess_image(img)
            
            # Extraer texto
            text = pytesseract.image_to_string(img, lang=language)
            
            # Limpiar texto
            text = text.strip()
            
            if not text:
                return "⚠️ No se detectó texto en la imagen"
            
            # Estadísticas
            words = len(text.split())
            lines = len([l for l in text.split('\n') if l.strip()])
            
            result = f"""✅ **Texto Extraído por OCR**

📄 **Imagen:** {image_file.name}
🌐 **Idioma:** {language}
📊 **Estadísticas:**
  - Caracteres: {len(text)}
  - Palabras: {words}
  - Líneas: {lines}

**Texto:**
{text if len(text) <= 1000 else text[:1000] + '...'}
"""
            
            # Guardar si se especificó
            if output_path:
                output_file = Path(output_path)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(text)
                
                result += f"\n\n📁 **Guardado en:** {output_file.absolute()}"
            
            return result
            
        except pytesseract.TesseractNotFoundError:
            return "[x] Tesseract no encontrado. Instala desde: https://github.com/tesseract-ocr/tesseract"
        except Exception as e:
            return f"[x] Error extrayendo texto: {e}"
    
    def _preprocess_image(self, img: Image.Image) -> Image.Image:
        """Preprocesa imagen para mejor OCR"""
        
        # Convertir a escala de grises
        img = img.convert('L')
        
        # Aumentar contraste
        img = ImageOps.autocontrast(img)
        
        # Aplicar threshold (binarización)
        # Convertir a numpy array
        import numpy as np
        img_array = np.array(img)
        
        # Threshold adaptativo simple
        threshold = img_array.mean()
        img_array = np.where(img_array > threshold, 255, 0).astype(np.uint8)
        
        img = Image.fromarray(img_array)
        
        # Reducir ruido
        img = img.filter(ImageFilter.MedianFilter(size=3))
        
        return img


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'ImageCompressTool',
    'VideoThumbnailTool',
    'PDFMergeSplitTool',
    'AudioTranscribeTool',
    'QRGeneratorTool',
    'OCRExtractTool'
]