import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import json

# ======================
# INTENTS (necesarios)
# ======================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ======================
# CONFIGURACIÓN GENERAL
# ======================
WELCOME_CHANNEL_ID = 1254534174430199888
TEXT_PANEL_CHANNEL_ID = 1425026451677384744
VOICE_CREATION_CHANNEL_ID = 1425009175489937408
DATA_FILE = "temvoice_data.json"

# ======================
# PERSISTENCIA
# ======================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

data = load_data()

# ======================
# UTIL: auto-delete
# ======================
async def auto_delete_msg(msg_obj, delay=120):
    """Intenta borrar msg_obj (discord.Message) después de `delay` segundos."""
    try:
        await asyncio.sleep(delay)
        await msg_obj.delete()
    except Exception:
        pass

async def ephemeral_response(interaction: discord.Interaction, content: str = None, embed: discord.Embed = None, view: discord.ui.View = None, delete_after: int = 120):
    """Envía interaction.response.send_message(..., ephemeral=True) y programa su borrado."""
    await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=True)
    try:
        msg = await interaction.original_response()
        asyncio.create_task(auto_delete_msg(msg, delete_after))
    except Exception:
        pass

async def followup_response(interaction: discord.Interaction, content: str = None, embed: discord.Embed = None, view: discord.ui.View = None, delete_after: int = 120):
    """Envía interaction.followup.send(...) y programa su borrado; devuelve el message."""
    msg = await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=True)
    try:
        asyncio.create_task(auto_delete_msg(msg, delete_after))
    except Exception:
        pass
    return msg

# ======================
# EVENTO: on_member_join (bienvenida)
# ======================
@bot.event
async def on_member_join(member):
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
        await canal.send(embed=embed)

# ======================
# SLASH COMMANDS BÁSICOS
# ======================
@bot.tree.command(name="bienvenida", description="El bot te da un saludo de bienvenida")
async def bienvenida(interaction: discord.Interaction):
    await interaction.response.send_message(f"👋 ¡Hola {interaction.user.mention}! Bienvenido al servidor 🦁", ephemeral=True)
    try:
        asyncio.create_task(auto_delete_msg(await interaction.original_response(), 120))
    except:
        pass

@bot.tree.command(name="info", description="Muestra información del servidor")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message(f"📌 Servidor: {interaction.guild.name}\n👥 Miembros: {interaction.guild.member_count}", ephemeral=True)
    try:
        asyncio.create_task(auto_delete_msg(await interaction.original_response(), 120))
    except:
        pass

@bot.tree.command(name="ban", description="Banea a un miembro y le envía un DM con la razón")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(member="El usuario que quieres banear", reason="La razón del baneo")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No se especificó razón"):
    # Intentar DM antes de banear
    try:
        embed = discord.Embed(
            title="⛔ Has sido baneado",
            description=f"Servidor: **{interaction.guild.name}**\nRazón: **{reason}**",
            color=discord.Color.red()
        )
        embed.set_footer(text="Si crees que fue un error, contacta con los admins.")
        await member.send(embed=embed)
    except:
        pass  # Ignorar si no se puede mandar DM

    # Ejecutar el ban
    await member.ban(reason=reason)

    # Confirmación en el chat (ephemeral para quien ejecuta)
    await interaction.response.send_message(f"🚨 {member.mention} fue baneado. Razón: {reason}", ephemeral=True)
    try:
        asyncio.create_task(auto_delete_msg(await interaction.original_response(), 120))
    except:
        pass

@bot.tree.command(name="sync", description="Forzar sincronización global de comandos")
async def sync_cmd(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"✅ Se sincronizaron {len(synced)} comandos globales", ephemeral=True)
    try:
        asyncio.create_task(auto_delete_msg(await interaction.original_response(), 120))
    except:
        pass

# ======================
# CANALES TEMPORALES AUTOMÁTICOS
# ======================
@bot.event
async def on_voice_state_update(member, before, after):
    # Crear canal temporal al entrar al canal base
    if after.channel and after.channel.id == VOICE_CREATION_CHANNEL_ID:
        guild = member.guild
        category = after.channel.category

        new_channel = await guild.create_voice_channel(
            name=f"🔊 {member.display_name}",
            category=category
        )

        # Visible para todos por defecto (view=True). Conectable por defecto.
        everyone = guild.default_role
        await new_channel.set_permissions(everyone, view_channel=True, connect=True)

        # Mover al usuario
        await member.move_to(new_channel)

        # Guardar dueño
        data[str(new_channel.id)] = {"owner_id": member.id}
        save_data(data)

    # Borrar canal temporal si queda vacío
    if before.channel and str(before.channel.id) in data:
        if len(before.channel.members) == 0:
            try:
                del data[str(before.channel.id)]
                save_data(data)
                await before.channel.delete()
            except Exception:
                pass

