import os

# Токен бота
BOT_TOKEN = os.environ.get('BOT_TOKEN')  # Только имя переменной!

# ID администраторов/поддержки
SUPPORT_IDS = [5109664392]  # Убери fake ID 987654321

# Состояния бота
class States:
    AWAITING_SUPPORT_RESPONSE = 1
    AWAITING_USER_RESPONSE = 2
