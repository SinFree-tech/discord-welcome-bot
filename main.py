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

temvoice_data = load_data()

# ======================
# UTILIDAD: envío temporal (sin DM)
# ======================
async def send_temporary(interaction: discord.Interaction, content: str = None, embed: discord.Embed = None, view: discord.ui.View = None, delete_after: int = 120):
    try:
        if not interaction.response.is_done():
            msg = await interaction.response.send_message(content=content, embed=embed, view=view)
        else:
            msg = await interaction.followup.send(content=content, embed=embed, view=view)

        if delete_after:
            async def _deleter():
                await asyncio.sleep(delete_after)
                try:
                    original = await interaction.original_response()
                    await original.delete()
                except:
                    pass
            asyncio.create_task(_deleter())
        return msg
    except Exception as e:
        traceback.print_exc()
        return None

async def send_error(interaction: discord.Interaction, message: str):
    await send_temporary(interaction, content=f"❌ {message}", delete_after=10)

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
class RenameModal(discord.ui.Modal, title="Cambiar nombre del canal"):
    new_name = discord.ui.TextInput(label="Nuevo nombre", placeholder="Introduce el nuevo nombre", max_length=100)

    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.channel.edit(name=self.new_name.value)
            await send_temporary(interaction, f"✅ Nombre cambiado a **{self.new_name.value}**", delete_after=10)
        except Exception as e:
            await send_error(interaction, f"Error al cambiar nombre: {e}")

class VoicePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Nombre", style=discord.ButtonStyle.primary, emoji="📝", custom_id="vc_rename")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_id = str(interaction.user.id)
        if owner_id not in temvoice_data:
            return await send_error(interaction, "No tienes una sala activa.")
        channel = interaction.guild.get_channel(temvoice_data[owner_id]["channel_id"])
        if not channel:
            return await send_error(interaction, "No encontré tu canal.")
        await interaction.response.send_modal(RenameModal(channel))

    @discord.ui.button(label="Privacidad", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="vc_privacy")
    async def privacy(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_id = str(interaction.user.id)
        if owner_id not in temvoice_data:
            return await send_error(interaction, "No tienes una sala activa.")
        channel = interaction.guild.get_channel(temvoice_data[owner_id]["channel_id"])
        if not channel:
            return await send_error(interaction, "No encontré tu canal.")

        current = channel.overwrites_for(interaction.guild.default_role)
        locked = current.connect is False

        if locked:
            await channel.set_permissions(interaction.guild.default_role, connect=True, view_channel=True)
            temvoice_data[owner_id]["locked"] = False
            save_data(temvoice_data)
            await send_temporary(interaction, "🔓 Canal desbloqueado.", delete_after=10)
        else:
            await channel.set_permissions(interaction.guild.default_role, connect=False, view_channel=True)
            temvoice_data[owner_id]["locked"] = True
            save_data(temvoice_data)
            await send_temporary(interaction, "🔒 Canal bloqueado.", delete_after=10)

# ======================
# COMANDOS
# ======================
@bot.tree.command(name="panel", description="Muestra o recrea el panel de control.")
async def panel_cmd(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await send_temporary(interaction, "❌ Solo administradores pueden usar este comando.", delete_after=10)
    channel = bot.get_channel(TEXT_PANEL_CHANNEL_ID)
    if not channel:
        return await send_temporary(interaction, "No se encontró el canal de panel.", delete_after=10)

    embed = discord.Embed(title="🎛️ Panel de control de salas", description=f"Únete a <#{VOICE_CREATION_CHANNEL_ID}> para crear tu sala.", color=discord.Color.blurple())
    embed.add_field(name="📝 Nombre", value="Cambia el nombre de tu canal.", inline=False)
    embed.add_field(name="🔒 Privacidad", value="Bloquea o desbloquea tu canal.", inline=False)

    await channel.send(embed=embed, view=VoicePanel())
    await send_temporary(interaction, "✅ Panel creado.", delete_after=8)

# ======================
# EVENTO DE VOZ
# ======================
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    try:
        if after.channel and after.channel.id == VOICE_CREATION_CHANNEL_ID:
            guild = member.guild
            category = after.channel.category
            new_channel = await guild.create_voice_channel(name=f"🔊 {member.display_name}", category=category)
            await new_channel.set_permissions(guild.default_role, view_channel=True, connect=True)
            await member.move_to(new_channel)
            temvoice_data[str(member.id)] = {"channel_id": new_channel.id, "locked": False}
            save_data(temvoice_data)

        if before.channel and before.channel.id != VOICE_CREATION_CHANNEL_ID:
            for owner_id, info in list(temvoice_data.items()):
                if info.get("channel_id") == before.channel.id:
                    if len(before.channel.members) == 0:
                        await before.channel.delete()
                        del temvoice_data[owner_id]
                        save_data(temvoice_data)
                    break
    except Exception:
        traceback.print_exc()

# ======================
# ON_READY
# ======================
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception as e:
        print("Error sincronizando comandos:", e)
    bot.add_view(VoicePanel())
    print(f"Conectado como {bot.user}")

# ======================
# RUN
# ======================
if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if not token:
        print("Error: falta variable de entorno TOKEN")
    else:
        bot.run(token)









