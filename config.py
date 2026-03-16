# Configuration file for Telegram Referral Bot

import os

# ==================== BOT SETTINGS ====================

# Bot Token (Get from @BotFather)
BOT_TOKEN = "8530536222:AAGxNIw4Kvet_TYxPLyNUjhZfVsvR-Z2704"

# Admin/Owner User ID (Get your ID from @userinfobot)
ADMIN_ID = 6781971357

# Force Join Channel/Group (Channel username without @)
FORCE_JOIN_CHANNEL = "CyberEliteBangladesh"
FORCE_JOIN_CHAT_ID = -1003807515463  # Channel/Group ID

# Bot Name
BOT_NAME = "Referral Bot"
BOT_VERSION = "1.0.0"

# ==================== REFERRAL SETTINGS ====================

# Referral Bonus per referral (USDT)
REFERRAL_BONUS = 0.08

# Minimum referrals to unlock withdraw
MIN_REFERRALS_TO_UNLOCK = 5

# Minimum withdraw amount (USDT)
MIN_WITHDRAW_AMOUNT = 1.0

# Maximum withdraw per day (USDT) - 0 = unlimited
MAX_WITHDRAW_PER_DAY = 100.0

# ==================== BONUS SETTINGS ====================

# Welcome bonus for new users (USDT)
WELCOME_BONUS = 0.00

# Daily login bonus (USDT)
DAILY_BONUS = 0.02

# Spin wheel bonus range (USDT)
SPIN_MIN_BONUS = 0.01
SPIN_MAX_BONUS = 0.10

# Spin wheel attempts per day
SPIN_ATTEMPTS_PER_DAY = 3

# Level bonus (extra when reaching level)
LEVEL_BONUSES = {
    1: 0.00,   # Beginner
    2: 0.05,   # Bronze
    3: 0.10,   # Silver
    4: 0.20,   # Gold
    5: 0.50,   # Platinum
    6: 1.00,   # Diamond
}

# Referrals needed for each level
LEVEL_THRESHOLDS = {
    1: 0,      # Beginner
    2: 5,      # Bronze - 5 refs
    3: 20,     # Silver - 20 refs
    4: 50,     # Gold - 50 refs
    5: 100,    # Platinum - 100 refs
    6: 250,    # Diamond - 250 refs
}

LEVEL_NAMES = {
    1: "🥉 Beginner",
    2: "🥉 Bronze",
    3: "🥈 Silver",
    4: "🥇 Gold",
    5: "💎 Platinum",
    6: "👑 Diamond",
}

# ==================== DATABASE SETTINGS ====================

DATABASE_NAME = "bot_database.db"

# Auto backup interval (hours) - 0 = disabled
BACKUP_INTERVAL = 24

# ==================== RATE LIMITING ====================

# Cooldown between commands (seconds)
COMMAND_COOLDOWN = 2

# Max withdrawals per day
MAX_WITHDRAWALS_PER_DAY = 3

# ==================== MESSAGES ====================

WELCOME_MESSAGE = """
🎉 **Welcome to {bot_name}!**

💰 Earn ${referral_bonus} USDT for each referral
🔓 Refer {min_referrals} friends to unlock withdrawals
💵 Minimum withdraw: ${min_withdraw} USDT

🎁 **Bonus Features:**
├ 🎯 Daily Bonus: ${daily_bonus} USDT
├ 🎰 Spin Wheel: Win up to ${spin_max} USDT
└ 🏆 Level System: Earn more rewards!

Click buttons below to start earning!
"""

NOT_JOINED_MESSAGE = """
⚠️ **You must join our channel first!**

📢 Channel: @{channel}

Please join and click ✅ Joined button.
"""

REFERRAL_LINK_MESSAGE = """
🔗 **Your Referral Link:**
`{referral_link}`

📊 **Your Stats:**
├ 📈 Referrals: {referral_count}/{min_referrals}
├ 💰 Balance: ${balance:.2f} USDT
├ 🏆 Level: {level}
└ 📅 Today's Referrals: {today_refs}

💡 Share this link and earn ${referral_bonus} per referral!
"""

BALANCE_MESSAGE = """
💼 **Your Balance: ${balance:.2f} USDT**

📊 **Statistics:**
├ 👥 Total Referrals: {referral_count}
├ 🏆 Level: {level}
├ 📅 Today's Referrals: {today_refs}
└ 📊 Total Earned: ${total_earned:.2f} USDT

{status}

{unlock_message}
"""

DAILY_BONUS_MESSAGE = """
🎁 **Daily Bonus Claimed!**

💰 You received: ${amount:.2f} USDT
📊 New Balance: ${balance:.2f} USDT

Come back tomorrow for more!
"""

SPIN_MESSAGE = """
🎰 **Spin Wheel**

🎁 You won: ${amount:.2f} USDT!
📊 New Balance: ${balance:.2f} USDT
🎯 Attempts left today: {attempts}

Spin again?
"""

WITHDRAW_MESSAGE = """
💸 **Withdraw Funds**

💰 Available Balance: ${balance:.2f} USDT
💵 Minimum Withdraw: ${min_withdraw} USDT
📊 Today's Withdrawals: {today_withdraws}/{max_withdraws}

{lock_status}
"""

WITHDRAW_REQUEST_MESSAGE = """
✅ **Withdrawal Request Submitted!**

📝 **Details:**
├ 💵 Amount: ${amount:.2f} USDT
├ 💼 Wallet: `{wallet}`
└ ⏳ Status: Pending

Admin will review and process your request soon.
"""

WITHDRAW_HISTORY_MESSAGE = """
📜 **Withdrawal History**

{history}

📊 Total Withdrawn: ${total:.2f} USDT
"""

LEVEL_UP_MESSAGE = """
🎉 **Congratulations! Level Up!**

🏆 You reached: {level_name}
🎁 Bonus: ${bonus:.2f} USDT
💰 New Balance: ${balance:.2f} USDT

Keep referring to unlock more rewards!
"""

# ==================== ADMIN MESSAGES ====================

ADMIN_PANEL_MESSAGE = """
🔐 **Admin Panel**

📊 **Statistics:**
├ 👥 Total Users: {total_users}
├ 💰 Pending Withdrawals: {pending_withdrawals}
├ 💵 Total Paid Out: ${total_paid:.2f} USDT
├ 🎰 Today's Spins: {today_spins}
└ 🎁 Today's Bonuses: ${today_bonuses:.2f} USDT

Select an option:
"""

ADMIN_STATS_MESSAGE = """
📊 **Bot Statistics**

👥 **Users:**
├ Total: {total_users}
├ Today: {today_users}
├ This Week: {week_users}
└ Active (24h): {active_users}

💰 **Finance:**
├ Total Balance: ${total_balance:.2f} USDT
├ Pending: ${pending:.2f} USDT
├ Paid Out: ${paid:.2f} USDT
└ Today's Earnings: ${today_earnings:.2f} USDT

📈 **Referrals:**
├ Total: {total_refs}
├ Today: {today_refs}
└ This Week: {week_refs}
"""
