# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS DE GENERACIÓN DE CÓDIGO
# Scaffold, Model Generator, API Endpoint Generator, Docstring Generator
# ═══════════════════════════════════════════════════════════════════════════════

import os
import re
import ast
import textwrap
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from .base import BaseTool, ToolParameter


# ─── Utilidades compartidas ──────────────────────────────────────────────────

@dataclass
class FieldDefinition:
    """Representa un campo parseado desde la notación compacta."""
    name: str
    type: str
    nullable: bool = False
    default: Optional[str] = None
    primary_key: bool = False
    unique: bool = False
    index: bool = False
    max_length: Optional[int] = None

    # Mapeo de tipos abreviados → tipos Python / SQLAlchemy / Pydantic
    _TYPE_MAP = {
        "str":      ("str",       "String",   "str"),
        "string":   ("str",       "String",   "str"),
        "int":      ("int",       "Integer",  "int"),
        "integer":  ("int",       "Integer",  "int"),
        "float":    ("float",     "Float",    "float"),
        "bool":     ("bool",      "Boolean",  "bool"),
        "boolean":  ("bool",      "Boolean",  "bool"),
        "text":     ("str",       "Text",     "str"),
        "date":     ("date",      "Date",     "date"),
        "datetime": ("datetime",  "DateTime", "datetime"),
        "decimal":  ("Decimal",   "Numeric",  "Decimal"),
        "json":     ("dict",      "JSON",     "Any"),
        "uuid":     ("UUID",      "UUID",     "UUID"),
        "email":    ("str",       "String",   "EmailStr"),
    }

    @property
    def python_type(self) -> str:
        base = self.type.lower().rstrip("?")
        entry = self._TYPE_MAP.get(base, ("str", "String", "str"))
        t = entry[0]
        if self.nullable:
            return f"Optional[{t}]"
        return t

    @property
    def sa_column_type(self) -> str:
        base = self.type.lower().rstrip("?")
        entry = self._TYPE_MAP.get(base, ("str", "String", "str"))
        col = entry[1]
        if col == "String" and self.max_length:
            return f"String({self.max_length})"
        return col

    @property
    def pydantic_type(self) -> str:
        base = self.type.lower().rstrip("?")
        entry = self._TYPE_MAP.get(base, ("str", "String", "str"))
        t = entry[2]
        if self.nullable:
            return f"Optional[{t}]"
        return t


def parse_fields(raw: str) -> List[FieldDefinition]:
    """
    Parsea una cadena compacta de campos.

    Formatos soportados:
        "name:str, age:int, email:str?"
        "name:str:unique, id:int:pk, bio:text?"
        "name:str(100), price:decimal"
    """
    fields: List[FieldDefinition] = []

    for token in re.split(r"[,;]\s*", raw.strip()):
        token = token.strip()
        if not token:
            continue

        # Extraer modificadores después del tipo  →  name:str:pk:unique
        parts = token.split(":")
        if len(parts) < 2:
            # Solo nombre → asumir str
            parts = [parts[0], "str"]

        name = parts[0].strip()
        raw_type = parts[1].strip()
        modifiers = [p.strip().lower() for p in parts[2:]]

        # Nullable con sufijo ?
        nullable = raw_type.endswith("?")
        raw_type = raw_type.rstrip("?")

        # Max length  →  str(255)
        max_length = None
        length_match = re.match(r"(\w+)\((\d+)\)", raw_type)
        if length_match:
            raw_type = length_match.group(1)
            max_length = int(length_match.group(2))

        field = FieldDefinition(
            name=name,
            type=raw_type,
            nullable=nullable,
            primary_key="pk" in modifiers or "primary" in modifiers,
            unique="unique" in modifiers or "uq" in modifiers,
            index="index" in modifiers or "idx" in modifiers,
            max_length=max_length,
        )

        # Default
        for mod in modifiers:
            if mod.startswith("default="):
                field.default = mod.split("=", 1)[1]

        fields.append(field)

    return fields


def _snake_to_pascal(name: str) -> str:
    """user_profile → UserProfile"""
    return "".join(word.capitalize() for word in name.split("_"))


def _pascal_to_snake(name: str) -> str:
    """UserProfile → user_profile"""
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    return s.lower()


def _pluralize(word: str) -> str:
    """Pluralización básica en inglés."""
    if word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "sh", "ch", "x", "z")):
        return word + "es"
    return word + "s"


def _write_file(path: Path, content: str, overwrite: bool = False) -> bool:
    """Escribe un archivo creando directorios intermedios. Retorna si se escribió."""
    if path.exists() and not overwrite:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _file_header(description: str) -> str:
    """Cabecera estándar para archivos generados."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f'"""\n'
        f"{description}\n"
        f"Auto-generado: {ts}\n"
        f'"""\n\n'
    )


# ─── 1. SCAFFOLD TOOL ───────────────────────────────────────────────────────