# ======================
# PANEL DE CONTROL DE SALAS
# ======================
class VoicePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def get_owned_channel(self, user: discord.Member):
        for ch_id, info in data.items():
            if info.get("owner_id") == user.id:
                return user.guild.get_channel(int(ch_id))
        return None

    # Cambiar nombre
    @discord.ui.button(label="Nombre", style=discord.ButtonStyle.primary, emoji="📝", custom_id="vc_rename")
    async def rename(self, interaction: discord.Interaction, _button):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await ephemeral_response(interaction, "❌ No eres dueño de ninguna sala activa.")
        await ephemeral_response(interaction, "✏️ Escribe el nuevo nombre (60s):")
        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            new_name = msg.content.strip()
            await channel.edit(name=new_name)
            try: await msg.delete()
            except: pass
            follow = await followup_response(interaction, f"✅ Nombre cambiado a **{new_name}**")
        except asyncio.TimeoutError:
            follow = await followup_response(interaction, "⏰ Tiempo agotado. Intenta de nuevo.")

    # Privacidad (visible = True always; connect toggled)
    @discord.ui.button(label="Privacidad", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="vc_lock")
    async def privacy(self, interaction: discord.Interaction, _button):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await ephemeral_response(interaction, "❌ No eres dueño de ninguna sala activa.")
        everyone = interaction.guild.default_role
        perms = channel.overwrites_for(everyone)
        # locked = connect False means locked
        locked = perms.connect is False
        if locked:
            # desbloquear: permitir conectar a todos
            await channel.set_permissions(everyone, view_channel=True, connect=True)
            await channel.set_permissions(interaction.user, view_channel=True, connect=True)
            await followup_response(interaction, "🔓 Canal abierto para todos.")
        else:
            # bloquear: seguir visible pero no conectable
            await channel.set_permissions(everyone, view_channel=True, connect=False)
            # aseguramos que el owner pueda entrar
            await channel.set_permissions(interaction.user, view_channel=True, connect=True, manage_channels=True)
            await followup_response(interaction, "🔒 Canal bloqueado (visible, pero sin acceso).")

    # Permitir (búsqueda manual y selección múltiple)
    @discord.ui.button(label="Permitir", style=discord.ButtonStyle.success, emoji="✅", custom_id="vc_allow")
    async def allow(self, interaction: discord.Interaction, _button):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await ephemeral_response(interaction, "❌ No eres dueño de ninguna sala activa.")

        await ephemeral_response(interaction, "🔍 Escribe el nombre o ID del usuario (60s):")
        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            qmsg = await bot.wait_for("message", check=check, timeout=60)
            query = qmsg.content.lower().strip()
            try: await qmsg.delete()
            except: pass

            matches = [m for m in interaction.guild.members if not m.bot and (query in m.display_name.lower() or query in m.name.lower() or query == str(m.id))]
            if not matches:
                return await followup_response(interaction, "❌ No encontré usuarios con ese nombre o ID.")

            matches = matches[:25]
            options = [discord.SelectOption(label=f"{m.display_name} — {m}", value=str(m.id)) for m in matches]

            class AllowSelect(discord.ui.Select):
                def __init__(self):
                    super().__init__(placeholder="Selecciona miembros para permitir", min_values=1, max_values=len(options), options=options, custom_id="vc_allow_select")
                async def callback(self, select_interaction: discord.Interaction):
                    for uid in self.values:
                        member = interaction.guild.get_member(int(uid))
                        if member:
                            await channel.set_permissions(member, view_channel=True, connect=True)
                    await select_interaction.response.send_message("✅ Permisos actualizados.", ephemeral=True)
                    try:
                        orig = await select_interaction.original_response()
                        asyncio.create_task(auto_delete_msg(orig, 120))
                    except: pass

            view = discord.ui.View(timeout=60)
            view.add_item(AllowSelect())
            await followup_response(interaction, "Selecciona los usuarios a los que darás acceso:", view=view)

        except asyncio.TimeoutError:
            await followup_response(interaction, "⏰ Tiempo agotado. Intenta de nuevo.")

    # Despermitir
    @discord.ui.button(label="Despermitir", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="vc_disallow")
    async def disallow(self, interaction: discord.Interaction, _button):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await ephemeral_response(interaction, "❌ No eres dueño de ninguna sala activa.")

        allowed = [m for m, o in channel.overwrites.items() if isinstance(m, discord.Member) and (o.connect or o.view_channel)]
        if not allowed:
            return await ephemeral_response(interaction, "⚠️ No hay usuarios permitidos.")

        options = [discord.SelectOption(label=f"{m.display_name} — {m}", value=str(m.id)) for m in allowed[:25]]

        class DisallowSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="Selecciona quién quitar", min_values=1, max_values=len(options), options=options, custom_id="vc_disallow_select")
            async def callback(self, select_interaction: discord.Interaction):
                for uid in self.values:
                    member = interaction.guild.get_member(int(uid))
                    if member:
                        await channel.set_permissions(member, overwrite=None)
                await select_interaction.response.send_message("🚫 Acceso retirado.", ephemeral=True)
                try:
                    orig = await select_interaction.original_response()
                    asyncio.create_task(auto_delete_msg(orig, 120))
                except: pass

        view = discord.ui.View(timeout=60)
        view.add_item(DisallowSelect())
        await followup_response(interaction, "Selecciona usuarios a los que quitar acceso:", view=view)

    # Expulsar (mover a None)
    @discord.ui.button(label="Expulsar", style=discord.ButtonStyle.danger, emoji="👢", custom_id="vc_kick")
    async def kick(self, interaction: discord.Interaction, _button):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await ephemeral_response(interaction, "❌ No eres dueño de ninguna sala activa.")

        members = [m for m in channel.members if not m.bot and m != interaction.user]
        if not members:
            return await ephemeral_response(interaction, "⚠️ No hay usuarios para expulsar.")

        options = [discord.SelectOption(label=f"{m.display_name} — {m}", value=str(m.id)) for m in members[:25]]

        class KickSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="Selecciona a quién expulsar", min_values=1, max_values=len(options), options=options, custom_id="vc_kick_select")
            async def callback(self, select_interaction: discord.Interaction):
                for uid in self.values:
                    member = interaction.guild.get_member(int(uid))
                    if member:
                        try:
                            await member.move_to(None)
                        except:
                            pass
                await select_interaction.response.send_message("👢 Usuarios expulsados.", ephemeral=True)
                try:
                    orig = await select_interaction.original_response()
                    asyncio.create_task(auto_delete_msg(orig, 120))
                except: pass

        view = discord.ui.View(timeout=60)
        view.add_item(KickSelect())
        await followup_response(interaction, "Selecciona usuarios a expulsar:", view=view)

