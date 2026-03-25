# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS DE DOCUMENTACIÓN
# Markdown to HTML, Changelog Generator, API Documentation
# ═══════════════════════════════════════════════════════════════════════════════

import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

from .base import BaseTool, ToolParameter


class MarkdownToHTMLTool(BaseTool):
    # Convierte archivos Markdown a HTML con temas.
    #
    # Genera HTML standalone con estilos incluidos.
    
    name = "markdown_to_html"
    description = """Convierte Markdown a HTML con estilos.

Temas disponibles:
- github: Estilo GitHub
- dark: Tema oscuro
- minimal: Minimalista
- docs: Estilo documentación

Ejemplo: input="README.md", output="docs/index.html", theme="github"
"""
    category = "docs"
    
    THEMES = {
        "github": '''
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; color: #24292e; }
h1, h2, h3 { border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
h1 { font-size: 2em; }
h2 { font-size: 1.5em; }
code { background: #f6f8fa; padding: 0.2em 0.4em; border-radius: 3px; font-size: 85%; }
pre { background: #f6f8fa; padding: 16px; overflow: auto; border-radius: 6px; }
pre code { background: none; padding: 0; }
blockquote { border-left: 4px solid #dfe2e5; margin: 0; padding-left: 16px; color: #6a737d; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #dfe2e5; padding: 8px 12px; }
th { background: #f6f8fa; }
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }
img { max-width: 100%; }
''',
        "dark": '''
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; background: #0d1117; color: #c9d1d9; }
h1, h2, h3 { border-bottom: 1px solid #21262d; padding-bottom: 0.3em; color: #f0f6fc; }
code { background: #161b22; padding: 0.2em 0.4em; border-radius: 3px; color: #79c0ff; }
pre { background: #161b22; padding: 16px; overflow: auto; border-radius: 6px; }
pre code { background: none; }
blockquote { border-left: 4px solid #3b434b; margin: 0; padding-left: 16px; color: #8b949e; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #21262d; padding: 8px 12px; }
th { background: #161b22; }
a { color: #58a6ff; }
''',
        "minimal": '''
body { font-family: Georgia, serif; line-height: 1.8; max-width: 700px; margin: 40px auto; padding: 20px; color: #333; }
h1, h2, h3 { font-weight: normal; }
code { font-family: 'Courier New', monospace; background: #f5f5f5; padding: 2px 5px; }
pre { background: #f5f5f5; padding: 15px; overflow: auto; }
blockquote { font-style: italic; border-left: 3px solid #ccc; margin-left: 0; padding-left: 20px; }
a { color: #0066cc; }
''',
        "docs": '''
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.7; margin: 0; padding: 0; display: flex; }
.sidebar { width: 250px; background: #f5f5f5; padding: 20px; position: fixed; height: 100vh; overflow-y: auto; }
.content { margin-left: 290px; padding: 40px; max-width: 800px; }
h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
h2 { color: #34495e; margin-top: 40px; }
code { background: #ecf0f1; padding: 2px 6px; border-radius: 3px; color: #e74c3c; }
pre { background: #2c3e50; color: #ecf0f1; padding: 20px; border-radius: 5px; overflow-x: auto; }
pre code { background: none; color: inherit; }
table { width: 100%; border-collapse: collapse; margin: 20px 0; }
th { background: #3498db; color: white; padding: 12px; text-align: left; }
td { padding: 10px; border-bottom: 1px solid #ddd; }
'''
    }
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "input": ToolParameter(
                name="input",
                type="string",
                description="Archivo Markdown de entrada",
                required=True
            ),
            "output": ToolParameter(
                name="output",
                type="string",
                description="Archivo HTML de salida",
                required=False
            ),
            "theme": ToolParameter(
                name="theme",
                type="string",
                description="Tema: github, dark, minimal, docs",
                required=False,
                enum=["github", "dark", "minimal", "docs"]
            ),
            "title": ToolParameter(
                name="title",
                type="string",
                description="Título del documento HTML",
                required=False
            ),
            "toc": ToolParameter(
                name="toc",
                type="boolean",
                description="Generar tabla de contenidos (default: true)",
                required=False
            )
        }
    
    def execute(
        self,
        input: str = None,
        output: str = None,
        theme: str = "github",
        title: str = None,
        toc: bool = True,
        **kwargs
    ) -> str:
        input_file = input or kwargs.get('input', '')
        output_file = output or kwargs.get('output', None)
        theme = theme or kwargs.get('theme', 'github')
        title = title or kwargs.get('title', None)
        toc = toc if toc is not None else kwargs.get('toc', True)
        
        if not input_file:
            return "❌ Se requiere 'input'"
        
        input_path = Path(input_file)
        if not input_path.exists():
            return f"❌ Archivo no existe: {input_file}"
        
        try:
            md_content = input_path.read_text(encoding='utf-8')
        except Exception as e:
            return f"❌ Error leyendo: {e}"
        
        # Convertir Markdown a HTML
        html_body = self._convert_markdown(md_content)
        
        # Generar TOC si se solicita
        toc_html = ""
        if toc:
            toc_html = self._generate_toc(md_content)
        
        # Título
        if not title:
            title_match = re.search(r'^#\s+(.+)$', md_content, re.MULTILINE)
            title = title_match.group(1) if title_match else input_path.stem
        
        # CSS
        css = self.THEMES.get(theme, self.THEMES["github"])
        
        # Construir HTML
        if theme == "docs" and toc_html:
            html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>{css}</style>
