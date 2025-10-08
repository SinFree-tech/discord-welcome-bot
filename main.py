import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
import traceback

# ======================
# CONFIGURACIÓN E INTENTS
# ======================
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ======================
# CONSTANTES / RUTAS
# ======================
WELCOME_CHANNEL_ID = 1254534174430199888
VOICE_CREATION_CHANNEL_ID = 1425009175489937408
TEXT_PANEL_CHANNEL_ID = 1425026451677384744
DATA_FILE = "temvoice_data.json"

# ======================
# PERSISTENCIA
# ======================
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=4)

temvoice_data = load_data()  # estructura: { owner_id_str: {"channel_id": int, "locked": bool} }

# ======================
# UTIL: envío seguro de mensajes efímeros + borrado automático
# ======================
async def send_temporary(interaction: discord.Interaction, content: str = None, embed: discord.Embed = None, view: discord.ui.View = None, delete_after: int = 120):
    """
    Envía un mensaje (preferentemente ephemeral) respondiendo a la interacción.
    Si ya hubo respuesta inicial usa followup. Programa borrado tras delete_after segundos.
    Devuelve el Message (o None si fallo).
    """
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=True)
            msg = await interaction.original_response()
        else:
            msg = await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=True)
    except Exception as e:
        # No se pudo responder correctamente
        try:
            # intento fallback: DM al user para dar diagnostico
            await interaction.user.send(f"Error al procesar la interacción: {e}")
        except:
            pass
        return None

    if delete_after and msg:
        async def _deleter(m):
            await asyncio.sleep(delete_after)
            try:
                await m.delete()
            except:
                pass
        asyncio.create_task(_deleter(msg))
    return msg

async def send_error(interaction: discord.Interaction, message: str):
    """Mensaje de error estándar, ephemeral y autodestruye."""
    await send_temporary(interaction, content=f"❌ {message}")

# ======================
# UTIL: chequear permisos del BOT en un canal
# ======================
def bot_missing_perms_in(channel: discord.abc.GuildChannel, perms_required: list[str]) -> list[str]:
    """
    Devuelve lista de permisos que faltan para el bot en ese canal.
    perms_required: lista de atributos de discord.Permissions (ej. "manage_channels", "move_members")
    """
    guild = channel.guild
    me = guild.me  # Member
    perms = channel.permissions_for(me)
    missing = []
    for p in perms_required:
        if not getattr(perms, p, False):
            missing.append(p)
    return missing

