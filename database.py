import aiosqlite
import os
from datetime import datetime, timedelta

DATABASE_NAME = "bot_database.db"

async def init_db():
    """Initialize database and create tables"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Users table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                balance REAL DEFAULT 0.0,
                total_earned REAL DEFAULT 0.0,
                referral_count INTEGER DEFAULT 0,
                today_referrals INTEGER DEFAULT 0,
                referred_by INTEGER,
                withdraw_unlocked INTEGER DEFAULT 0,
                wallet_address TEXT,
                is_banned INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                spin_attempts INTEGER DEFAULT 3,
                last_spin_date TEXT,
                last_daily_claim TEXT,
                last_withdraw_date TEXT,
                today_withdraws INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Withdrawals table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                wallet_address TEXT,
                status TEXT DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Transactions table (for history)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Spin history table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS spin_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Settings table (for admin config)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Broadcast queue table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS broadcast_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0
            )
        ''')

        # Tasks table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                reward REAL NOT NULL,
                task_type TEXT DEFAULT 'link',
                target_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # User completed tasks
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_id INTEGER,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id),
                UNIQUE(user_id, task_id)
            )
        ''')

        await db.commit()

# ==================== USER OPERATIONS ====================

async def add_user(user_id: int, username: str = None, first_name: str = None,
                   last_name: str = None, referred_by: int = None):
    """Add new user to database"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Check if user exists
        cursor = await db.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if await cursor.fetchone():
            return False  # User already exists

        # Insert new user
        await db.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, referred_by, spin_attempts)
            VALUES (?, ?, ?, ?, ?, 3)
        ''', (user_id, username, first_name, last_name, referred_by))

        # If referred, update referrer's stats
        if referred_by and referred_by != user_id:
            # Check if referrer exists
            cursor = await db.execute('SELECT user_id FROM users WHERE user_id = ?', (referred_by,))
            if await cursor.fetchone():
                # Update referral count and balance
                await db.execute('''
                    UPDATE users
                    SET referral_count = referral_count + 1,
                        today_referrals = today_referrals + 1,
                        balance = balance + 0.08,
                        total_earned = total_earned + 0.08,
                        last_active = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                ''', (referred_by,))

                # Check and update level
                cursor = await db.execute('SELECT referral_count FROM users WHERE user_id = ?', (referred_by,))
                result = await cursor.fetchone()
                if result:
                    ref_count = result[0]
                    new_level = get_level_from_refs(ref_count)
                    await db.execute('UPDATE users SET level = ? WHERE user_id = ? AND level < ?',
                                   (new_level, referred_by, new_level))

                # Unlock withdraw if >= 5 referrals
                await db.execute('''
                    UPDATE users SET withdraw_unlocked = 1
                    WHERE user_id = ? AND referral_count >= 5
                ''', (referred_by,))

                # Add transaction record
                await db.execute('''
                    INSERT INTO transactions (user_id, type, amount, description)
                    VALUES (?, 'referral', 0.08, ?)
                ''', (referred_by, f'Referral bonus from user {user_id}'))

        await db.commit()
        return True

def get_level_from_refs(ref_count: int) -> int:
    """Get level from referral count"""
    if ref_count >= 250: return 6
    elif ref_count >= 100: return 5
    elif ref_count >= 50: return 4
    elif ref_count >= 20: return 3
    elif ref_count >= 5: return 2
    return 1

async def get_user(user_id: int):
    """Get user data"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        result = await cursor.fetchone()
        if result:
            return {
                'user_id': result[0],
                'username': result[1],
                'first_name': result[2],
                'last_name': result[3],
                'balance': result[4],
                'total_earned': result[5],
                'referral_count': result[6],
                'today_referrals': result[7],
                'referred_by': result[8],
                'withdraw_unlocked': result[9],
                'wallet_address': result[10],
                'is_banned': result[11],
                'level': result[12],
                'spin_attempts': result[13],
                'last_spin_date': result[14],
                'last_daily_claim': result[15],
                'last_withdraw_date': result[16],
                'today_withdraws': result[17],
                'created_at': result[18],
                'last_active': result[19]
            }
        return None

async def update_user_balance(user_id: int, amount: float, description: str = None):
    """Update user balance"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if amount > 0:
            await db.execute('''
                UPDATE users SET balance = balance + ?, total_earned = total_earned + ?
                WHERE user_id = ?
            ''', (amount, amount, user_id))
        else:
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))

        if description:
            await db.execute('''
                INSERT INTO transactions (user_id, type, amount, description)
                VALUES (?, 'balance', ?, ?)
            ''', (user_id, amount, description))

        await db.commit()

async def set_user_balance(user_id: int, amount: float):
    """Set user balance to specific amount"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('UPDATE users SET balance = ? WHERE user_id = ?', (amount, user_id))
        await db.commit()

async def set_wallet_address(user_id: int, wallet: str):
    """Set user wallet address"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('UPDATE users SET wallet_address = ? WHERE user_id = ?', (wallet, user_id))
        await db.commit()

async def ban_user(user_id: int, ban: bool = True):
    """Ban or unban user"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('UPDATE users SET is_banned = ? WHERE user_id = ?', (1 if ban else 0, user_id))
        await db.commit()

async def update_last_active(user_id: int):
    """Update user last active timestamp"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
        await db.commit()

async def reset_daily_stats():
    """Reset daily statistics (run once per day)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('UPDATE users SET today_referrals = 0, spin_attempts = 3, today_withdraws = 0')
        await db.commit()

async def use_spin(user_id: int):
    """Use a spin attempt"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('UPDATE users SET spin_attempts = spin_attempts - 1 WHERE user_id = ?', (user_id,))
        await db.commit()

async def get_all_users():
    """Get all users"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            SELECT user_id, username, first_name, balance, referral_count, is_banned, level
            FROM users ORDER BY created_at DESC
        ''')
        results = await cursor.fetchall()
        return [{'user_id': r[0], 'username': r[1], 'first_name': r[2], 'balance': r[3],
                 'referral_count': r[4], 'is_banned': r[5], 'level': r[6]} for r in results]

