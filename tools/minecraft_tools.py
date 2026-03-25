"""
NVIDIA CODE - Minecraft Bot Tool (Mineflayer via JSPyBridge)
Interfaz completa para que un agente de IA juegue Minecraft:
movimiento, minería, combate, crafting, percepción, inventario, supervivencia y más.
"""

import os
import sys
import time
import math
import json
import threading
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from .base import BaseTool, ToolParameter


# ─────────────────────────────────────────────────────────────────────
#  Carga perezosa de JSPyBridge + Mineflayer
# ─────────────────────────────────────────────────────────────────────

_JS_MODULES: Dict[str, Any] = {}


def _require(package: str, version: str = "latest") -> Any:
    if package in _JS_MODULES:
        return _JS_MODULES[package]
    try:
        from javascript import require
        mod = require(package, version)
        _JS_MODULES[package] = mod
        return mod
    except ImportError:
        raise RuntimeError(
            "Se requiere JSPyBridge: pip install javascript\n"
            "También necesitas Node.js 14+ instalado."
        )
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar '{package}': {e}")


def _load_colors():
    try:
        from ui.colors import Colors
        return Colors()
    except ImportError:
        class _Stub:
            def __getattr__(self, _):
                return ""
        return _Stub()


# ─────────────────────────────────────────────────────────────────────
#  Constantes
# ─────────────────────────────────────────────────────────────────────

DEFAULT_RADIUS = 16
MAX_RADIUS = 64
MAX_PATHFIND_TIMEOUT = 120
MAX_DIG_TIMEOUT = 30
MAX_EVENTS = 100
MAX_CHAT_LOG = 50

EQUIPMENT_SLOTS = {
    "hand": "hand", "main_hand": "hand",
    "off_hand": "off-hand", "offhand": "off-hand",
    "head": "head", "helmet": "head",
    "chest": "torso", "chestplate": "torso", "torso": "torso",
    "legs": "legs", "leggings": "legs",
    "feet": "feet", "boots": "feet",
}

HOSTILE_MOBS = {
    "zombie", "skeleton", "creeper", "spider", "cave_spider",
    "enderman", "witch", "slime", "magma_cube", "blaze",
    "ghast", "wither_skeleton", "phantom", "drowned",
    "pillager", "vindicator", "ravager", "hoglin", "piglin_brute",
    "warden", "breeze", "bogged", "husk", "stray",
    "evoker", "vex", "guardian", "elder_guardian", "shulker",
    "silverfish", "endermite",
}

PASSIVE_MOBS = {
    "cow", "pig", "sheep", "chicken", "horse", "donkey",
    "mule", "rabbit", "cat", "wolf", "parrot", "fox",
    "bee", "turtle", "axolotl", "goat", "frog",
    "villager", "wandering_trader", "iron_golem", "snow_golem",
    "squid", "glow_squid", "dolphin", "cod", "salmon",
    "tropical_fish", "pufferfish", "bat", "allay", "sniffer",
    "camel", "armadillo",
}

FOOD_ITEMS = {
    "cooked_beef", "cooked_porkchop", "cooked_chicken",
    "cooked_mutton", "cooked_salmon", "cooked_cod",
    "bread", "apple", "golden_apple", "enchanted_golden_apple",
    "baked_potato", "cooked_rabbit", "golden_carrot",
    "mushroom_stew", "beetroot_soup", "rabbit_stew",
    "sweet_berries", "glow_berries", "melon_slice",
    "dried_kelp", "cookie", "pumpkin_pie", "cake",
}

TOOL_TIERS = ["netherite", "diamond", "iron", "stone", "wooden", "golden"]

SMELTABLE = {
    "raw_iron": "iron_ingot", "raw_gold": "gold_ingot",
    "raw_copper": "copper_ingot",
    "cobblestone": "stone", "sand": "glass",
    "clay_ball": "brick", "netherrack": "nether_brick",
    "wet_sponge": "sponge", "cactus": "green_dye",
    "oak_log": "charcoal", "spruce_log": "charcoal",
    "birch_log": "charcoal", "dark_oak_log": "charcoal",
    "raw_beef": "cooked_beef", "raw_porkchop": "cooked_porkchop",
    "raw_chicken": "cooked_chicken", "raw_mutton": "cooked_mutton",
    "raw_salmon": "cooked_salmon", "raw_cod": "cooked_cod",
    "raw_rabbit": "cooked_rabbit", "potato": "baked_potato",
    "kelp": "dried_kelp",
}


# ─────────────────────────────────────────────────────────────────────
#  Estructuras de datos
# ─────────────────────────────────────────────────────────────────────

@dataclass
class EventEntry:
    timestamp: float
    category: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

    def __str__(self):
        age = time.time() - self.timestamp
        if age < 60:
            ago = f"{age:.0f}s"
        elif age < 3600:
            ago = f"{age / 60:.1f}m"
        else:
            ago = f"{age / 3600:.1f}h"
        return f"[{ago} ago] [{self.category}] {self.message}"


class EventBuffer:
    def __init__(self, maxlen: int = MAX_EVENTS):
        self._buffer: deque[EventEntry] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add(self, category: str, message: str, data: Dict = None):
        with self._lock:
            self._buffer.append(EventEntry(
                timestamp=time.time(), category=category,
                message=message, data=data or {},
            ))

    def get_recent(self, count: int = 10, category: str = None) -> List[EventEntry]:
        with self._lock:
            entries = list(self._buffer)
        if category:
            entries = [e for e in entries if e.category == category]
        return entries[-count:]

    def clear(self):
        with self._lock:
            self._buffer.clear()

    def __len__(self):
        return len(self._buffer)


@dataclass
class Vec3Simple:
    x: float
    y: float
    z: float

    def distance_to(self, other: 'Vec3Simple') -> float:
        return math.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        )

    def direction_to(self, other: 'Vec3Simple') -> str:
        dx = other.x - self.x
        dz = other.z - self.z
        angle = math.degrees(math.atan2(-dx, dz)) % 360
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return dirs[int((angle + 22.5) / 45) % 8]

    def __str__(self):
        return f"({self.x:.1f}, {self.y:.1f}, {self.z:.1f})"


# ─────────────────────────────────────────────────────────────────────
#  BotManager — Gestión del bot Mineflayer (Singleton)
# ─────────────────────────────────────────────────────────────────────

