# =============================================================================
# crypto/models.py
# =============================================================================

from django.db import models
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
from django.db import models
from django.conf import settings

class Rank(models.Model):
    name = models.CharField(max_length=64)
    min_balance = models.DecimalField(max_digits=18, decimal_places=2)
    max_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)  # None for unlimited
    daily_profit_pct = models.DecimalField(max_digits=5, decimal_places=2)  # e.g., 1.67 for 1.67%
    copy_trades_limit = models.IntegerField()
    color = models.CharField(max_length=16)

    class Meta:
        ordering = ['min_balance']

    def __str__(self):
        return self.name
    
    @property
    def daily_profit_percentage(self):
        """Alias for backward compatibility"""
        return self.daily_profit_pct
    
    @property
    def max_copy_trades(self):
        """Alias for backward compatibility"""
        return self.copy_trades_limit


class CustomUser(AbstractUser):
    ROLE_CHOICES = [('user', 'User'), ('admin', 'Admin')]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    is_banned = models.BooleanField(default=False)
    is_flagged = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    phone = models.CharField(max_length=32, blank=True)

    @property
    def is_admin(self):
        return self.role == 'admin'


class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    rank = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True, blank=True, related_name='profiles')
    # Principal balance: user-deposited funds
    locked_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    withdrawable_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    profile_picture = models.TextField(blank=True)  # Store image URL for now
    referral_code = models.CharField(max_length=16, unique=True, null=True, blank=True)
    total_referrals = models.IntegerField(default=0)
    valid_referrals = models.IntegerField(default=0)
    referral_earnings = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    # last_daily_profit_at = models.DateTimeField(null=True, blank=True, default=None)  # Track daily profit generation
    last_withdrawal_at = models.DateTimeField(null=True, blank=True)

    @property
    def principal_balance(self):
        """Total active balance (principal) for rank calculation"""
        return self.locked_balance + self.withdrawable_balance

    @property
    def total_balance(self):
        """Alias for backward compatibility"""
        return self.principal_balance

    def get_rank(self):
        """Calculate and return rank based on principal balance"""
        if self.principal_balance <= 0:
            return None
        
        ranks = Rank.objects.order_by('min_balance')
        for rank in ranks:
            if self.principal_balance >= rank.min_balance:
                if rank.max_balance is None or self.principal_balance <= rank.max_balance:
                    return rank
        return None

    def update_rank(self):
        """Update rank based on current principal balance"""
        new_rank = self.get_rank()
        if new_rank != self.rank:
            self.rank = new_rank
            self.save(update_fields=['rank'])
        return new_rank

    def __str__(self):
        return f"Profile({self.user.username})"


class Deposit(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('expired', 'Expired')]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='deposits')
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    network = models.CharField(max_length=32)
    wallet_address = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    expires_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    referrer = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='referred_deposits')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Withdrawal(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    network = models.CharField(max_length=32)
    wallet_address = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class CopyTrade(models.Model):
    ACTION_CHOICES = [('buy', 'Buy'), ('sell', 'Sell')]
    STATUS_CHOICES = [('pending', 'Pending'), ('completed', 'Completed'), ('cancelled', 'Cancelled')]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='copy_trades')
    pair = models.CharField(max_length=32)
    action = models.CharField(max_length=4, choices=ACTION_CHOICES)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    profit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Referral(models.Model):
    referrer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='referrals_made')
    referee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='referrals_received')
    bonus_amount = models.DecimalField(max_digits=18, decimal_places=2)
    credited_to_locked = models.BooleanField(default=True)
    deposit = models.ForeignKey(Deposit, on_delete=models.SET_NULL, null=True, blank=True, related_name='referral_bonuses')
    created_at = models.DateTimeField(auto_now_add=True)


class DailyReward(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='daily_rewards')
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.10'))
    claimed_at = models.DateTimeField(auto_now_add=True)
    added_to_withdrawable = models.BooleanField(default=True)

    class Meta:
        ordering = ['-claimed_at']


class PromoCode(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('disabled', 'Disabled')]
    code = models.CharField(max_length=32, unique=True)
    bonus_min = models.DecimalField(max_digits=18, decimal_places=2)
    bonus_max = models.DecimalField(max_digits=18, decimal_places=2)
    expiration = models.DateTimeField(null=True, blank=True)
    usage_limit = models.IntegerField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class PromoRedemption(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='promo_redemptions')
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name='redemptions')
    bonus_amount = models.DecimalField(max_digits=18, decimal_places=2)
    credited_to_locked = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'promo_code']
        ordering = ['-created_at']