async def get_top_referrers(limit: int = 10):
    """Get top referrers"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            SELECT user_id, first_name, referral_count, balance, level
            FROM users WHERE is_banned = 0
            ORDER BY referral_count DESC LIMIT ?
        ''', (limit,))
        results = await cursor.fetchall()
        return [{'user_id': r[0], 'first_name': r[1], 'referral_count': r[2],
                 'balance': r[3], 'level': r[4]} for r in results]

async def get_total_users():
    """Get total user count"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('SELECT COUNT(*) FROM users')
        result = await cursor.fetchone()
        return result[0] if result else 0

async def get_today_users():
    """Get users joined today"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')")
        result = await cursor.fetchone()
        return result[0] if result else 0

async def get_active_users():
    """Get active users in last 24 hours"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE datetime(last_active) > datetime('now', '-24 hours')")
        result = await cursor.fetchone()
        return result[0] if result else 0

async def get_total_balance():
    """Get total balance of all users"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('SELECT SUM(balance) FROM users')
        result = await cursor.fetchone()
        return result[0] if result and result[0] else 0.0

async def get_total_referrals():
    """Get total referrals"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('SELECT SUM(referral_count) FROM users')
        result = await cursor.fetchone()
        return result[0] if result and result[0] else 0

# ==================== WITHDRAWAL OPERATIONS ====================

async def create_withdrawal(user_id: int, amount: float, wallet: str):
    """Create withdrawal request"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Deduct balance
        await db.execute('UPDATE users SET balance = balance - ?, today_withdraws = today_withdraws + 1 WHERE user_id = ?', (amount, user_id))

        # Update last withdraw date
        await db.execute("UPDATE users SET last_withdraw_date = date('now') WHERE user_id = ?", (user_id,))

        # Create withdrawal record
        await db.execute('''
            INSERT INTO withdrawals (user_id, amount, wallet_address, status)
            VALUES (?, ?, ?, 'pending')
        ''', (user_id, amount, wallet))

        # Add transaction
        await db.execute('''
            INSERT INTO transactions (user_id, type, amount, description)
            VALUES (?, 'withdraw', ?, ?)
        ''', (user_id, -amount, f'Withdrawal request to {wallet[:20]}'))

        await db.commit()

async def get_pending_withdrawals():
    """Get all pending withdrawals"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            SELECT w.id, w.user_id, u.first_name, u.username, w.amount, w.wallet_address, w.requested_at
            FROM withdrawals w
            JOIN users u ON w.user_id = u.user_id
            WHERE w.status = 'pending'
            ORDER BY w.requested_at DESC
        ''')
        results = await cursor.fetchall()
        return [{'id': r[0], 'user_id': r[1], 'first_name': r[2], 'username': r[3],
                 'amount': r[4], 'wallet_address': r[5], 'requested_at': r[6]} for r in results]

async def get_withdrawal(withdrawal_id: int):
    """Get specific withdrawal"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('SELECT * FROM withdrawals WHERE id = ?', (withdrawal_id,))
        result = await cursor.fetchone()
        if result:
            return {'id': result[0], 'user_id': result[1], 'amount': result[2],
                    'wallet_address': result[3], 'status': result[4]}
        return None

async def approve_withdrawal(withdrawal_id: int):
    """Approve withdrawal request"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            UPDATE withdrawals SET status = 'approved', processed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (withdrawal_id,))
        await db.commit()

async def reject_withdrawal(withdrawal_id: int):
    """Reject withdrawal request and refund balance"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Get withdrawal details
        cursor = await db.execute('SELECT user_id, amount FROM withdrawals WHERE id = ?', (withdrawal_id,))
        result = await cursor.fetchone()
        if result:
            user_id, amount = result
            # Refund balance
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
            # Update withdrawal status
            await db.execute('''
                UPDATE withdrawals SET status = 'rejected', processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (withdrawal_id,))
            await db.commit()

