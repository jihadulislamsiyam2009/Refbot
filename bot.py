import asyncio
import logging
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ApplicationBuilder

import config
from database import (
    init_db, add_user, get_user, update_user_balance, set_user_balance,
    set_wallet_address, ban_user, get_all_users, get_top_referrers,
    get_total_users, get_today_users, get_active_users, get_total_balance,
    get_total_referrals, create_withdrawal, get_pending_withdrawals,
    get_withdrawal, approve_withdrawal, reject_withdrawal, get_total_paid,
    get_user_withdrawals, claim_daily_bonus, can_claim_daily, add_spin_bonus,
    get_today_spins, get_user_transactions, get_bot_stats, get_setting,
    set_setting, search_users, use_spin, get_level_from_refs
)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# User states for conversation
WAITING_WALLET = 1
WAITING_BROADCAST = 2
WAITING_ADD_BALANCE = 3
WAITING_SEARCH = 4
WAITING_SET_AMOUNT = 5

# Store temporary data
user_data = {}

# Level names mapping
LEVEL_NAMES = {
    1: "🥉 Beginner",
    2: "🥉 Bronze",
    3: "🥈 Silver",
    4: "🥇 Gold",
    5: "💎 Platinum",
    6: "👑 Diamond"
}

LEVEL_BONUSES = {
    1: 0.00,
    2: 0.05,
    3: 0.10,
    4: 0.20,
    5: 0.50,
    6: 1.00
}

LEVEL_THRESHOLDS = {
    1: 0,
    2: 5,
    3: 20,
    4: 50,
    5: 100,
    6: 250
}

# ==================== HELPER FUNCTIONS ====================

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id == config.ADMIN_ID

