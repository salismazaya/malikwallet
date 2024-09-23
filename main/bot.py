from telebot import TeleBot
from django.conf import settings

bot = TeleBot(settings.TELEGRAM_BOT_TOKEN)