import os
import asyncio
import threading
from typing import List, Optional, Any
from .logger import logger
from .types import OpenClawMessage, ChannelType, TaskPriority
from .resilience import RateLimiter

# Discord checks
DISCORD_AVAILABLE = False
try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    pass

class DiscordBot:
    """Bot de Discord mejorado con reconexión y rate limiting"""

    def __init__(
        self,
        openclaw_agent: Any, # Use Any to avoid circular import if needed
        token: str = None,
        channel_whitelist: List[str] = None
    ):
        self.openclaw = openclaw_agent
        self.token = token or os.environ.get('DISCORD_TOKEN')
        self.channel_whitelist = set(channel_whitelist or [])
        self.bot = None
        self._ready = False
        self._rate_limiter = RateLimiter(max_calls=20, window_seconds=60.0)
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def is_available(self) -> bool:
        return DISCORD_AVAILABLE and self.token is not None

    async def _setup_internal(self):
        """Configuración interna ejecutada dentro del loop del bot"""
        if not self.is_available():
            return False

        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True

        self.bot = commands.Bot(
            command_prefix='!oc ',
            intents=intents,
            help_command=commands.DefaultHelpCommand()
        )

        @self.bot.event
        async def on_ready():
            self._ready = True
            logger.info(f"Discord bot connected as {self.bot.user}")
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name="tus mensajes | !oc help"
                )
            )

        @self.bot.event
        async def on_disconnect():
            self._ready = False
            logger.warning("Discord bot disconnected")

        @self.bot.event
        async def on_error(event, *args, **kwargs):
            logger.error(f"Discord event error in {event}: {args} {kwargs}", exc_info=True)

        @self.bot.event
        async def on_message(message):
            if message.author == self.bot.user:
                return

            if self.channel_whitelist:
                if str(message.channel.id) not in self.channel_whitelist:
                    return

            await self.bot.process_commands(message)

            ctx = await self.bot.get_context(message)
            if ctx.valid:
                return

            is_mentioned = self.bot.user in message.mentions
            is_dm = isinstance(message.channel, discord.DMChannel)

            # Si whitelist definida: solo responde si lo mencionan o es DM
            # Si whitelist vacía: responde a TODO el canal (modo abierto)
            if self.channel_whitelist and not is_mentioned and not is_dm:
                return

            if not self._rate_limiter.acquire(timeout=5.0):
                await message.channel.send(
                    "⏳ Demasiadas solicitudes. Espera un momento."
                )
                return

            content = message.content
            if self.bot.user:
                content = content.replace(
                    f'<@{self.bot.user.id}>', ''
                ).strip()

            if not content:
                return

            oc_message = OpenClawMessage(
                content=content,
                channel=ChannelType.DISCORD,
                user_id=str(message.author.id),
                channel_id=str(message.channel.id),
                metadata={
                    'author_name': message.author.display_name,
                    'channel_name': getattr(
                        message.channel, 'name', 'DM'
                    ),
                    'guild_name': (
                        message.guild.name if message.guild else 'DM'
                    )
                }
            )

            async with message.channel.typing():
                try:
                    # Bridgear hacia el loop del agente si existe
                    import concurrent.futures
                    agent_loop = getattr(self.openclaw, '_async_loop', None)
                    if agent_loop and not agent_loop.is_closed() and agent_loop.is_running():
                        future = asyncio.run_coroutine_threadsafe(
                            self.openclaw._process_message_async_internal(oc_message),
                            agent_loop
                        )
                        try:
                            response = await asyncio.get_event_loop().run_in_executor(
                                None, lambda: future.result(timeout=300)
                            )
                        except concurrent.futures.TimeoutError:
                            await message.channel.send("⏱️ Timeout - el agente tardó demasiado")
                            return
                    else:
                        response = await self.openclaw._process_message_async_internal(
                            oc_message
                        )

                    if response.content or response.thinking:
                        formatted = self._format_response(response)
                        for chunk in formatted:
                            await self._send_with_files(message.channel, chunk)
                except Exception as e:
                    logger.error(f"Discord message error: {e}", exc_info=True)
                    await message.channel.send(f"❌ Error: {str(e)[:200]}")

        @self.bot.command(name='model')
        async def switch_model(ctx, model_key: str = None):
            """Cambia el modelo de IA"""
            if model_key:
                success, msg = self.openclaw.model_selector.switch_model(
                    model_key
                )
                if success:
                    self.openclaw.current_model = (
                        self.openclaw.model_selector.current_model
                    )
                await ctx.send(f"🤖 {msg}")
            else:
                await ctx.send(
                    "📋 Uso: `!oc model <número>` (ej: `!oc model 3`)"
                )

        @self.bot.command(name='models')
        async def list_models(ctx):
            """Lista modelos disponibles"""
            context = {
                'current_model': self.openclaw.current_model
            }
            result = self.openclaw.skills._action_list_models("", context)
            await self._send_long_message(ctx.channel, result)

        @self.bot.command(name='status')
        async def status(ctx):
            """Muestra estado del sistema"""
            context = {
                'current_model': self.openclaw.current_model,
                'memory': self.openclaw.memory,
                'model_selector': self.openclaw.model_selector
            }
            result = self.openclaw.skills._action_status("", context)
            await self._send_long_message(ctx.channel, result)

        @self.bot.command(name='clear')
        async def clear(ctx):
            """Limpia el contexto de conversación"""
            self.openclaw.memory.clear_channel(str(ctx.channel.id))
            await ctx.send("🗑️ Contexto limpiado")

        @self.bot.command(name='health')
        async def health(ctx):
            """Muestra salud de los modelos"""
            context = {
                'model_selector': self.openclaw.model_selector
            }
            result = self.openclaw.skills._action_model_health("", context)
            await self._send_long_message(ctx.channel, result)

        return True

    def setup(self):
        """Marcador para compatibilidad"""
        return True

    def _format_response(self, response) -> list:
        """Formatea la respuesta del agente al estilo consola para Discord"""
        chunks = []
        model_name = response.model_used or (
            getattr(self.openclaw.current_model, 'name', 'OpenClaw')
            if self.openclaw.current_model else 'OpenClaw'
        )

        # Bloque de razonamiento/thinking
        if response.thinking:
            think_lines = response.thinking.strip().split('\n')
            bar_len = max(0, 44 - len(model_name))
            top_bar = '─' * bar_len
            bot_bar = '─' * 50
            box = f"╭─ **{model_name}** 🧠 Razonamiento ─{top_bar}╮\n"
            for line in think_lines[:30]:  # máx 30 líneas de thinking
                box += f"│ {line}\n"
            if len(think_lines) > 30:
                box += f"│ _...({len(think_lines)-30} líneas más)_\n"
            box += f"╰{bot_bar}╯"
            chunks.append(box)

        # Contenido principal
        if response.content:
            chunks.append(response.content)

        # Footer con metadata
        meta_parts = []
        if response.elapsed_time:
            meta_parts.append(f"⏱️ {response.elapsed_time:.1f}s")
        if response.tools_used:
            meta_parts.append(f"🔧 {', '.join(response.tools_used[:3])}")
        if meta_parts:
            chunks.append(f"-# {' | '.join(meta_parts)}")

        # Añadir archivos encontrados como markers para que _send_with_files los procese
        if response.files:
            file_chunk = " ".join(f"[FILE:{f}]" for f in response.files)
            chunks.append(file_chunk)

        return chunks if chunks else ["_(Sin respuesta)_"]

    async def _send_with_files(self, channel, content: str):
        """Envía mensaje detectando [FILE:path] tags y adjuntando archivos reales"""
        import re
        from pathlib import Path

        # Extraer todos los FILE markers
        file_pattern = re.compile(r'\[FILE:([^\]]+)\]')
        file_paths = file_pattern.findall(content)

        # Limpiar el texto de los markers
        clean_text = file_pattern.sub('', content).strip()

        # Filtrar archivos que existen y no son muy grandes (max 8MB para Discord free)
        MAX_SIZE = 8 * 1024 * 1024
        discord_files = []
        failed_files = []

        for path_str in file_paths:
            p = Path(path_str.strip())
            if p.exists():
                if p.stat().st_size <= MAX_SIZE:
                    discord_files.append(discord.File(str(p), filename=p.name))
                else:
                    size_mb = p.stat().st_size / (1024 * 1024)
                    failed_files.append(f"`{p.name}` ({size_mb:.1f} MB — muy grande para Discord)")
            else:
                failed_files.append(f"`{path_str}` — archivo no encontrado")

        # Añadir avisos de fallos al texto
        if failed_files:
            clean_text += "\n⚠️ Archivos no enviados:\n" + "\n".join(failed_files)

        # Enviar
        if discord_files:
            # Si hay texto, enviarlo con los archivos
            if clean_text:
                await self._send_long_message(channel, clean_text)
            # Enviar archivos (Discord permite max 10 por mensaje)
            for i in range(0, len(discord_files), 10):
                batch = discord_files[i:i+10]
                await channel.send(files=batch)
        else:
            # Sin archivos: envío normal
            if clean_text:
                await self._send_long_message(channel, clean_text)

    async def _send_long_message(
        self,
        channel,
        content: str,
        max_length: int = 1900
    ):
        """Envía mensaje largo dividiéndolo en chunks"""
        if len(content) <= max_length:
            await channel.send(content)
            return

        paragraphs = content.split('\n\n')
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 > max_length:
                if current_chunk:
                    await channel.send(current_chunk)
                    current_chunk = ""

                if len(para) > max_length:
                    for i in range(0, len(para), max_length):
                        await channel.send(para[i:i + max_length])
                    continue

            current_chunk += ("\n\n" if current_chunk else "") + para

        if current_chunk:
            await channel.send(current_chunk)

    def run_in_thread(self) -> Optional[threading.Thread]:
        """Ejecuta el bot en un thread separado con su propio event loop"""
        if not self.token:
            logger.error("Discord: no hay token, no se puede iniciar")
            return None

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            async def _start():
                await self._setup_internal()
                await self.bot.start(self.token, reconnect=True)
                
            try:
                self._loop.run_until_complete(_start())
            except Exception as e:
                logger.error(f"Discord bot error: {e}", exc_info=True)
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=_run, daemon=True, name="discord-bot")
        self._thread.start()
        return self._thread

    async def shutdown(self):
        """Apaga el bot limpiamente"""
        if self.bot and self._ready:
            await self.bot.close()
            self._ready = False

