import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import json

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

async def auto_delete_msg(msg_obj, delay=120):
    """Borra los mensajes efímeros después de cierto tiempo"""
    try:
        await asyncio.sleep(delay)
        await msg_obj.delete()
    except:
        pass

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
        await canal.send(embed=embed)

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
    if after.channel and after.channel.id == VOICE_CREATION_CHANNEL_ID:
        guild = member.guild
        category = after.channel.category
        new_channel = await guild.create_voice_channel(
            name=f"🔊 {member.display_name}",
            category=category
        )
        everyone = guild.default_role
        await new_channel.set_permissions(everyone, view_channel=True, connect=True)
        await member.move_to(new_channel)
        data[str(new_channel.id)] = {"owner_id": member.id}
        save_data(data)

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

    async def get_owned_channel(self, user):
        for ch_id, info in data.items():
            if info.get("owner_id") == user.id:
                return user.guild.get_channel(int(ch_id))
        return None

    @discord.ui.button(label="Nombre", style=discord.ButtonStyle.primary, emoji="📝", custom_id="vc_rename")
    async def rename(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message("❌ No eres dueño de ninguna sala activa.", ephemeral=True)
        await interaction.response.send_message("✏️ Escribe el nuevo nombre (60s):", ephemeral=True)

        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            await channel.edit(name=msg.content)
            await msg.delete()
            resp = await interaction.followup.send(f"✅ Nombre cambiado a **{msg.content}**", ephemeral=True)
            asyncio.create_task(auto_delete_msg(resp, 120))
        except asyncio.TimeoutError:
            resp = await interaction.followup.send("⏰ Tiempo agotado.", ephemeral=True)
            asyncio.create_task(auto_delete_msg(resp, 120))

    @discord.ui.button(label="Privacidad", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="vc_lock")
    async def privacy(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message("❌ No eres dueño de ninguna sala activa.", ephemeral=True)
        everyone = interaction.guild.default_role
        perms = channel.overwrites_for(everyone)
        locked = perms.connect is False

        if locked:
            await channel.set_permissions(everyone, view_channel=True, connect=True)
            msg = await interaction.response.send_message("🔓 Canal abierto para todos.", ephemeral=True)
        else:
            await channel.set_permissions(everyone, view_channel=True, connect=False)
            await channel.set_permissions(interaction.user, view_channel=True, connect=True)
            msg = await interaction.response.send_message("🔒 Canal bloqueado (visible pero sin acceso).", ephemeral=True)
        asyncio.create_task(auto_delete_msg(msg, 120))

    @discord.ui.button(label="Permitir", style=discord.ButtonStyle.success, emoji="✅", custom_id="vc_allow")
    async def allow(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message("❌ No eres dueño de ninguna sala activa.", ephemeral=True)

        await interaction.response.send_message("🔍 Escribe el nombre o ID del usuario (60s):", ephemeral=True)
        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            query = msg.content.lower().strip()
            await msg.delete()
            matches = [m for m in interaction.guild.members if query in m.display_name.lower() or query == str(m.id)]
            if not matches:
                return await interaction.followup.send("❌ No encontré usuarios.", ephemeral=True)

            options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in matches[:25]]
            class AllowSelect(discord.ui.Select):
                def __init__(self):
                    super().__init__(placeholder="Selecciona miembros", min_values=1, max_values=len(options), options=options)
                async def callback(self, si):
                    for uid in self.values:
                        member = interaction.guild.get_member(int(uid))
                        if member:
                            await channel.set_permissions(member, view_channel=True, connect=True)
                    resp = await si.response.send_message("✅ Permisos actualizados.", ephemeral=True)
                    asyncio.create_task(auto_delete_msg(resp, 120))
            view = discord.ui.View(timeout=60)
            view.add_item(AllowSelect())
            msg = await interaction.followup.send("Selecciona usuarios:", view=view, ephemeral=True)
            asyncio.create_task(auto_delete_msg(msg, 120))
        except asyncio.TimeoutError:
            msg = await interaction.followup.send("⏰ Tiempo agotado.", ephemeral=True)
            asyncio.create_task(auto_delete_msg(msg, 120))

    @discord.ui.button(label="Despermitir", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="vc_disallow")
    async def disallow(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message("❌ No eres dueño de ninguna sala activa.", ephemeral=True)

        allowed = [m for m, o in channel.overwrites.items() if isinstance(m, discord.Member) and (o.connect or o.view_channel)]
        if not allowed:
            return await interaction.response.send_message("⚠️ No hay usuarios permitidos.", ephemeral=True)
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in allowed[:25]]
        class DisallowSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="Selecciona quién quitar", min_values=1, max_values=len(options), options=options)
            async def callback(self, si):
                for uid in self.values:
                    member = interaction.guild.get_member(int(uid))
                    if member:
                        await channel.set_permissions(member, overwrite=None)
                resp = await si.response.send_message("🚫 Acceso retirado.", ephemeral=True)
                asyncio.create_task(auto_delete_msg(resp, 120))
        view = discord.ui.View(timeout=60)
        view.add_item(DisallowSelect())
        msg = await interaction.response.send_message("Selecciona usuarios:", view=view, ephemeral=True)
        asyncio.create_task(auto_delete_msg(msg, 120))

    @discord.ui.button(label="Expulsar", style=discord.ButtonStyle.danger, emoji="👢", custom_id="vc_kick")
    async def kick(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message("❌ No eres dueño de ninguna sala activa.", ephemeral=True)
        members = [m for m in channel.members if not m.bot and m != interaction.user]
        if not members:
            return await interaction.response.send_message("⚠️ No hay usuarios para expulsar.", ephemeral=True)
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        class KickSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="Selecciona a quién expulsar", min_values=1, max_values=len(options), options=options)
            async def callback(self, si):
                for uid in self.values:
                    member = interaction.guild.get_member(int(uid))
                    if member:
                        await member.move_to(None)
                resp = await si.response.send_message("👢 Usuarios expulsados.", ephemeral=True)
                asyncio.create_task(auto_delete_msg(resp, 120))
        view = discord.ui.View(timeout=60)
        view.add_item(KickSelect())
        msg = await interaction.response.send_message("Selecciona miembros:", view=view, ephemeral=True)
        asyncio.create_task(auto_delete_msg(msg, 120))

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
# SLASH COMMAND: /panel
# ======================
@bot.tree.command(name="panel", description="Recrear manualmente el panel")
async def panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Solo los administradores pueden usar esto.", ephemeral=True)
    await setup_panel()
    await interaction.response.send_message("✅ Panel recreado correctamente.", ephemeral=True)

# ======================
# SINCRONIZAR COMANDOS
# ======================
@bot.tree.command(name="sync", description="Forzar sincronización global de comandos")
async def sync(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"✅ Se sincronizaron {len(synced)} comandos globales", ephemeral=True)

# ======================
# EVENTO READY
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
    print(f"🤖 Conectado como {bot.user}")

# ======================
# INICIO
# ======================
bot.run(os.getenv("TOKEN"))





