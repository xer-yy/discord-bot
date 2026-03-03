import discord
from discord.ext import commands, tasks
import datetime
import json
import os
import asyncio

WARN_FILE = "warn_data.json"
ADMIN_FILE = "admin_data.json"
MUTE_FILE = "mute_data.json"
RESET_FILE = "reset_time.json"

UYARI_KANAL = "uyarı"
DUYURU_KANAL = "duyuru"
YONETIM_KANAL = "yonetim-uyari"

MUTE_SURE = 600  # 10 dakika


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warn_data = {}
        self.admins = []
        self.mute_data = {}
        self.load_data()
        self.reset_loop.start()
        self.mute_control.start()

    # ================= DATA =================

    def load_data(self):
        for file, attr in [
            (WARN_FILE, "warn_data"),
            (ADMIN_FILE, "admins"),
            (MUTE_FILE, "mute_data"),
        ]:
            if os.path.exists(file):
                with open(file, "r") as f:
                    setattr(self, attr, json.load(f))
            else:
                setattr(self, attr, {} if "data" in file else [])

        if not os.path.exists(RESET_FILE):
            with open(RESET_FILE, "w") as f:
                json.dump(
                    {"next_reset": (datetime.datetime.utcnow() + datetime.timedelta(days=10)).isoformat()},
                    f
                )

    def save(self, file, data):
        with open(file, "w") as f:
            json.dump(data, f, indent=4)

    # ================= ADMIN CONTROL =================

    def is_admin(self, user):
        return str(user.id) in self.admins

    async def admin_check(self, ctx):
        if not self.admins:
            self.admins.append(str(ctx.author.id))
            self.save(ADMIN_FILE, self.admins)
            await ctx.send("👑 İlk bot admini olarak atandın.")
            return True

        if not self.is_admin(ctx.author):
            await ctx.send("⛔ Bot admini değilsin.")
            return False
        return True

    @commands.command()
    async def adminekle(self, ctx, member: discord.Member):
        if not await self.admin_check(ctx): return
        if str(member.id) not in self.admins:
            self.admins.append(str(member.id))
            self.save(ADMIN_FILE, self.admins)
            await ctx.send(f"✅ {member.mention} admin yapıldı.")

    @commands.command()
    async def adminsil(self, ctx, member: discord.Member):
        if not await self.admin_check(ctx): return
        if str(member.id) in self.admins:
            self.admins.remove(str(member.id))
            self.save(ADMIN_FILE, self.admins)
            await ctx.send(f"❌ {member.mention} adminlikten çıkarıldı.")

    @commands.command()
    async def adminliste(self, ctx):
        if not await self.admin_check(ctx): return
        embed = discord.Embed(title="🛡 Bot Adminleri", color=discord.Color.gold())
        for i, admin_id in enumerate(self.admins, 1):
            member = ctx.guild.get_member(int(admin_id))
            embed.add_field(name=f"{i}.", value=member.mention if member else admin_id)
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
    async def warn(self, ctx, member: discord.Member, *, reason="Sebep yok"):
        if not await self.admin_check(ctx): return

        user_id = str(member.id)
        self.warn_data.setdefault(user_id, [])
        self.warn_data[user_id].append({
            "reason": reason,
            "moderator": str(ctx.author),
            "date": datetime.datetime.utcnow().strftime("%d.%m.%Y %H:%M")
        })

        count = len(self.warn_data[user_id])
        await self.update_warn_roles(member, count)
        self.save(WARN_FILE, self.warn_data)

        embed = discord.Embed(title="⚠ Warn Atıldı", color=discord.Color.orange())
        embed.add_field(name="Kullanıcı", value=member.mention)
        embed.add_field(name="Toplam Warn", value=str(count))
        embed.add_field(name="Sebep", value=reason, inline=False)
        await ctx.send(embed=embed)

        if count == 3:
            await self.mute_member(member)

        if count == 5:
            kanal = discord.utils.get(ctx.guild.text_channels, name=YONETIM_KANAL)
            if kanal:
                await kanal.send(f"🚨 {member.mention} 5 WARN seviyesine ulaştı!")

    async def mute_member(self, member):
        mute_role = discord.utils.get(member.guild.roles, name="Mute")
        if not mute_role: return
        await member.add_roles(mute_role)
        bitis = datetime.datetime.utcnow() + datetime.timedelta(seconds=MUTE_SURE)
        self.mute_data[str(member.id)] = bitis.isoformat()
        self.save(MUTE_FILE, self.mute_data)

    @commands.command()
    async def unmute(self, ctx, member: discord.Member):
        if not await self.admin_check(ctx): return
        mute_role = discord.utils.get(member.guild.roles, name="Mute")
        if mute_role in member.roles:
            await member.remove_roles(mute_role)
        self.mute_data.pop(str(member.id), None)
        self.save(MUTE_FILE, self.mute_data)
        await ctx.send("🔊 Kullanıcı unmute edildi.")

    # ================= SICIL =================

    @commands.command()
    async def sicil(self, ctx, member: discord.Member):
        if not await self.admin_check(ctx): return
        user_id = str(member.id)
        if user_id not in self.warn_data:
            await ctx.send("Sicil temiz.")
            return

        embed = discord.Embed(title="📜 Sicil", color=discord.Color.blue())
        for i, entry in enumerate(self.warn_data[user_id], 1):
            embed.add_field(name=f"{i}. Warn",
                            value=f"{entry['reason']} | {entry['moderator']} | {entry['date']}",
                            inline=False)
        await ctx.send(embed=embed)

    # ================= AUTO UNMUTE CONTROL =================

    @tasks.loop(seconds=30)
    async def mute_control(self):
        now = datetime.datetime.utcnow()
        for user_id, bitis in list(self.mute_data.items()):
            if now >= datetime.datetime.fromisoformat(bitis):
                for guild in self.bot.guilds:
                    member = guild.get_member(int(user_id))
                    if member:
                        mute_role = discord.utils.get(guild.roles, name="Mute")
                        if mute_role and mute_role in member.roles:
                            await member.remove_roles(mute_role)
                self.mute_data.pop(user_id)
        self.save(MUTE_FILE, self.mute_data)

    # ================= GLOBAL RESET =================

    @tasks.loop(hours=1)
    async def reset_loop(self):
        with open(RESET_FILE, "r") as f:
            data = json.load(f)

        next_reset = datetime.datetime.fromisoformat(data["next_reset"])
        if datetime.datetime.utcnow() >= next_reset:

            for guild in self.bot.guilds:
                for member in guild.members:
                    for role_name in ["Warn 1","Warn 2","Warn 3","Warn 4","Warn 5","Mute"]:
                        role = discord.utils.get(guild.roles, name=role_name)
                        if role and role in member.roles:
                            await member.remove_roles(role)

                for kanal_adi in [UYARI_KANAL, DUYURU_KANAL]:
                    kanal = discord.utils.get(guild.text_channels, name=kanal_adi)
                    if kanal:
                        await kanal.send("🔄 10 Günlük Ceza Reset Sistemi Çalıştı. Tüm cezalar temizlendi.")

            self.warn_data = {}
            self.mute_data = {}
            self.save(WARN_FILE, self.warn_data)
            self.save(MUTE_FILE, self.mute_data)

            with open(RESET_FILE, "w") as f:
                json.dump(
                    {"next_reset": (datetime.datetime.utcnow() + datetime.timedelta(days=10)).isoformat()},
                    f
                )

async def setup(bot):
    await bot.add_cog(Admin(bot))
