# =============================================================================
# crypto/admin.py
# Fully upgraded admin with safe actions, user control, and notifications
# =============================================================================

from decimal import Decimal
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import transaction
from django.utils import timezone

from .models import (
    Rank, CustomUser, Profile, Deposit, Withdrawal, CopyTrade,
    Referral, DailyReward, PromoCode, PromoRedemption, Notification
)

# ---------------------------------------------------------------------
# Rank
# ---------------------------------------------------------------------
@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_balance', 'max_balance', 'daily_profit_pct', 'copy_trades_limit', 'color')
    ordering = ('min_balance',)
    readonly_fields = ('name', 'min_balance', 'max_balance', 'daily_profit_pct', 'copy_trades_limit', 'color')
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

# ---------------------------------------------------------------------
# Profile Inline for users
# ---------------------------------------------------------------------
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fk_name = 'user'
    extra = 0

# ---------------------------------------------------------------------
# User Admin
# ---------------------------------------------------------------------
@admin.action(description="Ban selected users")
def ban_users(modeladmin, request, queryset):
    queryset.update(is_banned=True, is_flagged=True)
    for user in queryset:
        Notification.objects.create(user=user, message="⚠️ You have been banned by admin.")

@admin.action(description="Unban selected users")
def unban_users(modeladmin, request, queryset):
    queryset.update(is_banned=False)
    for user in queryset:
        Notification.objects.create(user=user, message="✅ You have been unbanned by admin.")

@admin.action(description="Flag selected users")
def flag_users(modeladmin, request, queryset):
    queryset.update(is_flagged=True)
    for user in queryset:
        Notification.objects.create(user=user, message="⚠️ Your account has been flagged by admin.")

@admin.action(description="Unflag selected users")
def unflag_users(modeladmin, request, queryset):
    queryset.update(is_flagged=False)
    for user in queryset:
        Notification.objects.create(user=user, message="✅ Your account has been unflagged by admin.")

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'is_banned', 'is_flagged', 'last_login_ip', 'is_staff')
    list_filter = ('role', 'is_banned', 'is_flagged')
    search_fields = ('username', 'email')
    inlines = (ProfileInline,)
    actions = [ban_users, unban_users, flag_users, unflag_users]
    fieldsets = BaseUserAdmin.fieldsets + (
        (None, {'fields': ('role', 'is_banned', 'is_flagged', 'last_login_ip', 'phone')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {'fields': ('email', 'role')}),
    )

# ---------------------------------------------------------------------
# Profile Admin
# ---------------------------------------------------------------------
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'rank', 'principal_balance', 'locked_balance', 'withdrawable_balance', 'referral_code', 'total_referrals', 'valid_referrals')
    list_filter = ('rank',)
    search_fields = ('user__username', 'referral_code')
    readonly_fields = ('user',)
    
    def principal_balance(self, obj):
        return obj.principal_balance
    principal_balance.short_description = 'Principal Balance'

# ---------------------------------------------------------------------
# Deposit Admin with safe approve action
# ---------------------------------------------------------------------
@admin.action(description="Approve selected deposits safely")
def approve_deposits(modeladmin, request, queryset):
    from .views import _update_user_rank  # Import to use the rank update function
    
    with transaction.atomic():
        for deposit in queryset.select_for_update():
            if deposit.status != "pending":
                continue  # skip already processed

            profile = deposit.user.profile
            profile.locked_balance += deposit.amount
            profile.save(update_fields=["locked_balance"])

            deposit.status = "approved"
            deposit.approved_at = timezone.now()
            from .utils import add_days, LOCK_DAYS
            deposit.expires_at = deposit.expires_at or add_days(timezone.now(), LOCK_DAYS)
            deposit.save(update_fields=["status", "approved_at", "expires_at"])

            # Handle referral bonus
            if deposit.referrer_id and deposit.referrer_id != deposit.user_id:
                from .utils import REFERRAL_PCT
                bonus = deposit.amount * REFERRAL_PCT
                ref_profile = Profile.objects.filter(user_id=deposit.referrer_id).first()
                if ref_profile:
                    ref_profile.locked_balance += bonus
                    ref_profile.total_referrals += 1
                    ref_profile.valid_referrals += 1
                    ref_profile.referral_earnings += bonus
                    ref_profile.save()
                    Referral.objects.create(referrer_id=deposit.referrer_id, referee=deposit.user, bonus_amount=bonus, deposit=deposit)
                    # Update referrer rank
                    ref_profile.update_rank()
            
            # Update user rank after deposit approval
            profile.update_rank()

            Notification.objects.create(
                user=deposit.user,
                message=f"✅ Deposit {deposit.id} of ${deposit.amount:.2f} approved and credited to your balance."
            )
            messages.success(request, f"Deposit {deposit.id} approved safely.")

