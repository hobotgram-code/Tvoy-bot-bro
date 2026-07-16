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

# Напоминания о тренировке, витаминах и еженедельном фото.
VITAMIN_HOUR = int(os.getenv("VITAMIN_HOUR", "10"))     # приём витаминов
PHOTO_HOUR = int(os.getenv("PHOTO_HOUR", "12"))         # еженедельное фото
PHOTO_WEEKDAY = int(os.getenv("PHOTO_WEEKDAY", "6"))    # 6 = воскресенье
WORKOUT_HOUR = int(os.getenv("WORKOUT_HOUR", "17"))     # напоминание о тренировке
# Дни тренировок (0=Пн … 6=Вс). По умолчанию 5 дней: Пн–Пт.
WORKOUT_DAYS = {int(x) for x in os.getenv("WORKOUT_DAYS", "0,1,2,3,4").split(",")}

# Еженедельный авто-бэкап данных пользователю (JSON в Telegram).
BACKUP_HOUR = int(os.getenv("BACKUP_HOUR", "11"))
BACKUP_WEEKDAY = int(os.getenv("BACKUP_WEEKDAY", "6"))  # 6 = воскресенье
