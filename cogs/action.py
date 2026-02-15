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
        staff_roles = [
            "moderator", "support", "eventsmod", "creative",
            "clanmaster", "closemaker", "broadcaster",
            "admin", "developer", "owner"
        ]
        return any(self._check_permission(member, r) for r in staff_roles)

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

    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        custom_id = inter.component.custom_id
        skip = ("gender_", "reprimand_support", "reprimand_moderator", "reprimand_control", "reprimand_admin",
                "chs_support", "chs_moderator", "chs_control", "chs_admin", "chs_common")
        if custom_id.startswith(skip):
            return

        parts = custom_id.split('_')
        action = parts[0]
        
        if action == "mute" and len(parts) >= 3:
            mute_type = parts[1]
            try:
                target_id = int(parts[2])
            except ValueError:
                return
            target = inter.guild.get_member(target_id)
            await self.handle_mute(inter, target, mute_type)
            return
        
        try:
            target_id = int(parts[-1])
        except (ValueError, IndexError):
            return
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
        else:
            await inter.response.send_message("Неизвестное действие.", ephemeral=True)

    # ========== Вспомогательные методы ==========
    async def _send_log(self, guild, title, color, fields):
        embed = disnake.Embed(title=title, color=color)
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=False)
        await log_action(guild, self.config["log_channel"], embed)

    async def _dm_user(self, user, text):
        try:
            await user.send(text)
        except:
            pass

    # ========== Обработчики действий ==========
    async def handle_ban(self, inter, target):
        if not (self._check_permission(inter.author, "moderator") or self._has_full_access(inter.author)):
            await inter.response.send_message("❌ Недостаточно прав.", ephemeral=True)
            return
        if not target:
            await inter.response.send_message("❌ Пользователь не найден.", ephemeral=True)
            return
        ban_role = self.config["roles"].get("ban")
        if not ban_role:
            await inter.response.send_message("❌ Роль бана не настроена в конфиге.", ephemeral=True)
            return
        if has_active_punishment(target.id, ban_role):
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
        ban_role = self.config["roles"].get("ban")
        if not ban_role:
            await inter.response.send_message("❌ Роль бана не настроена.", ephemeral=True)
            return
        if not has_active_punishment(target.id, ban_role):
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
        role_id = self.config["roles"].get("mute_text") if mute_type == "text" else self.config["roles"].get("mute_voice")
        if not role_id:
            await inter.response.send_message("❌ Роль мута не настроена.", ephemeral=True)
            return
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
        mute_text_role = self.config["roles"].get("mute_text")
        mute_voice_role = self.config["roles"].get("mute_voice")
        text_mute = has_active_punishment(target.id, mute_text_role) if mute_text_role else False
        voice_mute = has_active_punishment(target.id, mute_voice_role) if mute_voice_role else False
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
        unverified_role = self.config["roles"].get("unverified")
        if not unverified_role:
            await inter.response.send_message("❌ Роль неверифицированного не настроена.", ephemeral=True)
            return
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
        unverified_role = self.config["roles"].get("unverified")
        if not unverified_role:
            await inter.response.send_message("❌ Роль неверифицированного не настроена.", ephemeral=True)
            return
        if unverified_role not in [r.id for r in target.roles]:
            await inter.response.send_message("❌ Недопуск можно выдать только неверифицированному пользователю.", ephemeral=True)
            return
        nedopusk_role = self.config["roles"].get("nedopusk")
        if not nedopusk_role:
            await inter.response.send_message("❌ Роль недопуска не настроена.", ephemeral=True)
            return
        if has_active_punishment(target.id, nedopusk_role):
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
        nedopusk_role = self.config["roles"].get("nedopusk")
        if not nedopusk_role:
            await inter.response.send_message("❌ Роль недопуска не настроена.", ephemeral=True)
            return
        if not has_active_punishment(target.id, nedopusk_role):
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


