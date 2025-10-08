import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio

# ======================
# CONFIGURACIÓN E INTENTS
# ======================
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ======================
# CONFIGURACIÓN
# ======================
WELCOME_CHANNEL_ID = 1254534174430199888
VOICE_CREATION_CHANNEL_ID = 1425009175489937408
TEXT_PANEL_CHANNEL_ID = 1425026451677384744
DATA_FILE = "temvoice_data.json"

# ======================
# FUNCIONES DE GUARDADO
# ======================
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

temvoice_data = load_data()

# ======================
# RESPUESTAS TEMPORALES
# ======================
async def ephemeral_response(interaction, content=None, embed=None, view=None):
    await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=True)
    await asyncio.sleep(120)
    await interaction.delete_original_response()

async def followup_response(interaction, content=None, embed=None, view=None):
    msg = await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=True)
    await asyncio.sleep(120)
    await msg.delete()

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
# PANEL DE CONTROL DE SALAS
# ======================
class VoicePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Nombre", style=discord.ButtonStyle.primary, emoji="📝", custom_id="rename")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if user_id not in temvoice_data:
            return await ephemeral_response(interaction, "❌ No tienes una sala activa.")
        await ephemeral_response(interaction, "✏️ Escribe el nuevo nombre (tienes 60s):")

        def check(msg): 
            return msg.author == interaction.user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", timeout=60, check=check)
            channel = interaction.guild.get_channel(temvoice_data[user_id]["channel_id"])
            if channel:
                await channel.edit(name=msg.content)
                await followup_response(interaction, f"✅ Nombre cambiado a **{msg.content}**.")
            await msg.delete()
        except asyncio.TimeoutError:
            await followup_response(interaction, "⏰ Tiempo agotado.")

    @discord.ui.button(label="Privacidad", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="privacy")
    async def privacy(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if user_id not in temvoice_data:
            return await ephemeral_response(interaction, "❌ No tienes una sala activa.")
        channel = interaction.guild.get_channel(temvoice_data[user_id]["channel_id"])
        if channel:
            locked = temvoice_data[user_id].get("locked", False)
            if locked:
                await channel.set_permissions(interaction.guild.default_role, connect=True)
                temvoice_data[user_id]["locked"] = False
                await followup_response(interaction, "🔓 Canal abierto para todos.")
            else:
                await channel.set_permissions(interaction.guild.default_role, connect=False, view_channel=True)
                temvoice_data[user_id]["locked"] = True
                await followup_response(interaction, "🔒 Canal bloqueado (visible, pero sin acceso).")
            save_data(temvoice_data)

    @discord.ui.button(label="Permitir", style=discord.ButtonStyle.success, emoji="✅", custom_id="allow")
    async def allow(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if user_id not in temvoice_data:
            return await ephemeral_response(interaction, "❌ No tienes una sala activa.")

        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in interaction.guild.members if not m.bot
        ][:25]

        select = discord.ui.Select(placeholder="Selecciona miembros...", min_values=1, max_values=len(options), options=options, custom_id="allow_select")

        async def select_callback(interaction2: discord.Interaction):
            channel = interaction2.guild.get_channel(temvoice_data[user_id]["channel_id"])
            for user_id_str in select.values:
                member = interaction2.guild.get_member(int(user_id_str))
                if member:
                    await channel.set_permissions(member, connect=True, view_channel=True)
            await followup_response(interaction2, "✅ Permisos actualizados.")
        select.callback = select_callback

        view = discord.ui.View()
        view.add_item(select)
        await ephemeral_response(interaction, "Selecciona miembros para **permitir acceso**:", view=view)

    @discord.ui.button(label="Despermitir", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if user_id not in temvoice_data:
            return await ephemeral_response(interaction, "❌ No tienes una sala activa.")

        channel = interaction.guild.get_channel(temvoice_data[user_id]["channel_id"])
        allowed_members = [m for m in channel.members if m != interaction.user]
        if not allowed_members:
            return await followup_response(interaction, "⚠️ No hay usuarios con permisos actualmente.")

        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in allowed_members]
        select = discord.ui.Select(placeholder="Selecciona miembros para quitar acceso", options=options, custom_id="deny_select")

        async def select_callback(interaction2: discord.Interaction):
            for user_id_str in select.values:
                member = interaction2.guild.get_member(int(user_id_str))
                if member:
                    await channel.set_permissions(member, overwrite=None)
            await followup_response(interaction2, "🚫 Accesos revocados.")
        select.callback = select_callback

        view = discord.ui.View()
        view.add_item(select)
        await ephemeral_response(interaction, "Selecciona miembros para **quitar acceso**:", view=view)

    @discord.ui.button(label="Expulsar", style=discord.ButtonStyle.danger, emoji="💣", custom_id="kick")
    async def kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if user_id not in temvoice_data:
            return await ephemeral_response(interaction, "❌ No tienes una sala activa.")
        channel = interaction.guild.get_channel(temvoice_data[user_id]["channel_id"])
        members_in_channel = [m for m in channel.members if m != interaction.user]
        if not members_in_channel:
            return await followup_response(interaction, "⚠️ No hay usuarios en tu canal.")

        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members_in_channel]
        select = discord.ui.Select(placeholder="Selecciona usuarios para expulsar", options=options, custom_id="kick_select")

        async def select_callback(interaction2: discord.Interaction):
            for user_id_str in select.values:
                member = interaction2.guild.get_member(int(user_id_str))
                if member and member in channel.members:
                    await member.move_to(None)
            await followup_response(interaction2, "💣 Usuarios expulsados.")
        select.callback = select_callback

        view = discord.ui.View()
        view.add_item(select)
        await ephemeral_response(interaction, "Selecciona miembros para **expulsar**:", view=view)

