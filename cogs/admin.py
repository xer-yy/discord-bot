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
        self.data = {}
        self.load_data()
        self.reset_loop.start()

    # =========================
    # DATA
    # =========================
    def load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {}

        if not os.path.exists(RESET_FILE):
            with open(RESET_FILE, "w") as f:
                json.dump(
                    {"next_reset": self.get_next_reset().isoformat()},
                    f
                )

    def save_data(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)

    def get_next_reset(self):
        return datetime.datetime.utcnow() + datetime.timedelta(days=10)

    def update_reset_time(self):
        with open(RESET_FILE, "w") as f:
            json.dump(
                {"next_reset": self.get_next_reset().isoformat()},
                f
            )

    # =========================
    # ROLE GÜNCELLEME
    # =========================
    async def update_roles(self, member, warn_count):
        for i in range(1, 6):
            role = discord.utils.get(member.guild.roles, name=f"warn {i}")
            if role and role in member.roles:
                await member.remove_roles(role)

        if 1 <= warn_count <= 5:
            role = discord.utils.get(member.guild.roles, name=f"warn {warn_count}")
            if role:
                await member.add_roles(role)

    # =========================
    # WARN KOMUTU
    # =========================
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def warn(self, ctx, member: discord.Member, *, reason="Sebep belirtilmedi"):

        user_id = str(member.id)

        if user_id not in self.data:
            self.data[user_id] = []

        warn_entry = {
            "reason": reason,
            "moderator": str(ctx.author),
            "date": datetime.datetime.utcnow().strftime("%d.%m.%Y %H:%M")
        }

        self.data[user_id].append(warn_entry)
        warn_count = len(self.data[user_id])

        await self.update_roles(member, warn_count)
        self.save_data()

        embed = discord.Embed(
            title="⚠ Kullanıcı Uyarıldı",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Kullanıcı", value=member.mention, inline=False)
        embed.add_field(name="Toplam Warn", value=str(warn_count))
        embed.add_field(name="Sebep", value=reason, inline=False)
        embed.set_footer(text=f"Yetkili: {ctx.author}")

        await ctx.send(embed=embed)

        # 3 warn → 10 dk timeout
        if warn_count == 3:
            try:
                await member.timeout(datetime.timedelta(minutes=10))
                await ctx.send(f"{member.mention} 10 dakika timeout yedi.")
            except:
                pass

        # 5 warn → kanal bildirimi
        if warn_count == 5:
            for channel in ctx.guild.text_channels:
                if channel.name in [UYARI_KANAL, DUYURU_KANAL]:
                    warn_embed = discord.Embed(
                        title="🚨 5 WARN UYARISI",
                        color=discord.Color.red()
                    )
                    warn_embed.add_field(name="Kullanıcı", value=member.mention)
                    warn_embed.add_field(name="Sebep", value=reason)
                    await channel.send(embed=warn_embed)

    # =========================
    # SİCİL GÖRÜNTÜLEME
    # =========================
    @commands.command()
    async def sicil(self, ctx, member: discord.Member):

        user_id = str(member.id)

        if user_id not in self.data or len(self.data[user_id]) == 0:
            await ctx.send("Bu kullanıcının sicili temiz.")
            return

        embed = discord.Embed(
            title="📜 Sicil Geçmişi",
            color=discord.Color.blue()
        )

        for i, entry in enumerate(self.data[user_id], start=1):
            embed.add_field(
                name=f"Warn {i}",
                value=f"Sebep: {entry['reason']}\nYetkili: {entry['moderator']}\nTarih: {entry['date']}",
                inline=False
            )

        await ctx.send(embed=embed)

    # =========================
    # KULLANICI SİCİL TEMİZLE
    # =========================
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def siciltemizle(self, ctx, member: discord.Member):

        user_id = str(member.id)

        if user_id in self.data:
            del self.data[user_id]
            self.save_data()

        await self.update_roles(member, 0)

        try:
            await member.timeout(None)
        except:
            pass

        await ctx.send(f"{member.mention} kullanıcısının sicili temizlendi.")

    # =========================
    # MANUEL SUNUCU RESET
    # =========================
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def cezalarisifirla(self, ctx):

        self.data = {}
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
                await channel.send("📢 Sunucu geneli tüm cezalar sıfırlandı.")

        await ctx.send("✅ Tüm cezalar sıfırlandı.")

    # =========================
    # OTOMATİK 10 GÜN RESET
    # =========================
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

            self.data = {}
            self.save_data()
            self.update_reset_time()


async def setup(bot):
    await bot.add_cog(Admin(bot))