@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'network', 'status', 'created_at', 'expires_at')
    list_filter = ('status', 'network')
    search_fields = ('user__username',)
    raw_id_fields = ('user', 'referrer')
    readonly_fields = ('created_at',)
    actions = [approve_deposits]

# ---------------------------------------------------------------------
# Withdrawal Admin
# ---------------------------------------------------------------------
@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'network', 'status', 'created_at')
    list_filter = ('status', 'network')
    search_fields = ('user__username',)
    raw_id_fields = ('user',)
    readonly_fields = ('created_at',)

# ---------------------------------------------------------------------
# CopyTrade Admin
# ---------------------------------------------------------------------
@admin.register(CopyTrade)
class CopyTradeAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'pair', 'action', 'amount', 'profit', 'status', 'created_at')
    list_filter = ('status', 'action')
    search_fields = ('user__username', 'pair')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at',)

# ---------------------------------------------------------------------
# Referral Admin
# ---------------------------------------------------------------------
@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referee', 'bonus_amount', 'deposit', 'created_at')
    raw_id_fields = ('referrer', 'referee', 'deposit')
    readonly_fields = ('created_at',)

# ---------------------------------------------------------------------
# DailyReward Admin
# ---------------------------------------------------------------------
@admin.register(DailyReward)
class DailyRewardAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'claimed_at')
    raw_id_fields = ('user',)
    readonly_fields = ('claimed_at',)

# ---------------------------------------------------------------------
# PromoCode Admin
# ---------------------------------------------------------------------
@admin.action(description="Disable selected promo codes")
def disable_promos(modeladmin, request, queryset):
    queryset.update(status="disabled")
    for promo in queryset:
        messages.success(request, f"Promo {promo.code} disabled.")

@admin.action(description="Enable selected promo codes")
def enable_promos(modeladmin, request, queryset):
    queryset.update(status="active")
    for promo in queryset:
        messages.success(request, f"Promo {promo.code} enabled.")

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'bonus_min', 'bonus_max', 'expiration', 'usage_limit', 'usage_count', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('code',)
    actions = [disable_promos, enable_promos]

# ---------------------------------------------------------------------
# DailyProfit Admin (Temporarily disabled)
# ---------------------------------------------------------------------
# @admin.register(DailyProfit)
# class DailyProfitAdmin(admin.ModelAdmin):
#     list_display = ('user', 'amount', 'for_date', 'calculated_at', 'locked_balance_used', 'rank_used')
#     list_filter = ('for_date', 'rank_used')
#     search_fields = ('user__username',)
#     raw_id_fields = ('user', 'rank_used')
#     readonly_fields = ('user', 'amount', 'for_date', 'calculated_at', 'locked_balance_used', 'rank_used')
#     
#     def has_add_permission(self, request):
#         return False  # Daily profits are generated automatically
#     
#     def has_change_permission(self, request, obj=None):
#         return False  # Daily profits are immutable

# ---------------------------------------------------------------------
# PromoRedemption Admin
# ---------------------------------------------------------------------
@admin.register(PromoRedemption)
class PromoRedemptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'promo_code', 'bonus_amount', 'created_at')
    raw_id_fields = ('user', 'promo_code')
    readonly_fields = ('user', 'promo_code', 'bonus_amount', 'created_at')
    
    def has_add_permission(self, request):
        return False  # Promo redemptions are created by users
    
    def has_change_permission(self, request, obj=None):
        return False  # Promo redemptions are immutable