class ScaffoldTool(BaseTool):
    """
    Genera la estructura completa de un proyecto Python con archivos base
    listos para usar.

    Tipos soportados: fastapi, flask, cli, library
    """

    name = "scaffold"
    description = (
        "Genera estructura completa de proyecto Python con archivos base, "
        "configuración, tests y CI. Tipos: fastapi, flask, cli, library."
    )
    category = "codegen"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "type": ToolParameter(
                name="type",
                type="string",
                description="Tipo de proyecto: fastapi | flask | cli | library",
                required=True,
            ),
            "name": ToolParameter(
                name="name",
                type="string",
                description="Nombre del proyecto (snake_case recomendado)",
                required=True,
            ),
            "output_dir": ToolParameter(
                name="output_dir",
                type="string",
                description="Directorio de salida (default: .)",
                required=False,
            ),
            "description": ToolParameter(
                name="description",
                type="string",
                description="Descripción corta del proyecto",
                required=False,
            ),
            "python_version": ToolParameter(
                name="python_version",
                type="string",
                description="Versión mínima de Python (default: 3.11)",
                required=False,
            ),
        }

    # ── Templates internos ────────────────────────────────────────────────

    _COMMON_FILES = {
        ".gitignore": textwrap.dedent("""\
            __pycache__/
            *.py[cod]
            *$py.class
            .env
            .venv/
            venv/
            dist/
            build/
            *.egg-info/
            .pytest_cache/
            .mypy_cache/
            .ruff_cache/
            htmlcov/
            .coverage
        """),
        ".env.example": textwrap.dedent("""\
            # Configuración del entorno
            APP_ENV=development
            DEBUG=true
            DATABASE_URL=sqlite:///./dev.db
            SECRET_KEY=change-me-in-production
        """),
    }

    def execute(
        self,
        type: Optional[str] = None,
        name: Optional[str] = None,
        output_dir: Optional[str] = None,
        description: Optional[str] = None,
        python_version: Optional[str] = None,
        **kwargs,
    ) -> str:
        # ── Validación ────────────────────────────────────────────────────
        if not name:
            return "❌ Se requiere un nombre de proyecto."

        project_type = (type or "library").lower().strip()
        valid_types = ("fastapi", "flask", "cli", "library")
        if project_type not in valid_types:
            return f"❌ Tipo '{project_type}' no soportado. Usa: {', '.join(valid_types)}"

        name = re.sub(r"[^a-z0-9_]", "_", name.lower().strip())
        if not name:
            return "❌ Nombre de proyecto inválido."

        desc = description or f"Proyecto {name}"
        py_ver = python_version or "3.11"
        base = Path(output_dir or ".") / name

        if base.exists():
            return f"❌ El directorio '{base}' ya existe. Elimínalo o usa otro nombre."

        # ── Generar estructura ────────────────────────────────────────────
        generator = {
            "fastapi": self._scaffold_fastapi,
            "flask":   self._scaffold_flask,
            "cli":     self._scaffold_cli,
            "library": self._scaffold_library,
        }[project_type]

        files = generator(name, desc, py_ver)

        # Archivos comunes
        files.update(self._COMMON_FILES)
        files["README.md"] = self._readme(name, desc, project_type, py_ver)
        files["pyproject.toml"] = self._pyproject(name, desc, project_type, py_ver)

        # ── Escribir archivos ─────────────────────────────────────────────
        created = []
        for rel_path, content in sorted(files.items()):
            full_path = base / rel_path
            _write_file(full_path, content)
            created.append(f"  📄 {rel_path}")

        tree = "\n".join(created)
        return (
            f"✅ Proyecto **{name}** ({project_type}) creado en `{base}`\n\n"
            f"📁 {len(created)} archivos generados:\n{tree}\n\n"
            f"▶ Siguiente paso:\n"
            f"  cd {name} && python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
        )

    # ── Generadores por tipo ──────────────────────────────────────────────

    def _scaffold_fastapi(self, name: str, desc: str, py_ver: str) -> Dict[str, str]:
        return {
            f"{name}/__init__.py": f'"""{ desc }"""\n\n__version__ = "0.1.0"\n',
            f"{name}/main.py": textwrap.dedent(f"""\
                {_file_header(f'{desc} — Aplicación FastAPI')}
                from contextlib import asynccontextmanager
                from fastapi import FastAPI
                from fastapi.middleware.cors import CORSMiddleware

                from {name}.config import settings
                from {name}.api.router import api_router


                @asynccontextmanager
                async def lifespan(app: FastAPI):
                    # Startup
                    yield
                    # Shutdown


                app = FastAPI(
                    title="{_snake_to_pascal(name)}",
                    description="{desc}",
                    version="0.1.0",
                    lifespan=lifespan,
                )

                app.add_middleware(
                    CORSMiddleware,
                    allow_origins=settings.allowed_origins,
                    allow_credentials=True,
                    allow_methods=["*"],
                    allow_headers=["*"],
                )

                app.include_router(api_router, prefix="/api/v1")


                @app.get("/health")
                async def health_check():
                    return {{"status": "healthy"}}
            """),
            f"{name}/config.py": textwrap.dedent(f"""\
                {_file_header('Configuración centralizada')}
                from functools import lru_cache
                from pydantic_settings import BaseSettings


                class Settings(BaseSettings):
                    app_env: str = "development"
                    debug: bool = True
                    database_url: str = "sqlite:///./dev.db"
                    secret_key: str = "change-me"
                    allowed_origins: list[str] = ["*"]

                    model_config = {{"env_file": ".env", "extra": "ignore"}}


                @lru_cache
                def get_settings() -> Settings:
                    return Settings()


                settings = get_settings()
            """),
            f"{name}/api/__init__.py": "",
            f"{name}/api/router.py": textwrap.dedent(f"""\
                from fastapi import APIRouter

                api_router = APIRouter()

                # Importar y registrar routers aquí:
                # from {name}.api.endpoints import items
                # api_router.include_router(items.router, prefix="/items", tags=["items"])
            """),
            f"{name}/api/endpoints/__init__.py": "",
            f"{name}/api/deps.py": textwrap.dedent(f"""\
                {_file_header('Dependencias compartidas para endpoints')}
                from typing import Annotated
                from fastapi import Depends

                from {name}.config import Settings, get_settings

                SettingsDep = Annotated[Settings, Depends(get_settings)]
            """),
            f"{name}/models/__init__.py": "",
            f"{name}/schemas/__init__.py": "",
            f"{name}/services/__init__.py": "",
            f"tests/__init__.py": "",
            f"tests/conftest.py": textwrap.dedent(f"""\
                import pytest
                from fastapi.testclient import TestClient
                from {name}.main import app


                @pytest.fixture
                def client():
                    with TestClient(app) as c:
                        yield c
            """),
            f"tests/test_health.py": textwrap.dedent("""\
                def test_health_check(client):
                    resp = client.get("/health")
                    assert resp.status_code == 200
                    assert resp.json()["status"] == "healthy"
            """),
            "Dockerfile": textwrap.dedent(f"""\
                FROM python:{py_ver}-slim AS base
                WORKDIR /app
                COPY pyproject.toml .
                RUN pip install --no-cache-dir .
                COPY . .
                EXPOSE 8000
                CMD ["uvicorn", "{name}.main:app", "--host", "0.0.0.0", "--port", "8000"]
            """),
        }

    def _scaffold_flask(self, name: str, desc: str, py_ver: str) -> Dict[str, str]:
        return {
            f"{name}/__init__.py": textwrap.dedent(f"""\
                {_file_header(f'{desc} — Aplicación Flask')}
                from flask import Flask

                __version__ = "0.1.0"


                def create_app(config_name: str = "development") -> Flask:
                    app = Flask(__name__)
                    app.config.from_object(f"{name}.config.{{config_name}}")

                    # Registrar blueprints
                    from {name}.views import main_bp
                    app.register_blueprint(main_bp)

                    return app
            """),
            f"{name}/config.py": textwrap.dedent(f"""\
                import os


                class _Base:
                    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
                    SQLALCHEMY_TRACK_MODIFICATIONS = False


                class development(_Base):
                    DEBUG = True
                    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///dev.db")


                class production(_Base):
                    DEBUG = False
                    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
            """),
            f"{name}/views/__init__.py": textwrap.dedent(f"""\
                from flask import Blueprint

                main_bp = Blueprint("main", __name__)


                @main_bp.route("/health")
                def health():
                    return {{"status": "healthy"}}
            """),
            f"{name}/models/__init__.py": "",
            f"{name}/services/__init__.py": "",
            f"tests/__init__.py": "",
            f"tests/conftest.py": textwrap.dedent(f"""\
                import pytest
                from {name} import create_app


                @pytest.fixture
                def app():
                    app = create_app("development")
                    app.config["TESTING"] = True
                    yield app


                @pytest.fixture
                def client(app):
                    return app.test_client()
            """),
            f"tests/test_health.py": textwrap.dedent("""\
                def test_health(client):
                    resp = client.get("/health")
                    assert resp.status_code == 200
            """),
        }

    def _scaffold_cli(self, name: str, desc: str, py_ver: str) -> Dict[str, str]:
        return {
            f"{name}/__init__.py": f'"""{ desc }"""\n\n__version__ = "0.1.0"\n',
            f"{name}/__main__.py": textwrap.dedent(f"""\
                from {name}.cli import app

                app()
            """),
            f"{name}/cli.py": textwrap.dedent(f"""\
                {_file_header(f'{desc} — CLI con Typer')}
                from typing import Annotated, Optional
                import typer

                app = typer.Typer(
                    name="{name}",
                    help="{desc}",
                    add_completion=False,
                )


                @app.command()
                def hello(
                    name: Annotated[str, typer.Argument(help="Tu nombre")] = "mundo",
                    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
                ):
                    \"\"\"Saluda al usuario.\"\"\"
                    msg = f"¡Hola, {{name}}!"
                    if verbose:
                        msg += " (modo verbose activado)"
                    typer.echo(msg)


                if __name__ == "__main__":
                    app()
            """),
            f"{name}/config.py": textwrap.dedent(f"""\
                from pathlib import Path

                APP_DIR = Path.home() / ".{name}"
                APP_DIR.mkdir(exist_ok=True)

                CONFIG_FILE = APP_DIR / "config.toml"
            """),
            f"tests/__init__.py": "",
            f"tests/test_cli.py": textwrap.dedent(f"""\
                from typer.testing import CliRunner
                from {name}.cli import app

                runner = CliRunner()


                def test_hello_default():
                    result = runner.invoke(app, ["hello"])
                    assert result.exit_code == 0
                    assert "Hola" in result.stdout
            """),
        }

    def _scaffold_library(self, name: str, desc: str, py_ver: str) -> Dict[str, str]:
        return {
            f"src/{name}/__init__.py": textwrap.dedent(f"""\
                \"\"\"{desc}\"\"\"

                __version__ = "0.1.0"

                __all__: list[str] = []
            """),
            f"src/{name}/core.py": textwrap.dedent(f"""\
                {_file_header(f'{desc} — Módulo principal')}

                # Implementa aquí la lógica principal de la librería.
            """),
            f"src/{name}/exceptions.py": textwrap.dedent(f"""\
                class {_snake_to_pascal(name)}Error(Exception):
                    \"\"\"Error base de {name}.\"\"\"
            """),
            f"src/{name}/py.typed": "",  # PEP 561 marker
            f"tests/__init__.py": "",
            f"tests/test_core.py": textwrap.dedent(f"""\
                from {name} import __version__


                def test_version():
                    assert __version__ == "0.1.0"
            """),
            f"docs/index.md": f"# {_snake_to_pascal(name)}\n\n{desc}\n",
        }

    # ── Archivos transversales ────────────────────────────────────────────

    def _pyproject(self, name: str, desc: str, ptype: str, py_ver: str) -> str:
        deps = {
            "fastapi": '"fastapi>=0.115", "uvicorn[standard]>=0.34", "pydantic-settings>=2"',
            "flask":   '"flask>=3"',
            "cli":     '"typer>=0.15"',
            "library": "",
        }
        extras_test = '"pytest>=8", "pytest-cov>=6"'
        if ptype == "fastapi":
            extras_test += ', "httpx>=0.28"'

        pkg_dir = 'src' if ptype == "library" else ''
        packages_line = (
            f'[tool.setuptools.packages.find]\nwhere = ["src"]'
            if ptype == "library"
            else ""
        )

        scripts = ""
        if ptype == "cli":
            scripts = f'\n[project.scripts]\n{name} = "{name}.cli:app"\n'

        return textwrap.dedent(f"""\
            [build-system]
            requires = ["setuptools>=75", "wheel"]
            build-backend = "setuptools.build_meta"

            [project]
            name = "{name}"
            version = "0.1.0"
            description = "{desc}"
            requires-python = ">={py_ver}"
            dependencies = [{deps[ptype]}]

            [project.optional-dependencies]
            dev = [{extras_test}, "ruff>=0.9", "mypy>=1.14"]
            {scripts}
            {packages_line}

            [tool.pytest.ini_options]
            testpaths = ["tests"]
            addopts = "-v --tb=short"

            [tool.ruff]
            target-version = "py{py_ver.replace('.', '')}"
            line-length = 100

            [tool.ruff.lint]
            select = ["E", "F", "W", "I", "N", "UP", "B", "SIM"]

            [tool.mypy]
            python_version = "{py_ver}"
            strict = true
        """)

    def _readme(self, name: str, desc: str, ptype: str, py_ver: str) -> str:
        pascal = _snake_to_pascal(name)
        run_cmd = {
            "fastapi": f"uvicorn {name}.main:app --reload",
            "flask":   f"flask --app {name} run --debug",
            "cli":     f"python -m {name} --help",
            "library": f"python -c \"import {name}; print({name}.__version__)\"",
        }
        return textwrap.dedent(f"""\
            # {pascal}

            {desc}

            ## Requisitos

            - Python ≥ {py_ver}

            ## Instalación

            ```bash
            python -m venv .venv
            source .venv/bin/activate
            pip install -e ".[dev]"
            ```

            ## Uso

            ```bash
            {run_cmd[ptype]}
            ```

            ## Tests

            ```bash
            pytest
            ```
        """)


