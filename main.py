import discord
from discord.ext import commands
from discord import app_commands
import os
import json

# ======================
# CONFIGURACIÓN DE INTENTS
# ======================
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ======================
# CONFIGURACIÓN GENERAL
# ======================
WELCOME_CHANNEL_ID = 1254534174430199888
TEMP_VOICE_CREATOR_ID = 1425009175489937408  # Canal base de voz
TEMP_PANEL_CHANNEL_ID = 1425026451677384744  # Canal de texto donde va el panel
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

        await member.move_to(new_channel)

        TEMP_CHANNELS[new_channel.id] = member.id
        save_temp_channels()

    if before.channel and before.channel.id in TEMP_CHANNELS:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            TEMP_CHANNELS.pop(before.channel.id, None)
            save_temp_channels()

# ======================
# PANEL DE CONTROL DE VOZ
# ======================
class VoicePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def validate_owner(self, interaction: discord.Interaction):
        if not interaction.user.voice or interaction.user.voice.channel.id not in TEMP_CHANNELS:
            await interaction.response.send_message("❌ No estás en un canal temporal.", ephemeral=True)
            return None
        channel = interaction.user.voice.channel
        owner_id = TEMP_CHANNELS[channel.id]
        if owner_id != interaction.user.id:
            await interaction.response.send_message("🚫 Solo el dueño del canal puede usar este panel.", ephemeral=True)
            return None
        return channel

    # ======================
    # BOTONES
    # ======================
    @discord.ui.button(label="Cambiar nombre", style=discord.ButtonStyle.primary, emoji="📝", custom_id="rename_btn")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        await interaction.response.send_message("✏️ Escribe el nuevo nombre del canal:", ephemeral=True)

        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            await channel.edit(name=msg.content)
            await msg.delete()
            await interaction.followup.send(f"✅ Canal renombrado a **{msg.content}**", ephemeral=True)
        except Exception:
            await interaction.followup.send("⏰ Tiempo agotado, intenta de nuevo.", ephemeral=True)

    @discord.ui.button(label="Privacidad", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="privacy_btn")
    async def privacy(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        perms = channel.overwrites_for(interaction.guild.default_role)
        locked = perms.connect is False
        await channel.set_permissions(interaction.guild.default_role, connect=locked)
        estado = "🔓 Público" if locked else "🔒 Privado"
        await interaction.response.send_message(f"✅ Tu canal ahora es **{estado}**", ephemeral=True)

    @discord.ui.button(label="Permitir", style=discord.ButtonStyle.success, emoji="✅", custom_id="allow_btn")
    async def allow(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in interaction.guild.members if not m.bot
        ][:25]

        class AllowSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="Selecciona miembros para permitir acceso",
                    min_values=1,
                    max_values=len(options),
                    options=options,
                    custom_id="allow_select"
                )

            async def callback(self, select_interaction: discord.Interaction):
                for uid in self.values:
                    user = interaction.guild.get_member(int(uid))
                    await channel.set_permissions(user, connect=True, view_channel=True)
                await select_interaction.response.send_message("✅ Permisos actualizados.", ephemeral=True)

        view = discord.ui.View(timeout=60)
        view.add_item(AllowSelect())
        await interaction.response.send_message("Selecciona usuarios para permitir acceso:", view=view, ephemeral=True)

    @discord.ui.button(label="Quitar acceso", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="disallow_btn")
    async def disallow(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        allowed = [
            o for o in channel.overwrites
            if isinstance(o, discord.Member) and channel.overwrites[o].connect
        ]
        options = [discord.SelectOption(label=u.display_name, value=str(u.id)) for u in allowed][:25]
        if not options:
            return await interaction.response.send_message("⚠️ No hay usuarios con permisos especiales.", ephemeral=True)

        class DisallowSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="Selecciona miembros para quitar acceso",
                    min_values=1,
                    max_values=len(options),
                    options=options,
                    custom_id="disallow_select"
                )

            async def callback(self, select_interaction: discord.Interaction):
                for uid in self.values:
                    user = interaction.guild.get_member(int(uid))
                    await channel.set_permissions(user, overwrite=None)
                await select_interaction.response.send_message("🚫 Acceso retirado.", ephemeral=True)

        view = discord.ui.View(timeout=60)
        view.add_item(DisallowSelect())
        await interaction.response.send_message("Selecciona usuarios para quitar acceso:", view=view, ephemeral=True)

    @discord.ui.button(label="Mutear", style=discord.ButtonStyle.primary, emoji="🔇", custom_id="mute_btn")
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        members = [m for m in channel.members if not m.bot and m != interaction.user]
        if not members:
            return await interaction.response.send_message("⚠️ No hay usuarios en tu canal.", ephemeral=True)

        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members][:25]

        class MuteSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="Selecciona usuarios para mutear",
                    min_values=1,
                    max_values=len(options),
                    options=options,
                    custom_id="mute_select"
                )

            async def callback(self, select_interaction: discord.Interaction):
                for uid in self.values:
                    user = interaction.guild.get_member(int(uid))
                    await user.edit(mute=True)
                await select_interaction.response.send_message("🔇 Usuarios muteados.", ephemeral=True)

        view = discord.ui.View(timeout=60)
        view.add_item(MuteSelect())
        await interaction.response.send_message("Selecciona usuarios para mutear:", view=view, ephemeral=True)

    @discord.ui.button(label="Expulsar", style=discord.ButtonStyle.danger, emoji="👢", custom_id="kick_btn")
    async def kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        members = [m for m in channel.members if not m.bot and m != interaction.user]
        if not members:
            return await interaction.response.send_message("⚠️ No hay usuarios en tu canal.", ephemeral=True)

        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members][:25]

        class KickSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="Selecciona usuarios para expulsar",
                    min_values=1,
                    max_values=len(options),
                    options=options,
                    custom_id="kick_select"
                )

            async def callback(self, select_interaction: discord.Interaction):
                for uid in self.values:
                    user = interaction.guild.get_member(int(uid))
                    await user.move_to(None)
                await select_interaction.response.send_message("👢 Usuarios expulsados.", ephemeral=True)

        view = discord.ui.View(timeout=60)
        view.add_item(KickSelect())
        await interaction.response.send_message("Selecciona usuarios para expulsar:", view=view, ephemeral=True)

