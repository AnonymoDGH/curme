# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS DE BASE DE DATOS
# Consultas, esquemas, migraciones y backups
# ═══════════════════════════════════════════════════════════════════════════════

import os
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from .base import BaseTool, ToolParameter

# Intentar importar drivers de base de datos perezosamente
HAS_SQLITE = True
try:
    import sqlite3
except ImportError:
    HAS_SQLITE = False

HAS_POSTGRES = True
try:
    import psycopg2
except ImportError:
    HAS_POSTGRES = False

HAS_MYSQL = True
try:
    import mysql.connector
except ImportError:
    HAS_MYSQL = False
except Exception:
    HAS_MYSQL = False


class DatabaseQueryTool(BaseTool):
    # Ejecuta consultas SQL contra bases de datos.
    #
    # Soporta SQLite, PostgreSQL y MySQL.
    # Útil para consultas rápidas, debugging y exploración de datos.
    
    name = "db_query"
    description = """Ejecuta consultas SQL contra una base de datos.

Soporta:
- SQLite: connection="sqlite:///path/to/db.sqlite"
- PostgreSQL: connection="postgresql://user:pass@host:5432/db"
- MySQL: connection="mysql://user:pass@host:3306/db"

Ejemplos:
- SQLite: connection="sqlite:///data.db", sql="SELECT * FROM users LIMIT 5"
- PostgreSQL: connection="postgresql://admin:secret@localhost/myapp", sql="SELECT COUNT(*) FROM orders"

⚠️ Solo SELECT permitido por seguridad. Usa db_execute para modificaciones.
"""
    category = "database"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "connection": ToolParameter(
                name="connection",
                type="string",
                description="String de conexión (sqlite:///path, postgresql://..., mysql://...)",
                required=True
            ),
            "sql": ToolParameter(
                name="sql",
                type="string",
                description="Consulta SQL a ejecutar",
                required=True
            ),
            "limit": ToolParameter(
                name="limit",
                type="integer",
                description="Límite de filas a retornar (default: 100)",
                required=False
            ),
            "format": ToolParameter(
                name="format",
                type="string",
                description="Formato de salida: table, json, csv",
                required=False,
                enum=["table", "json", "csv"]
            )
        }
    
    def execute(
        self,
        connection: str = None,
        sql: str = None,
        limit: int = 100,
        format: str = "table",
        **kwargs
    ) -> str:
        connection = connection or kwargs.get('connection', '')
        sql = sql or kwargs.get('sql', '')
        limit = limit or kwargs.get('limit', 100)
        format = format or kwargs.get('format', 'table')
        
        if not connection or not sql:
            return "❌ Se requieren 'connection' y 'sql'"
        
        # Validar que es SELECT (seguridad)
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith('SELECT') and not sql_upper.startswith('WITH'):
            return "❌ Solo se permiten consultas SELECT. Usa db_execute para modificaciones."
        
        # Añadir LIMIT si no existe
        if 'LIMIT' not in sql_upper:
            sql = f"{sql.rstrip(';')} LIMIT {limit}"
        
        try:
            # Parsear connection string
            if connection.startswith('sqlite:///'):
                return self._query_sqlite(connection[10:], sql, format)
            elif connection.startswith('postgresql://') or connection.startswith('postgres://'):
                return self._query_postgres(connection, sql, format)
            elif connection.startswith('mysql://'):
                return self._query_mysql(connection, sql, format)
            else:
                return f"❌ Formato de conexión no soportado. Usa sqlite:/// postgresql:// o mysql://"
        
        except Exception as e:
            return f"❌ Error ejecutando query: {str(e)}"
    
    def _query_sqlite(self, db_path: str, sql: str, format: str) -> str:
        if not HAS_SQLITE:
            return "❌ SQLite no disponible"
        
        if not Path(db_path).exists():
            return f"❌ Base de datos no existe: {db_path}"
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description] if cursor.description else []
            
            return self._format_results(columns, [dict(row) for row in rows], format, sql)
        finally:
            conn.close()
    
    def _query_postgres(self, connection: str, sql: str, format: str) -> str:
        if not HAS_POSTGRES:
            return "❌ PostgreSQL driver no instalado. Ejecuta: pip install psycopg2-binary"
        
        conn = psycopg2.connect(connection)
        cursor = conn.cursor()
        
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            rows_dict = [dict(zip(columns, row)) for row in rows]
            return self._format_results(columns, rows_dict, format, sql)
        finally:
            conn.close()
    
    def _query_mysql(self, connection: str, sql: str, format: str) -> str:
        if not HAS_MYSQL:
            return "❌ MySQL driver no instalado. Ejecuta: pip install mysql-connector-python"
        
        # Parsear connection string mysql://user:pass@host:port/db
        match = re.match(r'mysql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', connection)
        if not match:
            return "❌ Formato de conexión MySQL inválido"
        
        user, password, host, port, database = match.groups()
        
        conn = mysql.connector.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database
        )
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = list(rows[0].keys()) if rows else []
            
            return self._format_results(columns, rows, format, sql)
        finally:
            conn.close()
    
    def _format_results(self, columns: List[str], rows: List[Dict], format: str, sql: str) -> str:
        if not rows:
            return f"📊 **Query ejecutada**\n\n`{sql[:100]}`\n\n✅ 0 filas retornadas"
        
        output = f"📊 **Query ejecutada**\n\n`{sql[:100]}`\n\n**{len(rows)} filas:**\n\n"
        
        if format == "json":
            output += f"```json\n{json.dumps(rows[:20], indent=2, default=str)}\n```"
            if len(rows) > 20:
                output += f"\n\n⚠️ Mostrando 20 de {len(rows)} filas"
        
        elif format == "csv":
            output += "```csv\n"
            output += ",".join(columns) + "\n"
            for row in rows[:30]:
                output += ",".join([str(row.get(c, ''))[:30] for c in columns]) + "\n"
            output += "```"
            if len(rows) > 30:
                output += f"\n\n⚠️ Mostrando 30 de {len(rows)} filas"
        
        else:  # table
            # Calcular anchos de columna
            widths = {c: max(len(c), max(len(str(row.get(c, ''))[:20]) for row in rows[:20])) for c in columns}
            
            # Header
            output += "| " + " | ".join(c.ljust(widths[c])[:20] for c in columns) + " |\n"
            output += "|-" + "-|-".join("-" * min(widths[c], 20) for c in columns) + "-|\n"
            
            # Rows
            for row in rows[:20]:
                output += "| " + " | ".join(str(row.get(c, ''))[:20].ljust(widths[c])[:20] for c in columns) + " |\n"
            
            if len(rows) > 20:
                output += f"\n⚠️ Mostrando 20 de {len(rows)} filas"
        
        return output


