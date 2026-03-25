# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS DE SEGURIDAD
# Detección de secrets, hashes, JWT, permisos
# ═══════════════════════════════════════════════════════════════════════════════

import re
import os
import stat
import hashlib
import base64
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .base import BaseTool, ToolParameter


class SecretsDetectorTool(BaseTool):
    # Detecta secrets, API keys, passwords y tokens expuestos en código.
    #
    # Escanea archivos buscando patrones comunes de credenciales
    # que no deberían estar en el código fuente.
    
    name = "detect_secrets"
    description = """Detecta secrets y credenciales expuestas en código.

Busca:
- API Keys (AWS, Google, GitHub, etc.)
- Passwords hardcoded
- Tokens JWT
- Connection strings con credenciales
- Private keys
- Secrets genéricos

Ejemplo: path="." (escanea directorio actual)
Excluye automáticamente: node_modules, .git, __pycache__, venv
"""
    category = "security"
    
    # Patrones de secrets comunes
    PATTERNS = {
        "AWS Access Key": r'AKIA[0-9A-Z]{16}',
        "AWS Secret Key": r'(?i)aws(.{0,20})?[\'"][0-9a-zA-Z\/+]{40}[\'"]',
        "GitHub Token": r'ghp_[a-zA-Z0-9]{36}',
        "GitHub OAuth": r'gho_[a-zA-Z0-9]{36}',
        "Google API Key": r'AIza[0-9A-Za-z\-_]{35}',
        "Slack Token": r'xox[baprs]-[0-9]{10,13}-[0-9a-zA-Z]{24}',
        "Slack Webhook": r'https://hooks\.slack\.com/services/T[a-zA-Z0-9_]+/B[a-zA-Z0-9_]+/[a-zA-Z0-9_]+',
        "Discord Webhook": r'https://discord(?:app)?\.com/api/webhooks/\d+/[\w-]+',
        "Discord Token": r'[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27}',
        "Stripe Key": r'sk_live_[0-9a-zA-Z]{24}',
        "Stripe Publishable": r'pk_live_[0-9a-zA-Z]{24}',
        "Twilio SID": r'AC[a-zA-Z0-9_\-]{32}',
        "Twilio Token": r'(?i)twilio(.{0,20})?[\'"][a-zA-Z0-9]{32}[\'"]',
        "SendGrid Key": r'SG\.[a-zA-Z0-9]{22}\.[a-zA-Z0-9]{43}',
        "Mailgun Key": r'key-[0-9a-zA-Z]{32}',
        "Heroku API Key": r'(?i)heroku(.{0,20})?[\'"][0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}[\'"]',
        "JWT Token": r'eyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*',
        "Generic API Key": r'(?i)(api[_-]?key|apikey|api_secret)[\'"\s:=]+[\'"]?[a-zA-Z0-9_\-]{20,}[\'"]?',
        "Generic Secret": r'(?i)(secret|password|passwd|pwd)[\'"\s:=]+[\'"]?[^\s\'",]{8,}[\'"]?',
        "Private Key": r'-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
        "Database URL": r'(?i)(postgres|mysql|mongodb|redis)://[^\s\'">]+:[^\s\'">]+@[^\s\'">]+',
        "Basic Auth": r'(?i)authorization:\s*basic\s+[a-zA-Z0-9+/=]+',
        "Bearer Token": r'(?i)bearer\s+[a-zA-Z0-9_\-\.]+',
        "NPM Token": r'//registry\.npmjs\.org/:_authToken=[a-zA-Z0-9\-]+',
        "PyPI Token": r'pypi-[a-zA-Z0-9]{32,}',
    }
    
    EXCLUDE_DIRS = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', 'env', '.env', 'dist', 'build', '.idea', '.vscode'}
    EXCLUDE_EXTENSIONS = {'.pyc', '.pyo', '.exe', '.dll', '.so', '.dylib', '.bin', '.dat', '.db', '.sqlite', '.jpg', '.png', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz'}
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(
                name="path",
                type="string",
                description="Directorio o archivo a escanear",
                required=True
            ),
            "include_pattern": ToolParameter(
                name="include_pattern",
                type="string",
                description="Patrón de archivos a incluir (ej: *.py)",
                required=False
            ),
            "show_context": ToolParameter(
                name="show_context",
                type="boolean",
                description="Mostrar contexto alrededor del secret (default: true)",
                required=False
            ),
            "max_findings": ToolParameter(
                name="max_findings",
                type="integer",
                description="Máximo de hallazgos a mostrar (default: 50)",
                required=False
            )
        }
    
    def execute(
        self,
        path: str = None,
        include_pattern: str = None,
        show_context: bool = True,
        max_findings: int = 50,
        **kwargs
    ) -> str:
        path = path or kwargs.get('path', '.')
        include_pattern = include_pattern or kwargs.get('include_pattern', None)
        show_context = show_context if show_context is not None else kwargs.get('show_context', True)
        max_findings = max_findings or kwargs.get('max_findings', 50)
        
        scan_path = Path(path)
        if not scan_path.exists():
            return f"❌ Ruta no existe: {path}"
        
        findings = []
        files_scanned = 0
        
        # Obtener archivos a escanear
        if scan_path.is_file():
            files = [scan_path]
        else:
            files = self._get_files(scan_path, include_pattern)
        
        for file_path in files:
            if len(findings) >= max_findings:
                break
            
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                files_scanned += 1
                
                for secret_type, pattern in self.PATTERNS.items():
                    for match in re.finditer(pattern, content):
                        if len(findings) >= max_findings:
                            break
                        
                        # Obtener línea
                        line_start = content.rfind('\n', 0, match.start()) + 1
                        line_end = content.find('\n', match.end())
                        if line_end == -1:
                            line_end = len(content)
                        
                        line_num = content[:match.start()].count('\n') + 1
                        line_content = content[line_start:line_end].strip()
                        
                        # Censurar parte del secret
                        secret_value = match.group()
                        if len(secret_value) > 10:
                            censored = secret_value[:6] + '*' * (len(secret_value) - 10) + secret_value[-4:]
                        else:
                            censored = secret_value[:2] + '*' * (len(secret_value) - 2)
                        
                        findings.append({
                            'file': str(file_path),
                            'line': line_num,
                            'type': secret_type,
                            'secret': censored,
                            'context': line_content[:100] if show_context else None
                        })
            except Exception:
                continue
        
        # Generar reporte
        if not findings:
            return f"""✅ **No se encontraron secrets expuestos**

| Propiedad | Valor |
|-----------|-------|
| Ruta | {path} |
| Archivos escaneados | {files_scanned} |
| Patrones verificados | {len(self.PATTERNS)} |

💡 Esto no garantiza que no haya secrets, solo que no coinciden con patrones conocidos.
"""
        
        # Agrupar por tipo
        by_type = {}
        for f in findings:
            t = f['type']
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(f)
        
        output = f"""🔐 **Secrets Detectados**

| Propiedad | Valor |
|-----------|-------|
| Ruta | {path} |
| Archivos escaneados | {files_scanned} |
| Secrets encontrados | {len(findings)} |
| Tipos diferentes | {len(by_type)} |

⚠️ **IMPORTANTE:** Estos secrets podrían estar expuestos. Revísalos y rótalos si es necesario.

---

"""
        
        for secret_type, items in sorted(by_type.items()):
            output += f"### 🔑 {secret_type} ({len(items)})\n\n"
            
            for item in items[:5]:
                output += f"**{item['file']}:{item['line']}**\n"
                output += f"- Secret: `{item['secret']}`\n"
                if item['context']:
                    ctx = item['context'].replace(item['secret'].replace('*', ''), '[REDACTED]')
                    output += f"- Contexto: `{ctx[:60]}...`\n"
                output += "\n"
            
            if len(items) > 5:
                output += f"... y {len(items) - 5} más de este tipo\n\n"
        
        output += """---

**🛡️ Recomendaciones:**
1. Usa variables de entorno para secrets
2. Añade archivos sensibles a `.gitignore`
3. Usa un gestor de secrets (Vault, AWS Secrets Manager)
4. Rota los secrets que hayan sido expuestos
"""
        
        return output
    
    def _get_files(self, path: Path, pattern: str) -> List[Path]:
        files = []
        
        for item in path.rglob(pattern or '*'):
            if item.is_file():
                # Excluir directorios
                if any(excluded in item.parts for excluded in self.EXCLUDE_DIRS):
                    continue
                
                # Excluir extensiones
                if item.suffix.lower() in self.EXCLUDE_EXTENSIONS:
                    continue
                
                # Excluir archivos muy grandes (>1MB)
                try:
                    if item.stat().st_size > 1024 * 1024:
                        continue
                except:
                    continue
                
                files.append(item)
        
        return files[:1000]  # Limitar a 1000 archivos


