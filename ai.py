"""ИИ-собеседник на базе Claude (Anthropic API).

Работает, только если задан ANTHROPIC_API_KEY и установлен пакет anthropic.
Модель по умолчанию — claude-opus-4-8 (можно переопределить через AI_MODEL).
"""
import os

AI_MODEL = os.getenv("AI_MODEL", "claude-opus-4-8")
MAX_HISTORY = 12  # сколько последних реплик держим в контексте

SYSTEM_PROMPT = (
    "Ты — «Бро», тёплый и поддерживающий русскоязычный помощник в приложении для "
    "борьбы с зависимостями (курение, алкоголь, порно/онанизм, плохое питание). "
    "Собеседник борется с тягой и срывами. Твоя задача: выслушать, поддержать без "
    "осуждения, помочь пережить момент тяги и найти рабочий следующий шаг.\n\n"
    "Правила:\n"
    "- Пиши коротко и по-человечески, на «ты», как близкий друг.\n"
    "- Не осуждай за срывы — это часть пути. Хвали за честность и за держание стрика.\n"
    "- Предлагай конкретные техники: дыхание 4-7-8, переждать 10 минут, вода, спорт, "
    "смена обстановки, звонок другу.\n"
    "- Ты не врач. При тяжёлых состояниях, депрессии или мыслях о суициде мягко "
    "советуй обратиться к специалисту или на горячую линию.\n"
    "- Отвечай 2–5 предложениями, без длинных лекций. Используй уместные эмодзи."
)


def is_available() -> bool:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


async def ai_reply(history: list, user_text: str):
    """Возвращает ответ ИИ или None, если ИИ недоступен/ошибка.

    history — список dict вида {"role": "user"|"assistant", "content": str}.
    """
    if not is_available():
        return None
    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic()
        messages = history[-MAX_HISTORY:] + [{"role": "user", "content": user_text}]
        resp = await client.messages.create(
            model=AI_MODEL,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        await client.close()
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return "\n".join(parts).strip() or None
    except Exception:  # noqa: BLE001
        return None
