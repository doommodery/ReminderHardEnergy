from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.db import init_db
from app.service import CourtScheduleService

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

service = CourtScheduleService()
bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.tz))


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/today"), KeyboardButton(text="/tomorrow")],
            [KeyboardButton(text="/next"), KeyboardButton(text="/reload")],
            [KeyboardButton(text="/start")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери команду или введи /date YYYY-MM-DD",
    )


def local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.tz))


async def answer_with_menu(message: Message, text: str) -> None:
    await message.answer(text, reply_markup=main_menu())


async def notify_all(text: str) -> None:
    for chat_id in settings.chat_id_list:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=main_menu(),
            )
        except Exception as e:
            logger.exception("Не удалось отправить сообщение в chat_id=%s: %s", chat_id, e)


async def sync_job(silent: bool = False) -> None:
    stats = service.sync()
    logger.info("Sync complete: %s", stats)
    if not silent:
        await notify_all(f"✅ Таблица обновлена. Активных событий: {stats['active_events']}")


async def reminder_job() -> None:
    rows, now = service.due_notifications()
    for row in rows:
        text = service.format_reminder_header(row) + "\n\n" + service.format_event(row)
        await notify_all(text)
        service.mark_sent(row["event_uid"], row["reminder_code"], now)


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await answer_with_menu(
        message,
        "Бот активен.\n\n"
        "Команды:\n"
        "/today — события на сегодня\n"
        "/tomorrow — события на завтра\n"
        "/date YYYY-MM-DD — события на дату\n"
        "/next — ближайшие события\n"
        "/reload — принудительно обновить таблицу"
    )


@dp.message(Command("today"))
async def cmd_today(message: Message) -> None:
    today = local_now().date()
    await answer_with_menu(message, service.events_for_date(today.isoformat()))


@dp.message(Command("chatid"))
async def cmd_chatid(message: Message) -> None:
    await answer_with_menu(
    message,
    f"chat_id: {message.chat.id}\n"
    f"type: {message.chat.type}\n"
    f"title: {message.chat.title or 'private'}"
    )

@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: Message) -> None:
    tomorrow = local_now().date() + timedelta(days=1)
    await answer_with_menu(message, service.events_for_date(tomorrow.isoformat()))


@dp.message(Command("next"))
async def cmd_next(message: Message) -> None:
    await answer_with_menu(message, service.next_events(limit=10))


@dp.message(Command("reload"))
async def cmd_reload(message: Message) -> None:
    stats = service.sync()
    await answer_with_menu(
        message,
        f"✅ Таблица обновлена. Активных событий: {stats['active_events']}"
    )


@dp.message(Command("date"))
async def cmd_date(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await answer_with_menu(message, "Используй формат: /date 2026-05-25")
        return

    try:
        requested = datetime.strptime(parts[1], "%Y-%m-%d").date()
    except ValueError:
        await answer_with_menu(message, "Неверный формат даты. Нужен YYYY-MM-DD.")
        return

    await answer_with_menu(message, service.events_for_date(requested.isoformat()))


@dp.message(F.text)
async def fallback(message: Message) -> None:
    await answer_with_menu(
        message,
        "Не понял команду.\n"
        "Доступно: /today, /tomorrow, /next, /reload, /date YYYY-MM-DD"
    )


async def main() -> None:
    init_db()
    await sync_job(silent=True)

    scheduler.add_job(
        sync_job,
        "cron",
        hour=settings.sync_hour,
        minute=0,
        kwargs={"silent": False},
    )

    # Проверка напоминаний каждую минуту
    scheduler.add_job(reminder_job, "interval", minutes=1)

    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())