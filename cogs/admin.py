import discord
from discord.ext import commands
import asyncio
import re
import sqlite3
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

    @commands.command()
    async def duyuru(self, ctx, *, mesaj):
        if not self.check_admin(ctx):
            return await ctx.send("❌ Yetkin yok.")

        kanal = discord.utils.get(ctx.guild.text_channels, name="duyurular")
        if kanal is None:
            return await ctx.send("❌ 'duyurular' kanalı yok.")

        embed = discord.Embed(
            title="📢 DUYURU",
            description=f"# {mesaj}",
            color=discord.Color.red()
        )

        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url
        )

        await kanal.send(embed=embed)
        await ctx.send("✅ Duyuru gönderildi.")

    @commands.command()
    async def mute(self, ctx, member: discord.Member, süre: str, *, sebep="Belirtilmedi"):
        if not self.check_admin(ctx):
            return await ctx.send("❌ Yetkin yok.")

        if member.top_role >= ctx.author.top_role and ctx.author.id != OWNER_ID:
            return await ctx.send("❌ Bu kişiyi susturamazsın (rol hiyerarşisi).")

        seconds = parse_duration(süre.replace(" ", ""))

        if not seconds:
            return await ctx.send("❌ Süre formatı hatalı.\nÖrnek: 10m, 2h, 1d, 1h30m")

        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")

        if muted_role is None:
            muted_role = await ctx.guild.create_role(name="Muted")
            for channel in ctx.guild.channels:
                await channel.set_permissions(muted_role, send_messages=False, speak=False)

        await member.add_roles(muted_role)

        add_punishment(ctx.guild.id, member.id, ctx.author.id, "MUTE", sebep)

        await ctx.send(f"🔇 {member.mention} {süre} boyunca susturuldu.")

        log = discord.utils.get(ctx.guild.text_channels, name="log")
        if log:
            await log.send(f"🔇 {member} susturuldu | Süre: {süre} | Yetkili: {ctx.author} | Sebep: {sebep}")

        await asyncio.sleep(seconds)

        if muted_role in member.roles:
            await member.remove_roles(muted_role)
            if log:
                await log.send(f"🔊 {member} otomatik olarak susturma kaldırıldı.")

    @commands.command()
    async def unmute(self, ctx, member: discord.Member):
        if not self.check_admin(ctx):
            return await ctx.send("❌ Yetkin yok.")

        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")

        if muted_role and muted_role in member.roles:
            await member.remove_roles(muted_role)
            await ctx.send(f"🔊 {member.mention} susturma kaldırıldı.")

            log = discord.utils.get(ctx.guild.text_channels, name="log")
            if log:
                await log.send(f"🔊 {member} susturma kaldırıldı | Yetkili: {ctx.author}")
        else:
            await ctx.send("❌ Kullanıcı muted değil.")

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
            title=f"🧾 {member.display_name} Sicil Kaydı",
            color=discord.Color.orange()
        )

        for tür, sebep, zaman in kayıtlar[:10]:
            embed.add_field(
                name=f"{tür} | {zaman}",
                value=f"Sebep: {sebep}",
                inline=False
            )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