# ─── 2. MODEL GENERATOR TOOL ────────────────────────────────────────────────

class ModelGeneratorTool(BaseTool):
    """
    Genera modelos de datos para SQLAlchemy (2.0), Pydantic v2 o Django ORM,
    incluyendo schemas de validación y migraciones básicas.
    """

    name = "generate_model"
    description = (
        "Genera modelos de datos (SQLAlchemy 2.0, Pydantic v2, Django). "
        "Campos en formato 'name:str, age:int, email:str?:unique'."
    )
    category = "codegen"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "name": ToolParameter(
                name="name",
                type="string",
                description="Nombre del modelo (PascalCase o snake_case)",
                required=True,
            ),
            "fields": ToolParameter(
                name="fields",
                type="string",
                description="Campos: 'name:str, age:int, email:str?:unique, price:decimal'",
                required=True,
            ),
            "orm": ToolParameter(
                name="orm",
                type="string",
                description="ORM: sqlalchemy (default) | pydantic | django | all",
                required=False,
            ),
            "output": ToolParameter(
                name="output",
                type="string",
                description="Archivo de salida (default: imprime en consola)",
                required=False,
            ),
            "timestamps": ToolParameter(
                name="timestamps",
                type="boolean",
                description="Agregar created_at / updated_at (default: true)",
                required=False,
            ),
        }

    def execute(
        self,
        name: Optional[str] = None,
        fields: Optional[str] = None,
        orm: str = "sqlalchemy",
        output: Optional[str] = None,
        timestamps: bool = True,
        **kwargs,
    ) -> str:
        if not name or not fields:
            return "❌ Se requieren 'name' y 'fields'."

        pascal = _snake_to_pascal(name) if "_" in name else name
        snake = _pascal_to_snake(name) if name[0].isupper() else name
        table = _pluralize(snake)

        try:
            parsed = parse_fields(fields)
        except Exception as e:
            return f"❌ Error parseando campos: {e}"

        if not parsed:
            return "❌ No se detectaron campos válidos."

        orm = orm.lower().strip()
        generators = {
            "sqlalchemy": self._gen_sqlalchemy,
            "pydantic":   self._gen_pydantic,
            "django":     self._gen_django,
        }

        if orm == "all":
            parts = [gen(pascal, snake, table, parsed, timestamps) for gen in generators.values()]
            code = "\n\n".join(parts)
        elif orm in generators:
            code = generators[orm](pascal, snake, table, parsed, timestamps)
        else:
            return f"❌ ORM '{orm}' no soportado. Usa: {', '.join(generators)} o 'all'."

        # Escribir a archivo si se pide
        if output:
            path = Path(output)
            _write_file(path, code, overwrite=True)
            return f"✅ Modelo **{pascal}** ({orm}) escrito en `{path}`\n\n```python\n{code}\n```"

        return f"✅ Modelo **{pascal}** generado ({orm}):\n\n```python\n{code}\n```"

    # ── Generador SQLAlchemy 2.0 (Mapped) ─────────────────────────────────

    def _gen_sqlalchemy(
        self, pascal: str, snake: str, table: str,
        fields: List[FieldDefinition], timestamps: bool,
    ) -> str:
        imports = {
            "from __future__ import annotations",
            "from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column",
        }
        sa_type_imports: set[str] = set()

        lines = []
        for f in fields:
            sa_type_imports.add(f.sa_column_type.split("(")[0])

            parts_col: list[str] = []
            if f.primary_key:
                parts_col.append("primary_key=True")
            if f.unique:
                parts_col.append("unique=True")
            if f.index:
                parts_col.append("index=True")
            if f.nullable:
                parts_col.append("nullable=True")
            if f.default is not None:
                parts_col.append(f"default={f.default}")

            col_args = ", ".join(parts_col)
            mapped_type = f.python_type

            if col_args:
                lines.append(f"    {f.name}: Mapped[{mapped_type}] = mapped_column({col_args})")
            else:
                lines.append(f"    {f.name}: Mapped[{mapped_type}] = mapped_column()")

        if timestamps:
            imports.add("from datetime import datetime")
            lines.append("")
            lines.append(
                "    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)"
            )
            lines.append(
                "    updated_at: Mapped[datetime] = mapped_column("
                "default=datetime.utcnow, onupdate=datetime.utcnow"
                ")"
            )

        # Agregar import de tipos SA usados
        if sa_type_imports:
            imports.add(f"from sqlalchemy import {', '.join(sorted(sa_type_imports))}")
        if any(f.nullable for f in fields):
            imports.add("from typing import Optional")
        if any(f.type.lower() in ("uuid",) for f in fields):
            imports.add("from uuid import UUID")
        if any(f.type.lower() in ("decimal",) for f in fields):
            imports.add("from decimal import Decimal")
        if any(f.type.lower() in ("date",) for f in fields):
            imports.add("from datetime import date")

        col_block = "\n".join(lines)
        import_block = "\n".join(sorted(imports))

        return textwrap.dedent(f"""\
            {import_block}


            class Base(DeclarativeBase):
                pass


            class {pascal}(Base):
                \"\"\"Modelo {pascal}.\"\"\"

                __tablename__ = "{table}"

                id: Mapped[int] = mapped_column(primary_key=True)
            {col_block}

                def __repr__(self) -> str:
                    return f"<{pascal}(id={{self.id}})>"
        """)

    # ── Generador Pydantic v2 ─────────────────────────────────────────────

    def _gen_pydantic(
        self, pascal: str, snake: str, table: str,
        fields: List[FieldDefinition], timestamps: bool,
    ) -> str:
        imports = {"from pydantic import BaseModel, ConfigDict"}
        lines_base = []
        lines_create = []
        lines_read = []

        for f in fields:
            ptype = f.pydantic_type
            default = ""

            if f.type.lower() == "email":
                imports.add("from pydantic import EmailStr")
            if f.nullable:
                imports.add("from typing import Optional")
                default = " = None"
            if f.default is not None:
                default = f" = {f.default}"
            if "date" in f.type.lower():
                imports.add("from datetime import datetime, date")
            if f.type.lower() == "uuid":
                imports.add("from uuid import UUID")
            if f.type.lower() == "decimal":
                imports.add("from decimal import Decimal")

            lines_base.append(f"    {f.name}: {ptype}{default}")
            if not f.primary_key:
                lines_create.append(f"    {f.name}: {ptype}{default}")

        lines_read.append("    id: int")
        if timestamps:
            imports.add("from datetime import datetime")
            lines_read.append("    created_at: datetime")
            lines_read.append("    updated_at: datetime")

        base_block = "\n".join(lines_base)
        create_block = "\n".join(lines_create) if lines_create else "    pass"
        read_block = "\n".join(lines_read)

        import_block = "\n".join(sorted(imports))

        return textwrap.dedent(f"""\
            {import_block}


            class {pascal}Base(BaseModel):
                \"\"\"Campos compartidos de {pascal}.\"\"\"
            {base_block}


            class {pascal}Create({pascal}Base):
                \"\"\"Schema para creación.\"\"\"
            {create_block}


            class {pascal}Update({pascal}Base):
                \"\"\"Schema para actualización (todos opcionales).\"\"\"
                model_config = ConfigDict(extra="forbid")
                # Tip: puedes hacer todos los campos Optional aquí para PATCH.


            class {pascal}Read({pascal}Base):
                \"\"\"Schema de lectura con id y timestamps.\"\"\"
                model_config = ConfigDict(from_attributes=True)
            {read_block}
        """)

    # ── Generador Django ──────────────────────────────────────────────────

    def _gen_django(
        self, pascal: str, snake: str, table: str,
        fields: List[FieldDefinition], timestamps: bool,
    ) -> str:
        _DJANGO_MAP = {
            "str": "CharField", "string": "CharField", "text": "TextField",
            "int": "IntegerField", "integer": "IntegerField",
            "float": "FloatField", "bool": "BooleanField", "boolean": "BooleanField",
            "date": "DateField", "datetime": "DateTimeField",
            "decimal": "DecimalField", "json": "JSONField", "uuid": "UUIDField",
            "email": "EmailField",
        }

        lines = []
        for f in fields:
            if f.primary_key:
                continue  # Django genera pk automáticamente

            base_type = f.type.lower().rstrip("?")
            django_field = _DJANGO_MAP.get(base_type, "CharField")

            args: list[str] = []
            if django_field == "CharField":
                ml = f.max_length or 255
                args.append(f"max_length={ml}")
            if django_field == "DecimalField":
                args.append("max_digits=10")
                args.append("decimal_places=2")
            if f.nullable:
                args.append("null=True")
                args.append("blank=True")
            if f.unique:
                args.append("unique=True")
            if f.index:
                args.append("db_index=True")
            if f.default is not None:
                args.append(f"default={f.default}")

            args_str = ", ".join(args)
            lines.append(f"    {f.name} = models.{django_field}({args_str})")

        if timestamps:
            lines.append("")
            lines.append("    created_at = models.DateTimeField(auto_now_add=True)")
            lines.append("    updated_at = models.DateTimeField(auto_now=True)")

        field_block = "\n".join(lines)

        return textwrap.dedent(f"""\
            from django.db import models


            class {pascal}(models.Model):
                \"\"\"Modelo {pascal}.\"\"\"

            {field_block}

                class Meta:
                    db_table = "{table}"
                    ordering = ["-created_at"]

                def __str__(self) -> str:
                    return f"{pascal} #{{self.pk}}"
        """)


