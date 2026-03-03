from discord.ext import commands

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def panel(self, ctx):
        await ctx.send("Owner panel aktif!")

async def setup(bot):
    await bot.add_cog(Owner(bot))
