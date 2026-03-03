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

    # ---------------- WARN SİSTEMİ ---------------- #

    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, sebep="Belirtilmedi"):
        if not self.check_admin(ctx):
            return await ctx.send("❌ Yetkin yok.")

        if member.top_role >= ctx.author.top_role and ctx.author.id != OWNER_ID:
            return await ctx.send("❌ Bu kullanıcıya warn veremezsin.")

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

        log = discord.utils.get(ctx.guild.text_channels, name="log")
        if log:
            await log.send(f"⚠️ {member} warn aldı | Yetkili: {ctx.author} | Sebep: {sebep}")

        # 3 WARN = 10 DK MUTE
        if warn_sayisi == 3:
            muted_role = discord.utils.get(ctx.guild.roles, name="Muted")

            if muted_role is None:
                muted_role = await ctx.guild.create_role(name="Muted")
                for channel in ctx.guild.channels:
                    await channel.set_permissions(muted_role, send_messages=False, speak=False)

            await member.add_roles(muted_role)
            await ctx.send("🔇 3 warn olduğu için 10 dakika susturuldu.")

            await asyncio.sleep(600)

            if muted_role in member.roles:
                await member.remove_roles(muted_role)

        # 5 WARN = YÖNETİM UYARI (KANAL ADI: uyarı)
        if warn_sayisi == 5:
            yonetim_kanal = discord.utils.get(ctx.guild.text_channels, name="uyarı")
            if yonetim_kanal:
                await yonetim_kanal.send(
                    f"🚨 {member.mention} 5 WARN'a ulaştı!\n"
                    f"Toplam Warn: {warn_sayisi}\n"
                    f"Son Yetkili: {ctx.author.mention}"
                )

    # ---------------- SİCİL ---------------- #

    @commands.command()
    async def sicil(self, ctx, member: discord.Member):
        if not self.check_admin(ctx):
            return await ctx.send("❌ Yetkin yok.")

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT type, reason, timestamp, moderator_id FROM punishments WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
            (ctx.guild.id, member.id)
        )

        kayıtlar = cursor.fetchall()
        conn.close()

        if not kayıtlar:
            return await ctx.send("🧾 Bu kullanıcının sicili temiz.")

        embed = discord.Embed(
            title=f"🧾 {member.display_name} Sicil Kaydı",
            color=discord.Color.orange()
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        toplam = len(kayıtlar)
        embed.description = f"**Toplam Ceza:** `{toplam}`\n\nSon 10 kayıt gösteriliyor.\n"

        for index, (tür, sebep, zaman, mod_id) in enumerate(kayıtlar[:10], start=1):

            try:
                zaman_obj = datetime.fromisoformat(zaman)
                unix = int(zaman_obj.timestamp())
                zaman_format = f"<t:{unix}:R>"
            except:
                zaman_format = zaman

            moderator = ctx.guild.get_member(mod_id)
            moderator_name = moderator.mention if moderator else f"ID: {mod_id}"

            embed.add_field(
                name=f"#{index} | {tür}",
                value=(
                    f"**Sebep:** {sebep}\n"
                    f"**Yetkili:** {moderator_name}\n"
                    f"**Tarih:** {zaman_format}"
                ),
                inline=False
            )

        embed.set_footer(text=f"Kullanıcı ID: {member.id}")

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
