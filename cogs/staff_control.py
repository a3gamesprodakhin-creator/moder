# cogs/staff_control.py
import disnake
from disnake.ext import commands

class StaffControl(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Здесь будут команды для контроля состава
    # Например:
    # @commands.slash_command(...)
    # async def staff(self, inter): ...

def setup(bot):
    bot.add_cog(StaffControl(bot))