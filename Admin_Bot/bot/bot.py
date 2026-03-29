"""
🛡️ Admin Guard Bot - Telegram бот для администрирования чатов
Автор: Admin Bot Team
Версия: 2.0
"""

import os
import json
import asyncio
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from functools import wraps

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, ChatPermissions,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, ReplyKeyboardMarkup, KeyboardButton,
    ChatMemberUpdated
)
from aiogram.enums import ParseMode, ChatType, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION

# ==================== КОНФИГУРАЦИЯ ====================

def _require_bot_token() -> str:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "Bot_Token=8635918990:AAGr7Wc1LAGnZcK7y-glbg12vZC9VRviHtg":
        raise RuntimeError(
            "Задайте переменную окружения BOT_TOKEN (токен от @BotFather). "
            "Пример: export BOT_TOKEN=123456:ABC..."
        )
    return token


BOT_TOKEN = _require_bot_token()
WEBAPP_URL = os.getenv("https://sanjisfun.github.io/Web/", "").strip()
DATA_FILE = os.getenv("BOT_DATA_FILE", "bot_data.json")

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== ИНИЦИАЛИЗАЦИЯ ====================

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# ==================== БАЗА ДАННЫХ (JSON) ====================

def load_data() -> Dict:
    """Загрузка данных из файла"""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "chats": {},
            "users": {},
            "logs": [],
            "global_stats": {
                "total_bans": 0,
                "total_mutes": 0,
                "total_warns": 0,
                "total_kicks": 0,
                "total_messages_deleted": 0
            }
        }

def save_data(data: Dict):
    """Сохранение данных в файл"""
    parent = os.path.dirname(os.path.abspath(DATA_FILE))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_chat_data(chat_id: int) -> Dict:
    """Получение данных чата"""
    data = load_data()
    chat_id_str = str(chat_id)
    if chat_id_str not in data["chats"]:
        data["chats"][chat_id_str] = {
            "settings": {
                "antispam": False,
                "antiflood": False,
                "antiflood_limit": 5,
                "captcha": False,
                "welcome": True,
                "welcome_text": "👋 Добро пожаловать, {user}!",
                "rules": "📜 Правила чата не установлены.",
                "slowmode": 0,
                "warn_limit": 3,
                "log_channel": None
            },
            "filters": [],
            "replies": {},
            "warns": {},
            "mutes": {},
            "bans": {},
            "captcha_pending": {},
            "stats": {
                "messages": 0,
                "members": 0,
                "bans": 0,
                "mutes": 0,
                "warns": 0,
                "kicks": 0
            }
        }
        save_data(data)
    return data["chats"][chat_id_str]

def update_chat_data(chat_id: int, chat_data: Dict):
    """Обновление данных чата"""
    data = load_data()
    data["chats"][str(chat_id)] = chat_data
    save_data(data)

def add_log(chat_id: int, action: str, admin: str, target: str, reason: str = ""):
    """Добавление записи в лог"""
    data = load_data()
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "chat_id": chat_id,
        "action": action,
        "admin": admin,
        "target": target,
        "reason": reason
    }
    data["logs"].insert(0, log_entry)
    data["logs"] = data["logs"][:1000]  # Храним последние 1000 записей
    save_data(data)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def parse_time(time_str: str) -> Optional[timedelta]:
    """Парсинг времени (1m, 1h, 1d, 1w)"""
    if not time_str:
        return None
    
    time_str = time_str.lower().strip()
    if time_str == "0" or time_str == "forever":
        return None
    
    multipliers = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        'w': 604800
    }
    
    try:
        unit = time_str[-1]
        if unit in multipliers:
            value = int(time_str[:-1])
            return timedelta(seconds=value * multipliers[unit])
        else:
            return timedelta(seconds=int(time_str))
    except (ValueError, IndexError):
        return None

def format_timedelta(td: timedelta) -> str:
    """Форматирование timedelta в читаемый вид"""
    total_seconds = int(td.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds} сек."
    elif total_seconds < 3600:
        return f"{total_seconds // 60} мин."
    elif total_seconds < 86400:
        return f"{total_seconds // 3600} ч."
    else:
        return f"{total_seconds // 86400} дн."

async def get_target_user(message: Message) -> Optional[types.User]:
    """Получение целевого пользователя из сообщения или реплая"""
    # Если это реплай
    if message.reply_to_message:
        return message.reply_to_message.from_user
    
    # Если указан @username или user_id
    args = message.text.split()[1:] if message.text else []
    if args:
        target = args[0]
        try:
            if target.startswith("@"):
                # По username - нужно искать в участниках чата
                return None  # Telegram API не позволяет напрямую получить по username
            else:
                # По user_id
                user_id = int(target)
                member = await bot.get_chat_member(message.chat.id, user_id)
                return member.user
        except (ValueError, TelegramBadRequest):
            return None
    
    return None

