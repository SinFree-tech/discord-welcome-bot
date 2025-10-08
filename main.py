import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os

# ======================
# INTENTS
# ======================
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ======================
# CONFIGURACIÓN GENERAL
# ======================
WELCOME_CHANNEL_ID = 1254534174430199888
VOICE_CREATOR_ID = 1425009175489937408
PANEL_CHANNEL_ID = 1425026451677384744

# ======================
# FUNCIONES AUXILIARES
# ======================
async def ephemeral_response(interaction, content=None, embed=None, view=None):
    """Envía mensaje efímero y lo borra después de 2 min"""
    await interaction.response.send_message(
        content=content, embed=embed, view=view, ephemeral=True
    )
    await asyncio.sleep(120)
    try:
        await interaction.delete_original_response()
    except:
        pass


async def followup_response(interaction, content=None, embed=None, view=None):
    """Envía respuesta de seguimiento efímera y la borra después de 2 min"""
    msg = await interaction.followup.send(
        content=content, embed=embed, view=view if view else None, ephemeral=True
    )
    await asyncio.sleep(120)
    try:
        await msg.delete()
    except:
        pass

# ======================
# BIENVENIDA
# ======================
@bot.event
async def on_member_join(member):
    canal = bot.get_channel(WELCOME_CHANNEL_ID)
    if canal:
        embed = discord.Embed(
            title="🎉 ¡Nuevo miembro en la familia!",
            description=(
                f"👋 Bienvenido {member.mention} a **{member.guild.name}**!\n\n"
                f"Contigo somos **{member.guild.member_count}** 🦁\n\n"
                "📜 No olvides leer las reglas y conseguir tus roles 🎭"
            ),
            color=discord.Color.green(),
        )
        embed.add_field(name="📢 Reglas", value="<#1253936573716762708>", inline=True)
        embed.add_field(name="🎲 Roles", value="<#1273266265405919284>", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Nos alegra tenerte con nosotros 🦁")
        await canal.send(embed=embed)

# ======================
# COMANDOS /bienvenida /info /ban /sync
# ======================
@bot.tree.command(name="bienvenida", description="El bot te da un saludo de bienvenida")
async def bienvenida(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"👋 ¡Hola {interaction.user.mention}! Bienvenido al servidor 🦁"
    )


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
            color=discord.Color.red(),
        )
        embed.set_footer(text="Si crees que fue un error, contacta con los admins.")
        await member.send(embed=embed)
    except:
        pass

    await member.ban(reason=reason)
    await interaction.response.send_message(f"🚨 {member.mention} fue baneado. Razón: {reason}")


@bot.tree.command(name="sync", description="Forza la sincronización de comandos")
async def sync(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(
        f"✅ Se sincronizaron {len(synced)} comandos globales", ephemeral=True
    )

# ======================
# SISTEMA DE CANALES TEMPORALES
# ======================
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == VOICE_CREATOR_ID:
        guild = member.guild
        category = after.channel.category
        channel_name = f"🎧│{member.display_name}"

        new_channel = await guild.create_voice_channel(
            name=channel_name,
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True),
                member: discord.PermissionOverwrite(manage_channels=True, connect=True, mute_members=True),
            },
        )
        await member.move_to(new_channel)

        bot.temp_channels = getattr(bot, "temp_channels", {})
        bot.temp_channels[member.id] = new_channel.id

    if before.channel and before.channel.id in getattr(bot, "temp_channels", {}).values():
        if len(before.channel.members) == 0:
            await before.channel.delete()

