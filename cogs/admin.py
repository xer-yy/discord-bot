import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime, timedelta
from config import OWNER_ID

DB = "bot.db"


# ================= DATABASE =================

def db():
    return sqlite3.connect(DB)


def setup_db():
    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS punishments(
        guild_id INTEGER,
        user_id INTEGER,
        moderator_id INTEGER,
        type TEXT,
        reason TEXT,
        timestamp TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS mutes(
        guild_id INTEGER,
        user_id INTEGER,
        end_time TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS admins(
        guild_id INTEGER,
        user_id INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS reset_timer(
        guild_id INTEGER,
        next_reset TEXT
    )
    """)

    conn.commit()
    conn.close()


# ================= COG =================

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        setup_db()
        self.mute_loop.start()
        self.reset_loop.start()

    # ---------- ADMIN CHECK ----------

    def is_admin(self, guild_id, user_id):
        if user_id == OWNER_ID:
            return True
        conn = db()
        c = conn.cursor()
        c.execute("SELECT * FROM admins WHERE guild_id=? AND user_id=?",
                  (guild_id, user_id))
        result = c.fetchone()
        conn.close()
        return result is not None

    # ---------- WARN COUNT ----------

    def warn_count(self, guild_id, user_id):
        conn = db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM punishments WHERE guild_id=? AND user_id=? AND type='WARN'",
                  (guild_id, user_id))
        count = c.fetchone()[0]
        conn.close()
        return count

    # ---------- WARN ROLE UPDATE ----------

    async def update_warn_roles(self, member, count):
        for i in range(1, 6):
            role = discord.utils.get(member.guild.roles, name=f"Warn {i}")
            if role and role in member.roles:
                await member.remove_roles(role)

        if 1 <= count <= 5:
            role = discord.utils.get(member.guild.roles, name=f"Warn {count}")
            if role:
                await member.add_roles(role)

    # ================= WARN =================

    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, reason="Belirtilmedi"):
        if not self.is_admin(ctx.guild.id, ctx.author.id):
            return await ctx.send("❌ Yetkin yok.")

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        conn = db()
        c = conn.cursor()
        c.execute("INSERT INTO punishments VALUES (?,?,?,?,?,?)",
                  (ctx.guild.id, member.id, ctx.author.id, "WARN", reason, now))
        conn.commit()
        conn.close()

        count = self.warn_count(ctx.guild.id, member.id)
        await self.update_warn_roles(member, count)

        await ctx.send(f"⚠ {member.mention} warn aldı. Toplam: {count}")

        if count == 3:
            await self.apply_mute(ctx.guild, member, 600, "3 WARN Otomatik Mute")

        if count == 5:
            kanal = discord.utils.get(ctx.guild.text_channels, name="uyarı")
            if kanal:
                embed = discord.Embed(
                    title="🚨 5 WARN UYARISI",
                    description=f"{member.mention} 5 warn aldı!\nSebep: {reason}",
                    color=discord.Color.red()
                )
                await kanal.send(embed=embed)

    # ================= MUTE =================

    async def apply_mute(self, guild, member, seconds, reason):
        role = discord.utils.get(guild.roles, name="Muted")
        if not role:
            role = await guild.create_role(name="Muted")
            for channel in guild.channels:
                await channel.set_permissions(role, send_messages=False, speak=False)

        await member.add_roles(role)

        end_time = datetime.utcnow() + timedelta(seconds=seconds)

        conn = db()
        c = conn.cursor()
        c.execute("INSERT INTO mutes VALUES (?,?,?)",
                  (guild.id, member.id, end_time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

    @commands.command()
    async def unmute(self, ctx, member: discord.Member):
        if not self.is_admin(ctx.guild.id, ctx.author.id):
            return await ctx.send("❌ Yetkin yok.")

        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if role and role in member.roles:
            await member.remove_roles(role)

        conn = db()
        c = conn.cursor()
        c.execute("DELETE FROM mutes WHERE guild_id=? AND user_id=?",
                  (ctx.guild.id, member.id))
        conn.commit()
        conn.close()

        await ctx.send("🔊 Unmute edildi.")

    # ================= SICIL =================

    @commands.command()
    async def sicil(self, ctx, member: discord.Member):
        if not self.is_admin(ctx.guild.id, ctx.author.id):
            return await ctx.send("❌ Yetkin yok.")

        conn = db()
        c = conn.cursor()
        c.execute("""
        SELECT type, reason, timestamp
        FROM punishments
        WHERE guild_id=? AND user_id=?
        ORDER BY timestamp DESC
        """, (ctx.guild.id, member.id))

        rows = c.fetchall()
        conn.close()

        if not rows:
            return await ctx.send("🧾 Sicil temiz.")

        embed = discord.Embed(title=f"{member.display_name} Sicil",
                              color=discord.Color.orange())

        for r in rows[:15]:
            embed.add_field(name=f"{r[0]} | {r[2]}",
                            value=f"Sebep: {r[1]}",
                            inline=False)

        await ctx.send(embed=embed)

    # ================= ADMIN SYSTEM =================

    @commands.command()
    async def adminekle(self, ctx, member: discord.Member):
        if ctx.author.id != OWNER_ID:
            return await ctx.send("❌ Sadece bot sahibi.")

        conn = db()
        c = conn.cursor()
        c.execute("INSERT INTO admins VALUES (?,?)",
                  (ctx.guild.id, member.id))
        conn.commit()
        conn.close()

        await ctx.send("✅ Admin eklendi.")

    @commands.command()
    async def adminsil(self, ctx, member: discord.Member):
        if ctx.author.id != OWNER_ID:
            return await ctx.send("❌ Sadece bot sahibi.")

        conn = db()
        c = conn.cursor()
        c.execute("DELETE FROM admins WHERE guild_id=? AND user_id=?",
                  (ctx.guild.id, member.id))
        conn.commit()
        conn.close()

        await ctx.send("🗑 Admin silindi.")

    @commands.command()
    async def adminliste(self, ctx):
        if ctx.author.id != OWNER_ID:
            return await ctx.send("❌ Sadece bot sahibi.")

        conn = db()
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins WHERE guild_id=?",
                  (ctx.guild.id,))
        rows = c.fetchall()
        conn.close()

        text = ""
        for r in rows:
            text += f"<@{r[0]}>\n"

        await ctx.send(f"📋 Adminler:\n{text}")

    # ================= RESET =================

    @commands.command()
    async def resetceza(self, ctx):
        if not self.is_admin(ctx.guild.id, ctx.author.id):
            return await ctx.send("❌ Yetkin yok.")

        await self.global_reset(ctx.guild)
        await ctx.send("♻ Tüm cezalar sıfırlandı.")

    async def global_reset(self, guild):
        conn = db()
        c = conn.cursor()
        c.execute("DELETE FROM punishments WHERE guild_id=?", (guild.id,))
        c.execute("DELETE FROM mutes WHERE guild_id=?", (guild.id,))
        conn.commit()
        conn.close()

        for member in guild.members:
            for i in range(1, 6):
                role = discord.utils.get(guild.roles, name=f"Warn {i}")
                if role and role in member.roles:
                    await member.remove_roles(role)

            mute = discord.utils.get(guild.roles, name="Muted")
            if mute and mute in member.roles:
                await member.remove_roles(mute)

        embed = discord.Embed(title="♻ GLOBAL CEZA RESET",
                              description="Tüm cezalar temizlendi.",
                              color=discord.Color.green())

        for name in ["uyarı", "duyurular"]:
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch:
                await ch.send(embed=embed)

        next_reset = datetime.utcnow() + timedelta(days=10)

        conn = db()
        c = conn.cursor()
        c.execute("DELETE FROM reset_timer WHERE guild_id=?", (guild.id,))
        c.execute("INSERT INTO reset_timer VALUES (?,?)",
                  (guild.id, next_reset.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

    # ================= LOOPS =================

    @tasks.loop(minutes=1)
    async def mute_loop(self):
        await self.bot.wait_until_ready()
        conn = db()
        c = conn.cursor()
        c.execute("SELECT guild_id, user_id, end_time FROM mutes")
        rows = c.fetchall()

        for g, u, end in rows:
            guild = self.bot.get_guild(g)
            if not guild:
                continue
            member = guild.get_member(u)
            if not member:
                continue
            if datetime.utcnow() >= datetime.strptime(end, "%Y-%m-%d %H:%M:%S"):
                role = discord.utils.get(guild.roles, name="Muted")
                if role and role in member.roles:
                    await member.remove_roles(role)
                c.execute("DELETE FROM mutes WHERE guild_id=? AND user_id=?",
                          (g, u))
                conn.commit()

        conn.close()

    @tasks.loop(hours=1)
    async def reset_loop(self):
        await self.bot.wait_until_ready()
        conn = db()
        c = conn.cursor()
        c.execute("SELECT guild_id, next_reset FROM reset_timer")
        rows = c.fetchall()

        for g, time in rows:
            guild = self.bot.get_guild(g)
            if guild and datetime.utcnow() >= datetime.strptime(time, "%Y-%m-%d %H:%M:%S"):
                await self.global_reset(guild)

        conn.close()


async def setup(bot):
    await bot.add_cog(Admin(bot))
