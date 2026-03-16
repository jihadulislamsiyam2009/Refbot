# Helper functions
from datetime import datetime

def format_timestamp(timestamp: str) -> str:
    """Format timestamp to readable date"""
    if not timestamp:
        return "N/A"
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return timestamp

def calculate_referral_progress(current: int, target: int = 5) -> str:
    """Create progress bar for referrals"""
    filled = int((current / target) * 10)
    empty = 10 - filled
    return "▓" * filled + "░" * empty

def is_valid_wallet(wallet: str) -> bool:
    """Basic wallet address validation"""
    if not wallet:
        return False
    # TRC20: starts with T, 34 chars
    # ERC20: starts with 0x, 42 chars
    wallet = wallet.strip()
    if wallet.startswith('T') and len(wallet) == 34:
        return True
    if wallet.startswith('0x') and len(wallet) == 42:
        return True
    return False

def format_balance(balance: float) -> str:
    """Format balance with proper decimals"""
    return f"${balance:.2f}"

def get_status_emoji(status: str) -> str:
    """Get emoji for status"""
    emojis = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌',
        'unlocked': '🔓',
        'locked': '🔒',
        'banned': '🚫',
        'active': '✅'
    }
    return emojis.get(status.lower(), '❓')