async def get_total_paid():
    """Get total amount paid out"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("SELECT SUM(amount) FROM withdrawals WHERE status = 'approved'")
        result = await cursor.fetchone()
        return result[0] if result and result[0] else 0.0

async def get_user_withdrawals(user_id: int, limit: int = 10):
    """Get user's withdrawal history"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            SELECT amount, wallet_address, status, requested_at
            FROM withdrawals WHERE user_id = ?
            ORDER BY requested_at DESC LIMIT ?
        ''', (user_id, limit))
        results = await cursor.fetchall()
        return [{'amount': r[0], 'wallet': r[1], 'status': r[2], 'date': r[3]} for r in results]

# ==================== BONUS OPERATIONS ====================

async def claim_daily_bonus(user_id: int, amount: float):
    """Claim daily bonus"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            UPDATE users
            SET balance = balance + ?,
                total_earned = total_earned + ?,
                last_daily_claim = date('now')
            WHERE user_id = ?
        ''', (amount, amount, user_id))

        await db.execute('''
            INSERT INTO transactions (user_id, type, amount, description)
            VALUES (?, 'daily_bonus', ?, 'Daily login bonus')
        ''', (user_id, amount))

        await db.commit()

async def can_claim_daily(user_id: int) -> bool:
    """Check if user can claim daily bonus"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('SELECT last_daily_claim FROM users WHERE user_id = ?', (user_id,))
        result = await cursor.fetchone()
        if result and result[0]:
            last_claim = result[0]
            today = datetime.now().strftime('%Y-%m-%d')
            return last_claim != today
        return True

async def add_spin_bonus(user_id: int, amount: float):
    """Add spin wheel bonus"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            UPDATE users
            SET balance = balance + ?,
                total_earned = total_earned + ?
            WHERE user_id = ?
        ''', (amount, amount, user_id))

        await db.execute('''
            INSERT INTO spin_history (user_id, amount)
            VALUES (?, ?)
        ''', (user_id, amount))

        await db.execute('''
            INSERT INTO transactions (user_id, type, amount, description)
            VALUES (?, 'spin', ?, 'Spin wheel bonus')
        ''', (user_id, amount))

        await db.commit()

async def get_today_spins():
    """Get total spin bonuses today"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("SELECT SUM(amount) FROM spin_history WHERE date(created_at) = date('now')")
        result = await cursor.fetchone()
        return result[0] if result and result[0] else 0.0

# ==================== TRANSACTION HISTORY ====================

async def get_user_transactions(user_id: int, limit: int = 20):
    """Get user transaction history"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            SELECT type, amount, description, created_at
            FROM transactions WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        ''', (user_id, limit))
        results = await cursor.fetchall()
        return [{'type': r[0], 'amount': r[1], 'description': r[2], 'date': r[3]} for r in results]

# ==================== STATISTICS ====================

