from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def setadmin(self, ctx):
        await ctx.send("Admin komutu çalıştı kankam 😎")

async def setup(bot):
    await bot.add_cog(Admin(bot))
