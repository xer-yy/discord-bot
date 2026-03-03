import discord
from discord.ext import commands, tasks
import datetime
import json
import os

UYARI_KANAL = "uyarı"
DUYURU_KANAL = "duyuru"

DATA_FILE = "warn_data.json"
RESET_FILE = "reset_time.json"


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warn_data = {}
        self.load_data()
        self.reset_loop.start()

    # ==========================
    # DATA
    # ==========================
    def load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                self.warn_data = json.load(f)
        else:
            self.warn_data = {}

        if not os.path.exists(RESET_FILE):
            with open(RESET_FILE, "w") as f:
                json.dump(
                    {"next_reset": self.get_next_reset().isoformat()}, f
                )

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.warn_data, f, indent=4)

    def get_next_reset(self):
        return datetime.datetime.utcnow() + datetime.timedelta(days=10)

    def update_reset_time(self):
        with open(RESET_FILE, "w") as f:
            json.dump(
                {"next_reset": self.get_next_reset().isoformat()}, f
            )

    # ==========================
    # ROLE UPDATE
    # ==========================
    async def update_roles(self, member, warn_count):
        guild = member.guild

        # tüm warn rollerini kaldır
        for i in range(1, 6):
            role = discord.utils.get(guild.roles, name=f"warn {i}")
            if role and role in member.roles:
                await member.remove_roles(role)

        # yeni warn rolü ver
        if 1 <= warn_count <= 5:
            role = discord.utils.get(guild.roles, name=f"warn {warn_count}")
            if role:
                await member.add_roles(role)

    # ==========================
    # WARN
    # ==========================
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def warn(self, ctx, member: discord.Member, *, reason="Sebep belirtilmedi"):

        user_id = str(member.id)

        if user_id not in self.warn_data:
            self.warn_data[user_id] = 0

        self.warn_data[user_id] += 1
        warn_count = self.warn_data[user_id]

        await self.update_roles(member, warn_count)
        self.save_data()

        embed = discord.Embed(
            title="⚠ Kullanıcı Uyarıldı",
            color=discord.Color.orange()
        )
        embed.add_field(name="Kullanıcı", value=member.mention)
        embed.add_field(name="Toplam Warn", value=warn_count)
        embed.add_field(name="Sebep", value=reason)
        embed.set_footer(text=f"Yetkili: {ctx.author}")

        await ctx.send(embed=embed)

        # 3 WARN → 10 dk mute
        if warn_count == 3:
            try:
                await member.timeout(datetime.timedelta(minutes=10))
                await ctx.send(f"{member.mention} 10 dakika timeout yedi.")
            except:
                pass

        # 5 WARN → kanal bildirimi
        if warn_count == 5:
            for channel in ctx.guild.text_channels:
                if channel.name in [UYARI_KANAL, DUYURU_KANAL]:
                    await channel.send(
                        f"🚨 {member.mention} 5 WARN aldı!\nSebep: {reason}"
                    )

    # ==========================
    # SİCİL
    # ==========================
    @commands.command()
    async def sicil(self, ctx, member: discord.Member):
        warn_count = self.warn_data.get(str(member.id), 0)

        embed = discord.Embed(
            title="📜 Sicil Bilgisi",
            color=discord.Color.blue()
        )
        embed.add_field(name="Kullanıcı", value=member.mention)
        embed.add_field(name="Toplam Warn", value=warn_count)

        await ctx.send(embed=embed)

    # ==========================
    # MANUEL RESET
    # ==========================
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def cezalarisifirla(self, ctx):

        self.warn_data = {}
        self.save_data()
        self.update_reset_time()

        for member in ctx.guild.members:
            await self.update_roles(member, 0)
            try:
                await member.timeout(None)
            except:
                pass

        for channel in ctx.guild.text_channels:
            if channel.name in [UYARI_KANAL, DUYURU_KANAL]:
                await channel.send(
                    "📢 Sunucu geneli tüm cezalar manuel olarak sıfırlandı."
                )

        await ctx.send("✅ Tüm cezalar sıfırlandı.")

    # ==========================
    # OTOMATİK 10 GÜN RESET
    # ==========================
    @tasks.loop(hours=1)
    async def reset_loop(self):

        if not os.path.exists(RESET_FILE):
            return

        with open(RESET_FILE, "r") as f:
            data = json.load(f)

        next_reset = datetime.datetime.fromisoformat(data["next_reset"])

        if datetime.datetime.utcnow() >= next_reset:

            for guild in self.bot.guilds:
                for member in guild.members:
                    await self.update_roles(member, 0)
                    try:
                        await member.timeout(None)
                    except:
                        pass

                for channel in guild.text_channels:
                    if channel.name in [UYARI_KANAL, DUYURU_KANAL]:
                        await channel.send(
                            "📢 10 günlük otomatik reset gerçekleşti. Tüm cezalar silindi."
                        )

            self.warn_data = {}
            self.save_data()
            self.update_reset_time()


async def setup(bot):
    await bot.add_cog(Admin(bot))