# ======================
# COMANDO /panel
# ======================
@bot.tree.command(name="panel", description="Muestra el panel de control de salas de voz.")
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎧 Panel de control de salas",
        description=f"Primero crea una sala uniéndote a este canal: <#{VOICE_CREATION_CHANNEL_ID}>",
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(embed=embed, view=VoicePanel())

# ======================
# EVENTOS DE CREACIÓN AUTOMÁTICA
# ======================
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == VOICE_CREATION_CHANNEL_ID:
        guild = member.guild
        category = after.channel.category
        new_channel = await guild.create_voice_channel(f"🔊 {member.display_name}", category=category)
        await member.move_to(new_channel)
        temvoice_data[str(member.id)] = {"channel_id": new_channel.id, "locked": False}
        save_data(temvoice_data)

    if before.channel and before.channel.id != VOICE_CREATION_CHANNEL_ID and len(before.channel.members) == 0:
        for owner_id, data in list(temvoice_data.items()):
            if data["channel_id"] == before.channel.id:
                await before.channel.delete()
                del temvoice_data[owner_id]
                save_data(temvoice_data)

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
@app_commands.describe(member="El usuario que quieres banear", reason="La razón del baneo")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No se especificó razón"):
    try:
        embed = discord.Embed(
            title="⛔ Has sido baneado",
            description=f"Servidor: **{interaction.guild.name}**\nRazón: **{reason}**",
            color=discord.Color.red()
        )
        await member.send(embed=embed)
    except:
        pass
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🚨 {member.mention} fue baneado. Razón: {reason}")

@bot.tree.command(name="sync", description="Forza la sincronización de comandos")
async def sync(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"✅ Se sincronizaron {len(synced)} comandos globales", ephemeral=True)

# ======================
# EVENTO READY
# ======================
@bot.event
async def on_ready():
    bot.add_view(VoicePanel())
    print("✅  TemVoice Plus activo y con memoria persistente.")
    print(f"🤖 Conectado como {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos sincronizados correctamente.")
    except Exception as e:
        print(f"❌ Error al sincronizar: {e}")

    # PANEL AUTOMÁTICO (sin duplicar)
    panel_channel = bot.get_channel(TEXT_PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=10):
            if msg.author == bot.user and msg.embeds and "Panel de control de salas" in msg.embeds[0].title:
                print("🔁 Panel ya existe, no se publica otro.")
                return
        embed = discord.Embed(
            title="🎧 Panel de control de salas",
            description=f"Primero crea una sala uniéndote a este canal: <#{VOICE_CREATION_CHANNEL_ID}>",
            color=discord.Color.blurple()
        )
        await panel_channel.send(embed=embed, view=VoicePanel())
        print("✅ Panel publicado automáticamente.")

# ======================
# INICIO DEL BOT
# ======================
bot.run(os.getenv("TOKEN"))







