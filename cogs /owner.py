from discord.ext import commands
from config import OWNER_IDS

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_owner(ctx):
        return ctx.author.id in OWNER_IDS

    @commands.command()
    @commands.check(is_owner)
    async def panel(self, ctx):
        await ctx.send("👑 Owner paneline hoşgeldin.")

async def setup(bot):
    await bot.add_cog(Owner(bot))