# ==========================================================================
# Классы View и Modal (все необходимые)
# ==========================================================================

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
        roles = cog.config["roles"]

        ban_role = roles.get("ban")
        mute_text_role = roles.get("mute_text")
        mute_voice_role = roles.get("mute_voice")
        nedopusk_role = roles.get("nedopusk")
        remark_role = roles.get("remark")
        unverified_role = roles.get("unverified")
        suspension_role = roles.get("ostranenie")

        has_ban = has_active_punishment(target.id, ban_role) if ban_role else False
        has_mute_text = has_active_punishment(target.id, mute_text_role) if mute_text_role else False
        has_mute_voice = has_active_punishment(target.id, mute_voice_role) if mute_voice_role else False
        has_nedopusk = has_active_punishment(target.id, nedopusk_role) if nedopusk_role else False
        has_remark = has_active_punishment(target.id, remark_role) if remark_role else False
        has_suspension = has_active_punishment(target.id, suspension_role) if suspension_role else False

        warn_roles = [roles.get(f"warn_{b}") for b in ["support","moderator","control","admin"] if roles.get(f"warn_{b}")]
        has_warn = any(has_active_punishment(target.id, rid) for rid in warn_roles if rid)

        chs_roles = [roles.get(f"chs_{b}") for b in ["support","moderator","control","admin","common"] if roles.get(f"chs_{b}")]
        has_chs = any(has_active_punishment(target.id, rid) for rid in chs_roles if rid)

        has_full = cog._has_full_access(moderator)
        is_mod = cog._check_permission(moderator, "moderator") or has_full
        is_support = cog._check_permission(moderator, "support") or has_full
        is_admin = cog._check_permission(moderator, "admin") or has_full

        if is_mod:
            if ban_role or has_full:
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
            if suspension_role or has_full:
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
            if mute_text_role or has_full:
                self.add_item(DisableableButton(
                    label="🔇 Выдать мут (текст)",
                    style=disnake.ButtonStyle.secondary,
                    custom_id=f"mute_text_{target.id}",
                    disabled=has_mute_text
                ))
            if mute_voice_role or has_full:
                self.add_item(DisableableButton(
                    label="🔊 Выдать мут (голос)",
                    style=disnake.ButtonStyle.secondary,
                    custom_id=f"mute_voice_{target.id}",
                    disabled=has_mute_voice
                ))
            if mute_text_role or mute_voice_role or has_full:
                self.add_item(DisableableButton(
                    label="✅ Снять мут",
                    style=disnake.ButtonStyle.secondary,
                    custom_id=f"unmute_{target.id}",
                    disabled=not (has_mute_text or has_mute_voice)
                ))
            if warn_roles or has_full:
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
            if remark_role or has_full:
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

        if is_support:
            if roles.get("verif_male") and roles.get("verif_female") or has_full:
                self.add_item(DisableableButton(
                    label="⚥ Сменить пол",
                    style=disnake.ButtonStyle.blurple,
                    custom_id=f"changegender_{target.id}",
                    disabled=False
                ))
            if unverified_role or has_full:
                can_verify = unverified_role in [r.id for r in target.roles] if unverified_role else False
                if roles.get("verif_male") and roles.get("verif_female") or has_full:
                    self.add_item(DisableableButton(
                        label="✅ Верифицировать",
                        style=disnake.ButtonStyle.green,
                        custom_id=f"verify_{target.id}",
                        disabled=not can_verify
                    ))
                if nedopusk_role or has_full:
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

        if is_admin:
            if warn_roles or has_full:
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
            if chs_roles or has_full:
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