async def is_admin(chat_id: int, user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except TelegramBadRequest:
        return False

async def is_bot_admin(chat_id: int) -> bool:
    """Проверка, является ли бот администратором"""
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        return bot_member.status == ChatMemberStatus.ADMINISTRATOR
    except TelegramBadRequest:
        return False

def admin_required(func):
    """Декоратор для проверки прав администратора"""
    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        if message.chat.type == ChatType.PRIVATE:
            await message.reply("❌ Эта команда работает только в группах!")
            return
        
        if not await is_admin(message.chat.id, message.from_user.id):
            await message.reply("❌ У вас нет прав администратора!")
            return
        
        if not await is_bot_admin(message.chat.id):
            await message.reply("❌ Бот не является администратором чата!")
            return
        
        return await func(message, *args, **kwargs)
    return wrapper

def get_user_mention(user: types.User) -> str:
    """Получение упоминания пользователя"""
    if user.username:
        return f"@{user.username}"
    return f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"

def generate_captcha() -> tuple:
    """Генерация капчи"""
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    answer = num1 + num2
    question = f"{num1} + {num2} = ?"
    return question, str(answer)

# ==================== КОМАНДЫ МОДЕРАЦИИ ====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    if message.chat.type == ChatType.PRIVATE:
        rows: List[List[InlineKeyboardButton]] = [
            [InlineKeyboardButton(text="➕ Добавить в чат", url=f"https://t.me/{(await bot.me()).username}?startgroup=true")],
        ]
        if WEBAPP_URL:
            rows.append([InlineKeyboardButton(text="📱 Открыть панель", web_app=WebAppInfo(url=WEBAPP_URL))])
        rows.append([InlineKeyboardButton(text="📚 Помощь", callback_data="help")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
        
        await message.reply(
            "🛡️ <b>Admin Guard Bot</b>\n\n"
            "Мощный бот для администрирования чатов и каналов.\n\n"
            "⚡ <b>Возможности:</b>\n"
            "• 🚫 Бан, мут, кик пользователей\n"
            "• ⚠️ Система предупреждений\n"
            "• 🛡️ Антиспам и антифлуд\n"
            "• 🔐 Капча для новых участников\n"
            "• 🔤 Фильтр слов\n"
            "• 💬 Автоответы\n"
            "• 📊 Статистика чата\n\n"
            "👇 Добавьте меня в чат и дайте права администратора!",
            reply_markup=keyboard
        )
    else:
        await message.reply("✅ Бот активен и готов к работе!")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help"""
    help_text = """
🛡️ <b>Admin Guard Bot - Команды</b>

⚖️ <b>МОДЕРАЦИЯ:</b>
/ban - Забанить (@user или реплай)
/unban - Разбанить (@user)
/mute - Замутить (@user 1h/1d/1w)
/unmute - Размутить (@user)
/kick - Кикнуть (@user)
/warn - Предупреждение (@user причина)
/unwarn - Снять варн (@user)
/del - Удалить сообщение (реплай)
/purge - Удалить сообщения (число)

⚙️ <b>НАСТРОЙКИ:</b>
/rules - Показать правила
/setrules - Установить правила (текст)
/pin - Закрепить (реплай)
/unpin - Открепить сообщение
/unpinall - Открепить все
/slowmode - Слоумод (0-60 сек)
/setwelcome - Приветствие (текст)
/welcomeoff - Выключить приветствие

🤖 <b>АВТОМАТИЗАЦИЯ:</b>
/antispam - Антиспам (on/off)
/antiflood - Антифлуд (число)
/addfilter - Добавить в фильтр (слово)
/delfilter - Убрать из фильтра (слово)
/filters - Список фильтров
/addreply - Автоответ (триггер | ответ)
/delreply - Удалить автоответ (триггер)
/replies - Список автоответов
/captcha - Капча (on/off)

📊 <b>ИНФОРМАЦИЯ:</b>
/stats - Статистика чата
/info - Инфо о юзере (@user)
/admins - Список админов
/id - ID чата или юзера
/logs - Последние действия

🔧 <b>ПРОЧЕЕ:</b>
/report - Жалоба (реплай)
/promote - Сделать модером (@user)
/demote - Снять модера (@user)
/settings - Настройки
"""
    await message.reply(help_text)

# ==================== БАН / РАЗБАН ====================

@router.message(Command("ban"))
@admin_required
async def cmd_ban(message: Message):
    """Забанить пользователя"""
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя (@user) или ответьте на его сообщение!")
        return
    
    if await is_admin(message.chat.id, target.id):
        await message.reply("❌ Нельзя забанить администратора!")
        return
    
    # Парсим время и причину
    args = message.text.split()[1:] if message.text else []
    time_delta = None
    reason = "Не указана"
    
    for i, arg in enumerate(args):
        parsed_time = parse_time(arg)
        if parsed_time:
            time_delta = parsed_time
        elif not arg.startswith("@") and not arg.isdigit():
            reason = " ".join(args[i:])
            break
    
    try:
        until_date = datetime.now() + time_delta if time_delta else None
        await bot.ban_chat_member(message.chat.id, target.id, until_date=until_date)
        
        # Обновляем статистику
        chat_data = get_chat_data(message.chat.id)
        chat_data["stats"]["bans"] += 1
        chat_data["bans"][str(target.id)] = {
            "date": datetime.now().isoformat(),
            "admin": message.from_user.id,
            "reason": reason,
            "until": until_date.isoformat() if until_date else None
        }
        update_chat_data(message.chat.id, chat_data)
        
        # Логируем
        add_log(message.chat.id, "BAN", message.from_user.full_name, target.full_name, reason)
        
        time_str = f" на {format_timedelta(time_delta)}" if time_delta else " навсегда"
        await message.reply(
            f"🚫 <b>Пользователь забанен{time_str}</b>\n\n"
            f"👤 Пользователь: {get_user_mention(target)}\n"
            f"👮 Админ: {get_user_mention(message.from_user)}\n"
            f"📝 Причина: {reason}"
        )
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

@router.message(Command("unban"))
@admin_required
async def cmd_unban(message: Message):
    """Разбанить пользователя"""
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя (@user) или ID!")
        return
    
    try:
        await bot.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
        
        # Обновляем данные
        chat_data = get_chat_data(message.chat.id)
        if str(target.id) in chat_data["bans"]:
            del chat_data["bans"][str(target.id)]
            update_chat_data(message.chat.id, chat_data)
        
        add_log(message.chat.id, "UNBAN", message.from_user.full_name, target.full_name)
        
        await message.reply(
            f"✅ <b>Пользователь разбанен</b>\n\n"
            f"👤 Пользователь: {get_user_mention(target)}\n"
            f"👮 Админ: {get_user_mention(message.from_user)}"
        )
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

# ==================== МУТ / РАЗМУТ ====================

@router.message(Command("mute"))
@admin_required
async def cmd_mute(message: Message):
    """Замутить пользователя"""
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя (@user) или ответьте на его сообщение!")
        return
    
    if await is_admin(message.chat.id, target.id):
        await message.reply("❌ Нельзя замутить администратора!")
        return
    
    # Парсим время и причину
    args = message.text.split()[1:] if message.text else []
    time_delta = timedelta(hours=1)  # По умолчанию 1 час
    reason = "Не указана"
    
    for i, arg in enumerate(args):
        parsed_time = parse_time(arg)
        if parsed_time:
            time_delta = parsed_time
        elif not arg.startswith("@") and not arg.isdigit():
            reason = " ".join(args[i:])
            break
    
    try:
        until_date = datetime.now() + time_delta
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
        await bot.restrict_chat_member(message.chat.id, target.id, permissions=permissions, until_date=until_date)
        
        # Обновляем статистику
        chat_data = get_chat_data(message.chat.id)
        chat_data["stats"]["mutes"] += 1
        chat_data["mutes"][str(target.id)] = {
            "date": datetime.now().isoformat(),
            "admin": message.from_user.id,
            "reason": reason,
            "until": until_date.isoformat()
        }
        update_chat_data(message.chat.id, chat_data)
        
        add_log(message.chat.id, "MUTE", message.from_user.full_name, target.full_name, reason)
        
        await message.reply(
            f"🔇 <b>Пользователь замучен на {format_timedelta(time_delta)}</b>\n\n"
            f"👤 Пользователь: {get_user_mention(target)}\n"
            f"👮 Админ: {get_user_mention(message.from_user)}\n"
            f"📝 Причина: {reason}"
        )
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

@router.message(Command("unmute"))
@admin_required
async def cmd_unmute(message: Message):
    """Размутить пользователя"""
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя (@user) или ответьте на его сообщение!")
        return
    
    try:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_send_polls=True,
            can_invite_users=True,
            can_change_info=False,
            can_pin_messages=False
        )
        await bot.restrict_chat_member(message.chat.id, target.id, permissions=permissions)
        
        # Обновляем данные
        chat_data = get_chat_data(message.chat.id)
        if str(target.id) in chat_data["mutes"]:
            del chat_data["mutes"][str(target.id)]
            update_chat_data(message.chat.id, chat_data)
        
        add_log(message.chat.id, "UNMUTE", message.from_user.full_name, target.full_name)
        
        await message.reply(
            f"🔊 <b>Пользователь размучен</b>\n\n"
            f"👤 Пользователь: {get_user_mention(target)}\n"
            f"👮 Админ: {get_user_mention(message.from_user)}"
        )
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

# ==================== КИК ====================

@router.message(Command("kick"))
@admin_required
async def cmd_kick(message: Message):
    """Кикнуть пользователя"""
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя (@user) или ответьте на его сообщение!")
        return
    
    if await is_admin(message.chat.id, target.id):
        await message.reply("❌ Нельзя кикнуть администратора!")
        return
    
    reason = " ".join(message.text.split()[2:]) if len(message.text.split()) > 2 else "Не указана"
    
    try:
        await bot.ban_chat_member(message.chat.id, target.id)
        await bot.unban_chat_member(message.chat.id, target.id)
        
        # Обновляем статистику
        chat_data = get_chat_data(message.chat.id)
        chat_data["stats"]["kicks"] += 1
        update_chat_data(message.chat.id, chat_data)
        
        add_log(message.chat.id, "KICK", message.from_user.full_name, target.full_name, reason)
        
        await message.reply(
            f"👢 <b>Пользователь кикнут</b>\n\n"
            f"👤 Пользователь: {get_user_mention(target)}\n"
            f"👮 Админ: {get_user_mention(message.from_user)}\n"
            f"📝 Причина: {reason}"
        )
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

# ==================== ПРЕДУПРЕЖДЕНИЯ ====================

@router.message(Command("warn"))
@admin_required
async def cmd_warn(message: Message):
    """Выдать предупреждение"""
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя (@user) или ответьте на его сообщение!")
        return
    
    if await is_admin(message.chat.id, target.id):
        await message.reply("❌ Нельзя выдать предупреждение администратору!")
        return
    
    reason = " ".join(message.text.split()[2:]) if len(message.text.split()) > 2 else "Не указана"
    
    # Обновляем данные
    chat_data = get_chat_data(message.chat.id)
    user_id_str = str(target.id)
    
    if user_id_str not in chat_data["warns"]:
        chat_data["warns"][user_id_str] = []
    
    chat_data["warns"][user_id_str].append({
        "date": datetime.now().isoformat(),
        "admin": message.from_user.id,
        "reason": reason
    })
    
    warn_count = len(chat_data["warns"][user_id_str])
    warn_limit = chat_data["settings"]["warn_limit"]
    chat_data["stats"]["warns"] += 1
    update_chat_data(message.chat.id, chat_data)
    
    add_log(message.chat.id, "WARN", message.from_user.full_name, target.full_name, reason)
    
    # Если превышен лимит - баним
    if warn_count >= warn_limit:
        try:
            await bot.ban_chat_member(message.chat.id, target.id)
            chat_data["warns"][user_id_str] = []
            update_chat_data(message.chat.id, chat_data)
            
            await message.reply(
                f"🚫 <b>Пользователь забанен</b>\n\n"
                f"👤 Пользователь: {get_user_mention(target)}\n"
                f"⚠️ Причина: Превышен лимит предупреждений ({warn_limit}/{warn_limit})"
            )
        except TelegramBadRequest as e:
            await message.reply(f"❌ Ошибка при бане: {e.message}")
    else:
        await message.reply(
            f"⚠️ <b>Предупреждение выдано</b>\n\n"
            f"👤 Пользователь: {get_user_mention(target)}\n"
            f"👮 Админ: {get_user_mention(message.from_user)}\n"
            f"📝 Причина: {reason}\n"
            f"⚠️ Предупреждений: {warn_count}/{warn_limit}"
        )

@router.message(Command("unwarn"))
@admin_required
async def cmd_unwarn(message: Message):
    """Снять предупреждение"""
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя (@user) или ответьте на его сообщение!")
        return
    
    chat_data = get_chat_data(message.chat.id)
    user_id_str = str(target.id)
    
    if user_id_str not in chat_data["warns"] or not chat_data["warns"][user_id_str]:
        await message.reply("❌ У пользователя нет предупреждений!")
        return
    
    chat_data["warns"][user_id_str].pop()
    warn_count = len(chat_data["warns"][user_id_str])
    update_chat_data(message.chat.id, chat_data)
    
    add_log(message.chat.id, "UNWARN", message.from_user.full_name, target.full_name)
    
    await message.reply(
        f"🔄 <b>Предупреждение снято</b>\n\n"
        f"👤 Пользователь: {get_user_mention(target)}\n"
        f"⚠️ Осталось предупреждений: {warn_count}/{chat_data['settings']['warn_limit']}"
    )

# ==================== УДАЛЕНИЕ СООБЩЕНИЙ ====================

@router.message(Command("del"))
@admin_required
async def cmd_del(message: Message):
    """Удалить сообщение"""
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение, которое нужно удалить!")
        return
    
    try:
        await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
        await bot.delete_message(message.chat.id, message.message_id)
        
        add_log(message.chat.id, "DELETE", message.from_user.full_name, 
                message.reply_to_message.from_user.full_name if message.reply_to_message.from_user else "Unknown")
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

@router.message(Command("purge"))
@admin_required
async def cmd_purge(message: Message):
    """Удалить последние N сообщений"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Укажите количество сообщений: /purge 10")
        return
    
    try:
        count = min(int(args[1]), 100)  # Максимум 100
    except ValueError:
        await message.reply("❌ Укажите число!")
        return
    
    try:
        deleted = 0
        async for msg in bot.get_chat_history(message.chat.id, limit=count + 1):
            try:
                await bot.delete_message(message.chat.id, msg.message_id)
                deleted += 1
            except:
                pass
        
        add_log(message.chat.id, "PURGE", message.from_user.full_name, f"{deleted} сообщений")
        
        notify = await message.answer(f"🧹 Удалено {deleted} сообщений")
        await asyncio.sleep(3)
        await notify.delete()
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")

# ==================== ПРАВИЛА ====================

@router.message(Command("rules"))
async def cmd_rules(message: Message):
    """Показать правила чата"""
    if message.chat.type == ChatType.PRIVATE:
        await message.reply("❌ Эта команда работает только в группах!")
        return
    
    chat_data = get_chat_data(message.chat.id)
    rules = chat_data["settings"]["rules"]
    
    await message.reply(f"📜 <b>Правила чата:</b>\n\n{rules}")

@router.message(Command("setrules"))
@admin_required
async def cmd_setrules(message: Message):
    """Установить правила чата"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Укажите текст правил: /setrules Текст правил...")
        return
    
    rules = args[1]
    chat_data = get_chat_data(message.chat.id)
    chat_data["settings"]["rules"] = rules
    update_chat_data(message.chat.id, chat_data)
    
    add_log(message.chat.id, "SET_RULES", message.from_user.full_name, "")
    
    await message.reply(f"✅ Правила установлены!\n\n📜 {rules}")

# ==================== ЗАКРЕПЛЕНИЕ ====================

@router.message(Command("pin"))
@admin_required
async def cmd_pin(message: Message):
    """Закрепить сообщение"""
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение, которое нужно закрепить!")
        return
    
    try:
        await bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id)
        add_log(message.chat.id, "PIN", message.from_user.full_name, "")
        await message.reply("📌 Сообщение закреплено!")
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

@router.message(Command("unpin"))
@admin_required
async def cmd_unpin(message: Message):
    """Открепить сообщение"""
    try:
        await bot.unpin_chat_message(message.chat.id)
        add_log(message.chat.id, "UNPIN", message.from_user.full_name, "")
        await message.reply("📍 Сообщение откреплено!")
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

@router.message(Command("unpinall"))
@admin_required
async def cmd_unpinall(message: Message):
    """Открепить все сообщения"""
    try:
        await bot.unpin_all_chat_messages(message.chat.id)
        add_log(message.chat.id, "UNPIN_ALL", message.from_user.full_name, "")
        await message.reply("📍 Все сообщения откреплены!")
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

# ==================== СЛОУМОД ====================

@router.message(Command("slowmode"))
@admin_required
async def cmd_slowmode(message: Message):
    """Установить медленный режим"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Укажите время в секундах: /slowmode 60")
        return
    
    try:
        seconds = int(args[1])
        if seconds < 0 or seconds > 86400:
            await message.reply("❌ Укажите от 0 до 86400 секунд!")
            return
    except ValueError:
        await message.reply("❌ Укажите число!")
        return
    
    try:
        await bot.set_chat_slow_mode_delay(message.chat.id, seconds)
        
        chat_data = get_chat_data(message.chat.id)
        chat_data["settings"]["slowmode"] = seconds
        update_chat_data(message.chat.id, chat_data)
        
        add_log(message.chat.id, "SLOWMODE", message.from_user.full_name, f"{seconds} сек")
        
        if seconds == 0:
            await message.reply("🐌 Медленный режим выключен!")
        else:
            await message.reply(f"🐌 Медленный режим: {seconds} сек.")
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

# ==================== ПРИВЕТСТВИЕ ====================

@router.message(Command("setwelcome"))
@admin_required
async def cmd_setwelcome(message: Message):
    """Установить приветствие"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply(
            "❌ Укажите текст приветствия!\n\n"
            "📝 Доступные переменные:\n"
            "{user} - имя пользователя\n"
            "{username} - @username\n"
            "{chat} - название чата\n"
            "{count} - количество участников\n"
            "{id} - ID пользователя\n\n"
            "Пример: /setwelcome Привет, {user}! 👋"
        )
        return
    
    welcome_text = args[1]
    chat_data = get_chat_data(message.chat.id)
    chat_data["settings"]["welcome_text"] = welcome_text
    chat_data["settings"]["welcome"] = True
    update_chat_data(message.chat.id, chat_data)
    
    add_log(message.chat.id, "SET_WELCOME", message.from_user.full_name, "")
    
    await message.reply(f"✅ Приветствие установлено!\n\n👋 {welcome_text}")

@router.message(Command("welcomeoff"))
@admin_required
async def cmd_welcomeoff(message: Message):
    """Выключить приветствие"""
    chat_data = get_chat_data(message.chat.id)
    chat_data["settings"]["welcome"] = False
    update_chat_data(message.chat.id, chat_data)
    
    await message.reply("✅ Приветствие выключено!")

# ==================== АНТИСПАМ / АНТИФЛУД ====================

@router.message(Command("antispam"))
@admin_required
async def cmd_antispam(message: Message):
    """Включить/выключить антиспам"""
    args = message.text.split()
    if len(args) < 2 or args[1].lower() not in ["on", "off"]:
        await message.reply("❌ Использование: /antispam on или /antispam off")
        return
    
    enabled = args[1].lower() == "on"
    chat_data = get_chat_data(message.chat.id)
    chat_data["settings"]["antispam"] = enabled
    update_chat_data(message.chat.id, chat_data)
    
    add_log(message.chat.id, "ANTISPAM", message.from_user.full_name, "on" if enabled else "off")
    
    status = "включен ✅" if enabled else "выключен ❌"
    await message.reply(f"🛡️ Антиспам {status}")

@router.message(Command("antiflood"))
@admin_required
async def cmd_antiflood(message: Message):
    """Настроить антифлуд"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Укажите лимит сообщений в минуту: /antiflood 5")
        return
    
    try:
        limit = int(args[1])
        if limit < 0 or limit > 60:
            await message.reply("❌ Укажите от 0 до 60!")
            return
    except ValueError:
        await message.reply("❌ Укажите число!")
        return
    
    chat_data = get_chat_data(message.chat.id)
    chat_data["settings"]["antiflood"] = limit > 0
    chat_data["settings"]["antiflood_limit"] = limit
    update_chat_data(message.chat.id, chat_data)
    
    add_log(message.chat.id, "ANTIFLOOD", message.from_user.full_name, str(limit))
    
    if limit == 0:
        await message.reply("🌊 Антифлуд выключен!")
    else:
        await message.reply(f"🌊 Антифлуд: максимум {limit} сообщений в минуту")