# ─── 3. API ENDPOINT GENERATOR TOOL ─────────────────────────────────────────

class APIEndpointGeneratorTool(BaseTool):
    """
    Genera endpoints CRUD completos para un recurso REST,
    incluyendo router, schemas y servicio.
    """

    name = "generate_endpoint"
    description = (
        "Genera endpoints CRUD (Create, Read, Update, Delete, List) "
        "para FastAPI o Flask, incluyendo schemas y servicio."
    )
    category = "codegen"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "resource": ToolParameter(
                name="resource",
                type="string",
                description="Nombre del recurso (ej: 'user', 'product')",
                required=True,
            ),
            "fields": ToolParameter(
                name="fields",
                type="string",
                description="Campos (opcional): 'name:str, price:float, active:bool'",
                required=False,
            ),
            "framework": ToolParameter(
                name="framework",
                type="string",
                description="Framework: fastapi (default) | flask",
                required=False,
            ),
            "output_dir": ToolParameter(
                name="output_dir",
                type="string",
                description="Directorio para escribir archivos",
                required=False,
            ),
            "auth": ToolParameter(
                name="auth",
                type="boolean",
                description="Incluir dependencia de autenticación (default: false)",
                required=False,
            ),
        }

    def execute(
        self,
        resource: Optional[str] = None,
        fields: Optional[str] = None,
        framework: str = "fastapi",
        output_dir: Optional[str] = None,
        auth: bool = False,
        **kwargs,
    ) -> str:
        if not resource:
            return "❌ Se requiere el nombre del recurso."

        snake = _pascal_to_snake(resource) if resource[0].isupper() else resource
        snake = re.sub(r"[^a-z0-9_]", "_", snake.lower())
        pascal = _snake_to_pascal(snake)
        plural = _pluralize(snake)

        parsed = parse_fields(fields) if fields else []

        framework = framework.lower().strip()
        if framework == "fastapi":
            result = self._gen_fastapi_crud(pascal, snake, plural, parsed, auth)
        elif framework == "flask":
            result = self._gen_flask_crud(pascal, snake, plural, parsed, auth)
        else:
            return f"❌ Framework '{framework}' no soportado. Usa: fastapi, flask."

        if output_dir:
            base = Path(output_dir)
            written = []
            for filename, content in result.items():
                path = base / filename
                _write_file(path, content, overwrite=True)
                written.append(f"  📄 {path}")
            file_list = "\n".join(written)
            return (
                f"✅ CRUD para **{pascal}** ({framework}) generado:\n{file_list}"
            )

        # Retornar código concatenado
        blocks = []
        for filename, content in result.items():
            blocks.append(f"# ── {filename} ──\n\n{content}")
        code = "\n\n".join(blocks)
        return f"✅ CRUD para **{pascal}** ({framework}):\n\n```python\n{code}\n```"

    # ── FastAPI CRUD ──────────────────────────────────────────────────────

    def _gen_fastapi_crud(
        self, pascal: str, snake: str, plural: str,
        fields: List[FieldDefinition], auth: bool,
    ) -> Dict[str, str]:
        # ── Schemas ───────────────────────────────────────────────────────
        if fields:
            field_lines = "\n".join(
                f"    {f.name}: {f.pydantic_type}"
                + (" = None" if f.nullable else "")
                for f in fields
            )
            optional_lines = "\n".join(
                f"    {f.name}: Optional[{f.pydantic_type.replace('Optional[', '').rstrip(']')}] = None"
                for f in fields
            )
        else:
            field_lines = "    pass  # TODO: agregar campos"
            optional_lines = "    pass  # TODO: agregar campos"

        schemas_code = textwrap.dedent(f"""\
            from __future__ import annotations
            from typing import Optional
            from pydantic import BaseModel, ConfigDict


            class {pascal}Create(BaseModel):
                \"\"\"Schema para crear {snake}.\"\"\"
            {field_lines}


            class {pascal}Update(BaseModel):
                \"\"\"Schema para actualizar {snake} (parcial).\"\"\"
            {optional_lines}


            class {pascal}Read(BaseModel):
                \"\"\"Schema de respuesta.\"\"\"
                model_config = ConfigDict(from_attributes=True)

                id: int
            {field_lines}
        """)

        # ── Router ────────────────────────────────────────────────────────
        auth_import = ""
        auth_dep = ""
        if auth:
            auth_import = "\nfrom ..deps import get_current_user\n"
            auth_dep = ", current_user=Depends(get_current_user)"

        router_code = textwrap.dedent(f"""\
            from __future__ import annotations
            from typing import Annotated
            from fastapi import APIRouter, Depends, HTTPException, Query, status
            {auth_import}
            from .schemas_{snake} import {pascal}Create, {pascal}Update, {pascal}Read

            router = APIRouter(prefix="/{plural}", tags=["{plural}"])


            # ── Fake in-memory store (reemplazar con DB real) ──
            _store: dict[int, dict] = {{}}
            _next_id = 1


            @router.get("/", response_model=list[{pascal}Read])
            async def list_{plural}(
                skip: int = Query(0, ge=0),
                limit: int = Query(20, ge=1, le=100),{auth_dep}
            ):
                \"\"\"Listar {plural} con paginación.\"\"\"
                items = list(_store.values())
                return items[skip : skip + limit]


            @router.get("/{{item_id}}", response_model={pascal}Read)
            async def get_{snake}(item_id: int{auth_dep}):
                \"\"\"Obtener un {snake} por ID.\"\"\"
                if item_id not in _store:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, f"{pascal} {{item_id}} no encontrado")
                return _store[item_id]


            @router.post("/", response_model={pascal}Read, status_code=status.HTTP_201_CREATED)
            async def create_{snake}(body: {pascal}Create{auth_dep}):
                \"\"\"Crear un nuevo {snake}.\"\"\"
                global _next_id
                data = {{"id": _next_id, **body.model_dump()}}
                _store[_next_id] = data
                _next_id += 1
                return data


            @router.patch("/{{item_id}}", response_model={pascal}Read)
            async def update_{snake}(item_id: int, body: {pascal}Update{auth_dep}):
                \"\"\"Actualizar parcialmente un {snake}.\"\"\"
                if item_id not in _store:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, f"{pascal} {{item_id}} no encontrado")
                stored = _store[item_id]
                updates = body.model_dump(exclude_unset=True)
                stored.update(updates)
                return stored


            @router.delete("/{{item_id}}", status_code=status.HTTP_204_NO_CONTENT)
            async def delete_{snake}(item_id: int{auth_dep}):
                \"\"\"Eliminar un {snake}.\"\"\"
                if item_id not in _store:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, f"{pascal} {{item_id}} no encontrado")
                del _store[item_id]
        """)

        # ── Test ──────────────────────────────────────────────────────────
        test_code = textwrap.dedent(f"""\
            import pytest
            from fastapi.testclient import TestClient


            class Test{pascal}CRUD:
                \"\"\"Tests para el CRUD de {pascal}.\"\"\"

                def test_create(self, client: TestClient):
                    resp = client.post("/api/v1/{plural}/", json={{}})
                    assert resp.status_code == 201
                    assert "id" in resp.json()

                def test_list(self, client: TestClient):
                    resp = client.get("/api/v1/{plural}/")
                    assert resp.status_code == 200
                    assert isinstance(resp.json(), list)

                def test_get_not_found(self, client: TestClient):
                    resp = client.get("/api/v1/{plural}/99999")
                    assert resp.status_code == 404

                def test_delete(self, client: TestClient):
                    create = client.post("/api/v1/{plural}/", json={{}})
                    item_id = create.json()["id"]
                    resp = client.delete(f"/api/v1/{plural}/{{item_id}}")
                    assert resp.status_code == 204
        """)

        return {
            f"schemas_{snake}.py": schemas_code,
            f"router_{snake}.py": router_code,
            f"test_{snake}.py": test_code,
        }

    # ── Flask CRUD ────────────────────────────────────────────────────────

    def _gen_flask_crud(
        self, pascal: str, snake: str, plural: str,
        fields: List[FieldDefinition], auth: bool,
    ) -> Dict[str, str]:
        auth_decorator = ""
        if auth:
            auth_decorator = "    # @login_required  # TODO: descomentar cuando auth esté listo\n"

        bp_code = textwrap.dedent(f"""\
            from flask import Blueprint, jsonify, request, abort

            {snake}_bp = Blueprint("{plural}", __name__, url_prefix="/{plural}")

            # ── Fake in-memory store (reemplazar con DB real) ──
            _store: dict[int, dict] = {{}}
            _next_id = 1


            @{snake}_bp.get("/")
            def list_{plural}():
                \"\"\"Listar {plural}.\"\"\"
            {auth_decorator}    skip = request.args.get("skip", 0, type=int)
                limit = request.args.get("limit", 20, type=int)
                items = list(_store.values())[skip : skip + limit]
                return jsonify(items)


            @{snake}_bp.get("/<int:item_id>")
            def get_{snake}(item_id: int):
                \"\"\"Obtener un {snake}.\"\"\"
            {auth_decorator}    if item_id not in _store:
                    abort(404)
                return jsonify(_store[item_id])


            @{snake}_bp.post("/")
            def create_{snake}():
                \"\"\"Crear un {snake}.\"\"\"
            {auth_decorator}    global _next_id
                data = request.get_json(force=True)
                data["id"] = _next_id
                _store[_next_id] = data
                _next_id += 1
                return jsonify(data), 201


            @{snake}_bp.patch("/<int:item_id>")
            def update_{snake}(item_id: int):
                \"\"\"Actualizar un {snake}.\"\"\"
            {auth_decorator}    if item_id not in _store:
                    abort(404)
                data = request.get_json(force=True)
                _store[item_id].update(data)
                return jsonify(_store[item_id])


            @{snake}_bp.delete("/<int:item_id>")
            def delete_{snake}(item_id: int):
                \"\"\"Eliminar un {snake}.\"\"\"
            {auth_decorator}    if item_id not in _store:
                    abort(404)
                del _store[item_id]
                return "", 204
        """)

        return {f"views_{snake}.py": bp_code}


