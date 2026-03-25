# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS DEVOPS
# Network Scan, Cron Scheduler
# ═══════════════════════════════════════════════════════════════════════════════

import socket
import subprocess
import re
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import BaseTool, ToolParameter


class NetworkScanTool(BaseTool):
    # Escanea red para descubrir hosts y puertos abiertos.
    #
    # Útil para:
    # - Descubrir dispositivos en red local
    # - Verificar servicios activos
    # - Auditoría básica de red
    
    name = "network_scan"
    description = """Escanea red para descubrir hosts y puertos.

Funcionalidades:
- Ping sweep para descubrir hosts activos
- Escaneo de puertos comunes
- Detección de servicios

Ejemplos:
- Escanear red local: subnet="192.168.1.0/24"
- Escanear host específico: target="192.168.1.1", ports="22,80,443"
- Rango de puertos: target="10.0.0.5", ports="1-1000"

⚠️ Solo usar en redes propias o con autorización.
"""
    category = "devops"
    
    COMMON_PORTS = {
        21: 'FTP',
        22: 'SSH',
        23: 'Telnet',
        25: 'SMTP',
        53: 'DNS',
        80: 'HTTP',
        110: 'POP3',
        143: 'IMAP',
        443: 'HTTPS',
        445: 'SMB',
        3306: 'MySQL',
        5432: 'PostgreSQL',
        6379: 'Redis',
        8080: 'HTTP-Alt',
        8443: 'HTTPS-Alt',
        27017: 'MongoDB'
    }
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "target": ToolParameter(
                name="target",
                type="string",
                description="IP o hostname a escanear",
                required=False
            ),
            "subnet": ToolParameter(
                name="subnet",
                type="string",
                description="Subred CIDR (ej: 192.168.1.0/24)",
                required=False
            ),
            "ports": ToolParameter(
                name="ports",
                type="string",
                description="Puertos: 'common', '22,80,443', '1-1000'",
                required=False
            ),
            "timeout": ToolParameter(
                name="timeout",
                type="number",
                description="Timeout por conexión en segundos (default: 1)",
                required=False
            )
        }
    
    def execute(
        self,
        target: str = None,
        subnet: str = None,
        ports: str = "common",
        timeout: float = 1.0,
        **kwargs
    ) -> str:
        target = target or kwargs.get('target', None)
        subnet = subnet or kwargs.get('subnet', None)
        ports = ports or kwargs.get('ports', 'common')
        timeout = timeout or kwargs.get('timeout', 1.0)
        
        if not target and not subnet:
            return "❌ Se requiere 'target' o 'subnet'"
        
        if subnet:
            return self._scan_subnet(subnet, timeout)
        else:
            return self._scan_host(target, ports, timeout)
    
    def _scan_subnet(self, subnet: str, timeout: float) -> str:
        # Parsear CIDR
        match = re.match(r'(\d+\.\d+\.\d+)\.(\d+)/(\d+)', subnet)
        if not match:
            return f"❌ Formato de subred inválido: {subnet}"
        
        base_ip = match.group(1)
        start = int(match.group(2))
        cidr = int(match.group(3))
        
        # Calcular rango (simplificado para /24)
        if cidr == 24:
            hosts = [f"{base_ip}.{i}" for i in range(1, 255)]
        elif cidr == 16:
            # Limitar para no tardar mucho
            hosts = [f"{base_ip}.{i}" for i in range(1, 255)]
        else:
            hosts = [f"{base_ip}.{i}" for i in range(max(1, start-10), min(255, start+10))]
        
        print(f"🔍 Escaneando {len(hosts)} hosts...")
        
        alive_hosts = []
        
        def ping_host(ip):
            try:
                # Intentar conexión TCP al puerto 80 o 443 (más rápido que ping)
                for port in [80, 443, 22]:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((ip, port))
                    sock.close()
                    if result == 0:
                        return ip, port
                return None, None
            except:
                return None, None
        
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(ping_host, ip): ip for ip in hosts}
            
            for future in as_completed(futures, timeout=60):
                try:
                    ip, port = future.result()
                    if ip:
                        alive_hosts.append({'ip': ip, 'port': port})
                except:
                    continue
        
        if not alive_hosts:
            return f"""🔍 **Escaneo de Red: {subnet}**

No se encontraron hosts activos.

💡 Posibles razones:
- Firewall bloqueando conexiones
- Hosts no responden en puertos comunes
- Red incorrecta
"""
        
        output = f"""🌐 **Escaneo de Red: {subnet}**

| Hosts escaneados | {len(hosts)} |
| Hosts activos | {len(alive_hosts)} |

**Hosts encontrados:**

| IP | Puerto Detectado |
|----| ----------------|
"""
        
        for host in sorted(alive_hosts, key=lambda x: [int(i) for i in x['ip'].split('.')]):
            service = self.COMMON_PORTS.get(host['port'], 'Unknown')
            output += f"| {host['ip']} | {host['port']} ({service}) |\n"
        
        return output
    
    def _scan_host(self, target: str, ports_spec: str, timeout: float) -> str:
        # Resolver hostname
        try:
            ip = socket.gethostbyname(target)
        except socket.gaierror:
            return f"❌ No se puede resolver: {target}"
        
        # Parsear puertos
        if ports_spec == 'common':
            ports_to_scan = list(self.COMMON_PORTS.keys())
        elif '-' in ports_spec:
            start, end = map(int, ports_spec.split('-'))
            ports_to_scan = list(range(start, min(end + 1, start + 1000)))
        else:
            ports_to_scan = [int(p.strip()) for p in ports_spec.split(',')]
        
        print(f"🔍 Escaneando {len(ports_to_scan)} puertos en {target}...")
        
        open_ports = []
        
        def scan_port(port):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                sock.close()
                return port if result == 0 else None
            except:
                return None
        
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = {executor.submit(scan_port, port): port for port in ports_to_scan}
            
            for future in as_completed(futures, timeout=120):
                try:
                    port = future.result()
                    if port:
                        open_ports.append(port)
                except:
                    continue
        
        open_ports.sort()
        
        output = f"""🎯 **Escaneo de Host: {target}**

| Propiedad | Valor |
|-----------|-------|
| Target | {target} |
| IP | {ip} |
| Puertos escaneados | {len(ports_to_scan)} |
| Puertos abiertos | {len(open_ports)} |

"""
        
        if open_ports:
            output += "**Puertos Abiertos:**\n\n"
            output += "| Puerto | Servicio |\n"
            output += "|--------|----------|\n"
            
            for port in open_ports:
                service = self.COMMON_PORTS.get(port, 'Unknown')
                output += f"| {port} | {service} |\n"
        else:
            output += "No se encontraron puertos abiertos.\n"
        
        return output