# ==================== ФИЛЬТРЫ СЛОВ ====================

@router.message(Command("addfilter"))
@admin_required
async def cmd_addfilter(message: Message):
    """Добавить слово в фильтр"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Укажите слово: /addfilter слово")
        return
    
    word = args[1].lower().strip()
    chat_data = get_chat_data(message.chat.id)
    
    if word in chat_data["filters"]:
        await message.reply("❌ Это слово уже в фильтре!")
        return
    
    chat_data["filters"].append(word)
    update_chat_data(message.chat.id, chat_data)
    
    add_log(message.chat.id, "ADD_FILTER", message.from_user.full_name, word)
    
    await message.reply(f"✅ Слово «{word}» добавлено в фильтр!")

@router.message(Command("delfilter"))
@admin_required
async def cmd_delfilter(message: Message):
    """Удалить слово из фильтра"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Укажите слово: /delfilter слово")
        return
    
    word = args[1].lower().strip()
    chat_data = get_chat_data(message.chat.id)
    
    if word not in chat_data["filters"]:
        await message.reply("❌ Это слово не в фильтре!")
        return
    
    chat_data["filters"].remove(word)
    update_chat_data(message.chat.id, chat_data)
    
    add_log(message.chat.id, "DEL_FILTER", message.from_user.full_name, word)
    
    await message.reply(f"✅ Слово «{word}» удалено из фильтра!")

