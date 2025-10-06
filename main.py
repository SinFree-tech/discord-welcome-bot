import discord
from discord.ext import commands
from discord import app_commands
import os

# ======================
# INTENTS (necesarios para bienvenida y moderación)
# ======================
intents = discord.Intents.default()
intents.members = True  # habilitar detección de joins

# Crear bot
bot = commands.Bot(command_prefix="!", intents=intents)

# ======================
# CONFIGURACIÓN
# ======================
WELCOME_CHANNEL_ID = 1254534174430199888  # 👈 tu canal de bienvenida

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
                f"Contigo somos **{member.guild.member_count}** <a:dinnoo:1370259875132866650>\n\n"
                "📜 No olvides leer las reglas y conseguir tus roles 🎭"
            ),
            color=discord.Color.green()
        )

        # Accesos directos en campos
        embed.add_field(
            name="📢 Reglas",
            value="<#1253936573716762708>",
            inline=True
        )
        embed.add_field(
            name="🎲 Roles",
            value="<#1273266265405919284>",
            inline=True
        )

        # Avatar del nuevo miembro como miniatura
        embed.set_thumbnail(url=member.display_avatar.url)

        # Pie de página bonito
        embed.set_footer(text="Nos alegra tenerte con nosotros 🦁")

        await canal.send(embed=embed)

# ======================
# SLASH COMMAND: /bienvenida
# ======================
@bot.tree.command(name="bienvenida", description="El bot te da un saludo de bienvenida")
async def bienvenida(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"👋 ¡Hola {interaction.user.mention}! Bienvenido al servidor 🦁"
    )

# ======================
# SLASH COMMAND: /info
# ======================
@bot.tree.command(name="info", description="Muestra información del servidor")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"📌 Servidor: {interaction.guild.name}\n👥 Miembros: {interaction.guild.member_count}"
    )

# ======================
# SLASH COMMAND: /ban
# ======================
@bot.tree.command(name="ban", description="Banea a un miembro y le envía un DM con la razón")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(
    member="El usuario que quieres banear",
    reason="La razón del baneo"
)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No se especificó razón"
):
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

    # Confirmación en el chat
    await interaction.response.send_message(
        f"🚨 {member.mention} fue baneado. Razón: {reason}"
    )

# ======================
# SLASH COMMAND: /sync
# ======================
@bot.tree.command(name="sync", description="Forza la sincronización de comandos")
async def sync(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(
        f"✅ Se sincronizaron {len(synced)} comandos globales",
        ephemeral=True
    )

# ======================
# EVENTO: on_ready → registrar comandos globalmente
# ======================
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()  # 🔥 Global sync
        print(f"✅ Se sincronizaron {len(synced)} comandos globales")
    except Exception as e:
        print(f"❌ Error al sincronizar: {e}")

    print(f"Bot conectado como {bot.user}")

# ======================
# INICIO DEL BOT
# ======================
bot.run(os.getenv("TOKEN"))



