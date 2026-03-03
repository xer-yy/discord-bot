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

async def setup(bot):
    await bot.add_cog(Admin(bot))
