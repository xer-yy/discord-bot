import discord
from discord.ext import commands

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Rol adını buradan değiştiriyorsun
        role_name = "izm"

        role = discord.utils.get(member.guild.roles, name=role_name)

        if role is None:
            print(f"{role_name} rolü bulunamadı.")
            return

        try:
            await member.add_roles(role)
            print(f"{member} kullanıcısına {role_name} rolü verildi.")
        except Exception as e:
            print(f"Rol verilirken hata oluştu: {e}")

async def setup(bot):
    await bot.add_cog(AutoRole(bot))
