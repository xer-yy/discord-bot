import discord
from discord.ext import commands
from config import OWNER_ID
from database import add_admin, remove_admin, get_admins

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def panel(self, ctx):
        if ctx.author.id != OWNER_ID:1265528345576341648
            return await ctx.send("❌ Bu panel sadece owner içindir.")

        embed = discord.Embed(
            title="👑 Owner Panel",
            description="!addadmin @kişi\n!removeadmin @kişi\n!adminlist",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def addadmin(self, ctx, member: discord.Member):
        if ctx.author.id != OWNER_ID:
            return await ctx.send("❌ Yetkin yok.")

        add_admin(ctx.guild.id, member.id)
        await ctx.send(f"✅ {member.mention} admin yapıldı.")

    @commands.command()
    async def removeadmin(self, ctx, member: discord.Member):
        if ctx.author.id != OWNER_ID:
            return await ctx.send("❌ Yetkin yok.")

        remove_admin(ctx.guild.id, member.id)
        await ctx.send(f"❌ {member.mention} adminlikten çıkarıldı.")

    @commands.command()
    async def adminlist(self, ctx):
        admins = get_admins(ctx.guild.id)

        if not admins:
            return await ctx.send("Admin yok.")

        mentions = []
        for admin in admins:
            user = await self.bot.fetch_user(admin[0])
            mentions.append(user.name)

        await ctx.send("🛡 Adminler:\n" + "\n".join(mentions))

async def setup(bot):
    await bot.add_cog(Owner(bot))
