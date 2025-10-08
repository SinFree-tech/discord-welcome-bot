import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import json
import traceback

# ======================
# INTENTS
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
# FUNCIONES DE PERSISTENCIA
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
# UTIL: enviar mensaje (response o followup) y auto-borrar
# ======================
async def send_and_autodelete(interaction: discord.Interaction, content: str = None,
                              embed: discord.Embed = None, view: discord.ui.View = None,
                              ephemeral: bool = True, delete_after: int = 120):
    """
    Envía un mensaje relacionado a la interacción. Si interaction.response no está usado
    lo envía como response, si ya está usado, lo envía como followup. Programa borrado.
    Devuelve el objeto Message enviado o None si fallo.
    """
    try:
        # Si no se ha respondido, usar response
        if not interaction.response.is_done():
            await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
            # original_response() devuelve el Message asociado a la response
            msg = await interaction.original_response()
        else:
            msg = await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
    except Exception as e:
        # No insisto; devuelvo None
        # registra para diagnóstico
        traceback.print_exc()
        return None

    # Programar borrado si se solicitó
    if delete_after and msg:
        async def _deleter(m, delay):
            await asyncio.sleep(delay)
            try:
                await m.delete()
            except:
                pass
        asyncio.create_task(_deleter(msg, delete_after))

    return msg

# ======================
# EVENTO: BIENVENIDA
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
        try:
            await canal.send(embed=embed)
        except:
            pass

# ======================
# COMANDOS BÁSICOS
# ======================
@bot.tree.command(name="bienvenida", description="El bot te da un saludo de bienvenida")
async def bienvenida(interaction: discord.Interaction):
    await interaction.response.send_message(f"👋 ¡Hola {interaction.user.mention}! Bienvenido al servidor 🦁")

@bot.tree.command(name="info", description="Muestra información del servidor")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"📌 Servidor: {interaction.guild.name}\n👥 Miembros: {interaction.guild.member_count}"
    )

@bot.tree.command(name="ban", description="Banea a un miembro y le envía un DM con la razón")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(member="El usuario a banear", reason="Razón del baneo")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No se especificó razón"):
    try:
        embed = discord.Embed(
            title="⛔ Has sido baneado",
            description=f"Servidor: **{interaction.guild.name}**\nRazón: **{reason}**",
            color=discord.Color.red()
        )
        embed.set_footer(text="Si crees que fue un error, contacta con los admins.")
        await member.send(embed=embed)
    except:
        pass
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🚨 {member.mention} fue baneado. Razón: {reason}")

# ======================
# CANALES TEMPORALES
# ======================
@bot.event
async def on_voice_state_update(member, before, after):
    # Crear canal temporal al unirse al canal base
    if after.channel and after.channel.id == VOICE_CREATION_CHANNEL_ID:
        guild = member.guild
        category = after.channel.category
        new_channel = await guild.create_voice_channel(
            name=f"🔊 {member.display_name}",
            category=category
        )
        everyone = guild.default_role
        await new_channel.set_permissions(everyone, view_channel=True, connect=True)
        try:
            await member.move_to(new_channel)
        except:
            # Si el bot no puede mover (permiso), seguimos; el canal igual fue creado y guardado.
            pass
        data[str(new_channel.id)] = {"owner_id": member.id}
        save_data(data)

    # Eliminar canal vacío si está en registros
    if before.channel and str(before.channel.id) in data:
        if len(before.channel.members) == 0:
            try:
                del data[str(before.channel.id)]
                save_data(data)
                await before.channel.delete()
            except:
                pass

