import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import asyncpg

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

# ======================
# CONEXIÓN A LA BASE DE DATOS
# ======================
async def init_db():
    bot.db = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await bot.db.execute("""
        CREATE TABLE IF NOT EXISTS temp_channels (
            channel_id BIGINT PRIMARY KEY,
            owner_id BIGINT
        )
    """)

async def save_channel(channel_id, owner_id):
    await bot.db.execute("""
        INSERT INTO temp_channels (channel_id, owner_id)
        VALUES ($1, $2)
        ON CONFLICT (channel_id) DO UPDATE SET owner_id = EXCLUDED.owner_id
    """, channel_id, owner_id)

async def delete_channel(channel_id):
    await bot.db.execute("DELETE FROM temp_channels WHERE channel_id = $1", channel_id)

async def load_channels():
    rows = await bot.db.fetch("SELECT channel_id, owner_id FROM temp_channels")
    return {str(r["channel_id"]): {"owner_id": r["owner_id"]} for r in rows}

data = {}

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
                f"👋 ¡Nos alegra tenerte en **{member.guild.name}**!\n\n"
                f"Contigo somos **{member.guild.member_count}** <a:dinnoo:1370259875132866650>\n\n"
                "📜 No olvides leer las reglas y conseguir tus roles 🎭"
            ),
            color=discord.Color.green()
        )
        embed.add_field(name="📢 Reglas", value="<#1253936573716762708>", inline=True)
        embed.add_field(name="🎲 Roles", value="<#1273266265405919284>", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Las sombras se agitan… un nuevo león despierta en NoMercy 🦁")

        await canal.send(content=f"👋 ¡Bienvenido {member.mention}! 🎉", embed=embed)

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
    global data
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
        await save_channel(new_channel.id, member.id)

    if before.channel and str(before.channel.id) in data:
        if len(before.channel.members) == 0:
            try:
                del data[str(before.channel.id)]
                await delete_channel(before.channel.id)
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

    # 📝 BOTÓN: Cambiar nombre del canal
    @discord.ui.button(label="Nombre", style=discord.ButtonStyle.primary, emoji="📝", custom_id="vc_rename")
    async def rename(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message("❌ No eres dueño de ninguna sala activa.", ephemeral=True)
        
        await interaction.response.send_message("✏️ Escribe el nuevo nombre (60s):", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            new_name = msg.content[:100]
            await msg.delete()
            await channel.edit(name=new_name)
            await asyncio.sleep(1)
            await channel.purge(limit=100)
            await interaction.followup.send(f"✅ Nombre cambiado a **{new_name}**", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Tiempo agotado.", ephemeral=True)

    # 🔒 BOTÓN: Privacidad
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
            await interaction.response.send_message("🔓 Canal abierto para todos.", ephemeral=True)
        else:
            await channel.set_permissions(everyone, view_channel=True, connect=False)
            await channel.set_permissions(interaction.user, view_channel=True, connect=True)
            await interaction.response.send_message("🔒 Canal bloqueado (visible pero sin acceso).", ephemeral=True)

    # ✅ BOTÓN: Permitir acceso
    @discord.ui.button(label="Permitir", style=discord.ButtonStyle.success, emoji="✅", custom_id="vc_allow")
    async def allow(self, interaction: discord.Interaction, _):
        channel = await self.get_owned_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message("❌ No eres dueño de ninguna sala activa.", ephemeral=True)

        await interaction.response.send_message("🔍 Escribe el nombre o ID del usuario (60s):", ephemeral=True)
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            query = msg.content.lower().strip()
            await msg.delete()
            await asyncio.sleep(1)
            await channel.purge(limit=100)

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
                    await si.response.send_message("✅ Permisos actualizados.", ephemeral=True)

            view = discord.ui.View(timeout=60)
            view.add_item(AllowSelect())
            await interaction.followup.send("Selecciona usuarios:", view=view, ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Tiempo agotado.", ephemeral=True)

    # 🚫 BOTÓN: Despermitir acceso
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
                await asyncio.sleep(1)
                await channel.purge(limit=100)
                await si.response.send_message("🚫 Acceso retirado.", ephemeral=True)

        view = discord.ui.View(timeout=60)
        view.add_item(DisallowSelect())
        await interaction.response.send_message("Selecciona usuarios:", view=view, ephemeral=True)

    # 👢 BOTÓN: Expulsar miembros
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
                await si.response.send_message("👢 Usuarios expulsados.", ephemeral=True)

        view = discord.ui.View(timeout=60)
        view.add_item(KickSelect())
        await interaction.response.send_message("Selecciona miembros:", view=view, ephemeral=True)

# ======================
# DB TEST
# ======================
@bot.tree.command(name="dbtest", description="Verifica la conexión a la base de datos")
async def dbtest(interaction: discord.Interaction):
    try:
        result = await bot.db.fetch("SELECT 1;")
        await interaction.response.send_message("✅ Conectado correctamente a PostgreSQL.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error en la conexión:\n```{e}```", ephemeral=True)

# ======================
# RESTAURAR CANALES
# ======================
async def restore_temp_channels():
    global data
    await bot.wait_until_ready()
    guild = bot.guilds[0]
    data = await load_channels()
    to_delete = []
    for ch_id, info in data.items():
        ch = guild.get_channel(int(ch_id))
        if ch is None:
            to_delete.append(ch_id)
    for ch_id in to_delete:
        del data[ch_id]
        await delete_channel(int(ch_id))
    if to_delete:
        print(f"🧹 Eliminados {len(to_delete)} registros huérfanos.")
    print("🔁 Restauración completada. Canales activos recordados correctamente.")

# ======================
# PANEL AUTOMÁTICO
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
# ADMIN
# ======================
@bot.tree.command(name="panel", description="Recrear manualmente el panel")
async def panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Solo los administradores pueden usar esto.", ephemeral=True)
    await setup_panel()
    await interaction.response.send_message("✅ Panel recreado correctamente.", ephemeral=True)

@bot.tree.command(name="sync", description="Forzar sincronización global de comandos")
async def sync(interaction: discord.Interaction):
    synced = await bot.tree.sync()
    await interaction.response.send_message(f"✅ Se sincronizaron {len(synced)} comandos globales", ephemeral=True)

# ======================
# READY
# ======================
@bot.event
async def on_ready():
    await init_db()
    global data
    data = await load_channels()
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
# RUN
# ======================
bot.run(os.getenv("TOKEN"))
