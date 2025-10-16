import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from config import BOT_TOKEN, SUPPORT_IDS, States
from database import TicketSystem

class StalkerSupportBot:
    def __init__(self):
        self.ticket_system = TicketSystem()
        self.active_chats = {}  # {user_id: support_id, support_id: user_id}
    
    async def start(self, update: Update, context):
        user = update.effective_user
        keyboard = [
            [InlineKeyboardButton("💬 Написать в поддержку", callback_data="start_chat")],
            [InlineKeyboardButton("📋 Частые вопросы", callback_data="faq")],
            [InlineKeyboardButton("🌐 Статус серверов", callback_data="server_status")]
        ]
        
        await update.message.reply_text(
            f"🛠️ Привет, сталкер {user.first_name}!\n\n"
            "Добро пожаловать в поддержку STALKER SPA.\n"
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def start_chat_with_support(self, update: Update, context):
        query = update.callback_query
        user = query.from_user
        user_id = user.id
        
        # Создаем тикет
        ticket = self.ticket_system.get_user_ticket(user_id)
        if not ticket:
            ticket_id = self.ticket_system.create_ticket(user_id, user.username or user.first_name)
        else:
            ticket_id = ticket[0]
        
        # Уведомляем поддержку
        support_message = (
            f"🆕 НОВЫЙ ЗАПРОС В ПОДДЕРЖКУ\n"
            f"👤 Пользователь: @{user.username or 'No username'}\n"
            f"🆔 ID: {user_id}\n"
            f"📋 Тикет: #{ticket_id}\n\n"
            f"Нажмите кнопку ниже чтобы ответить:"
        )
        
        keyboard = [[InlineKeyboardButton("💬 Ответить", callback_data=f"accept_ticket_{user_id}")]]
        
        for support_id in SUPPORT_IDS:
            try:
                await context.bot.send_message(support_id, support_message, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as e:
                print(f"Не удалось уведомить поддержку {support_id}: {e}")
        
        await query.edit_message_text(
            "💬 Ваше сообщение отправлено в поддержку. Ожидайте ответа...\n\n"
            "Напишите ваше сообщение прямо сейчас:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отменить", callback_data="cancel_chat")]])
        )
        
        return States.AWAITING_SUPPORT_RESPONSE
    
    async def accept_ticket(self, update: Update, context):
        query = update.callback_query
        support_id = query.from_user.id
        user_id = int(query.data.split('_')[-1])
        
        # Связываем пользователя и поддержку
        self.active_chats[user_id] = support_id
        self.active_chats[support_id] = user_id
        
        # Обновляем тикет
        ticket = self.ticket_system.get_user_ticket(user_id)
        if ticket:
            self.ticket_system.assign_support(ticket[0], support_id)
        
        await query.edit_message_text(
            f"💬 Вы подключились к чату с пользователем.\n"
            f"Теперь все ваши сообщения будут пересылаться ему.\n\n"
            f"Напишите приветственное сообщение:"
        )
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                user_id, 
                "✅ С вами подключился специалист поддержки. Можете общаться!"
            )
        except:
            pass
        
        return States.AWAITING_USER_RESPONSE
    
    async def forward_to_support(self, update: Update, context):
        user_id = update.effective_user.id
        message_text = update.message.text
        
        if user_id in self.active_chats:
            support_id = self.active_chats[user_id]
            try:
                await context.bot.send_message(
                    support_id,
                    f"👤 Игрок: {message_text}"
                )
                await update.message.reply_text("✅ Сообщение доставлено")
            except:
                await update.message.reply_text("❌ Поддержка сейчас недоступна")
        else:
            await update.message.reply_text("⏳ Ожидайте подключения поддержки...")
    
    async def forward_to_user(self, update: Update, context):
        support_id = update.effective_user.id
        message_text = update.message.text
        
        if support_id in self.active_chats:
            user_id = self.active_chats[support_id]
            try:
                await context.bot.send_message(
                    user_id,
                    f"🛠️ Поддержка: {message_text}"
                )
                await update.message.reply_text("✅ Сообщение доставлено игроку")
            except:
                await update.message.reply_text("❌ Игрок отключился")
        else:
            await update.message.reply_text("❌ Нет активных чатов")
    
    async def cancel_chat(self, update: Update, context):
        query = update.callback_query
        user_id = query.from_user.id
        
        # Очищаем чат
        if user_id in self.active_chats:
            support_id = self.active_chats[user_id]
            self.active_chats.pop(user_id, None)
            self.active_chats.pop(support_id, None)
            
            # Уведомляем поддержку
            try:
                await context.bot.send_message(support_id, "❌ Пользователь завершил чат")
            except:
                pass
        
        await query.edit_message_text("❌ Чат с поддержкой завершен")
        return ConversationHandler.END

# Настройка Conversation Handler
def setup_handlers(app):
    bot = StalkerSupportBot()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot.start_chat_with_support, pattern='^start_chat$')],
        states={
            States.AWAITING_SUPPORT_RESPONSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.forward_to_support),
                CallbackQueryHandler(bot.cancel_chat, pattern='^cancel_chat$')
            ],
            States.AWAITING_USER_RESPONSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.forward_to_user)
            ]
        },
        fallbacks=[CommandHandler('cancel', bot.cancel_chat)]
    )
    
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CallbackQueryHandler(bot.accept_ticket, pattern='^accept_ticket_'))
    app.add_handler(conv_handler)
    
    # Обработчики для поддержки
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(SUPPORT_IDS), 
        bot.forward_to_user
    ))
    
    # Обработчики для пользователей
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.User(SUPPORT_IDS), 
        bot.forward_to_support
    ))

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(app)
    
    print("🛠️ Бот поддержки STALKER SPA запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