class BotManager:
    _instance: Optional['BotManager'] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.bot = None
        self.connected = False
        self.host = ""
        self.port = 25565
        self.username = ""

        self._mineflayer = None
        self._pathfinder = None
        self._movements = None
        self._vec3_cls = None
        self._mcdata = None

        self.events = EventBuffer()
        self.chat_log: deque = deque(maxlen=MAX_CHAT_LOG)
        self._state_lock = threading.RLock()
        self._navigating = False
        self._fighting = False
        self._current_window = None

    # ══════════════════════════════════════════════════════════════════
    #  CONEXIÓN
    # ══════════════════════════════════════════════════════════════════

    def connect(
        self, host: str = "127.0.0.1", port: int = 25565,
        username: str = "NvidiaBot", version: str = None,
        auth: str = None, password: str = None,
    ) -> str:
        if self.connected and self.bot:
            return f"⚠️ Ya conectado a {self.host}:{self.port} como **{self.username}**"

        try:
            self._mineflayer = _require("mineflayer")
            self._pathfinder = _require("mineflayer-pathfinder")
            self._vec3_cls = _require("vec3").Vec3
        except RuntimeError as e:
            return f"❌ {e}"

        bot_options = {
            "host": host, "port": int(port),
            "username": username, "hideErrors": False,
        }
        if version:
            bot_options["version"] = version
        if auth:
            bot_options["auth"] = auth
        if password:
            bot_options["password"] = password

        try:
            self.bot = self._mineflayer.createBot(bot_options)
            self.host = host
            self.port = int(port)
            self.username = username

            self.bot.loadPlugin(self._pathfinder.pathfinder)

            # Plugins opcionales
            for plugin_name in [
                "mineflayer-pvp", "mineflayer-armor-manager",
                "mineflayer-collectblock", "mineflayer-auto-eat",
            ]:
                try:
                    plugin = _require(plugin_name)
                    self.bot.loadPlugin(getattr(plugin, 'plugin', plugin))
                except Exception:
                    pass

            self._setup_events()
            self._wait_for_event("spawn", timeout=30)
            self.connected = True

            try:
                self._movements = self._pathfinder.Movements(self.bot)
                self.bot.pathfinder.setMovements(self._movements)
            except Exception:
                pass

            pos = self._get_pos()
            self.events.add("system", f"Conectado a {host}:{port}")

            return (
                f"✅ **Conectado exitosamente**\n"
                f"- Servidor: `{host}:{port}`\n"
                f"- Usuario: `{username}`\n"
                f"- Posición: {pos}\n"
                f"- Versión: `{self.bot.version}`"
            )
        except Exception as e:
            self.connected = False
            self.bot = None
            return f"❌ Error de conexión: {e}"

    def disconnect(self) -> str:
        if not self.connected or not self.bot:
            return "⚠️ No hay conexión activa."
        try:
            self.bot.quit("Bot desconectado")
        except Exception:
            pass
        self.connected = False
        self.bot = None
        self._navigating = False
        self._fighting = False
        self.events.add("system", "Desconectado")
        return "✅ Desconectado del servidor."

    def reconnect(self) -> str:
        if self.connected:
            self.disconnect()
        if not self.host:
            return "❌ No hay conexión previa."
        return self.connect(self.host, self.port, self.username)

    def _ensure_connected(self) -> Optional[str]:
        if not self.connected or not self.bot:
            return "❌ Bot no conectado. Usa `action: connect` primero."
        return None

    # ══════════════════════════════════════════════════════════════════
    #  EVENTOS
    # ══════════════════════════════════════════════════════════════════

    def _setup_events(self):
        from javascript import On
        bot = self.bot
        events = self.events
        chat_log = self.chat_log

        @On(bot, "chat")
        def on_chat(this, username, message, *args):
            if username != self.username:
                chat_log.append({
                    "sender": username, "message": message,
                    "time": time.time(),
                })
                events.add("chat", f"{username}: {message}")

        @On(bot, "whisper")
        def on_whisper(this, username, message, *args):
            chat_log.append({
                "sender": username,
                "message": f"(whisper) {message}",
                "time": time.time(),
            })
            events.add("chat", f"{username} whispers: {message}")

        @On(bot, "health")
        def on_health(this):
            events.add("status", f"Salud: {bot.health:.0f} | Comida: {bot.food:.0f}")

        @On(bot, "death")
        def on_death(this):
            events.add("combat", "¡He muerto! 💀")
            self._navigating = False
            self._fighting = False

        @On(bot, "kicked")
        def on_kicked(this, reason, *args):
            events.add("system", f"Expulsado: {reason}")
            self.connected = False

        @On(bot, "error")
        def on_error(this, err, *args):
            events.add("error", str(err))

        @On(bot, "end")
        def on_end(this, reason, *args):
            events.add("system", f"Conexión terminada: {reason}")
            self.connected = False

        @On(bot, "entityHurt")
        def on_entity_hurt(this, entity, *args):
            try:
                name = getattr(entity, 'username', None) or \
                       getattr(entity, 'displayName', '?')
                if name == self.username:
                    events.add("combat",
                               f"Recibí daño. Salud: {bot.health:.0f}")
                else:
                    events.add("combat", f"{name} recibió daño")
            except Exception:
                pass

        @On(bot, "playerJoined")
        def on_player_joined(this, player, *args):
            try:
                name = player["username"] if isinstance(player, dict) \
                    else player.username
                if name != self.username:
                    events.add("players", f"{name} se unió")
            except Exception:
                pass

        @On(bot, "playerLeft")
        def on_player_left(this, player, *args):
            try:
                name = player["username"] if isinstance(player, dict) \
                    else player.username
                events.add("players", f"{name} se fue")
            except Exception:
                pass

        @On(bot, "rain")
        def on_rain(this):
            state = "lloviendo 🌧️" if bot.isRaining else "despejado ☀️"
            events.add("weather", f"Clima: {state}")

        @On(bot, "spawn")
        def on_spawn(this):
            events.add("system", "Spawn/Respawn")

        @On(bot, "goal_reached")
        def on_goal_reached(this, *args):
            self._navigating = False
            events.add("movement", "Destino alcanzado ✅")

        @On(bot, "path_update")
        def on_path_update(this, results, *args):
            try:
                status = getattr(results, 'status', str(results))
                if status == "noPath":
                    self._navigating = False
                    events.add("movement", "No se encontró ruta ❌")
            except Exception:
                pass

        @On(bot, "entitySpawn")
        def on_entity_spawn(this, entity, *args):
            try:
                name = (getattr(entity, 'name', '') or '').lower()
                if getattr(entity, 'type', '') == "mob" and name in HOSTILE_MOBS:
                    p = entity.position
                    events.add("combat",
                               f"⚠️ {name} hostil cerca "
                               f"({p.x:.0f}, {p.y:.0f}, {p.z:.0f})")
            except Exception:
                pass

        @On(bot, "playerCollect")
        def on_collect(this, collector, collected, *args):
            try:
                if getattr(collector, 'username', '') == self.username:
                    events.add("items", "Recogí un objeto")
            except Exception:
                pass

        @On(bot, "windowOpen")
        def on_window_open(this, window, *args):
            self._current_window = window
            events.add("interact", f"Ventana abierta: {getattr(window, 'title', '?')}")

        @On(bot, "windowClose")
        def on_window_close(this, *args):
            self._current_window = None
            events.add("interact", "Ventana cerrada")

    def _wait_for_event(self, event_name: str, timeout: float = 10) -> bool:
        from javascript import Once
        done = threading.Event()

        @Once(self.bot, event_name)
        def handler(this, *args):
            done.set()

        return done.wait(timeout=timeout)

    # ══════════════════════════════════════════════════════════════════
    #  HELPERS INTERNOS
    # ══════════════════════════════════════════════════════════════════

    def _get_pos(self) -> Vec3Simple:
        try:
            p = self.bot.entity.position
            return Vec3Simple(float(p.x), float(p.y), float(p.z))
        except Exception:
            return Vec3Simple(0, 0, 0)

    def _vec3(self, x, y, z):
        return self._vec3_cls(float(x), float(y), float(z))

    def _entity_display(self, entity) -> str:
        for attr in ('username', 'displayName', 'name'):
            val = getattr(entity, attr, None)
            if val:
                return str(val)
        return "?"

    def _entity_type(self, entity) -> str:
        return getattr(entity, 'type', 'unknown')

    def _entity_health(self, entity) -> str:
        hp = getattr(entity, 'health', None)
        return f"{float(hp):.0f}" if hp is not None else "?"

    def _is_hostile(self, entity) -> bool:
        name = (getattr(entity, 'name', '') or '').lower()
        return name in HOSTILE_MOBS

    def _find_entity_by(
        self, name: str = None, entity_type: str = None,
        max_dist: float = 32,
    ) -> Optional[Any]:
        try:
            bot_pos = self.bot.entity.position
            best, best_dist = None, max_dist
            for eid in self.bot.entities:
                e = self.bot.entities[eid]
                if e == self.bot.entity:
                    continue
                etype = self._entity_type(e)
                ename = self._entity_display(e).lower()
                match = False
                if name and name.lower() in ename:
                    match = True
                if entity_type and etype == entity_type:
                    match = True
                if not name and not entity_type:
                    match = True
                if match:
                    try:
                        dist = float(e.position.distanceTo(bot_pos))
                        if dist < best_dist:
                            best, best_dist = e, dist
                    except Exception:
                        pass
            return best
        except Exception:
            return None

    def _find_item_in_inventory(self, item_name: str) -> Optional[Any]:
        try:
            name_lower = item_name.lower().replace(' ', '_')
            for item in self.bot.inventory.items():
                iname = (getattr(item, 'name', '') or '').lower()
                display = (getattr(item, 'displayName', '') or '').lower()
                if name_lower in iname or name_lower in display:
                    return item
            return None
        except Exception:
            return None

    def _find_best_food(self) -> Optional[Any]:
        try:
            best, best_priority = None, -1
            food_priority = list(FOOD_ITEMS)
            for item in self.bot.inventory.items():
                iname = (getattr(item, 'name', '') or '').lower()
                if iname in FOOD_ITEMS:
                    try:
                        prio = food_priority.index(iname)
                    except ValueError:
                        prio = 999
                    if best is None or prio < best_priority:
                        best, best_priority = item, prio
            return best
        except Exception:
            return None

    def _find_best_tool(self, tool_type: str) -> Optional[Any]:
        """Encuentra la mejor herramienta de un tipo (pickaxe, axe, etc.)."""
        try:
            best, best_tier = None, len(TOOL_TIERS)
            for item in self.bot.inventory.items():
                iname = (getattr(item, 'name', '') or '').lower()
                if tool_type in iname:
                    for i, tier in enumerate(TOOL_TIERS):
                        if tier in iname and i < best_tier:
                            best, best_tier = item, i
                            break
            return best
        except Exception:
            return None

    def _wait_goal(self, timeout: float = 30) -> bool:
        """Espera hasta que se alcance el goal o timeout."""
        start = time.time()
        while self._navigating and (time.time() - start) < timeout:
            time.sleep(0.3)
        return not self._navigating

    @staticmethod
    def _make_bar(value: float, max_val: float, length: int = 10) -> str:
        filled = int((value / max(max_val, 1)) * length)
        return "█" * filled + "░" * (length - filled)

    # ══════════════════════════════════════════════════════════════════
    #  PERCEPCIÓN — El bot ve y siente el mundo
    # ══════════════════════════════════════════════════════════════════

    def look_around(self, radius: int = DEFAULT_RADIUS) -> str:
        err = self._ensure_connected()
        if err:
            return err
        radius = min(int(radius), MAX_RADIUS)
        sections = [
            self._format_bot_status(),
            self._format_nearby_entities(radius),
            self._format_notable_blocks(radius),
            self._format_inventory_summary(),
            self._format_equipment(),
            self._format_recent_chat(5),
            self._format_recent_events(5),
        ]
        return "\n\n".join(s for s in sections if s)

    def get_status(self) -> str:
        err = self._ensure_connected()
        if err:
            return err
        return self._format_bot_status()

    def scan_blocks(
        self, block_name: str = None,
        radius: int = DEFAULT_RADIUS, count: int = 20,
    ) -> str:
        err = self._ensure_connected()
        if err:
            return err
        radius = min(int(radius), MAX_RADIUS)
        try:
            if block_name:
                return self._scan_specific_block(block_name, radius, count)
            return self._format_notable_blocks(radius, max_types=15)
        except Exception as e:
            return f"❌ Error escaneando: {e}"

    def get_entities(
        self, radius: float = DEFAULT_RADIUS,
        entity_type: str = None,
    ) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            bot_pos = self.bot.entity.position
            found = []
            for eid in self.bot.entities:
                e = self.bot.entities[eid]
                if e == self.bot.entity:
                    continue
                etype = self._entity_type(e)
                if entity_type and etype != entity_type:
                    continue
                try:
                    dist = float(e.position.distanceTo(bot_pos))
                except Exception:
                    continue
                if dist > radius:
                    continue
                name = self._entity_display(e)
                hp = self._entity_health(e)
                my_pos = self._get_pos()
                epos = Vec3Simple(
                    float(e.position.x),
                    float(e.position.y),
                    float(e.position.z),
                )
                direction = my_pos.direction_to(epos)
                hostile = "⚠️" if self._is_hostile(e) else ""
                found.append((name, etype, dist, direction, hp, hostile))

            if not found:
                return f"👀 No hay entidades en {radius} bloques."
            found.sort(key=lambda x: x[2])
            lines = [f"## 👀 Entidades ({len(found)}) radio={radius}\n"]
            lines.append("| Entidad | Tipo | Dist | Dir | HP | |")
            lines.append("|---------|------|------|-----|----|-|")
            for row in found[:30]:
                lines.append(
                    f"| {row[0]} | {row[1]} | {row[2]:.1f} "
                    f"| {row[3]} | {row[4]} | {row[5]} |"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {e}"

    def get_players(self) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            bot_pos = self.bot.entity.position
            lines = ["## 👥 Jugadores\n"]
            lines.append("| Jugador | Ping | Dist |")
            lines.append("|---------|------|------|")
            for name in self.bot.players:
                p = self.bot.players[name]
                ping = getattr(p, 'ping', '?')
                entity = getattr(p, 'entity', None)
                dist = "?"
                if entity:
                    try:
                        dist = f"{float(entity.position.distanceTo(bot_pos)):.1f}"
                    except Exception:
                        pass
                else:
                    dist = "fuera de rango"
                me = " ← yo" if name == self.username else ""
                lines.append(f"| {name}{me} | {ping}ms | {dist} |")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {e}"

    def get_inventory(self) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            items = list(self.bot.inventory.items())
            if not items:
                return "🎒 Inventario vacío."
            lines = ["## 🎒 Inventario\n"]
            lines.append("| Slot | Item | Cant | Durabilidad |")
            lines.append("|------|------|------|-------------|")
            for item in items:
                slot = getattr(item, 'slot', '?')
                name = getattr(item, 'displayName',
                               getattr(item, 'name', '?'))
                count = getattr(item, 'count', 1)
                dur = ""
                try:
                    max_d = getattr(item, 'maxDurability', None)
                    if max_d:
                        cur_d = int(max_d) - int(
                            getattr(item, 'durabilityUsed', 0))
                        dur = f"{cur_d}/{max_d}"
                except Exception:
                    pass
                lines.append(f"| {slot} | {name} | {count} | {dur} |")
            try:
                free = 36 - len(items)
                lines.append(f"\n📦 Espacios libres: **{free}**/36")
            except Exception:
                pass
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {e}"

    def get_block_at(self, x: float, y: float, z: float) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            block = self.bot.blockAt(self._vec3(x, y, z))
            if not block:
                return f"❌ No hay bloque en ({x}, {y}, {z})"
            name = getattr(block, 'displayName',
                           getattr(block, 'name', '?'))
            hardness = getattr(block, 'hardness', '?')
            diggable = getattr(block, 'diggable', False)
            transparent = getattr(block, 'transparent', False)
            biome = ""
            try:
                biome = f"\n- **Bioma:** {block.biome.name}"
            except Exception:
                pass
            tool_hint = ""
            try:
                if diggable:
                    t = self.bot.pathfinder.bestHarvestTool(block)
                    tn = getattr(t, 'displayName', 'mano') if t else "mano"
                    tool_hint = f"\n- **Herramienta:** {tn}"
            except Exception:
                pass
            return (
                f"## 🧱 Bloque ({x:.0f}, {y:.0f}, {z:.0f})\n"
                f"- **Nombre:** {name}\n"
                f"- **Dureza:** {hardness}\n"
                f"- **Minable:** {'✅' if diggable else '❌'}\n"
                f"- **Transparente:** {'✅' if transparent else '❌'}"
                f"{biome}{tool_hint}"
            )
        except Exception as e:
            return f"❌ Error: {e}"

    def find_block(
        self, block_name: str,
        radius: int = DEFAULT_RADIUS, count: int = 5,
    ) -> str:
        err = self._ensure_connected()
        if err:
            return err
        return self._scan_specific_block(block_name, radius, count)

    def find_entity(
        self, name: str = None,
        entity_type: str = None, radius: int = DEFAULT_RADIUS,
    ) -> str:
        err = self._ensure_connected()
        if err:
            return err
        entity = self._find_entity_by(name, entity_type, float(radius))
        if not entity:
            search = name or entity_type or "entidad"
            return f"❌ No encontré **{search}** en {radius} bloques."
        ename = self._entity_display(entity)
        ep = entity.position
        dist = float(ep.distanceTo(self.bot.entity.position))
        hp = self._entity_health(entity)
        my_pos = self._get_pos()
        tp = Vec3Simple(float(ep.x), float(ep.y), float(ep.z))
        return (
            f"🔍 **{ename}**\n"
            f"- Pos: ({ep.x:.1f}, {ep.y:.1f}, {ep.z:.1f})\n"
            f"- Dist: {dist:.1f} ({my_pos.direction_to(tp)})\n"
            f"- HP: {hp}\n"
            f"- Hostil: {'⚠️ Sí' if self._is_hostile(entity) else '✅ No'}"
        )

    def get_weather(self) -> str:
        err = self._ensure_connected()
        if err:
            return err
        thundering = getattr(self.bot, 'thunderState', 0) > 0
        raining = getattr(self.bot, 'isRaining', False)
        if thundering:
            return "🌩️ **Tormenta eléctrica**"
        if raining:
            return "🌧️ **Lluvia**"
        return "☀️ **Despejado**"

    def get_time(self) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            t = int(self.bot.time.timeOfDay)
            day = int(self.bot.time.day)
            phases = [
                (6000, "🌅 Mañana"), (12000, "☀️ Tarde"),
                (13000, "🌅 Atardecer"), (18000, "🌙 Noche"),
                (24000, "🌑 Noche profunda"),
            ]
            phase = "🌍 ?"
            for limit, label in phases:
                if t < limit:
                    phase = label
                    break
            h = (t // 1000 + 6) % 24
            m = (t % 1000) * 60 // 1000
            return (
                f"🕐 **{phase}** {h:02d}:{m:02d} "
                f"(día #{day}, ticks={t}, "
                f"dormir={'✅' if t >= 12542 else '❌'})"
            )
        except Exception as e:
            return f"❌ Error: {e}"

    def get_events(
        self, count: int = 15, category: str = None,
    ) -> str:
        entries = self.events.get_recent(count, category)
        if not entries:
            return "📋 Sin eventos."
        lines = [f"## 📋 Eventos ({len(entries)})\n"]
        for entry in reversed(entries):
            lines.append(f"- {entry}")
        return "\n".join(lines)

    def get_recipe(self, item_name: str) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            name_lower = item_name.lower().replace(' ', '_')
            items_by_name = self.bot.registry.itemsByName
            if name_lower not in items_by_name:
                return f"❌ Item no encontrado: `{item_name}`"
            item_id = int(items_by_name[name_lower].id)
            recipes = list(self.bot.recipesFor(item_id))
            if not recipes:
                return f"❌ Sin receta para **{item_name}**."
            lines = [f"## 📖 Recetas: **{item_name}**\n"]
            for i, recipe in enumerate(recipes):
                lines.append(f"### Receta {i + 1}")
                try:
                    for delta in recipe.delta:
                        cnt = getattr(delta, 'count', 1)
                        rid = getattr(delta, 'id', '?')
                        try:
                            rname = self.bot.registry.items[
                                int(rid)].displayName
                        except Exception:
                            rname = f"ID:{rid}"
                        if cnt < 0:
                            lines.append(
                                f"  - Necesita: **{abs(cnt)}x {rname}**")
                        else:
                            lines.append(
                                f"  - Produce: **{cnt}x {rname}**")
                except Exception:
                    lines.append("  - (detalles no disponibles)")
                try:
                    if getattr(recipe, 'requiresTable', False):
                        lines.append(
                            "  - ⚠️ Requiere **mesa de crafteo**")
                except Exception:
                    pass
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {e}"

    # ── Formateadores internos ───────────────────────────────────────

    def _format_bot_status(self) -> str:
        try:
            pos = self._get_pos()
            hp = float(self.bot.health)
            food = float(self.bot.food)
            xp_lvl = int(self.bot.experience.level)
            xp_pct = float(self.bot.experience.progress) * 100
            hp_bar = self._make_bar(hp, 20)
            food_bar = self._make_bar(food, 20)
            biome = "?"
            try:
                biome = self.bot.blockAt(
                    self.bot.entity.position).biome.name
            except Exception:
                pass
            gm = "?"
            try:
                gm = {
                    0: "Survival", 1: "Creative",
                    2: "Adventure", 3: "Spectator",
                }.get(int(self.bot.game.gameMode), "?")
            except Exception:
                pass
            dim = "?"
            try:
                dim = str(self.bot.game.dimension)
            except Exception:
                pass
            oxygen = ""
            try:
                o2 = float(self.bot.oxygenLevel)
                if o2 < 20:
                    oxygen = (
                        f"\n- **Oxígeno:** "
                        f"{self._make_bar(o2, 20)} {o2:.0f}/20"
                    )
            except Exception:
                pass
            return (
                f"## 📍 Estado\n"
                f"- **Pos:** {pos} | **Bioma:** {biome}\n"
                f"- **Dim:** {dim} | **Modo:** {gm}\n"
                f"- **HP:** {hp_bar} {hp:.0f}/20\n"
                f"- **Comida:** {food_bar} {food:.0f}/20\n"
                f"- **XP:** Lvl {xp_lvl} ({xp_pct:.0f}%)"
                f"{oxygen}\n"
                f"- **Nav:** {'🚶 Sí' if self._navigating else 'No'} "
                f"| **Pelea:** {'⚔️ Sí' if self._fighting else 'No'}"
            )
        except Exception as e:
            return f"❌ Error estado: {e}"

    def _format_nearby_entities(self, radius: int) -> str:
        try:
            bot_pos = self.bot.entity.position
            groups: Dict[str, List] = {
                "hostile": [], "player": [],
                "passive": [], "item": [],
            }
            for eid in self.bot.entities:
                e = self.bot.entities[eid]
                if e == self.bot.entity:
                    continue
                try:
                    dist = float(e.position.distanceTo(bot_pos))
                except Exception:
                    continue
                if dist > radius:
                    continue
                name = self._entity_display(e)
                etype = self._entity_type(e)
                if etype == "player":
                    groups["player"].append((name, dist))
                elif etype == "mob":
                    key = "hostile" if self._is_hostile(e) else "passive"
                    groups[key].append((name, dist))
                elif etype == "object":
                    groups["item"].append((name, dist))
            lines = [f"## 👀 Entidades (radio={radius})"]
            labels = [
                ("hostile", "Hostiles", "⚠️"),
                ("player", "Jugadores", "👤"),
                ("passive", "Pasivos", "🐄"),
                ("item", "Objetos", "📦"),
            ]
            total = 0
            for key, label, emoji in labels:
                elist = groups[key]
                total += len(elist)
                if elist:
                    elist.sort(key=lambda x: x[1])
                    items = ", ".join(
                        f"{n} ({d:.0f}m)" for n, d in elist[:8])
                    extra = (
                        f" +{len(elist) - 8} más"
                        if len(elist) > 8 else ""
                    )
                    lines.append(
                        f"- {emoji} **{label}:** {items}{extra}")
            if total == 0:
                lines.append("- _Ninguna_")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {e}"

    def _format_notable_blocks(
        self, radius: int, max_types: int = 10,
    ) -> str:
        try:
            notable = [
                "diamond_ore", "deepslate_diamond_ore",
                "iron_ore", "deepslate_iron_ore",
                "gold_ore", "deepslate_gold_ore",
                "coal_ore", "deepslate_coal_ore",
                "copper_ore", "deepslate_copper_ore",
                "lapis_ore", "deepslate_lapis_ore",
                "redstone_ore", "deepslate_redstone_ore",
                "emerald_ore", "deepslate_emerald_ore",
                "ancient_debris",
                "crafting_table", "furnace", "chest",
                "ender_chest", "enchanting_table", "anvil",
                "brewing_stand", "bed", "spawner",
                "water", "lava",
                "oak_log", "spruce_log", "birch_log",
            ]
            lines = [f"## 🧱 Bloques notables (radio={radius})\n"]
            found = 0
            for bn in notable:
                try:
                    bd = self.bot.registry.blocksByName.get(bn)
                    if not bd:
                        continue
                    positions = list(self.bot.findBlocks({
                        "matching": int(bd.id),
                        "maxDistance": radius,
                        "count": 10,
                    }) or [])
                    if positions:
                        found += 1
                        if found > max_types:
                            break
                        nearest = positions[0]
                        display = bn.replace('_', ' ').title()
                        lines.append(
                            f"- **{display}** ×{len(positions)}"
                            f" — ({nearest.x:.0f}, {nearest.y:.0f},"
                            f" {nearest.z:.0f})"
                        )
                except Exception:
                    continue
            if found == 0:
                lines.append("- _Ninguno_")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {e}"

    def _scan_specific_block(
        self, block_name: str, radius: int, count: int,
    ) -> str:
        try:
            name_lower = block_name.lower().replace(' ', '_')
            bd = self.bot.registry.blocksByName.get(name_lower)
            if not bd:
                return f"❌ Bloque desconocido: `{block_name}`"
            positions = list(self.bot.findBlocks({
                "matching": int(bd.id),
                "maxDistance": radius,
                "count": int(count),
            }) or [])
            if not positions:
                return f"🔍 No encontré **{block_name}** en {radius}."
            display = block_name.replace('_', ' ').title()
            lines = [f"## 🔍 {display}: {len(positions)}\n"]
            bp = self.bot.entity.position
            for p in positions:
                try:
                    d = float(p.distanceTo(bp))
                except Exception:
                    d = 0
                lines.append(
                    f"- ({p.x:.0f}, {p.y:.0f}, {p.z:.0f}) — {d:.1f}m")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {e}"

    def _format_inventory_summary(self) -> str:
        try:
            items = list(self.bot.inventory.items())
            if not items:
                return "## 🎒 Inventario\n- _Vacío_"
            groups: Dict[str, int] = {}
            for item in items:
                name = getattr(
                    item, 'displayName',
                    getattr(item, 'name', '?'))
                cnt = int(getattr(item, 'count', 1))
                groups[name] = groups.get(name, 0) + cnt
            sorted_items = sorted(groups.items(), key=lambda x: -x[1])
            lines = [f"## 🎒 Inventario ({len(items)} stacks)\n"]
            for name, cnt in sorted_items[:15]:
                lines.append(f"- {name} ×{cnt}")
            if len(sorted_items) > 15:
                lines.append(f"- _+{len(sorted_items) - 15} más_")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {e}"

    def _format_equipment(self) -> str:
        try:
            lines = ["## 🛡️ Equipo\n"]
            held = self.bot.heldItem
            lines.append(
                f"- **Mano:** "
                f"{getattr(held, 'displayName', 'Nada') if held else 'Nada'}"
            )
            armor_slots = [
                ("Cabeza", 5), ("Pecho", 6),
                ("Piernas", 7), ("Pies", 8),
            ]
            for label, slot_num in armor_slots:
                try:
                    slot = self.bot.inventory.slots[slot_num]
                    name = getattr(
                        slot, 'displayName', 'Nada'
                    ) if slot else "Nada"
                except Exception:
                    name = "Nada"
                lines.append(f"- **{label}:** {name}")
            try:
                offhand = self.bot.inventory.slots[45]
                oh = getattr(
                    offhand, 'displayName', 'Nada'
                ) if offhand else "Nada"
                lines.append(f"- **Off-hand:** {oh}")
            except Exception:
                pass
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {e}"

    def _format_recent_chat(self, count: int) -> str:
        msgs = list(self.chat_log)[-count:]
        if not msgs:
            return "## 💬 Chat\n- _Sin mensajes_"
        lines = ["## 💬 Chat\n"]
        for m in msgs:
            lines.append(f"- **{m['sender']}:** {m['message']}")
        return "\n".join(lines)

    def _format_recent_events(self, count: int) -> str:
        entries = self.events.get_recent(count)
        if not entries:
            return "## 📋 Eventos\n- _Sin eventos_"
        lines = ["## 📋 Eventos\n"]
        for e in reversed(entries):
            lines.append(f"- {e}")
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════
    #  MOVIMIENTO
    # ══════════════════════════════════════════════════════════════════

    def goto(
        self, x: float, y: float, z: float, sprint: bool = True,
    ) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            goal = self._pathfinder.goals.GoalNear(
                float(x), float(y), float(z), 1)
            self.bot.pathfinder.setGoal(goal)
            self._navigating = True
            if sprint:
                self.bot.setControlState("sprint", True)
            pos = self._get_pos()
            target = Vec3Simple(float(x), float(y), float(z))
            dist = pos.distance_to(target)
            self.events.add(
                "movement",
                f"Navegando a ({x:.0f}, {y:.0f}, {z:.0f})",
            )
            return (
                f"🚶 **Navegando** a ({x:.0f}, {y:.0f}, {z:.0f})\n"
                f"- Distancia: {dist:.1f}\n"
                f"- Sprint: {'✅' if sprint else '❌'}"
            )
        except Exception as e:
            self._navigating = False
            return f"❌ Error nav: {e}"

    def follow(self, target: str, distance: float = 3) -> str:
        err = self._ensure_connected()
        if err:
            return err
        entity = self._find_entity_by(name=target, entity_type="player")
        if not entity:
            return f"❌ No encontré a **{target}**."
        try:
            goal = self._pathfinder.goals.GoalFollow(
                entity, float(distance))
            self.bot.pathfinder.setGoal(goal, True)
            self._navigating = True
            self.events.add("movement", f"Siguiendo a {target}")
            return f"🚶 **Siguiendo** a **{target}** (dist={distance})"
        except Exception as e:
            return f"❌ Error: {e}"

    def come(self, player_name: str) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            player = self.bot.players.get(player_name)
            if not player or not player.entity:
                return f"❌ No puedo ver a **{player_name}**."
            p = player.entity.position
            return self.goto(float(p.x), float(p.y), float(p.z))
        except Exception as e:
            return f"❌ Error: {e}"

    def flee(self, target: str = None, distance: float = 16) -> str:
        err = self._ensure_connected()
        if err:
            return err
        entity = (
            self._find_entity_by(name=target) if target
            else self._find_entity_by(entity_type="mob")
        )
        if not entity:
            return "❌ No hay de qué huir."
        try:
            inner = self._pathfinder.goals.GoalFollow(
                entity, float(distance))
            goal = self._pathfinder.goals.GoalInvert(inner)
            self.bot.pathfinder.setGoal(goal, True)
            self._navigating = True
            name = self._entity_display(entity)
            self.events.add("movement", f"Huyendo de {name}")
            return f"🏃 **Huyendo** de **{name}**"
        except Exception as e:
            return f"❌ Error: {e}"

    def jump(self) -> str:
        err = self._ensure_connected()
        if err:
            return err
        self.bot.setControlState("jump", True)
        time.sleep(0.25)
        self.bot.setControlState("jump", False)
        return "⬆️ Salté."

    def set_sprint(self, enabled: bool = True) -> str:
        err = self._ensure_connected()
        if err:
            return err
        self.bot.setControlState("sprint", bool(enabled))
        return f"🏃 Sprint {'ON' if enabled else 'OFF'}"

    def set_sneak(self, enabled: bool = True) -> str:
        err = self._ensure_connected()
        if err:
            return err
        self.bot.setControlState("sneak", bool(enabled))
        return f"🥷 Sneak {'ON' if enabled else 'OFF'}"

    def stop(self) -> str:
        err = self._ensure_connected()
        if err:
            return err
        self.bot.pathfinder.setGoal(None)
        self.bot.clearControlStates()
        self._navigating = False
        self._fighting = False
        return "🛑 Detenido."

    def look_at(self, x: float, y: float, z: float) -> str:
        err = self._ensure_connected()
        if err:
            return err
        self.bot.lookAt(self._vec3(x, y, z))
        return f"👁️ Mirando a ({x:.0f}, {y:.0f}, {z:.0f})"

    def look_at_entity(self, target: str) -> str:
        err = self._ensure_connected()
        if err:
            return err
        entity = self._find_entity_by(name=target)
        if not entity:
            return f"❌ No encontré a **{target}**."
        h = float(getattr(entity, 'height', 1.6))
        self.bot.lookAt(entity.position.offset(0, h, 0))
        return f"👁️ Mirando a **{self._entity_display(entity)}**"

    # ══════════════════════════════════════════════════════════════════
    #  BLOQUES — Minar, colocar, interactuar
    # ══════════════════════════════════════════════════════════════════

    def dig(self, x: float, y: float, z: float) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            block = self.bot.blockAt(self._vec3(x, y, z))
            if not block or not getattr(block, 'diggable', False):
                name = getattr(block, 'displayName', 'aire') \
                    if block else 'aire'
                return f"❌ No minable: **{name}**"
            name = getattr(block, 'displayName', '?')
            try:
                tool = self.bot.pathfinder.bestHarvestTool(block)
                if tool:
                    self.bot.equip(tool, "hand")
            except Exception:
                pass
            self.bot.dig(block)
            self.events.add(
                "blocks",
                f"Miné {name} ({x:.0f}, {y:.0f}, {z:.0f})",
            )
            return f"⛏️ Miné **{name}** ({x:.0f}, {y:.0f}, {z:.0f})"
        except Exception as e:
            return f"❌ Error minando: {e}"

    def place(
        self, x: float, y: float, z: float,
        item_name: str = None, face: str = "top",
    ) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            if item_name:
                item = self._find_item_in_inventory(item_name)
                if not item:
                    return f"❌ No tengo **{item_name}**."
                self.bot.equip(item, "hand")
            ref = self.bot.blockAt(self._vec3(x, y, z))
            if not ref:
                return f"❌ Sin bloque de referencia."
            faces = {
                "top": (0, 1, 0), "bottom": (0, -1, 0),
                "north": (0, 0, -1), "south": (0, 0, 1),
                "east": (1, 0, 0), "west": (-1, 0, 0),
            }
            fx, fy, fz = faces.get(face.lower(), (0, 1, 0))
            self.bot.placeBlock(ref, self._vec3(fx, fy, fz))
            held = self.bot.heldItem
            hn = getattr(held, 'displayName', '?') if held else '?'
            self.events.add("blocks", f"Coloqué {hn}")
            return f"🧱 Coloqué **{hn}** ({x:.0f},{y:.0f},{z:.0f}) cara={face}"
        except Exception as e:
            return f"❌ Error colocando: {e}"

    def collect_block(
        self, block_name: str, count: int = 1,
        radius: int = DEFAULT_RADIUS,
    ) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            name_lower = block_name.lower().replace(' ', '_')
            bd = self.bot.registry.blocksByName.get(name_lower)
            if not bd:
                return f"❌ Bloque desconocido: `{block_name}`"
            positions = list(self.bot.findBlocks({
                "matching": int(bd.id),
                "maxDistance": radius,
                "count": int(count),
            }) or [])
            if not positions:
                return f"❌ No encontré **{block_name}**."
            collected = 0
            display = block_name.replace('_', ' ').title()
            for pos in positions[:count]:
                try:
                    block = self.bot.blockAt(pos)
                    if not block or not getattr(block, 'diggable', False):
                        continue
                    try:
                        tool = self.bot.pathfinder.bestHarvestTool(block)
                        if tool:
                            self.bot.equip(tool, "hand")
                    except Exception:
                        pass
                    goal = self._pathfinder.goals.GoalNear(
                        float(pos.x), float(pos.y), float(pos.z), 3)
                    self.bot.pathfinder.setGoal(goal)
                    self._navigating = True
                    for _ in range(60):
                        try:
                            if float(pos.distanceTo(
                                    self.bot.entity.position)) < 4:
                                break
                        except Exception:
                            pass
                        time.sleep(0.25)
                    self.bot.dig(block)
                    collected += 1
                    time.sleep(0.3)
                except Exception:
                    continue
            self.events.add("blocks", f"Recolecté {collected}x {display}")
            return (
                f"⛏️ Recolecté **{collected}x {display}** "
                f"(de {len(positions)} encontrados)"
            )
        except Exception as e:
            return f"❌ Error: {e}"

    def activate_block(self, x: float, y: float, z: float) -> str:
        """Activa/interactúa con un bloque (cofre, mesa, puerta, etc.)."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            block = self.bot.blockAt(self._vec3(x, y, z))
            if not block:
                return f"❌ Sin bloque en ({x:.0f}, {y:.0f}, {z:.0f})"
            name = getattr(block, 'displayName',
                           getattr(block, 'name', '?'))
            self.bot.activateBlock(block)
            self.events.add("interact", f"Activé {name}")
            return f"🔧 Activé **{name}** en ({x:.0f}, {y:.0f}, {z:.0f})"
        except Exception as e:
            return f"❌ Error: {e}"

    def close_window(self) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            if self._current_window:
                self.bot.closeWindow(self._current_window)
                self._current_window = None
                return "✅ Ventana cerrada."
            return "⚠️ No hay ventana abierta."
        except Exception as e:
            return f"❌ Error: {e}"

    def use_chest(
        self, x: float, y: float, z: float,
        action: str = "list",
        item_name: str = None, count: int = 1,
    ) -> str:
        """Interactúa con un cofre: list, deposit, withdraw."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            block = self.bot.blockAt(self._vec3(x, y, z))
            if not block:
                return "❌ Sin bloque."
            chest = self.bot.openChest(block)
            time.sleep(0.5)  # Esperar apertura

            if action == "list":
                items = list(chest.items())
                if not items:
                    chest.close()
                    return "📦 Cofre vacío."
                lines = ["## 📦 Contenido del cofre\n"]
                for item in items:
                    name = getattr(item, 'displayName',
                                   getattr(item, 'name', '?'))
                    cnt = getattr(item, 'count', 1)
                    lines.append(f"- {name} ×{cnt}")
                chest.close()
                return "\n".join(lines)

            elif action == "deposit" and item_name:
                item = self._find_item_in_inventory(item_name)
                if not item:
                    chest.close()
                    return f"❌ No tengo **{item_name}**."
                chest.deposit(
                    int(getattr(item, 'type', item)),
                    None, min(int(count), int(getattr(item, 'count', 1))),
                )
                chest.close()
                return f"📥 Deposité **{item_name}** ×{count}"

            elif action == "withdraw" and item_name:
                name_lower = item_name.lower().replace(' ', '_')
                target = None
                for item in chest.items():
                    iname = (getattr(item, 'name', '') or '').lower()
                    if name_lower in iname:
                        target = item
                        break
                if not target:
                    chest.close()
                    return f"❌ **{item_name}** no está en el cofre."
                chest.withdraw(
                    int(getattr(target, 'type', target)),
                    None, min(int(count),
                              int(getattr(target, 'count', 1))),
                )
                chest.close()
                return f"📤 Retiré **{item_name}** ×{count}"

            else:
                chest.close()
                return "⚠️ Acción no válida. Usa: list, deposit, withdraw"

        except Exception as e:
            return f"❌ Error cofre: {e}"

    # ══════════════════════════════════════════════════════════════════
    #  COMBATE
    # ══════════════════════════════════════════════════════════════════

    def attack(self, target: str = None) -> str:
        err = self._ensure_connected()
        if err:
            return err
        if target:
            entity = self._find_entity_by(name=target)
        else:
            entity = self._find_entity_by(entity_type="mob")
        if not entity:
            return f"❌ No encontré a **{target or 'mob cercano'}**."
        try:
            name = self._entity_display(entity)
            # Equipar la mejor arma
            best_weapon = None
            for tier in TOOL_TIERS:
                for wtype in ["sword", "axe"]:
                    w = self._find_item_in_inventory(f"{tier}_{wtype}")
                    if w:
                        best_weapon = w
                        break
                if best_weapon:
                    break
            if best_weapon:
                self.bot.equip(best_weapon, "hand")
            self.bot.attack(entity)
            self._fighting = True
            self.events.add("combat", f"Atacando a {name}")
            return f"⚔️ Atacando a **{name}**"
        except Exception as e:
            return f"❌ Error atacando: {e}"

    def attack_continuous(
        self, target: str = None, max_hits: int = 20,
    ) -> str:
        """Ataca repetidamente hasta matar o alcanzar max_hits."""
        err = self._ensure_connected()
        if err:
            return err
        if target:
            entity = self._find_entity_by(name=target)
        else:
            entity = self._find_entity_by(entity_type="mob")
        if not entity:
            return f"❌ No encontré a **{target or 'mob'}**."
        try:
            name = self._entity_display(entity)
            # Equipar arma
            for tier in TOOL_TIERS:
                for wtype in ["sword", "axe"]:
                    w = self._find_item_in_inventory(f"{tier}_{wtype}")
                    if w:
                        self.bot.equip(w, "hand")
                        break
                else:
                    continue
                break

            self._fighting = True
            hits = 0
            self.events.add("combat", f"Luchando con {name}")

            for _ in range(max_hits):
                if not self._fighting:
                    break
                try:
                    hp = getattr(entity, 'health', None)
                    if hp is not None and float(hp) <= 0:
                        break
                    if not getattr(entity, 'isValid', True):
                        break
                except Exception:
                    break

                try:
                    dist = float(entity.position.distanceTo(
                        self.bot.entity.position))
                    if dist > 5:
                        # Acercarse
                        goal = self._pathfinder.goals.GoalNear(
                            float(entity.position.x),
                            float(entity.position.y),
                            float(entity.position.z), 2,
                        )
                        self.bot.pathfinder.setGoal(goal)
                        time.sleep(0.5)
                except Exception:
                    pass

                try:
                    self.bot.lookAt(entity.position.offset(0, 1, 0))
                    self.bot.attack(entity)
                    hits += 1
                except Exception:
                    break
                time.sleep(0.6)  # Cooldown de ataque

            self._fighting = False
            self.events.add("combat", f"Terminé pelea con {name} ({hits} golpes)")
            return f"⚔️ Pelea con **{name}**: {hits} golpes"
        except Exception as e:
            self._fighting = False
            return f"❌ Error: {e}"

    def shoot(self, target: str = None) -> str:
        """Usa arco/ballesta para atacar a distancia."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            bow = (
                self._find_item_in_inventory("bow")
                or self._find_item_in_inventory("crossbow")
            )
            if not bow:
                return "❌ No tengo arco/ballesta."
            self.bot.equip(bow, "hand")

            if target:
                entity = self._find_entity_by(name=target)
            else:
                entity = self._find_entity_by(entity_type="mob")
            if not entity:
                return "❌ Sin objetivo."

            name = self._entity_display(entity)
            self.bot.lookAt(entity.position.offset(0, 1.5, 0))
            self.bot.activateItem()  # Tensar arco
            time.sleep(1.2)          # Cargar
            self.bot.deactivateItem()  # Soltar flecha
            self.events.add("combat", f"Disparé a {name}")
            return f"🏹 Disparé a **{name}**"
        except Exception as e:
            return f"❌ Error: {e}"

    def use_shield(self, activate: bool = True) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            shield = self._find_item_in_inventory("shield")
            if not shield:
                return "❌ No tengo escudo."
            self.bot.equip(shield, "off-hand")
            if activate:
                self.bot.activateItem()
                return "🛡️ Escudo activado."
            else:
                self.bot.deactivateItem()
                return "🛡️ Escudo desactivado."
        except Exception as e:
            return f"❌ Error: {e}"

    def defend(self, radius: float = 8) -> str:
        """Ataca al mob hostil más cercano."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            bot_pos = self.bot.entity.position
            closest, closest_dist = None, radius
            for eid in self.bot.entities:
                e = self.bot.entities[eid]
                if e == self.bot.entity:
                    continue
                if not self._is_hostile(e):
                    continue
                try:
                    d = float(e.position.distanceTo(bot_pos))
                    if d < closest_dist:
                        closest, closest_dist = e, d
                except Exception:
                    continue
            if not closest:
                return "✅ No hay amenazas cercanas."
            name = self._entity_display(closest)
            return self.attack_continuous(target=name)
        except Exception as e:
            return f"❌ Error: {e}"

    # ══════════════════════════════════════════════════════════════════
    #  INVENTARIO Y EQUIPAMIENTO
    # ══════════════════════════════════════════════════════════════════

    def equip(self, item_name: str, slot: str = "hand") -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            item = self._find_item_in_inventory(item_name)
            if not item:
                return f"❌ No tengo **{item_name}**."
            dest = EQUIPMENT_SLOTS.get(slot.lower(), slot)
            self.bot.equip(item, dest)
            self.events.add("items", f"Equipé {item_name} en {dest}")
            return f"🔧 Equipé **{item_name}** en {dest}"
        except Exception as e:
            return f"❌ Error: {e}"

    def unequip(self, slot: str = "hand") -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            dest = EQUIPMENT_SLOTS.get(slot.lower(), slot)
            self.bot.unequip(dest)
            return f"🔧 Desequipé {dest}"
        except Exception as e:
            return f"❌ Error: {e}"

    def toss(self, item_name: str, count: int = None) -> str:
        """Tira un item al suelo."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            item = self._find_item_in_inventory(item_name)
            if not item:
                return f"❌ No tengo **{item_name}**."
            amount = count or int(getattr(item, 'count', 1))
            self.bot.tossStack(item) if count is None \
                else self.bot.toss(
                    int(getattr(item, 'type', 0)), None, int(amount))
            return f"🗑️ Tiré **{item_name}** ×{amount}"
        except Exception as e:
            return f"❌ Error: {e}"

    def transfer_to_chest(
        self, x: float, y: float, z: float,
        item_name: str, count: int = 1,
    ) -> str:
        return self.use_chest(x, y, z, "deposit", item_name, count)

    def take_from_chest(
        self, x: float, y: float, z: float,
        item_name: str, count: int = 1,
    ) -> str:
        return self.use_chest(x, y, z, "withdraw", item_name, count)

    # ══════════════════════════════════════════════════════════════════
    #  CRAFTING
    # ══════════════════════════════════════════════════════════════════

    def craft(
        self, item_name: str, count: int = 1,
        use_table: bool = False,
    ) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            name_lower = item_name.lower().replace(' ', '_')
            items_by_name = self.bot.registry.itemsByName
            if name_lower not in items_by_name:
                return f"❌ Item desconocido: `{item_name}`"
            item_id = int(items_by_name[name_lower].id)

            # Buscar mesa de crafteo si es necesario
            table = None
            if use_table:
                try:
                    bd = self.bot.registry.blocksByName.get('crafting_table')
                    if bd:
                        positions = list(self.bot.findBlocks({
                            "matching": int(bd.id),
                            "maxDistance": 32,
                            "count": 1,
                        }) or [])
                        if positions:
                            table = self.bot.blockAt(positions[0])
                except Exception:
                    pass
                if not table:
                    return "❌ No hay **mesa de crafteo** cerca."

            recipes = list(self.bot.recipesFor(item_id, None, 1, table))
            if not recipes:
                if not use_table:
                    return self.craft(item_name, count, use_table=True)
                return f"❌ Sin receta para **{item_name}** o faltan materiales."

            recipe = recipes[0]
            self.bot.craft(recipe, int(count), table)

            display = item_name.replace('_', ' ').title()
            self.events.add("craft", f"Crafteé {count}x {display}")
            return (
                f"🔨 Crafteé **{count}x {display}**"
                f"{' (con mesa)' if table else ''}"
            )
        except Exception as e:
            return f"❌ Error crafting: {e}"

    def smelt(
        self, item_name: str, count: int = 1,
        fuel: str = None,
    ) -> str:
        """Funde un item en un horno cercano."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            # Buscar horno
            bd = self.bot.registry.blocksByName.get('furnace')
            if not bd:
                return "❌ Registro de horno no encontrado."
            positions = list(self.bot.findBlocks({
                "matching": int(bd.id),
                "maxDistance": 32,
                "count": 1,
            }) or [])
            if not positions:
                return "❌ No hay **horno** cerca."

            furnace_block = self.bot.blockAt(positions[0])

            # Navegar al horno
            goal = self._pathfinder.goals.GoalNear(
                float(positions[0].x), float(positions[0].y),
                float(positions[0].z), 3,
            )
            self.bot.pathfinder.setGoal(goal)
            self._navigating = True
            self._wait_goal(timeout=15)

            # Abrir horno
            furnace = self.bot.openFurnace(furnace_block)
            time.sleep(0.5)

            # Poner item
            item = self._find_item_in_inventory(item_name)
            if not item:
                furnace.close()
                return f"❌ No tengo **{item_name}**."

            furnace.putInput(
                int(getattr(item, 'type', 0)), None,
                min(int(count), int(getattr(item, 'count', 1))),
            )

            # Poner combustible
            fuel_name = fuel or "coal"
            fuel_item = self._find_item_in_inventory(fuel_name)
            if fuel_item:
                furnace.putFuel(
                    int(getattr(fuel_item, 'type', 0)), None, 1)

            # Esperar fundido
            display = item_name.replace('_', ' ').title()
            result = SMELTABLE.get(
                item_name.lower().replace(' ', '_'), '?')
            time.sleep(min(count * 10, 60))

            # Sacar resultado
            try:
                furnace.takeOutput()
            except Exception:
                pass
            furnace.close()

            self.events.add("craft", f"Fundí {count}x {display}")
            return f"🔥 Fundí **{count}x {display}** → **{result}**"
        except Exception as e:
            return f"❌ Error fundiendo: {e}"

    # ══════════════════════════════════════════════════════════════════
    #  SUPERVIVENCIA
    # ══════════════════════════════════════════════════════════════════

    def eat(self, food_name: str = None) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            if food_name:
                item = self._find_item_in_inventory(food_name)
            else:
                item = self._find_best_food()
            if not item:
                return "❌ Sin comida en el inventario."
            name = getattr(item, 'displayName',
                           getattr(item, 'name', '?'))
            self.bot.equip(item, "hand")
            self.bot.activateItem()
            time.sleep(1.6)  # Tiempo de comer
            self.bot.deactivateItem()
            self.events.add("survival", f"Comí {name}")
            return f"🍖 Comí **{name}** (comida: {self.bot.food:.0f}/20)"
        except Exception as e:
            return f"❌ Error: {e}"

    def sleep(self) -> str:
        """Duerme en una cama cercana."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            bed_names = [
                "white_bed", "orange_bed", "magenta_bed",
                "light_blue_bed", "yellow_bed", "lime_bed",
                "pink_bed", "gray_bed", "light_gray_bed",
                "cyan_bed", "purple_bed", "blue_bed",
                "brown_bed", "green_bed", "red_bed", "black_bed",
            ]
            bed_block = None
            for bn in bed_names:
                bd = self.bot.registry.blocksByName.get(bn)
                if not bd:
                    continue
                positions = list(self.bot.findBlocks({
                    "matching": int(bd.id),
                    "maxDistance": 16,
                    "count": 1,
                }) or [])
                if positions:
                    bed_block = self.bot.blockAt(positions[0])
                    break
            if not bed_block:
                return "❌ No hay cama cercana."
            self.bot.sleep(bed_block)
            self.events.add("survival", "Durmiendo 😴")
            return "😴 Durmiendo..."
        except Exception as e:
            return f"❌ Error: {e}"

    def wake(self) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            self.bot.wake()
            return "☀️ Despierto."
        except Exception as e:
            return f"❌ Error: {e}"

    def use_item(self, item_name: str = None) -> str:
        """Usa el item en la mano (o equipa y usa el especificado)."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            if item_name:
                item = self._find_item_in_inventory(item_name)
                if not item:
                    return f"❌ No tengo **{item_name}**."
                self.bot.equip(item, "hand")
            self.bot.activateItem()
            time.sleep(0.3)
            held = self.bot.heldItem
            name = getattr(held, 'displayName', '?') if held else '?'
            return f"✨ Usando **{name}**"
        except Exception as e:
            return f"❌ Error: {e}"

    def fish(self, timeout: int = 30) -> str:
        """Pesca usando una caña de pescar."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            rod = self._find_item_in_inventory("fishing_rod")
            if not rod:
                return "❌ No tengo **caña de pescar**."
            self.bot.equip(rod, "hand")
            self.bot.activateItem()  # Lanzar
            self.events.add("survival", "Pescando...")

            # Esperar pesca
            caught = threading.Event()

            from javascript import On
            @On(self.bot, "playerCollect")
            def on_catch(this, collector, collected, *args):
                try:
                    if getattr(collector, 'username', '') == self.username:
                        caught.set()
                except Exception:
                    pass

            caught.wait(timeout=timeout)
            self.bot.activateItem()  # Recoger

            if caught.is_set():
                self.events.add("survival", "¡Pesqué algo!")
                return "🎣 ¡Pesqué algo!"
            else:
                return "🎣 Timeout pescando."
        except Exception as e:
            return f"❌ Error: {e}"

    def heal_check(self) -> str:
        """Verifica si necesita comer/curarse y actúa."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            hp = float(self.bot.health)
            food = float(self.bot.food)
            parts = [f"❤️ HP: {hp:.0f}/20 | 🍖 Comida: {food:.0f}/20"]

            if food <= 6:
                result = self.eat()
                parts.append(f"Acción: {result}")
            elif hp < 10 and food < 18:
                result = self.eat()
                parts.append(f"Comí para regenerar: {result}")
            else:
                parts.append("✅ Estado saludable.")

            return "\n".join(parts)
        except Exception as e:
            return f"❌ Error: {e}"

    # ══════════════════════════════════════════════════════════════════
    #  SOCIAL — Chat e interacción con jugadores
    # ══════════════════════════════════════════════════════════════════

    def chat(self, message: str) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            self.bot.chat(str(message))
            self.events.add("chat", f"[Yo]: {message}")
            return f"💬 Dije: {message}"
        except Exception as e:
            return f"❌ Error: {e}"

    def whisper(self, player: str, message: str) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            self.bot.whisper(player, str(message))
            self.events.add("chat", f"[Yo → {player}]: {message}")
            return f"🤫 Susurré a **{player}**: {message}"
        except Exception as e:
            return f"❌ Error: {e}"

    def trade_with_villager(self, target: str = None) -> str:
        """Lista los trades de un villager cercano."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            entity = self._find_entity_by(
                name=target or "villager", entity_type="mob")
            if not entity:
                return "❌ No hay villager cerca."
            name = self._entity_display(entity)

            # Acercarse
            pos = entity.position
            goal = self._pathfinder.goals.GoalNear(
                float(pos.x), float(pos.y), float(pos.z), 2)
            self.bot.pathfinder.setGoal(goal)
            self._navigating = True
            self._wait_goal(timeout=10)

            villager = self.bot.openVillager(entity)
            time.sleep(0.5)

            trades = list(villager.trades) if villager.trades else []
            if not trades:
                villager.close()
                return f"❌ **{name}** no tiene trades."

            lines = [f"## 🤝 Trades de **{name}**\n"]
            for i, trade in enumerate(trades):
                try:
                    inp1 = getattr(trade, 'inputItem1', None)
                    inp2 = getattr(trade, 'inputItem2', None)
                    out = getattr(trade, 'outputItem', None)
                    i1 = (f"{getattr(inp1, 'count', '?')}x "
                          f"{getattr(inp1, 'displayName', '?')}"
                          if inp1 else "?")
                    i2 = (f" + {getattr(inp2, 'count', '?')}x "
                          f"{getattr(inp2, 'displayName', '?')}"
                          if inp2 else "")
                    o = (f"{getattr(out, 'count', '?')}x "
                         f"{getattr(out, 'displayName', '?')}"
                         if out else "?")
                    disabled = " ❌" if getattr(
                        trade, 'disabled', False) else ""
                    lines.append(f"{i + 1}. {i1}{i2} → **{o}**{disabled}")
                except Exception:
                    lines.append(f"{i + 1}. (error leyendo trade)")

            villager.close()
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {e}"

    # ══════════════════════════════════════════════════════════════════
    #  MISCELÁNEOS
    # ══════════════════════════════════════════════════════════════════

    def respawn(self) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            self.bot.chat("/kill")
            time.sleep(3)
            return "💀 Respawneé."
        except Exception as e:
            return f"❌ Error: {e}"

    def set_hotbar_slot(self, slot: int) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            self.bot.setQuickBarSlot(int(slot))
            return f"🔢 Slot activo: {slot}"
        except Exception as e:
            return f"❌ Error: {e}"

    def use_entity(self, target: str) -> str:
        """Interactúa (click derecho) con una entidad."""
        err = self._ensure_connected()
        if err:
            return err
        entity = self._find_entity_by(name=target)
        if not entity:
            return f"❌ No encontré **{target}**."
        try:
            self.bot.useOn(entity)
            name = self._entity_display(entity)
            return f"🤝 Interactué con **{name}**"
        except Exception as e:
            return f"❌ Error: {e}"

    def mount(self, target: str = None) -> str:
        """Monta un animal/vehículo cercano."""
        err = self._ensure_connected()
        if err:
            return err
        entity = self._find_entity_by(name=target) if target \
            else self._find_entity_by(entity_type="mob")
        if not entity:
            return "❌ Nada que montar."
        try:
            self.bot.mount(entity)
            name = self._entity_display(entity)
            return f"🐴 Monté **{name}**"
        except Exception as e:
            return f"❌ Error: {e}"

    def dismount(self) -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            self.bot.dismount()
            return "🚶 Desmonté."
        except Exception as e:
            return f"❌ Error: {e}"

    def drop_all(self, item_name: str = None) -> str:
        """Tira todos los items de un tipo, o todo el inventario."""
        err = self._ensure_connected()
        if err:
            return err
        try:
            items = list(self.bot.inventory.items())
            dropped = 0
            for item in items:
                iname = (getattr(item, 'name', '') or '').lower()
                if item_name:
                    if item_name.lower().replace(' ', '_') not in iname:
                        continue
                self.bot.tossStack(item)
                dropped += 1
                time.sleep(0.1)
            return f"🗑️ Tiré **{dropped}** stacks."
        except Exception as e:
            return f"❌ Error: {e}"


# ─────────────────────────────────────────────────────────────────────
#  HERRAMIENTA PRINCIPAL — MinecraftTool (BaseTool para el agente)
# ─────────────────────────────────────────────────────────────────────

class MinecraftTool(BaseTool):
    """
    Herramienta unificada que expone TODAS las capacidades del bot
    al agente de IA mediante un único parámetro `action`.

    Uso:
        action: "connect"
        params: {"host": "127.0.0.1", "port": 25565, "username": "Bot"}

        action: "look_around"

        action: "goto"
        params: {"x": 100, "y": 64, "z": -200}

        action: "attack"
        params: {"target": "zombie"}
    """

    name = "minecraft"
    description = (
        "Controla un bot de Minecraft: movimiento, minería, combate, "
        "crafting, inventario, percepción, supervivencia e interacción social. "
        "Especifica 'action' y opcionalmente 'params'."
    )
    category = "minecraft"

    # Mapa de acciones válidas con descripción para el agente
    ACTIONS_HELP = {
        # Conexión
        "connect":         "Conectar al servidor (host, port, username, version, auth, password)",
        "disconnect":      "Desconectar del servidor",
        "reconnect":       "Reconectar al último servidor",
        # Percepción
        "look_around":     "Vista completa del entorno (radius)",
        "status":          "Estado del bot (HP, comida, XP, etc.)",
        "scan_blocks":     "Escanear bloques (block_name, radius, count)",
        "get_entities":    "Listar entidades cercanas (radius, entity_type)",
        "get_players":     "Listar jugadores en el servidor",
        "get_inventory":   "Ver inventario completo",
        "get_block_at":    "Info de un bloque (x, y, z)",
        "find_block":      "Buscar un bloque (block_name, radius, count)",
        "find_entity":     "Buscar una entidad (name, entity_type, radius)",
        "get_weather":     "Ver clima actual",
        "get_time":        "Ver hora del juego",
        "get_events":      "Ver eventos recientes (count, category)",
        "get_recipe":      "Ver receta de crafting (item_name)",
        # Movimiento
        "goto":            "Navegar a coordenadas (x, y, z, sprint)",
        "follow":          "Seguir a entidad/jugador (target, distance)",
        "come":            "Ir hacia un jugador (player_name)",
        "flee":            "Huir de una entidad (target, distance)",
        "jump":            "Saltar",
        "sprint":          "Activar/desactivar sprint (enabled)",
        "sneak":           "Activar/desactivar agacharse (enabled)",
        "stop":            "Detener todo movimiento y combate",
        "look_at":         "Mirar coordenadas (x, y, z)",
        "look_at_entity":  "Mirar a una entidad (target)",
        # Bloques
        "dig":             "Minar bloque (x, y, z)",
        "place":           "Colocar bloque (x, y, z, item_name, face)",
        "collect_block":   "Recolectar bloque (block_name, count, radius)",
        "activate_block":  "Activar bloque: cofre, puerta, etc. (x, y, z)",
        "close_window":    "Cerrar ventana abierta",
        "use_chest":       "Usar cofre (x, y, z, action=list/deposit/withdraw, item_name, count)",
        # Combate
        "attack":          "Atacar entidad (target)",
        "attack_continuous": "Atacar repetidamente (target, max_hits)",
        "shoot":           "Disparar con arco (target)",
        "use_shield":      "Usar escudo (activate)",
        "defend":          "Atacar mob hostil más cercano (radius)",
        # Inventario
        "equip":           "Equipar item (item_name, slot)",
        "unequip":         "Desequipar slot (slot)",
        "toss":            "Tirar item (item_name, count)",
        "drop_all":        "Tirar todos los items (item_name opcional)",
        # Crafting
        "craft":           "Craftear item (item_name, count, use_table)",
        "smelt":           "Fundir en horno (item_name, count, fuel)",
        # Supervivencia
        "eat":             "Comer (food_name opcional)",
        "sleep":           "Dormir en cama cercana",
        "wake":            "Despertarse",
        "use_item":        "Usar item en mano (item_name)",
        "fish":            "Pescar (timeout)",
        "heal_check":      "Verificar salud y comer si es necesario",
        # Social
        "chat":            "Enviar mensaje al chat (message)",
        "whisper":         "Enviar whisper (player, message)",
        "trade":           "Ver trades de villager (target)",
        # Misceláneos
        "respawn":         "Respawnear",
        "set_hotbar":      "Cambiar slot activo (slot)",
        "use_entity":      "Interactuar con entidad (target)",
        "mount":           "Montar animal/vehículo (target)",
        "dismount":        "Desmontar",
        "help":            "Mostrar todas las acciones disponibles",
    }

    def __init__(self):
        self.bot_manager = BotManager()

    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        actions_list = ", ".join(sorted(self.ACTIONS_HELP.keys()))
        return {
            "action": ToolParameter(
                name="action",
                type="string",
                description=f"Acción a realizar. Opciones: {actions_list}",
                required=True,
            ),
            "params": ToolParameter(
                name="params",
                type="object",
                description=(
                    "Parámetros de la acción como JSON. "
                    "Ej: {\"x\": 100, \"y\": 64, \"z\": -200}"
                ),
                required=False,
            ),
        }

    def execute(
        self, action: str = None, params: dict = None, **kwargs,
    ) -> str:
        action = (action or kwargs.get("action", "")).strip().lower()
        params = params or kwargs.get("params", {}) or {}

        # Fusionar kwargs sueltos en params
        for k, v in kwargs.items():
            if k not in ("action", "params") and k not in params:
                params[k] = v

        if not action:
            return self._help()

        bm = self.bot_manager

        # ── Dispatch table ───────────────────────────────────────────
        dispatch = {
            # Conexión
            "connect":          lambda: bm.connect(**params),
            "disconnect":       lambda: bm.disconnect(),
            "reconnect":        lambda: bm.reconnect(),
            # Percepción
            "look_around":      lambda: bm.look_around(
                                    params.get("radius", DEFAULT_RADIUS)),
            "status":           lambda: bm.get_status(),
            "scan_blocks":      lambda: bm.scan_blocks(
                                    params.get("block_name"),
                                    params.get("radius", DEFAULT_RADIUS),
                                    params.get("count", 20)),
            "get_entities":     lambda: bm.get_entities(
                                    params.get("radius", DEFAULT_RADIUS),
                                    params.get("entity_type")),
            "get_players":      lambda: bm.get_players(),
            "get_inventory":    lambda: bm.get_inventory(),
            "get_block_at":     lambda: bm.get_block_at(
                                    params["x"], params["y"], params["z"]),
            "find_block":       lambda: bm.find_block(
                                    params["block_name"],
                                    params.get("radius", DEFAULT_RADIUS),
                                    params.get("count", 5)),
            "find_entity":      lambda: bm.find_entity(
                                    params.get("name"),
                                    params.get("entity_type"),
                                    params.get("radius", DEFAULT_RADIUS)),
            "get_weather":      lambda: bm.get_weather(),
            "get_time":         lambda: bm.get_time(),
            "get_events":       lambda: bm.get_events(
                                    params.get("count", 15),
                                    params.get("category")),
            "get_recipe":       lambda: bm.get_recipe(params["item_name"]),
            # Movimiento
            "goto":             lambda: bm.goto(
                                    params["x"], params["y"], params["z"],
                                    params.get("sprint", True)),
            "follow":           lambda: bm.follow(
                                    params["target"],
                                    params.get("distance", 3)),
            "come":             lambda: bm.come(params["player_name"]),
            "flee":             lambda: bm.flee(
                                    params.get("target"),
                                    params.get("distance", 16)),
            "jump":             lambda: bm.jump(),
            "sprint":           lambda: bm.set_sprint(
                                    params.get("enabled", True)),
            "sneak":            lambda: bm.set_sneak(
                                    params.get("enabled", True)),
            "stop":             lambda: bm.stop(),
            "look_at":          lambda: bm.look_at(
                                    params["x"], params["y"], params["z"]),
            "look_at_entity":   lambda: bm.look_at_entity(params["target"]),
            # Bloques
            "dig":              lambda: bm.dig(
                                    params["x"], params["y"], params["z"]),
            "place":            lambda: bm.place(
                                    params["x"], params["y"], params["z"],
                                    params.get("item_name"),
                                    params.get("face", "top")),
            "collect_block":    lambda: bm.collect_block(
                                    params["block_name"],
                                    params.get("count", 1),
                                    params.get("radius", DEFAULT_RADIUS)),
            "activate_block":   lambda: bm.activate_block(
                                    params["x"], params["y"], params["z"]),
            "close_window":     lambda: bm.close_window(),
            "use_chest":        lambda: bm.use_chest(
                                    params["x"], params["y"], params["z"],
                                    params.get("action", "list"),
                                    params.get("item_name"),
                                    params.get("count", 1)),
            # Combate
            "attack":           lambda: bm.attack(params.get("target")),
            "attack_continuous": lambda: bm.attack_continuous(
                                    params.get("target"),
                                    params.get("max_hits", 20)),
            "shoot":            lambda: bm.shoot(params.get("target")),
            "use_shield":       lambda: bm.use_shield(
                                    params.get("activate", True)),
            "defend":           lambda: bm.defend(
                                    params.get("radius", 8)),
            # Inventario
            "equip":            lambda: bm.equip(
                                    params["item_name"],
                                    params.get("slot", "hand")),
            "unequip":          lambda: bm.unequip(
                                    params.get("slot", "hand")),
            "toss":             lambda: bm.toss(
                                    params["item_name"],
                                    params.get("count")),
            "drop_all":         lambda: bm.drop_all(
                                    params.get("item_name")),
            # Crafting
            "craft":            lambda: bm.craft(
                                    params["item_name"],
                                    params.get("count", 1),
                                    params.get("use_table", False)),
            "smelt":            lambda: bm.smelt(
                                    params["item_name"],
                                    params.get("count", 1),
                                    params.get("fuel")),
            # Supervivencia
            "eat":              lambda: bm.eat(params.get("food_name")),
            "sleep":            lambda: bm.sleep(),
            "wake":             lambda: bm.wake(),
            "use_item":         lambda: bm.use_item(
                                    params.get("item_name")),
            "fish":             lambda: bm.fish(
                                    params.get("timeout", 30)),
            "heal_check":       lambda: bm.heal_check(),
            # Social
            "chat":             lambda: bm.chat(params["message"]),
            "whisper":          lambda: bm.whisper(
                                    params["player"], params["message"]),
            "trade":            lambda: bm.trade_with_villager(
                                    params.get("target")),
            # Misc
            "respawn":          lambda: bm.respawn(),
            "set_hotbar":       lambda: bm.set_hotbar_slot(params["slot"]),
            "use_entity":       lambda: bm.use_entity(params["target"]),
            "mount":            lambda: bm.mount(params.get("target")),
            "dismount":         lambda: bm.dismount(),
            "help":             lambda: self._help(),
        }

        handler = dispatch.get(action)
        if not handler:
            # Buscar coincidencia parcial
            matches = [
                k for k in dispatch if k.startswith(action)
            ]
            if len(matches) == 1:
                handler = dispatch[matches[0]]
            else:
                suggestions = ", ".join(matches[:5]) if matches \
                    else "usa action: help"
                return (
                    f"❌ Acción desconocida: `{action}`\n"
                    f"Sugerencias: {suggestions}"
                )

        try:
            return handler()
        except KeyError as e:
            return f"❌ Parámetro requerido faltante: {e}"
        except TypeError as e:
            return f"❌ Error de parámetros: {e}"
        except Exception as e:
            return f"❌ Error ejecutando `{action}`: {e}"

    def _help(self) -> str:
        """Genera la ayuda completa de acciones."""
        lines = [
            "## 🎮 Minecraft Bot — Acciones disponibles\n",
            "Usa `action` + `params` (JSON). Ejemplos:\n",
            '```',
            'action: "connect"',
            'params: {"host": "127.0.0.1", "port": 25565}',
            '',
            'action: "goto"',
            'params: {"x": 100, "y": 64, "z": -200}',
            '',
            'action: "attack"',
            'params: {"target": "zombie"}',
            '```\n',
        ]

        categories = {
            "🔌 Conexión": [
                "connect", "disconnect", "reconnect",
            ],
            "👁️ Percepción": [
                "look_around", "status", "scan_blocks",
                "get_entities", "get_players", "get_inventory",
                "get_block_at", "find_block", "find_entity",
                "get_weather", "get_time", "get_events", "get_recipe",
            ],
            "🚶 Movimiento": [
                "goto", "follow", "come", "flee",
                "jump", "sprint", "sneak", "stop",
                "look_at", "look_at_entity",
            ],
            "⛏️ Bloques": [
                "dig", "place", "collect_block",
                "activate_block", "close_window", "use_chest",
            ],
            "⚔️ Combate": [
                "attack", "attack_continuous", "shoot",
                "use_shield", "defend",
            ],
            "🎒 Inventario": [
                "equip", "unequip", "toss", "drop_all",
            ],
            "🔨 Crafting": [
                "craft", "smelt",
            ],
            "❤️ Supervivencia": [
                "eat", "sleep", "wake", "use_item",
                "fish", "heal_check",
            ],
            "💬 Social": [
                "chat", "whisper", "trade",
            ],
            "🔧 Misc": [
                "respawn", "set_hotbar", "use_entity",
                "mount", "dismount",
            ],
        }

        for cat_name, actions in categories.items():
            lines.append(f"### {cat_name}")
            for action in actions:
                desc = self.ACTIONS_HELP.get(action, "")
                lines.append(f"- **{action}** — {desc}")
            lines.append("")

        return "\n".join(lines)