async def get_bot_stats():
    """Get comprehensive bot statistics"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        stats = {}

        # Total users
        cursor = await db.execute('SELECT COUNT(*) FROM users')
        stats['total_users'] = (await cursor.fetchone())[0]

        # Today's users
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')")
        stats['today_users'] = (await cursor.fetchone())[0]

        # Active users (24h)
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE datetime(last_active) > datetime('now', '-24 hours')")
        stats['active_users'] = (await cursor.fetchone())[0]

        # Total balance
        cursor = await db.execute('SELECT SUM(balance) FROM users')
        result = await cursor.fetchone()
        stats['total_balance'] = result[0] if result and result[0] else 0.0

        # Total earned
        cursor = await db.execute('SELECT SUM(total_earned) FROM users')
        result = await cursor.fetchone()
        stats['total_earned'] = result[0] if result and result[0] else 0.0

        # Pending withdrawals
        cursor = await db.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'")
        stats['pending_withdrawals'] = (await cursor.fetchone())[0]

        # Total paid
        cursor = await db.execute("SELECT SUM(amount) FROM withdrawals WHERE status = 'approved'")
        result = await cursor.fetchone()
        stats['total_paid'] = result[0] if result and result[0] else 0.0

        # Total referrals
        cursor = await db.execute('SELECT SUM(referral_count) FROM users')
        result = await cursor.fetchone()
        stats['total_referrals'] = result[0] if result and result[0] else 0

        return stats

# ==================== SETTINGS ====================

async def get_setting(key: str, default: str = None):
    """Get setting value"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = await cursor.fetchone()
        return result[0] if result else default

async def set_setting(key: str, value: str):
    """Set setting value"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
        await db.commit()

# ==================== SEARCH USERS ====================

async def search_users(query: str, limit: int = 10):
    """Search users by name or ID"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            SELECT user_id, username, first_name, balance, referral_count, is_banned
            FROM users
            WHERE username LIKE ? OR first_name LIKE ? OR CAST(user_id AS TEXT) LIKE ?
            LIMIT ?
        ''', (f'%{query}%', f'%{query}%', f'%{query}%', limit))
        results = await cursor.fetchall()
        return [{'user_id': r[0], 'username': r[1], 'first_name': r[2],
                 'balance': r[3], 'referral_count': r[4], 'is_banned': r[5]} for r in results]

# ==================== TASK SYSTEM ====================

async def add_task(title: str, description: str, reward: float, task_type: str = 'link', target_url: str = None):
    """Add new task"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            INSERT INTO tasks (title, description, reward, task_type, target_url)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, description, reward, task_type, target_url))
        await db.commit()

async def get_all_tasks():
    """Get all active tasks"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('SELECT * FROM tasks WHERE is_active = 1 ORDER BY id')
        results = await cursor.fetchall()
        return [{'id': r[0], 'title': r[1], 'description': r[2], 'reward': r[3],
                 'task_type': r[4], 'target_url': r[5], 'is_active': r[6]} for r in results]

async def get_task(task_id: int):
    """Get specific task"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        result = await cursor.fetchone()
        if result:
            return {'id': result[0], 'title': result[1], 'description': result[2],
                    'reward': result[3], 'task_type': result[4], 'target_url': result[5]}
        return None

async def delete_task(task_id: int):
    """Delete task"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('UPDATE tasks SET is_active = 0 WHERE id = ?', (task_id,))
        await db.commit()

async def is_task_completed(user_id: int, task_id: int) -> bool:
    """Check if user completed task"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('SELECT id FROM user_tasks WHERE user_id = ? AND task_id = ?', (user_id, task_id))
        return await cursor.fetchone() is not None

async def complete_task(user_id: int, task_id: int):
    """Mark task as completed and give reward"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Check if already completed
        cursor = await db.execute('SELECT id FROM user_tasks WHERE user_id = ? AND task_id = ?', (user_id, task_id))
        if await cursor.fetchone():
            return False
        
        # Get task reward
        cursor = await db.execute('SELECT reward FROM tasks WHERE id = ?', (task_id,))
        result = await cursor.fetchone()
        if not result:
            return False
        
        reward = result[0]
        
        # Add reward to user
        await db.execute('UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?', 
                        (reward, reward, user_id))
        
        # Mark task completed
        await db.execute('INSERT INTO user_tasks (user_id, task_id) VALUES (?, ?)', (user_id, task_id))
        
        # Add transaction
        await db.execute('''
            INSERT INTO transactions (user_id, type, amount, description)
            VALUES (?, 'task', ?, ?)
        ''', (user_id, reward, f'Task completed - ID: {task_id}'))
        
        await db.commit()
        return True

async def get_user_completed_tasks(user_id: int):
    """Get user's completed tasks"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            SELECT t.id, t.title, t.reward, ut.completed_at
            FROM user_tasks ut
            JOIN tasks t ON ut.task_id = t.id
            WHERE ut.user_id = ?
            ORDER BY ut.completed_at DESC
        ''', (user_id,))
        results = await cursor.fetchall()
        return [{'id': r[0], 'title': r[1], 'reward': r[2], 'completed_at': r[3]} for r in results]

async def get_total_tasks():
    """Get total active tasks"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('SELECT COUNT(*) FROM tasks WHERE is_active = 1')
        result = await cursor.fetchone()
        return result[0] if result else 0