async def check_member_status(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Check if user is member of required channel/group"""
    for chat_id in [config.FORCE_JOIN_CHAT_ID, f"@{config.FORCE_JOIN_CHANNEL}", config.FORCE_JOIN_CHANNEL]:
        try:
            member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in [
                ChatMemberStatus.MEMBER, 
                ChatMemberStatus.ADMINISTRATOR, 
                ChatMemberStatus.OWNER,
                ChatMemberStatus.RESTRICTED
            ]:
                return True
        except:
            continue
    return False

def get_main_keyboard():
    """Get main menu keyboard with colored buttons"""
    keyboard = [
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily")],
        [InlineKeyboardButton("🎰 Spin", callback_data="spin"),
         InlineKeyboardButton("💰 Balance", callback_data="balance")],
        [InlineKeyboardButton("🔗 Referral", callback_data="referral"),
         InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("📜 History", callback_data="history"),
         InlineKeyboardButton("🏆 Top Users", callback_data="leaderboard")],
        [InlineKeyboardButton("📊 My Stats", callback_data="mystats")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_join_keyboard():
    """Get force join keyboard with improved design"""
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{config.FORCE_JOIN_CHANNEL}")],
        [InlineKeyboardButton("✅ Verify Membership", callback_data="check_join")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    """Get admin panel keyboard with improved design"""
    keyboard = [
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 All Users", callback_data="admin_users"),
         InlineKeyboardButton("🔍 Search", callback_data="admin_search")],
        [InlineKeyboardButton("💰 Pending Withdrawals", callback_data="admin_withdraws")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
         InlineKeyboardButton("💵 Add Balance", callback_data="admin_balance")],
        [InlineKeyboardButton("🔄 Reset Daily", callback_data="admin_reset")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_spin_result():
    """Generate random spin result"""
    # Weighted random selection - smaller amounts more common
    amounts = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    weights = [20, 18, 15, 12, 10, 8, 6, 5, 4, 2]  # Higher weights for smaller amounts
    return random.choices(amounts, weights=weights)[0]

# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id

    # Check if user is banned
    db_user = await get_user(user_id)
    if db_user and db_user['is_banned']:
        await update.message.reply_text("⛔ You are banned from this bot!")
        return

    # Check force join
    is_member = await check_member_status(context, user_id)
    if not is_member:
        await update.message.reply_text(
            config.NOT_JOINED_MESSAGE.format(channel=config.FORCE_JOIN_CHANNEL),
            reply_markup=get_join_keyboard()
        )
        return

    # Get referral code from deep link
    referrer_id = None
    if context.args and context.args[0].startswith('ref_'):
        try:
            referrer_id = int(context.args[0].replace('ref_', ''))
            if referrer_id == user_id:
                referrer_id = None
        except ValueError:
            referrer_id = None

    # Add user to database
    await add_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        referred_by=referrer_id
    )

    # Get updated user data
    db_user = await get_user(user_id)
    if not db_user:
        db_user = {'balance': 0, 'referral_count': 0, 'withdraw_unlocked': 0, 'level': 1, 'today_referrals': 0}

    await update.message.reply_text(
        config.WELCOME_MESSAGE.format(
            bot_name=config.BOT_NAME,
            referral_bonus=config.REFERRAL_BONUS,
            min_referrals=config.MIN_REFERRALS_TO_UNLOCK,
            min_withdraw=config.MIN_WITHDRAW_AMOUNT,
            daily_bonus=config.DAILY_BONUS,
            spin_max=config.SPIN_MAX_BONUS
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = f"""
📚 **Bot Help**

**How to Earn:**
1. Share your referral link with friends
2. Earn ${config.REFERRAL_BONUS:.2f} USDT for each referral
3. Refer {config.MIN_REFERRALS_TO_UNLOCK} friends to unlock withdrawals
4. Minimum withdraw: ${config.MIN_WITHDRAW_AMOUNT:.2f} USDT

**Features:**
├ 🎯 Daily Bonus: ${config.DAILY_BONUS:.2f} USDT/day
├ 🎰 Spin Wheel: Win up to ${config.SPIN_MAX_BONUS:.2f} USDT
├ 🏆 Level System: Earn level bonuses
└ 📊 Leaderboard: Top referrers

**Commands:**
/start - Start bot
/balance - Check balance
/referral - Get referral link
/withdraw - Request withdrawal
/history - Withdrawal history
/daily - Claim daily bonus
/spin - Spin wheel
/leaderboard - Top referrers
/stats - Your statistics

**Need Help?** Contact admin
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command"""
    user_id = update.effective_user.id
    db_user = await get_user(user_id)

    if not db_user:
        await update.message.reply_text("⚠️ Please use /start first!")
        return

    status = "✅ Withdraw Unlocked" if db_user['withdraw_unlocked'] else f"🔒 Need {5 - db_user['referral_count']} more refs"
    unlock_msg = "" if db_user['withdraw_unlocked'] else f"\n\n💡 Refer {5 - db_user['referral_count']} more friends to unlock withdrawals!"

    text = f"""
💼 **Your Balance: ${db_user['balance']:.2f} USDT**

📊 **Statistics:**
├ 👥 Total Referrals: {db_user['referral_count']}
├ 🏆 Level: {LEVEL_NAMES.get(db_user['level'], 'Beginner')}
├ 📅 Today's Referrals: {db_user['today_referrals']}
└ 📊 Total Earned: ${db_user['total_earned']:.2f} USDT

{status}
{unlock_msg}
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /referral command"""
    user_id = update.effective_user.id
    db_user = await get_user(user_id)

    if not db_user:
        await update.message.reply_text("⚠️ Please use /start first!")
        return

    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    text = f"""
🔗 **Your Referral Link:**
`{referral_link}`

📊 **Your Stats:**
├ 📈 Referrals: {db_user['referral_count']}/{config.MIN_REFERRALS_TO_UNLOCK}
├ 💰 Balance: ${db_user['balance']:.2f} USDT
├ 🏆 Level: {LEVEL_NAMES.get(db_user['level'], 'Beginner')}
└ 📅 Today: {db_user['today_referrals']} referrals

💡 Share this link and earn ${config.REFERRAL_BONUS} per referral!
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /withdraw command"""
    user_id = update.effective_user.id
    db_user = await get_user(user_id)

    if not db_user:
        await update.message.reply_text("⚠️ Please use /start first!")
        return

    if not db_user['withdraw_unlocked']:
        await update.message.reply_text(
            f"🔒 You need to refer {config.MIN_REFERRALS_TO_UNLOCK} friends to unlock withdrawals!\n\n"
            f"Current referrals: {db_user['referral_count']}/{config.MIN_REFERRALS_TO_UNLOCK}",
            reply_markup=get_main_keyboard()
        )
        return

    if db_user['balance'] < config.MIN_WITHDRAW_AMOUNT:
        await update.message.reply_text(
            f"⚠️ Minimum withdrawal amount is ${config.MIN_WITHDRAW_AMOUNT:.2f} USDT\n\n"
            f"Your balance: ${db_user['balance']:.2f} USDT",
            reply_markup=get_main_keyboard()
        )
        return

    keyboard = [[InlineKeyboardButton("💸 Request Withdraw", callback_data="withdraw_request")]]
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])

    await update.message.reply_text(
        f"""
💸 **Withdraw Funds**

💰 Available: ${db_user['balance']:.2f} USDT
💵 Minimum: ${config.MIN_WITHDRAW_AMOUNT:.2f} USDT
📊 Today: {db_user['today_withdraws']}/{config.MAX_WITHDRAWALS_PER_DAY} withdrawals
""",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /history command"""
    user_id = update.effective_user.id
    withdrawals = await get_user_withdrawals(user_id)

    if not withdrawals:
        await update.message.reply_text("📜 No withdrawal history found.", reply_markup=get_main_keyboard())
        return

    text = "📜 **Withdrawal History:**\n\n"
    total = 0
    for w in withdrawals[:10]:
        status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(w['status'], "❓")
        text += f"{status_emoji} ${w['amount']:.2f} | {w['status']}\n"
        text += f"   Wallet: `{w['wallet'][:15]}...`\n\n"
        if w['status'] == 'approved':
            total += w['amount']

    text += f"\n📊 Total Withdrawn: ${total:.2f} USDT"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /daily command - claim daily bonus"""
    user_id = update.effective_user.id
    db_user = await get_user(user_id)

    if not db_user:
        await update.message.reply_text("⚠️ Please use /start first!")
        return

    # Check if already claimed today
    can_claim = await can_claim_daily(user_id)
    if not can_claim:
        await update.message.reply_text(
            "⚠️ You already claimed your daily bonus today!\n\nCome back tomorrow.",
            reply_markup=get_main_keyboard()
        )
        return

    # Claim bonus
    await claim_daily_bonus(user_id, config.DAILY_BONUS)
    db_user = await get_user(user_id)

    await update.message.reply_text(
        f"🎁 **Daily Bonus Claimed!**\n\n💰 Received: ${config.DAILY_BONUS:.2f} USDT\n📊 New Balance: ${db_user['balance']:.2f} USDT",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard()
    )

async def spin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /spin command - spin wheel"""
    user_id = update.effective_user.id
    db_user = await get_user(user_id)

    if not db_user:
        await update.message.reply_text("⚠️ Please use /start first!")
        return

    # Check spin attempts
    if db_user['spin_attempts'] <= 0:
        await update.message.reply_text(
            "⚠️ No spin attempts left today!\n\nCome back tomorrow for more spins.",
            reply_markup=get_main_keyboard()
        )
        return

    # Spin and get result
    result = get_spin_result()
    await use_spin(user_id)
    await add_spin_bonus(user_id, result)
    db_user = await get_user(user_id)

    # Check for level up
    new_level = get_level_from_refs(db_user['referral_count'])
    level_bonus = 0
    if new_level > db_user['level']:
        level_bonus = LEVEL_BONUSES.get(new_level, 0)
        await update_user_balance(user_id, level_bonus, f"Level up bonus - {LEVEL_NAMES[new_level]}")

    keyboard = [[InlineKeyboardButton("🎰 Spin Again", callback_data="spin")]]
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])

    text = f"🎰 **Spin Result**\n\n🎁 You won: ${result:.2f} USDT!\n🎯 Attempts left: {db_user['spin_attempts'] - 1}"
    if level_bonus > 0:
        text += f"\n\n🎉 **Level Up!** {LEVEL_NAMES[new_level]}\n💎 Bonus: ${level_bonus:.2f} USDT"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /leaderboard command"""
    top_users = await get_top_referrers(10)

    text = "🏆 **Top Referrers Leaderboard**\n\n"
    medals = ["🥇", "🥈", "🥉"]

    for i, u in enumerate(top_users):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {u['first_name']}\n"
        text += f"   👥 {u['referral_count']} refs | 💰 ${u['balance']:.2f}\n"

    text += "\nKeep referring to climb the leaderboard!"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user_id = update.effective_user.id
    db_user = await get_user(user_id)

    if not db_user:
        await update.message.reply_text("⚠️ Please use /start first!")
        return

    level_name = LEVEL_NAMES.get(db_user['level'], 'Beginner')
    next_level = db_user['level'] + 1
    next_threshold = LEVEL_THRESHOLDS.get(next_level, 999)
    refs_needed = next_threshold - db_user['referral_count']

    text = f"""