class HashGeneratorTool(BaseTool):
    # Genera y verifica hashes criptográficos.
    #
    # Soporta múltiples algoritmos: MD5, SHA1, SHA256, SHA512, bcrypt.
    
    name = "hash_generate"
    description = """Genera o verifica hashes criptográficos.

Algoritmos soportados:
- md5: Rápido pero inseguro (solo para checksums)
- sha1: Legacy, no recomendado para seguridad
- sha256: Recomendado para integridad
- sha512: Más seguro, más lento
- bcrypt: Para passwords (requiere pip install bcrypt)

Ejemplos:
- Generar hash: algorithm="sha256", input="mi texto"
- Hash de archivo: algorithm="sha256", input="archivo.txt", is_file=true
- Verificar: algorithm="sha256", input="texto", verify="hash_esperado"
"""
    category = "security"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "algorithm": ToolParameter(
                name="algorithm",
                type="string",
                description="Algoritmo: md5, sha1, sha256, sha512, bcrypt",
                required=True,
                enum=["md5", "sha1", "sha256", "sha512", "bcrypt"]
            ),
            "input": ToolParameter(
                name="input",
                type="string",
                description="Texto o ruta de archivo a hashear",
                required=True
            ),
            "is_file": ToolParameter(
                name="is_file",
                type="boolean",
                description="Si input es ruta de archivo (default: false)",
                required=False
            ),
            "verify": ToolParameter(
                name="verify",
                type="string",
                description="Hash a verificar (opcional)",
                required=False
            )
        }
    
    def execute(
        self,
        algorithm: str = None,
        input: str = None,
        is_file: bool = False,
        verify: str = None,
        **kwargs
    ) -> str:
        algorithm = (algorithm or kwargs.get('algorithm', 'sha256')).lower()
        input_data = input or kwargs.get('input', '')
        is_file = is_file or kwargs.get('is_file', False)
        verify = verify or kwargs.get('verify', None)
        
        if not input_data:
            return "❌ Se requiere 'input'"
        
        # Obtener datos
        if is_file:
            path = Path(input_data)
            if not path.exists():
                return f"❌ Archivo no existe: {input_data}"
            data = path.read_bytes()
        else:
            data = input_data.encode('utf-8')
        
        # Generar hash
        try:
            if algorithm == 'bcrypt':
                return self._bcrypt_hash(data, verify)
            
            hash_func = {
                'md5': hashlib.md5,
                'sha1': hashlib.sha1,
                'sha256': hashlib.sha256,
                'sha512': hashlib.sha512
            }.get(algorithm)
            
            if not hash_func:
                return f"❌ Algoritmo no soportado: {algorithm}"
            
            computed_hash = hash_func(data).hexdigest()
            
            if verify:
                match = computed_hash.lower() == verify.lower()
                status = "✅ Hash coincide" if match else "❌ Hash NO coincide"
                
                return f"""🔐 **Verificación de Hash**

| Propiedad | Valor |
|-----------|-------|
| Algoritmo | {algorithm.upper()} |
| Input | {input_data[:50]}{'...' if len(input_data) > 50 else ''} |
| Hash calculado | `{computed_hash}` |
| Hash esperado | `{verify}` |
| **Resultado** | **{status}** |
"""
            else:
                return f"""🔐 **Hash Generado**

| Propiedad | Valor |
|-----------|-------|
| Algoritmo | {algorithm.upper()} |
| Input | {input_data[:50]}{'...' if len(input_data) > 50 else ''} |
| Tamaño | {len(data)} bytes |

**Hash:**
```
{computed_hash}
```
"""
        
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def _bcrypt_hash(self, data: bytes, verify: str) -> str:
        try:
            import bcrypt
        except ImportError:
            return "❌ bcrypt no instalado. Ejecuta: pip install bcrypt"
        
        if verify:
            try:
                match = bcrypt.checkpw(data, verify.encode('utf-8'))
                status = "✅ Password coincide" if match else "❌ Password NO coincide"
                return f"""🔐 **Verificación bcrypt**

| Resultado | {status} |
"""
            except Exception as e:
                return f"❌ Error verificando: {e}"
        else:
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(data, salt)
            
            return f"""🔐 **Hash bcrypt Generado**

**Hash:**
```
{hashed.decode('utf-8')}
```

💡 Guarda este hash para verificar passwords.
"""