class CronSchedulerTool(BaseTool):
    # Gestiona tareas programadas con cron.
    #
    # Permite crear, listar y eliminar jobs de cron.
    
    name = "cron_schedule"
    description = """Gestiona tareas programadas con cron.

Acciones:
- list: Ver crontab actual
- add: Agregar tarea
- remove: Eliminar tarea
- validate: Validar expresión cron

Formato cron: minuto hora día mes día_semana comando
- * * * * * = cada minuto
- 0 * * * * = cada hora
- 0 0 * * * = cada día a medianoche
- 0 2 * * 0 = domingos a las 2am

Ejemplos:
- Listar: action="list"
- Agregar: action="add", expression="0 2 * * *", command="backup.sh"
- Validar: action="validate", expression="*/5 * * * *"
"""
    category = "devops"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description="Acción: list, add, remove, validate",
                required=True,
                enum=["list", "add", "remove", "validate"]
            ),
            "expression": ToolParameter(
                name="expression",
                type="string",
                description="Expresión cron (para add/validate)",
                required=False
            ),
            "command": ToolParameter(
                name="command",
                type="string",
                description="Comando a ejecutar (para add)",
                required=False
            ),
            "comment": ToolParameter(
                name="comment",
                type="string",
                description="Comentario identificador (para add/remove)",
                required=False
            )
        }
    
    def execute(
        self,
        action: str = None,
        expression: str = None,
        command: str = None,
        comment: str = None,
        **kwargs
    ) -> str:
        action = action or kwargs.get('action', '')
        expression = expression or kwargs.get('expression', '')
        command = command or kwargs.get('command', '')
        comment = comment or kwargs.get('comment', f'nvidia_code_{datetime.now().strftime("%Y%m%d%H%M%S")}')
        
        if not action:
            return "❌ Se requiere 'action'"
        
        if action == "list":
            return self._list_crontab()
        elif action == "add":
            if not expression or not command:
                return "❌ Se requieren 'expression' y 'command' para agregar"
            return self._add_cron(expression, command, comment)
        elif action == "remove":
            if not comment:
                return "❌ Se requiere 'comment' para identificar la tarea a eliminar"
            return self._remove_cron(comment)
        elif action == "validate":
            if not expression:
                return "❌ Se requiere 'expression' para validar"
            return self._validate_cron(expression)
        else:
            return f"❌ Acción no válida: {action}"
    
    def _list_crontab(self) -> str:
        try:
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                if "no crontab" in result.stderr.lower():
                    return "📋 **Crontab vacío** - No hay tareas programadas"
                return f"❌ Error: {result.stderr}"
            
            lines = result.stdout.strip().split('\n')
            jobs = []
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                jobs.append(line)
            
            if not jobs:
                return "📋 **Crontab vacío** - No hay tareas programadas"
            
            output = f"""📋 **Crontab Actual**

**{len(jobs)} tareas programadas:**

```cron
{chr(10).join(jobs)}
```

**Referencia rápida:**
| Campo | Valores |
|-------|---------|
| Minuto | 0-59 |
| Hora | 0-23 |
| Día del mes | 1-31 |
| Mes | 1-12 |
| Día semana | 0-7 (0 y 7 = domingo) |
"""
            return output
            
        except FileNotFoundError:
            return "❌ crontab no disponible en este sistema"
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def _add_cron(self, expression: str, command: str, comment: str) -> str:
        # Validar expresión
        validation = self._validate_cron(expression)
        if "❌" in validation:
            return validation
        
        try:
            # Obtener crontab actual
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True, text=True
            )
            
            current = result.stdout if result.returncode == 0 else ""
            
            # Agregar nueva línea
            new_line = f"# {comment}\n{expression} {command}\n"
            new_crontab = current + new_line
            
            # Escribir nuevo crontab
            process = subprocess.Popen(
                ["crontab", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=new_crontab)
            
            if process.returncode != 0:
                return f"❌ Error agregando cron: {stderr}"
            
            return f"""✅ **Tarea Cron Agregada**

| Propiedad | Valor |
|-----------|-------|
| Expresión | `{expression}` |
| Comando | `{command}` |
| Comentario | {comment} |

{self._explain_cron(expression)}

💡 Para eliminar: action="remove", comment="{comment}"
"""
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def _remove_cron(self, comment: str) -> str:
        try:
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                return "❌ No hay crontab o error accediendo"
            
            lines = result.stdout.split('\n')
            new_lines = []
            removed = False
            skip_next = False
            
            for line in lines:
                if skip_next:
                    skip_next = False
                    removed = True
                    continue
                
                if comment in line and line.strip().startswith('#'):
                    skip_next = True
                    continue
                
                new_lines.append(line)
            
            if not removed:
                return f"❌ No se encontró tarea con comentario: {comment}"
            
            # Escribir nuevo crontab
            new_crontab = '\n'.join(new_lines)
            
            process = subprocess.Popen(
                ["crontab", "-"],
                stdin=subprocess.PIPE,
                text=True
            )
            process.communicate(input=new_crontab)
            
            return f"""✅ **Tarea Eliminada**

Comentario: {comment}
"""
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def _validate_cron(self, expression: str) -> str:
        parts = expression.split()
        
        if len(parts) < 5:
            return f"❌ Expresión cron inválida. Necesita 5 campos, tiene {len(parts)}"
        
        fields = ['minuto', 'hora', 'día del mes', 'mes', 'día de semana']
        ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
        
        for i, (field, part) in enumerate(zip(fields, parts[:5])):
            if not self._validate_cron_field(part, ranges[i]):
                return f"❌ Campo '{field}' inválido: {part}"
        
        return f"""✅ **Expresión Cron Válida**

`{expression}`

{self._explain_cron(expression)}
"""
    
    def _validate_cron_field(self, field: str, valid_range: tuple) -> bool:
        min_val, max_val = valid_range
        
        # Wildcard
        if field == '*':
            return True
        
        # Step (*/5)
        if field.startswith('*/'):
            try:
                step = int(field[2:])
                return step > 0 and step <= max_val
            except:
                return False
        
        # Range (1-5)
        if '-' in field:
            try:
                start, end = map(int, field.split('-'))
                return min_val <= start <= max_val and min_val <= end <= max_val
            except:
                return False
        
        # List (1,2,3)
        if ',' in field:
            try:
                values = [int(v) for v in field.split(',')]
                return all(min_val <= v <= max_val for v in values)
            except:
                return False
        
        # Single value
        try:
            val = int(field)
            return min_val <= val <= max_val
        except:
            return False
    
    def _explain_cron(self, expression: str) -> str:
        parts = expression.split()[:5]
        if len(parts) < 5:
            return ""
        
        minute, hour, dom, month, dow = parts
        
        explanations = []
        
        # Minuto
        if minute == '*':
            explanations.append("cada minuto")
        elif minute.startswith('*/'):
            explanations.append(f"cada {minute[2:]} minutos")
        elif minute == '0':
            pass  # Se maneja con hora
        else:
            explanations.append(f"en el minuto {minute}")
        
        # Hora
        if hour == '*':
            if minute != '*':
                explanations.append("cada hora")
        elif hour.startswith('*/'):
            explanations.append(f"cada {hour[2:]} horas")
        else:
            explanations.append(f"a las {hour}:{minute.zfill(2) if minute != '*' else '00'}")
        
        # Día del mes
        if dom != '*':
            explanations.append(f"el día {dom} del mes")
        
        # Mes
        if month != '*':
            months = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                     'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
            try:
                explanations.append(f"en {months[int(month)]}")
            except:
                explanations.append(f"en mes {month}")
        
        # Día de semana
        if dow != '*':
            days = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
            try:
                explanations.append(f"los {days[int(dow)]}")
            except:
                explanations.append(f"día de semana {dow}")
        
        return "**Ejecuta:** " + ", ".join(explanations) if explanations else ""