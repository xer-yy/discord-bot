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
            return await ctx.send("❌ Bu komutu kullanamazsın.")

        await ctx.send(f"📢 DUYURU:\n{mesaj}")

async def setup(bot):
    await bot.add_cog(Admin(bot))