@router.message(Command("filters"))
@admin_required
async def cmd_filters(message: Message):
    """Список фильтров"""
    chat_data = get_chat_data(message.chat.id)
    filters = chat_data["filters"]
    
    if not filters:
        await message.reply("📋 Фильтр пуст!")
        return
    
    filters_text = "\n".join([f"• {word}" for word in filters])
    await message.reply(f"🔤 <b>Фильтр слов:</b>\n\n{filters_text}")

# ==================== АВТООТВЕТЫ ====================

@router.message(Command("addreply"))
@admin_required
async def cmd_addreply(message: Message):
    """Добавить автоответ"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or "|" not in args[1]:
        await message.reply("❌ Использование: /addreply триггер | ответ")
        return
    
    parts = args[1].split("|", 1)
    trigger = parts[0].strip().lower()
    reply = parts[1].strip()
    
    chat_data = get_chat_data(message.chat.id)
    chat_data["replies"][trigger] = reply
    update_chat_data(message.chat.id, chat_data)
    
    add_log(message.chat.id, "ADD_REPLY", message.from_user.full_name, trigger)
    
    await message.reply(f"✅ Автоответ добавлен!\n\n🔹 Триггер: {trigger}\n🔹 Ответ: {reply}")

@router.message(Command("delreply"))
@admin_required
async def cmd_delreply(message: Message):
    """Удалить автоответ"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Укажите триггер: /delreply триггер")
        return
    
    trigger = args[1].lower().strip()
    chat_data = get_chat_data(message.chat.id)
    
    if trigger not in chat_data["replies"]:
        await message.reply("❌ Такой триггер не найден!")
        return
    
    del chat_data["replies"][trigger]
    update_chat_data(message.chat.id, chat_data)
    
    add_log(message.chat.id, "DEL_REPLY", message.from_user.full_name, trigger)
    
    await message.reply(f"✅ Автоответ «{trigger}» удалён!")

