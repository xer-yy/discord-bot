import discord
from discord.ext import commands
from database import is_admin
from config import OWNER_ID

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def check_admin(self, ctx):
        return ctx.author.id == OWNER_ID or is_admin(ctx.guild.id, ctx.author.id)

    @commands.command()
    async def duyuru(self, ctx, *, mesaj):
        if not self.check_admin(ctx):
            await ctx.send("❌ Bu komutu kullanamazsın.")
            return

        kanal = discord.utils.get(ctx.guild.text_channels, name="duyurular")

        if kanal is None:
            await ctx.send("❌ 'duyurular' adında kanal bulunamadı.")
            return

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
import asyncio
from database import add_punishment
@commands.command()
async def mute(self, ctx, member: discord.Member, süre: str, *, sebep="Belirtilmedi"):
    if not self.check_admin(ctx):
        return await ctx.send("❌ Yetkin yok.")

    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")

    if muted_role is None:
        muted_role = await ctx.guild.create_role(name="Muted")

        for channel in ctx.guild.channels:
            await channel.set_permissions(muted_role, send_messages=False, speak=False)

    await member.add_roles(muted_role)

    # Süre hesaplama
    if süre.endswith("m"):
        seconds = int(süre[:-1]) * 60
    elif süre.endswith("h"):
        seconds = int(süre[:-1]) * 3600
    else:
        return await ctx.send("❌ Süre formatı: 10m veya 1h")

    add_punishment(ctx.guild.id, member.id, ctx.author.id, "MUTE", sebep)

    await ctx.send(f"🔇 {member.mention} {süre} boyunca susturuldu.")

    # Log
    log = discord.utils.get(ctx.guild.text_channels, name="log")
    if log:
        await log.send(f"🔇 {member} susturuldu | Süre: {süre} | Yetkili: {ctx.author}")

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

    if muted_role in member.roles:
        await member.remove_roles(muted_role)
        await ctx.send(f"🔊 {member.mention} susturma kaldırıldı.")

        log = discord.utils.get(ctx.guild.text_channels, name="log")
        if log:
            await log.send(f"🔊 {member} susturma kaldırıldı | Yetkili: {ctx.author}")
    else:
        await ctx.send("❌ Kullanıcı muted değil.")
async def setup(bot):
    await bot.add_cog(Admin(bot))
