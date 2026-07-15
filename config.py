"""Конфигурация бота. Все значения берутся из переменных окружения."""
import os

# Токен бота от @BotFather — обязателен.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Путь к файлу базы данных SQLite.
DB_PATH = os.getenv("DB_PATH", "tracker.db")

# Часовой пояс пользователя по умолчанию (смещение от UTC в часах). 3 = МСК.
DEFAULT_TZ_OFFSET = int(os.getenv("TZ_OFFSET", "3"))

# Часы (по локальному времени пользователя) для утреннего и вечернего уведомления.
MORNING_HOUR = int(os.getenv("MORNING_HOUR", "9"))
EVENING_HOUR = int(os.getenv("EVENING_HOUR", "21"))
