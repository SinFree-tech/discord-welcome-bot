import discord
from discord.ext import commands
from discord import app_commands
import os
import json

# ======================
# INTENTS (necesarios para bienvenida y moderación)
# ======================
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True  # 👈 necesario para detectar entrada/salida de voz

bot = commands.Bot(command_prefix="!", intents=intents)

# ======================
# CONFIGURACIÓN
# ======================
WELCOME_CHANNEL_ID = 1254534174430199888
TEMP_VOICE_CREATOR_ID = 1425009175489937408  # 👈 Canal base para crear salas temporales
TEMP_CHANNELS_FILE = "temp_channels.json"
TEMP_CHANNELS = {}

# ======================
# FUNCIONES DE PERSISTENCIA
# ======================
def load_temp_channels():
    try:
        with open(TEMP_CHANNELS_FILE, "r") as f:
            return {int(k): v for k, v in json.load(f).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_temp_channels():
    with open(TEMP_CHANNELS_FILE, "w") as f:
        json.dump({str(k): v for k, v in TEMP_CHANNELS.items()}, f, indent=4)

# ======================
# EVENTO: on_member_join (bienvenida con embed)
# ======================
@bot.event
async def on_member_join(member):
    canal = bot.get_channel(WELCOME_CHANNEL_ID)
    if canal:
        embed = discord.Embed(
            title="🎉 ¡Nuevo miembro en la familia!",
            description=(
                f"👋 Bienvenido {member.mention} a **{member.guild.name}**!\n\n"
                f"Contigo somos **{member.guild.member_count}** 🎈\n\n"
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
# SISTEMA DE CANALES TEMPORALES
# ======================
@bot.event
async def on_voice_state_update(member, before, after):
    # Crear canal temporal
    if after.channel and after.channel.id == TEMP_VOICE_CREATOR_ID:
        guild = member.guild
        category = after.channel.category

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
            member: discord.PermissionOverwrite(
                connect=True,
                view_channel=True,
                manage_channels=True,
                move_members=True,
                mute_members=True,
            ),
        }

        new_channel = await guild.create_voice_channel(
            name=f"🎧 Sala de {member.display_name}",
            overwrites=overwrites,
            category=category,
        )

        # Mover al usuario al nuevo canal
        await member.move_to(new_channel)

        # Guardar el canal
        TEMP_CHANNELS[new_channel.id] = member.id
        save_temp_channels()

    # Eliminar canal si queda vacío
    if before.channel and before.channel.id in TEMP_CHANNELS:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            TEMP_CHANNELS.pop(before.channel.id, None)
            save_temp_channels()

# ======================
# COMANDOS /vc_* (solo dueño del canal)
# ======================
@bot.tree.command(name="vc_rename", description="Cambia el nombre de tu canal temporal")
@app_commands.describe(nombre="Nuevo nombre del canal")
async def vc_rename(interaction: discord.Interaction, nombre: str):
    channel = interaction.user.voice.channel if interaction.user.voice else None
    if not channel or channel.id not in TEMP_CHANNELS:
        return await interaction.response.send_message("❌ No estás en un canal temporal.", ephemeral=True)
    if TEMP_CHANNELS[channel.id] != interaction.user.id:
        return await interaction.response.send_message("🚫 Solo el dueño del canal puede hacerlo.", ephemeral=True)
    await channel.edit(name=nombre)
    await interaction.response.send_message(f"✅ Canal renombrado a **{nombre}**")

@bot.tree.command(name="vc_lock", description="Haz tu canal temporal privado")
async def vc_lock(interaction: discord.Interaction):
    channel = interaction.user.voice.channel if interaction.user.voice else None
    if not channel or channel.id not in TEMP_CHANNELS:
        return await interaction.response.send_message("❌ No estás en un canal temporal.", ephemeral=True)
    if TEMP_CHANNELS[channel.id] != interaction.user.id:
        return await interaction.response.send_message("🚫 Solo el dueño del canal puede hacerlo.", ephemeral=True)
    await channel.set_permissions(interaction.guild.default_role, connect=False)
    await interaction.response.send_message("🔒 Tu canal ahora es **privado**.")

@bot.tree.command(name="vc_unlock", description="Haz tu canal temporal público")
async def vc_unlock(interaction: discord.Interaction):
    channel = interaction.user.voice.channel if interaction.user.voice else None
    if not channel or channel.id not in TEMP_CHANNELS:
        return await interaction.response.send_message("❌ No estás en un canal temporal.", ephemeral=True)
    if TEMP_CHANNELS[channel.id] != interaction.user.id:
        return await interaction.response.send_message("🚫 Solo el dueño del canal puede hacerlo.", ephemeral=True)
    await channel.set_permissions(interaction.guild.default_role, connect=True)
    await interaction.response.send_message("🔓 Tu canal ahora es **público**.")

@bot.tree.command(name="vc_mute", description="Mutea a un miembro en tu canal temporal")
@app_commands.describe(miembro="Miembro a mutear")
async def vc_mute(interaction: discord.Interaction, miembro: discord.Member):
    channel = interaction.user.voice.channel if interaction.user.voice else None
    if not channel or channel.id not in TEMP_CHANNELS:
        return await interaction.response.send_message("❌ No estás en un canal temporal.", ephemeral=True)
    if TEMP_CHANNELS[channel.id] != interaction.user.id:
        return await interaction.response.send_message("🚫 Solo el dueño del canal puede hacerlo.", ephemeral=True)
    if miembro not in channel.members:
        return await interaction.response.send_message("❌ Ese usuario no está en tu canal.", ephemeral=True)
    await miembro.edit(mute=True)
    await interaction.response.send_message(f"🔇 {miembro.mention} fue muteado.")

@bot.tree.command(name="vc_unmute", description="Desmutea a un miembro en tu canal temporal")
@app_commands.describe(miembro="Miembro a desmutear")
async def vc_unmute(interaction: discord.Interaction, miembro: discord.Member):
    channel = interaction.user.voice.channel if interaction.user.voice else None
    if not channel or channel.id not in TEMP_CHANNELS:
        return await interaction.response.send_message("❌ No estás en un canal temporal.", ephemeral=True)
    if TEMP_CHANNELS[channel.id] != interaction.user.id:
        return await interaction.response.send_message("🚫 Solo el dueño del canal puede hacerlo.", ephemeral=True)
    if miembro not in channel.members:
        return await interaction.response.send_message("❌ Ese usuario no está en tu canal.", ephemeral=True)
    await miembro.edit(mute=False)
    await interaction.response.send_message(f"🔊 {miembro.mention} fue desmuteado.")

# ======================
# OTROS COMANDOS / BÁSICOS
# ======================
@bot.tree.command(name="bienvenida", description="El bot te da un saludo de bienvenida")
async def bienvenida(interaction: discord.Interaction):
    await interaction.response.send_message(f"👋 ¡Hola {interaction.user.mention}! Bienvenido al servidor 🦁")

@bot.tree.command(name="info", description="Muestra información del servidor")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message(f"📌 Servidor: {interaction.guild.name}\n👥 Miembros: {interaction.guild.member_count}")

@bot.tree.command(name="ban", description="Banea a un miembro")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, miembro: discord.Member, razon: str = "No se especificó razón"):
    try:
        await miembro.send(f"Has sido baneado de {interaction.guild.name}. Razón: {razon}")
    except:
        pass
    await miembro.ban(reason=razon)
    await interaction.response.send_message(f"🚨 {miembro.mention} fue baneado. Razón: {razon}")

@bot.tree.command(name="sync", description="Sincroniza los comandos del bot")
async def sync(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"✅ Se sincronizaron {len(synced)} comandos.", ephemeral=True)

# ======================
# EVENTO: on_ready
# ======================
@bot.event
async def on_ready():
    global TEMP_CHANNELS
    loaded = load_temp_channels()
    TEMP_CHANNELS.update(loaded)

    for ch_id in list(TEMP_CHANNELS.keys()):
        if not bot.get_channel(ch_id):
            TEMP_CHANNELS.pop(ch_id, None)
    save_temp_channels()

    try:
        synced = await bot.tree.sync()
        print(f"✅ Se sincronizaron {len(synced)} comandos globales")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")

    print(f"🤖 Bot conectado como {bot.user}")
    print(f"📂 Canales temporales cargados: {len(TEMP_CHANNELS)}")

# ======================
# EJECUCIÓN
# ======================
bot.run(os.getenv("TOKEN"))




