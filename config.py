import os

# Токен бота
BOT_TOKEN = os.environ.get('8393818320:AAG9P89WyHZvLg1lNpjyk2vyKoTQ0qyBnzM')

# ID администраторов/поддержки
SUPPORT_IDS = [5109664392, 987654321]  # Замени на реальные ID

# Состояния бота
class States:
    AWAITING_SUPPORT_RESPONSE = 1
    AWAITING_USER_RESPONSE = 2
