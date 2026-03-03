import discord
from discord.ext import commands, tasks
import sqlite3
import datetime
import asyncio
from config import OWNER_ID

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

# ================= CONFIG =================

PREFIX = "!"
WARNING_CHANNEL_NAME = "uyarı"
MUTE_ROLE_NAME = "Muted"
GLOBAL_RESET_DAYS = 10

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ================= DATABASE ENGINE =================

class Database:

    def __init__(self):
        self.conn = sqlite3.connect("ultra_moderation.db")
        self.cursor = self.conn.cursor()
        self.setup()

    def setup(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS warns (
            guild_id INTEGER,
            user_id INTEGER,
            moderator_id INTEGER,
            reason TEXT,
            timestamp TEXT
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS mutes (
            guild_id INTEGER,
            user_id INTEGER,
            end_time TEXT
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            guild_id INTEGER,
            user_id INTEGER
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS reset_timer (
            guild_id INTEGER,
            next_reset TEXT
        )
        """)

        self.conn.commit()

    def execute(self, query, params=()):
        self.cursor.execute(query, params)
        self.conn.commit()

    def fetchall(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def fetchone(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchone()


db = Database()

# ================= EMBED ENGINE =================

class UltraEmbed:

    @staticmethod
    def progress_bar(current, total=5):
        filled = int((current / total) * 10)
        return "█" * filled + "░" * (10 - filled)

    @staticmethod
    def warn_color(level):
        if level <= 2:
            return discord.Color.gold()
        elif level == 3:
            return discord.Color.orange()
        elif level == 4:
            return discord.Color.red()
        else:
            return discord.Color.dark_red()

    @staticmethod
    def base(title, description=None, color=discord.Color.blurple()):
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.timestamp = datetime.datetime.utcnow()
        embed.set_footer(text="Ultra Elite Moderation System • 2026")
        return embed

# ================= PERMISSION SYSTEM =================

class PermissionSystem:

    @staticmethod
    def is_admin(guild_id, user_id):
        if user_id == OWNER_ID:
            return True

        result = db.fetchone(
            "SELECT * FROM admins WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )

        return result is not None

# ================= HELPER FUNCTIONS =================

async def get_mute_role(guild):
    role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)

    if not role:
        role = await guild.create_role(name=MUTE_ROLE_NAME)

        for channel in guild.channels:
            await channel.set_permissions(role, send_messages=False, speak=False)

    return role

def get_warn_count(guild_id, user_id):
    result = db.fetchone(
        "SELECT COUNT(*) FROM warns WHERE guild_id=? AND user_id=?",
        (guild_id, user_id)
    )
    return result[0] if result else 0

async def update_warn_roles(member, count):
    for i in range(1, 6):
        role = discord.utils.get(member.guild.roles, name=f"Warn {i}")
        if role and role in member.roles:
            await member.remove_roles(role)

    if 1 <= count <= 5:
        role = discord.utils.get(member.guild.roles, name=f"Warn {count}")
        if role:
            await member.add_roles(role)

# ================= AUTO TASKS =================

@tasks.loop(seconds=30)
async def mute_loop():

    now = datetime.datetime.utcnow()

    rows = db.fetchall("SELECT guild_id, user_id, end_time FROM mutes")

    for guild_id, user_id, end_time in rows:

        guild = bot.get_guild(guild_id)
        if not guild:
            continue

        member = guild.get_member(user_id)
        if not member:
            continue

        end_time_obj = datetime.datetime.fromisoformat(end_time)

        if now >= end_time_obj:

            role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
            if role and role in member.roles:
                await member.remove_roles(role)

            db.execute(
                "DELETE FROM mutes WHERE guild_id=? AND user_id=?",
                (guild_id, user_id)
            )

@tasks.loop(hours=1)
async def global_reset_loop():

    now = datetime.datetime.utcnow()

    rows = db.fetchall("SELECT guild_id, next_reset FROM reset_timer")

    for guild_id, next_reset in rows:

        guild = bot.get_guild(guild_id)
        if not guild:
            continue

        reset_time = datetime.datetime.fromisoformat(next_reset)

        if now >= reset_time:
            await global_reset(guild)

async def global_reset(guild):

    db.execute("DELETE FROM warns WHERE guild_id=?", (guild.id,))
    db.execute("DELETE FROM mutes WHERE guild_id=?", (guild.id,))

    for member in guild.members:

        for i in range(1, 6):
            role = discord.utils.get(guild.roles, name=f"Warn {i}")
            if role and role in member.roles:
                await member.remove_roles(role)

        mute_role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
        if mute_role and mute_role in member.roles:
            await member.remove_roles(mute_role)

    embed = UltraEmbed.base(
        "♻ GLOBAL CEZA SİSTEMİ RESETLENDİ",
        "Tüm warn ve mute kayıtları sıfırlandı.",
        discord.Color.green()
    )

    for channel_name in ["uyarı", "duyurular"]:
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel:
            await channel.send(embed=embed)

    next_reset = datetime.datetime.utcnow() + datetime.timedelta(days=GLOBAL_RESET_DAYS)

    db.execute(
        "DELETE FROM reset_timer WHERE guild_id=?",
        (guild.id,)
    )

    db.execute(
        "INSERT INTO reset_timer VALUES (?,?)",
        (guild.id, next_reset.isoformat())
    )

@bot.event
async def on_ready():
    print(f"{bot.user} Ultra Elite System Aktif.")
    mute_loop.start()
    global_reset_loop.start()
# ================= ADMIN MANAGEMENT =================

@bot.command()
async def admin_ekle(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID:
        return

    db.execute(
        "INSERT INTO admins VALUES (?,?)",
        (ctx.guild.id, member.id)
    )

    embed = UltraEmbed.base(
        "👑 ADMIN EKLENDİ",
        f"{member.mention} artık admin yetkisine sahip.",
        discord.Color.green()
    )
    await ctx.send(embed=embed)


@bot.command()
async def admin_sil(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID:
        return

    db.execute(
        "DELETE FROM admins WHERE guild_id=? AND user_id=?",
        (ctx.guild.id, member.id)
    )

    embed = UltraEmbed.base(
        "❌ ADMIN KALDIRILDI",
        f"{member.mention} adminlikten çıkarıldı.",
        discord.Color.red()
    )
    await ctx.send(embed=embed)


@bot.command()
async def admin_list(ctx):
    rows = db.fetchall(
        "SELECT user_id FROM admins WHERE guild_id=?",
        (ctx.guild.id,)
    )

    if not rows:
        return await ctx.send("Admin bulunamadı.")

    desc = ""
    for r in rows:
        member = ctx.guild.get_member(r[0])
        if member:
            desc += f"• {member.mention}\n"

    embed = UltraEmbed.base(
        "📋 ADMIN LİSTESİ",
        desc,
        discord.Color.blurple()
    )

    await ctx.send(embed=embed)

# ================= WARN SYSTEM =================

@bot.command()
async def warn(ctx, member: discord.Member, *, reason="Sebep belirtilmedi"):
    if not PermissionSystem.is_admin(ctx.guild.id, ctx.author.id):
        return

    db.execute(
        "INSERT INTO warns VALUES (?,?,?,?,?)",
        (
            ctx.guild.id,
            member.id,
            ctx.author.id,
            reason,
            datetime.datetime.utcnow().isoformat()
        )
    )

    count = get_warn_count(ctx.guild.id, member.id)
    await update_warn_roles(member, count)

    embed = UltraEmbed.base(
        f"⚠ WARN VERİLDİ ({count}/5)",
        f"👤 Kullanıcı: {member.mention}\n"
        f"🛡 Moderator: {ctx.author.mention}\n"
        f"📌 Sebep: {reason}\n\n"
        f"{UltraEmbed.progress_bar(count)}",
        UltraEmbed.warn_color(count)
    )

    await ctx.send(embed=embed)

    # 3 WARN = 10 DK MUTE
    if count == 3:
        await apply_mute(ctx, member, 10, "3 Warn Otomatik Mute")

    # 5 WARN = UYARI KANALINA MESAJ
    if count == 5:
        channel = discord.utils.get(ctx.guild.text_channels, name=WARNING_CHANNEL_NAME)
        if channel:
            warn_embed = UltraEmbed.base(
                "🚨 5 WARN ULAŞILDI",
                f"{member.mention} 5 warn oldu.\nYönetim dikkat.",
                discord.Color.dark_red()
            )
            await channel.send(embed=warn_embed)


@bot.command()
async def sicil(ctx, member: discord.Member = None):
    member = member or ctx.author

    rows = db.fetchall(
        "SELECT moderator_id, reason, timestamp FROM warns WHERE guild_id=? AND user_id=?",
        (ctx.guild.id, member.id)
    )

    count = len(rows)

    if count == 0:
        return await ctx.send("Temiz sicil.")

    desc = f"Toplam Warn: {count}\n\n"

    for mod_id, reason, ts in rows[-5:]:
        mod = ctx.guild.get_member(mod_id)
        desc += f"• {reason} | {mod.mention if mod else 'Bilinmiyor'}\n"

    embed = UltraEmbed.base(
        f"📄 SİCİL - {member}",
        desc,
        UltraEmbed.warn_color(count)
    )

    await ctx.send(embed=embed)


@bot.command()
async def warn_sil(ctx, member: discord.Member, adet: int):
    if not PermissionSystem.is_admin(ctx.guild.id, ctx.author.id):
        return

    rows = db.fetchall(
        "SELECT rowid FROM warns WHERE guild_id=? AND user_id=?",
        (ctx.guild.id, member.id)
    )

    if not rows:
        return await ctx.send("Warn yok.")

    for r in rows[:adet]:
        db.execute("DELETE FROM warns WHERE rowid=?", (r[0],))

    count = get_warn_count(ctx.guild.id, member.id)
    await update_warn_roles(member, count)

    embed = UltraEmbed.base(
        "🗑 WARN SİLİNDİ",
        f"{adet} warn silindi.\nYeni warn sayısı: {count}",
        discord.Color.green()
    )

    await ctx.send(embed=embed)

# ================= MUTE SYSTEM =================

async def apply_mute(ctx, member, minutes, reason):

    role = await get_mute_role(ctx.guild)
    await member.add_roles(role)

    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes)

    db.execute(
        "INSERT OR REPLACE INTO mutes VALUES (?,?,?)",
        (ctx.guild.id, member.id, end_time.isoformat())
    )

    embed = UltraEmbed.base(
        "🔇 MUTE UYGULANDI",
        f"{member.mention} susturuldu.\n"
        f"Süre: {minutes} dakika\n"
        f"Sebep: {reason}",
        discord.Color.red()
    )

    await ctx.send(embed=embed)


@bot.command()
async def mute(ctx, member: discord.Member, dakika: int, *, reason="Sebep belirtilmedi"):
    if not PermissionSystem.is_admin(ctx.guild.id, ctx.author.id):
        return

    await apply_mute(ctx, member, dakika, reason)


@bot.command()
async def unmute(ctx, member: discord.Member):
    if not PermissionSystem.is_admin(ctx.guild.id, ctx.author.id):
        return

    role = discord.utils.get(ctx.guild.roles, name=MUTE_ROLE_NAME)
    if role and role in member.roles:
        await member.remove_roles(role)

    db.execute(
        "DELETE FROM mutes WHERE guild_id=? AND user_id=?",
        (ctx.guild.id, member.id)
    )

    embed = UltraEmbed.base(
        "🔊 UNMUTE",
        f"{member.mention} susturması kaldırıldı.",
        discord.Color.green()
    )

    await ctx.send(embed=embed)


@bot.command()
async def ceza_temizle(ctx, member: discord.Member):
    if not PermissionSystem.is_admin(ctx.guild.id, ctx.author.id):
        return

    db.execute(
        "DELETE FROM warns WHERE guild_id=? AND user_id=?",
        (ctx.guild.id, member.id)
    )

    db.execute(
        "DELETE FROM mutes WHERE guild_id=? AND user_id=?",
        (ctx.guild.id, member.id)
    )

    await update_warn_roles(member, 0)

    role = discord.utils.get(ctx.guild.roles, name=MUTE_ROLE_NAME)
    if role and role in member.roles:
        await member.remove_roles(role)

    embed = UltraEmbed.base(
        "♻ CEZA SİSTEMİ TEMİZLENDİ",
        f"{member.mention} tüm cezaları silindi.",
        discord.Color.green()
    )

    await ctx.send(embed=embed)
# ================= ULTRA DASHBOARD =================

@bot.command()
async def dashboard(ctx):
    if not PermissionSystem.is_admin(ctx.guild.id, ctx.author.id):
        return

    total_warns = db.fetchone(
        "SELECT COUNT(*) FROM warns WHERE guild_id=?",
        (ctx.guild.id,)
    )[0]

    total_mutes = db.fetchone(
        "SELECT COUNT(*) FROM mutes WHERE guild_id=?",
        (ctx.guild.id,)
    )[0]

    admin_count = len(db.fetchall(
        "SELECT user_id FROM admins WHERE guild_id=?",
        (ctx.guild.id,)
    ))

    members_with_warn = len(set([row[0] for row in db.fetchall(
        "SELECT user_id FROM warns WHERE guild_id=?",
        (ctx.guild.id,)
    )]))

    embed = UltraEmbed.base(
        "📊 ULTRA MODERATION DASHBOARD",
        color=discord.Color.dark_blue()
    )

    embed.add_field(name="⚠ Toplam Warn", value=f"```{total_warns}```", inline=True)
    embed.add_field(name="🔇 Aktif Mute", value=f"```{total_mutes}```", inline=True)
    embed.add_field(name="👑 Admin Sayısı", value=f"```{admin_count}```", inline=True)
    embed.add_field(name="👥 Warnlı Üye", value=f"```{members_with_warn}```", inline=True)

    embed.add_field(
        name="♻ Global Reset",
        value=f"{GLOBAL_RESET_DAYS} günde bir otomatik sıfırlanır.",
        inline=False
    )

    await ctx.send(embed=embed)

# ================= YETKİLİ CEZA İSTATİSTİK =================

@bot.command()
async def yetkili(ctx, member: discord.Member = None):
    if not PermissionSystem.is_admin(ctx.guild.id, ctx.author.id):
        return

    member = member or ctx.author

    warn_count = len(db.fetchall(
        "SELECT * FROM warns WHERE guild_id=? AND moderator_id=?",
        (ctx.guild.id, member.id)
    ))

    embed = UltraEmbed.base(
        f"🛡 YETKİLİ PERFORMANS PANELİ",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="👤 Yetkili",
        value=member.mention,
        inline=False
    )

    embed.add_field(
        name="⚠ Verilen Warn",
        value=f"```{warn_count}```",
        inline=True
    )

    embed.add_field(
        name="📈 Aktivite Seviyesi",
        value="Yüksek" if warn_count >= 5 else "Orta" if warn_count >= 2 else "Düşük",
        inline=True
    )

    await ctx.send(embed=embed)

# ================= SUNUCU CEZA LİDERLİK =================

@bot.command()
async def liderlik(ctx):
    if not PermissionSystem.is_admin(ctx.guild.id, ctx.author.id):
        return

    rows = db.fetchall(
        "SELECT moderator_id, COUNT(*) FROM warns WHERE guild_id=? GROUP BY moderator_id ORDER BY COUNT(*) DESC",
        (ctx.guild.id,)
    )

    if not rows:
        return await ctx.send("Veri yok.")

    desc = ""
    for i, row in enumerate(rows[:5], start=1):
        member = ctx.guild.get_member(row[0])
        if member:
            desc += f"**{i}.** {member.mention} → {row[1]} warn\n"

    embed = UltraEmbed.base(
        "🏆 YETKİLİ CEZA LİDERLİĞİ",
        desc,
        discord.Color.gold()
    )

    await ctx.send(embed=embed)

# ================= AKTİF MUTE LİSTESİ =================

@bot.command()
async def mutelist(ctx):
    if not PermissionSystem.is_admin(ctx.guild.id, ctx.author.id):
        return

    rows = db.fetchall(
        "SELECT user_id, end_time FROM mutes WHERE guild_id=?",
        (ctx.guild.id,)
    )

    if not rows:
        return await ctx.send("Aktif mute yok.")

    desc = ""
    now = datetime.datetime.utcnow()

    for user_id, end_time in rows:
        member = ctx.guild.get_member(user_id)
        if member:
            end = datetime.datetime.fromisoformat(end_time)
            kalan = int((end - now).total_seconds() / 60)
            desc += f"• {member.mention} → {kalan} dk kaldı\n"

    embed = UltraEmbed.base(
        "🔇 AKTİF MUTE LİSTESİ",
        desc,
        discord.Color.red()
    )

    await ctx.send(embed=embed)

# ================= SİSTEM DURUM =================

@bot.command()
async def sistem(ctx):
    embed = UltraEmbed.base(
        "🧠 ULTRA SYSTEM STATUS",
        f"""
Prefix: {PREFIX}
Warn Limit: 5
Auto Mute: 3 Warn → 10 dk
Global Reset: {GLOBAL_RESET_DAYS} gün
Warning Kanal: #{WARNING_CHANNEL_NAME}
Mute Rol: {MUTE_ROLE_NAME}
""",
        discord.Color.green()
    )

    await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot))
