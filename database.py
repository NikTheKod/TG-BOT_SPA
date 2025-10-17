import sqlite3
import datetime

class TicketSystem:
    def __init__(self):
        self.conn = sqlite3.connect('tickets.db', check_same_thread=False)
        self.create_table()
    
    def create_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_name TEXT,
                support_id INTEGER,
                status TEXT,
                created_at TEXT,
                last_message TEXT
            )
        ''')
        self.conn.commit()
    
    def create_ticket(self, user_id, user_name):
        ticket_id = self.conn.execute('''
            INSERT INTO tickets (user_id, user_name, status, created_at) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, user_name, 'open', datetime.datetime.now().isoformat())).lastrowid
        self.conn.commit()
        return ticket_id
    
    def assign_support(self, ticket_id, support_id):
        self.conn.execute('''
            UPDATE tickets SET support_id = ?, status = 'in_progress' WHERE id = ?
        ''', (support_id, ticket_id))
        self.conn.commit()
    
    def get_user_ticket(self, user_id):
        cursor = self.conn.execute('SELECT * FROM tickets WHERE user_id = ? AND status != "closed"', (user_id,))
        return cursor.fetchone()

def close_ticket(self, ticket_id):
    self.conn.execute('''
        UPDATE tickets SET status = 'closed' WHERE id = ?
    ''', (ticket_id,))
    self.conn.commit()
