import discord
from discord.ext import commands
import asyncio
import re
import sqlite3
from datetime import datetime
from database import is_admin, add_punishment
from config import OWNER_ID


def parse_duration(duration_str):
    pattern = r"(\d+)([smhdw])"
    matches = re.findall(pattern, duration_str.lower())

    if not matches:
        return None

    total_seconds = 0

    for value, unit in matches:
        value = int(value)

        if unit == "s":
            total_seconds += value
        elif unit == "m":
            total_seconds += value * 60
        elif unit == "h":
            total_seconds += value * 3600
        elif unit == "d":
            total_seconds += value * 86400
        elif unit == "w":
            total_seconds += value * 604800

    return total_seconds


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def check_admin(self, ctx):
        return ctx.author.id == OWNER_ID or is_admin(ctx.guild.id, ctx.author.id)

    # ---------------- WARN ---------------- #

    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, sebep="Belirtilmedi"):
        if not self.check_admin(ctx):
            return await ctx.send("❌ Yetkin yok.")

        add_punishment(ctx.guild.id, member.id, ctx.author.id, "WARN", sebep)

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM punishments WHERE guild_id = ? AND user_id = ? AND type = 'WARN'",
            (ctx.guild.id, member.id)
        )
        warn_sayisi = cursor.fetchone()[0]
        conn.close()

        await ctx.send(f"⚠️ {member.mention} uyarıldı. (Toplam Warn: {warn_sayisi})")

        # WARN ROLLERİ
        for i in range(1, 6):
            rol = discord.utils.get(ctx.guild.roles, name=f"warn {i}")
            if rol and rol in member.roles:
                await member.remove_roles(rol)

        if warn_sayisi <= 5:
            yeni_rol = discord.utils.get(ctx.guild.roles, name=f"warn {warn_sayisi}")
            if yeni_rol:
                await member.add_roles(yeni_rol)

        # 3 WARN = 10 DK MUTE
        if warn_sayisi == 3:
            muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
            if muted_role:
                await member.add_roles(muted_role)
                await ctx.send("🔇 3 warn olduğu için 10 dakika susturuldu.")
                await asyncio.sleep(600)
                if muted_role in member.roles:
                    await member.remove_roles(muted_role)

        # 5 WARN = UYARI KANALI
        if warn_sayisi == 5:
            kanal = discord.utils.get(ctx.guild.text_channels, name="uyarı")
            if kanal:
                await kanal.send(f"🚨 {member.mention} 5 WARN'a ulaştı!")

    # ---------------- WARN RESET ---------------- #

    @commands.command()
    async def warnreset(self, ctx, member: discord.Member):
        if not self.check_admin(ctx):
            return await ctx.send("❌ Yetkin yok.")

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM punishments WHERE guild_id = ? AND user_id = ? AND type = 'WARN'",
            (ctx.guild.id, member.id)
        )
        conn.commit()
        conn.close()

        # WARN ROLLERİNİ SİL
        for i in range(1, 6):
            rol = discord.utils.get(ctx.guild.roles, name=f"warn {i}")
            if rol and rol in member.roles:
                await member.remove_roles(rol)

        # MUTE VARSA KALDIR
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if muted_role and muted_role in member.roles:
            await member.remove_roles(muted_role)

        await ctx.send(f"♻️ {member.mention} kullanıcısının tüm warnları sıfırlandı.")

    # ---------------- SİCİL ---------------- #

    @commands.command()
    async def sicil(self, ctx, member: discord.Member):
        if not self.check_admin(ctx):
            return await ctx.send("❌ Yetkin yok.")

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT type, reason, timestamp FROM punishments WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
            (ctx.guild.id, member.id)
        )

        kayıtlar = cursor.fetchall()
        conn.close()

        if not kayıtlar:
            return await ctx.send("🧾 Bu kullanıcının sicili temiz.")

        embed = discord.Embed(
            title=f"🧾 {member.display_name} Sicil",
            color=discord.Color.orange()
        )

        embed.description = f"Toplam Ceza: {len(kayıtlar)}"

        for tür, sebep, zaman in kayıtlar[:10]:
            embed.add_field(
                name=f"{tür}",
                value=f"Sebep: {sebep}\nTarih: {zaman}",
                inline=False
            )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
