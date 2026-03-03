import discord
from discord.ext import commands, tasks
import asyncio
import sqlite3
from datetime import datetime, timedelta
from database import is_admin
from config import OWNER_ID

RESET_DAYS = 10


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_mutes.start()
        self.check_global_reset.start()

    # ---------------- DATABASE INIT ---------------- #

    def init_db(self):
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS punishments (
            guild_id INTEGER,
            user_id INTEGER,
            moderator_id INTEGER,
            type TEXT,
            reason TEXT,
            end_time TEXT,
            timestamp TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)

        conn.commit()
        conn.close()

    # ---------------- ADMIN CHECK ---------------- #

    def check_admin(self, ctx):
        return ctx.author.id == OWNER_ID or is_admin(ctx.guild.id, ctx.author.id)

    # ---------------- WARN ---------------- #

    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, reason="Belirtilmedi"):
        if not self.check_admin(ctx):
            return await ctx.send("❌ Yetkin yok.")

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        cursor.execute("""
        INSERT INTO punishments VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ctx.guild.id, member.id, ctx.author.id, "WARN", reason, None, now))

        conn.commit()

        cursor.execute("""
        SELECT COUNT(*) FROM punishments
        WHERE guild_id=? AND user_id=? AND type='WARN'
        """, (ctx.guild.id, member.id))

        warn_count = cursor.fetchone()[0]
        conn.close()

        await ctx.send(f"⚠️ {member.mention} uyarıldı. (Toplam Warn: {warn_count})")

        # Warn Rolleri Güncelle
        await self.update_warn_roles(member, warn_count)

        # 3 Warn = 10 dk mute
        if warn_count == 3:
            await self.apply_mute(ctx.guild, member, 600, "3 Warn Ceza")

        # 5 Warn = Yönetim Bildirim
        if warn_count == 5:
            kanal = discord.utils.get(ctx.guild.text_channels, name="uyarı")
            if kanal:
                embed = discord.Embed(
                    title="🚨 5 WARN UYARISI",
                    color=discord.Color.red()
                )
                embed.add_field(name="Kullanıcı", value=member.mention)
                embed.add_field(name="Sebep", value=reason)
                embed.add_field(name="Toplam Warn", value=str(warn_count))
                embed.add_field(name="Yetkili", value=ctx.author.mention)
                await kanal.send(embed=embed)

    # ---------------- MUTE ---------------- #

    async def apply_mute(self, guild, member, seconds, reason):
        muted_role = discord.utils.get(guild.roles, name="Muted")
        if not muted_role:
            return

        await member.add_roles(muted_role)

        end_time = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO punishments VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (guild.id, member.id, self.bot.user.id, "MUTE", reason, end_time, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

    @tasks.loop(seconds=30)
    async def check_mutes(self):
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute("""
        SELECT guild_id, user_id, end_time FROM punishments
        WHERE type='MUTE' AND end_time IS NOT NULL
        """)

        rows = cursor.fetchall()

        for guild_id, user_id, end_time in rows:
            if datetime.utcnow() >= datetime.fromisoformat(end_time):
                guild = self.bot.get_guild(guild_id)
                if guild:
                    member = guild.get_member(user_id)
                    muted_role = discord.utils.get(guild.roles, name="Muted")
                    if member and muted_role and muted_role in member.roles:
                        await member.remove_roles(muted_role)

                cursor.execute("""
                DELETE FROM punishments
                WHERE guild_id=? AND user_id=? AND type='MUTE'
                """, (guild_id, user_id))

        conn.commit()
        conn.close()

    # ---------------- WARN ROLLERİ ---------------- #

    async def update_warn_roles(self, member, warn_count):
        guild = member.guild

        # Tüm warn rollerini sil
        for i in range(1, 6):
            role = discord.utils.get(guild.roles, name=f"warn {i}")
            if role and role in member.roles:
                await member.remove_roles(role)

        # Yeni warn rolü ver
        if 1 <= warn_count <= 5:
            role = discord.utils.get(guild.roles, name=f"warn {warn_count}")
            if role:
                await member.add_roles(role)

    # ---------------- GLOBAL RESET ---------------- #

    @tasks.loop(hours=1)
    async def check_global_reset(self):
        self.init_db()

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM system WHERE key='reset_time'")
        row = cursor.fetchone()

        if not row:
            next_reset = (datetime.utcnow() + timedelta(days=RESET_DAYS)).isoformat()
            cursor.execute("INSERT OR REPLACE INTO system VALUES (?,?)", ("reset_time", next_reset))
            conn.commit()
            conn.close()
            return

        reset_time = datetime.fromisoformat(row[0])

        if datetime.utcnow() >= reset_time:
            for guild in self.bot.guilds:

                # Roller Temizle
                for member in guild.members:
                    for i in range(1, 6):
                        role = discord.utils.get(guild.roles, name=f"warn {i}")
                        if role and role in member.roles:
                            await member.remove_roles(role)

                    muted_role = discord.utils.get(guild.roles, name="Muted")
                    if muted_role and muted_role in member.roles:
                        await member.remove_roles(muted_role)

                # Kanallara Duyuru
                embed = discord.Embed(
                    title="♻ CEZA SİSTEMİ RESETLENDİ",
                    description="Sunucu genelindeki tüm warn ve cezalar otomatik olarak sıfırlandı.",
                    color=discord.Color.green()
                )

                uyari = discord.utils.get(guild.text_channels, name="uyarı")
                duyuru = discord.utils.get(guild.text_channels, name="duyurular")

                if uyari:
                    await uyari.send(embed=embed)
                if duyuru:
                    await duyuru.send(embed=embed)

            # DB Temizle
            cursor.execute("DELETE FROM punishments")
            next_reset = (datetime.utcnow() + timedelta(days=RESET_DAYS)).isoformat()
            cursor.execute("INSERT OR REPLACE INTO system VALUES (?,?)", ("reset_time", next_reset))

        conn.commit()
        conn.close()

    # ---------------- SİCİL ---------------- #

    @commands.command()
    async def sicil(self, ctx, member: discord.Member):
        if not self.check_admin(ctx):
            return await ctx.send("❌ Yetkin yok.")

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute("""
        SELECT type, reason, timestamp FROM punishments
        WHERE guild_id=? AND user_id=?
        ORDER BY timestamp DESC
        """, (ctx.guild.id, member.id))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return await ctx.send("🧾 Bu kullanıcının sicili temiz.")

        embed = discord.Embed(
            title=f"🧾 {member.display_name} Sicil",
            color=discord.Color.orange()
        )

        embed.description = f"Toplam Ceza: {len(rows)}"

        for type_, reason, timestamp in rows[:10]:
            time_obj = datetime.fromisoformat(timestamp)
            unix = int(time_obj.timestamp())
            embed.add_field(
                name=type_,
                value=f"Sebep: {reason}\nTarih: <t:{unix}:R>",
                inline=False
            )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
