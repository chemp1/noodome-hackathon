"""
Каркас FAQ-бота Noodome для трёхчасового хакатона.

Команда НЕ трогает этот файл — она редактирует два текстовых файла рядом:
  ../faq.md            — база знаний (вопросы и ответы)
  system-prompt.txt    — как бот отвечает (тон, правила)

Бот перечитывает оба файла на каждое сообщение, поэтому правки
применяются сразу — без перезапуска.

Запуск (см. README.md):
  export TELEGRAM_BOT_TOKEN=...
  export ANTHROPIC_API_KEY=...
  export TEAM_CHAT_ID=...        # чат команды для эскалаций
  python bot.py
"""

import asyncio
import os
from pathlib import Path

import anthropic
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

HERE = Path(__file__).parent
FAQ_PATH = HERE.parent / "faq.md"
PROMPT_PATH = HERE / "system-prompt.txt"

ESCALATE_MARKER = "ESCALATE:"

claude = anthropic.Anthropic()  # читает ANTHROPIC_API_KEY из окружения


def ask_claude(question: str) -> str:
    """Отвечает на вопрос строго по базе знаний. Синхронно (вызываем в thread)."""
    faq = FAQ_PATH.read_text(encoding="utf-8")
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    response = claude.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": f"{system_prompt}\n\n<база_знаний>\n{faq}\n</база_знаний>",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": question}],
    )
    if response.stop_reason == "refusal":
        return f"{ESCALATE_MARKER} вопрос требует живого человека"
    return next((b.text for b in response.content if b.type == "text"), "").strip()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = update.message.text
    answer = await asyncio.to_thread(ask_claude, question)

    if answer.startswith(ESCALATE_MARKER):
        await update.message.reply_text(
            "Хороший вопрос — уточню у команды и вернусь с ответом 🙌"
        )
        team_chat_id = os.environ.get("TEAM_CHAT_ID")
        if team_chat_id:
            user = update.effective_user
            await context.bot.send_message(
                chat_id=team_chat_id,
                text=(
                    "🔔 Вопрос без ответа в базе\n"
                    f"От: {user.full_name} (@{user.username})\n"
                    f"Вопрос: {question}\n"
                    f"Суть: {answer.removeprefix(ESCALATE_MARKER).strip()}"
                ),
            )
    else:
        await update.message.reply_text(answer)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я помощник Noodome. Спросите меня про гостей, парковку, "
        "бронирования, мероприятия — отвечу по правилам клуба."
    )


def main() -> None:
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен. Ctrl+C для остановки.")
    app.run_polling()


if __name__ == "__main__":
    main()