📊 **Your Statistics**

👤 **Profile:**
├ ID: `{user_id}`
├ Level: {level_name}
└ Joined: {db_user['created_at'][:10] if db_user['created_at'] else 'N/A'}

💰 **Finance:**
├ Balance: ${db_user['balance']:.2f} USDT
├ Total Earned: ${db_user['total_earned']:.2f} USDT
└ Spins Today: {db_user['spin_attempts']}/3

👥 **Referrals:**
├ Total: {db_user['referral_count']}
├ Today: {db_user['today_referrals']}
└ Unlock Status: {'✅ Unlocked' if db_user['withdraw_unlocked'] else '🔒 Locked'}

📈 **Progress:**
├ Level: {db_user['level']}/6
├ Next Level: {next_level} ({refs_needed} more refs needed)
└ Withdraw Status: {'✅ Available' if db_user['withdraw_unlocked'] else f'🔒 Need {5 - db_user['referral_count']} refs'}
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

# ==================== CALLBACK HANDLERS ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Check if user is banned
    db_user = await get_user(user_id)
    if db_user and db_user['is_banned']:
        await query.edit_message_text("⛔ You are banned from this bot!")
        return
    
    # Handle check join first (doesn't require db_user)
    if data == "check_join":
        is_member = await check_member_status(context, user_id)
        if is_member:
            await add_user(
                user_id=user_id,
                username=query.from_user.username,
                first_name=query.from_user.first_name,
                last_name=query.from_user.last_name
            )
            db_user = await get_user(user_id)
            if not db_user:
                db_user = {'balance': 0, 'referral_count': 0, 'withdraw_unlocked': 0, 'level': 1, 'today_referrals': 0, 'total_earned': 0}
            await query.edit_message_text(
                config.WELCOME_MESSAGE.format(
                    bot_name=config.BOT_NAME,
                    referral_bonus=config.REFERRAL_BONUS,
                    min_referrals=config.MIN_REFERRALS_TO_UNLOCK,
                    min_withdraw=config.MIN_WITHDRAW_AMOUNT,
                    daily_bonus=config.DAILY_BONUS,
                    spin_max=config.SPIN_MAX_BONUS
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_keyboard()
            )
        else:
            await query.edit_message_text(
                config.NOT_JOINED_MESSAGE.format(channel=config.FORCE_JOIN_CHANNEL),
                reply_markup=get_join_keyboard()
            )
        return

    # Ensure db_user exists for other handlers
    if not db_user:
        db_user = {'balance': 0, 'referral_count': 0, 'withdraw_unlocked': 0, 'level': 1, 'today_referrals': 0, 'total_earned': 0}

    # Back to main menu
    if data == "back_main":
        await query.edit_message_text(
            "🏠 **Main Menu**\n\nSelect an option:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard()
        )
        return

    # Handle referral
    if data == "referral":
        bot_username = context.bot.username
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        status = "✅ Unlocked" if db_user['referral_count'] >= 5 else f"🔒 Locked ({db_user['referral_count']}/5)"

        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]

        await query.edit_message_text(
            f"🔗 **Your Referral Link:**\n\n"
            f"`{referral_link}`\n\n"
            f"📊 Referrals: {db_user['referral_count']}/{config.MIN_REFERRALS_TO_UNLOCK}\n"
            f"💰 Balance: ${db_user['balance']:.2f} USDT\n"
            f"🏆 Level: {LEVEL_NAMES.get(db_user['level'], 'Beginner')}\n"
            f"📈 Status: {status}\n\n"
            f"👆 Click the link above to copy!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle copy link
    if data == "copy_link":
        bot_username = context.bot.username
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        await query.answer(f"Link: {referral_link}", show_alert=True)
        return

    # Handle balance
    if data == "balance":
        status = "✅ Withdraw Unlocked" if db_user['withdraw_unlocked'] else f"🔒 Need {5 - db_user['referral_count']} more refs"
        unlock_msg = "" if db_user['withdraw_unlocked'] else f"\n\n💡 Refer {5 - db_user['referral_count']} more friends!"

        await query.edit_message_text(
            f"💼 **Balance: ${db_user['balance']:.2f} USDT**\n\n"
            f"👥 Referrals: {db_user['referral_count']}\n"
            f"🏆 Level: {LEVEL_NAMES.get(db_user['level'], 'Beginner')}\n"
            f"📊 Total Earned: ${db_user['total_earned']:.2f} USDT\n\n{status}{unlock_msg}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard()
        )
        return

    # Handle withdraw
    if data == "withdraw":
        if not db_user['withdraw_unlocked']:
            await query.edit_message_text(
                f"🔒 You need to refer {config.MIN_REFERRALS_TO_UNLOCK} friends to unlock withdrawals!\n\n"
                f"Current: {db_user['referral_count']}/{config.MIN_REFERRALS_TO_UNLOCK}",
                reply_markup=get_main_keyboard()
            )
            return

        if db_user['balance'] < config.MIN_WITHDRAW_AMOUNT:
            await query.edit_message_text(
                f"⚠️ Minimum withdrawal: ${config.MIN_WITHDRAW_AMOUNT:.2f} USDT\n\n"
                f"Your balance: ${db_user['balance']:.2f} USDT",
                reply_markup=get_main_keyboard()
            )
            return

        keyboard = [[InlineKeyboardButton("💸 Request Withdraw", callback_data="withdraw_request")]]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])

        await query.edit_message_text(
            f"💸 **Withdraw**\n\n💰 Available: ${db_user['balance']:.2f} USDT\n"
            f"💵 Minimum: ${config.MIN_WITHDRAW_AMOUNT:.2f} USDT",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle withdraw request
    if data == "withdraw_request":
        user_data[user_id] = {'state': WAITING_WALLET, 'balance': db_user['balance']}
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            f"💸 Enter your USDT wallet address (TRC20/ERC20):\n\n"
            f"Amount to withdraw: ${db_user['balance']:.2f} USDT",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle history
    if data == "history":
        withdrawals = await get_user_withdrawals(user_id)
        if not withdrawals:
            await query.edit_message_text("📜 No withdrawal history found.", reply_markup=get_main_keyboard())
            return

        text = "📜 **Withdrawal History:**\n\n"
        for w in withdrawals[:10]:
            status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(w['status'], "❓")
            text += f"{status_emoji} ${w['amount']:.2f} | {w['status']}\n"
            text += f"   Wallet: `{w['wallet'][:15]}...`\n\n"

        text += "\n🔙 Press back to return"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Handle daily bonus
    if data == "daily":
        can_claim = await can_claim_daily(user_id)
        if not can_claim:
            await query.edit_message_text(
                "⚠️ You already claimed your daily bonus!\n\nCome back tomorrow.",
                reply_markup=get_main_keyboard()
            )
            return

        await claim_daily_bonus(user_id, config.DAILY_BONUS)
        db_user = await get_user(user_id)

        await query.edit_message_text(
            f"🎁 **Daily Bonus Claimed!**\n\n💰 Received: ${config.DAILY_BONUS:.2f} USDT\n"
            f"📊 New Balance: ${db_user['balance']:.2f} USDT",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard()
        )
        return

    # Handle spin
    if data == "spin":
        if db_user['spin_attempts'] <= 0:
            await query.edit_message_text(
                "⚠️ No spin attempts left today!\n\nCome back tomorrow.",
                reply_markup=get_main_keyboard()
            )
            return

        result = get_spin_result()
        await use_spin(user_id)
        await add_spin_bonus(user_id, result)
        db_user = await get_user(user_id)

        keyboard = [[InlineKeyboardButton("🎰 Spin Again", callback_data="spin")]]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])

        await query.edit_message_text(
            f"🎰 **Spin Result**\n\n🎁 You won: ${result:.2f} USDT!\n"
            f"📊 New Balance: ${db_user['balance']:.2f} USDT\n"
            f"🎯 Attempts left: {db_user['spin_attempts']}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle leaderboard
    if data == "leaderboard":
        top_users = await get_top_referrers(10)
        text = "🏆 **Top Referrers**\n\n"
        medals = ["🥇", "🥈", "🥉"]

        for i, u in enumerate(top_users):
            medal = medals[i] if i < 3 else f"{i+1}."
            text += f"{medal} {u['first_name']} - {u['referral_count']} refs\n"

        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Handle my stats
    if data == "mystats":
        db_user = await get_user(user_id)
        if not db_user:
            await query.edit_message_text("⚠️ Please use /start first!", reply_markup=get_main_keyboard())
            return
        
        level_name = LEVEL_NAMES.get(db_user['level'], 'Beginner')
        next_level = db_user['level'] + 1
        next_threshold = LEVEL_THRESHOLDS.get(next_level, 999)
        refs_needed = next_threshold - db_user['referral_count']
        
        text = f"""
📊 **Your Statistics**

👤 **Profile:**
├ ID: `{user_id}`
├ Level: {level_name}
└ Joined: {db_user['created_at'][:10] if db_user['created_at'] else 'N/A'}

💰 **Finance:**
├ Balance: ${db_user['balance']:.2f} USDT
├ Total Earned: ${db_user['total_earned']:.2f} USDT
└ Spins Today: {db_user['spin_attempts']}/3

👥 **Referrals:**
├ Total: {db_user['referral_count']}
├ Today: {db_user['today_referrals']}
└ Unlock Status: {'✅ Unlocked' if db_user['withdraw_unlocked'] else '🔒 Locked'}

📈 **Progress:**
├ Level: {db_user['level']}/6
├ Next Level: {next_level} ({refs_needed} more refs needed)
└ Withdraw Status: {'✅ Available' if db_user['withdraw_unlocked'] else f'🔒 Need {5 - db_user[\"referral_count\"]} refs'}
"""
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Handle cancel
    if data == "cancel":
        if user_id in user_data:
            del user_data[user_id]
        await query.edit_message_text("❌ Cancelled.", reply_markup=get_main_keyboard())
        return

    # ==================== ADMIN CALLBACKS ====================

    if data == "admin_panel":
        if not is_admin(user_id):
            return

        stats = await get_bot_stats()
        await query.edit_message_text(
            config.ADMIN_PANEL_MESSAGE.format(
                total_users=stats['total_users'],
                pending_withdrawals=stats['pending_withdrawals'],
                total_paid=stats['total_paid'],
                today_spins=0,
                today_bonuses=0.0
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_admin_keyboard()
        )
        return

    if data == "admin_users":
        if not is_admin(user_id):
            return

        users = await get_all_users()
        text = f"👥 **Total Users: {len(users)}**\n\n"
        for u in users[:15]:
            ban_status = "🚫" if u['is_banned'] else "✅"
            text += f"{ban_status} {u['first_name']} (`{u['user_id']}`)\n"
            text += f"   💰 ${u['balance']:.2f} | 📈 {u['referral_count']} refs | 🏆 Lv.{u['level']}\n"

        if len(users) > 15:
            text += f"\n... and {len(users) - 15} more users"

        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "admin_withdraws":
        if not is_admin(user_id):
            return

        pending = await get_pending_withdrawals()
        if not pending:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
            await query.edit_message_text("✅ No pending withdrawals.", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        text = "💰 **Pending Withdrawals:**\n\n"
        keyboard = []
        for w in pending[:5]:
            text += f"ID: {w['id']} | ${w['amount']:.2f}\n"
            text += f"User: {w['first_name']} (`{w['user_id']}`)\n"
            text += f"Wallet: `{w['wallet_address'][:20]}...`\n\n"
            keyboard.append([
                InlineKeyboardButton(f"✅ {w['id']}", callback_data=f"approve_{w['id']}"),
                InlineKeyboardButton(f"❌ {w['id']}", callback_data=f"reject_{w['id']}")
            ])

        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("approve_"):
        if not is_admin(user_id):
            return

        w_id = int(data.split("_")[1])
        w = await get_withdrawal(w_id)
        await approve_withdrawal(w_id)

        try:
            await context.bot.send_message(
                w['user_id'],
                f"✅ **Withdrawal Approved!**\n\n💵 Amount: ${w['amount']:.2f} USDT\n💼 Wallet: `{w['wallet_address']}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

        await query.edit_message_text(
            f"✅ Withdrawal #{w_id} approved!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_withdraws")]])
        )
        return

    if data.startswith("reject_"):
        if not is_admin(user_id):
            return

        w_id = int(data.split("_")[1])
        w = await get_withdrawal(w_id)
        await reject_withdrawal(w_id)

        try:
            await context.bot.send_message(
                w['user_id'],
                f"❌ **Withdrawal Rejected**\n\n💵 Amount: ${w['amount']:.2f} USDT\n💰 Balance refunded!",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

        await query.edit_message_text(
            f"❌ Withdrawal #{w_id} rejected and balance refunded!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_withdraws")]])
        )
        return

    if data == "admin_stats":
        if not is_admin(user_id):
            return

        stats = await get_bot_stats()
        text = f"""
📊 **Bot Statistics**

👥 **Users:**
├ Total: {stats['total_users']}
├ Today: {stats['today_users']}
└ Active (24h): {stats['active_users']}

💰 **Finance:**
├ Total Balance: ${stats['total_balance']:.2f} USDT
├ Total Earned: ${stats['total_earned']:.2f} USDT
├ Pending: ${stats['pending_withdrawals']} requests
└ Paid Out: ${stats['total_paid']:.2f} USDT

📈 **Referrals:**
└ Total: {stats['total_referrals']}
"""
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "admin_broadcast":
        if not is_admin(user_id):
            return

        user_data[user_id] = {'state': WAITING_BROADCAST}
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text("📢 Enter the message to broadcast:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "admin_balance":
        if not is_admin(user_id):
            return

        user_data[user_id] = {'state': WAITING_ADD_BALANCE}
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text(
            "💵 Enter user ID and amount:\n\nFormat: `user_id amount`\nExample: `123456789 10.5`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "admin_search":
        if not is_admin(user_id):
            return

        user_data[user_id] = {'state': WAITING_SEARCH}
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        await query.edit_message_text("🔍 Enter user ID or name to search:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "admin_reset":
        if not is_admin(user_id):
            return

        from database import reset_daily_stats
        await reset_daily_stats()
        await query.edit_message_text(
            "✅ Daily stats reset successfully!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]])
        )
        return

# ==================== MESSAGE HANDLERS ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user_id = update.effective_user.id

    if user_id not in user_data:
        return

    state = user_data[user_id].get('state')
    message_text = update.message.text

    # Handle wallet address input
    if state == WAITING_WALLET:
        wallet = message_text.strip()
        balance = user_data[user_id]['balance']

        await set_wallet_address(user_id, wallet)
        await create_withdrawal(user_id, balance, wallet)

        del user_data[user_id]

        # Notify admin
        try:
            await context.bot.send_message(
                config.ADMIN_ID,
                f"💰 **New Withdrawal Request**\n\n"
                f"User ID: `{user_id}`\n"
                f"Amount: ${balance:.2f} USDT\n"
                f"Wallet: `{wallet}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

        await update.message.reply_text(
            f"✅ **Withdrawal Request Submitted!**\n\n"
            f"💵 Amount: ${balance:.2f} USDT\n"
            f"💼 Wallet: `{wallet}`\n"
            f"⏳ Status: Pending\n\n"
            f"Admin will review and process your request.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard()
        )
        return

    # Handle broadcast
    if state == WAITING_BROADCAST:
        if not is_admin(user_id):
            return

        users = await get_all_users()
        success = 0
        for u in users:
            try:
                await context.bot.send_message(u['user_id'], f"📢 **Broadcast:**\n\n{message_text}", parse_mode=ParseMode.MARKDOWN)
                success += 1
            except:
                pass

        del user_data[user_id]
        await update.message.reply_text(f"📢 Broadcast sent to {success}/{len(users)} users!")
        return

    # Handle add balance
    if state == WAITING_ADD_BALANCE:
        if not is_admin(user_id):
            return

        try:
            parts = message_text.split()
            target_id = int(parts[0])
            amount = float(parts[1])

            await update_user_balance(target_id, amount, f"Admin added balance")

            try:
                await context.bot.send_message(
                    target_id,
                    f"💰 **Balance Updated!**\n\n💵 Added: ${amount:.2f} USDT",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass

            del user_data[user_id]
            await update.message.reply_text(f"✅ Added ${amount:.2f} to user {target_id}!")
        except:
            await update.message.reply_text("❌ Invalid format! Use: `user_id amount`", parse_mode=ParseMode.MARKDOWN)
        return

    # Handle search
    if state == WAITING_SEARCH:
        if not is_admin(user_id):
            return

        results = await search_users(message_text)
        if not results:
            await update.message.reply_text("❌ No users found.")
            return

        text = f"🔍 **Search Results:**\n\n"
        for u in results[:10]:
            ban_status = "🚫" if u['is_banned'] else "✅"
            text += f"{ban_status} {u['first_name']} (`{u['user_id']}`)\n"
            text += f"   💰 ${u['balance']:.2f} | 📈 {u['referral_count']} refs\n"

        del user_data[user_id]
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_admin_keyboard())
        return

# ==================== ADMIN COMMANDS ====================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("⛔ You are not authorized!")
        return

    stats = await get_bot_stats()

    await update.message.reply_text(
        config.ADMIN_PANEL_MESSAGE.format(
            total_users=stats['total_users'],
            pending_withdrawals=stats['pending_withdrawals'],
            total_paid=stats['total_paid'],
            today_spins=0,
            today_bonuses=0.0
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_admin_keyboard()
    )

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ban command"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("⛔ You are not authorized!")
        return

    if not context.args:
        await update.message.reply_text("Usage: /ban user_id")
        return

    try:
        target_id = int(context.args[0])
        await ban_user(target_id, True)
        await update.message.reply_text(f"✅ User {target_id} has been banned!")
    except:
        await update.message.reply_text("❌ Invalid user ID!")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unban command"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("⛔ You are not authorized!")
        return

    if not context.args:
        await update.message.reply_text("Usage: /unban user_id")
        return

    try:
        target_id = int(context.args[0])
        await ban_user(target_id, False)
        await update.message.reply_text(f"✅ User {target_id} has been unbanned!")
    except:
        await update.message.reply_text("❌ Invalid user ID!")

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

# ==================== MAIN ====================

def main():
    """Start the bot"""
    # Initialize database
    asyncio.run(init_db())

    # Create application
    application = ApplicationBuilder().token(config.BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("referral", referral_command))
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("daily", daily_command))
    application.add_handler(CommandHandler("spin", spin_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))

    # Add callback handler
    application.add_handler(CallbackQueryHandler(button_callback))

    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start bot
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()