class JWTDecoderTool(BaseTool):
    # Decodifica y analiza tokens JWT.
    #
    # Muestra header, payload y verifica estructura.
    
    name = "jwt_decode"
    description = """Decodifica y analiza tokens JWT.

Muestra:
- Header (algoritmo, tipo)
- Payload (claims, expiración)
- Verificación de estructura
- Advertencias de seguridad

Ejemplo: token="eyJhbGciOiJIUzI1NiIs..."

⚠️ No verifica la firma (requiere secret key)
"""
    category = "security"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "token": ToolParameter(
                name="token",
                type="string",
                description="Token JWT a decodificar",
                required=True
            ),
            "verify_exp": ToolParameter(
                name="verify_exp",
                type="boolean",
                description="Verificar expiración (default: true)",
                required=False
            )
        }
    
    def execute(
        self,
        token: str = None,
        verify_exp: bool = True,
        **kwargs
    ) -> str:
        token = token or kwargs.get('token', '')
        verify_exp = verify_exp if verify_exp is not None else kwargs.get('verify_exp', True)
        
        if not token:
            return "❌ Se requiere 'token'"
        
        # Limpiar token
        token = token.strip()
        if token.lower().startswith('bearer '):
            token = token[7:]
        
        parts = token.split('.')
        if len(parts) != 3:
            return f"❌ Token JWT inválido. Debe tener 3 partes separadas por '.', tiene {len(parts)}"
        
        try:
            # Decodificar header
            header_b64 = parts[0]
            # Añadir padding si es necesario
            header_b64 += '=' * (4 - len(header_b64) % 4)
            header = json.loads(base64.urlsafe_b64decode(header_b64))
            
            # Decodificar payload
            payload_b64 = parts[1]
            payload_b64 += '=' * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            
        except Exception as e:
            return f"❌ Error decodificando JWT: {str(e)}"
        
        # Analizar claims
        warnings = []
        
        # Verificar expiración
        exp = payload.get('exp')
        exp_status = "No especificado"
        if exp:
            try:
                exp_date = datetime.fromtimestamp(exp)
                if exp_date < datetime.now():
                    exp_status = f"❌ EXPIRADO ({exp_date.isoformat()})"
                    warnings.append("Token expirado")
                else:
                    exp_status = f"✅ Válido hasta {exp_date.isoformat()}"
            except:
                exp_status = f"Valor: {exp}"
        
        # Verificar algoritmo
        alg = header.get('alg', 'none')
        if alg.lower() == 'none':
            warnings.append("⚠️ Algoritmo 'none' - Token no firmado")
        elif alg.lower() in ['hs256', 'hs384', 'hs512']:
            pass  # OK
        elif alg.lower() in ['rs256', 'rs384', 'rs512', 'es256', 'es384', 'es512']:
            pass  # OK - Asimétrico
        else:
            warnings.append(f"⚠️ Algoritmo poco común: {alg}")
        
        # Claims estándar
        iat = payload.get('iat')
        iat_str = datetime.fromtimestamp(iat).isoformat() if iat else "No especificado"
        
        nbf = payload.get('nbf')
        nbf_str = datetime.fromtimestamp(nbf).isoformat() if nbf else "No especificado"
        
        output = f"""🔑 **JWT Decodificado**

**📋 Header:**
```json
{json.dumps(header, indent=2)}
```

**📦 Payload:**
```json
{json.dumps(payload, indent=2, default=str)}
```

**⏰ Timestamps:**
| Claim | Valor |
|-------|-------|
| Issued At (iat) | {iat_str} |
| Not Before (nbf) | {nbf_str} |
| Expiration (exp) | {exp_status} |

**📊 Claims presentes:** {', '.join(payload.keys())}

"""
        
        if warnings:
            output += "**⚠️ Advertencias:**\n"
            for w in warnings:
                output += f"- {w}\n"
        
        output += """
---
💡 **Nota:** Esta herramienta solo decodifica, no verifica la firma.
   Para verificar la firma necesitas la secret key o public key.
"""
        
        return output


