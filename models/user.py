# User Model
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class User:
    """User data model"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    balance: float = 0.0
    referral_count: int = 0
    referred_by: Optional[int] = None
    withdraw_unlocked: bool = False
    wallet_address: Optional[str] = None
    is_banned: bool = False
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'balance': self.balance,
            'referral_count': self.referral_count,
            'referred_by': self.referred_by,
            'withdraw_unlocked': self.withdraw_unlocked,
            'wallet_address': self.wallet_address,
            'is_banned': self.is_banned,
            'created_at': self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        return cls(
            user_id=data.get('user_id'),
            username=data.get('username'),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            balance=data.get('balance', 0.0),
            referral_count=data.get('referral_count', 0),
            referred_by=data.get('referred_by'),
            withdraw_unlocked=data.get('withdraw_unlocked', False),
            wallet_address=data.get('wallet_address'),
            is_banned=data.get('is_banned', False),
            created_at=data.get('created_at')
        )

@dataclass
class Withdrawal:
    """Withdrawal data model"""
    id: int
    user_id: int
    amount: float
    wallet_address: str
    status: str = 'pending'  # pending, approved, rejected
    requested_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'wallet_address': self.wallet_address,
            'status': self.status,
            'requested_at': self.requested_at,
            'processed_at': self.processed_at
        }