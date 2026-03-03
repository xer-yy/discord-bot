import discord
from discord.ext import commands, tasks
import datetime
import json
import os
import asyncio

# ================= CONFIG =================

WARN_FILE = "warn_data.json"
ADMIN_FILE = "admin_data.json"
MUTE_FILE = "mute_data.json"
RESET_FILE = "reset_time.json"
STATS_FILE = "stats_data.json"

UYARI_KANAL = "uyarı"
DUYURU_KANAL = "duyuru"
YONETIM_KANAL = "yonetim-uyari"

MUTE_ROLE_NAME = "Mute"
MUTE_DURATION = 600  # 10 dakika
RESET_GUN = 10

# =========================================


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warn_data = {}
        self.admins = []
        self.mute_data = {}
        self.stats_data = {}
        self.load_all_data()
        self.reset_loop.start()
        self.mute_loop.start()

    # ================= DATA LOAD =================

    def load_json(self, file, default):
        if os.path.exists(file):
            with open(file, "r") as f:
                return json.load(f)
        return default

    def save_json(self, file, data):
        with open(file, "w") as f:
            json.dump(data, f, indent=4)

    def load_all_data(self):
        self.warn_data = self.load_json(WARN_FILE, {})
        self.admins = self.load_json(ADMIN_FILE, [])
        self.mute_data = self.load_json(MUTE_FILE, {})
        self.stats_data = self.load_json(STATS_FILE, {})

        if not os.path.exists(RESET_FILE):
            next_reset = datetime.datetime.utcnow() + datetime.timedelta(days=RESET_GUN)
            self.save_json(RESET_FILE, {"next_reset": next_reset.isoformat()})

    # ================= ADMIN SYSTEM =================

    def is_bot_admin(self, user):
        return str(user.id) in self.admins

    async def admin_control(self, ctx):
        if not self.admins:
            self.admins.append(str(ctx.author.id))
            self.save_json(ADMIN_FILE, self.admins)
            await ctx.send("👑 İlk bot admini olarak atandın.")
            return True

        if not self.is_bot_admin(ctx.author):
            await ctx.send("⛔ Bu komutu kullanmak için bot admini olmalısın.")
            return False

        return True

    @commands.command()
    async def adminekle(self, ctx, member: discord.Member):
        if not await self.admin_control(ctx):
            return

        if str(member.id) not in self.admins:
            self.admins.append(str(member.id))
            self.save_json(ADMIN_FILE, self.admins)
            await ctx.send(f"✅ {member.mention} admin yapıldı.")

    @commands.command()
    async def adminsil(self, ctx, member: discord.Member):
        if not await self.admin_control(ctx):
            return

        if str(member.id) in self.admins:
            self.admins.remove(str(member.id))
            self.save_json(ADMIN_FILE, self.admins)
            await ctx.send(f"❌ {member.mention} adminlikten çıkarıldı.")

    @commands.command()
    async def adminliste(self, ctx):
        if not await self.admin_control(ctx):
            return

        embed = discord.Embed(title="🛡 Bot Admin Listesi", color=discord.Color.gold())

        for i, admin_id in enumerate(self.admins, 1):
            member = ctx.guild.get_member(int(admin_id))
            embed.add_field(
                name=f"{i}. Admin",
                value=member.mention if member else f"ID: {admin_id}",
                inline=False
            )

        await ctx.send(embed=embed)

    # ================= WARN SYSTEM =================

    async def update_warn_roles(self, member, count):
        for i in range(1, 6):
            role = discord.utils.get(member.guild.roles, name=f"Warn {i}")
            if role and role in member.roles:
                await member.remove_roles(role)

        if 1 <= count <= 5:
            role = discord.utils.get(member.guild.roles, name=f"Warn {count}")
            if role:
                await member.add_roles(role)

    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, reason="Sebep belirtilmedi"):
        if not await self.admin_control(ctx):
            return

        user_id = str(member.id)

        self.warn_data.setdefault(user_id, [])
        self.warn_data[user_id].append({
            "reason": reason,
            "moderator": str(ctx.author),
            "date": datetime.datetime.utcnow().strftime("%d.%m.%Y %H:%M")
        })

        count = len(self.warn_data[user_id])
        await self.update_warn_roles(member, count)
        self.save_json(WARN_FILE, self.warn_data)

        # Stats
        mod_id = str(ctx.author.id)
        self.stats_data.setdefault(mod_id, {"warn": 0, "mute": 0})
        self.stats_data[mod_id]["warn"] += 1
        self.save_json(STATS_FILE, self.stats_data)

        embed = discord.Embed(
            title="⚠ Kullanıcı Uyarıldı",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Kullanıcı", value=member.mention)
        embed.add_field(name="Toplam Warn", value=str(count))
        embed.add_field(name="Sebep", value=reason, inline=False)

        await ctx.send(embed=embed)

        # 3 Warn → Mute
        if count == 3:
            await self.mute_member(member, ctx.author)

        # 5 Warn → Yönetim Alarm
        if count == 5:
            kanal = discord.utils.get(ctx.guild.text_channels, name=YONETIM_KANAL)
            if kanal:
                await kanal.send(
                    f"🚨 {member.mention} 5 WARN seviyesine ulaştı! Yönetim incelemesi gerekli."
                )

    # ================= MUTE SYSTEM =================

    async def mute_member(self, member, moderator):
        mute_role = discord.utils.get(member.guild.roles, name=MUTE_ROLE_NAME)
        if not mute_role:
            return

        await member.add_roles(mute_role)

        bitis = datetime.datetime.utcnow() + datetime.timedelta(seconds=MUTE_DURATION)
        self.mute_data[str(member.id)] = bitis.isoformat()
        self.save_json(MUTE_FILE, self.mute_data)

        # Stats
        mod_id = str(moderator.id)
        self.stats_data.setdefault(mod_id, {"warn": 0, "mute": 0})
        self.stats_data[mod_id]["mute"] += 1
        self.save_json(STATS_FILE, self.stats_data)

    @commands.command()
    async def unmute(self, ctx, member: discord.Member):
        if not await self.admin_control(ctx):
            return

        mute_role = discord.utils.get(ctx.guild.roles, name=MUTE_ROLE_NAME)
        if mute_role and mute_role in member.roles:
            await member.remove_roles(mute_role)

        self.mute_data.pop(str(member.id), None)
        self.save_json(MUTE_FILE, self.mute_data)

        await ctx.send("🔊 Kullanıcı unmute edildi.")

    # Restart güvenli otomatik unmute
    @tasks.loop(seconds=30)
    async def mute_loop(self):
        now = datetime.datetime.utcnow()

        for user_id, bitis in list(self.mute_data.items()):
            if now >= datetime.datetime.fromisoformat(bitis):
                for guild in self.bot.guilds:
                    member = guild.get_member(int(user_id))
                    if member:
                        mute_role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
                        if mute_role and mute_role in member.roles:
                            await member.remove_roles(mute_role)

                self.mute_data.pop(user_id)

        self.save_json(MUTE_FILE, self.mute_data)

    # ================= SICIL =================

    @commands.command()
    async def sicil(self, ctx, member: discord.Member):
        if not await self.admin_control(ctx):
            return

        user_id = str(member.id)

        if user_id not in self.warn_data:
            await ctx.send("📜 Sicil temiz.")
            return

        embed = discord.Embed(
            title="📜 Kullanıcı Sicili",
            color=discord.Color.blue()
        )

        for i, entry in enumerate(self.warn_data[user_id], 1):
            embed.add_field(
                name=f"{i}. Warn",
                value=f"{entry['reason']} | {entry['moderator']} | {entry['date']}",
                inline=False
            )

        embed.set_footer(text=f"Toplam Warn: {len(self.warn_data[user_id])}")
        await ctx.send(embed=embed)

    # ================= YETKİLİ İSTATİSTİK =================

    @commands.command()
    async def ystat(self, ctx):
        if not await self.admin_control(ctx):
            return

        embed = discord.Embed(
            title="📊 Yetkili Performans Paneli",
            color=discord.Color.purple()
        )

        if not self.stats_data:
            embed.description = "Henüz veri yok."
            await ctx.send(embed=embed)
            return

        en_aktif = None
        en_warn = 0

        for admin_id, stats in self.stats_data.items():
            member = ctx.guild.get_member(int(admin_id))
            isim = member.mention if member else admin_id

            embed.add_field(
                name=isim,
                value=f"Warn: {stats['warn']} | Mute: {stats['mute']}",
                inline=False
            )

            if stats["warn"] > en_warn:
                en_warn = stats["warn"]
                en_aktif = isim

        embed.set_footer(text=f"En Aktif Moderator: {en_aktif}")
        await ctx.send(embed=embed)

    # ================= MOD PANEL (DASHBOARD) =================

    @commands.command()
    async def modpanel(self, ctx):
        if not await self.admin_control(ctx):
            return

        toplam_warn = sum(len(v) for v in self.warn_data.values())
        warn_kisi = len(self.warn_data)
        aktif_mute = len(self.mute_data)

        with open(RESET_FILE, "r") as f:
            reset_data = json.load(f)

        sonraki_reset = datetime.datetime.fromisoformat(reset_data["next_reset"])

        embed = discord.Embed(
            title="🛡 Moderasyon Dashboard",
            color=discord.Color.dark_gold(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.add_field(name="Toplam Aktif Warn", value=str(toplam_warn))
        embed.add_field(name="Warn Alan Kişi", value=str(warn_kisi))
        embed.add_field(name="Aktif Mute", value=str(aktif_mute))
        embed.add_field(name="Sonraki Reset", value=sonraki_reset.strftime("%d.%m.%Y %H:%M"))

        await ctx.send(embed=embed)

    # ================= GLOBAL RESET =================

    @tasks.loop(hours=1)
    async def reset_loop(self):

        with open(RESET_FILE, "r") as f:
            data = json.load(f)

        next_reset = datetime.datetime.fromisoformat(data["next_reset"])

        if datetime.datetime.utcnow() >= next_reset:

            for guild in self.bot.guilds:

                for member in guild.members:
                    for role_name in ["Warn 1","Warn 2","Warn 3","Warn 4","Warn 5", MUTE_ROLE_NAME]:
                        role = discord.utils.get(guild.roles, name=role_name)
                        if role and role in member.roles:
                            await member.remove_roles(role)

                for kanal_adi in [UYARI_KANAL, DUYURU_KANAL]:
                    kanal = discord.utils.get(guild.text_channels, name=kanal_adi)
                    if kanal:
                        embed = discord.Embed(
                            title="🔄 10 Günlük Ceza Reset",
                            description="Tüm warn ve mute cezaları temizlendi.",
                            color=discord.Color.green()
                        )
                        await kanal.send(embed=embed)

            self.warn_data = {}
            self.mute_data = {}

            self.save_json(WARN_FILE, self.warn_data)
            self.save_json(MUTE_FILE, self.mute_data)

            yeni_reset = datetime.datetime.utcnow() + datetime.timedelta(days=RESET_GUN)
            self.save_json(RESET_FILE, {"next_reset": yeni_reset.isoformat()})


async def setup(bot):
    await bot.add_cog(Admin(bot))