class PermissionsCheckTool(BaseTool):
    # Verifica permisos de archivos y detecta configuraciones inseguras.
    
    name = "check_permissions"
    description = """Verifica permisos de archivos y directorios.

Detecta:
- Archivos world-writable (777)
- Archivos sensibles con permisos amplios
- SUID/SGID bits
- Archivos sin dueño

Ejemplo: path="/var/www"
Útil para auditorías de seguridad.
"""
    category = "security"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "path": ToolParameter(
                name="path",
                type="string",
                description="Directorio a verificar",
                required=True
            ),
            "recursive": ToolParameter(
                name="recursive",
                type="boolean",
                description="Escanear recursivamente (default: true)",
                required=False
            ),
            "check_sensitive": ToolParameter(
                name="check_sensitive",
                type="boolean",
                description="Verificar archivos sensibles (.env, keys, etc.)",
                required=False
            )
        }
    
    SENSITIVE_PATTERNS = [
        '*.pem', '*.key', '*.crt', '*.p12', '*.pfx',
        '.env', '.env.*', 'credentials*', 'secrets*',
        'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519',
        '*.sqlite', '*.db', 'config.json', 'settings.json'
    ]
    
    def execute(
        self,
        path: str = None,
        recursive: bool = True,
        check_sensitive: bool = True,
        **kwargs
    ) -> str:
        path = path or kwargs.get('path', '.')
        recursive = recursive if recursive is not None else kwargs.get('recursive', True)
        check_sensitive = check_sensitive if check_sensitive is not None else kwargs.get('check_sensitive', True)
        
        scan_path = Path(path)
        if not scan_path.exists():
            return f"❌ Ruta no existe: {path}"
        
        issues = []
        files_checked = 0
        
        # Obtener archivos
        if recursive:
            files = list(scan_path.rglob('*'))
        else:
            files = list(scan_path.glob('*'))
        
        for file_path in files:
            try:
                files_checked += 1
                stat_info = file_path.stat()
                mode = stat_info.st_mode
                
                # World-writable
                if mode & stat.S_IWOTH:
                    issues.append({
                        'file': str(file_path),
                        'issue': 'World-writable',
                        'severity': 'HIGH',
                        'perms': oct(mode)[-3:]
                    })
                
                # SUID bit
                if mode & stat.S_ISUID:
                    issues.append({
                        'file': str(file_path),
                        'issue': 'SUID bit set',
                        'severity': 'MEDIUM',
                        'perms': oct(mode)[-4:]
                    })
                
                # SGID bit
                if mode & stat.S_ISGID:
                    issues.append({
                        'file': str(file_path),
                        'issue': 'SGID bit set',
                        'severity': 'LOW',
                        'perms': oct(mode)[-4:]
                    })
                
                # Archivos sensibles con permisos amplios
                if check_sensitive:
                    is_sensitive = any(
                        file_path.match(pattern) for pattern in self.SENSITIVE_PATTERNS
                    )
                    
                    if is_sensitive:
                        # Verificar si es legible por otros
                        if mode & stat.S_IROTH or mode & stat.S_IRGRP:
                            issues.append({
                                'file': str(file_path),
                                'issue': 'Archivo sensible legible por otros',
                                'severity': 'HIGH',
                                'perms': oct(mode)[-3:]
                            })
                
            except PermissionError:
                continue
            except Exception:
                continue
        
        # Generar reporte
        if not issues:
            return f"""✅ **No se encontraron problemas de permisos**

| Propiedad | Valor |
|-----------|-------|
| Ruta | {path} |
| Archivos verificados | {files_checked} |
| Recursivo | {'Sí' if recursive else 'No'} |
"""
        
        # Agrupar por severidad
        high = [i for i in issues if i['severity'] == 'HIGH']
        medium = [i for i in issues if i['severity'] == 'MEDIUM']
        low = [i for i in issues if i['severity'] == 'LOW']
        
        output = f"""🔒 **Análisis de Permisos**

| Propiedad | Valor |
|-----------|-------|
| Ruta | {path} |
| Archivos verificados | {files_checked} |
| Problemas encontrados | {len(issues)} |

**Resumen:**
- 🔴 Alta severidad: {len(high)}
- 🟡 Media severidad: {len(medium)}
- 🟢 Baja severidad: {len(low)}

---

"""
        
        if high:
            output += "### 🔴 Alta Severidad\n\n"
            for issue in high[:10]:
                output += f"- `{issue['file']}` ({issue['perms']})\n"
                output += f"  {issue['issue']}\n"
            if len(high) > 10:
                output += f"- ... y {len(high) - 10} más\n"
            output += "\n"
        
        if medium:
            output += "### 🟡 Media Severidad\n\n"
            for issue in medium[:10]:
                output += f"- `{issue['file']}` - {issue['issue']}\n"
            output += "\n"
        
        output += """---

**🛡️ Recomendaciones:**
- Archivos sensibles: `chmod 600 archivo`
- Directorios: `chmod 755 directorio`
- Remover world-writable: `chmod o-w archivo`
"""
        
        return output