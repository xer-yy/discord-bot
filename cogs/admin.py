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

    # ================= DATA =================
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

    # ================= ROLE UPDATE =================
    async def update_roles(self, member, warn_count):
        for i in range(1, 6):
            role = discord.utils.get(member.guild.roles, name=f"warn {i}")
            if role and role in member.roles:
                await member.remove_roles(role)

        if 1 <= warn_count <= 5:
            role = discord.utils.get(member.guild.roles, name=f"warn {warn_count}")
            if role:
                await member.add_roles(role)

    # ================= WARN =================
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

        if warn_count == 3:
            try:
                await member.timeout(datetime.timedelta(minutes=10))
                await ctx.send(f"{member.mention} 10 dakika timeout yedi.")
            except:
                pass

        if warn_count == 5:
            for channel in ctx.guild.text_channels:
                if channel.name in [UYARI_KANAL, DUYURU_KANAL]:
                    alert = discord.Embed(
                        title="🚨 5 WARN UYARISI",
                        color=discord.Color.red()
                    )
                    alert.add_field(name="Kullanıcı", value=member.mention)
                    alert.add_field(name="Sebep", value=reason)
                    await channel.send(embed=alert)

    # ================= SICIL =================
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

    # ================= SICIL TEMIZLE =================
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

    # ================= MANUEL RESET =================
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

    # ================= MOD PANEL =================
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def modpanel(self, ctx):

        total_warn = 0
        user_count = 0
        moderator_stats = {}
        last_7_days = 0
        last_24_hours = 0

        now = datetime.datetime.utcnow()

        for user_id, warns in self.data.items():
            if len(warns) > 0:
                user_count += 1
                total_warn += len(warns)

                for entry in warns:
                    mod = entry["moderator"]
                    date = datetime.datetime.strptime(entry["date"], "%d.%m.%Y %H:%M")

                    if mod not in moderator_stats:
                        moderator_stats[mod] = 0
                    moderator_stats[mod] += 1

                    if (now - date).days <= 7:
                        last_7_days += 1

                    if (now - date).total_seconds() <= 86400:
                        last_24_hours += 1

        sorted_mods = sorted(moderator_stats.items(), key=lambda x: x[1], reverse=True)

        top1 = sorted_mods[0] if len(sorted_mods) > 0 else ("Yok", 0)
        top2 = sorted_mods[1] if len(sorted_mods) > 1 else ("Yok", 0)
        top3 = sorted_mods[2] if len(sorted_mods) > 2 else ("Yok", 0)

        top_user = None
        top_user_warn = 0

        for user_id, warns in self.data.items():
            if len(warns) > top_user_warn:
                top_user_warn = len(warns)
                top_user = user_id

        top_user_display = "Yok"
        if top_user:
            member = ctx.guild.get_member(int(top_user))
            if member:
                top_user_display = f"{member.mention} ({top_user_warn} warn)"

        next_reset_text = "Bilinmiyor"
        if os.path.exists(RESET_FILE):
            with open(RESET_FILE, "r") as f:
                data = json.load(f)
                next_reset = datetime.datetime.fromisoformat(data["next_reset"])
                remaining_days = (next_reset - now).days
                next_reset_text = f"{remaining_days} gün kaldı"

        avg_daily = round(total_warn / 10, 2) if total_warn > 0 else 0

        embed = discord.Embed(
            title="🛡 Moderasyon Dashboard",
            color=discord.Color.dark_gold(),
            timestamp=now
        )

        embed.add_field(
            name="📊 Genel İstatistik",
            value=(
                f"⚠ Toplam Aktif Warn: {total_warn}\n"
                f"👥 Warn Alan Kullanıcı: {user_count}\n"
                f"📅 Son 7 Gün: {last_7_days}\n"
                f"📆 Son 24 Saat: {last_24_hours}\n"
                f"⏳ Reset: {next_reset_text}"
            ),
            inline=False
        )

        embed.add_field(
            name="🏆 Yetkili Performansı",
            value=(
                f"🥇 {top1[0]} → {top1[1]}\n"
                f"🥈 {top2[0]} → {top2[1]}\n"
                f"🥉 {top3[0]} → {top3[1]}"
            ),
            inline=False
        )

        embed.add_field(
            name="🔥 Risk Analizi",
            value=(
                f"🚨 En Çok Warn Alan: {top_user_display}\n"
                f"📈 Günlük Ortalama: {avg_daily}"
            ),
            inline=False
        )

        embed.set_footer(text="IZM Moderasyon Sistemi • PRO")

        await ctx.send(embed=embed)

    # ================= OTOMATIK RESET =================
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
