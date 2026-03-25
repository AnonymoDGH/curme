# NVIDIA CODE - Herramientas de Proyectos

from pathlib import Path
from typing import Dict
from .base import BaseTool, ToolParameter


class CreateDirectoryTool(BaseTool):
    # Crea un directorio
    
    name = "create_directory"
    description = "Crea un nuevo directorio"
    category = "project"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(name="path", type="string", description="Ruta del directorio", required=True)
        }
    
    def execute(self, **kwargs) -> str:
        path = kwargs.get('path', '')
        
        if not path:
            return "[x] Se requiere 'path'"
        
        try:
            dir_path = Path(path)
            dir_path.mkdir(parents=True, exist_ok=True)
            return f"[OK] Directorio creado: {dir_path.absolute()}"
        except Exception as e:
            return f"[x] Error: {e}"


class CreateProjectTool(BaseTool):
    # Crea estructura de proyecto
    
    name = "create_project"
    description = "Crea la estructura de un proyecto"
    category = "project"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "name": ToolParameter(name="name", type="string", description="Nombre del proyecto", required=True),
            "type": ToolParameter(name="type", type="string", description="Tipo de proyecto", required=False, enum=["python", "node", "fastapi", "flask", "react", "basic"])
        }
    
    def execute(self, **kwargs) -> str:
        project_name = kwargs.get('name', '')
        project_type = kwargs.get('type', 'basic')
        
        if not project_name:
            return "[x] Se requiere 'name'"
        
        try:
            base = Path(project_name)
            
            if base.exists():
                return f"[x] Ya existe: {project_name}"
            
            base.mkdir(parents=True)
            
            if project_type == "python":
                (base / "src").mkdir()
                (base / "tests").mkdir()
                (base / "src" / "__init__.py").write_text("")
                (base / "tests" / "__init__.py").write_text("")
                (base / "README.md").write_text(f"# {project_name}\n")
                (base / "requirements.txt").write_text("")
                (base / ".gitignore").write_text("__pycache__/\n*.pyc\nvenv/\n.env\n")
                
                main_py = "# Main module\n\ndef main():\n    print('Hello!')\n\nif __name__ == '__main__':\n    main()\n"
                (base / "src" / "main.py").write_text(main_py)
            
            elif project_type == "fastapi":
                (base / "app").mkdir()
                (base / "app" / "__init__.py").write_text("")
                (base / "tests").mkdir()
                (base / "README.md").write_text(f"# {project_name}\n\nFastAPI project\n")
                (base / "requirements.txt").write_text("fastapi\nuvicorn\n")
                (base / ".gitignore").write_text("__pycache__/\n*.pyc\nvenv/\n.env\n")
                
                main_py = 'from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/")\ndef root():\n    return {"message": "Hello"}\n'
                (base / "app" / "main.py").write_text(main_py)
            
            elif project_type == "flask":
                (base / "app").mkdir()
                (base / "app" / "__init__.py").write_text("")
                (base / "templates").mkdir()
                (base / "static").mkdir()
                (base / "README.md").write_text(f"# {project_name}\n\nFlask project\n")
                (base / "requirements.txt").write_text("flask\n")
                
                app_py = 'from flask import Flask\n\napp = Flask(__name__)\n\n@app.route("/")\ndef index():\n    return "Hello!"\n\nif __name__ == "__main__":\n    app.run(debug=True)\n'
                (base / "app" / "main.py").write_text(app_py)
            
            elif project_type == "node":
                (base / "src").mkdir()
                (base / "tests").mkdir()
                (base / "README.md").write_text(f"# {project_name}\n")
                (base / ".gitignore").write_text("node_modules/\n.env\n")
                
                pkg = '{\n  "name": "' + project_name + '",\n  "version": "1.0.0",\n  "main": "src/index.js"\n}\n'
                (base / "package.json").write_text(pkg)
                (base / "src" / "index.js").write_text('console.log("Hello!");\n')
            
            elif project_type == "react":
                (base / "src").mkdir()
                (base / "public").mkdir()
                (base / "README.md").write_text(f"# {project_name}\n\nReact project\n")
                (base / ".gitignore").write_text("node_modules/\nbuild/\n.env\n")
                
                pkg = '{\n  "name": "' + project_name + '",\n  "version": "1.0.0",\n  "scripts": {\n    "dev": "vite",\n    "build": "vite build"\n  }\n}\n'
                (base / "package.json").write_text(pkg)
            
            else:
                # basic
                (base / "src").mkdir()
                (base / "README.md").write_text(f"# {project_name}\n")
                (base / ".gitignore").write_text("")
            
            return f"[OK] Proyecto '{project_name}' creado (tipo: {project_type})"
            
        except Exception as e:
            return f"[x] Error: {e}"