# ======================
# EVENTO: on_ready
# ======================
@bot.event
async def on_ready():
    global TEMP_CHANNELS
    TEMP_CHANNELS.update(load_temp_channels())

    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos sincronizados.")
    except Exception as e:
        print(f"❌ Error al sincronizar: {e}")

    print(f"🤖 Conectado como {bot.user}")

    # Mantener el panel activo
    bot.add_view(VoicePanel())

    # Crear panel visual si no existe
    channel = bot.get_channel(TEMP_PANEL_CHANNEL_ID)
    if channel:
        async for msg in channel.history(limit=10):
            if msg.author == bot.user and msg.components:
                break
        else:
            embed = discord.Embed(
                title="🎛️ Panel de control de salas temporales",
                description=(
                    "Crea una sala uniéndote al canal de voz base.\n\n"
                    "**Desde aquí puedes:**\n"
                    "📝 Cambiar el nombre de tu sala.\n"
                    "🔒 Hacerla privada o pública.\n"
                    "✅ Permitir acceso a usuarios.\n"
                    "🚫 Quitar acceso a usuarios.\n"
                    "🔇 Mutear miembros dentro de tu canal.\n"
                    "👢 Expulsar miembros del canal.\n\n"
                    "⚙️ *Solo el dueño del canal puede usar estos controles.*"
                ),
                color=discord.Color.blurple()
            )
            embed.set_footer(text="🎧 Sistema TemVoice Plus | by CesarBot")
            await channel.send(embed=embed, view=VoicePanel())

# ======================
# COMANDOS BÁSICOS
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
# INICIO
# ======================
bot.run(os.getenv("TOKEN"))






