# cogs/appeals.py
import disnake
from disnake.ext import commands

class Appeals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    # Здесь будут команды для аппеляций (если нужно)

def setup(bot):
    bot.add_cog(Appeals(bot))