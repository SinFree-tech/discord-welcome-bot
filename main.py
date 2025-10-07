import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import asyncio
import json

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# IDs configurables
TEXT_PANEL_CHANNEL_ID = 1425026451677384744
VOICE_CREATION_CHANNEL_ID = 1425009175489937408

# Archivo para guardar datos persistentes
DATA_FILE = "temvoice_data.json"


# ---------------------- FUNCIONES DE APOYO ----------------------

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


data = load_data()


async def auto_delete_msg(msg, delay=120):
    """Elimina el mensaje después de cierto tiempo si sigue existiendo"""
    try:
        await asyncio.sleep(delay)
        await msg.delete()
    except:
        pass


# ---------------------- CONFIGURACIÓN DEL BOT ----------------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------- EVENTO DE INICIO ----------------------

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🤖 Conectado como {bot.user}")
    print("✅ Comandos sincronizados.")

    await setup_panel()
    bot.add_view(VoicePanel())  # Persistencia del panel tras reinicios


# ---------------------- CREAR EL PANEL ----------------------

async def setup_panel():
    await bot.wait_until_ready()
    channel = bot.get_channel(TEXT_PANEL_CHANNEL_ID)
    if not channel:
        print("❌ No se encontró el canal del panel.")
        return

    async for msg in channel.history(limit=10):
        if msg.author == bot.user:
            await msg.delete()

    embed = discord.Embed(
        title="🎛️ Panel de control de salas temporales",
        description=(
            "Primero crea una sala uniéndote a este canal: <#1425009175489937408>\n\n"
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

    view = VoicePanel()
    await channel.send(embed=embed, view=view)


# ---------------------- CLASE DEL PANEL ----------------------

class VoicePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def validate_owner(self, interaction: discord.Interaction):
        for ch_id, info in data.items():
            if info["owner_id"] == interaction.user.id:
                channel = interaction.guild.get_channel(int(ch_id))
                return channel
        msg = await interaction.response.send_message("❌ No eres dueño de ninguna sala activa.", ephemeral=True)
        return None

    # Cambiar nombre
    @discord.ui.button(label="Nombre", style=discord.ButtonStyle.primary, emoji="📝", custom_id="rename_btn")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        msg = await interaction.response.send_message("✏️ Escribe el nuevo nombre para tu canal:", ephemeral=True)
        asyncio.create_task(auto_delete_msg(await interaction.original_response()))

        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            user_msg = await bot.wait_for("message", check=check, timeout=60)
            await channel.edit(name=user_msg.content)
            await user_msg.delete()
            follow = await interaction.followup.send(f"✅ Nombre actualizado a **{user_msg.content}**", ephemeral=True)
            asyncio.create_task(auto_delete_msg(follow))
        except asyncio.TimeoutError:
            follow = await interaction.followup.send("⏰ Tiempo agotado. Intenta de nuevo.", ephemeral=True)
            asyncio.create_task(auto_delete_msg(follow))

    # Privacidad
    @discord.ui.button(label="Privacidad", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="privacy_btn")
    async def privacy(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        overwrites = channel.overwrites
        everyone = interaction.guild.default_role
        locked = overwrites.get(everyone, None)

        if locked and locked.view_channel is False:
            overwrites[everyone].view_channel = True
            await channel.edit(overwrites=overwrites)
            msg = await interaction.response.send_message("🔓 Canal ahora es **público**.", ephemeral=True)
        else:
            overwrites[everyone] = discord.PermissionOverwrite(view_channel=False)
            overwrites[interaction.user] = discord.PermissionOverwrite(view_channel=True, connect=True)
            await channel.edit(overwrites=overwrites)
            msg = await interaction.response.send_message("🔒 Canal ahora es **privado**.", ephemeral=True)
        asyncio.create_task(auto_delete_msg(await interaction.original_response()))

    # ✅ Permitir usuarios (búsqueda)
    @discord.ui.button(label="Permitir", style=discord.ButtonStyle.success, emoji="✅", custom_id="allow_btn")
    async def allow(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        first_msg = await interaction.response.send_message(
            "🔍 Escribe el nombre o ID del usuario al que quieres permitir acceso:",
            ephemeral=True
        )
        asyncio.create_task(auto_delete_msg(await interaction.original_response()))

        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            query = msg.content.lower()
            matches = [
                m for m in interaction.guild.members
                if not m.bot and (query in m.display_name.lower() or query in m.name.lower() or query in str(m.id))
            ]
            await msg.delete()

            if not matches:
                follow = await interaction.followup.send("❌ No encontré usuarios con ese nombre o ID.", ephemeral=True)
                asyncio.create_task(auto_delete_msg(follow))
                return

            matches = matches[:25]
            options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in matches]

            class AllowSelect(discord.ui.Select):
                def __init__(self):
                    super().__init__(
                        placeholder="Selecciona usuarios para permitir acceso",
                        min_values=1,
                        max_values=len(options),
                        options=options,
                        custom_id="allow_select"
                    )

                async def callback(self, select_interaction: discord.Interaction):
                    for uid in self.values:
                        user = interaction.guild.get_member(int(uid))
                        await channel.set_permissions(user, connect=True, view_channel=True)
                    resp = await select_interaction.response.send_message("✅ Permisos actualizados.", ephemeral=True)
                    asyncio.create_task(auto_delete_msg(await select_interaction.original_response()))

            view = discord.ui.View(timeout=60)
            view.add_item(AllowSelect())
            follow = await interaction.followup.send("Selecciona los usuarios a los que darás acceso:", view=view, ephemeral=True)
            asyncio.create_task(auto_delete_msg(follow))

        except Exception:
            follow = await interaction.followup.send("⏰ Tiempo agotado. Intenta de nuevo.", ephemeral=True)
            asyncio.create_task(auto_delete_msg(follow))

    # 🚫 Quitar acceso
    @discord.ui.button(label="Despermitir", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="deny_btn")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        allowed_users = [
            m for m, perm in channel.overwrites.items()
            if isinstance(m, discord.Member) and perm.view_channel
        ]
        if not allowed_users:
            msg = await interaction.response.send_message("No hay usuarios con permiso actualmente.", ephemeral=True)
            asyncio.create_task(auto_delete_msg(await interaction.original_response()))
            return

        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in allowed_users]
        view = discord.ui.View(timeout=60)

        class DenySelect(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="Selecciona usuarios para quitar acceso",
                    min_values=1,
                    max_values=len(options),
                    options=options,
                    custom_id="deny_select"
                )

            async def callback(self, select_interaction: discord.Interaction):
                for uid in self.values:
                    user = interaction.guild.get_member(int(uid))
                    await channel.set_permissions(user, overwrite=None)
                resp = await select_interaction.response.send_message("🚫 Acceso eliminado.", ephemeral=True)
                asyncio.create_task(auto_delete_msg(await select_interaction.original_response()))

        view.add_item(DenySelect())
        msg = await interaction.response.send_message("Selecciona a quién quitar acceso:", view=view, ephemeral=True)
        asyncio.create_task(auto_delete_msg(await interaction.original_response()))

    # 🔇 Mutear usuarios
    @discord.ui.button(label="Mutear", style=discord.ButtonStyle.danger, emoji="🔇", custom_id="mute_btn")
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        members = channel.members
        if not members:
            msg = await interaction.response.send_message("No hay miembros en tu canal.", ephemeral=True)
            asyncio.create_task(auto_delete_msg(await interaction.original_response()))
            return

        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        view = discord.ui.View(timeout=60)

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
                resp = await select_interaction.response.send_message("🔇 Usuarios muteados.", ephemeral=True)
                asyncio.create_task(auto_delete_msg(await select_interaction.original_response()))

        view.add_item(MuteSelect())
        msg = await interaction.response.send_message("Selecciona a quién mutear:", view=view, ephemeral=True)
        asyncio.create_task(auto_delete_msg(await interaction.original_response()))

    # 👢 Expulsar
    @discord.ui.button(label="Expulsar", style=discord.ButtonStyle.secondary, emoji="👢", custom_id="kick_btn")
    async def kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self.validate_owner(interaction)
        if not channel:
            return

        members = channel.members
        if not members:
            msg = await interaction.response.send_message("No hay miembros en tu canal.", ephemeral=True)
            asyncio.create_task(auto_delete_msg(await interaction.original_response()))
            return

        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members]
        view = discord.ui.View(timeout=60)

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
                resp = await select_interaction.response.send_message("👢 Usuarios expulsados del canal.", ephemeral=True)
                asyncio.create_task(auto_delete_msg(await select_interaction.original_response()))

        view.add_item(KickSelect())
        msg = await interaction.response.send_message("Selecciona a quién expulsar:", view=view, ephemeral=True)
        asyncio.create_task(auto_delete_msg(await interaction.original_response()))


# ---------------------- CREACIÓN AUTOMÁTICA DE SALAS ----------------------

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == VOICE_CREATION_CHANNEL_ID:
        guild = member.guild
        category = after.channel.category

        new_channel = await guild.create_voice_channel(
            name=f"🔊 {member.display_name}",
            category=category
        )
        await member.move_to(new_channel)

        data[str(new_channel.id)] = {"owner_id": member.id}
        save_data(data)

    if before.channel and str(before.channel.id) in data:
        if len(before.channel.members) == 0:
            del data[str(before.channel.id)]
            save_data(data)
            await before.channel.delete()


# ---------------------- COMANDOS ----------------------

@bot.tree.command(name="vc", description="Ver tus canales temporales activos")
async def vc(interaction: discord.Interaction):
    owned = [cid for cid, info in data.items() if info["owner_id"] == interaction.user.id]
    if not owned:
        msg = await interaction.response.send_message("No tienes canales activos.", ephemeral=True)
        asyncio.create_task(auto_delete_msg(await interaction.original_response()))
        return

    channels = [f"<#{cid}>" for cid in owned]
    msg = await interaction.response.send_message(f"Tus canales: {', '.join(channels)}", ephemeral=True)
    asyncio.create_task(auto_delete_msg(await interaction.original_response()))


# ---------------------- EJECUCIÓN ----------------------

bot.run(TOKEN)