@router.message(Command("replies"))
@admin_required
async def cmd_replies(message: Message):
    """Список автоответов"""
    chat_data = get_chat_data(message.chat.id)
    replies = chat_data["replies"]
    
    if not replies:
        await message.reply("📋 Автоответы не настроены!")
        return
    
    replies_text = "\n".join([f"🔹 {trigger} → {reply}" for trigger, reply in replies.items()])
    await message.reply(f"💬 <b>Автоответы:</b>\n\n{replies_text}")

# ==================== КАПЧА ====================

@router.message(Command("captcha"))
@admin_required
async def cmd_captcha(message: Message):
    """Включить/выключить капчу"""
    args = message.text.split()
    if len(args) < 2 or args[1].lower() not in ["on", "off"]:
        await message.reply("❌ Использование: /captcha on или /captcha off")
        return
    
    enabled = args[1].lower() == "on"
    chat_data = get_chat_data(message.chat.id)
    chat_data["settings"]["captcha"] = enabled
    update_chat_data(message.chat.id, chat_data)
    
    add_log(message.chat.id, "CAPTCHA", message.from_user.full_name, "on" if enabled else "off")
    
    status = "включена ✅" if enabled else "выключена ❌"
    await message.reply(f"🔐 Капча {status}")

# ==================== СТАТИСТИКА ====================

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика чата"""
    if message.chat.type == ChatType.PRIVATE:
        await message.reply("❌ Эта команда работает только в группах!")
        return
    
    chat_data = get_chat_data(message.chat.id)
    stats = chat_data["stats"]
    settings = chat_data["settings"]
    
    try:
        members_count = await bot.get_chat_member_count(message.chat.id)
    except:
        members_count = "N/A"
    
    # Статус функций
    antispam_status = "✅" if settings["antispam"] else "❌"
    antiflood_status = "✅" if settings["antiflood"] else "❌"
    captcha_status = "✅" if settings["captcha"] else "❌"
    welcome_status = "✅" if settings["welcome"] else "❌"
    
    await message.reply(
        f"📊 <b>Статистика чата</b>\n\n"
        f"👥 Участников: {members_count}\n"
        f"🚫 Банов: {stats['bans']}\n"
        f"🔇 Мутов: {stats['mutes']}\n"
        f"⚠️ Предупреждений: {stats['warns']}\n"
        f"👢 Киков: {stats['kicks']}\n\n"
        f"<b>Настройки:</b>\n"
        f"🛡️ Антиспам: {antispam_status}\n"
        f"🌊 Антифлуд: {antiflood_status}\n"
        f"🔐 Капча: {captcha_status}\n"
        f"👋 Приветствие: {welcome_status}\n"
        f"🐌 Слоумод: {settings['slowmode']} сек.\n"
        f"🔤 Фильтров: {len(chat_data['filters'])}\n"
        f"💬 Автоответов: {len(chat_data['replies'])}"
    )

@router.message(Command("info"))
async def cmd_info(message: Message):
    """Информация о пользователе"""
    target = await get_target_user(message)
    if not target:
        target = message.from_user
    
    try:
        member = await bot.get_chat_member(message.chat.id, target.id)
        status_map = {
            ChatMemberStatus.CREATOR: "👑 Создатель",
            ChatMemberStatus.ADMINISTRATOR: "👮 Админ",
            ChatMemberStatus.MEMBER: "👤 Участник",
            ChatMemberStatus.RESTRICTED: "⚠️ Ограничен",
            ChatMemberStatus.LEFT: "🚪 Покинул",
            ChatMemberStatus.KICKED: "🚫 Забанен"
        }
        status = status_map.get(member.status, "❓ Неизвестно")
    except:
        status = "❓ Неизвестно"
    
    chat_data = get_chat_data(message.chat.id)
    warns = len(chat_data["warns"].get(str(target.id), []))
    
    await message.reply(
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"📛 Имя: {target.full_name}\n"
        f"🔗 Username: @{target.username or 'нет'}\n"
        f"🆔 ID: <code>{target.id}</code>\n"
        f"📊 Статус: {status}\n"
        f"⚠️ Предупреждений: {warns}/{chat_data['settings']['warn_limit']}"
    )

@router.message(Command("admins"))
async def cmd_admins(message: Message):
    """Список администраторов"""
    if message.chat.type == ChatType.PRIVATE:
        await message.reply("❌ Эта команда работает только в группах!")
        return
    
    try:
        admins = await bot.get_chat_administrators(message.chat.id)
        admins_text = []
        
        for admin in admins:
            if admin.status == ChatMemberStatus.CREATOR:
                admins_text.append(f"👑 {admin.user.full_name}")
            else:
                admins_text.append(f"👮 {admin.user.full_name}")
        
        await message.reply(f"👑 <b>Администраторы чата:</b>\n\n" + "\n".join(admins_text))
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

@router.message(Command("id"))
async def cmd_id(message: Message):
    """Показать ID"""
    target = await get_target_user(message) if message.reply_to_message else message.from_user
    
    await message.reply(
        f"🆔 <b>ID информация</b>\n\n"
        f"👤 Ваш ID: <code>{message.from_user.id}</code>\n"
        f"💬 ID чата: <code>{message.chat.id}</code>\n"
        f"👤 ID цели: <code>{target.id if target else 'N/A'}</code>"
    )

@router.message(Command("logs"))
@admin_required
async def cmd_logs(message: Message):
    """Показать логи"""
    args = message.text.split()
    limit = 10
    if len(args) > 1:
        try:
            limit = min(int(args[1]), 50)
        except ValueError:
            pass
    
    data = load_data()
    chat_logs = [log for log in data["logs"] if log["chat_id"] == message.chat.id][:limit]
    
    if not chat_logs:
        await message.reply("📜 Логи пусты!")
        return
    
    logs_text = []
    for log in chat_logs:
        timestamp = datetime.fromisoformat(log["timestamp"]).strftime("%d.%m %H:%M")
        logs_text.append(f"[{timestamp}] {log['action']}: {log['admin']} → {log['target']}")
    
    await message.reply(f"📜 <b>Последние действия:</b>\n\n" + "\n".join(logs_text))

# ==================== ЖАЛОБЫ И МОДЕРАТОРЫ ====================

@router.message(Command("report"))
async def cmd_report(message: Message):
    """Пожаловаться на сообщение"""
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение, на которое хотите пожаловаться!")
        return
    
    try:
        admins = await bot.get_chat_administrators(message.chat.id)
        admin_mentions = [get_user_mention(admin.user) for admin in admins if not admin.user.is_bot]
        
        await message.reply(
            f"🚨 <b>Жалоба!</b>\n\n"
            f"👤 От: {get_user_mention(message.from_user)}\n"
            f"👤 На: {get_user_mention(message.reply_to_message.from_user)}\n\n"
            f"👮 Админы: {', '.join(admin_mentions[:5])}"
        )
        
        add_log(message.chat.id, "REPORT", message.from_user.full_name, 
                message.reply_to_message.from_user.full_name if message.reply_to_message.from_user else "Unknown")
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

@router.message(Command("promote"))
@admin_required
async def cmd_promote(message: Message):
    """Повысить до модератора"""
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя (@user) или ответьте на его сообщение!")
        return
    
    try:
        await bot.promote_chat_member(
            message.chat.id, 
            target.id,
            can_delete_messages=True,
            can_restrict_members=True,
            can_pin_messages=True
        )
        
        add_log(message.chat.id, "PROMOTE", message.from_user.full_name, target.full_name)
        
        await message.reply(
            f"⬆️ <b>Пользователь повышен до модератора</b>\n\n"
            f"👤 Пользователь: {get_user_mention(target)}\n"
            f"👮 Админ: {get_user_mention(message.from_user)}"
        )
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

@router.message(Command("demote"))
@admin_required
async def cmd_demote(message: Message):
    """Снять права модератора"""
    target = await get_target_user(message)
    if not target:
        await message.reply("❌ Укажите пользователя (@user) или ответьте на его сообщение!")
        return
    
    try:
        await bot.promote_chat_member(
            message.chat.id, 
            target.id,
            can_delete_messages=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=False
        )
        
        add_log(message.chat.id, "DEMOTE", message.from_user.full_name, target.full_name)
        
        await message.reply(
            f"⬇️ <b>Права модератора сняты</b>\n\n"
            f"👤 Пользователь: {get_user_mention(target)}\n"
            f"👮 Админ: {get_user_mention(message.from_user)}"
        )
    except TelegramBadRequest as e:
        await message.reply(f"❌ Ошибка: {e.message}")

@router.message(Command("settings"))
@admin_required
async def cmd_settings(message: Message):
    """Открыть настройки"""
    settings_rows: List[List[InlineKeyboardButton]] = []
    if WEBAPP_URL:
        settings_rows.append([InlineKeyboardButton(text="📱 Открыть панель управления", web_app=WebAppInfo(url=WEBAPP_URL))])
    settings_rows.extend([
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="⚙️ Быстрые настройки", callback_data="quick_settings")],
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=settings_rows)
    
    await message.reply(
        "⚙️ <b>Настройки бота</b>\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

# ==================== ОБРАБОТКА НОВЫХ УЧАСТНИКОВ ====================

@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_user_join(event: ChatMemberUpdated):
    """Обработка входа нового участника"""
    chat_data = get_chat_data(event.chat.id)
    user = event.new_chat_member.user
    
    # Капча
    if chat_data["settings"]["captcha"]:
        question, answer = generate_captcha()
        chat_data["captcha_pending"][str(user.id)] = {
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        }
        update_chat_data(event.chat.id, chat_data)
        
        # Ограничиваем права
        try:
            permissions = ChatPermissions(can_send_messages=False)
            await bot.restrict_chat_member(event.chat.id, user.id, permissions=permissions)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=str(random.randint(1, 20)), callback_data=f"captcha_{user.id}_wrong"),
                    InlineKeyboardButton(text=answer, callback_data=f"captcha_{user.id}_correct"),
                    InlineKeyboardButton(text=str(random.randint(1, 20)), callback_data=f"captcha_{user.id}_wrong")
                ]
            ])
            
            await bot.send_message(
                event.chat.id,
                f"🔐 {get_user_mention(user)}, решите пример:\n\n<b>{question}</b>",
                reply_markup=keyboard
            )
        except TelegramBadRequest:
            pass
    
    # Приветствие
    elif chat_data["settings"]["welcome"]:
        welcome_text = chat_data["settings"]["welcome_text"]
        
        try:
            members_count = await bot.get_chat_member_count(event.chat.id)
        except:
            members_count = 0
        
        welcome_text = welcome_text.replace("{user}", user.full_name)
        welcome_text = welcome_text.replace("{username}", f"@{user.username}" if user.username else user.full_name)
        welcome_text = welcome_text.replace("{chat}", event.chat.title or "чат")
        welcome_text = welcome_text.replace("{count}", str(members_count))
        welcome_text = welcome_text.replace("{id}", str(user.id))
        
        await bot.send_message(event.chat.id, welcome_text)

# ==================== ОБРАБОТКА КАПЧИ ====================

@router.callback_query(F.data.startswith("captcha_"))
async def captcha_callback(callback: CallbackQuery):
    """Обработка ответа на капчу"""
    parts = callback.data.split("_")
    user_id = int(parts[1])
    result = parts[2]
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ Это не ваша капча!", show_alert=True)
        return
    
    chat_data = get_chat_data(callback.message.chat.id)
    
    if result == "correct":
        # Снимаем ограничения
        try:
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
            await bot.restrict_chat_member(callback.message.chat.id, user_id, permissions=permissions)
            
            # Удаляем из ожидающих
            if str(user_id) in chat_data["captcha_pending"]:
                del chat_data["captcha_pending"][str(user_id)]
                update_chat_data(callback.message.chat.id, chat_data)
            
            await callback.message.edit_text(f"✅ {get_user_mention(callback.from_user)} прошёл проверку!")
            
            # Отправляем приветствие
            if chat_data["settings"]["welcome"]:
                welcome_text = chat_data["settings"]["welcome_text"]
                welcome_text = welcome_text.replace("{user}", callback.from_user.full_name)
                welcome_text = welcome_text.replace("{username}", f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.full_name)
                welcome_text = welcome_text.replace("{chat}", callback.message.chat.title or "чат")
                
                await bot.send_message(callback.message.chat.id, welcome_text)
        except TelegramBadRequest:
            pass
    else:
        # Неправильный ответ - кикаем
        try:
            await bot.ban_chat_member(callback.message.chat.id, user_id)
            await bot.unban_chat_member(callback.message.chat.id, user_id)
            await callback.message.edit_text(f"❌ {get_user_mention(callback.from_user)} не прошёл проверку и был удалён.")
        except TelegramBadRequest:
            pass
    
    await callback.answer()

# ==================== ФИЛЬТРАЦИЯ СООБЩЕНИЙ ====================

@router.message(F.text)
async def filter_messages(message: Message):
    """Фильтрация сообщений"""
    if message.chat.type == ChatType.PRIVATE:
        return
    
    # Пропускаем админов
    if await is_admin(message.chat.id, message.from_user.id):
        return
    
    chat_data = get_chat_data(message.chat.id)
    text_lower = message.text.lower()
    
    # Проверка фильтров
    for word in chat_data["filters"]:
        if word in text_lower:
            try:
                await message.delete()
                add_log(message.chat.id, "FILTER_DELETE", "BOT", message.from_user.full_name, f"Слово: {word}")
            except TelegramBadRequest:
                pass
            return
    
    # Автоответы
    for trigger, reply in chat_data["replies"].items():
        if trigger in text_lower:
            await message.reply(reply)
            return

# ==================== ЗАПУСК БОТА ====================

async def main():
    """Запуск бота"""
    logger.info("🛡️ Admin Guard Bot запущен!")
    
    # Удаляем вебхук если есть
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем поллинг
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