</head>
<body>
    <nav class="sidebar">
        <h3>Contenido</h3>
        {toc_html}
    </nav>
    <main class="content">
        {html_body}
    </main>
</body>
</html>'''
        else:
            toc_section = f'<nav class="toc"><h2>Contenido</h2>{toc_html}</nav>' if toc_html else ''
            html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>{css}</style>
</head>
<body>
    {toc_section}
    {html_body}
    <footer style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 0.9em;">
        Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')}
    </footer>
</body>
</html>'''
        
        # Guardar
        if not output_file:
            output_file = input_path.with_suffix('.html')
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding='utf-8')
        
        return f"""✅ **HTML Generado**

| Propiedad | Valor |
|-----------|-------|
| Entrada | `{input_file}` |
| Salida | `{output_path}` |
| Tema | {theme} |
| TOC | {'Sí' if toc else 'No'} |
| Tamaño | {len(html):,} bytes |

💡 Abre `{output_path}` en tu navegador.
"""
    
    def _convert_markdown(self, md: str) -> str:
        # Conversión básica de Markdown a HTML
        html = md
        
        # Escapar HTML existente
        html = html.replace('&', '&amp;')
        html = html.replace('<', '&lt;')
        html = html.replace('>', '&gt;')
        
        # Code blocks (antes de otras conversiones)
        def code_block_replace(match):
            lang = match.group(1) or ''
            code = match.group(2)
            return f'<pre><code class="language-{lang}">{code}</code></pre>'
        
        html = re.sub(r'```(\w*)\n(.*?)```', code_block_replace, html, flags=re.DOTALL)
        
        # Inline code
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        
        # Headers
        html = re.sub(r'^######\s+(.+)$', r'<h6>\1</h6>', html, flags=re.MULTILINE)
        html = re.sub(r'^#####\s+(.+)$', r'<h5>\1</h5>', html, flags=re.MULTILINE)
        html = re.sub(r'^####\s+(.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        
        # Bold and italic
        html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        
        # Links
        html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
        
        # Images
        html = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1">', html)
        
        # Blockquotes
        html = re.sub(r'^>\s+(.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
        
        # Horizontal rules
        html = re.sub(r'^---+$', r'<hr>', html, flags=re.MULTILINE)
        
        # Unordered lists
        def ul_replace(match):
            items = re.findall(r'^\s*[-*]\s+(.+)$', match.group(0), re.MULTILINE)
            li_items = ''.join(f'<li>{item}</li>' for item in items)
            return f'<ul>{li_items}</ul>'
        
        html = re.sub(r'((?:^\s*[-*]\s+.+$\n?)+)', ul_replace, html, flags=re.MULTILINE)
        
        # Ordered lists
        def ol_replace(match):
            items = re.findall(r'^\s*\d+\.\s+(.+)$', match.group(0), re.MULTILINE)
            li_items = ''.join(f'<li>{item}</li>' for item in items)
            return f'<ol>{li_items}</ol>'
        
        html = re.sub(r'((?:^\s*\d+\.\s+.+$\n?)+)', ol_replace, html, flags=re.MULTILINE)
        
        # Tables
        def table_replace(match):
            lines = match.group(0).strip().split('\n')
            if len(lines) < 2:
                return match.group(0)
            
            # Header
            headers = [h.strip() for h in lines[0].split('|') if h.strip()]
            thead = '<tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr>'
            
            # Body
            tbody_rows = []
            for line in lines[2:]:
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if cells:
                    tbody_rows.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
            
            tbody = ''.join(tbody_rows)
            
            return f'<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>'
        
        html = re.sub(r'(\|.+\|\n\|[-:\s|]+\|\n(?:\|.+\|\n?)+)', table_replace, html)
        
        # Paragraphs
        paragraphs = html.split('\n\n')
        processed = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith('<'):
                p = f'<p>{p}</p>'
            processed.append(p)
        
        html = '\n\n'.join(processed)
        
        return html
    
    def _generate_toc(self, md: str) -> str:
        headers = re.findall(r'^(#{1,3})\s+(.+)$', md, re.MULTILINE)
        
        if not headers:
            return ""
        
        toc_items = []
        for level, text in headers:
            depth = len(level)
            slug = re.sub(r'[^\w\s-]', '', text.lower()).replace(' ', '-')
            indent = '  ' * (depth - 1)
            toc_items.append(f'{indent}<li><a href="#{slug}">{text}</a></li>')
        
        return '<ul class="toc-list">\n' + '\n'.join(toc_items) + '\n</ul>'


class ChangelogGeneratorTool(BaseTool):
    # Genera CHANGELOG.md desde commits de Git.
    #
    # Agrupa commits por tipo (feat, fix, docs, etc.)
    
    name = "generate_changelog"
    description = """Genera CHANGELOG.md desde commits de Git.

Agrupa commits por tipo según Conventional Commits:
- feat: Nuevas funcionalidades
- fix: Correcciones de bugs
- docs: Documentación
- style: Formateo
- refactor: Refactoring
- test: Tests
- chore: Mantenimiento

Ejemplo: from_tag="v1.0.0", to_tag="HEAD"
"""
    category = "docs"
    
    COMMIT_TYPES = {
        'feat': '✨ Features',
        'fix': '🐛 Bug Fixes',
        'docs': '📚 Documentation',
        'style': '💅 Styles',
        'refactor': '♻️ Refactoring',
        'perf': '⚡ Performance',
        'test': '✅ Tests',
        'build': '🔧 Build',
        'ci': '👷 CI/CD',
        'chore': '🔨 Chores',
        'revert': '⏪ Reverts'
    }
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "from_tag": ToolParameter(
                name="from_tag",
                type="string",
                description="Tag o commit inicial (ej: v1.0.0)",
                required=False
            ),
            "to_tag": ToolParameter(
                name="to_tag",
                type="string",
                description="Tag o commit final (default: HEAD)",
                required=False
            ),
            "output": ToolParameter(
                name="output",
                type="string",
                description="Archivo de salida (default: CHANGELOG.md)",
                required=False
            ),
            "version": ToolParameter(
                name="version",
                type="string",
                description="Versión para el changelog",
                required=False
            ),
            "append": ToolParameter(
                name="append",
                type="boolean",
                description="Añadir al CHANGELOG existente",
                required=False
            )
        }
    
    def execute(
        self,
        from_tag: str = None,
        to_tag: str = "HEAD",
        output: str = "CHANGELOG.md",
        version: str = None,
        append: bool = True,
        **kwargs
    ) -> str:
        from_tag = from_tag or kwargs.get('from_tag', None)
        to_tag = to_tag or kwargs.get('to_tag', 'HEAD')
        output = output or kwargs.get('output', 'CHANGELOG.md')
        version = version or kwargs.get('version', None)
        append = append if append is not None else kwargs.get('append', True)
        
        # Verificar que es repo git
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return "❌ No es un repositorio Git"
        
        # Obtener commits
        if from_tag:
            commit_range = f"{from_tag}..{to_tag}"
        else:
            commit_range = to_tag
        
        result = subprocess.run(
            ["git", "log", commit_range, "--pretty=format:%H|%s|%an|%ad", "--date=short"],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            return f"❌ Error obteniendo commits: {result.stderr}"
        
        if not result.stdout.strip():
            return "ℹ️ No hay commits en el rango especificado"
        
        # Parsear commits
        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|')
            if len(parts) >= 4:
                commits.append({
                    'hash': parts[0],
                    'message': parts[1],
                    'author': parts[2],
                    'date': parts[3]
                })
        
        # Categorizar commits
        categorized = defaultdict(list)
        uncategorized = []
        
        for commit in commits:
            msg = commit['message']
            
            # Intentar parsear conventional commit
            match = re.match(r'^(\w+)(?:\(([^)]+)\))?:\s*(.+)$', msg)
            
            if match:
                commit_type = match.group(1).lower()
                scope = match.group(2)
                description = match.group(3)
                
                if commit_type in self.COMMIT_TYPES:
                    categorized[commit_type].append({
                        'scope': scope,
                        'description': description,
                        'hash': commit['hash'][:7],
                        'author': commit['author']
                    })
                else:
                    uncategorized.append(commit)
            else:
                uncategorized.append(commit)
        
        # Generar markdown
        version_str = version or to_tag
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        changelog = f"## [{version_str}] - {date_str}\n\n"
        
        for commit_type, type_title in self.COMMIT_TYPES.items():
            if commit_type in categorized:
                changelog += f"### {type_title}\n\n"
                for c in categorized[commit_type]:
                    scope_str = f"**{c['scope']}:** " if c['scope'] else ""
                    changelog += f"- {scope_str}{c['description']} ([{c['hash']}])\n"
                changelog += "\n"
        
        if uncategorized:
            changelog += "### 📝 Other Changes\n\n"
            for c in uncategorized[:10]:
                changelog += f"- {c['message'][:60]} ([{c['hash'][:7]}])\n"
            if len(uncategorized) > 10:
                changelog += f"- ... and {len(uncategorized) - 10} more\n"
            changelog += "\n"
        
        # Guardar
        output_path = Path(output)
        
        if append and output_path.exists():
            existing = output_path.read_text()
            # Insertar después del título
            if existing.startswith('# '):
                title_end = existing.find('\n\n')
                if title_end > 0:
                    new_content = existing[:title_end + 2] + changelog + existing[title_end + 2:]
                else:
                    new_content = existing + '\n\n' + changelog
            else:
                new_content = changelog + '\n' + existing
        else:
            new_content = f"# Changelog\n\nAll notable changes to this project.\n\n{changelog}"
        
        output_path.write_text(new_content)
        
        # Estadísticas
        total_commits = len(commits)
        categorized_count = sum(len(c) for c in categorized.values())
        
        return f"""✅ **Changelog Generado**

| Propiedad | Valor |
|-----------|-------|
| Versión | {version_str} |
| Rango | {from_tag or 'inicio'} → {to_tag} |
| Commits totales | {total_commits} |
| Categorizados | {categorized_count} |
| Archivo | `{output}` |

**Por categoría:**
{chr(10).join([f"- {self.COMMIT_TYPES[t]}: {len(c)}" for t, c in categorized.items()])}

💡 Usa Conventional Commits para mejor categorización:
   `feat: add new feature`
   `fix(auth): resolve login issue`
"""


class APIDocumentationTool(BaseTool):
    # Genera documentación de API en formato Markdown.
    #
    # Extrae información de código fuente.
    
    name = "document_api"
    description = """Genera documentación de API desde código fuente.

Analiza archivos Python y extrae:
- Funciones públicas con docstrings
- Clases y sus métodos
- Parámetros y tipos
- Ejemplos de uso

Formatos de salida: markdown, html

Ejemplo: path="src/api.py", format="markdown"
"""
    category = "docs"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(
                name="path",
                type="string",
                description="Archivo o directorio a documentar",
                required=True
            ),
            "format": ToolParameter(
                name="format",
                type="string",
                description="Formato: markdown, html",
                required=False,
                enum=["markdown", "html"]
            ),
            "output": ToolParameter(
                name="output",
                type="string",
                description="Archivo de salida",
                required=False
            ),
            "include_private": ToolParameter(
                name="include_private",
                type="boolean",
                description="Incluir funciones privadas (_func)",
                required=False
            ),
            "include_source": ToolParameter(
                name="include_source",
                type="boolean",
                description="Incluir código fuente",
                required=False
            )
        }
    
    def execute(
        self,
        path: str = None,
        format: str = "markdown",
        output: str = None,
        include_private: bool = False,
        include_source: bool = False,
        **kwargs
    ) -> str:
        import ast
        
        path = path or kwargs.get('path', '')
        format = format or kwargs.get('format', 'markdown')
        output = output or kwargs.get('output', None)
        include_private = include_private or kwargs.get('include_private', False)
        include_source = include_source or kwargs.get('include_source', False)
        
        if not path:
            return "❌ Se requiere 'path'"
        
        source_path = Path(path)
        if not source_path.exists():
            return f"❌ Ruta no existe: {path}"
        
        # Obtener archivos
        if source_path.is_file():
            files = [source_path]
        else:
            files = list(source_path.rglob("*.py"))
        
        # Extraer documentación
        all_docs = []
        
        for file_path in files:
            try:
                content = file_path.read_text()
                tree = ast.parse(content)
                
                file_doc = {
                    'path': str(file_path),
                    'module_doc': ast.get_docstring(tree),
                    'classes': [],
                    'functions': []
                }
                
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.ClassDef):
                        if not include_private and node.name.startswith('_'):
                            continue
                        
                        class_doc = self._extract_class(node, content, include_private, include_source)
                        file_doc['classes'].append(class_doc)
                    
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not include_private and node.name.startswith('_'):
                            continue
                        
                        func_doc = self._extract_function(node, content, include_source)
                        file_doc['functions'].append(func_doc)
                
                if file_doc['classes'] or file_doc['functions'] or file_doc['module_doc']:
                    all_docs.append(file_doc)
                    
            except Exception as e:
                continue
        
        if not all_docs:
            return f"⚠️ No se encontró documentación en {path}"
        
        # Generar salida
        if format == "markdown":
            doc_content = self._generate_markdown_docs(all_docs)
        else:
            doc_content = self._generate_html_docs(all_docs)
        
        # Guardar
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(doc_content)
        
        # Estadísticas
        total_classes = sum(len(d['classes']) for d in all_docs)
        total_functions = sum(len(d['functions']) for d in all_docs)
        total_methods = sum(
            len(c['methods']) for d in all_docs for c in d['classes']
        )
        
        result = f"""✅ **Documentación Generada**

| Propiedad | Valor |
|-----------|-------|
| Archivos | {len(all_docs)} |
| Clases | {total_classes} |
| Funciones | {total_functions} |
| Métodos | {total_methods} |
| Formato | {format} |
{"| Salida | `" + output + "` |" if output else ""}

"""
        
        if not output:
            result += f"**Preview:**\n\n```markdown\n{doc_content[:1500]}...\n```"
        
        return result
    
    def _extract_class(self, node, content: str, include_private: bool, include_source: bool) -> Dict:
        import ast
        
        class_doc = {
            'name': node.name,
            'docstring': ast.get_docstring(node),
            'bases': [ast.unparse(b) for b in node.bases],
            'methods': []
        }
        
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not include_private and item.name.startswith('_') and item.name != '__init__':
                    continue
                
                method_doc = self._extract_function(item, content, include_source)
                class_doc['methods'].append(method_doc)
        
        return class_doc
    
    def _extract_function(self, node, content: str, include_source: bool) -> Dict:
        import ast
        
        # Parámetros
        params = []
        for arg in node.args.args:
            param = {'name': arg.arg}
            if arg.annotation:
                param['type'] = ast.unparse(arg.annotation)
            params.append(param)
        
        # Return type
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)
        
        func_doc = {
            'name': node.name,
            'docstring': ast.get_docstring(node),
            'params': params,
            'return_type': return_type,
            'is_async': isinstance(node, ast.AsyncFunctionDef),
            'decorators': [ast.unparse(d) for d in node.decorator_list]
        }
        
        if include_source:
            func_doc['source'] = ast.unparse(node)
        
        return func_doc
    
    def _generate_markdown_docs(self, all_docs: List[Dict]) -> str:
        md = "# API Documentation\n\n"
        md += f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"
        md += "---\n\n"
        
        for doc in all_docs:
            md += f"## 📄 {doc['path']}\n\n"
            
            if doc['module_doc']:
                md += f"{doc['module_doc']}\n\n"
            
            # Clases
            for cls in doc['classes']:
                bases_str = f"({', '.join(cls['bases'])})" if cls['bases'] else ""
                md += f"### 📦 class `{cls['name']}`{bases_str}\n\n"
                
                if cls['docstring']:
                    md += f"{cls['docstring']}\n\n"
                
                if cls['methods']:
                    md += "**Methods:**\n\n"
                    for method in cls['methods']:
                        md += self._format_function_md(method, indent="  ")
            
            # Funciones
            if doc['functions']:
                md += "### ⚡ Functions\n\n"
                for func in doc['functions']:
                    md += self._format_function_md(func)
            
            md += "---\n\n"
        
        return md
    
    def _format_function_md(self, func: Dict, indent: str = "") -> str:
        async_str = "async " if func['is_async'] else ""
        
        # Signature
        params_str = ", ".join(
            f"{p['name']}: {p.get('type', 'Any')}" for p in func['params']
        )
        return_str = f" -> {func['return_type']}" if func['return_type'] else ""
        
        md = f"{indent}#### `{async_str}{func['name']}({params_str}){return_str}`\n\n"
        
        # Decorators
        if func['decorators']:
            md += f"{indent}*Decorators: {', '.join(func['decorators'])}*\n\n"
        
        # Docstring
        if func['docstring']:
            for line in func['docstring'].split('\n'):
                md += f"{indent}{line}\n"
            md += "\n"
        
        # Source
        if func.get('source'):
            md += f"{indent}```python\n{func['source']}\n{indent}```\n\n"
        
        return md
    
    def _generate_html_docs(self, all_docs: List[Dict]) -> str:
        html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>API Documentation</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }
        h1 { border-bottom: 2px solid #333; }
        h2 { color: #2c3e50; margin-top: 40px; }
        h3 { color: #3498db; }
        code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }
        pre { background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 5px; overflow-x: auto; }
        .docstring { color: #666; font-style: italic; }
        .function { margin: 20px 0; padding: 15px; border-left: 3px solid #3498db; background: #f9f9f9; }
        .class { margin: 30px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>API Documentation</h1>
'''
        
        for doc in all_docs:
            html += f'<h2>📄 {doc["path"]}</h2>\n'
            
            if doc['module_doc']:
                html += f'<p class="docstring">{doc["module_doc"]}</p>\n'
            
            for cls in doc['classes']:
                html += f'<div class="class">\n'
                html += f'<h3>📦 class {cls["name"]}</h3>\n'
                if cls['docstring']:
                    html += f'<p class="docstring">{cls["docstring"]}</p>\n'
                
                for method in cls['methods']:
                    html += f'<div class="function">\n'
                    html += f'<code>{method["name"]}()</code>\n'
                    if method['docstring']:
                        html += f'<p class="docstring">{method["docstring"][:200]}</p>\n'
                    html += '</div>\n'
                
                html += '</div>\n'
            
            for func in doc['functions']:
                html += f'<div class="function">\n'
                html += f'<h4>⚡ {func["name"]}()</h4>\n'
                if func['docstring']:
                    html += f'<p class="docstring">{func["docstring"]}</p>\n'
                html += '</div>\n'
        
        html += '</body></html>'
        return html