# class DailyProfit(models.Model):
#     """Track daily profit generation for each user"""
#     user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='daily_profits')
#     amount = models.DecimalField(max_digits=18, decimal_places=2)
#     calculated_at = models.DateTimeField(auto_now_add=True)
#     for_date = models.DateField()  # The date this profit is for
#     locked_balance_used = models.DecimalField(max_digits=18, decimal_places=2)  # Balance used for calculation
#     rank_used = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True)
#     
#     class Meta:
#         unique_together = ['user', 'for_date']
#         ordering = ['-for_date']


class LocalWithdrawal(models.Model):
    """Local withdrawal with Paystack integration"""
    STATUS_CHOICES = [
        ('pending_admin_approval', 'Pending Admin Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='local_withdrawals')
    amount_usdt = models.DecimalField(max_digits=18, decimal_places=2)
    conversion_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1600'))
    amount_ngn = models.DecimalField(max_digits=18, decimal_places=2)
    
    # Bank details
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    account_holder_name = models.CharField(max_length=100)
    
    def get_bank_code(self):
        """Get Paystack bank code from bank name"""
        bank_codes = {
            'Access Bank': '044',
            'Access Diamond': '044',
            'ALAT by Wema': '035',
            'ASO Savings': '401',
            'Citibank': '023',
            'Carbon': '565',
            'Ecobank': '050',
            'EcoBank': '050',
            'Fidelity Bank': '070',
            'First Bank': '011',
            'First Bank of Nigeria': '011',
            'First City Monument Bank': '214',
            'FCMB': '214',
            'FSDH Merchant': '501',
            'Globus Bank': '103',
            'Guaranty Trust Bank': '058',
            'GTBank': '058',
            'Heritage Bank': '030',
            'Jaiz Bank': '301',
            'Keystone Bank': '082',
            'Kuda Bank': '50211',
            'Moniepoint': '50215',
            'Opay': '999992',
            'Palmpay': '999991',
            'Polaris Bank': '076',
            'Providus Bank': '101',
            'Stanbic IBTC': '221',
            'Standard Chartered': '068',
            'Sterling Bank': '232',
            'Suntrust Bank': '100',
            'Taj Bank': '302',
            'Union Bank': '032',
            'United Bank for Africa': '033',
            'UBA': '033',
            'Unity Bank': '215',
            'Wema Bank': '035',
            'Zenith Bank': '057',
            'OPAY': '999992',
        }
        return bank_codes.get(self.bank_name, '999992')  # Default to OPAY if not found
    
    # Status and tracking
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_admin_approval')
    paystack_transfer_reference = models.CharField(max_length=100, null=True, blank=True)
    paystack_response = models.JSONField(null=True, blank=True)
    
    # Admin actions
    admin_notes = models.TextField(null=True, blank=True)
    processed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_withdrawals')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Local Withdrawal {self.id} - {self.user.username} - ${self.amount_usdt}"
    
    def save(self, *args, **kwargs):
        # Calculate NGN amount if not set
        if not self.amount_ngn:
            self.amount_ngn = self.amount_usdt * self.conversion_rate
        super().save(*args, **kwargs)


class LocalDeposit(models.Model):
    """Local deposit with Paystack payment"""
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='local_deposits')
    amount_usdt = models.DecimalField(max_digits=18, decimal_places=2)
    amount_ngn = models.DecimalField(max_digits=18, decimal_places=2)
    conversion_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1600'))
    
    # Referral support
    referrer = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='referred_local_deposits')
    
    # Paystack integration
    paystack_reference = models.CharField(max_length=100, unique=True)
    paystack_access_code = models.CharField(max_length=100, null=True, blank=True)
    paystack_response = models.JSONField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Admin confirmation
    confirmed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_deposits')
    admin_notes = models.TextField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Local Deposit {self.id} - {self.user.username} - ${self.amount_usdt}"
    
    def save(self, *args, **kwargs):
        # Calculate NGN amount if not set
        if not self.amount_ngn:
            self.amount_ngn = self.amount_usdt * self.conversion_rate
        super().save(*args, **kwargs)

#     def __str__(self):
#         return f"DailyProfit({self.user.username}, {self.for_date}, ${self.amount})"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:20]}"