# ─── 4. DOCSTRING GENERATOR TOOL ────────────────────────────────────────────

class DocstringGeneratorTool(BaseTool):
    """
    Analiza archivos Python con AST y genera docstrings Google-style
    para funciones, métodos y clases que carezcan de ellos.
    """

    name = "generate_docstrings"
    description = (
        "Analiza código Python y genera docstrings Google-style para "
        "funciones, métodos y clases sin documentar."
    )
    category = "codegen"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(
                name="path",
                type="string",
                description="Archivo o directorio Python",
                required=True,
            ),
            "style": ToolParameter(
                name="style",
                type="string",
                description="Estilo: google (default) | numpy | sphinx",
                required=False,
            ),
            "overwrite": ToolParameter(
                name="overwrite",
                type="boolean",
                description="Sobrescribir docstrings existentes (default: false)",
                required=False,
            ),
            "dry_run": ToolParameter(
                name="dry_run",
                type="boolean",
                description="Solo mostrar sin modificar archivos (default: true)",
                required=False,
            ),
        }

    def execute(
        self,
        path: Optional[str] = None,
        style: str = "google",
        overwrite: bool = False,
        dry_run: bool = True,
        **kwargs,
    ) -> str:
        if not path:
            return "❌ Se requiere 'path'."

        target = Path(path)
        style = style.lower().strip()
        if style not in ("google", "numpy", "sphinx"):
            return f"❌ Estilo '{style}' no soportado. Usa: google, numpy, sphinx."

        if target.is_file():
            files = [target] if target.suffix == ".py" else []
        elif target.is_dir():
            files = sorted(target.rglob("*.py"))
        else:
            return f"❌ Ruta no encontrada: {target}"

        if not files:
            return f"❌ No se encontraron archivos .py en {target}"

        total_added = 0
        results: list[str] = []

        for file in files:
            try:
                source = file.read_text(encoding="utf-8")
                new_source, count = self._process_file(source, style, overwrite)
            except SyntaxError as e:
                results.append(f"  ⚠️  {file}: error de sintaxis — {e}")
                continue

            if count == 0:
                results.append(f"  ✔️  {file}: ya documentado")
                continue

            total_added += count

            if dry_run:
                results.append(f"  📝 {file}: {count} docstrings por agregar")
            else:
                file.write_text(new_source, encoding="utf-8")
                results.append(f"  ✅ {file}: {count} docstrings agregados")

        detail = "\n".join(results)
        mode = "DRY RUN" if dry_run else "APLICADO"
        return (
            f"📖 Docstrings — {mode} ({style}-style)\n"
            f"   Archivos analizados: {len(files)}\n"
            f"   Docstrings {'por agregar' if dry_run else 'agregados'}: {total_added}\n\n"
            f"{detail}"
        )

    def _process_file(
        self, source: str, style: str, overwrite: bool
    ) -> Tuple[str, int]:
        """Procesa un archivo y retorna (nuevo_source, cantidad_docstrings_agregados)."""
        tree = ast.parse(source)
        lines = source.splitlines(keepends=True)

        insertions: List[Tuple[int, str]] = []  # (line_number, docstring)

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue

            existing = ast.get_docstring(node)
            if existing and not overwrite:
                continue

            docstring = self._build_docstring(node, style)
            if not docstring:
                continue

            # Calcular la línea de inserción y la indentación
            if node.body:
                first = node.body[0]
                # Si ya tiene docstring y overwrite=True → reemplazar
                if (
                    existing
                    and overwrite
                    and isinstance(first, ast.Expr)
                    and isinstance(first.value, (ast.Constant, ast.Str))
                ):
                    # Marcar para reemplazo
                    insert_line = first.lineno - 1
                    end_line = first.end_lineno or first.lineno
                    indent = self._get_indent(lines, first.lineno - 1)
                    formatted = self._indent_docstring(docstring, indent)
                    # Reemplazar líneas existentes
                    for i in range(insert_line, end_line):
                        lines[i] = ""
                    lines[insert_line] = formatted + "\n"
                    insertions.append((insert_line, ""))  # conteo
                    continue

                insert_line = first.lineno - 1
            else:
                insert_line = node.lineno

            indent = self._get_indent(lines, node.lineno - 1) + "    "
            formatted = self._indent_docstring(docstring, indent)
            insertions.append((insert_line, formatted + "\n"))

        if not insertions:
            return source, 0

        # Insertar de abajo hacia arriba para no alterar los índices
        for line_no, text in sorted(insertions, key=lambda x: x[0], reverse=True):
            if text:  # Solo insertar si no es reemplazo
                lines.insert(line_no, text)

        return "".join(lines), len(insertions)

    def _build_docstring(
        self, node: ast.AST, style: str
    ) -> Optional[str]:
        """Construye un docstring basado en el nodo AST."""
        if isinstance(node, ast.ClassDef):
            return self._docstring_for_class(node, style)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self._docstring_for_function(node, style)
        return None

    def _docstring_for_class(self, node: ast.ClassDef, style: str) -> str:
        bases = [self._get_name(b) for b in node.bases]
        base_info = f" Hereda de: {', '.join(bases)}." if bases else ""

        attrs = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                ann = self._annotation_str(item.annotation)
                attrs.append((item.target.id, ann))

        if style == "google":
            lines = [f"{node.name}.{base_info}"]
            if attrs:
                lines.append("")
                lines.append("Attributes:")
                for name, ann in attrs:
                    lines.append(f"    {name} ({ann}): TODO.")
            return "\n".join(lines)

        elif style == "numpy":
            lines = [f"{node.name}.{base_info}"]
            if attrs:
                lines.append("")
                lines.append("Attributes")
                lines.append("----------")
                for name, ann in attrs:
                    lines.append(f"{name} : {ann}")
                    lines.append("    TODO.")
            return "\n".join(lines)

        else:  # sphinx
            lines = [f"{node.name}.{base_info}"]
            for name, ann in attrs:
                lines.append(f":param {name}: TODO.")
                lines.append(f":type {name}: {ann}")
            return "\n".join(lines)

    def _docstring_for_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, style: str
    ) -> str:
        # Recoger argumentos (excluir self/cls)
        args_info: List[Tuple[str, str, Optional[str]]] = []
        args = node.args

        all_args = args.args + args.posonlyargs
        defaults_offset = len(all_args) - len(args.defaults)

        for i, arg in enumerate(all_args):
            if arg.arg in ("self", "cls"):
                continue
            ann = self._annotation_str(arg.annotation) if arg.annotation else "Any"
            default = None
            di = i - defaults_offset
            if di >= 0 and di < len(args.defaults):
                default = self._default_str(args.defaults[di])
            args_info.append((arg.arg, ann, default))

        # *args
        if args.vararg:
            ann = self._annotation_str(args.vararg.annotation) if args.vararg.annotation else "Any"
            args_info.append((f"*{args.vararg.arg}", ann, None))

        # **kwargs
        for arg in args.kwonlyargs:
            ann = self._annotation_str(arg.annotation) if arg.annotation else "Any"
            args_info.append((arg.arg, ann, None))

        if args.kwarg:
            ann = self._annotation_str(args.kwarg.annotation) if args.kwarg.annotation else "Any"
            args_info.append((f"**{args.kwarg.arg}", ann, None))

        # Return type
        returns = self._annotation_str(node.returns) if node.returns else None

        # Detectar raises
        raises: List[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Raise) and child.exc:
                exc_name = self._get_name(child.exc)
                if exc_name and exc_name not in raises:
                    raises.append(exc_name)

        # Determinar si es property, async, etc.
        prefix = ""
        is_async = isinstance(node, ast.AsyncFunctionDef)
        if is_async:
            prefix = "(async) "

        description = f"{prefix}{self._humanize_name(node.name)}."

        # Formatear según estilo
        if style == "google":
            return self._format_google(description, args_info, returns, raises)
        elif style == "numpy":
            return self._format_numpy(description, args_info, returns, raises)
        else:
            return self._format_sphinx(description, args_info, returns, raises)

    # ── Formateadores de estilo ───────────────────────────────────────────

    def _format_google(
        self, desc: str, args: list, returns: Optional[str], raises: list
    ) -> str:
        lines = [desc]
        if args:
            lines.append("")
            lines.append("Args:")
            for name, ann, default in args:
                d = f" Defaults to {default}." if default else ""
                lines.append(f"    {name} ({ann}): TODO.{d}")
        if returns and returns != "None":
            lines.append("")
            lines.append("Returns:")
            lines.append(f"    {returns}: TODO.")
        if raises:
            lines.append("")
            lines.append("Raises:")
            for exc in raises:
                lines.append(f"    {exc}: TODO.")
        return "\n".join(lines)

    def _format_numpy(
        self, desc: str, args: list, returns: Optional[str], raises: list
    ) -> str:
        lines = [desc]
        if args:
            lines.append("")
            lines.append("Parameters")
            lines.append("----------")
            for name, ann, default in args:
                d = f", default {default}" if default else ""
                lines.append(f"{name} : {ann}{d}")
                lines.append("    TODO.")
        if returns and returns != "None":
            lines.append("")
            lines.append("Returns")
            lines.append("-------")
            lines.append(f"{returns}")
            lines.append("    TODO.")
        if raises:
            lines.append("")
            lines.append("Raises")
            lines.append("------")
            for exc in raises:
                lines.append(exc)
                lines.append("    TODO.")
        return "\n".join(lines)

    def _format_sphinx(
        self, desc: str, args: list, returns: Optional[str], raises: list
    ) -> str:
        lines = [desc]
        if args:
            lines.append("")
            for name, ann, default in args:
                d = f" Defaults to {default}." if default else ""
                lines.append(f":param {name}: TODO.{d}")
                lines.append(f":type {name}: {ann}")
        if returns and returns != "None":
            lines.append(f":returns: TODO.")
            lines.append(f":rtype: {returns}")
        if raises:
            for exc in raises:
                lines.append(f":raises {exc}: TODO.")
        return "\n".join(lines)

    # ── Helpers AST ───────────────────────────────────────────────────────

    @staticmethod
    def _annotation_str(node: Optional[ast.AST]) -> str:
        """Convierte un nodo de anotación AST a string legible."""
        if node is None:
            return "Any"
        return ast.unparse(node)

    @staticmethod
    def _default_str(node: ast.AST) -> str:
        """Convierte un nodo de default AST a string."""
        return ast.unparse(node)

    @staticmethod
    def _get_name(node: ast.AST) -> str:
        """Extrae un nombre legible de un nodo AST."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return DocstringGeneratorTool._get_name(node.func)
        return ast.unparse(node)

    @staticmethod
    def _get_indent(lines: list, line_no: int) -> str:
        """Obtiene la indentación de una línea."""
        if line_no < len(lines):
            match = re.match(r"^(\s*)", lines[line_no])
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _indent_docstring(docstring: str, indent: str) -> str:
        """Envuelve un docstring con triple-comillas e indentación."""
        doc_lines = docstring.split("\n")
        if len(doc_lines) == 1:
            return f'{indent}"""{doc_lines[0]}"""'

        result = [f'{indent}"""{ doc_lines[0]}']
        for line in doc_lines[1:]:
            if line.strip():
                result.append(f"{indent}{line}")
            else:
                result.append("")
        result.append(f'{indent}"""')
        return "\n".join(result)

    @staticmethod
    def _humanize_name(name: str) -> str:
        """Convierte snake_case a una descripción legible."""
        name = name.lstrip("_")
        words = name.split("_")
        if not words:
            return "TODO"
        words[0] = words[0].capitalize()
        return " ".join(words)