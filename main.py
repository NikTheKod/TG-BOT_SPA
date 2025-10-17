import logging
import sqlite3
import threading
from datetime import datetime
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_FOR_QUESTION = 1

class TicketSystem:
    def __init__(self, db_path='tickets.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()
        self.lock = threading.Lock()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                question TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
        cursor.close()

    def create_ticket(self, user_id, username, first_name, question):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO tickets (user_id, username, first_name, question, status)
                VALUES (?, ?, ?, ?, 'open')
            ''', (user_id, username, first_name, question))
            ticket_id = cursor.lastrowid
            self.conn.commit()
            cursor.close()
            return ticket_id

    def get_user_ticket(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, user_id, username, first_name, question, status, created_at
            FROM tickets 
            WHERE user_id = ? AND status = 'open'
            ORDER BY created_at DESC 
            LIMIT 1
        ''', (user_id,))
        ticket = cursor.fetchone()
        cursor.close()
        return ticket

    def close_ticket(self, ticket_id):
        """Закрывает тикет по ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM tickets WHERE id = ?', (ticket_id,))
            self.conn.commit()
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка при закрытии тикета: {e}")
            return False

    def close_user_ticket(self, user_id):
        """Закрывает активный тикет пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM tickets WHERE user_id = ? AND status = "open"', (user_id,))
            rows_affected = cursor.rowcount
            self.conn.commit()
            cursor.close()
            return rows_affected > 0
        except Exception as e:
            logger.error(f"Ошибка при закрытии тикета пользователя: {e}")
            return False

    def get_all_tickets(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, user_id, username, first_name, question, status, created_at
            FROM tickets 
            WHERE status = 'open'
            ORDER BY created_at DESC
        ''')
        tickets = cursor.fetchall()
        cursor.close()
        return tickets

class SupportBot:
    def __init__(self, token, admin_chat_id):
        self.token = token
        self.admin_chat_id = admin_chat_id
        self.application = Application.builder().token(token).build()
        self.ticket_system = TicketSystem()
        
        self.setup_handlers()

    def setup_handlers(self):
        # Команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("closeticket", self.close_ticket_command))
        
        # Обработчики кнопок
        self.application.add_handler(CallbackQueryHandler(self.button_handler, pattern='^support$'))
        self.application.add_handler(CallbackQueryHandler(self.button_handler, pattern='^faq$'))
        self.application.add_handler(CallbackQueryHandler(self.button_handler, pattern='^status$'))
        self.application.add_handler(CallbackQueryHandler(self.button_handler, pattern='^back$'))
        self.application.add_handler(CallbackQueryHandler(self.show_server_status, pattern='^server_status$'))
        
        # Обработчик сообщений для поддержки
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_user_message))
        
        # ConversationHandler для создания тикетов
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_support_chat, pattern='^start_support$')],
            states={
                WAITING_FOR_QUESTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_support_question)
                ],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_support)],
            per_message=False
        )
        self.application.add_handler(conv_handler)
        
        # Обработчики ошибок
        self.application.add_error_handler(self.error_handler)

    async def start(self, update: Update, context):
        user = update.effective_user
        keyboard = [
            [InlineKeyboardButton("Написать в поддержку", callback_data="start_support")],
            [InlineKeyboardButton("Частые вопросы", callback_data="faq")],
            [InlineKeyboardButton("Статус серверов", callback_data="server_status")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            f"Привет, {user.first_name}!\n\n"
            "Добро пожаловать в поддержку STALKER SPA.\n"
            "Выберите нужный вариант:"
        )
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    async def button_handler(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == 'support':
            await self.show_support_options(query)
        elif data == 'faq':
            await self.show_faq(query)
        elif data == 'status':
            await self.show_server_status(query)
        elif data == 'back':
            await self.show_main_menu(query)

    async def show_main_menu(self, query):
        keyboard = [
            [InlineKeyboardButton("Написать в поддержку", callback_data="start_support")],
            [InlineKeyboardButton("Частые вопросы", callback_data="faq")],
            [InlineKeyboardButton("Статус серверов", callback_data="server_status")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Главное меню поддержки STALKER SPA:\n\n"
            "Выберите нужный вариант:",
            reply_markup=reply_markup
        )

    async def show_support_options(self, query):
        keyboard = [
            [InlineKeyboardButton("Начать чат с поддержкой", callback_data="start_support")],
            [InlineKeyboardButton("Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📞 Поддержка STALKER SPA\n\n"
            "Здесь вы можете задать вопрос нашей технической поддержке.\n"
            "Среднее время ответа: 5-15 минут",
            reply_markup=reply_markup
        )

    async def start_support_chat(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        ticket = self.ticket_system.get_user_ticket(user.id)
        
        if ticket:
            ticket_text = (
                "⚠️ У вас уже есть активный тикет\n\n"
                f"ID тикета: #{ticket[0]}\n"
                f"Ваш вопрос: {ticket[4]}\n"
                f"Создан: {ticket[6]}\n\n"
                "Дождитесь ответа поддержки или закройте текущий тикет командой /closeticket"
            )
            await query.edit_message_text(ticket_text)
            return ConversationHandler.END
        
        support_text = (
            "💬 Чат с поддержкой\n\n"
            "Опишите вашу проблему или вопрос подробно.\n"
            "Мы постараемся ответить как можно скорее.\n\n"
            "Для отмены используйте /cancel"
        )
        
        await query.edit_message_text(support_text)
        return WAITING_FOR_QUESTION

    async def handle_support_question(self, update: Update, context):
        user = update.effective_user
        question = update.message.text
        
        # Создаем тикет
        ticket_id = self.ticket_system.create_ticket(
            user.id, 
            user.username, 
            user.first_name, 
            question
        )
        
        # Отправляем уведомление админу
        admin_message = (
            f"🆕 Новый тикет #{ticket_id}\n"
            f"👤 Пользователь: {user.first_name} (@{user.username or 'N/A'})\n"
            f"🆔 ID: {user.id}\n"
            f"❓ Вопрос: {question}"
        )
        
        try:
            await self.application.bot.send_message(
                chat_id=self.admin_chat_id,
                text=admin_message,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Ответить", callback_data=f"reply_{ticket_id}"),
                    InlineKeyboardButton("Закрыть", callback_data=f"close_{ticket_id}")
                ]])
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу: {e}")
        
        # Ответ пользователю
        success_text = (
            f"✅ Ваш тикет #{ticket_id} создан!\n\n"
            f"Ваш вопрос: {question}\n\n"
            "Ожидайте ответа поддержки. Мы свяжемся с вами в этом чате.\n"
            "Среднее время ответа: 5-15 минут\n\n"
            "Чтобы закрыть тикет, используйте /closeticket"
        )
        
        await update.message.reply_text(success_text)
        return ConversationHandler.END

    async def cancel_support(self, update: Update, context):
        await update.message.reply_text("Создание тикета отменено.")
        return ConversationHandler.END

    async def close_ticket_command(self, update: Update, context):
        user = update.effective_user
        ticket = self.ticket_system.get_user_ticket(user.id)
        
        if not ticket:
            await update.message.reply_text("У вас нет активных тикетов.")
            return
        
        # Используем новый метод close_ticket
        if self.ticket_system.close_ticket(ticket[0]):
            await update.message.reply_text("✅ Ваш тикет закрыт.")
        else:
            await update.message.reply_text("❌ Ошибка при закрытии тикета.")

    async def show_faq(self, query):
        faq_text = (
            "❓ Частые вопросы\n\n"
            "1. ❓ Как восстановить пароль?\n"
            "   ✅ Используйте функцию 'Забыли пароль' на странице входа\n\n"
            "2. ❓ Сервер не отвечает, что делать?\n"
            "   ✅ Проверьте статус серверов в соответствующем разделе\n\n"
            "3. ❓ Как пополнить баланс?\n"
            "   ✅ Доступные методы оплаты: карта, Qiwi, Яндекс.Деньги\n\n"
            "4. ❓ Не запускается лаунчер?\n"
            "   ✅ Попробуйте запустить от имени администратора\n\n"
            "Если вы не нашли ответ на свой вопрос - напишите в поддержку!"
        )
        
        keyboard = [[InlineKeyboardButton("Назад", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(faq_text, reply_markup=reply_markup)
        except telegram.error.BadRequest as e:
            if "Message is not modified" in str(e):
                pass
            else:
                raise e

    async def show_server_status(self, query):
        # Здесь можно добавить реальную проверку статуса серверов
        status_text = (
            "🟢 Статус серверов STALKER SPA\n\n"
            "• Игровой сервер #1: 🟢 ONLINE\n"
            "• Игровой сервер #2: 🟢 ONLINE\n"
            "• Веб-сайт: 🟢 ONLINE\n"
            "• База данных: 🟢 ONLINE\n\n"
            "Обновлено: " + datetime.now().strftime("%H:%M:%S")
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="server_status")],
            [InlineKeyboardButton("Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(status_text, reply_markup=reply_markup)
        except telegram.error.BadRequest as e:
            if "Message is not modified" in str(e):
                # Игнорируем ошибку, если сообщение не изменилось
                pass
            else:
                raise e

    async def handle_user_message(self, update: Update, context):
        # Обработка сообщений пользователя (для ответов в тикетах)
        user = update.effective_user
        message_text = update.message.text
        
        ticket = self.ticket_system.get_user_ticket(user.id)
        if ticket:
            # Пересылаем сообщение админу
            admin_message = (
                f"💬 Сообщение из тикета #{ticket[0]}\n"
                f"👤 {user.first_name} (@{user.username or 'N/A'}):\n"
                f"{message_text}"
            )
            
            try:
                await self.application.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=admin_message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Ответить", callback_data=f"reply_{ticket[0]}"),
                        InlineKeyboardButton("Закрыть", callback_data=f"close_{ticket[0]}")
                    ]])
                )
                await update.message.reply_text("✅ Сообщение отправлено в поддержку.")
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения админу: {e}")
                await update.message.reply_text("❌ Ошибка отправки сообщения.")

    async def error_handler(self, update: Update, context):
        logger.error(msg="Exception while handling an update:", exc_info=context.error)

    def run(self):
        logger.info("🛠️ Бот поддержки STALKER SPA запущен!")
        self.application.run_polling()

if __name__ == '__main__':
    # Конфигурация
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Замените на ваш токен
    ADMIN_CHAT_ID = "YOUR_ADMIN_CHAT_ID_HERE"  # Замените на ID чата админа
    
    bot = SupportBot(BOT_TOKEN, ADMIN_CHAT_ID)
    bot.run()
