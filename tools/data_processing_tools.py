# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS DE PROCESAMIENTO DE DATOS
# CSV Transform, Validación, Visualización, Conversión de formatos
# ═══════════════════════════════════════════════════════════════════════════════

import csv
import io
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .base import BaseTool, ToolParameter

try:
    import xml.etree.ElementTree as ET

    HAS_XML = True
except ImportError:
    HAS_XML = False

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ─── Utilidades compartidas ──────────────────────────────────────────────────


def _load_data(source: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """
    Carga datos desde archivo o string inline.

    Retorna (filas, columnas, formato_detectado).
    """
    path = Path(source)

    if path.exists() and path.is_file():
        raw = path.read_text(encoding="utf-8")
        suffix = path.suffix.lower()
    else:
        raw = source.strip()
        suffix = _detect_format(raw)

    if suffix in (".csv", "csv"):
        return _parse_csv(raw)
    elif suffix in (".json", "json"):
        return _parse_json(raw)
    elif suffix in (".xml", "xml") and HAS_XML:
        return _parse_xml(raw)
    elif suffix in (".yaml", ".yml", "yaml") and HAS_YAML:
        return _parse_yaml(raw)

    # Intentar CSV como fallback
    try:
        return _parse_csv(raw)
    except Exception:
        return [], [], "unknown"


def _detect_format(raw: str) -> str:
    """Detecta el formato de un string de datos."""
    stripped = raw.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    if stripped.startswith("<?xml") or stripped.startswith("<"):
        return "xml"
    if ":" in stripped.split("\n")[0] and not "," in stripped.split("\n")[0]:
        return "yaml"
    return "csv"


def _parse_csv(raw: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """Parsea CSV desde string."""
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    columns = reader.fieldnames or []
    return rows, list(columns), "csv"


def _parse_json(raw: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """Parsea JSON (lista de objetos o objeto único)."""
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return [], [], "json"
    columns = []
    if data:
        # Unión de todas las keys
        seen: set[str] = set()
        for row in data:
            if isinstance(row, dict):
                for k in row:
                    if k not in seen:
                        columns.append(k)
                        seen.add(k)
    return data, columns, "json"


def _parse_xml(raw: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """Parsea XML a lista de dicts (primer nivel de hijos)."""
    root = ET.fromstring(raw)
    rows = []
    columns_set: set[str] = set()
    columns: list[str] = []

    for child in root:
        row: Dict[str, Any] = {"_tag": child.tag}
        row.update(child.attrib)
        for sub in child:
            row[sub.tag] = (sub.text or "").strip()
        for k in row:
            if k not in columns_set:
                columns.append(k)
                columns_set.add(k)
        rows.append(row)

    return rows, columns, "xml"


def _parse_yaml(raw: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """Parsea YAML a lista de dicts."""
    data = yaml.safe_load(raw)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return [], [], "yaml"
    columns: list[str] = []
    seen: set[str] = set()
    for row in data:
        if isinstance(row, dict):
            for k in row:
                if k not in seen:
                    columns.append(k)
                    seen.add(k)
    return data, columns, "yaml"


def _coerce_number(value: Any) -> Optional[float]:
    """Intenta convertir un valor a número."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    return None


def _write_output(
    rows: List[Dict[str, Any]],
    columns: List[str],
    path: Optional[str],
    fmt: str = "csv",
) -> Optional[str]:
    """Escribe datos a archivo. Retorna path si se escribió."""
    if not path:
        return None

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    suffix = out.suffix.lower()
    if suffix in (".json",) or fmt == "json":
        out.write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    elif suffix in (".csv",) or fmt == "csv":
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    else:
        out.write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    return str(out)


# ─── 1. CSV TRANSFORM TOOL ──────────────────────────────────────────────────


class CSVTransformTool(BaseTool):
    """
    Transforma datos tabulares con un pipeline de operaciones encadenadas.

    Operaciones soportadas:
        - filter:   filtra filas (field=value, field>value, field~=regex)
        - sort:     ordena por columnas (col:asc, col:desc)
        - select:   selecciona columnas
        - rename:   renombra columnas (old→new)
        - drop:     elimina columnas
        - add:      agrega columna calculada
        - dedup:    elimina duplicados
        - head/tail: primeras/últimas N filas
        - group:    agrupa y agrega (sum, avg, count, min, max)
        - fill:     rellena valores nulos
        - replace:  buscar y reemplazar en valores
        - cast:     convierte tipos de columna
    """

    name = "csv_transform"
    description = (
        "Transforma datos CSV/JSON con un pipeline de operaciones: "
        "filter, sort, select, rename, drop, add, dedup, head, tail, "
        "group, fill, replace, cast."
    )
    category = "data"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "input": ToolParameter(
                name="input",
                type="string",
                description="Archivo CSV/JSON o datos inline",
                required=True,
            ),
            "operations": ToolParameter(
                name="operations",
                type="array",
                description=(
                    "Lista de operaciones. Cada una es un dict con 'op' y parámetros. "
                    "Ej: [{'op':'filter','field':'age','gt':18}, {'op':'sort','by':'name'}]"
                ),
                required=True,
            ),
            "output": ToolParameter(
                name="output",
                type="string",
                description="Archivo de salida (opcional, default: muestra resultado)",
                required=False,
            ),
            "format": ToolParameter(
                name="format",
                type="string",
                description="Formato de salida: csv | json (default: csv)",
                required=False,
            ),
            "preview": ToolParameter(
                name="preview",
                type="integer",
                description="Cantidad de filas a mostrar en preview (default: 10)",
                required=False,
            ),
        }

    # ── Dispatch de operaciones ───────────────────────────────────────────

    _OPERATORS: Dict[str, Callable] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def execute(
        self,
        input: Optional[str] = None,
        operations: Optional[List[Dict[str, Any]]] = None,
        output: Optional[str] = None,
        format: str = "csv",
        preview: int = 10,
        **kwargs,
    ) -> str:
        input_src = input or kwargs.get("input", "")
        operations = operations or kwargs.get("operations", [])
        output = output or kwargs.get("output")

        if not input_src:
            return "❌ Se requiere 'input' (archivo o datos inline)."
        if not operations:
            return "❌ Se requiere al menos una operación."

        # ── Cargar datos ──────────────────────────────────────────────────
        try:
            rows, columns, src_fmt = _load_data(input_src)
        except Exception as e:
            return f"❌ Error cargando datos: {e}"

        if not rows:
            return "❌ No se encontraron datos para procesar."

        original_count = len(rows)
        log: List[str] = []

        # ── Pipeline de operaciones ───────────────────────────────────────
        for i, op_def in enumerate(operations, 1):
            if isinstance(op_def, str):
                # Soporte para formato simplificado: "filter:age>18"
                op_def = self._parse_shorthand(op_def)

            if not isinstance(op_def, dict):
                log.append(f"  ⚠️  Op {i}: formato inválido, ignorada")
                continue

            op_name = op_def.get("op", "").lower().strip()
            handler = getattr(self, f"_op_{op_name}", None)

            if not handler:
                log.append(f"  ⚠️  Op {i}: '{op_name}' no reconocida")
                continue

            try:
                rows, columns, msg = handler(rows, columns, op_def)
                log.append(f"  ✅ Op {i} ({op_name}): {msg}")
            except Exception as e:
                log.append(f"  ❌ Op {i} ({op_name}): error — {e}")

        # ── Salida ────────────────────────────────────────────────────────
        written = _write_output(rows, columns, output, format)

        # Generar preview
        preview_text = self._format_preview(rows, columns, preview)

        pipeline_log = "\n".join(log)
        result = (
            f"📊 **CSV Transform**\n\n"
            f"- Entrada: `{input_src}` ({src_fmt})\n"
            f"- Filas: {original_count} → {len(rows)}\n"
            f"- Columnas: {len(columns)} ({', '.join(columns[:8])}"
            f"{'...' if len(columns) > 8 else ''})\n\n"
            f"**Pipeline:**\n{pipeline_log}\n\n"
            f"**Preview** (primeras {min(preview, len(rows))} filas):\n"
            f"```\n{preview_text}\n```"
        )

        if written:
            result += f"\n\n💾 Guardado en: `{written}`"

        return result

    # ── Operaciones individuales ──────────────────────────────────────────

    def _op_filter(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Filtra filas según condiciones."""
        field = op.get("field", "")
        before = len(rows)

        if "eq" in op:
            val = str(op["eq"])
            rows = [r for r in rows if str(r.get(field, "")) == val]
        elif "ne" in op:
            val = str(op["ne"])
            rows = [r for r in rows if str(r.get(field, "")) != val]
        elif "gt" in op:
            threshold = float(op["gt"])
            rows = [r for r in rows if (_coerce_number(r.get(field)) or 0) > threshold]
        elif "gte" in op:
            threshold = float(op["gte"])
            rows = [r for r in rows if (_coerce_number(r.get(field)) or 0) >= threshold]
        elif "lt" in op:
            threshold = float(op["lt"])
            rows = [r for r in rows if (_coerce_number(r.get(field)) or 0) < threshold]
        elif "lte" in op:
            threshold = float(op["lte"])
            rows = [r for r in rows if (_coerce_number(r.get(field)) or 0) <= threshold]
        elif "contains" in op:
            sub = str(op["contains"]).lower()
            rows = [r for r in rows if sub in str(r.get(field, "")).lower()]
        elif "regex" in op:
            pattern = re.compile(op["regex"])
            rows = [r for r in rows if pattern.search(str(r.get(field, "")))]
        elif "in" in op:
            values = set(str(v) for v in op["in"])
            rows = [r for r in rows if str(r.get(field, "")) in values]
        elif "not_in" in op:
            values = set(str(v) for v in op["not_in"])
            rows = [r for r in rows if str(r.get(field, "")) not in values]
        elif "is_null" in op:
            if op["is_null"]:
                rows = [r for r in rows if not r.get(field) or str(r.get(field, "")).strip() == ""]
            else:
                rows = [r for r in rows if r.get(field) and str(r.get(field, "")).strip() != ""]
        elif "between" in op:
            lo, hi = float(op["between"][0]), float(op["between"][1])
            rows = [r for r in rows if lo <= (_coerce_number(r.get(field)) or 0) <= hi]
        elif "value" in op:
            # Formato genérico: field=value
            val = str(op["value"])
            rows = [r for r in rows if str(r.get(field, "")) == val]

        return rows, columns, f"{field}: {before} → {len(rows)} filas"

    def _op_sort(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Ordena filas por una o más columnas."""
        by = op.get("by", op.get("field", ""))
        desc = op.get("desc", op.get("descending", False))

        if isinstance(by, str):
            sort_keys = [by]
        else:
            sort_keys = list(by)

        def sort_fn(row: Dict) -> tuple:
            result = []
            for key in sort_keys:
                val = row.get(key, "")
                num = _coerce_number(val)
                # Numérico primero, string después
                result.append((0, num) if num is not None else (1, str(val).lower()))
            return tuple(result)

        rows.sort(key=sort_fn, reverse=bool(desc))
        direction = "↓ desc" if desc else "↑ asc"
        return rows, columns, f"por {', '.join(sort_keys)} ({direction})"

    def _op_select(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Selecciona solo ciertas columnas."""
        cols = op.get("columns", op.get("cols", []))
        if isinstance(cols, str):
            cols = [c.strip() for c in cols.split(",")]

        valid = [c for c in cols if c in columns]
        if not valid:
            return rows, columns, "sin columnas válidas (sin cambios)"

        rows = [{k: r.get(k) for k in valid} for r in rows]
        return rows, valid, f"{len(valid)} columnas seleccionadas"

    def _op_drop(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Elimina columnas."""
        cols = op.get("columns", op.get("cols", []))
        if isinstance(cols, str):
            cols = [c.strip() for c in cols.split(",")]

        drop_set = set(cols)
        new_columns = [c for c in columns if c not in drop_set]

        rows = [{k: v for k, v in r.items() if k not in drop_set} for r in rows]
        return rows, new_columns, f"eliminadas: {', '.join(cols)}"

    def _op_rename(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Renombra columnas."""
        mapping = op.get("mapping", op.get("columns", {}))
        if not isinstance(mapping, dict):
            return rows, columns, "mapping inválido"

        new_columns = [mapping.get(c, c) for c in columns]
        rows = [{mapping.get(k, k): v for k, v in r.items()} for r in rows]
        renamed = [f"{old}→{new}" for old, new in mapping.items() if old in columns]

        return rows, new_columns, f"renombradas: {', '.join(renamed)}"

    def _op_add(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Agrega columna calculada."""
        col_name = op.get("column", op.get("name", "new_column"))
        expr = op.get("expr", op.get("expression", ""))
        value = op.get("value")

        if value is not None:
            # Valor estático
            for r in rows:
                r[col_name] = value
        elif expr:
            # Expresión simple: soporta operaciones entre columnas
            # Formatos: "col1 + col2", "col1 * 1.21", "upper(col1)"
            for r in rows:
                r[col_name] = self._eval_expr(r, expr)
        else:
            for r in rows:
                r[col_name] = ""

        if col_name not in columns:
            columns = columns + [col_name]

        return rows, columns, f"columna '{col_name}' agregada"

    def _op_dedup(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Elimina duplicados."""
        subset = op.get("columns", op.get("subset"))
        if isinstance(subset, str):
            subset = [s.strip() for s in subset.split(",")]

        before = len(rows)
        seen: set = set()
        deduped: List[Dict] = []

        for r in rows:
            if subset:
                key = tuple(str(r.get(c, "")) for c in subset)
            else:
                key = tuple(str(v) for v in r.values())

            if key not in seen:
                seen.add(key)
                deduped.append(r)

        removed = before - len(deduped)
        return deduped, columns, f"{removed} duplicados eliminados"

    def _op_head(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Primeras N filas."""
        n = int(op.get("n", op.get("count", 10)))
        return rows[:n], columns, f"primeras {n} filas"

    def _op_tail(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Últimas N filas."""
        n = int(op.get("n", op.get("count", 10)))
        return rows[-n:], columns, f"últimas {n} filas"

    def _op_group(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Agrupa y agrega."""
        by = op.get("by", op.get("field", ""))
        if isinstance(by, str):
            by = [by]

        agg = op.get("agg", op.get("aggregations", {}))
        # agg format: {"column": "sum|avg|count|min|max|first|last|concat"}

        # Agrupar
        groups: Dict[tuple, List[Dict]] = defaultdict(list)
        for r in rows:
            key = tuple(str(r.get(b, "")) for b in by)
            groups[key].append(r)

        # Agregar
        result_rows: List[Dict] = []
        new_columns = list(by)

        for key, group in groups.items():
            row = dict(zip(by, key))

            if not agg:
                # Default: count
                row["count"] = len(group)
                if "count" not in new_columns:
                    new_columns.append("count")
            else:
                for col, func in agg.items():
                    col_name = f"{col}_{func}"
                    values = [_coerce_number(r.get(col)) for r in group]
                    numeric = [v for v in values if v is not None]
                    str_values = [str(r.get(col, "")) for r in group]

                    if func == "sum":
                        row[col_name] = sum(numeric) if numeric else 0
                    elif func == "avg" or func == "mean":
                        row[col_name] = round(statistics.mean(numeric), 2) if numeric else 0
                    elif func == "min":
                        row[col_name] = min(numeric) if numeric else None
                    elif func == "max":
                        row[col_name] = max(numeric) if numeric else None
                    elif func == "count":
                        row[col_name] = len(group)
                    elif func == "first":
                        row[col_name] = str_values[0] if str_values else ""
                    elif func == "last":
                        row[col_name] = str_values[-1] if str_values else ""
                    elif func == "concat":
                        sep = op.get("separator", ", ")
                        row[col_name] = sep.join(str_values)
                    elif func == "median":
                        row[col_name] = round(statistics.median(numeric), 2) if numeric else 0
                    elif func == "stdev":
                        row[col_name] = (
                            round(statistics.stdev(numeric), 2) if len(numeric) > 1 else 0
                        )
                    elif func == "distinct":
                        row[col_name] = len(set(str_values))

                    if col_name not in new_columns:
                        new_columns.append(col_name)

            result_rows.append(row)

        msg = f"agrupado por {', '.join(by)}: {len(groups)} grupos"
        return result_rows, new_columns, msg

    def _op_fill(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Rellena valores nulos o vacíos."""
        col = op.get("column", op.get("field"))
        value = op.get("value", "")
        strategy = op.get("strategy", "value")
        target_cols = [col] if col else columns
        filled = 0

        for r in rows:
            for c in target_cols:
                if not r.get(c) or str(r.get(c, "")).strip() == "":
                    if strategy == "value":
                        r[c] = value
                    elif strategy == "forward":
                        pass  # Manejado abajo
                    elif strategy == "mean":
                        pass  # Manejado abajo
                    filled += 1

        # Forward fill
        if strategy == "forward":
            for c in target_cols:
                last_val = value
                for r in rows:
                    if r.get(c) and str(r.get(c, "")).strip():
                        last_val = r[c]
                    else:
                        r[c] = last_val

        # Mean fill
        if strategy == "mean":
            for c in target_cols:
                nums = [
                    _coerce_number(r.get(c))
                    for r in rows
                    if _coerce_number(r.get(c)) is not None
                ]
                mean_val = round(statistics.mean(nums), 2) if nums else 0
                for r in rows:
                    if not r.get(c) or str(r.get(c, "")).strip() == "":
                        r[c] = mean_val

        return rows, columns, f"{filled} valores rellenados ({strategy})"

    def _op_replace(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Buscar y reemplazar en valores."""
        col = op.get("column", op.get("field"))
        search = str(op.get("search", op.get("find", "")))
        replacement = str(op.get("replace", op.get("with", "")))
        use_regex = op.get("regex", False)
        count = 0

        target_cols = [col] if col else columns

        for r in rows:
            for c in target_cols:
                val = str(r.get(c, ""))
                if use_regex:
                    new_val = re.sub(search, replacement, val)
                else:
                    new_val = val.replace(search, replacement)
                if new_val != val:
                    r[c] = new_val
                    count += 1

        return rows, columns, f"{count} reemplazos realizados"

    def _op_cast(
        self, rows: List[Dict], columns: List[str], op: Dict
    ) -> Tuple[List[Dict], List[str], str]:
        """Convierte tipos de columna."""
        mapping = op.get("mapping", op.get("types", {}))
        # mapping: {"col": "int|float|str|bool|date"}

        casters: Dict[str, Callable] = {
            "int": lambda v: int(float(v)) if v else 0,
            "float": lambda v: float(v) if v else 0.0,
            "str": lambda v: str(v),
            "bool": lambda v: str(v).lower() in ("true", "1", "yes", "sí"),
            "date": lambda v: str(v),  # Mantiene como string formateado
        }

        casted = 0
        for col, type_name in mapping.items():
            caster = casters.get(type_name, str)
            for r in rows:
                if col in r:
                    try:
                        r[col] = caster(r[col])
                        casted += 1
                    except (ValueError, TypeError):
                        pass

        return rows, columns, f"{casted} valores convertidos"

    # ── Helpers ───────────────────────────────────────────────────────────

    def _parse_shorthand(self, shorthand: str) -> Dict[str, Any]:
        """Parsea formato abreviado: 'filter:age>18', 'sort:name:desc'."""
        parts = shorthand.split(":", maxsplit=1)
        op_name = parts[0].strip()

        if len(parts) < 2:
            return {"op": op_name}

        rest = parts[1].strip()

        if op_name == "filter":
            # age>18, name=John, status!=active
            for sym, key in [(">=", "gte"), ("<=", "lte"), ("!=", "ne"),
                             (">", "gt"), ("<", "lt"), ("~=", "regex"),
                             ("=", "eq")]:
                if sym in rest:
                    field, value = rest.split(sym, 1)
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                    return {"op": "filter", "field": field.strip(), key: value}
            return {"op": "filter", "field": rest}

        if op_name == "sort":
            sub = rest.split(":")
            by = sub[0].strip()
            desc = len(sub) > 1 and sub[1].strip().lower() in ("desc", "d", "descending")
            return {"op": "sort", "by": by, "desc": desc}

        if op_name in ("head", "tail"):
            return {"op": op_name, "n": int(rest)}

        if op_name == "select":
            return {"op": "select", "columns": [c.strip() for c in rest.split(",")]}

        if op_name == "drop":
            return {"op": "drop", "columns": [c.strip() for c in rest.split(",")]}

        return {"op": op_name, "value": rest}

    def _eval_expr(self, row: Dict, expr: str) -> Any:
        """
        Evalúa expresión simple y segura sobre una fila.

        Soporta:
            "col1 + col2", "col1 * 1.21"
            "upper(col1)", "lower(col1)", "len(col1)"
            "col1 + ' ' + col2"  (concatenación)
        """
        # Funciones de string
        func_match = re.match(r"(\w+)\((\w+)\)", expr.strip())
        if func_match:
            func, col = func_match.group(1), func_match.group(2)
            val = str(row.get(col, ""))
            funcs = {
                "upper": str.upper,
                "lower": str.lower,
                "strip": str.strip,
                "title": str.title,
                "len": lambda s: str(len(s)),
                "capitalize": str.capitalize,
            }
            if func in funcs:
                return funcs[func](val)

        # Operación aritmética simple:  col1 op col2  o  col1 op number
        arith = re.match(r"(\w+)\s*([+\-*/])\s*(.+)", expr.strip())
        if arith:
            left_name, operator, right_raw = arith.groups()
            left_val = _coerce_number(row.get(left_name))
            right_val = _coerce_number(right_raw.strip())

            # Si right es un nombre de columna
            if right_val is None:
                right_val = _coerce_number(row.get(right_raw.strip()))

            if left_val is not None and right_val is not None:
                ops = {"+": float.__add__, "-": float.__sub__,
                       "*": float.__mul__, "/": float.__truediv__}
                if operator in ops:
                    try:
                        result = ops[operator](left_val, right_val)
                        return round(result, 4) if result != int(result) else int(result)
                    except ZeroDivisionError:
                        return None

            # Concatenación de strings
            if operator == "+":
                return str(row.get(left_name, "")) + str(row.get(right_raw.strip(), right_raw.strip()))

        # Fallback: valor literal o referencia a columna
        if expr.strip() in row:
            return row[expr.strip()]

        return expr

    def _format_preview(
        self, rows: List[Dict], columns: List[str], n: int
    ) -> str:
        """Genera tabla ASCII de preview."""
        if not rows or not columns:
            return "(sin datos)"

        preview_rows = rows[:n]

        # Calcular anchos
        widths: Dict[str, int] = {}
        for col in columns:
            values = [str(r.get(col, ""))[:40] for r in preview_rows]
            widths[col] = max(len(col), max((len(v) for v in values), default=0))

        # Header
        header = " │ ".join(col.ljust(widths[col]) for col in columns)
        separator = "─┼─".join("─" * widths[col] for col in columns)

        # Filas
        body_lines = []
        for r in preview_rows:
            line = " │ ".join(
                str(r.get(col, ""))[:40].ljust(widths[col]) for col in columns
            )
            body_lines.append(line)

        total_note = ""
        if len(rows) > n:
            total_note = f"\n... y {len(rows) - n} filas más"

        return f"{header}\n{separator}\n" + "\n".join(body_lines) + total_note


# ─── 2. DATA VALIDATOR TOOL ─────────────────────────────────────────────────


class DataValidatorTool(BaseTool):
    """
    Valida datos tabulares (CSV/JSON) contra un esquema de reglas.

    El esquema define reglas por columna: tipo, required, min, max,
    pattern, values (enum), unique, custom.
    """

    name = "validate_data"
    description = (
        "Valida datos CSV/JSON contra un esquema de reglas por columna. "
        "Soporta: tipo, required, min/max, regex, enum, unique."
    )
    category = "data"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "file": ToolParameter(
                name="file",
                type="string",
                description="Archivo CSV/JSON o datos inline",
                required=True,
            ),
            "schema": ToolParameter(
                name="schema",
                type="string",
                description=(
                    "Esquema JSON con reglas por columna. "
                    "Ej: {\"name\":{\"type\":\"str\",\"required\":true}, "
                    "\"age\":{\"type\":\"int\",\"min\":0,\"max\":150}}"
                ),
                required=True,
            ),
            "max_errors": ToolParameter(
                name="max_errors",
                type="integer",
                description="Máximo de errores a reportar (default: 50)",
                required=False,
            ),
            "stop_on_first": ToolParameter(
                name="stop_on_first",
                type="boolean",
                description="Detener en el primer error por fila (default: false)",
                required=False,
            ),
        }

    # ── Validadores por tipo ──────────────────────────────────────────────

    _TYPE_VALIDATORS: Dict[str, Callable[[str], bool]] = {
        "str":      lambda v: isinstance(v, str),
        "string":   lambda v: isinstance(v, str),
        "int":      lambda v: _coerce_number(v) is not None and float(v) == int(float(v)),
        "integer":  lambda v: _coerce_number(v) is not None and float(v) == int(float(v)),
        "float":    lambda v: _coerce_number(v) is not None,
        "number":   lambda v: _coerce_number(v) is not None,
        "bool":     lambda v: str(v).lower() in ("true", "false", "0", "1", "yes", "no"),
        "boolean":  lambda v: str(v).lower() in ("true", "false", "0", "1", "yes", "no"),
        "email":    lambda v: bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(v))),
        "url":      lambda v: bool(re.match(r"^https?://\S+", str(v))),
        "date":     lambda v: _is_date(str(v)),
        "uuid":     lambda v: bool(re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            str(v).lower(),
        )),
        "ip":       lambda v: bool(re.match(
            r"^(\d{1,3}\.){3}\d{1,3}$", str(v)
        )),
        "phone":    lambda v: bool(re.match(r"^\+?[\d\s\-()]{7,20}$", str(v))),
    }

    def execute(
        self,
        file: Optional[str] = None,
        schema: Optional[str] = None,
        max_errors: int = 50,
        stop_on_first: bool = False,
        **kwargs,
    ) -> str:
        if not file:
            return "❌ Se requiere 'file' (archivo o datos inline)."
        if not schema:
            return "❌ Se requiere 'schema' (reglas de validación)."

        # ── Cargar datos ──────────────────────────────────────────────────
        try:
            rows, columns, fmt = _load_data(file)
        except Exception as e:
            return f"❌ Error cargando datos: {e}"

        if not rows:
            return "❌ No se encontraron datos para validar."

        # ── Parsear schema ────────────────────────────────────────────────
        try:
            if isinstance(schema, str):
                schema_dict = json.loads(schema)
            else:
                schema_dict = schema
        except json.JSONDecodeError as e:
            return f"❌ Schema JSON inválido: {e}"

        if not isinstance(schema_dict, dict):
            return "❌ El schema debe ser un objeto con columnas como keys."

        # ── Validar ───────────────────────────────────────────────────────
        errors: List[Dict[str, Any]] = []
        warnings: List[str] = []
        stats = {
            "total_rows": len(rows),
            "valid_rows": 0,
            "invalid_rows": 0,
            "errors_by_column": Counter(),
            "errors_by_type": Counter(),
        }

        # Verificar columnas faltantes
        schema_cols = set(schema_dict.keys())
        data_cols = set(columns)
        missing_cols = schema_cols - data_cols
        extra_cols = data_cols - schema_cols

        if missing_cols:
            warnings.append(f"Columnas en schema pero no en datos: {', '.join(missing_cols)}")
        if extra_cols:
            warnings.append(f"Columnas en datos pero no en schema: {', '.join(extra_cols)}")

        # Recolectar valores para validación de unicidad
        unique_trackers: Dict[str, Dict[str, int]] = {}
        for col, rules in schema_dict.items():
            if isinstance(rules, dict) and rules.get("unique"):
                unique_trackers[col] = {}

        # Validar fila por fila
        for row_idx, row in enumerate(rows, 1):
            row_valid = True

            for col, rules in schema_dict.items():
                if not isinstance(rules, dict):
                    continue

                value = row.get(col)
                str_value = str(value).strip() if value is not None else ""
                is_empty = value is None or str_value == ""

                # ── Required ──────────────────────────────────────────────
                if rules.get("required") and is_empty:
                    errors.append({
                        "row": row_idx, "column": col,
                        "rule": "required", "value": value,
                        "message": f"Campo requerido vacío",
                    })
                    stats["errors_by_column"][col] += 1
                    stats["errors_by_type"]["required"] += 1
                    row_valid = False
                    if stop_on_first:
                        continue
                    continue

                # Saltar validaciones si el campo está vacío y no es required
                if is_empty:
                    continue

                # ── Type ──────────────────────────────────────────────────
                expected_type = rules.get("type")
                if expected_type:
                    validator = self._TYPE_VALIDATORS.get(expected_type.lower())
                    if validator and not validator(str_value):
                        errors.append({
                            "row": row_idx, "column": col,
                            "rule": "type", "value": str_value,
                            "message": f"Se esperaba '{expected_type}', valor: '{str_value}'",
                        })
                        stats["errors_by_column"][col] += 1
                        stats["errors_by_type"]["type"] += 1
                        row_valid = False
                        if stop_on_first:
                            continue

                # ── Min / Max (numérico) ──────────────────────────────────
                num_val = _coerce_number(str_value)
                if "min" in rules and num_val is not None:
                    if num_val < rules["min"]:
                        errors.append({
                            "row": row_idx, "column": col,
                            "rule": "min", "value": str_value,
                            "message": f"Valor {num_val} < mínimo {rules['min']}",
                        })
                        stats["errors_by_column"][col] += 1
                        stats["errors_by_type"]["min"] += 1
                        row_valid = False

                if "max" in rules and num_val is not None:
                    if num_val > rules["max"]:
                        errors.append({
                            "row": row_idx, "column": col,
                            "rule": "max", "value": str_value,
                            "message": f"Valor {num_val} > máximo {rules['max']}",
                        })
                        stats["errors_by_column"][col] += 1
                        stats["errors_by_type"]["max"] += 1
                        row_valid = False

                # ── Min / Max length (string) ─────────────────────────────
                if "min_length" in rules:
                    if len(str_value) < rules["min_length"]:
                        errors.append({
                            "row": row_idx, "column": col,
                            "rule": "min_length", "value": str_value,
                            "message": f"Longitud {len(str_value)} < mínimo {rules['min_length']}",
                        })
                        stats["errors_by_column"][col] += 1
                        stats["errors_by_type"]["min_length"] += 1
                        row_valid = False

                if "max_length" in rules:
                    if len(str_value) > rules["max_length"]:
                        errors.append({
                            "row": row_idx, "column": col,
                            "rule": "max_length", "value": str_value[:20] + "...",
                            "message": f"Longitud {len(str_value)} > máximo {rules['max_length']}",
                        })
                        stats["errors_by_column"][col] += 1
                        stats["errors_by_type"]["max_length"] += 1
                        row_valid = False

                # ── Pattern (regex) ───────────────────────────────────────
                pattern = rules.get("pattern", rules.get("regex"))
                if pattern:
                    if not re.match(pattern, str_value):
                        errors.append({
                            "row": row_idx, "column": col,
                            "rule": "pattern", "value": str_value,
                            "message": f"No coincide con patrón '{pattern}'",
                        })
                        stats["errors_by_column"][col] += 1
                        stats["errors_by_type"]["pattern"] += 1
                        row_valid = False

                # ── Values (enum) ─────────────────────────────────────────
                allowed = rules.get("values", rules.get("enum", rules.get("in")))
                if allowed:
                    allowed_set = set(str(v) for v in allowed)
                    if str_value not in allowed_set:
                        errors.append({
                            "row": row_idx, "column": col,
                            "rule": "values", "value": str_value,
                            "message": f"'{str_value}' no está en valores permitidos",
                        })
                        stats["errors_by_column"][col] += 1
                        stats["errors_by_type"]["values"] += 1
                        row_valid = False

                # ── Unique (tracking) ─────────────────────────────────────
                if col in unique_trackers:
                    if str_value in unique_trackers[col]:
                        errors.append({
                            "row": row_idx, "column": col,
                            "rule": "unique", "value": str_value,
                            "message": (
                                f"Valor duplicado '{str_value}' "
                                f"(primera vez en fila {unique_trackers[col][str_value]})"
                            ),
                        })
                        stats["errors_by_column"][col] += 1
                        stats["errors_by_type"]["unique"] += 1
                        row_valid = False
                    else:
                        unique_trackers[col][str_value] = row_idx

                # Cortar si ya tenemos demasiados errores
                if len(errors) >= max_errors:
                    break

            if row_valid:
                stats["valid_rows"] += 1
            else:
                stats["invalid_rows"] += 1

            if len(errors) >= max_errors:
                break

        # ── Construir reporte ─────────────────────────────────────────────
        return self._build_report(stats, errors, warnings, max_errors)

    def _build_report(
        self,
        stats: Dict,
        errors: List[Dict],
        warnings: List[str],
        max_errors: int,
    ) -> str:
        total = stats["total_rows"]
        valid = stats["valid_rows"]
        invalid = stats["invalid_rows"]
        ratio = (valid / total * 100) if total else 0

        # Status icon
        if not errors:
            status = "✅ VÁLIDO"
        elif ratio > 90:
            status = "⚠️  PARCIALMENTE VÁLIDO"
        else:
            status = "❌ INVÁLIDO"

        # Header
        lines = [
            f"📋 **Validación de datos** — {status}\n",
            f"- Total filas: {total}",
            f"- Válidas: {valid} ({ratio:.1f}%)",
            f"- Inválidas: {invalid}",
            f"- Errores encontrados: {len(errors)}",
        ]

        # Warnings
        if warnings:
            lines.append("\n⚠️  **Advertencias:**")
            for w in warnings:
                lines.append(f"  - {w}")

        # Errores por columna
        if stats["errors_by_column"]:
            lines.append("\n📊 **Errores por columna:**")
            for col, count in stats["errors_by_column"].most_common(10):
                bar = "█" * min(count, 30)
                lines.append(f"  {col:20s} {bar} {count}")

        # Errores por tipo
        if stats["errors_by_type"]:
            lines.append("\n📊 **Errores por tipo de regla:**")
            for rule, count in stats["errors_by_type"].most_common():
                lines.append(f"  {rule:15s}: {count}")

        # Detalle de errores
        if errors:
            lines.append(f"\n🔍 **Detalle** (primeros {min(len(errors), 20)}):")
            for err in errors[:20]:
                lines.append(
                    f"  Fila {err['row']:>4d} │ {err['column']:>15s} │ "
                    f"{err['rule']:>10s} │ {err['message']}"
                )
            if len(errors) > 20:
                lines.append(f"  ... y {len(errors) - 20} errores más")

            if len(errors) >= max_errors:
                lines.append(f"\n  ⚠️  Se alcanzó el límite de {max_errors} errores.")

        return "\n".join(lines)


def _is_date(value: str) -> bool:
    """Intenta parsear un string como fecha en formatos comunes."""
    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y", "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            datetime.strptime(value.strip(), fmt)
            return True
        except ValueError:
            continue
    return False


# ─── 3. DATA VISUALIZATION TOOL ─────────────────────────────────────────────


class DataVisualizationTool(BaseTool):
    """
    Genera visualizaciones de datos en texto/ASCII sin dependencias externas.

    Tipos: table, bar, hbar, line, histogram, pie, summary, sparkline, heatmap.
    """

    name = "visualize"
    description = (
        "Genera visualizaciones ASCII de datos CSV/JSON: "
        "table, bar, hbar, line, histogram, pie, summary, sparkline, heatmap."
    )
    category = "data"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "data": ToolParameter(
                name="data",
                type="string",
                description="Archivo CSV/JSON o datos inline",
                required=True,
            ),
            "type": ToolParameter(
                name="type",
                type="string",
                description="Tipo de gráfico: table|bar|hbar|line|histogram|pie|summary|sparkline|heatmap",
                required=False,
            ),
            "x": ToolParameter(
                name="x",
                type="string",
                description="Columna para eje X / categorías",
                required=False,
            ),
            "y": ToolParameter(
                name="y",
                type="string",
                description="Columna para eje Y / valores",
                required=False,
            ),
            "title": ToolParameter(
                name="title",
                type="string",
                description="Título del gráfico",
                required=False,
            ),
            "width": ToolParameter(
                name="width",
                type="integer",
                description="Ancho del gráfico (default: 60)",
                required=False,
            ),
            "height": ToolParameter(
                name="height",
                type="integer",
                description="Alto del gráfico para line/histogram (default: 15)",
                required=False,
            ),
            "max_rows": ToolParameter(
                name="max_rows",
                type="integer",
                description="Máximo de filas a mostrar en tabla (default: 30)",
                required=False,
            ),
            "sort": ToolParameter(
                name="sort",
                type="boolean",
                description="Ordenar valores descendente (default: true)",
                required=False,
            ),
        }

    def execute(
        self,
        data: Optional[str] = None,
        type: str = "table",
        x: Optional[str] = None,
        y: Optional[str] = None,
        title: Optional[str] = None,
        width: int = 60,
        height: int = 15,
        max_rows: int = 30,
        sort: bool = True,
        **kwargs,
    ) -> str:
        if not data:
            return "❌ Se requiere 'data' (archivo o datos inline)."

        try:
            rows, columns, fmt = _load_data(data)
        except Exception as e:
            return f"❌ Error cargando datos: {e}"

        if not rows:
            return "❌ No se encontraron datos."

        viz_type = type.lower().strip()
        chart_title = title or f"Datos ({len(rows)} filas)"

        generators = {
            "table":     self._viz_table,
            "bar":       self._viz_bar,
            "hbar":      self._viz_hbar,
            "line":      self._viz_line,
            "histogram": self._viz_histogram,
            "hist":      self._viz_histogram,
            "pie":       self._viz_pie,
            "summary":   self._viz_summary,
            "sparkline": self._viz_sparkline,
            "spark":     self._viz_sparkline,
            "heatmap":   self._viz_heatmap,
        }

        generator = generators.get(viz_type)
        if not generator:
            opts = ", ".join(generators.keys())
            return f"❌ Tipo '{viz_type}' no soportado. Opciones: {opts}"

        try:
            result = generator(
                rows=rows, columns=columns, x=x, y=y,
                title=chart_title, width=width, height=height,
                max_rows=max_rows, sort_desc=sort,
            )
        except Exception as e:
            return f"❌ Error generando visualización: {e}"

        return f"```\n{result}\n```"

    # ── Visualizaciones ──────────────────────────────────────────────────

    def _viz_table(self, rows, columns, max_rows, title, **kw) -> str:
        """Tabla formateada con bordes."""
        display_rows = rows[:max_rows]
        cols = columns[:15]  # Limitar columnas

        # Calcular anchos
        widths = {}
        for col in cols:
            vals = [str(r.get(col, ""))[:30] for r in display_rows]
            widths[col] = max(len(col), max((len(v) for v in vals), default=0))

        total_w = sum(widths.values()) + 3 * (len(cols) - 1) + 4

        # Construir tabla
        lines = [f"┌{'─' * (total_w - 2)}┐"]
        lines.append(f"│ {title:^{total_w - 4}} │")
        lines.append(f"├{'─┬─'.join('─' * widths[c] for c in cols)}┤")

        # Header
        header = " │ ".join(col.ljust(widths[col]) for col in cols)
        lines.append(f"│{header}│")
        lines.append(f"├{'─┼─'.join('─' * widths[c] for c in cols)}┤")

        # Data
        for r in display_rows:
            row_str = " │ ".join(
                str(r.get(c, ""))[:30].ljust(widths[c]) for c in cols
            )
            lines.append(f"│{row_str}│")

        lines.append(f"└{'─┴─'.join('─' * widths[c] for c in cols)}┘")

        if len(rows) > max_rows:
            lines.append(f"  ... {len(rows) - max_rows} filas más")

        return "\n".join(lines)

    def _viz_bar(self, rows, columns, x, y, title, width, sort_desc, **kw) -> str:
        """Gráfico de barras verticales ASCII."""
        pairs = self._extract_pairs(rows, columns, x, y, sort_desc)
        if not pairs:
            return "Sin datos numéricos para graficar."

        max_val = max(v for _, v in pairs)
        if max_val == 0:
            return "Todos los valores son 0."

        height = kw.get("height", 15)
        n_bars = min(len(pairs), width // 3)
        pairs = pairs[:n_bars]

        # Construir gráfico vertical
        lines = [f"  {title}"]
        lines.append("")

        # Calcular niveles
        for level in range(height, 0, -1):
            threshold = max_val * level / height
            row_chars = []
            for _, val in pairs:
                if val >= threshold:
                    row_chars.append(" ██")
                else:
                    row_chars.append("   ")
            # Eje Y
            if level == height:
                label = f"{max_val:>8.1f} │"
            elif level == height // 2:
                label = f"{max_val / 2:>8.1f} │"
            elif level == 1:
                label = f"{'0':>8s} │"
            else:
                label = f"{'':>8s} │"
            lines.append(f"{label}{''.join(row_chars)}")

        # Eje X
        lines.append(f"{'':>8s} └{'───' * len(pairs)}")
        # Labels
        label_line = "         "
        for label, _ in pairs:
            label_line += f" {str(label)[:2]:>2s}"
        lines.append(label_line)

        # Leyenda
        lines.append("")
        for label, val in pairs:
            lines.append(f"  {str(label):>12s}: {val:,.2f}")

        return "\n".join(lines)

    def _viz_hbar(self, rows, columns, x, y, title, width, sort_desc, **kw) -> str:
        """Gráfico de barras horizontales."""
        pairs = self._extract_pairs(rows, columns, x, y, sort_desc)
        if not pairs:
            return "Sin datos numéricos para graficar."

        max_val = max(v for _, v in pairs)
        if max_val == 0:
            return "Todos los valores son 0."

        max_label = max(len(str(label)) for label, _ in pairs)
        bar_width = width - max_label - 15

        lines = [f"  {title}", ""]

        for label, val in pairs:
            filled = int(val / max_val * bar_width) if max_val > 0 else 0
            bar = "█" * filled + "░" * (bar_width - filled)
            lines.append(f"  {str(label):>{max_label}s} │{bar}│ {val:,.2f}")

        lines.append(f"  {'':>{max_label}s} └{'─' * bar_width}┘")
        lines.append(f"  {'':>{max_label}s}  0{' ' * (bar_width - len(str(int(max_val))) - 1)}{max_val:,.0f}")

        return "\n".join(lines)

    def _viz_line(self, rows, columns, x, y, title, width, height, **kw) -> str:
        """Gráfico de línea ASCII."""
        pairs = self._extract_pairs(rows, columns, x, y, sort_desc=False)
        if not pairs:
            return "Sin datos numéricos para graficar."

        values = [v for _, v in pairs]
        min_val = min(values)
        max_val = max(values)
        val_range = max_val - min_val if max_val != min_val else 1

        # Normalizar a grid
        n_points = min(len(values), width - 12)
        if len(values) > n_points:
            # Resamplear
            step = len(values) / n_points
            sampled = [values[int(i * step)] for i in range(n_points)]
        else:
            sampled = values

        lines = [f"  {title}", ""]

        # Canvas
        canvas: List[List[str]] = [[" "] * len(sampled) for _ in range(height)]

        for col_idx, val in enumerate(sampled):
            row_idx = int((val - min_val) / val_range * (height - 1))
            row_idx = height - 1 - row_idx  # Invertir Y
            canvas[row_idx][col_idx] = "●"

            # Conectar puntos verticalmente
            if col_idx > 0:
                prev_val = sampled[col_idx - 1]
                prev_row = height - 1 - int((prev_val - min_val) / val_range * (height - 1))
                lo, hi = sorted([prev_row, row_idx])
                for r in range(lo + 1, hi):
                    if canvas[r][col_idx - 1] == " ":
                        canvas[r][col_idx - 1] = "│"

        # Renderizar
        for i, row in enumerate(canvas):
            if i == 0:
                label = f"{max_val:>8.1f}"
            elif i == height - 1:
                label = f"{min_val:>8.1f}"
            elif i == height // 2:
                label = f"{(max_val + min_val) / 2:>8.1f}"
            else:
                label = " " * 8
            lines.append(f"{label} │{''.join(row)}")

        lines.append(f"{'':>8s} └{'─' * len(sampled)}")

        return "\n".join(lines)

    def _viz_histogram(self, rows, columns, y, title, width, height, **kw) -> str:
        """Histograma de distribución de frecuencias."""
        col = y or kw.get("x") or self._first_numeric_col(rows, columns)
        if not col:
            return "No se encontró columna numérica para histograma."

        values = [
            _coerce_number(r.get(col))
            for r in rows
            if _coerce_number(r.get(col)) is not None
        ]
        if not values:
            return f"No hay valores numéricos en columna '{col}'."

        n_bins = min(20, max(5, int(math.sqrt(len(values)))))
        min_val = min(values)
        max_val = max(values)
        bin_width = (max_val - min_val) / n_bins if max_val != min_val else 1

        # Contar frecuencias
        bins = [0] * n_bins
        for v in values:
            idx = min(int((v - min_val) / bin_width), n_bins - 1)
            bins[idx] += 1

        max_freq = max(bins) if bins else 1
        bar_max = width - 20

        lines = [
            f"  {title} — Histograma de '{col}'",
            f"  n={len(values)}, min={min_val:.2f}, max={max_val:.2f}, "
            f"mean={statistics.mean(values):.2f}, stdev={statistics.stdev(values) if len(values) > 1 else 0:.2f}",
            "",
        ]

        for i, freq in enumerate(bins):
            lo = min_val + i * bin_width
            hi = lo + bin_width
            filled = int(freq / max_freq * bar_max) if max_freq > 0 else 0
            bar = "█" * filled
            lines.append(f"  [{lo:>7.1f}, {hi:>7.1f}) │{bar} {freq}")

        lines.append(f"  {'':>17s} └{'─' * bar_max}")

        return "\n".join(lines)

    def _viz_pie(self, rows, columns, x, y, title, width, sort_desc, **kw) -> str:
        """Gráfico de 'pie' en texto (porcentajes con barras)."""
        pairs = self._extract_pairs(rows, columns, x, y, sort_desc)
        if not pairs:
            return "Sin datos para pie chart."

        total = sum(v for _, v in pairs)
        if total == 0:
            return "Total es 0, no se puede generar pie chart."

        symbols = ["█", "▓", "▒", "░", "▪", "▫", "●", "○", "◆", "◇"]
        bar_width = width - 30

        lines = [f"  {title} — Distribución", ""]

        for i, (label, val) in enumerate(pairs):
            pct = val / total * 100
            filled = int(pct / 100 * bar_width)
            sym = symbols[i % len(symbols)]
            bar = sym * filled
            lines.append(f"  {str(label):>15s} {bar:<{bar_width}s} {pct:5.1f}% ({val:,.0f})")

        lines.append(f"  {'':>15s} {'─' * bar_width}")
        lines.append(f"  {'Total':>15s} {'':>{bar_width}s} 100.0% ({total:,.0f})")

        return "\n".join(lines)

    def _viz_summary(self, rows, columns, title, **kw) -> str:
        """Resumen estadístico de todas las columnas."""
        lines = [f"  {title} — Resumen estadístico", f"  {len(rows)} filas × {len(columns)} columnas", ""]

        # Header de tabla de estadísticas
        lines.append(f"  {'Columna':>18s} │ {'Tipo':>7s} │ {'No Null':>7s} │ {'Unique':>6s} │ "
                      f"{'Min':>10s} │ {'Max':>10s} │ {'Mean':>10s} │ {'Stdev':>10s}")
        lines.append(f"  {'─' * 18}─┼─{'─' * 7}─┼─{'─' * 7}─┼─{'─' * 6}─┼─"
                      f"{'─' * 10}─┼─{'─' * 10}─┼─{'─' * 10}─┼─{'─' * 10}")

        for col in columns:
            values = [r.get(col) for r in rows]
            non_null = [v for v in values if v is not None and str(v).strip() != ""]
            nums = [_coerce_number(v) for v in non_null]
            nums = [n for n in nums if n is not None]

            unique = len(set(str(v) for v in non_null))

            if nums and len(nums) > len(non_null) * 0.5:
                # Columna predominantemente numérica
                col_type = "numeric"
                min_v = f"{min(nums):>10.2f}"
                max_v = f"{max(nums):>10.2f}"
                mean_v = f"{statistics.mean(nums):>10.2f}"
                std_v = f"{statistics.stdev(nums):>10.2f}" if len(nums) > 1 else f"{'N/A':>10s}"
            else:
                col_type = "string"
                str_vals = [str(v) for v in non_null]
                min_v = f"{min(str_vals)[:10]:>10s}" if str_vals else f"{'':>10s}"
                max_v = f"{max(str_vals)[:10]:>10s}" if str_vals else f"{'':>10s}"
                mean_v = f"{'N/A':>10s}"
                std_v = f"{'N/A':>10s}"

            lines.append(
                f"  {col:>18s} │ {col_type:>7s} │ {len(non_null):>7d} │ {unique:>6d} │ "
                f"{min_v} │ {max_v} │ {mean_v} │ {std_v}"
            )

        # Top nulls
        null_counts = []
        for col in columns:
            nulls = sum(1 for r in rows if not r.get(col) or str(r.get(col, "")).strip() == "")
            if nulls > 0:
                null_counts.append((col, nulls, nulls / len(rows) * 100))

        if null_counts:
            null_counts.sort(key=lambda x: x[1], reverse=True)
            lines.append("")
            lines.append("  ⚠️  Valores nulos:")
            for col, count, pct in null_counts[:10]:
                lines.append(f"    {col}: {count} ({pct:.1f}%)")

        return "\n".join(lines)

    def _viz_sparkline(self, rows, columns, y, title, width, **kw) -> str:
        """Sparklines compactos para columnas numéricas."""
        spark_chars = "▁▂▃▄▅▆▇█"

        target_cols = [y] if y else [
            c for c in columns
            if any(_coerce_number(r.get(c)) is not None for r in rows[:10])
        ]

        lines = [f"  {title} — Sparklines", ""]

        for col in target_cols[:10]:
            values = [_coerce_number(r.get(col)) for r in rows]
            nums = [v if v is not None else 0 for v in values]

            if not nums:
                continue

            min_v = min(nums)
            max_v = max(nums)
            v_range = max_v - min_v if max_v != min_v else 1

            # Resamplear si hay demasiados puntos
            max_points = width - 25
            if len(nums) > max_points:
                step = len(nums) / max_points
                nums = [nums[int(i * step)] for i in range(max_points)]

            spark = ""
            for v in nums:
                idx = int((v - min_v) / v_range * (len(spark_chars) - 1))
                spark += spark_chars[idx]

            mean = statistics.mean(nums)
            lines.append(f"  {col:>15s} │ {spark} │ μ={mean:.1f}")

        return "\n".join(lines)

    def _viz_heatmap(self, rows, columns, title, width, **kw) -> str:
        """Heatmap de correlación entre columnas numéricas."""
        heat_chars = " ░▒▓█"

        # Encontrar columnas numéricas
        num_cols = []
        col_values: Dict[str, List[float]] = {}
        for col in columns:
            vals = [_coerce_number(r.get(col)) for r in rows]
            nums = [v for v in vals if v is not None]
            if len(nums) > len(rows) * 0.5:
                num_cols.append(col)
                # Rellenar None con media
                mean = statistics.mean(nums) if nums else 0
                col_values[col] = [v if v is not None else mean for v in vals]

        if len(num_cols) < 2:
            return "Se necesitan al menos 2 columnas numéricas para heatmap."

        num_cols = num_cols[:10]  # Limitar

        # Calcular correlaciones (Pearson simplificado)
        def _correlation(a: List[float], b: List[float]) -> float:
            n = min(len(a), len(b))
            if n < 2:
                return 0
            mean_a = sum(a[:n]) / n
            mean_b = sum(b[:n]) / n
            cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n)) / n
            std_a = math.sqrt(sum((a[i] - mean_a) ** 2 for i in range(n)) / n)
            std_b = math.sqrt(sum((b[i] - mean_b) ** 2 for i in range(n)) / n)
            if std_a == 0 or std_b == 0:
                return 0
            return cov / (std_a * std_b)

        max_label = max(len(c) for c in num_cols)
        lines = [f"  {title} — Heatmap de correlación", ""]

        # Header
        header = " " * (max_label + 3)
        for c in num_cols:
            header += f" {c[:3]:>3s}"
        lines.append(header)

        for c1 in num_cols:
            row_str = f"  {c1:>{max_label}s} │"
            for c2 in num_cols:
                corr = _correlation(col_values[c1], col_values[c2])
                idx = int(abs(corr) * (len(heat_chars) - 1))
                idx = min(idx, len(heat_chars) - 1)
                char = heat_chars[idx]
                sign = "+" if corr >= 0 else "-"
                row_str += f"  {sign}{char}"
            lines.append(row_str)

        lines.append("")
        lines.append("  Leyenda: ░ débil  ▒ moderada  ▓ fuerte  █ muy fuerte  (+/-)")

        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _extract_pairs(
        self,
        rows: List[Dict],
        columns: List[str],
        x: Optional[str],
        y: Optional[str],
        sort_desc: bool,
    ) -> List[Tuple[str, float]]:
        """Extrae pares (label, value) de los datos."""
        if x and y:
            # Columnas explícitas
            pairs = []
            for r in rows:
                label = str(r.get(x, ""))
                val = _coerce_number(r.get(y))
                if val is not None:
                    pairs.append((label, val))
        elif y:
            # Solo Y → usar índice como X
            pairs = []
            for i, r in enumerate(rows):
                val = _coerce_number(r.get(y))
                if val is not None:
                    pairs.append((str(i + 1), val))
        elif x:
            # Solo X → contar frecuencias
            counter = Counter(str(r.get(x, "")) for r in rows)
            pairs = [(k, float(v)) for k, v in counter.items()]
        else:
            # Auto-detectar: primera string como X, primer numérico como Y
            x_col = None
            y_col = None
            for col in columns:
                sample = [r.get(col) for r in rows[:5]]
                nums = [_coerce_number(v) for v in sample]
                if all(n is not None for n in nums) and y_col is None:
                    y_col = col
                elif x_col is None:
                    x_col = col

            if x_col and y_col:
                pairs = []
                for r in rows:
                    label = str(r.get(x_col, ""))
                    val = _coerce_number(r.get(y_col))
                    if val is not None:
                        pairs.append((label, val))
            elif y_col:
                pairs = [(str(i + 1), _coerce_number(r.get(y_col)) or 0) for i, r in enumerate(rows)]
            else:
                # Contar frecuencias de la primera columna
                col = columns[0] if columns else ""
                counter = Counter(str(r.get(col, "")) for r in rows)
                pairs = [(k, float(v)) for k, v in counter.items()]

        if sort_desc:
            pairs.sort(key=lambda p: p[1], reverse=True)

        return pairs

    def _first_numeric_col(
        self, rows: List[Dict], columns: List[str]
    ) -> Optional[str]:
        """Encuentra la primera columna predominantemente numérica."""
        for col in columns:
            sample = [_coerce_number(r.get(col)) for r in rows[:20]]
            if sum(1 for v in sample if v is not None) > len(sample) * 0.5:
                return col
        return None


# ─── 4. FORMAT CONVERTER TOOL ───────────────────────────────────────────────


class FormatConverterTool(BaseTool):
    """
    Convierte datos entre formatos: CSV, JSON, XML, YAML, Markdown table,
    SQL INSERT, HTML table.
    """

    name = "convert_format"
    description = (
        "Convierte entre formatos de datos: csv, json, xml, yaml, "
        "markdown, sql, html, toml."
    )
    category = "data"

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "input": ToolParameter(
                name="input",
                type="string",
                description="Archivo o datos inline",
                required=True,
            ),
            "format": ToolParameter(
                name="format",
                type="string",
                description=(
                    "Conversión: csv_to_json, json_to_csv, csv_to_xml, "
                    "json_to_xml, xml_to_json, csv_to_markdown, csv_to_sql, "
                    "csv_to_html, json_to_yaml, yaml_to_json, auto_to_<target>"
                ),
                required=True,
            ),
            "output": ToolParameter(
                name="output",
                type="string",
                description="Archivo de salida (opcional)",
                required=False,
            ),
            "table_name": ToolParameter(
                name="table_name",
                type="string",
                description="Nombre de tabla para SQL/XML (default: 'data')",
                required=False,
            ),
            "pretty": ToolParameter(
                name="pretty",
                type="boolean",
                description="Formatear salida legible (default: true)",
                required=False,
            ),
            "root_element": ToolParameter(
                name="root_element",
                type="string",
                description="Elemento raíz para XML (default: 'records')",
                required=False,
            ),
        }

    def execute(
        self,
        input: Optional[str] = None,
        format: Optional[str] = None,
        output: Optional[str] = None,
        table_name: str = "data",
        pretty: bool = True,
        root_element: str = "records",
        **kwargs,
    ) -> str:
        if not input:
            return "❌ Se requiere 'input'."
        if not format:
            return "❌ Se requiere 'format' (ej: csv_to_json)."

        fmt = format.lower().strip().replace("-", "_").replace(" ", "_")

        # ── Cargar datos ──────────────────────────────────────────────────
        try:
            rows, columns, src_fmt = _load_data(input)
        except Exception as e:
            return f"❌ Error cargando datos: {e}"

        if not rows:
            return "❌ No se encontraron datos."

        # ── Determinar formato destino ────────────────────────────────────
        # Soportar "auto_to_json", "csv_to_json", o solo "json"
        if "_to_" in fmt:
            target = fmt.split("_to_")[-1]
        else:
            target = fmt

        converters = {
            "json":     self._to_json,
            "csv":      self._to_csv,
            "xml":      self._to_xml,
            "yaml":     self._to_yaml,
            "yml":      self._to_yaml,
            "markdown": self._to_markdown,
            "md":       self._to_markdown,
            "sql":      self._to_sql,
            "html":     self._to_html,
            "toml":     self._to_toml,
        }

        converter = converters.get(target)
        if not converter:
            opts = ", ".join(converters.keys())
            return f"❌ Formato destino '{target}' no soportado. Opciones: {opts}"

        try:
            result = converter(
                rows=rows, columns=columns, table_name=table_name,
                pretty=pretty, root_element=root_element,
            )
        except Exception as e:
            return f"❌ Error en conversión: {e}"

        # ── Escribir salida ───────────────────────────────────────────────
        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(result, encoding="utf-8")
            # Mostrar preview truncado
            preview = result[:500] + ("..." if len(result) > 500 else "")
            return (
                f"✅ Conversión {src_fmt} → {target} completada\n"
                f"   {len(rows)} registros → `{output}`\n\n"
                f"```\n{preview}\n```"
            )

        return (
            f"✅ Conversión {src_fmt} → {target} ({len(rows)} registros):\n\n"
            f"```{target}\n{result}\n```"
        )

    # ── Conversores ──────────────────────────────────────────────────────

    def _to_json(self, rows, columns, pretty, **kw) -> str:
        """Convierte a JSON."""
        indent = 2 if pretty else None
        return json.dumps(rows, indent=indent, ensure_ascii=False, default=str)

    def _to_csv(self, rows, columns, **kw) -> str:
        """Convierte a CSV."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def _to_xml(self, rows, columns, root_element, table_name, pretty, **kw) -> str:
        """Convierte a XML."""
        if not HAS_XML:
            return "❌ Módulo XML no disponible."

        root = ET.Element(root_element)
        for row in rows:
            item = ET.SubElement(root, table_name)
            for col in columns:
                child = ET.SubElement(item, re.sub(r"[^a-zA-Z0-9_]", "_", col))
                child.text = str(row.get(col, ""))

        if pretty:
            ET.indent(root, space="  ")

        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
            root, encoding="unicode"
        )

    def _to_yaml(self, rows, columns, **kw) -> str:
        """Convierte a YAML."""
        if HAS_YAML:
            return yaml.dump(rows, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # Fallback sin PyYAML
        lines = []
        for row in rows:
            lines.append("-")
            for col in columns:
                val = row.get(col, "")
                if isinstance(val, str) and (":" in val or "#" in val or "\n" in val):
                    val = f'"{val}"'
                lines.append(f"  {col}: {val}")
        return "\n".join(lines)

    def _to_markdown(self, rows, columns, **kw) -> str:
        """Convierte a tabla Markdown."""
        if not columns:
            return ""

        # Calcular anchos
        widths = {}
        for col in columns:
            vals = [str(r.get(col, ""))[:40] for r in rows]
            widths[col] = max(len(col), max((len(v) for v in vals), default=0))

        # Header
        header = "| " + " | ".join(col.ljust(widths[col]) for col in columns) + " |"
        separator = "| " + " | ".join("-" * widths[col] for col in columns) + " |"

        # Body
        body_lines = []
        for r in rows:
            line = "| " + " | ".join(
                str(r.get(col, ""))[:40].ljust(widths[col]) for col in columns
            ) + " |"
            body_lines.append(line)

        return "\n".join([header, separator] + body_lines)

    def _to_sql(self, rows, columns, table_name, **kw) -> str:
        """Genera INSERT statements SQL."""
        lines = []

        # CREATE TABLE
        lines.append(f"-- Auto-generated SQL for table '{table_name}'")
        lines.append(f"-- {len(rows)} records\n")

        col_types = {}
        for col in columns:
            sample = [r.get(col) for r in rows[:20] if r.get(col)]
            nums = [_coerce_number(v) for v in sample]
            if all(n is not None for n in nums) and nums:
                if all(float(n) == int(float(n)) for n in nums if n is not None):
                    col_types[col] = "INTEGER"
                else:
                    col_types[col] = "REAL"
            else:
                max_len = max((len(str(v)) for v in sample), default=255)
                col_types[col] = f"VARCHAR({max(max_len, 50)})"

        safe_cols = [re.sub(r"[^a-zA-Z0-9_]", "_", c) for c in columns]

        lines.append(f"CREATE TABLE IF NOT EXISTS {table_name} (")
        lines.append(f"    id INTEGER PRIMARY KEY AUTOINCREMENT,")
        for i, (col, safe) in enumerate(zip(columns, safe_cols)):
            comma = "," if i < len(columns) - 1 else ""
            lines.append(f"    {safe} {col_types.get(col, 'TEXT')}{comma}")
        lines.append(");\n")

        # INSERT statements
        for row in rows:
            values = []
            for col in columns:
                val = row.get(col, "")
                if val is None or str(val).strip() == "":
                    values.append("NULL")
                elif _coerce_number(val) is not None and col_types.get(col) in ("INTEGER", "REAL"):
                    values.append(str(val))
                else:
                    escaped = str(val).replace("'", "''")
                    values.append(f"'{escaped}'")

            cols_str = ", ".join(safe_cols)
            vals_str = ", ".join(values)
            lines.append(f"INSERT INTO {table_name} ({cols_str}) VALUES ({vals_str});")

        return "\n".join(lines)

    def _to_html(self, rows, columns, table_name, pretty, **kw) -> str:
        """Genera tabla HTML."""
        indent = "  " if pretty else ""
        nl = "\n" if pretty else ""

        lines = [
            f'<table class="data-table" id="{table_name}">',
            f"{indent}<caption>{table_name} ({len(rows)} registros)</caption>",
            f"{indent}<thead>",
            f"{indent}{indent}<tr>",
        ]

        for col in columns:
            lines.append(f"{indent}{indent}{indent}<th>{_html_escape(col)}</th>")

        lines.extend([
            f"{indent}{indent}</tr>",
            f"{indent}</thead>",
            f"{indent}<tbody>",
        ])

        for row in rows:
            lines.append(f"{indent}{indent}<tr>")
            for col in columns:
                val = _html_escape(str(row.get(col, "")))
                lines.append(f"{indent}{indent}{indent}<td>{val}</td>")
            lines.append(f"{indent}{indent}</tr>")

        lines.extend([
            f"{indent}</tbody>",
            "</table>",
        ])

        return nl.join(lines)

    def _to_toml(self, rows, columns, table_name, **kw) -> str:
        """Genera formato TOML (array of tables)."""
        lines = [f"# {len(rows)} registros", ""]
        for row in rows:
            lines.append(f"[[{table_name}]]")
            for col in columns:
                val = row.get(col, "")
                num = _coerce_number(val)
                if num is not None:
                    if float(num) == int(float(num)):
                        lines.append(f'{col} = {int(float(num))}')
                    else:
                        lines.append(f'{col} = {num}')
                elif isinstance(val, bool):
                    lines.append(f'{col} = {str(val).lower()}')
                else:
                    escaped = str(val).replace('"', '\\"')
                    lines.append(f'{col} = "{escaped}"')
            lines.append("")

        return "\n".join(lines)


def _html_escape(text: str) -> str:
    """Escapa caracteres especiales HTML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )