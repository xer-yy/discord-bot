from discord.ext import commands
from database import set_role, get_role
from config import OWNER_IDS

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin(ctx):
        if ctx.author.id in OWNER_IDS:
            return True
        role = get_role(ctx.guild.id, ctx.author.id)
        return role == "admin"

    @commands.command()
    async def setadmin(self, ctx, member):
        if ctx.author.id not in OWNER_IDS:
            return await ctx.send("Bunu sadece owner yapabilir.")

        member = ctx.guild.get_member(int(member.replace("<@", "").replace(">", "").replace("!", "")))
        set_role(ctx.guild.id, member.id, "admin")
        await ctx.send(f"{member.mention} artık admin.")

    @commands.command()
    @commands.check(is_admin)
    async def yönetim(self, ctx):
        await ctx.send("🛡️ Yönetim paneli açık.")

async def setup(bot):
    await bot.add_cog(Admin(bot))