# ===== Модальные окна =====

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

        role_id = self.cog.config["roles"].get("ban")
        if not role_id:
            await inter.response.send_message("❌ Роль бана не настроена.", ephemeral=True)
            return
        role = inter.guild.get_role(role_id)
        await self.target.edit(roles=[role])
        add_punishment(self.target.id, "ban", role.id, end_time, reason)

        embed = disnake.Embed(title="🔨 Бан", color=disnake.Color.red())
        embed.add_field(name="Модератор", value=inter.author.mention)
        embed.add_field(name="Нарушитель", value=self.target.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        if end_time:
            embed.add_field(name="Срок", value=f"до <t:{int(end_time)}:f>")
        else:
            embed.add_field(name="Срок", value="бессрочно")
        await log_action(inter.guild, self.cog.config["log_channel"], embed)

        await self.cog._dm_user(self.target, f"🚫 Вы получили бан.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Пользователь {self.target.mention} забанен.", ephemeral=True)


class UnbanModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина снятия бана",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Разбан {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        role_id = self.cog.config["roles"].get("ban")
        if not role_id:
            await inter.response.send_message("❌ Роль бана не настроена.", ephemeral=True)
            return
        role = inter.guild.get_role(role_id)
        if role in self.target.roles:
            await self.target.remove_roles(role, reason=reason)
            remove_punishment(self.target.id, role.id)

            embed = disnake.Embed(title="🔓 Разбан", color=disnake.Color.green())
            embed.add_field(name="Модератор", value=inter.author.mention)
            embed.add_field(name="Пользователь", value=self.target.mention)
            embed.add_field(name="Причина", value=reason, inline=False)
            await log_action(inter.guild, self.cog.config["log_channel"], embed)

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
                label="Причина предупреждения",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Предупреждение {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        # Определяем, какую роль предупреждения выдавать (упрощённо)
        if self.cog._check_permission(self.target, "moderator"):
            role_id = self.cog.config["roles"].get("warn_moderator")
            warn_type = "moderator_warn"
        else:
            role_id = self.cog.config["roles"].get("warn_support")
            warn_type = "support_warn"

        if not role_id:
            await inter.response.send_message("❌ Роль предупреждения не настроена.", ephemeral=True)
            return

        role = inter.guild.get_role(role_id)
        if role in self.target.roles:
            await inter.response.send_message("❌ У пользователя уже есть активное предупреждение данного типа.", ephemeral=True)
            return

        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, warn_type, role.id, None, reason)

        embed = disnake.Embed(title="⚠ Предупреждение", color=disnake.Color.orange())
        embed.add_field(name="Модератор", value=inter.author.mention)
        embed.add_field(name="Пользователь", value=self.target.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        await log_action(inter.guild, self.cog.config["log_channel"], embed)

        await self.cog._dm_user(self.target, f"⚠ Вы получили предупреждение.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Предупреждение выдано {self.target.mention}.", ephemeral=True)


class UnwarnModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина снятия предупреждения",
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

            embed = disnake.Embed(title="✅ Снятие предупреждения", color=disnake.Color.green())
            embed.add_field(name="Модератор", value=inter.author.mention)
            embed.add_field(name="Пользователь", value=self.target.mention)
            embed.add_field(name="Причина", value=reason, inline=False)
            await log_action(inter.guild, self.cog.config["log_channel"], embed)

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
        role_id = self.cog.config["roles"].get("remark")
        if not role_id:
            await inter.response.send_message("❌ Роль замечания не настроена.", ephemeral=True)
            return
        role = inter.guild.get_role(role_id)
        if role in self.target.roles:
            await inter.response.send_message("❌ У пользователя уже есть активное замечание.", ephemeral=True)
            return

        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, "remark", role.id, None, reason)

        embed = disnake.Embed(title="📝 Замечание", color=disnake.Color.orange())
        embed.add_field(name="Модератор", value=inter.author.mention)
        embed.add_field(name="Пользователь", value=self.target.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        await log_action(inter.guild, self.cog.config["log_channel"], embed)

        await self.cog._dm_user(self.target, f"📝 Вам вынесено замечание.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Замечание выдано {self.target.mention}.", ephemeral=True)


class UnremarkModal(disnake.ui.Modal):
    def __init__(self, cog, target):
        self.cog = cog
        self.target = target
        components = [
            disnake.ui.TextInput(
                label="Причина снятия замечания",
                placeholder="Укажите причину",
                custom_id="reason",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
            )
        ]
        super().__init__(title=f"Снятие замечания {target.display_name}", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        reason = inter.text_values["reason"]
        role_id = self.cog.config["roles"].get("remark")
        if not role_id:
            await inter.response.send_message("❌ Роль замечания не настроена.", ephemeral=True)
            return
        role = inter.guild.get_role(role_id)
        if role not in self.target.roles:
            await inter.response.send_message("❌ У пользователя нет активного замечания.", ephemeral=True)
            return

        await self.target.remove_roles(role, reason=reason)
        remove_punishment(self.target.id, role.id)

        embed = disnake.Embed(title="✅ Снятие замечания", color=disnake.Color.green())
        embed.add_field(name="Модератор", value=inter.author.mention)
        embed.add_field(name="Пользователь", value=self.target.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        await log_action(inter.guild, self.cog.config["log_channel"], embed)

        await self.cog._dm_user(self.target, f"✅ Ваше замечание снято.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Замечание снято с {self.target.mention}.", ephemeral=True)


class MuteModal(disnake.ui.Modal):
    def __init__(self, cog, target, mute_type):
        self.cog = cog
        self.target = target
        self.mute_type = mute_type  # "text" или "voice"
        title = f"{'Текстовый' if mute_type=='text' else 'Голосовой'} мут {target.display_name}"
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

        role_id = self.cog.config["roles"].get("mute_text") if self.mute_type == "text" else self.cog.config["roles"].get("mute_voice")
        if not role_id:
            await inter.response.send_message("❌ Роль мута не настроена.", ephemeral=True)
            return
        role = inter.guild.get_role(role_id)
        if role in self.target.roles:
            await inter.response.send_message(f"❌ У пользователя уже есть {'текстовый' if self.mute_type=='text' else 'голосовой'} мут.", ephemeral=True)
            return

        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, f"mute_{self.mute_type}", role.id, end_time, reason)

        embed = disnake.Embed(title=f"🔇 {'Текстовый' if self.mute_type=='text' else 'Голосовой'} мут", color=disnake.Color.dark_gray())
        embed.add_field(name="Модератор", value=inter.author.mention)
        embed.add_field(name="Пользователь", value=self.target.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        if end_time:
            embed.add_field(name="Срок", value=f"до <t:{int(end_time)}:f>")
        else:
            embed.add_field(name="Срок", value="бессрочно")
        await log_action(inter.guild, self.cog.config["log_channel"], embed)

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

            embed = disnake.Embed(title="🔊 Снятие мута", color=disnake.Color.green())
            embed.add_field(name="Модератор", value=inter.author.mention)
            embed.add_field(name="Пользователь", value=self.target.mention)
            embed.add_field(name="Причина", value=reason, inline=False)
            await log_action(inter.guild, self.cog.config["log_channel"], embed)

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
        nedopusk_rid = self.cog.config["roles"].get("nedopusk")
        unverified_rid = self.cog.config["roles"].get("unverified")
        if not nedopusk_rid or not unverified_rid:
            await inter.response.send_message("❌ Роли не настроены.", ephemeral=True)
            return
        nedopusk_role = inter.guild.get_role(nedopusk_rid)
        unverified_role = inter.guild.get_role(unverified_rid)

        if nedopusk_role in self.target.roles:
            await inter.response.send_message("❌ У пользователя уже есть недопуск.", ephemeral=True)
            return

        await self.target.remove_roles(unverified_role, reason=reason)
        await self.target.add_roles(nedopusk_role, reason=reason)
        add_punishment(self.target.id, "nedopusk", nedopusk_role.id, None, reason)

        embed = disnake.Embed(title="🚫 Недопуск", color=disnake.Color.dark_red())
        embed.add_field(name="Модератор", value=inter.author.mention)
        embed.add_field(name="Пользователь", value=self.target.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        await log_action(inter.guild, self.cog.config["log_channel"], embed)

        await self.cog._dm_user(self.target, f"🚫 Вам выдан недопуск.\nПричина: {reason}")
        try:
            await self.target.move_to(None, reason="Недопуск")
        except:
            pass
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
        nedopusk_rid = self.cog.config["roles"].get("nedopusk")
        if not nedopusk_rid:
            await inter.response.send_message("❌ Роль недопуска не настроена.", ephemeral=True)
            return
        nedopusk_role = inter.guild.get_role(nedopusk_rid)

        if nedopusk_role not in self.target.roles:
            await inter.response.send_message("❌ У пользователя нет недопуска.", ephemeral=True)
            return

        await self.target.remove_roles(nedopusk_role, reason=reason)
        remove_punishment(self.target.id, nedopusk_role.id)

        embed = disnake.Embed(title="✅ Снятие недопуска", color=disnake.Color.green())
        embed.add_field(name="Модератор", value=inter.author.mention)
        embed.add_field(name="Пользователь", value=self.target.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        await log_action(inter.guild, self.cog.config["log_channel"], embed)

        await self.cog._dm_user(self.target, f"✅ Ваш недопуск снят.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Недопуск снят с {self.target.mention}.", ephemeral=True)


class GenderView(disnake.ui.View):
    def __init__(self, cog, target, change):
        super().__init__(timeout=60)
        self.cog = cog
        self.target = target
        self.change = change

    @disnake.ui.button(label="♂ Мужской", style=disnake.ButtonStyle.blurple, custom_id="gender_male")
    async def male_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.process_gender(inter, "male")

    @disnake.ui.button(label="♀ Женский", style=disnake.ButtonStyle.blurple, custom_id="gender_female")
    async def female_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.process_gender(inter, "female")

    async def process_gender(self, inter, gender):
        male_role = self.cog.config["roles"].get("verif_male")
        female_role = self.cog.config["roles"].get("verif_female")
        unverified_role = self.cog.config["roles"].get("unverified")

        if not male_role or not female_role:
            await inter.response.send_message("❌ Роли верификации не настроены.", ephemeral=True)
            return

        await self.target.remove_roles(inter.guild.get_role(male_role), reason="Смена пола/верификация")
        await self.target.remove_roles(inter.guild.get_role(female_role), reason="Смена пола/верификация")

        new_role = male_role if gender == "male" else female_role
        await self.target.add_roles(inter.guild.get_role(new_role), reason="Смена пола/верификация")

        if not self.change and unverified_role:  # верификация
            await self.target.remove_roles(inter.guild.get_role(unverified_role), reason="Верификация")

        await inter.response.send_message(f"✅ Пол успешно изменён на {'мужской' if gender=='male' else 'женский'}.", ephemeral=True)

        await self.cog._send_log(
            inter.guild,
            "Смена пола" if self.change else "Верификация",
            disnake.Color.green(),
            [("Модератор", inter.author.mention), ("Пользователь", self.target.mention), ("Новый пол", "мужской" if gender=="male" else "женский")]
        )


class ReprimandBranchView(disnake.ui.View):
    def __init__(self, cog, target):
        super().__init__(timeout=60)
        self.cog = cog
        self.target = target

    @disnake.ui.button(label="Саппорты", style=disnake.ButtonStyle.red, custom_id="reprimand_support")
    async def support_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.open_reprimand_modal(inter, "support")

    @disnake.ui.button(label="Модераторы", style=disnake.ButtonStyle.red, custom_id="reprimand_moderator")
    async def moderator_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.open_reprimand_modal(inter, "moderator")

    @disnake.ui.button(label="Контроль", style=disnake.ButtonStyle.red, custom_id="reprimand_control")
    async def control_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.open_reprimand_modal(inter, "control")

    @disnake.ui.button(label="Администрация", style=disnake.ButtonStyle.red, custom_id="reprimand_admin")
    async def admin_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.open_reprimand_modal(inter, "admin")

    async def open_reprimand_modal(self, inter, branch):
        modal = ReprimandModal(self.cog, self.target, branch)
        await inter.response.send_modal(modal)


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

        role_id = self.cog.config["roles"].get(f"warn_{self.branch}")
        if not role_id:
            await inter.response.send_message("❌ Роль выговора не настроена для этой ветки.", ephemeral=True)
            return
        role = inter.guild.get_role(role_id)
        if role in self.target.roles:
            await inter.response.send_message("❌ У пользователя уже есть активный выговор по этой ветке.", ephemeral=True)
            return

        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, f"reprimand_{self.branch}", role.id, end_time, reason)

        embed = disnake.Embed(title=f"📢 Выговор ({self.branch})", color=disnake.Color.orange())
        embed.add_field(name="Модератор", value=inter.author.mention)
        embed.add_field(name="Пользователь", value=self.target.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        if end_time:
            embed.add_field(name="Срок", value=f"до <t:{int(end_time)}:f>")
        else:
            embed.add_field(name="Срок", value="бессрочно")
        await log_action(inter.guild, self.cog.config["log_channel"], embed)

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

            embed = disnake.Embed(title="✅ Снятие выговора", color=disnake.Color.green())
            embed.add_field(name="Модератор", value=inter.author.mention)
            embed.add_field(name="Пользователь", value=self.target.mention)
            embed.add_field(name="Причина", value=reason, inline=False)
            await log_action(inter.guild, self.cog.config["log_channel"], embed)

            await self.cog._dm_user(self.target, f"✅ Ваш выговор снят.\nПричина: {reason}")
            await inter.response.send_message(f"✅ Выговор снят с {self.target.mention}.", ephemeral=True)
        else:
            await inter.response.send_message("❌ Ошибка: роль выговора не найдена.", ephemeral=True)


class CHSBranchView(disnake.ui.View):
    def __init__(self, cog, target):
        super().__init__(timeout=60)
        self.cog = cog
        self.target = target

    @disnake.ui.button(label="Саппорты", style=disnake.ButtonStyle.red, custom_id="chs_support")
    async def support_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.open_chs_modal(inter, "support")

    @disnake.ui.button(label="Модераторы", style=disnake.ButtonStyle.red, custom_id="chs_moderator")
    async def moderator_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.open_chs_modal(inter, "moderator")

    @disnake.ui.button(label="Контроль", style=disnake.ButtonStyle.red, custom_id="chs_control")
    async def control_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.open_chs_modal(inter, "control")

    @disnake.ui.button(label="Администрация", style=disnake.ButtonStyle.red, custom_id="chs_admin")
    async def admin_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.open_chs_modal(inter, "admin")

    @disnake.ui.button(label="Общий ЧС", style=disnake.ButtonStyle.red, custom_id="chs_common")
    async def common_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await self.open_chs_modal(inter, "common")

    async def open_chs_modal(self, inter, branch):
        modal = CHSModal(self.cog, self.target, branch)
        await inter.response.send_modal(modal)


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
        role_id = self.cog.config["roles"].get(f"chs_{self.branch}")
        if not role_id:
            await inter.response.send_message("❌ Роль ЧС не настроена для этой ветки.", ephemeral=True)
            return
        role = inter.guild.get_role(role_id)
        if role in self.target.roles:
            await inter.response.send_message("❌ У пользователя уже есть ЧС по этой ветке.", ephemeral=True)
            return

        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, f"chs_{self.branch}", role.id, None, reason)

        embed = disnake.Embed(title=f"⛔ ЧС состава ({self.branch})", color=disnake.Color.red())
        embed.add_field(name="Модератор", value=inter.author.mention)
        embed.add_field(name="Пользователь", value=self.target.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        await log_action(inter.guild, self.cog.config["log_channel"], embed)

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

            embed = disnake.Embed(title="✅ Снятие ЧС", color=disnake.Color.green())
            embed.add_field(name="Модератор", value=inter.author.mention)
            embed.add_field(name="Пользователь", value=self.target.mention)
            embed.add_field(name="Причина", value=reason, inline=False)
            await log_action(inter.guild, self.cog.config["log_channel"], embed)

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

        role_id = self.cog.config["roles"].get("ostranenie")
        if not role_id:
            await inter.response.send_message("❌ Роль отстранения не настроена.", ephemeral=True)
            return
        role = inter.guild.get_role(role_id)
        if role in self.target.roles:
            await inter.response.send_message("❌ У пользователя уже есть активное отстранение.", ephemeral=True)
            return

        await self.target.add_roles(role, reason=reason)
        add_punishment(self.target.id, "suspension", role.id, end_time, reason)

        embed = disnake.Embed(title="⏳ Отстранение", color=disnake.Color.dark_red())
        embed.add_field(name="Модератор", value=inter.author.mention)
        embed.add_field(name="Пользователь", value=self.target.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        if end_time:
            embed.add_field(name="Срок", value=f"до <t:{int(end_time)}:f>")
        else:
            embed.add_field(name="Срок", value="бессрочно")
        await log_action(inter.guild, self.cog.config["log_channel"], embed)

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
        role_id = self.cog.config["roles"].get("ostranenie")
        if not role_id:
            await inter.response.send_message("❌ Роль отстранения не настроена.", ephemeral=True)
            return
        role = inter.guild.get_role(role_id)
        if role not in self.target.roles:
            await inter.response.send_message("❌ У пользователя нет активного отстранения.", ephemeral=True)
            return

        await self.target.remove_roles(role, reason=reason)
        remove_punishment(self.target.id, role.id)

        embed = disnake.Embed(title="✅ Снятие отстранения", color=disnake.Color.green())
        embed.add_field(name="Модератор", value=inter.author.mention)
        embed.add_field(name="Пользователь", value=self.target.mention)
        embed.add_field(name="Причина", value=reason, inline=False)
        await log_action(inter.guild, self.cog.config["log_channel"], embed)

        await self.cog._dm_user(self.target, f"✅ Ваше отстранение снято.\nПричина: {reason}")
        await inter.response.send_message(f"✅ Отстранение снято с {self.target.mention}.", ephemeral=True)


def setup(bot):
    bot.add_cog(Action(bot))