# ======================
# PANEL DE CONTROL
# ======================
class VoicePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def get_owned_channel(self, user: discord.Member):
        for ch_id, info in data.items():
            if info.get("owner_id") == user.id:
                return user.guild.get_channel(int(ch_id))
        return None

    # ----- RENAME -----
    @discord.ui.button(label="Nombre", style=discord.ButtonStyle.primary, emoji="📝", custom_id="vc_rename")
    async def rename(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await send_and_autodelete(interaction, "❌ No eres dueño de ninguna sala activa.", delete_after=8)
        # Pedir nuevo nombre (ephemeral)
        await send_and_autodelete(interaction, "✏️ Escribe el nuevo nombre (60s):", delete_after=120)

        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            new_name = msg.content.strip()
            # verificar permiso manage_channels antes de editar
            try:
                await channel.edit(name=new_name)
            except Exception:
                # informar si fallo
                await send_and_autodelete(interaction, "❌ No pude renombrar el canal (falta permiso Manage Channels).", delete_after=10)
                try: await msg.delete()
                except: pass
                return
            try: await msg.delete()
            except: pass
            await send_and_autodelete(interaction, f"✅ Nombre cambiado a **{new_name}**", delete_after=8)
        except asyncio.TimeoutError:
            await send_and_autodelete(interaction, "⏰ Tiempo agotado.", delete_after=8)

    # ----- PRIVACY -----
    @discord.ui.button(label="Privacidad", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="vc_lock")
    async def privacy(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await send_and_autodelete(interaction, "❌ No eres dueño de ninguna sala activa.", delete_after=8)
        everyone = interaction.guild.default_role
        perms = channel.overwrites_for(everyone)
        locked = perms.connect is False

        # Intentar cambiar overwrites (revisar permiso manage_channels)
        try:
            if locked:
                await channel.set_permissions(everyone, view_channel=True, connect=True)
                await send_and_autodelete(interaction, "🔓 Canal abierto para todos.", delete_after=8)
            else:
                await channel.set_permissions(everyone, view_channel=True, connect=False)
                await channel.set_permissions(interaction.user, view_channel=True, connect=True)
                await send_and_autodelete(interaction, "🔒 Canal bloqueado (visible pero sin acceso).", delete_after=8)
        except Exception:
            await send_and_autodelete(interaction, "❌ No pude cambiar la privacidad (falta permiso Manage Channels).", delete_after=10)

    # ----- ALLOW -----
    @discord.ui.button(label="Permitir", style=discord.ButtonStyle.success, emoji="✅", custom_id="vc_allow")
    async def allow(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await send_and_autodelete(interaction, "❌ No eres dueño de ninguna sala activa.", delete_after=8)

        # Pedir query (ephemeral)
        await send_and_autodelete(interaction, "🔍 Escribe el nombre o ID del usuario (60s):", delete_after=120)
        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            query = msg.content.lower().strip()
            try: await msg.delete()
            except: pass

            matches = [m for m in interaction.guild.members if query in m.display_name.lower() or query == str(m.id)]
            if not matches:
                return await send_and_autodelete(interaction, "❌ No encontré usuarios.", delete_after=8)

            options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in matches[:25]]

            class AllowSelect(discord.ui.Select):
                def __init__(self):
                    super().__init__(placeholder="Selecciona miembros", min_values=1, max_values=len(options), options=options)

                async def callback(self, si: discord.Interaction):
                    for uid in self.values:
                        member = interaction.guild.get_member(int(uid))
                        if member:
                            try:
                                await channel.set_permissions(member, view_channel=True, connect=True)
                            except:
                                pass
                    await send_and_autodelete(si, "✅ Permisos actualizados.", delete_after=8)

            view = discord.ui.View(timeout=60)
            view.add_item(AllowSelect())
            await send_and_autodelete(interaction, "Selecciona usuarios:", view=view, delete_after=120)
        except asyncio.TimeoutError:
            await send_and_autodelete(interaction, "⏰ Tiempo agotado.", delete_after=8)

    # ----- DISALLOW -----
    @discord.ui.button(label="Despermitir", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="vc_disallow")
    async def disallow(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await send_and_autodelete(interaction, "❌ No eres dueño de ninguna sala activa.", delete_after=8)

        allowed = [m for m, o in channel.overwrites.items() if isinstance(m, discord.Member) and (o.connect or o.view_channel)]
        if not allowed:
            return await send_and_autodelete(interaction, "⚠️ No hay usuarios permitidos.", delete_after=8)

        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in allowed[:25]]

        class DisallowSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="Selecciona quién quitar", min_values=1, max_values=len(options), options=options)

            async def callback(self, si: discord.Interaction):
                for uid in self.values:
                    member = si.guild.get_member(int(uid))
                    if member:
                        try:
                            await channel.set_permissions(member, overwrite=None)
                        except:
                            pass
                await send_and_autodelete(si, "🚫 Acceso retirado.", delete_after=8)

        view = discord.ui.View(timeout=60)
        view.add_item(DisallowSelect())
        await send_and_autodelete(interaction, "Selecciona usuarios:", view=view, delete_after=120)

    # ----- KICK -----
    @discord.ui.button(label="Expulsar", style=discord.ButtonStyle.danger, emoji="👢", custom_id="vc_kick")
    async def kick(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await send_and_autodelete(interaction, "❌ No eres dueño de ninguna sala activa.", delete_after=8)

        members = [m for m in channel.members if not m.bot and m != interaction.user]
        if not members:
            return await send_and_autodelete(interaction, "⚠️ No hay usuarios para expulsar.", delete_after=8)

        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]

        class KickSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="Selecciona a quién expulsar", min_values=1, max_values=len(options), options=options)

            async def callback(self, si: discord.Interaction):
                for uid in self.values:
                    member = si.guild.get_member(int(uid))
                    if member and member in channel.members:
                        try:
                            await member.move_to(None)
                        except:
                            pass
                await send_and_autodelete(si, "👢 Usuarios expulsados.", delete_after=8)

        view = discord.ui.View(timeout=60)
        view.add_item(KickSelect())
        await send_and_autodelete(interaction, "Selecciona miembros:", view=view, delete_after=120)

# ======================
# RESTAURAR CANALES AL INICIAR
# ======================
async def restore_temp_channels():
    await bot.wait_until_ready()
    # intentamos limpiar registros huérfanos
    for ch_id in list(data.keys()):
        exists = False
        for g in bot.guilds:
            if g.get_channel(int(ch_id)):
                exists = True
                break
        if not exists:
            del data[ch_id]
    save_data(data)
    print("🔁 Restauración completada. Registros huérfanos eliminados.")

# ======================
# CREACIÓN AUTOMÁTICA DEL PANEL
# ======================
async def setup_panel():
    await bot.wait_until_ready()
    channel = bot.get_channel(TEXT_PANEL_CHANNEL_ID)
    if not channel:
        print("❌ Canal del panel no encontrado.")
        return
    async for msg in channel.history(limit=10):
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
# /panel manual
# ======================
@bot.tree.command(name="panel", description="Recrear manualmente el panel")
async def panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Solo los administradores pueden usar esto.", ephemeral=True)
    await setup_panel()
    await interaction.response.send_message("✅ Panel recreado correctamente.", ephemeral=True)

# ======================
# /sync
# ======================
@bot.tree.command(name="sync", description="Forzar sincronización global de comandos")
async def sync(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"✅ Se sincronizaron {len(synced)} comandos globales", ephemeral=True)

# ======================
# READY
# ======================
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos sincronizados correctamente.")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")
    bot.add_view(VoicePanel())
    asyncio.create_task(setup_panel())
    asyncio.create_task(restore_temp_channels())
    print(f"🤖 Conectado como {bot.user}")

# ======================
# INICIO
# ======================
bot.run(os.getenv("TOKEN"))