# ======================
# CREACIÓN AUTOMÁTICA DEL PANEL
# ======================
async def setup_panel():
    await bot.wait_until_ready()
    channel = bot.get_channel(TEXT_PANEL_CHANNEL_ID)
    if not channel:
        print("❌ Canal del panel no encontrado.")
        return

    # Evitar duplicados: si ya hay mensaje del bot con componentes, no crear otro
    async for msg in channel.history(limit=20):
        if msg.author == bot.user and msg.components:
            return

    embed = discord.Embed(
        title="🎛️ Panel de control de salas temporales",
        description=(
            f"Primero crea una sala uniéndote a este canal: <#{VOICE_CREATION_CHANNEL_ID}>\n\n"
            "**Desde aquí puedes:**\n"
            "📝 Cambiar el nombre de tu sala.\n"
            "🔒 Bloquear o desbloquear tu canal.\n"
            "✅ Permitir acceso a usuarios.\n"
            "🚫 Quitar acceso a usuarios.\n"
            "👢 Expulsar miembros.\n\n"
            "⚙️ *Solo el dueño de la sala puede usar estos botones.*"
        ),
        color=discord.Color.blurple()
    )
    await channel.send(embed=embed, view=VoicePanel())

# ======================
# SLASH: /panel (manual)
# ======================
@bot.tree.command(name="panel", description="Recrear manualmente el panel")
async def panel_cmd(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await ephemeral_response(interaction, "❌ Solo los administradores pueden usar esto.")
    await setup_panel()
    await ephemeral_response(interaction, "✅ Panel recreado correctamente.")

# ======================
# SYNC / READY
# ======================
@bot.event
async def on_ready():
    # Intentamos sincronizar comandos. Si ya hay sincronización global, esto confirmará.
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos sincronizados correctamente.")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")

    # Asegurar persistence y crear panel si falta
    bot.add_view(VoicePanel())
    asyncio.create_task(setup_panel())
    print(f"🤖 Conectado como {bot.user}")

# ======================
# INICIO DEL BOT
# ======================
bot.run(os.getenv("TOKEN"))






