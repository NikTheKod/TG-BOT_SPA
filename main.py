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
    
    def get_main_keyboard(self):
        """Главное меню с кнопками"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Написать в поддержку", callback_data="start_chat")],
            [InlineKeyboardButton("📋 Частые вопросы", callback_data="faq")],
            [InlineKeyboardButton("🌐 Статус серверов", callback_data="server_status")]
        ])
    
    async def start(self, update: Update, context):
        user = update.effective_user
        await update.message.reply_text(
            f"🛠️ Привет, сталкер {user.first_name}!\n\n"
            "Добро пожаловать в поддержку STALKER SPA.\n"
            "Выберите действие:",
            reply_markup=self.get_main_keyboard()
        )
    
    async def ticket_command(self, update: Update, context):
        """Команда /ticket - открыть тикет"""
        user = update.effective_user
        user_id = user.id
        
        # Проверяем есть ли активный тикет
        existing_ticket = self.ticket_system.get_user_ticket(user_id)
        if existing_ticket:
            await update.message.reply_text(
                f"⚠️ У вас уже есть активный тикет #{existing_ticket[0]}\n"
                "Дождитесь ответа поддержки или закройте текущий тикет.",
                reply_markup=self.get_main_keyboard()
            )
            return
        
        # Создаем новый тикет
        ticket_id = self.ticket_system.create_ticket(user_id, user.username or user.first_name)
        
        # Уведомляем поддержку
        support_message = (
            f"🆕 НОВЫЙ ТИКЕТ ОТ КОМАНДЫ /ticket\n"
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
        
        await update.message.reply_text(
            f"✅ Тикет #{ticket_id} создан!\n"
            "Ожидайте ответа поддержки. Вы можете писать сообщения прямо здесь.",
            reply_markup=self.get_main_keyboard()
        )
    
    async def close_ticket_command(self, update: Update, context):
        """Команда /closeticket - закрыть тикет пользователем"""
        user_id = update.effective_user.id
        
        # Ищем активный тикет
        ticket = self.ticket_system.get_user_ticket(user_id)
        if not ticket:
            await update.message.reply_text(
                "❌ У вас нет активных тикетов.",
                reply_markup=self.get_main_keyboard()
            )
            return
        
        # Закрываем тикет
        self.ticket_system.close_ticket(ticket[0])
        
        # Очищаем активный чат
        if user_id in self.active_chats:
            support_id = self.active_chats[user_id]
            self.active_chats.pop(user_id, None)
            self.active_chats.pop(support_id, None)
            
            # Уведомляем поддержку
            try:
                await context.bot.send_message(support_id, f"❌ Пользователь закрыл тикет #{ticket[0]}")
            except:
                pass
        
        await update.message.reply_text(
            f"✅ Тикет #{ticket[0]} закрыт.\n"
            "Спасибо за обращение!",
            reply_markup=self.get_main_keyboard()
        )
    
    async def admin_close_ticket_command(self, update: Update, context):
        """Команда /admincloseticket - закрыть тикет админом"""
        user_id = update.effective_user.id
        
        # Проверяем права админа
        if user_id not in SUPPORT_IDS:
            await update.message.reply_text("❌ Эта команда только для поддержки.")
            return
        
        # Проверяем аргументы команды
        if not context.args:
            await update.message.reply_text("❌ Использование: /admincloseticket <user_id>")
            return
        
        try:
            target_user_id = int(context.args[0])
            ticket = self.ticket_system.get_user_ticket(target_user_id)
            
            if not ticket:
                await update.message.reply_text("❌ У пользователя нет активных тикетов.")
                return
            
            # Закрываем тикет
            self.ticket_system.close_ticket(ticket[0])
            
            # Очищаем активный чат
            if target_user_id in self.active_chats:
                self.active_chats.pop(target_user_id, None)
                self.active_chats.pop(user_id, None)  # support_id
            
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    target_user_id, 
                    f"✅ Ваш тикет #{ticket[0]} закрыт поддержкой."
                )
            except:
                pass
            
            await update.message.reply_text(f"✅ Тикет #{ticket[0]} закрыт.")
            
        except ValueError:
            await update.message.reply_text("❌ Неверный user_id.")
    
    async def start_chat_with_support(self, update: Update, context):
        """Обработчик кнопки 'Написать в поддержку'"""
        query = update.callback_query
        await query.answer()  # Убираем "часики"
        
        user = query.from_user
        user_id = user.id
        
        # Проверяем есть ли активный тикет
        existing_ticket = self.ticket_system.get_user_ticket(user_id)
        if existing_ticket:
            await query.edit_message_text(
                f"⚠️ У вас уже есть активный тикет #{existing_ticket[0]}\n"
                "Дождитесь ответа поддержки или закройте текущий тикет командой /closeticket",
                reply_markup=self.get_main_keyboard()
            )
            return
        
        # Создаем тикет
        ticket_id = self.ticket_system.create_ticket(user_id, user.username or user.first_name)
        
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
            f"💬 Тикет #{ticket_id} создан! Ожидайте ответа поддержки...\n\n"
            "Напишите ваше сообщение прямо сейчас:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить тикет", callback_data="cancel_chat")],
                [InlineKeyboardButton("📋 Главное меню", callback_data="main_menu")]
            ])
        )
        
        return States.AWAITING_SUPPORT_RESPONSE
    
    async def show_faq(self, update: Update, context):
        """Показать частые вопросы"""
        query = update.callback_query
        await query.answer()
        
        faq_text = (
            "📋 Частые вопросы STALKER SPA:\n\n"
            "❓ Установка:\n"
            "• Скачайте лаунчер с официального сайта\n"
            "• Запустите установщик от имени администратора\n\n"
            "🔧 Ошибки:\n"
            "• Переустановите DirectX 11\n"
            "• Обновите драйвера видеокарты\n\n"
            "🎮 Моды:\n"
            "• Доступны через встроенный мод-менеджер\n\n"
            "Нужна дополнительная помощь? Напишите в поддержку!"
        )
        
        await query.edit_message_text(
            faq_text,
            reply_markup=self.get_main_keyboard()
        )
    
    async def show_server_status(self, update: Update, context):
        """Показать статус серверов"""
        query = update.callback_query
        await query.answer()
        
        status_text = (
            "🌐 Статус серверов STALKER SPA:\n\n"
            "🟢 SPA-1 (Европа): 145/150 игроков\n"
            "🟢 SPA-2 (Россия): 89/150 игроков\n"
            "🟡 SPA-3 (Азия): 67/150 игроков\n"
            "🔴 SPA-4 (Америка): на тех. работах\n\n"
            "Общий онлайн: 301 игрок"
        )
        
        await query.edit_message_text(
            status_text,
            reply_markup=self.get_main_keyboard()
        )
    
    async def show_main_menu(self, update: Update, context):
        """Вернуться в главное меню"""
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        await query.edit_message_text(
            f"🛠️ Привет, сталкер {user.first_name}!\n\n"
            "Добро пожаловать в поддержку STALKER SPA.\n"
            "Выберите действие:",
            reply_markup=self.get_main_keyboard()
        )
    
    async def accept_ticket(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        
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
                "✅ С вами подключился специалист поддержки. Можете общаться!",
                reply_markup=self.get_main_keyboard()
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
                await update.message.reply_text("✅ Сообщение доставлено", reply_markup=self.get_main_keyboard())
            except:
                await update.message.reply_text("❌ Поддержка сейчас недоступна", reply_markup=self.get_main_keyboard())
        else:
            await update.message.reply_text("⏳ Ожидайте подключения поддержки...", reply_markup=self.get_main_keyboard())
    
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
        await query.answer()
        
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
        
        await query.edit_message_text(
            "❌ Чат с поддержкой завершен",
            reply_markup=self.get_main_keyboard()
        )
        return ConversationHandler.END

# Настройка Conversation Handler
def setup_handlers(app):
    bot = StalkerSupportBot()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(bot.start_chat_with_support, pattern='^start_chat$'),
            CommandHandler('ticket', bot.ticket_command)
        ],
        states={
            States.AWAITING_SUPPORT_RESPONSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.forward_to_support),
                CallbackQueryHandler(bot.cancel_chat, pattern='^cancel_chat$'),
                CallbackQueryHandler(bot.show_main_menu, pattern='^main_menu$')
            ],
            States.AWAITING_USER_RESPONSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.forward_to_user)
            ]
        },
        fallbacks=[CommandHandler('cancel', bot.cancel_chat)]
    )
    
    # Команды
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("ticket", bot.ticket_command))
    app.add_handler(CommandHandler("closeticket", bot.close_ticket_command))
    app.add_handler(CommandHandler("admincloseticket", bot.admin_close_ticket_command))
    
    # Обработчики callback
    app.add_handler(CallbackQueryHandler(bot.accept_ticket, pattern='^accept_ticket_'))
    app.add_handler(CallbackQueryHandler(bot.show_faq, pattern='^faq$'))
    app.add_handler(CallbackQueryHandler(bot.show_server_status, pattern='^server_status$'))
    app.add_handler(CallbackQueryHandler(bot.show_main_menu, pattern='^main_menu$'))
    
    app.add_handler(conv_handler)
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(SUPPORT_IDS), 
        bot.forward_to_user
    ))
    
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