# ======================
# EVENTO: BIENVENIDA
# ======================
@bot.event
async def on_member_join(member: discord.Member):
    canal = bot.get_channel(WELCOME_CHANNEL_ID)
    if canal:
        embed = discord.Embed(
            title="🎉 ¡Nuevo miembro en la familia!",
            description=(
                f"👋 Bienvenido {member.mention} a **{member.guild.name}**!\n\n"
                f"Contigo somos **{member.guild.member_count}** <a:dinnoo:1370259875132866650>\n\n"
                "📜 No olvides leer las reglas y conseguir tus roles 🎭"
            ),
            color=discord.Color.green()
        )
        embed.add_field(name="📢 Reglas", value="<#1253936573716762708>", inline=True)
        embed.add_field(name="🎲 Roles", value="<#1273266265405919284>", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Nos alegra tenerte con nosotros 🦁")
        try:
            await canal.send(embed=embed)
        except Exception:
            pass

# ======================
# PANEL: vista con botones
# ======================
class VoicePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # ---------- RENAME ----------
    @discord.ui.button(label="Nombre", style=discord.ButtonStyle.primary, emoji="📝", custom_id="vc_rename")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            owner_id = str(interaction.user.id)
            if owner_id not in temvoice_data:
                return await send_error(interaction, "No tienes una sala activa.")
            channel_id = temvoice_data[owner_id]["channel_id"]
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                return await send_error(interaction, "No encontré tu canal (quizá fue eliminado).")

            # Verificar permisos del bot para renombrar
            missing = bot_missing_perms_in(channel, ["manage_channels"])
            if missing:
                return await send_error(interaction, f"Faltan permisos para renombrar el canal: {', '.join(missing)}. Dale permisos de **Manage Channels** al bot.")

            await send_temporary(interaction, "✏️ Escribe el nuevo nombre (tienes 60s):")

            def check(m): return m.author == interaction.user and m.channel == interaction.channel

            try:
                msg = await bot.wait_for("message", check=check, timeout=60)
                new_name = msg.content.strip()
                await channel.edit(name=new_name)
                try: await msg.delete()
                except: pass
                await send_temporary(interaction, f"✅ Nombre cambiado a **{new_name}**")
            except asyncio.TimeoutError:
                await send_temporary(interaction, "⏰ Tiempo agotado.")
        except Exception as e:
            traceback.print_exc()
            await send_error(interaction, f"Error interno: {e}")

    # ---------- PRIVACY (lock/unlock) ----------
    @discord.ui.button(label="Privacidad", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="vc_privacy")
    async def privacy(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            owner_id = str(interaction.user.id)
            if owner_id not in temvoice_data:
                return await send_error(interaction, "No tienes una sala activa.")
            channel_id = temvoice_data[owner_id]["channel_id"]
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                return await send_error(interaction, "No encontré tu canal.")

            # require manage_channels for overwrites
            missing = bot_missing_perms_in(channel, ["manage_channels"])
            if missing:
                return await send_error(interaction, f"Faltan permisos para cambiar privacidad: {', '.join(missing)}")

            current = channel.overwrites_for(interaction.guild.default_role)
            locked = current.connect is False

            if locked:
                # Unlock: allow everyone connect
                await channel.set_permissions(interaction.guild.default_role, connect=True, view_channel=True)
                temvoice_data[owner_id]["locked"] = False
                save_data(temvoice_data)
                await send_temporary(interaction, "🔓 Canal desbloqueado: ahora cualquiera puede entrar.")
            else:
                # Lock: visible but not connect
                await channel.set_permissions(interaction.guild.default_role, connect=False, view_channel=True)
                temvoice_data[owner_id]["locked"] = True
                save_data(temvoice_data)
                await send_temporary(interaction, "🔒 Canal bloqueado (visible, pero sin acceso).")
        except Exception as e:
            traceback.print_exc()
            await send_error(interaction, f"Error interno: {e}")

    # ---------- ALLOW (dar acceso) ----------
    @discord.ui.button(label="Permitir", style=discord.ButtonStyle.success, emoji="✅", custom_id="vc_allow")
    async def allow(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            owner_id = str(interaction.user.id)
            if owner_id not in temvoice_data:
                return await send_error(interaction, "No tienes una sala activa.")
            channel_id = temvoice_data[owner_id]["channel_id"]
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                return await send_error(interaction, "No encontré tu canal.")

            missing = bot_missing_perms_in(channel, ["manage_channels"])
            if missing:
                return await send_error(interaction, f"Faltan permisos para gestionar accesos: {', '.join(missing)}")

            # crear lista de opciones solo con miembros no-bot (hasta 25)
            options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in interaction.guild.members if not m.bot][:25]
            if not options:
                return await send_temporary(interaction, "No hay miembros para seleccionar.", delete_after=10)

            select = discord.ui.Select(placeholder="Selecciona miembros para permitir", min_values=1, max_values=len(options), options=options, custom_id=f"vc_allow_select_{owner_id}")

            async def select_callback(select_interaction: discord.Interaction):
                try:
                    for uid in select.values:
                        member = select_interaction.guild.get_member(int(uid))
                        if member:
                            await channel.set_permissions(member, connect=True, view_channel=True)
                    await send_temporary(select_interaction, "✅ Permisos otorgados.")
                except Exception as e:
                    traceback.print_exc()
                    await send_error(select_interaction, f"Error al otorgar permisos: {e}")

            select.callback = select_callback
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            await send_temporary(interaction, "Selecciona los miembros a los que darás acceso:", view=view)
        except Exception as e:
            traceback.print_exc()
            await send_error(interaction, f"Error interno: {e}")

    # ---------- DISALLOW (quitar acceso) ----------
    @discord.ui.button(label="Despermitir", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="vc_disallow")
    async def disallow(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            owner_id = str(interaction.user.id)
            if owner_id not in temvoice_data:
                return await send_error(interaction, "No tienes una sala activa.")
            channel_id = temvoice_data[owner_id]["channel_id"]
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                return await send_error(interaction, "No encontré tu canal.")

            missing = bot_missing_perms_in(channel, ["manage_channels"])
            if missing:
                return await send_error(interaction, f"Faltan permisos para gestionar accesos: {', '.join(missing)}")

            # Buscar miembros con overwrites en el canal
            allowed = []
            for target, overw in channel.overwrites.items():
                if isinstance(target, discord.Member):
                    if getattr(overw, "connect", None) or getattr(overw, "view_channel", None):
                        allowed.append(target)
            if not allowed:
                return await send_temporary(interaction, "⚠️ No hay usuarios con permisos personalizados.", delete_after=10)

            options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in allowed][:25]
            select = discord.ui.Select(placeholder="Selecciona miembros para quitar acceso", min_values=1, max_values=len(options), options=options, custom_id=f"vc_disallow_select_{owner_id}")

            async def select_callback(select_interaction: discord.Interaction):
                try:
                    for uid in select.values:
                        member = select_interaction.guild.get_member(int(uid))
                        if member:
                            await channel.set_permissions(member, overwrite=None)
                    await send_temporary(select_interaction, "🚫 Acceso(s) retirado(s).")
                except Exception as e:
                    traceback.print_exc()
                    await send_error(select_interaction, f"Error al quitar permisos: {e}")

            select.callback = select_callback
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            await send_temporary(interaction, "Selecciona usuarios a los que quitar acceso:", view=view)
        except Exception as e:
            traceback.print_exc()
            await send_error(interaction, f"Error interno: {e}")

    # ---------- KICK (expulsar del canal moviendo a None) ----------
    @discord.ui.button(label="Expulsar", style=discord.ButtonStyle.danger, emoji="👢", custom_id="vc_kick")
    async def kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            owner_id = str(interaction.user.id)
            if owner_id not in temvoice_data:
                return await send_error(interaction, "No tienes una sala activa.")
            channel_id = temvoice_data[owner_id]["channel_id"]
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                return await send_error(interaction, "No encontré tu canal.")

            missing = bot_missing_perms_in(channel, ["move_members"])
            if missing:
                # If the bot can't move members, inform clearly
                return await send_error(interaction, f"Faltan permisos para mover/expulsar: {', '.join(missing)} (dale permiso Move Members al bot).")

            members = [m for m in channel.members if m != interaction.user and not m.bot]
            if not members:
                return await send_temporary(interaction, "⚠️ No hay usuarios para expulsar.", delete_after=10)

            options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members][:25]
            select = discord.ui.Select(placeholder="Selecciona usuarios para expulsar", min_values=1, max_values=len(options), options=options, custom_id=f"vc_kick_select_{owner_id}")

            async def select_callback(select_interaction: discord.Interaction):
                try:
                    for uid in select.values:
                        member = select_interaction.guild.get_member(int(uid))
                        if member and member in channel.members:
                            try:
                                await member.move_to(None)
                            except Exception:
                                # ignore individual move errors
                                pass
                    await send_temporary(select_interaction, "👢 Usuarios expulsados.")
                except Exception as e:
                    traceback.print_exc()
                    await send_error(select_interaction, f"Error al expulsar: {e}")

            select.callback = select_callback
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            await send_temporary(interaction, "Selecciona usuarios a expulsar:", view=view)
        except Exception as e:
            traceback.print_exc()
            await send_error(interaction, f"Error interno: {e}")

# ======================
# COMANDO /panel (opcional)
# ======================
@bot.tree.command(name="panel", description="Mostrar/recrear panel (admins).")
async def panel_cmd(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await send_temporary(interaction, "❌ Solo administradores pueden usar este comando.", delete_after=10)
    channel = bot.get_channel(TEXT_PANEL_CHANNEL_ID)
    if not channel:
        return await send_temporary(interaction, "Canal de panel no encontrado.", delete_after=10)
    # comprobar si ya existe panel
    async for m in channel.history(limit=20):
        if m.author == bot.user and m.embeds and "Panel de control de salas" in (m.embeds[0].title or ""):
            return await send_temporary(interaction, "✅ Ya existe un panel en ese canal.", delete_after=7)
    embed = discord.Embed(title="🎛️ Panel de control de salas", description=f"Primero crea una sala uniéndote a este canal: <#{VOICE_CREATION_CHANNEL_ID}>", color=discord.Color.blurple())
    await channel.send(embed=embed, view=VoicePanel())
    await send_temporary(interaction, "✅ Panel creado.")

# ======================
# CREACIÓN AUTOMÁTICA / BORRADO / PERSISTENCIA
# ======================
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    # CREAR canal temporal al unirse al creator
    try:
        if after.channel and after.channel.id == VOICE_CREATION_CHANNEL_ID:
            guild = member.guild
            category = after.channel.category
            new_channel = await guild.create_voice_channel(name=f"🔊 {member.display_name}", category=category)
            # visible para todos, conectable por defecto
            await new_channel.set_permissions(guild.default_role, view_channel=True, connect=True)
            # mueve al usuario
            try:
                await member.move_to(new_channel)
            except Exception:
                # falla mover = falta permiso move_members del bot; igual creamos y guardamos
                pass
            temvoice_data[str(member.id)] = {"channel_id": new_channel.id, "locked": False}
            save_data(temvoice_data)

        # BORRAR canal temporal si queda vacío
        if before.channel and before.channel.id != VOICE_CREATION_CHANNEL_ID:
            # comprobar si es un canal guardado en temvoice_data
            for owner_id, info in list(temvoice_data.items()):
                if info.get("channel_id") == before.channel.id:
                    if len(before.channel.members) == 0:
                        try:
                            await before.channel.delete()
                        except Exception:
                            pass
                        # eliminar del registro
                        del temvoice_data[owner_id]
                        save_data(temvoice_data)
                    break
    except Exception:
        traceback.print_exc()

# ======================
# COMANDOS BÁSICOS (también incluidos)
# ======================
@bot.tree.command(name="bienvenida", description="Saludo de bienvenida")
async def cmd_bienvenida(interaction: discord.Interaction):
    await send_temporary(interaction, f"👋 ¡Hola {interaction.user.mention}! Bienvenido al servidor 🦁", delete_after=10)

@bot.tree.command(name="info", description="Muestra info del servidor")
async def cmd_info(interaction: discord.Interaction):
    await send_temporary(interaction, f"📌 Servidor: {interaction.guild.name}\n👥 Miembros: {interaction.guild.member_count}", delete_after=12)

@bot.tree.command(name="ban", description="Banea a un miembro (requiere permiso)")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(member="Miembro", reason="Razón")
async def cmd_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No se especificó razón"):
    try:
        await member.send(f"⛔ Has sido baneado de {interaction.guild.name}. Razón: {reason}")
    except:
        pass
    try:
        await member.ban(reason=reason)
        await send_temporary(interaction, f"🚨 {member.mention} fue baneado. Razón: {reason}", delete_after=8)
    except Exception as e:
        traceback.print_exc()
        await send_error(interaction, f"Error al banear: {e}")

@bot.tree.command(name="sync", description="Sincroniza comandos")
async def cmd_sync(interaction: discord.Interaction):
    try:
        synced = await bot.tree.sync()
        await send_temporary(interaction, f"✅ {len(synced)} comandos sincronizados.", delete_after=8)
    except Exception as e:
        traceback.print_exc()
        await send_error(interaction, f"Error al sincronizar: {e}")

# ======================
# ON_READY: publicar panel si no existe + cargar datos / limpieza
# ======================
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception as e:
        print("Error sincronizando comandos:", e)
    bot.add_view(VoicePanel())
    print(f"Conectado como {bot.user} — TemVoice activo.")

    # limpiar registros de canales que ya no existen
    changed = False
    for owner_id, info in list(temvoice_data.items()):
        ch = bot.get_channel(info.get("channel_id"))
        if ch is None:
            del temvoice_data[owner_id]
            changed = True
    if changed:
        save_data(temvoice_data)

    # publicar el panel si no existe ya en el canal de panel
    panel_channel = bot.get_channel(TEXT_PANEL_CHANNEL_ID)
    if panel_channel:
        found = False
        async for m in panel_channel.history(limit=20):
            if m.author == bot.user and m.embeds:
                title = m.embeds[0].title or ""
                if "Panel de control de salas" in title:
                    found = True
                    break
        if not found:
            try:
                embed = discord.Embed(title="🎛️ Panel de control de salas", description=f"Primero crea una sala uniéndote a este canal: <#{VOICE_CREATION_CHANNEL_ID}>", color=discord.Color.blurple())
                await panel_channel.send(embed=embed, view=VoicePanel())
                print("Panel publicado automáticamente.")
            except Exception:
                traceback.print_exc()

# ======================
# RUN
# ======================
bot.run(os.getenv("TOKEN"))








