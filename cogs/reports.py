import disnake
from disnake.ext import commands
import json

class Reports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open("config.json") as f:
            self.config = json.load(f)

    @commands.slash_command(name="report")
    async def report(self, inter, user: disnake.Member, reason: str):

        embed = disnake.Embed(
            title="Новый репорт",
            color=disnake.Color.red()
        )

        embed.add_field(name="Жалоба на", value=user.mention)
        embed.add_field(name="От", value=inter.author.mention)
        embed.add_field(name="Причина", value=reason)

        channel = inter.guild.get_channel(self.config["report_channel"])

        view = disnake.ui.View()
        view.add_item(disnake.ui.Button(
            label="Принять",
            style=disnake.ButtonStyle.success,
            custom_id=f"report_accept_{user.id}"
        ))
        view.add_item(disnake.ui.Button(
            label="Отклонить",
            style=disnake.ButtonStyle.danger,
            custom_id=f"report_deny_{user.id}"
        ))

        await channel.send(embed=embed, view=view)
        await inter.response.send_message("Репорт отправлен.", ephemeral=True)

    @commands.Cog.listener()
    async def on_button_click(self, inter):

        if inter.component.custom_id.startswith("report_accept"):
            await inter.response.send_message("Репорт принят.", ephemeral=True)

        if inter.component.custom_id.startswith("report_deny"):
            await inter.response.send_message("Репорт отклонен.", ephemeral=True)

def setup(bot):
    bot.add_cog(Reports(bot))
