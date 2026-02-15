import disnake
from disnake.ext import commands
import json
import time

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active = {}  # {user_id: {"zone": "verification"/"mod", "start": timestamp}}
        self.data_file = "data/voice.json"

    def load_data(self):
        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_data(self, data):
        import os
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=4)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Получаем ID зон из конфига
        with open("config.json") as f:
            config = json.load(f)
        verif_zone = config["voice_zones"]["verification_zone"]
        mod_zone = config["voice_zones"]["mod_zone"]

        data = self.load_data()
        user_id = str(member.id)

        # Функция завершения текущей сессии (если есть)
        async def finish_session():
            if user_id in self.active:
                zone = self.active[user_id]["zone"]
                start = self.active[user_id]["start"]
                duration = time.time() - start
                if zone == "verification":
                    data.setdefault(user_id, {"verification": 0, "mod": 0})
                    data[user_id]["verification"] += duration
                elif zone == "mod":
                    data.setdefault(user_id, {"verification": 0, "mod": 0})
                    data[user_id]["mod"] += duration
                del self.active[user_id]

        # Если пользователь зашёл в канал
        if after.channel:
            # Определяем, является ли канал отслеживаемой зоной
            zone = None
            if after.channel.id == verif_zone:
                zone = "verification"
            elif after.channel.id == mod_zone:
                zone = "mod"

            if zone:
                # Завершаем предыдущую сессию (если была в другой зоне)
                await finish_session()
                # Начинаем новую
                self.active[user_id] = {"zone": zone, "start": time.time()}
            else:
                # Зашёл в неотслеживаемый канал — завершаем сессию, если была
                await finish_session()
        else:
            # Вышел из канала — завершаем сессию
            await finish_session()

        self.save_data(data)

    @commands.slash_command(name="voice", description="Показывает время в голосовых зонах")
    async def voice(
        self,
        inter: disnake.AppCmdInter,
        group: str = commands.Param(name="группа", choices=["support", "moderator"]),
        user: disnake.Member = commands.Param(name="пользователь", default=None)
    ):
        if not user:
            user = inter.author

        data = self.load_data()
        user_data = data.get(str(user.id), {"verification": 0, "mod": 0})

        if group == "support":
            minutes = user_data["verification"] / 60
            zone_name = "верификации"
        else:
            minutes = user_data["mod"] / 60
            zone_name = "модераторской"

        await inter.response.send_message(
            f"Пользователь {user.mention} провёл {minutes:.2f} мин. в зоне {zone_name}."
        )

def setup(bot):
    bot.add_cog(Voice(bot))