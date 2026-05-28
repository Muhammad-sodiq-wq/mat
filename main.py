"""
Telegram бот для фильтрации мата (русский + узбекский)
Установка: pip install aiogram better-profanity
"""

import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
import asyncio
import re

# ======== НАСТРОЙКИ ========
BOT_TOKEN = "ВАШ_ТОКЕН_СЮДА"  # Получить у @BotFather
MUTE_DURATION = 60  # Мут в секундах (60 = 1 минута)
WARN_BEFORE_MUTE = True  # Предупреждать перед мутом
MAX_WARNINGS = 2  # Кол-во предупреждений до мута
# ===========================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Счётчик предупреждений: {chat_id: {user_id: count}}
warnings: dict = {}

# --- Базовый список паттернов для фильтрации ---
# Здесь используем регулярки вместо явных слов
PROFANITY_PATTERNS = [
    # Русский мат — паттерны на основе корней
    r'[хx][уuy][йеёеяиi]',
    r'[пp][иi][зz][дd]',
    r'[еёe][бb][а-яa-z]',
    r'[бb][л][яy]',
    r'[сs][уuy][кk][аa]',
    r'[мm][уuy][дd][аa]',
    r'[гg][оo][вv][нn][оo]',
    r'[дd][рr][оo][чч][иi]',
    r'[шш][лl][юю][хx]',
    r'[пp][иi][дd][аa][рr]',
    r'[зz][аa][лl][уuy][пp]',
    r'[мm][мm][дd][аa]',
    # Узбекский мат — паттерны
    r'[аa][мm][аa][кk][иi]',
    r'[оo][тt][аa][кk][иi]',
    r'[сs][иi][кk][аa]',
    r'[бb][еe][кk][аa][сs]',
    r'[кk][аa][лl][тt][аa][кk]',
    r'[хx][аa][рr][оo][мm]',
    r'[тt][еe][лl][бb][аa]',
    r'[еe][шш][аa][кk]',
    r'[нn][оo][дd][оo][нn]',
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in PROFANITY_PATTERNS]


def contains_profanity(text: str) -> bool:
    """Проверяет текст на наличие мата"""
    # Нормализация: заменяем цифры и похожие символы
    normalized = text.lower()
    normalized = normalized.replace('0', 'о').replace('3', 'з').replace('1', 'и')
    normalized = normalized.replace('@', 'а').replace('4', 'ч').replace('6', 'б')

    for pattern in COMPILED:
        if pattern.search(normalized):
            return True
    return False


def get_warnings(chat_id: int, user_id: int) -> int:
    return warnings.get(chat_id, {}).get(user_id, 0)


def add_warning(chat_id: int, user_id: int) -> int:
    if chat_id not in warnings:
        warnings[chat_id] = {}
    warnings[chat_id][user_id] = warnings[chat_id].get(user_id, 0) + 1
    return warnings[chat_id][user_id]


def reset_warnings(chat_id: int, user_id: int):
    if chat_id in warnings and user_id in warnings[chat_id]:
        warnings[chat_id][user_id] = 0


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👮 Бот-модератор активирован!\n\n"
        "Я слежу за соблюдением правил чата.\n"
        f"⚠️ Предупреждений до мута: {MAX_WARNINGS}\n"
        f"🔇 Длительность мута: {MUTE_DURATION} сек."
    )


@dp.message(Command("warnings"))
async def cmd_warnings(message: Message):
    """Показать предупреждения пользователя"""
    count = get_warnings(message.chat.id, message.from_user.id)
    await message.answer(
        f"⚠️ У вас {count}/{MAX_WARNINGS} предупреждений."
    )


@dp.message(Command("resetwarnings"))
async def cmd_reset(message: Message):
    """Сброс предупреждений (только для админов)"""
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ("administrator", "creator"):
        await message.answer("❌ Только администраторы могут сбрасывать предупреждения.")
        return

    if message.reply_to_message:
        target = message.reply_to_message.from_user
        reset_warnings(message.chat.id, target.id)
        await message.answer(f"✅ Предупреждения {target.full_name} сброшены.")
    else:
        await message.answer("↩️ Ответьте на сообщение пользователя.")


@dp.message(F.text)
async def filter_message(message: Message):
    """Основной обработчик сообщений"""
    if not message.text:
        return

    # Пропускаем ботов
    if message.from_user.is_bot:
        return

    # Пропускаем админов
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status in ("administrator", "creator"):
            return
    except Exception:
        pass

    if contains_profanity(message.text):
        user = message.from_user
        chat_id = message.chat.id

        # Удаляем сообщение
        try:
            await message.delete()
        except Exception:
            pass

        warn_count = add_warning(chat_id, user.id)

        if WARN_BEFORE_MUTE and warn_count < MAX_WARNINGS:
            await message.answer(
                f"⚠️ {user.mention_html()}, нецензурная лексика запрещена!\n"
                f"Предупреждение {warn_count}/{MAX_WARNINGS}.",
                parse_mode="HTML"
            )
        else:
            # Мутим пользователя
            try:
                from aiogram.types import ChatPermissions
                from datetime import datetime, timedelta

                until = datetime.now() + timedelta(seconds=MUTE_DURATION)
                await bot.restrict_chat_member(
                    chat_id,
                    user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until
                )
                reset_warnings(chat_id, user.id)
                await message.answer(
                    f"🔇 {user.mention_html()} получил мут на {MUTE_DURATION} секунд "
                    f"за нецензурную лексику.",
                    parse_mode="HTML"
                )
            except Exception as e:
                await message.answer(
                    f"⚠️ {user.mention_html()}, последнее предупреждение!",
                    parse_mode="HTML"
                )
                logging.error(f"Mute error: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())