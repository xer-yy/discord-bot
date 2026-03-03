import discord
from discord.ext import commands
import os
import asyncio

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"{bot.user} olarak giriş yapıldı!")
    print("Bot aktif!")


async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"{filename} yüklendi.")


async def main():
    async with bot:
        await load_cogs()
        await bot.start(os.getenv("TOKEN"))


asyncio.run(main())