class DatabaseSchemaTool(BaseTool):
    # Muestra el esquema de una base de datos.
    #
    # Incluye tablas, columnas, tipos, índices y relaciones.
    
    name = "db_schema"
    description = """Muestra el esquema completo de una base de datos.

Muestra:
- Lista de tablas
- Columnas con tipos de datos
- Claves primarias y foráneas
- Índices
- Conteo de filas por tabla

Ejemplo: connection="sqlite:///app.db"
"""
    category = "database"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "connection": ToolParameter(
                name="connection",
                type="string",
                description="String de conexión",
                required=True
            ),
            "table": ToolParameter(
                name="table",
                type="string",
                description="Tabla específica a analizar (opcional)",
                required=False
            ),
            "show_counts": ToolParameter(
                name="show_counts",
                type="boolean",
                description="Mostrar conteo de filas por tabla (default: true)",
                required=False
            )
        }
    
    def execute(
        self,
        connection: str = None,
        table: str = None,
        show_counts: bool = True,
        **kwargs
    ) -> str:
        connection = connection or kwargs.get('connection', '')
        table = table or kwargs.get('table', None)
        show_counts = show_counts if show_counts is not None else kwargs.get('show_counts', True)
        
        if not connection:
            return "❌ Se requiere 'connection'"
        
        try:
            if connection.startswith('sqlite:///'):
                return self._schema_sqlite(connection[10:], table, show_counts)
            elif connection.startswith('postgresql://') or connection.startswith('postgres://'):
                return self._schema_postgres(connection, table, show_counts)
            else:
                return "❌ Formato de conexión no soportado"
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def _schema_sqlite(self, db_path: str, table: str, show_counts: bool) -> str:
        if not Path(db_path).exists():
            return f"❌ Base de datos no existe: {db_path}"
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            output = f"📋 **Esquema de Base de Datos**\n\n`{db_path}`\n\n"
            
            # Obtener tablas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            
            if table:
                tables = [t for t in tables if t == table]
                if not tables:
                    return f"❌ Tabla no encontrada: {table}"
            
            output += f"**Tablas ({len(tables)}):**\n\n"
            
            for tbl in tables:
                # Info de columnas
                cursor.execute(f"PRAGMA table_info({tbl})")
                columns = cursor.fetchall()
                
                # Conteo
                count_str = ""
                if show_counts:
                    cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
                    count = cursor.fetchone()[0]
                    count_str = f" ({count:,} filas)"
                
                output += f"### 📊 `{tbl}`{count_str}\n\n"
                output += "| Columna | Tipo | PK | Not Null | Default |\n"
                output += "|---------|------|:--:|:--------:|:-------:|\n"
                
                for col in columns:
                    cid, name, dtype, notnull, default, pk = col
                    output += f"| {name} | {dtype} | {'✓' if pk else ''} | {'✓' if notnull else ''} | {default or ''} |\n"
                
                # Índices
                cursor.execute(f"PRAGMA index_list({tbl})")
                indexes = cursor.fetchall()
                
                if indexes:
                    output += f"\n**Índices:**\n"
                    for idx in indexes:
                        output += f"- `{idx[1]}` {'(único)' if idx[2] else ''}\n"
                
                output += "\n"
            
            return output
            
        finally:
            conn.close()
    
    def _schema_postgres(self, connection: str, table: str, show_counts: bool) -> str:
        if not HAS_POSTGRES:
            return "❌ PostgreSQL driver no instalado"
        
        conn = psycopg2.connect(connection)
        cursor = conn.cursor()
        
        try:
            output = "📋 **Esquema de Base de Datos (PostgreSQL)**\n\n"
            
            # Obtener tablas
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            if table:
                tables = [t for t in tables if t == table]
            
            for tbl in tables:
                # Columnas
                cursor.execute(f"""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = '{tbl}'
                """)
                columns = cursor.fetchall()
                
                count_str = ""
                if show_counts:
                    cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
                    count = cursor.fetchone()[0]
                    count_str = f" ({count:,} filas)"
                
                output += f"### 📊 `{tbl}`{count_str}\n\n"
                output += "| Columna | Tipo | Nullable | Default |\n"
                output += "|---------|------|:--------:|:-------:|\n"
                
                for col in columns:
                    name, dtype, nullable, default = col
                    output += f"| {name} | {dtype} | {'✓' if nullable == 'YES' else ''} | {(default or '')[:20]} |\n"
                
                output += "\n"
            
            return output
            
        finally:
            conn.close()


