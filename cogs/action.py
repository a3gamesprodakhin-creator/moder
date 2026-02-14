import disnake
from disnake.ext import commands
import json
import datetime
from utils.checks import has_role
from utils.time_parser import parse_time
from utils.helpers import (
    load_punishments, save_punishments,
    add_punishment, remove_punishment,
    has_active_punishment, count_punishments, count_nicknames
)
from utils.logger import log_action

class Action(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open("config.json") as f:
            self.config = json.load(f)

    def _check_permission(self, member, role_key):
        role_id = self.config["roles"].get(role_key)
        if not role_id:
            return False
        return has_role(member, role_id)

    def _has_full_access(self, member):
        full_roles = ["admin", "developer", "owner"]
        for role_key in full_roles:
            if self._check_permission(member, role_key):
                return True
        return False

    def _is_staff(self, member):
        staff_roles = ["moderator", "support", "control", "admin", "developer", "owner"]
        return any(self._check_permission(member, r) for r in staff_roles)

    async def _send_log(self, inter, action_type, sub_type, target, duration=None, reason=None, gender=None):
        """Универсальный метод для отправки логов в стиле, как на скринах"""
        guild = inter.guild
        channel = guild.get_channel(self.config["log_channel"])
        if not channel:
            return

        # Определяем заголовок и цвет
        if action_type == "mute":
            title = f"🔇 Логи — {'Текстовый' if sub_type=='text' else 'Голосовой'} мут"
            color = disnake.Color.dark_gray()
        elif action_type == "unmute":
            title = f"🔊 Логи — Снятие мута"
            color = disnake.Color.green()
        elif action_type == "ban":
            title = "🔨 Логи — Бан"
            color = disnake.Color.red()
        elif action_type == "unban":
            title = "🔓 Логи — Разбан"
            color = disnake.Color.green()
        elif action_type == "warn":
            title = "⚠ Логи — Предупреждение"
            color = disnake.Color.orange()
        elif action_type == "unwarn":
            title = "✅ Логи — Снятие предупреждения"
            color = disnake.Color.green()
        elif action_type == "remark":
            title = "📝 Логи — Замечание"
            color = disnake.Color.gold()
        elif action_type == "unremark":
            title = "✅ Логи — Снятие замечания"
            color = disnake.Color.green()
        elif action_type == "suspension":
            title = "⏳ Логи — Отстранение (ивент бан)"
            color = disnake.Color.dark_red()
        elif action_type == "unsuspension":
            title = "🔄 Логи — Снятие отстранения"
            color = disnake.Color.green()
        elif action_type == "chs":
            title = f"⛔ Логи — ЧС состава ({sub_type})"
            color = disnake.Color.red()
        elif action_type == "unchs":
            title = f"✅ Логи — Снятие ЧС ({sub_type})"
            color = disnake.Color.green()
        elif action_type == "gender":
            title = "⚥ Логи смены гендера"
            color = disnake.Color.blurple()
        elif action_type == "verify":
            title = "✅ Логи — Верификация"
            color = disnake.Color.green()
        elif action_type == "nedopusk":
            title = "🚫 Логи — Недопуск"
            color = disnake.Color.dark_red()
        elif action_type == "unnedopusk":
            title = "🟢 Логи — Снятие недопуска"
            color = disnake.Color.green()
        elif action_type == "reprimand":
            title = f"📢 Логи — Выговор ({sub_type})"
            color = disnake.Color.red()
        elif action_type == "unreprimand":
            title = "🔇 Логи — Снятие выговора"
            color = disnake.Color.green()
        else:
            title = "Логи"
            color = disnake.Color.blue()

        embed = disnake.Embed(title=title, color=color, timestamp=datetime.datetime.now(datetime.timezone.utc))

        # Определяем, выдаём или снимаем
        if action_type.startswith("un") or action_type in ["unmute", "unban", "unwarn", "unremark", "unsuspension", "unchs", "unnedopusk", "unreprimand"]:
            embed.add_field(name="Снятие наказания", value="", inline=False)
        else:
            embed.add_field(name="Выдача наказания", value="", inline=False)

        # Исполнитель
        embed.add_field(name="Исполнитель", value=f"{inter.author.mention}\n• {inter.author.name}\n• ID: {inter.author.id}", inline=False)

        # Цель (нарушитель)
        embed.add_field(name="Нарушитель" if action_type not in ["gender", "verify"] else "Пользователь",
                        value=f"{target.mention}\n• {target.name}\n• ID: {target.id}", inline=False)

        # Длительность (если есть)
        if duration:
            if isinstance(duration, str):
                embed.add_field(name="Длительность", value=duration, inline=False)
            else:
                embed.add_field(name="Длительность", value=f"<t:{int(duration)}:R>", inline=False)

        # Причина / описание
        if reason:
            embed.add_field(name="Причина" if action_type not in ["gender"] else "Гендер", value=reason, inline=False)

        # Для смены гендера добавляем поле "Гендер"
        if action_type == "gender" and gender:
            embed.add_field(name="Гендер", value=gender, inline=False)

        # Дата внизу (уже есть timestamp, но можно добавить явно)
        embed.set_footer(text=f"{datetime.datetime.now(datetime.timezone.utc).strftime('%d/%m/%Y, %H:%M')}")

        await channel.send(embed=embed)

    # ------------------------------------------------------------------
    # Команда /action
    # ------------------------------------------------------------------
    @commands.slash_command(name="action", description="Панель модерации")
    async def action(self, inter: disnake.AppCmdInter, user: disnake.Member):
        if not self._is_staff(inter.author):
            await inter.response.send_message("❌ Эта команда доступна только персоналу.", ephemeral=True)
            return

        embed = disnake.Embed(
            title=f"🛠 Взаимодействие с участником – {user.display_name}",
            description=(
                f"- ID: {user.id}\n"
                f"- Дата входа: <t:{int(user.joined_at.timestamp())}:D>\n"
                f"- Дата создания аккаунта: <t:{int(user.created_at.timestamp())}:D>"
            ),
            color=disnake.Color.blue()
        )
        view = await ActionView.create(self, user, inter.author)
        await inter.response.send_message(embed=embed, view=view, ephemeral=True)

    # ------------------------------------------------------------------
    # Обработчики кнопок
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        parts = custom_id.split('_')
        action = parts[0]
        
        # Обработка мута (custom_id: mute_text_123, mute_voice_123)
        if action == "mute" and len(parts) >= 3:
            mute_type = parts[1]  # text или voice
            target_id = int(parts[2])
            target = inter.guild.get_member(target_id)
            await self.handle_mute(inter, target, mute_type)
            return

        # Остальные кнопки: формат "действие_id"
        target_id = int(parts[1]) if len(parts) > 1 else None
        target = inter.guild.get_member(target_id) if target_id else None

        handlers = {
            "ban": self.handle_ban,
            "unban": self.handle_unban,
            "suspension": self.handle_suspension,
            "unsuspension": self.handle_unsuspension,
            "warn": self.handle_warn,
            "unwarn": self.handle_unwarn,
            "remark": self.handle_remark,
            "unremark": self.handle_unremark,
            "unmute": self.handle_unmute,
            "changegender": self.handle_change_gender,
            "verify": self.handle_verify,
            "nedopusk": self.handle_nedopusk,
            "unnedopusk": self.handle_un_nedopusk,
            "history": self.handle_history,
            "nickhistory": self.handle_nick_history,
            "reprimand": self.handle_reprimand,
            "unreprimand": self.handle_unreprimand,
            "chs": self.handle_chs,
            "unchs": self.handle_unchs,
        }

        handler = handlers.get(action)
        if handler:
            await handler(inter, target)

    # ------------------------------------------------------------------
    # Обработчики действий (все с проверками прав и вызовом логов)
    # ------------------------------------------------------------------
    async def handle_ban(self, inter, target):
        if not (self._check_permission(inter.author, "moderator") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        if has_active_punishment(target.id, self.config["roles"]["ban"]):
            await inter.response.send_message("❌ Пользователь уже забанен.", ephemeral=True)
            return
        modal = BanModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_unban(self, inter, target):
        if not (self._check_permission(inter.author, "moderator") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        if not has_active_punishment(target.id, self.config["roles"]["ban"]):
            await inter.response.send_message("❌ У пользователя нет активного бана.", ephemeral=True)
            return
        modal = UnbanModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_suspension(self, inter, target):
        if not self._has_full_access(inter.author):
            await inter.response.send_message("❌ Только администратор может выдавать отстранения.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        role_id = self.config["roles"].get("ostranenie")
        if role_id and has_active_punishment(target.id, role_id):
            await inter.response.send_message("❌ У пользователя уже есть активное отстранение.", ephemeral=True)
            return
        modal = SuspensionModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_unsuspension(self, inter, target):
        if not self._has_full_access(inter.author):
            await inter.response.send_message("❌ Только администратор может снимать отстранения.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        role_id = self.config["roles"].get("ostranenie")
        if not role_id or not has_active_punishment(target.id, role_id):
            await inter.response.send_message("❌ У пользователя нет активного отстранения.", ephemeral=True)
            return
        modal = UnsuspensionModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_warn(self, inter, target):
        if not (self._check_permission(inter.author, "moderator") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        modal = WarnModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_unwarn(self, inter, target):
        if not (self._check_permission(inter.author, "moderator") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        warn_roles = [self.config["roles"].get(f"warn_{b}") for b in ["support","moderator","control","admin"] if self.config["roles"].get(f"warn_{b}")]
        if not any(has_active_punishment(target.id, rid) for rid in warn_roles if rid):
            await inter.response.send_message("❌ У пользователя нет активных предупреждений.", ephemeral=True)
            return
        modal = UnwarnModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_remark(self, inter, target):
        if not (self._check_permission(inter.author, "moderator") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        role_id = self.config["roles"].get("remark")
        if role_id and has_active_punishment(target.id, role_id):
            await inter.response.send_message("❌ У пользователя уже есть активное замечание.", ephemeral=True)
            return
        modal = RemarkModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_unremark(self, inter, target):
        if not (self._check_permission(inter.author, "moderator") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        role_id = self.config["roles"].get("remark")
        if not role_id or not has_active_punishment(target.id, role_id):
            await inter.response.send_message("❌ У пользователя нет активного замечания.", ephemeral=True)
            return
        modal = UnremarkModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_mute(self, inter, target, mute_type):
        if not (self._check_permission(inter.author, "moderator") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        role_id = self.config["roles"]["mute_text"] if mute_type == "text" else self.config["roles"]["mute_voice"]
        if has_active_punishment(target.id, role_id):
            await inter.response.send_message(f"❌ У пользователя уже есть {'текстовый' if mute_type=='text' else 'голосовой'} мут.", ephemeral=True)
            return
        modal = MuteModal(self, target, mute_type)
        await inter.response.send_modal(modal)

    async def handle_unmute(self, inter, target):
        if not (self._check_permission(inter.author, "moderator") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        text_mute = has_active_punishment(target.id, self.config["roles"]["mute_text"])
        voice_mute = has_active_punishment(target.id, self.config["roles"]["mute_voice"])
        if not (text_mute or voice_mute):
            await inter.response.send_message("❌ У пользователя нет активного мута.", ephemeral=True)
            return
        modal = UnmuteModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_change_gender(self, inter, target):
        if not (self._check_permission(inter.author, "support") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        view = GenderView(self, target, change=True)
        await inter.response.send_message("Выберите новый пол:", view=view, ephemeral=True)

    async def handle_verify(self, inter, target):
        if not (self._check_permission(inter.author, "support") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        unverified_role = self.config["roles"]["unverified"]
        if unverified_role not in [r.id for r in target.roles]:
            await inter.response.send_message("❌ Верифицировать можно только неверифицированного пользователя.", ephemeral=True)
            return
        view = GenderView(self, target, change=False)
        await inter.response.send_message("Выберите пол для верификации:", view=view, ephemeral=True)

    async def handle_nedopusk(self, inter, target):
        if not (self._check_permission(inter.author, "support") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        unverified_role = self.config["roles"]["unverified"]
        if unverified_role not in [r.id for r in target.roles]:
            await inter.response.send_message("❌ Недопуск можно выдать только неверифицированному пользователю.", ephemeral=True)
            return
        if has_active_punishment(target.id, self.config["roles"]["nedopusk"]):
            await inter.response.send_message("❌ У пользователя уже есть недопуск.", ephemeral=True)
            return
        modal = NedopuskModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_un_nedopusk(self, inter, target):
        if not (self._check_permission(inter.author, "support") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        if not has_active_punishment(target.id, self.config["roles"]["nedopusk"]):
            await inter.response.send_message("❌ У пользователя нет недопуска.", ephemeral=True)
            return
        modal = UnNedopuskModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_history(self, inter, target):
        if not self._is_staff(inter.author):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            target = inter.author
        data = load_punishments()
        user_data = data.get(str(target.id), [])
        if not user_data:
            await inter.response.send_message("📭 История нарушений отсутствует.", ephemeral=True)
            return
        embed = disnake.Embed(title=f"📜 История нарушений {target.display_name}", color=disnake.Color.orange())
        for i, p in enumerate(user_data[-10:], 1):
            dt = datetime.datetime.fromtimestamp(p["issued_at"]).strftime("%d.%m.%Y %H:%M")
            embed.add_field(
                name=f"{i}. {p['type']} ({dt})",
                value=f"Причина: {p['reason']}\nРоль: <@&{p['role_id']}>",
                inline=False
            )
        await inter.response.send_message(embed=embed, ephemeral=True)

    async def handle_nick_history(self, inter, target):
        if not self._is_staff(inter.author):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        await inter.response.send_message("Используйте команду `/history_nick` для просмотра истории никнеймов.", ephemeral=True)

    async def handle_reprimand(self, inter, target):
        if not self._has_full_access(inter.author):
            await inter.response.send_message("❌ Только администратор может выдавать выговоры.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        warn_roles = [self.config["roles"].get(f"warn_{b}") for b in ["support","moderator","control","admin"] if self.config["roles"].get(f"warn_{b}")]
        if any(has_active_punishment(target.id, rid) for rid in warn_roles if rid):
            await inter.response.send_message("❌ У пользователя уже есть активный выговор.", ephemeral=True)
            return
        view = ReprimandBranchView(self, target)
        await inter.response.send_message("Выберите ветку для выговора:", view=view, ephemeral=True)

    async def handle_unreprimand(self, inter, target):
        if not self._has_full_access(inter.author):
            await inter.response.send_message("❌ Только администратор может снимать выговоры.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        warn_roles = [self.config["roles"].get(f"warn_{b}") for b in ["support","moderator","control","admin"] if self.config["roles"].get(f"warn_{b}")]
        if not any(has_active_punishment(target.id, rid) for rid in warn_roles if rid):
            await inter.response.send_message("❌ У пользователя нет активных выговоров.", ephemeral=True)
            return
        modal = UnreprimandModal(self, target)
        await inter.response.send_modal(modal)

    async def handle_chs(self, inter, target):
        if not self._has_full_access(inter.author):
            await inter.response.send_message("❌ Только администратор может выдавать ЧС состава.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        chs_roles = [self.config["roles"].get(f"chs_{b}") for b in ["support","moderator","control","admin","common"] if self.config["roles"].get(f"chs_{b}")]
        if any(has_active_punishment(target.id, rid) for rid in chs_roles if rid):
            await inter.response.send_message("❌ У пользователя уже есть ЧС состава.", ephemeral=True)
            return
        view = CHSBranchView(self, target)
        await inter.response.send_message("Выберите ветку для ЧС:", view=view, ephemeral=True)

    async def handle_unchs(self, inter, target):
        if not self._has_full_access(inter.author):
            await inter.response.send_message("❌ Только администратор может снимать ЧС состава.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        chs_roles = [self.config["roles"].get(f"chs_{b}") for b in ["support","moderator","control","admin","common"] if self.config["roles"].get(f"chs_{b}")]
        if not any(has_active_punishment(target.id, rid) for rid in chs_roles if rid):
            await inter.response.send_message("❌ У пользователя нет активного ЧС.", ephemeral=True)
            return
        modal = UnCHSModal(self, target)
        await inter.response.send_modal(modal)


# ==================== VIEWS (ДЛЯ ВЫБОРА) ====================

class DisableableButton(disnake.ui.Button):
    pass

class ActionView(disnake.ui.View):
    @classmethod
    async def create(cls, cog, target, moderator):
        self = cls(timeout=180)
        self.cog = cog
        self.target = target
        self.moderator = moderator

        violations_count = count_punishments(target.id)
        nick_count = count_nicknames(target.id)

        has_ban = has_active_punishment(target.id, cog.config["roles"]["ban"])
        has_mute_text = has_active_punishment(target.id, cog.config["roles"]["mute_text"])
        has_mute_voice = has_active_punishment(target.id, cog.config["roles"]["mute_voice"])
        has_nedopusk = has_active_punishment(target.id, cog.config["roles"]["nedopusk"])
        remark_role = cog.config["roles"].get("remark")
        has_remark = has_active_punishment(target.id, remark_role) if remark_role else False

        warn_roles = [cog.config["roles"].get(f"warn_{b}") for b in ["support","moderator","control","admin"] if cog.config["roles"].get(f"warn_{b}")]
        has_warn = any(has_active_punishment(target.id, rid) for rid in warn_roles if rid)

        chs_roles = [cog.config["roles"].get(f"chs_{b}") for b in ["support","moderator","control","admin","common"] if cog.config["roles"].get(f"chs_{b}")]
        has_chs = any(has_active_punishment(target.id, rid) for rid in chs_roles if rid)

        suspension_role = cog.config["roles"].get("ostranenie")
        has_suspension = has_active_punishment(target.id, suspension_role) if suspension_role else False

        has_full = cog._has_full_access(moderator)
        is_mod = cog._check_permission(moderator, "moderator") or has_full
        is_support = cog._check_permission(moderator, "support") or has_full
        is_admin = cog._check_permission(moderator, "admin") or has_full

        # ---- Модератор ----
        if is_mod:
            self.add_item(DisableableButton(
                label="🔨 Забанить",
                style=disnake.ButtonStyle.danger,
                custom_id=f"ban_{target.id}",
                disabled=has_ban
            ))
            self.add_item(DisableableButton(
                label="🔓 Разбанить",
                style=disnake.ButtonStyle.success,
                custom_id=f"unban_{target.id}",
                disabled=not has_ban
            ))
            self.add_item(DisableableButton(
                label="⏳ Выдать отстранение",
                style=disnake.ButtonStyle.secondary,
                custom_id=f"suspension_{target.id}",
                disabled=has_suspension
            ))
            self.add_item(DisableableButton(
                label="🔄 Снять отстранение",
                style=disnake.ButtonStyle.secondary,
                custom_id=f"unsuspension_{target.id}",
                disabled=not has_suspension
            ))
            self.add_item(DisableableButton(
                label="🔇 Выдать мут (текст)",
                style=disnake.ButtonStyle.secondary,
                custom_id=f"mute_text_{target.id}",
                disabled=has_mute_text
            ))
            self.add_item(DisableableButton(
                label="🔊 Выдать мут (голос)",
                style=disnake.ButtonStyle.secondary,
                custom_id=f"mute_voice_{target.id}",
                disabled=has_mute_voice
            ))
            self.add_item(DisableableButton(
                label="✅ Снять мут",
                style=disnake.ButtonStyle.secondary,
                custom_id=f"unmute_{target.id}",
                disabled=not (has_mute_text or has_mute_voice)
            ))
            self.add_item(DisableableButton(
                label="⚠ Выдать предупреждение",
                style=disnake.ButtonStyle.secondary,
                custom_id=f"warn_{target.id}",
                disabled=False
            ))
            self.add_item(DisableableButton(
                label="✅ Снять предупреждение",
                style=disnake.ButtonStyle.secondary,
                custom_id=f"unwarn_{target.id}",
                disabled=not has_warn
            ))
            if remark_role:
                self.add_item(DisableableButton(
                    label="📝 Выдать замечание",
                    style=disnake.ButtonStyle.secondary,
                    custom_id=f"remark_{target.id}",
                    disabled=has_remark
                ))
                self.add_item(DisableableButton(
                    label="✅ Снять замечание",
                    style=disnake.ButtonStyle.secondary,
                    custom_id=f"unremark_{target.id}",
                    disabled=not has_remark
                ))

        # ---- Саппорт ----
        if is_support:
            self.add_item(DisableableButton(
                label="⚥ Сменить пол",
                style=disnake.ButtonStyle.blurple,
                custom_id=f"changegender_{target.id}",
                disabled=False
            ))
            unverified_role = cog.config["roles"]["unverified"]
            can_verify = unverified_role in [r.id for r in target.roles]
            self.add_item(DisableableButton(
                label="✅ Верифицировать",
                style=disnake.ButtonStyle.green,
                custom_id=f"verify_{target.id}",
                disabled=not can_verify
            ))
            self.add_item(DisableableButton(
                label="🚫 Выдать недопуск",
                style=disnake.ButtonStyle.gray,
                custom_id=f"nedopusk_{target.id}",
                disabled=has_nedopusk or not can_verify
            ))
            self.add_item(DisableableButton(
                label="🟢 Снять недопуск",
                style=disnake.ButtonStyle.gray,
                custom_id=f"unnedopusk_{target.id}",
                disabled=not has_nedopusk
            ))

        # ---- Для всех стафф (истории) ----
        if is_mod or is_support or is_admin:
            self.add_item(DisableableButton(
                label=f"📜 История нарушений — {violations_count}",
                style=disnake.ButtonStyle.blurple,
                custom_id=f"history_{target.id}",
                disabled=False
            ))
            self.add_item(DisableableButton(
                label=f"📝 История никнеймов — {nick_count}",
                style=disnake.ButtonStyle.blurple,
                custom_id=f"nickhistory_{target.id}",
                disabled=False
            ))

        # ---- Админ (выговор, ЧС) ----
        if is_admin:
            self.add_item(DisableableButton(
                label="📢 Выдать выговор",
                style=disnake.ButtonStyle.red,
                custom_id=f"reprimand_{target.id}",
                disabled=has_warn
            ))
            self.add_item(DisableableButton(
                label="🔇 Снять выговор",
                style=disnake.ButtonStyle.red,
                custom_id=f"unreprimand_{target.id}",
                disabled=not has_warn
            ))
            self.add_item(DisableableButton(
                label="⛔ Добавить в ЧС состава",
                style=disnake.ButtonStyle.red,
                custom_id=f"chs_{target.id}",
                disabled=has_chs
            ))
            self.add_item(DisableableButton(
                label="✅ Убрать из ЧС состава",
                style=disnake.ButtonStyle.red,
                custom_id=f"unchs_{target.id}",
                disabled=not has_chs
            ))

        return self


class GenderView(disnake.ui.View):
    def __init__(self, cog, target, change):
        super().__init__(timeout=60)
        self.cog = cog
        self.target = target
        self.change = change  # True - смена пола, False - верификация

    @disnake.ui.button(label="♂ Мужской", style=disnake.ButtonStyle.blurple, custom_id="gender_male")
    async def male_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.process_gender(inter, "male")

    @disnake.ui.button(label="♀ Женский", style=disnake.ButtonStyle.blurple, custom_id="gender_female")
    async def female_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.process_gender(inter, "female")

    async def process_gender(self, inter, gender):
        male_role = self.cog.config["roles"]["verif_male"]
        female_role = self.cog.config["roles"]["verif_female"]
        unverified_role = self.cog.config["roles"]["unverified"]

        # Снимаем все гендерные роли
        await self.target.remove_roles(inter.guild.get_role(male_role), reason="Смена пола/верификация")
        await self.target.remove_roles(inter.guild.get_role(female_role), reason="Смена пола/верификация")

        # Выдаём выбранную
        new_role = male_role if gender == "male" else female_role
        await self.target.add_roles(inter.guild.get_role(new_role), reason="Смена пола/верификация")

        if not self.change:  # верификация - снимаем unverified
            await self.target.remove_roles(inter.guild.get_role(unverified_role), reason="Верификация")
            # Перемещаем в общий голосовой канал (опционально)
            # Например, в первый попавшийся
            for vc in inter.guild.voice_channels:
                await self.target.move_to(vc)
                break

        # Логирование через общий метод
        await self.cog._send_log(
            inter,
            "gender" if self.change else "verify",
            None,
            self.target,
            gender=gender
        )

        await inter.response.send_message(f"✅ Пол успешно изменён на {'мужской' if gender=='male' else 'женский'}.", ephemeral=True)


class ReprimandBranchView(disnake.ui.View):
    def __init__(self, cog, target):
        super().__init__(timeout=60)
        self.cog = cog
        self.target = target

    @disnake.ui.button(label="Саппорты", style=disnake.ButtonStyle.red, custom_id="reprimand_support")
    async def support_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        modal = ReprimandModal(self.cog, self.target, "support")
        await inter.response.send_modal(modal)

    @disnake.ui.button(label="Модераторы", style=disnake.ButtonStyle.red, custom_id="reprimand_moderator")
    async def moderator_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        modal = ReprimandModal(self.cog, self.target, "moderator")
        await inter.response.send_modal(modal)

    @disnake.ui.button(label="Контроль", style=disnake.ButtonStyle.red, custom_id="reprimand_control")
    async def control_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        modal = ReprimandModal(self.cog, self.target, "control")
        await inter.response.send_modal(modal)

    @disnake.ui.button(label="Администрация", style=disnake.ButtonStyle.red, custom_id="reprimand_admin")
    async def admin_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        modal = ReprimandModal(self.cog, self.target, "admin")
        await inter.response.send_modal(modal)


class CHSBranchView(disnake.ui.View):
    def __init__(self, cog, target):
        super().__init__(timeout=60)
        self.cog = cog
        self.target = target

    @disnake.ui.button(label="Саппорты", style=disnake.ButtonStyle.red, custom_id="chs_support")
    async def support_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        modal = CHSModal(self.cog, self.target, "support")
        await inter.response.send_modal(modal)

    @disnake.ui.button(label="Модераторы", style=disnake.ButtonStyle.red, custom_id="chs_moderator")
    async def moderator_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        modal = CHSModal(self.cog, self.target, "moderator")
        await inter.response.send_modal(modal)

    @disnake.ui.button(label="Контроль", style=disnake.ButtonStyle.red, custom_id="chs_control")
    async def control_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        modal = CHSModal(self.cog, self.target, "control")
        await inter.response.send_modal(modal)

    @disnake.ui.button(label="Администрация", style=disnake.ButtonStyle.red, custom_id="chs_admin")
    async def admin_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        modal = CHSModal(self.cog, self.target, "admin")
        await inter.response.send_modal(modal)

    @disnake.ui.button(label="Общий ЧС", style=disnake.ButtonStyle.red, custom_id="chs_common")
    async def common_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        modal = CHSModal(self.cog, self.target, "common")
        await inter.response.send_modal(modal)


# ==================== МОДАЛЬНЫЕ ОКНА ====================

class BanModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина",
                placeholder="Укажите причину бана",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            ),
            disnake.ui.TextInput(
                label="Срок",
                placeholder="15m, 30m, 1h, или оставьте пустым",
                custom_id="duration",
                required=False,
                max_length=10,
            )
        ]
        super().__init__(title=f"Бан {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        duration_str = inter.text_values.get("duration")
        end_time = None
        if duration_str:
            delta = parse_time(duration_str)
            if delta:
                end_time = (datetime.datetime.now(datetime.timezone.utc) + delta).timestamp()
            else:
                await inter.response.send_message("Неверный формат срока.", ephemeral=True)
                return

        role = inter.guild.get_role(self.cog.config["roles"]["ban"])
        await self.target.edit(roles=[role])
        add_punishment(self.target.id, "ban", role.id, end_time, reason)

        await self.cog._send_log(inter, "ban", None, self.target, end_time, reason)
        await self.cog._dm_user(self.target, f"🚫 Вы получили бан.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Пользователь {self.target.mention} забанен.", ephemeral=True)


class UnbanModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина снятия",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Разбан {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        role = inter.guild.get_role(self.cog.config["roles"]["ban"])
        if role in self.target.roles:
            await self.target.remove_roles(role, reason=reason)
            remove_punishment(self.target.id, role.id)
            await self.cog._send_log(inter, "unban", None, self.target, reason=reason)
            await self.cog._dm_user(self.target, f"✅ Ваш бан снят.\nПричина: {reason}")
            await inter.response.send_message(f"✅ Бан снят с {self.target.mention}.", ephemeral=True)
        else:
            await inter.response.send_message("❌ У пользователя нет роли бана.", ephemeral=True)


class WarnModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина",
                placeholder="Укажите причину предупреждения",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Предупреждение {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        # Определяем роль предупреждения в зависимости от ролей цели (упрощённо)
        if self.cog._check_permission(self.target, "moderator"):
            role_id = self.cog.config["roles"]["warn_moderator"]
            warn_type = "moderator_warn"
        else:
            role_id = self.cog.config["roles"]["warn_support"]
            warn_type = "support_warn"

        role = inter.guild.get_role(role_id)
        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, warn_type, role.id, None, reason)

        await self.cog._send_log(inter, "warn", None, self.target, reason=reason)
        await self.cog._dm_user(self.target, f"⚠ Вы получили предупреждение.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Предупреждение выдано {self.target.mention}.", ephemeral=True)


class UnwarnModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина снятия",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Снятие предупреждения {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        data = load_punishments()
        user_data = data.get(str(self.target.id), [])
        warn_punishment = None
        for p in user_data:
            if p["type"] in ["support_warn", "moderator_warn"]:
                warn_punishment = p
                break

        if not warn_punishment:
            await inter.response.send_message("❌ У пользователя нет активных предупреждений.", ephemeral=True)
            return

        role = inter.guild.get_role(warn_punishment["role_id"])
        if role in self.target.roles:
            await self.target.remove_roles(role, reason=reason)
            remove_punishment(self.target.id, role.id)
            await self.cog._send_log(inter, "unwarn", None, self.target, reason=reason)
            await self.cog._dm_user(self.target, f"✅ Ваше предупреждение снято.\nПричина: {reason}")
            await inter.response.send_message(f"✅ Предупреждение снято с {self.target.mention}.", ephemeral=True)
        else:
            await inter.response.send_message("❌ Ошибка: роль предупреждения не найдена.", ephemeral=True)


class RemarkModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина замечания",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Замечание {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        role_id = self.cog.config["roles"]["remark"]
        role = inter.guild.get_role(role_id)
        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, "remark", role.id, None, reason)
        await self.cog._send_log(inter, "remark", None, self.target, reason=reason)
        await self.cog._dm_user(self.target, f"📝 Вы получили замечание.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Замечание выдано {self.target.mention}.", ephemeral=True)


class UnremarkModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина снятия",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Снятие замечания {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        role_id = self.cog.config["roles"]["remark"]
        role = inter.guild.get_role(role_id)
        if role in self.target.roles:
            await self.target.remove_roles(role, reason=reason)
            remove_punishment(self.target.id, role.id)
            await self.cog._send_log(inter, "unremark", None, self.target, reason=reason)
            await self.cog._dm_user(self.target, f"✅ Ваше замечание снято.\nПричина: {reason}")
            await inter.response.send_message(f"✅ Замечание снято с {self.target.mention}.", ephemeral=True)
        else:
            await inter.response.send_message("❌ У пользователя нет замечания.", ephemeral=True)


class MuteModal(disnake.ui.Modal):
    def __init__(self, cog, target, mute_type):
        self.cog = cog
        self.target = target
        self.mute_type = mute_type
        components = [
            disnake.ui.TextInput(
                label="Причина мута",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            ),
            disnake.ui.TextInput(
                label="Срок",
                placeholder="15m, 30m, 1h, или оставьте пустым",
                custom_id="duration",
                required=False,
                max_length=10,
            )
        ]
        title = f"{'Текстовый' if mute_type=='text' else 'Голосовой'} мут {target.display_name}"
        super().__init__(title=title, components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        duration_str = inter.text_values.get("duration")
        end_time = None
        if duration_str:
            delta = parse_time(duration_str)
            if delta:
                end_time = (datetime.datetime.now(datetime.timezone.utc) + delta).timestamp()
            else:
                await inter.response.send_message("Неверный формат срока.", ephemeral=True)
                return

        role_id = self.cog.config["roles"]["mute_text"] if self.mute_type == "text" else self.cog.config["roles"]["mute_voice"]
        role = inter.guild.get_role(role_id)

        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, f"mute_{self.mute_type}", role.id, end_time, reason)

        await self.cog._send_log(inter, "mute", self.mute_type, self.target, end_time, reason)
        await self.cog._dm_user(self.target, f"🔇 Вы получили {'текстовый' if self.mute_type=='text' else 'голосовой'} мут.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Мут выдан {self.target.mention}.", ephemeral=True)


class UnmuteModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина снятия мута",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Снятие мута {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        data = load_punishments()
        user_data = data.get(str(self.target.id), [])
        mute_punishment = None
        for p in user_data:
            if p["type"].startswith("mute_"):
                mute_punishment = p
                break

        if not mute_punishment:
            await inter.response.send_message("❌ У пользователя нет активного мута.", ephemeral=True)
            return

        role = inter.guild.get_role(mute_punishment["role_id"])
        if role in self.target.roles:
            await self.target.remove_roles(role, reason=reason)
            remove_punishment(self.target.id, role.id)
            await self.cog._send_log(inter, "unmute", None, self.target, reason=reason)
            await self.cog._dm_user(self.target, f"✅ Ваш мут снят.\nПричина: {reason}")
            await inter.response.send_message(f"✅ Мут снят с {self.target.mention}.", ephemeral=True)
        else:
            await inter.response.send_message("❌ Ошибка: роль мута не найдена.", ephemeral=True)


class NedopuskModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина недопуска",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Недопуск {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        nedopusk_role = inter.guild.get_role(self.cog.config["roles"]["nedopusk"])
        unverified_role = inter.guild.get_role(self.cog.config["roles"]["unverified"])

        await self.target.remove_roles(unverified_role, reason=reason)
        await self.target.add_roles(nedopusk_role, reason=reason)
        add_punishment(self.target.id, "nedopusk", nedopusk_role.id, None, reason)

        # Кик с голосового канала (перемещение в none)
        try:
            await self.target.move_to(None)
        except:
            pass

        await self.cog._send_log(inter, "nedopusk", None, self.target, reason=reason)
        await self.cog._dm_user(self.target, f"🚫 Вам выдан недопуск.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Недопуск выдан {self.target.mention}.", ephemeral=True)


class UnNedopuskModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина снятия недопуска",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Снятие недопуска {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        nedopusk_role = inter.guild.get_role(self.cog.config["roles"]["nedopusk"])

        if nedopusk_role in self.target.roles:
            await self.target.remove_roles(nedopusk_role, reason=reason)
            remove_punishment(self.target.id, nedopusk_role.id)
            await self.cog._send_log(inter, "unnedopusk", None, self.target, reason=reason)
            await self.cog._dm_user(self.target, f"✅ Ваш недопуск снят.\nПричина: {reason}")
            await inter.response.send_message(f"✅ Недопуск снят с {self.target.mention}.", ephemeral=True)
        else:
            await inter.response.send_message("❌ У пользователя нет недопуска.", ephemeral=True)


class ReprimandModal(disnake.ui.Modal):
    def __init__(self, cog, target, branch):
        self.cog = cog
        self.target = target
        self.branch = branch
        components = [
            disnake.ui.TextInput(
                label="Причина выговора",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            ),
            disnake.ui.TextInput(
                label="Срок",
                placeholder="1w, 1m, или оставьте пустым",
                custom_id="duration",
                required=False,
                max_length=10,
            )
        ]
        super().__init__(title=f"Выговор ({branch}) {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        duration_str = inter.text_values.get("duration")
        end_time = None
        if duration_str:
            delta = parse_time(duration_str)
            if delta:
                end_time = (datetime.datetime.now(datetime.timezone.utc) + delta).timestamp()
            else:
                await inter.response.send_message("Неверный формат срока.", ephemeral=True)
                return

        role_id = self.cog.config["roles"][f"warn_{self.branch}"]
        role = inter.guild.get_role(role_id)

        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, f"reprimand_{self.branch}", role.id, end_time, reason)

        await self.cog._send_log(inter, "reprimand", self.branch, self.target, end_time, reason)
        await self.cog._dm_user(self.target, f"📢 Вы получили выговор ({self.branch}).\nПричина: {reason}")
        await inter.response.send_message(f"✅ Выговор ({self.branch}) выдан {self.target.mention}.", ephemeral=True)


class UnreprimandModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина снятия выговора",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Снятие выговора {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        data = load_punishments()
        user_data = data.get(str(self.target.id), [])
        reprimand_punishment = None
        for p in user_data:
            if p["type"].startswith("reprimand_"):
                reprimand_punishment = p
                break

        if not reprimand_punishment:
            await inter.response.send_message("❌ У пользователя нет активных выговоров.", ephemeral=True)
            return

        role = inter.guild.get_role(reprimand_punishment["role_id"])
        if role in self.target.roles:
            await self.target.remove_roles(role, reason=reason)
            remove_punishment(self.target.id, role.id)
            branch = reprimand_punishment["type"].replace("reprimand_", "")
            await self.cog._send_log(inter, "unreprimand", branch, self.target, reason=reason)
            await self.cog._dm_user(self.target, f"✅ Ваш выговор снят.\nПричина: {reason}")
            await inter.response.send_message(f"✅ Выговор снят с {self.target.mention}.", ephemeral=True)
        else:
            await inter.response.send_message("❌ Ошибка: роль выговора не найдена.", ephemeral=True)


class CHSModal(disnake.ui.Modal):
    def __init__(self, cog, target, branch):
        self.cog = cog
        self.target = target
        self.branch = branch
        components = [
            disnake.ui.TextInput(
                label="Причина ЧС",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"ЧС состава ({branch}) {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        role_id = self.cog.config["roles"][f"chs_{self.branch}"]
        role = inter.guild.get_role(role_id)

        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, f"chs_{self.branch}", role.id, None, reason)

        await self.cog._send_log(inter, "chs", self.branch, self.target, reason=reason)
        await self.cog._dm_user(self.target, f"⛔ Вы попали в ЧС состава ({self.branch}).\nПричина: {reason}")
        await inter.response.send_message(f"✅ ЧС ({self.branch}) выдано {self.target.mention}.", ephemeral=True)


class UnCHSModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина снятия ЧС",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Снятие ЧС {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        data = load_punishments()
        user_data = data.get(str(self.target.id), [])
        chs_punishment = None
        for p in user_data:
            if p["type"].startswith("chs_"):
                chs_punishment = p
                break

        if not chs_punishment:
            await inter.response.send_message("❌ У пользователя нет активного ЧС.", ephemeral=True)
            return

        role = inter.guild.get_role(chs_punishment["role_id"])
        if role in self.target.roles:
            await self.target.remove_roles(role, reason=reason)
            remove_punishment(self.target.id, role.id)
            branch = chs_punishment["type"].replace("chs_", "")
            await self.cog._send_log(inter, "unchs", branch, self.target, reason=reason)
            await self.cog._dm_user(self.target, f"✅ Ваше ЧС снято.\nПричина: {reason}")
            await inter.response.send_message(f"✅ ЧС снято с {self.target.mention}.", ephemeral=True)
        else:
            await inter.response.send_message("❌ Ошибка: роль ЧС не найдена.", ephemeral=True)


class SuspensionModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина отстранения",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            ),
            disnake.ui.TextInput(
                label="Срок",
                placeholder="30m, 1h, или оставьте пустым",
                custom_id="duration",
                required=False,
                max_length=10,
            )
        ]
        super().__init__(title=f"Отстранение {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        duration_str = inter.text_values.get("duration")
        end_time = None
        if duration_str:
            delta = parse_time(duration_str)
            if delta:
                end_time = (datetime.datetime.now(datetime.timezone.utc) + delta).timestamp()
            else:
                await inter.response.send_message("Неверный формат срока.", ephemeral=True)
                return

        role_id = self.cog.config["roles"]["ostranenie"]
        role = inter.guild.get_role(role_id)

        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, "suspension", role.id, end_time, reason)

        await self.cog._send_log(inter, "suspension", None, self.target, end_time, reason)
        await self.cog._dm_user(self.target, f"⏳ Вы получили отстранение.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Отстранение выдано {self.target.mention}.", ephemeral=True)


class UnsuspensionModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина снятия отстранения",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Снятие отстранения {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        role_id = self.cog.config["roles"]["ostranenie"]
        role = inter.guild.get_role(role_id)

        if role in self.target.roles:
            await self.target.remove_roles(role, reason=reason)
            remove_punishment(self.target.id, role.id)
            await self.cog._send_log(inter, "unsuspension", None, self.target, reason=reason)
            await self.cog._dm_user(self.target, f"✅ Ваше отстранение снято.\nПричина: {reason}")
            await inter.response.send_message(f"✅ Отстранение снято с {self.target.mention}.", ephemeral=True)
        else:
            await inter.response.send_message("❌ У пользователя нет активного отстранения.", ephemeral=True)


def setup(bot):
    bot.add_cog(Action(bot))