# ======================
# PANEL DE CONTROL DE CANALES
# ======================
class VoicePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # Cambiar nombre
    @discord.ui.button(label="Nombre", style=discord.ButtonStyle.primary, emoji="📝")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_channel_id = getattr(bot, "temp_channels", {}).get(interaction.user.id)
        if not owner_channel_id:
            return await ephemeral_response(interaction, "❌ No eres dueño de ningún canal temporal.")
        channel = interaction.guild.get_channel(owner_channel_id)
        await ephemeral_response(interaction, "✏️ Escribe el nuevo nombre (60s):")

        try:
            msg = await bot.wait_for(
                "message",
                timeout=60,
                check=lambda m: m.author == interaction.user and isinstance(m.channel, discord.TextChannel),
            )
            await channel.edit(name=f"🎧│{msg.content}")
            await msg.delete()
            await followup_response(interaction, f"✅ Nombre cambiado a **{msg.content}**.")
        except asyncio.TimeoutError:
            await followup_response(interaction, "⏰ Tiempo agotado, intenta de nuevo.")

    # Privacidad (candado)
    @discord.ui.button(label="Privacidad", style=discord.ButtonStyle.secondary, emoji="🔒")
    async def privacy(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_channel_id = getattr(bot, "temp_channels", {}).get(interaction.user.id)
        if not owner_channel_id:
            return await ephemeral_response(interaction, "❌ No eres dueño de ningún canal temporal.")

        channel = interaction.guild.get_channel(owner_channel_id)
        current = channel.overwrites_for(interaction.guild.default_role)
        locked = current.connect is False

        if locked:
            await channel.set_permissions(interaction.guild.default_role, connect=True, view_channel=True)
            await followup_response(interaction, "🔓 Canal abierto para todos.")
        else:
            await channel.set_permissions(interaction.guild.default_role, connect=False, view_channel=True)
            await followup_response(interaction, "🔒 Canal bloqueado (visible, pero sin acceso).")

    # Permitir acceso
    @discord.ui.button(label="Permitir", style=discord.ButtonStyle.success, emoji="✅")
    async def allow(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_channel_id = getattr(bot, "temp_channels", {}).get(interaction.user.id)
        if not owner_channel_id:
            return await ephemeral_response(interaction, "❌ No eres dueño de ningún canal temporal.")
        channel = interaction.guild.get_channel(owner_channel_id)

        options = [
            discord.SelectOption(label=member.display_name, value=str(member.id))
            for member in interaction.guild.members[:25]
            if not member.bot
        ]

        class AllowMenu(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.select(placeholder="Selecciona miembros para permitir acceso", min_values=1, max_values=len(options), options=options)
            async def select_callback(self, select_interaction: discord.Interaction, select):
                for user_id in select.values:
                    user = interaction.guild.get_member(int(user_id))
                    await channel.set_permissions(user, connect=True, view_channel=True)
                await followup_response(select_interaction, "✅ Permisos otorgados correctamente.")

        await ephemeral_response(interaction, "Selecciona miembros para permitir acceso:", view=AllowMenu())

    # Quitar permisos
    @discord.ui.button(label="Despermitir", style=discord.ButtonStyle.danger, emoji="🚫")
    async def disallow(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_channel_id = getattr(bot, "temp_channels", {}).get(interaction.user.id)
        if not owner_channel_id:
            return await ephemeral_response(interaction, "❌ No eres dueño de ningún canal temporal.")
        channel = interaction.guild.get_channel(owner_channel_id)

        allowed_users = [p for p in channel.overwrites if isinstance(p, discord.Member) and channel.overwrites[p].connect]
        if not allowed_users:
            return await ephemeral_response(interaction, "⚠️ No hay usuarios con permisos personalizados.")

        options = [discord.SelectOption(label=u.display_name, value=str(u.id)) for u in allowed_users]

        class DisallowMenu(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.select(placeholder="Selecciona miembros para quitar acceso", min_values=1, max_values=len(options), options=options)
            async def select_callback(self, select_interaction: discord.Interaction, select):
                for user_id in select.values:
                    user = interaction.guild.get_member(int(user_id))
                    await channel.set_permissions(user, overwrite=None)
                await followup_response(select_interaction, "🚫 Permisos retirados correctamente.")

        await ephemeral_response(interaction, "Selecciona miembros para quitar acceso:", view=DisallowMenu())

# ======================
# ON_READY (panel automático)
# ======================
@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.add_view(VoicePanel())

    # Enviar el panel automáticamente al canal asignado
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🎧 Panel de control TemVoice Plus",
            description="Primero crea una sala uniéndote a este canal: <#1425009175489937408>",
            color=discord.Color.blurple(),
        )
        await channel.purge(limit=5)  # Limpia mensajes antiguos del canal de panel
        await channel.send(embed=embed, view=VoicePanel())

    print("✅ 5 comandos sincronizados correctamente.")
    print(f"🤖 Conectado como {bot.user}")

# ======================
# RUN
# ======================
bot.run(os.getenv("TOKEN"))