class DatabaseMigrationTool(BaseTool):
    # Gestiona migraciones de base de datos.
    #
    # Crea, aplica y revierte migraciones.
    
    name = "db_migrate"
    description = """Gestiona migraciones de base de datos.

Acciones:
- create: Crea archivo de migración nuevo
- upgrade: Aplica migraciones pendientes
- rollback: Revierte última migración
- status: Muestra estado de migraciones
- history: Muestra historial

Ejemplos:
- Crear migración: action="create", name="add_users_table"
- Aplicar: action="upgrade"
- Revertir: action="rollback"
"""
    category = "database"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description="Acción: create, upgrade, rollback, status, history",
                required=True,
                enum=["create", "upgrade", "rollback", "status", "history"]
            ),
            "name": ToolParameter(
                name="name",
                type="string",
                description="Nombre de la migración (para create)",
                required=False
            ),
            "migrations_dir": ToolParameter(
                name="migrations_dir",
                type="string",
                description="Directorio de migraciones (default: migrations/)",
                required=False
            )
        }
    
    def execute(
        self,
        action: str = None,
        name: str = None,
        migrations_dir: str = "migrations",
        **kwargs
    ) -> str:
        action = action or kwargs.get('action', '')
        name = name or kwargs.get('name', '')
        migrations_dir = migrations_dir or kwargs.get('migrations_dir', 'migrations')
        
        if not action:
            return "❌ Se requieren 'action'"
        
        mig_path = Path(migrations_dir)
        mig_path.mkdir(exist_ok=True)
        
        if action == "create":
            if not name:
                return "❌ Se requiere 'name' para crear migración"
            
            return self._create_migration(mig_path, name)
        
        elif action == "status":
            return self._migration_status(mig_path)
        
        elif action == "history":
            return self._migration_history(mig_path)
        
        elif action == "upgrade":
            return "⚠️ Upgrade requiere configuración de base de datos. Usa un framework como Alembic o Django migrations."
        
        elif action == "rollback":
            return "⚠️ Rollback requiere configuración de base de datos. Usa un framework como Alembic o Django migrations."
        
        return f"❌ Acción no válida: {action}"
    
    def _create_migration(self, mig_path: Path, name: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{name}.sql"
        filepath = mig_path / filename
        
        template = f"""-- Migration: {name}
-- Created: {datetime.now().isoformat()}

-- ============ UPGRADE ============

-- Escribe aquí los cambios a aplicar



-- ============ DOWNGRADE ============

-- Escribe aquí cómo revertir los cambios

"""
        
        filepath.write_text(template)
        
        return f"""✅ **Migración creada**

Archivo: `{filepath}`

Edita el archivo para añadir:
1. SQL de UPGRADE (cambios a aplicar)
2. SQL de DOWNGRADE (cómo revertir)

```sql
{template[:300]}
```
"""
    
    def _migration_status(self, mig_path: Path) -> str:
        migrations = sorted(mig_path.glob("*.sql"))
        
        if not migrations:
            return "📂 No hay migraciones en el directorio"
        
        output = f"📋 **Estado de Migraciones**\n\nDirectorio: `{mig_path}`\n\n"
        output += "| # | Archivo | Estado |\n"
        output += "|---|---------|--------|\n"
        
        for i, mig in enumerate(migrations, 1):
            output += f"| {i} | {mig.name} | ⏳ Pendiente |\n"
        
        output += "\n💡 Para aplicar migraciones, configura un framework como Alembic."
        
        return output
    
    def _migration_history(self, mig_path: Path) -> str:
        migrations = sorted(mig_path.glob("*.sql"))
        
        if not migrations:
            return "📂 No hay migraciones"
        
        output = "📜 **Historial de Migraciones**\n\n"
        
        for mig in migrations:
            content = mig.read_text()[:200]
            output += f"**{mig.name}**\n```sql\n{content}\n```\n\n"
        
        return output


class DatabaseBackupTool(BaseTool):
    # Crea backups de bases de datos.
    #
    # Soporta SQLite, PostgreSQL y MySQL.
    
    name = "db_backup"
    description = """Crea backup de una base de datos.

Formatos:
- SQLite: Copia el archivo .db
- PostgreSQL: Usa pg_dump
- MySQL: Usa mysqldump

Ejemplos:
- SQLite: connection="sqlite:///app.db", output="backup.sql"
- PostgreSQL: connection="postgresql://user:pass@host/db", output="backup.sql"
"""
    category = "database"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "connection": ToolParameter(
                name="connection",
                type="string",
                description="String de conexión",
                required=True
            ),
            "output": ToolParameter(
                name="output",
                type="string",
                description="Archivo de salida",
                required=True
            ),
            "format": ToolParameter(
                name="format",
                type="string",
                description="Formato: sql, binary (default: sql)",
                required=False,
                enum=["sql", "binary"]
            ),
            "tables": ToolParameter(
                name="tables",
                type="array",
                description="Tablas específicas (opcional, default: todas)",
                required=False
            )
        }
    
    def execute(
        self,
        connection: str = None,
        output: str = None,
        format: str = "sql",
        tables: List[str] = None,
        **kwargs
    ) -> str:
        connection = connection or kwargs.get('connection', '')
        output = output or kwargs.get('output', '')
        format = format or kwargs.get('format', 'sql')
        tables = tables or kwargs.get('tables', None)
        
        if not connection or not output:
            return "❌ Se requieren 'connection' y 'output'"
        
        try:
            if connection.startswith('sqlite:///'):
                return self._backup_sqlite(connection[10:], output, format)
            elif connection.startswith('postgresql://'):
                return self._backup_postgres(connection, output, tables)
            elif connection.startswith('mysql://'):
                return self._backup_mysql(connection, output, tables)
            else:
                return "❌ Formato de conexión no soportado"
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def _backup_sqlite(self, db_path: str, output: str, format: str) -> str:
        import shutil
        
        if not Path(db_path).exists():
            return f"❌ Base de datos no existe: {db_path}"
        
        if format == "binary":
            shutil.copy2(db_path, output)
            size = Path(output).stat().st_size
            return f"""✅ **Backup SQLite creado**

| Propiedad | Valor |
|-----------|-------|
| Origen | {db_path} |
| Destino | {output} |
| Tamaño | {size / 1024:.1f} KB |
| Formato | Binario (copia directa) |
"""
        else:
            # Exportar como SQL
            conn = sqlite3.connect(db_path)
            
            with open(output, 'w') as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
            
            conn.close()
            size = Path(output).stat().st_size
            
            return f"""✅ **Backup SQLite creado**

| Propiedad | Valor |
|-----------|-------|
| Origen | {db_path} |
| Destino | {output} |
| Tamaño | {size / 1024:.1f} KB |
| Formato | SQL dump |

💡 Restaurar con: `sqlite3 new.db < {output}`
"""
    
    def _backup_postgres(self, connection: str, output: str, tables: List[str]) -> str:
        # Parsear connection string
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):?(\d+)?/(.+)', connection)
        if not match:
            return "❌ Formato de conexión PostgreSQL inválido"
        
        user, password, host, port, database = match.groups()
        port = port or "5432"
        
        cmd = [
            "pg_dump",
            "-h", host,
            "-p", port,
            "-U", user,
            "-d", database,
            "-f", output
        ]
        
        if tables:
            for t in tables:
                cmd.extend(["-t", t])
        
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                size = Path(output).stat().st_size
                return f"""✅ **Backup PostgreSQL creado**

| Propiedad | Valor |
|-----------|-------|
| Base de datos | {database} |
| Destino | {output} |
| Tamaño | {size / 1024:.1f} KB |

💡 Restaurar con: `psql -h {host} -U {user} -d {database} < {output}`
"""
            else:
                return f"❌ Error pg_dump:\n{result.stderr}"
        except FileNotFoundError:
            return "❌ pg_dump no encontrado. Instala PostgreSQL client."
    
    def _backup_mysql(self, connection: str, output: str, tables: List[str]) -> str:
        match = re.match(r'mysql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', connection)
        if not match:
            return "❌ Formato de conexión MySQL inválido"
        
        user, password, host, port, database = match.groups()
        
        cmd = [
            "mysqldump",
            "-h", host,
            "-P", port,
            "-u", user,
            f"-p{password}",
            database
        ]
        
        if tables:
            cmd.extend(tables)
        
        try:
            with open(output, 'w') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, timeout=300)
            
            if result.returncode == 0:
                size = Path(output).stat().st_size
                return f"""✅ **Backup MySQL creado**

| Propiedad | Valor |
|-----------|-------|
| Base de datos | {database} |
| Destino | {output} |
| Tamaño | {size / 1024:.1f} KB |

💡 Restaurar con: `mysql -h {host} -u {user} -p {database} < {output}`
"""
            else:
                return f"❌ Error mysqldump:\n{result.stderr}"
        except FileNotFoundError:
            return "❌ mysqldump no encontrado. Instala MySQL client."