# =============================================================================
# crypto/views.py
# Fully merged version — all user, dashboard, finance, profile, referral, and admin views
# =============================================================================
# pyright: reportMissingImports=false

import random
import uuid
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from .models import (
    Deposit, Withdrawal, PromoCode, PromoRedemption, CopyTrade,
    Profile, Referral, CustomUser as User, Rank, DailyReward, LocalDeposit, Notification
)
from .rank_utils import (
    calculate_user_rank, update_user_rank, generate_daily_profit, 
    get_copy_trade_limit, can_execute_copy_trade, get_concurrent_copy_trades,
    is_copy_trade_limit_reached
)
from .forms import (
    SignupForm, LoginForm, ProfileUpdateForm, DepositForm, WithdrawalForm,
    PromoRedeemForm, PromoCodeCreateForm
)
from .utils import (
    add_days, REFERRAL_PCT, PAIRS, LOCK_DAYS, get_client_ip, get_random_wallet, get_available_wallet,
    generate_referral_code, is_same_day, NETWORKS, MIN_DEPOSIT, MIN_WITHDRAWAL, DAILY_REWARD
)

User = get_user_model()

@csrf_exempt
@require_http_methods(["GET"])
@login_required(login_url='crypto:login')
def check_deposit_status_view(request):
    """API endpoint to check deposit status in real-time"""
    deposit_id = request.GET.get('deposit_id')
    deposit_type = request.GET.get('deposit_type', 'crypto')
    
    if not deposit_id:
        return JsonResponse({'error': 'Deposit ID required'}, status=400)
    
    try:
        if deposit_type == 'local':
            # Check LocalDeposit status
            from crypto.models import LocalDeposit
            deposit = LocalDeposit.objects.get(id=deposit_id, user=request.user)
            
            return JsonResponse({
                'status': deposit.status,
                'approved': deposit.status == 'paid',
                'rejected': deposit.status == 'failed'
            })
        else:
            # Check crypto Deposit status
            deposit = Deposit.objects.get(id=deposit_id, user=request.user)
            
            return JsonResponse({
                'status': deposit.status,
                'approved': deposit.status == 'approved',
                'rejected': deposit.status == 'rejected'
            })
            
    except (Deposit.DoesNotExist, LocalDeposit.DoesNotExist):
        return JsonResponse({'error': 'Deposit not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@login_required(login_url='crypto:login')
def clear_deposit_session_view(request):
    """API endpoint to clear deposit session data after approval"""
    try:
        # Clear the last_deposit session data
        if 'last_deposit' in request.session:
            del request.session['last_deposit']
            request.session.save()
        
        return JsonResponse({'success': True, 'message': 'Session cleared successfully'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def test_webhook_view(request):
    """Test endpoint to simulate Paystack webhooks"""
    if request.method == 'GET':
        # Show test form
        return JsonResponse({
            'message': 'Send POST request to test webhook',
            'example_payload': {
                'event': 'charge.success',
                'data': {
                    'reference': 'TEST_REF_123',
                    'status': 'success',
                    'amount': 10000,  # 100 NGN in kobo
                    'customer': {
                        'email': 'test@example.com'
                    }
                }
            }
        })
    
    elif request.method == 'POST':
        # Simulate webhook
        import json
        from crypto.paystack_service import PaystackWebhookHandler
        
        try:
            payload = json.loads(request.body)
            event = payload.get('event', '')
            
            if event == 'charge.success':
                success, message = PaystackWebhookHandler.handle_charge_success(payload)
                return JsonResponse({
                    'success': success,
                    'message': message,
                    'payload': payload
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Unsupported event: {event}'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)

@require_http_methods(["GET"])
def webhook_status_view(request):
    """Check webhook endpoint status"""
    return JsonResponse({
        'webhook_url': 'http://127.0.0.1:8000/paystack/callback/',
        'status': 'active',
        'test_endpoint': 'http://127.0.0.1:8000/test-webhook/',
        'instructions': [
            '1. For local testing, use ngrok to expose your localhost',
            '2. Set webhook URL in Paystack dashboard to: https://your-ngrok-url.ngrok.io/paystack/callback/',
            '3. Test with: POST to /test-webhook/ with sample payload',
            '4. Check server logs for DEBUG messages'
        ]
    })

@require_http_methods(["GET"])
def public_test_paystack_view(request):
    """Public Paystack configuration test (no login required)"""
    from crypto.paystack_service import PaystackService
    from django.conf import settings
    
    # Check configuration
    secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    public_key = getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')
    
    config_status = {
        'secret_key_configured': bool(secret_key and secret_key != 'sk_test_your_secret_key_here'),
        'public_key_configured': bool(public_key and public_key != 'pk_test_your_public_key_here'),
        'secret_key_prefix': secret_key[:8] if secret_key else 'Not set',
        'public_key_prefix': public_key[:8] if public_key else 'Not set',
    }
    
    # Test API connectivity
    test_result = PaystackService.initialize_transaction(
        amount=100,  # 100 NGN (small test amount)
        email='test@example.com',
        callback_url=getattr(settings, 'PAYSTACK_CALLBACK_URL', ''),
        reference=f"TEST_{uuid.uuid4().hex[:8]}"
    )
    
    return JsonResponse({
        'config_status': config_status,
        'test_result': test_result,
        'is_working': test_result.get('status', False),
        'message': 'Paystack is working!' if test_result.get('status') else 'Paystack configuration needs attention'
    })

@csrf_exempt
@require_http_methods(["GET"])
@login_required(login_url='crypto:login')
def test_paystack_view(request):
    """Test Paystack configuration and connectivity"""
    from crypto.paystack_service import PaystackService
    from django.conf import settings
    
    # Check configuration
    secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    public_key = getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')
    
    config_status = {
        'secret_key_configured': bool(secret_key and secret_key != 'sk_test_your_secret_key_here'),
        'public_key_configured': bool(public_key and public_key != 'pk_test_your_public_key_here'),
        'secret_key_prefix': secret_key[:8] if secret_key else 'Not set',
        'public_key_prefix': public_key[:8] if public_key else 'Not set',
    }
    
    # Test API connectivity
    test_result = PaystackService.initialize_transaction(
        amount=100,  # 100 NGN (small test amount)
        email=request.user.email,
        callback_url=getattr(settings, 'PAYSTACK_CALLBACK_URL', ''),
        reference=f"TEST_{uuid.uuid4().hex[:8]}"
    )
    
    return JsonResponse({
        'config_status': config_status,
        'test_result': test_result,
        'is_working': test_result.get('status', False),
        'message': 'Paystack is working!' if test_result.get('status') else 'Paystack configuration needs attention'
    })

@login_required(login_url='crypto:login')
def paystack_test_page_view(request):
    """Paystack test page"""
    return render(request, 'crypto/paystack_test.html')

def process_expired_deposits():
    """Process expired deposits and update locked balance and ranks"""
    from django.utils import timezone
    from decimal import Decimal
    
    # Get expired approved deposits
    expired_time = timezone.now()
    expired_deposits = Deposit.objects.filter(
        status='approved',
        expires_at__lte=expired_time
    ).order_by('approved_at')  # FIFO - oldest first
    
    for deposit in expired_deposits:
        profile = deposit.user.profile
        
        # Remove expired amount from locked balance
        if profile.locked_balance >= deposit.amount:
            profile.locked_balance -= deposit.amount
            profile.save(update_fields=['locked_balance'])
            
            # Mark deposit as expired
            deposit.status = 'expired'
            deposit.save(update_fields=['status'])
            
            # Check if user needs to be demoted
            old_rank = profile.rank
            new_rank = profile.get_rank()
            
            if old_rank != new_rank:
                profile.rank = new_rank
                profile.save(update_fields=['rank'])
                
                # Create notification for rank change
                Notification.objects.create(
                    user=deposit.user,
                    message=f"Your rank has been demoted from {old_rank.name if old_rank else 'None'} to {new_rank.name if new_rank else 'None'} due to expired deposit."
                )

def complete_pending_trades():
    """Complete trades that have been pending long enough"""
    from django.utils import timezone
    from datetime import timedelta
    
    # Complete trades older than 35 seconds
    completion_time = timezone.now() - timedelta(seconds=35)
    pending_trades = CopyTrade.objects.filter(
        status='pending',
        created_at__lte=completion_time
    )
    
    for trade in pending_trades:
        # Final profit is already calculated and stored
        final_profit = trade.profit
        
        # Update status to completed
        trade.status = 'completed'
        trade.save(update_fields=['status'])
        
        # Add profit to withdrawable balance
        profile = trade.user.profile
        profile.withdrawable_balance += final_profit
        profile.save(update_fields=['withdrawable_balance'])

def update_pending_trades_profit():
    """Update pending trades with fluctuating profits to simulate real trading"""
    from django.utils import timezone
    from datetime import timedelta
    import random
    from decimal import Decimal
    
    # Get all pending trades
    pending_trades = CopyTrade.objects.filter(status='pending')
    
    for trade in pending_trades:
        # Calculate how long the trade has been pending
        time_elapsed = timezone.now() - trade.created_at
        seconds_elapsed = time_elapsed.total_seconds()
        
        # Only start showing profit after 10 seconds
        if seconds_elapsed < 10:
            trade.profit = Decimal('0')
        else:
            # Simulate fluctuating profit based on time elapsed
            # Profit increases gradually over time
            progress = min(seconds_elapsed / 30, 1.0)  # Full profit after 30 seconds
            
            # Get target profit based on user's potential daily profit
            profile = trade.user.profile
            rank = profile.get_rank()
            
            if rank and profile.locked_balance > 0 and rank.daily_profit_pct:
                potential_daily_profit = profile.locked_balance * (Decimal(str(rank.daily_profit_pct)) / Decimal('100'))
            else:
                potential_daily_profit = Decimal('0.50')
            
            # Calculate profit per trade (potential daily profit divided by daily trade limit)
            try:
                max_trades_allowed = int(rank.copy_trades_limit) if rank else 1
            except (ValueError, AttributeError):
                max_trades_allowed = 1  # Default to 1 trade per day
            
            # Calculate profit per individual trade
            if max_trades_allowed > 0:
                profit_per_trade = potential_daily_profit / Decimal(str(max_trades_allowed))
            else:
                profit_per_trade = Decimal('0.50')  # Default minimum
            
            # Add small variance to make it realistic (±5% variation)
            variance_percentage = Decimal('0.05')  # 5% variance
            variance_amount = profit_per_trade * variance_percentage
            variance = (Decimal('0.5') + Decimal(str(random.random()))) * variance_amount  # 50% to 150% of variance
            
            # Randomly decide if it's slightly above or below the target
            if random.random() < 0.6:  # 60% chance to be slightly above target
                target_profit = profit_per_trade + variance
            else:  # 40% chance to be slightly below target
                target_profit = profit_per_trade - variance
            
            # Ensure profit is not negative
            target_profit = max(target_profit, Decimal('0.01'))
            
            # Remove restrictive lot size limits - use the calculated per-trade profit
            # This ensures users reach their potential daily profit across all trades
            
            # Apply gradual progress with realistic fluctuation
            fluctuation = Decimal('0.95') + Decimal('0.15') * Decimal(str(random.random()))  # 95% to 110%
            current_profit = target_profit * Decimal(str(progress)) * fluctuation
            
            trade.profit = current_profit
        
        trade.save(update_fields=['profit'])

# =============================================================================
# Helper functions
# =============================================================================

def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not (request.user.is_superuser or getattr(request.user, 'role', '') == 'admin'):
            messages.error(request, 'You are not authorized to access this page.')
            return redirect('crypto:login')
        return view_func(request, *args, **kwargs)
    return wrapper

def detect_and_flag_multiple_accounts():
    """Comprehensive multi-account detection system"""
    from django.utils import timezone
    from datetime import timedelta
    from collections import defaultdict
    
    flagged_count = 0
    
    # 1. IP-based detection (multiple accounts from same IP)
    ip_users = defaultdict(list)
    for user in User.objects.filter(is_banned=False, is_flagged=False).exclude(role='admin'):
        if user.last_login_ip:
            ip_users[user.last_login_ip].append(user)
    
    for ip, users in ip_users.items():
        if len(users) >= 2:  # Multiple accounts from same IP
            # Flag all accounts from this IP
            for user in users:
                user.is_flagged = True
                user.save(update_fields=['is_flagged'])
                flagged_count += 1
                
                # Create notification
                Notification.objects.create(
                    user=user,
                    message=f"Your account has been flagged for multiple accounts from IP address {ip}."
                )
    
    # 2. Phone-based detection (multiple accounts with same phone)
    phone_users = defaultdict(list)
    for user in User.objects.filter(is_banned=False, is_flagged=False).exclude(role='admin'):
        if user.phone and user.phone.strip():
            phone_users[user.phone].append(user)
    
    for phone, users in phone_users.items():
        if len(users) >= 2:  # Multiple accounts with same phone
            for user in users:
                user.is_flagged = True
                user.save(update_fields=['is_flagged'])
                flagged_count += 1
                
                # Create notification
                Notification.objects.create(
                    user=user,
                    message=f"Your account has been flagged for multiple accounts with phone number {phone}."
                )
    
    # 3. Device fingerprinting (same user agent + IP pattern)
    # This would require storing user agent on login - for future enhancement
    
    # 4. Referral abuse detection (circular referrals)
    for user in User.objects.filter(is_banned=False, is_flagged=False).exclude(role='admin'):
        profile = getattr(user, 'profile', None)
        if profile and profile.referral_code:
            # Check if user is referring themselves through other accounts
            referred_users = User.objects.filter(
                profile__referral_code=profile.referral_code
            ).exclude(pk=user.pk)
            
            if referred_users.exists():
                user.is_flagged = True
                user.save(update_fields=['is_flagged'])
                flagged_count += 1
                
                Notification.objects.create(
                    user=user,
                    message="Your account has been flagged for referral abuse."
                )
    
    # 5. Suspicious timing patterns (multiple accounts created in short time)
    recent_time = timezone.now() - timedelta(hours=24)
    recent_users = User.objects.filter(
        date_joined__gte=recent_time,
        is_banned=False,
        is_flagged=False
    ).exclude(role='admin')
    
    # Group by hour of creation
    hour_groups = defaultdict(list)
    for user in recent_users:
        hour_key = user.date_joined.replace(minute=0, second=0, microsecond=0)
        hour_groups[hour_key].append(user)
    
    for hour, users in hour_groups.items():
        if len(users) >= 3:  # 3+ accounts created in same hour
            for user in users:
                user.is_flagged = True
                user.save(update_fields=['is_flagged'])
                flagged_count += 1
                
                Notification.objects.create(
                    user=user,
                    message=f"Your account has been flagged for suspicious registration patterns."
                )
    
    return flagged_count

def _check_multi_account(ip, phone, exclude_user_id=None):
    """Legacy function - kept for compatibility"""
    q = Q()
    if ip:
        q |= Q(last_login_ip=ip)
    if phone:
        q |= Q(phone=phone)
    if not q:
        return False, 0
    qs = User.objects.filter(q).exclude(role='admin')
    if exclude_user_id:
        qs = qs.exclude(pk=exclude_user_id)
    n = qs.count()
    return n >= 2, n

def _flag_multi_accounts(ip, phone):
    """Legacy function - kept for compatibility"""
    q = Q()
    if ip:
        q |= Q(last_login_ip=ip)
    if phone:
        q |= Q(phone=phone)
    if not q:
        return 0
    return User.objects.filter(q).exclude(role='admin').update(is_flagged=True)

def _update_user_rank(user):
    """Update user rank based on principal balance only"""
    try:
        profile = Profile.objects.select_related('rank').get(user=user)
        profile.update_rank()
        return profile.rank
    except Profile.DoesNotExist:
        return None

def calculate_daily_profit(user):
    """Calculate daily profit for user - idempotent, once per day"""
    try:
        profile = Profile.objects.select_related('rank').get(user=user)
    except Profile.DoesNotExist:
        return None
    
    # Safety invariants
    if profile.locked_balance <= 0:
        return None
    
    rank = profile.get_rank()
    if not rank:
        return None
    
    # TODO: Implement DailyProfit tracking after migration
    # For now, just calculate and return the amount
    daily_profit_amount = profile.locked_balance * (rank.daily_profit_percentage / Decimal('100'))
    
    if daily_profit_amount <= 0:
        return None
    
    # Add profit to withdrawable balance
    profile.withdrawable_balance += daily_profit_amount
    profile.save(update_fields=['withdrawable_balance'])
    
    return daily_profit_amount

def get_concurrent_copy_trades(user):
    """Get count of copy trades in the last 24 hours"""
    from django.utils import timezone
    from datetime import timedelta
    
    last_24_hours = timezone.now() - timedelta(hours=24)
    return CopyTrade.objects.filter(
        user=user, 
        created_at__gte=last_24_hours
    ).count()

# =============================================================================
# Auth
# =============================================================================

@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('crypto:dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        if user.is_banned:
            messages.error(request, 'Account banned.')
            return redirect('crypto:login')
        ip = get_client_ip(request)
        user.last_login_ip = ip
        user.save(update_fields=['last_login_ip'])
        multi, _ = _check_multi_account(ip, user.phone, user.pk)
        if multi:
            _flag_multi_accounts(ip, user.phone)
        login(request, user)
        messages.success(request, 'Logged in.')
        next_url = request.GET.get('next') or 'crypto:dashboard'
        return redirect(next_url)
    return render(request, 'crypto/login.html', {'form': form})

@require_http_methods(['GET', 'POST'])
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('crypto:dashboard')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ip = get_client_ip(request)
        if User.objects.filter(last_login_ip=ip, is_banned=True).exists():
            messages.error(request, 'Access denied.')
            return redirect('crypto:signup')
        user = form.save(commit=False)
        user.role = 'user'
        user.save()
        multi, _ = _check_multi_account(ip, getattr(user, 'phone', None), user.pk)
        if multi:
            _flag_multi_accounts(ip, getattr(user, 'phone', None))
        code = generate_referral_code()
        while Profile.objects.filter(referral_code=code).exists():
            code = generate_referral_code()
        Profile.objects.create(user=user, referral_code=code)
        login(request, user)
        messages.success(request, 'Account created.')
        return redirect('crypto:dashboard')
    return render(request, 'crypto/signup.html', {'form': form})

@require_GET
def logout_view(request):
    logout(request)
    messages.info(request, 'Logged out.')
    return redirect('crypto:login')

# Dashboard
# =============================================================================

@login_required(login_url='crypto:login')
def dashboard_view(request):
    if request.user.is_banned:
        logout(request)
        return redirect('crypto:login')
    
    # Process any pending trades (realistic delay processing)
    update_pending_trades_profit()  # Update fluctuating profits
    complete_pending_trades()  # Complete trades that are ready
    process_expired_deposits()  # Process expired deposits and rank changes
    
    # Run multi-account detection periodically (every 50th visit to reduce overhead)
    import random
    if random.randint(1, 50) == 1:  # 2% chance on each dashboard load (reduced from 10%)
        flagged_count = detect_and_flag_multiple_accounts()
        if flagged_count > 0 and request.user.is_staff:
            messages.info(request, f"Auto-detected and flagged {flagged_count} accounts for multi-account abuse.")
    
    # TODO: Fix admin redirect after database is properly set up
    # Temporarily disable admin redirect to avoid loops
    # if request.user.is_staff or getattr(request.user, 'role', '') == 'admin':
    #     return redirect('crypto:admin_dashboard')
    
    profile = getattr(request.user, 'profile', None)
    if not profile:
        # Create profile if it doesn't exist
        from crypto.models import Profile
        try:
            profile = Profile.objects.create(user=request.user, referral_code='TEMP123')
        except Exception:
            # If profile creation fails, redirect to login
            return redirect('crypto:login')
    
    # Update rank based on current principal balance
    profile.update_rank()
    rank = profile.rank
    
    # Calculate daily profit if eligible (only once per day)
    # Check if profit already calculated for today
    from django.utils import timezone
    from datetime import timedelta
    today = timezone.now().date()
    
    # Since DailyProfit model is commented out, we'll use a simple approach
    # Calculate today's actual profit from copy trades + potential daily profit
    last_24_hours = timezone.now() - timedelta(hours=24)
    
    # Get copy trades from today (since midnight)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    copy_trades_today = CopyTrade.objects.filter(
        user=request.user,
        created_at__gte=today_start
    )
    
    # Calculate today's actual profit from copy trades
    copy_trade_profit_today = copy_trades_today.aggregate(
        total=Sum('profit')
    )['total'] or Decimal('0')
    
    # Calculate potential daily profit from rank
    if rank and profile.locked_balance > 0 and rank.daily_profit_pct:
        potential_daily_profit = profile.locked_balance * (Decimal(str(rank.daily_profit_pct)) / Decimal('100'))
    else:
        potential_daily_profit = Decimal('0')
    
    # Today's total profit = copy trade profit from today
    daily_profit_amount = copy_trade_profit_today
    
    # Use the calculated values
    todays_potential_profit = potential_daily_profit
    
    # Calculate copy trade profit in last 24 hours (separate from today's profit)
    copy_trades_24h = CopyTrade.objects.filter(
        user=request.user,
        created_at__gte=last_24_hours
    )
    total_copy_trade_profit_24h = copy_trades_24h.aggregate(
        total=Sum('profit')
    )['total'] or Decimal('0')
    
    # Count profitable vs loss trades in last 24 hours
    profitable_trades_24h = copy_trades_24h.filter(profit__gt=0).count()
    loss_trades_24h = copy_trades_24h.filter(profit__lt=0).count()
    
    # Get copy trade limit safely
    try:
        limit = int(rank.max_copy_trades) if rank else 0
    except (ValueError, AttributeError):
        try:
            limit = int(rank.copy_trades_limit) if rank else 0
        except (ValueError, AttributeError):
            limit = 5  # Default limit
    trades = CopyTrade.objects.filter(user=request.user).order_by('-created_at')[: max(limit, 20)]
    pending_deposits = Deposit.objects.filter(user=request.user, status='pending').order_by('-created_at')
    last_reward = DailyReward.objects.filter(user=request.user).order_by('-claimed_at').first()
    can_claim = not last_reward or not is_same_day(last_reward.claimed_at, timezone.now())
    ranks = list(Rank.objects.order_by('min_balance'))
    
    # Mark current rank
    for r in ranks:
        r.is_current = rank and r.pk == rank.pk
    
    ctx = {
        'profile': profile,
        'copy_trades': trades,
        'copy_trades_limit': limit,
        'pending_deposits': pending_deposits,
        'can_claim_daily': can_claim,
        'daily_reward_amount': DAILY_REWARD,
        'ranks': ranks,
        'min_withdrawal': MIN_WITHDRAWAL,
        'todays_profit': daily_profit_amount or Decimal('0'),
        'todays_potential_profit': todays_potential_profit,
        'rank': rank,
    }
    return render(request, 'crypto/dashboard.html', ctx)

@login_required(login_url='crypto:login')
@require_POST
def daily_reward_view(request):
    if request.user.is_banned:
        return redirect('crypto:login')
    profile = get_object_or_404(Profile, user=request.user)
    last = DailyReward.objects.filter(user=request.user).order_by('-claimed_at').first()
    if last and is_same_day(last.claimed_at, timezone.now()):
        messages.warning(request, 'Already claimed today.')
        return redirect('crypto:dashboard')
    profile.withdrawable_balance += DAILY_REWARD
    profile.save(update_fields=['withdrawable_balance'])
    DailyReward.objects.create(user=request.user, amount=DAILY_REWARD)
    _update_user_rank(request.user)
    messages.success(request, f'Daily reward ${DAILY_REWARD} claimed.')
    return redirect('crypto:dashboard')

# --------------------------------------------------------------------------
# Copy trade simulation (user)
# --------------------------------------------------------------------------

@login_required(login_url='crypto:login')
@require_POST
def copy_trade_simulate_view(request):
    if request.user.is_banned:
        return redirect('crypto:login')
    profile = get_object_or_404(Profile, user=request.user)
    rank = profile.get_rank()
    
    # Safety check: user must have a rank to trade
    if not rank:
        messages.warning(request, 'No rank assigned. Cannot execute copy trades.')
        return redirect('crypto:dashboard')
    
    # Check copy trade limit for last 24 hours
    trades_last_24h = get_concurrent_copy_trades(request.user)
    # Get max trades allowed safely
    try:
        max_trades_allowed = int(rank.max_copy_trades) if rank else 0
    except (ValueError, AttributeError):
        try:
            max_trades_allowed = int(rank.copy_trades_limit) if rank else 0
        except (ValueError, AttributeError):
            max_trades_allowed = 5  # Default limit
    
    if trades_last_24h >= max_trades_allowed:
        messages.warning(request, f'Copy trade limit reached for the last 24 hours ({max_trades_allowed}/{max_trades_allowed}). Try again tomorrow.')
        return redirect('crypto:dashboard')
    
    messages.info(request, f'Copy trades used: {trades_last_24h}/{max_trades_allowed} in last 24 hours')
    
    # Safety check: must have principal balance
    if profile.principal_balance <= 0:
        messages.warning(request, 'Insufficient balance to execute copy trades.')
        return redirect('crypto:dashboard')
    
    pair = random.choice(PAIRS)
    action = random.choice(['buy', 'sell'])
    # Small lot size for copy trading (0.01 to 0.1) - generates big profit from small lots
    lot_amount = Decimal('0.01') + Decimal('0.09') * Decimal(str(random.random()))  # 0.01 to 0.10
    amount = lot_amount
    
    # Generate realistic profit/loss for the trade (can be positive or negative)
    # 100% win rate - players always win with profits close to potential daily profit
    # Calculate target daily profit based on user's rank
    if rank and profile.locked_balance > 0 and rank.daily_profit_pct:
        potential_daily_profit = profile.locked_balance * (Decimal(str(rank.daily_profit_pct)) / Decimal('100'))
    else:
        potential_daily_profit = Decimal('0.50')  # Default minimum target
    
    # Calculate profit per trade (potential daily profit divided by daily trade limit)
    # This ensures users reach potential daily profit when executing maximum trades
    try:
        max_trades_allowed = int(rank.copy_trades_limit) if rank else 1
    except (ValueError, AttributeError):
        max_trades_allowed = 1  # Default to 1 trade per day
    
    # Calculate profit per individual trade
    if max_trades_allowed > 0:
        profit_per_trade = potential_daily_profit / Decimal(str(max_trades_allowed))
    else:
        profit_per_trade = Decimal('0.50')  # Default minimum
    
    # Add small variance to make it realistic (±5% variation)
    variance_percentage = Decimal('0.05')  # 5% variance
    variance_amount = profit_per_trade * variance_percentage
    variance = (Decimal('0.5') + Decimal(str(random.random()))) * variance_amount  # 50% to 150% of variance
    
    # Randomly decide if it's slightly above or below the target
    if random.random() < 0.6:  # 60% chance to be slightly above target
        trade_profit = profit_per_trade + variance
    else:  # 40% chance to be slightly below target
        trade_profit = profit_per_trade - variance
    
    # Ensure profit is not negative
    trade_profit = max(trade_profit, Decimal('0.01'))
    
    # Remove restrictive lot size limits - use the calculated per-trade profit
    # This ensures users reach their potential daily profit across all trades
    
    # Create copy trade with initial status 'pending' (realistic delay)
    trade = CopyTrade.objects.create(
        user=request.user, 
        pair=pair, 
        action=action, 
        amount=amount, 
        profit=Decimal('0'),  # Start with 0 profit
        status='pending'  # Pending status for realistic delay
    )
    
    messages.success(request, f'Copy trade submitted: {pair} {action} — ${amount:.2f}. Processing...')
    return redirect('crypto:dashboard')

# =============================================================================
# Finance
# =============================================================================

@login_required(login_url='crypto:login')
def finance_view(request):
    if request.user.is_banned:
        return redirect('crypto:login')
    from django.conf import settings
    from django.utils import timezone
    import datetime
    
    profile = getattr(request.user, 'profile', None)
    
    # Crypto deposits and withdrawals
    # Crypto deposits
    deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')
    withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
    total_deposits = deposits.filter(status='approved').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    pending_deposits = deposits.filter(status='pending').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    total_withdrawals = withdrawals.filter(status='approved').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    
    # Local deposits and withdrawals
    from crypto.models import LocalDeposit, LocalWithdrawal
    local_deposits = LocalDeposit.objects.filter(user=request.user).order_by('-created_at')
    local_withdrawals = LocalWithdrawal.objects.filter(user=request.user).order_by('-created_at')
    total_local_deposits = local_deposits.filter(status='paid').aggregate(s=Sum('amount_usdt'))['s'] or Decimal('0')
    pending_local_deposits = local_deposits.filter(status='pending').aggregate(s=Sum('amount_usdt'))['s'] or Decimal('0')
    total_local_withdrawals = local_withdrawals.filter(status='completed').aggregate(s=Sum('amount_usdt'))['s'] or Decimal('0')
    
    # Combine all deposits into a single list sorted by date
    all_deposits = []
    
    # Add crypto deposits
    for deposit in deposits:
        all_deposits.append({
            'pk': deposit.id,
            'id': deposit.id,
            'user': deposit.user,
            'amount': deposit.amount,
            'type': 'crypto',
            'network': deposit.network,
            'wallet_address': deposit.wallet_address,
            'status': deposit.status,
            'created_at': deposit.created_at,
            'approved_at': deposit.approved_at,
            'referrer': deposit.referrer,
        })
    
    # Add Paystack deposits
    for deposit in local_deposits:
        all_deposits.append({
            'pk': deposit.id,
            'id': deposit.id,
            'user': deposit.user,
            'amount': deposit.amount_usdt,
            'type': 'paystack',
            'network': f'Paystack NGN (₦{deposit.amount_ngn:.2f})',
            'wallet_address': deposit.paystack_reference,
            'status': 'paid' if deposit.status == 'paid' else deposit.status,
            'created_at': deposit.created_at,
            'approved_at': deposit.paid_at,
            'referrer': deposit.referrer,
        })
    
    # Sort all deposits by created_at (newest first)
    all_deposits.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Combine crypto and local withdrawals into a single list
    all_withdrawals = []
    
    # Add crypto withdrawals
    for withdrawal in withdrawals:
        all_withdrawals.append({
            'pk': withdrawal.id,
            'amount': withdrawal.amount,
            'type': 'crypto',
            'network': withdrawal.network,
            'wallet_address': withdrawal.wallet_address,
            'status': withdrawal.status,
            'created_at': withdrawal.created_at,
            'processed_at': withdrawal.processed_at,
        })
    
    # Add local withdrawals
    for withdrawal in local_withdrawals:
        all_withdrawals.append({
            'pk': withdrawal.id,
            'amount': withdrawal.amount_usdt,
            'type': 'local',
            'network': f'{withdrawal.bank_name} ({withdrawal.account_number})',
            'wallet_address': f'{withdrawal.account_holder_name}',
            'status': withdrawal.status,
            'created_at': withdrawal.created_at,
            'processed_at': withdrawal.processed_at,
        })
    
    # Sort all withdrawals by created_at (newest first)
    all_withdrawals.sort(key=lambda x: x['created_at'], reverse=True)
    
    ref_bonus = profile.referral_earnings if profile else Decimal('0')
    daily_sum = DailyReward.objects.filter(user=request.user).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    
    # Forms
    from crypto.forms import LocalDepositForm, LocalWithdrawalForm
    deposit_form = DepositForm(request.POST or None)
    withdrawal_form = WithdrawalForm(request.POST or None)
    local_deposit_form = LocalDepositForm(request.POST or None)
    local_withdrawal_form = LocalWithdrawalForm(request.POST or None, user=request.user)
    
    last_deposit = request.session.get('last_deposit')
    
    # Check if deposit has expired (5 minutes)
    if last_deposit:
        created_at_str = last_deposit.get('created_at')
        if created_at_str:
            try:
                # Parse the timestamp and check if it's older than 5 minutes
                created_at = datetime.datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                current_time = timezone.now()
                time_diff = current_time - created_at
                
                if time_diff.total_seconds() >= 300:  # 5 minutes = 300 seconds
                    # Deposit expired, remove from session
                    del request.session['last_deposit']
                    last_deposit = None
                    messages.info(request, 'Your previous deposit wallet address has expired. Please create a new deposit.')
            except (ValueError, AttributeError):
                # Invalid timestamp, remove the deposit
                del request.session['last_deposit']
                last_deposit = None
    
    # Convert session data to object-like structure for template
    if last_deposit:
        class LastDeposit:
            def __init__(self, data):
                self.amount = data.get('amount')
                self.network = data.get('network')
                self.wallet_address = data.get('wallet_address')
                self.created_at = data.get('created_at')
                self.created_timestamp = data.get('created_timestamp')
                self.deposit_id = data.get('deposit_id')
                self.deposit_type = data.get('deposit_type', 'crypto')
                self.paystack_reference = data.get('paystack_reference')
        
        last_deposit = LastDeposit(last_deposit)

    if request.method == 'POST':
        # Crypto deposit submission
        if 'deposit' in request.POST and deposit_form.is_valid():
            amt = deposit_form.cleaned_data['amount']
            net = deposit_form.cleaned_data['network']
            ref_code = (deposit_form.cleaned_data.get('referrer_code') or '').strip()
            ref = None
            if ref_code:
                p = Profile.objects.filter(referral_code=ref_code).exclude(user=request.user).first()
                if p:
                    ref = p.user
            
            # Get available wallet with 5-minute assignment
            wallet, time_remaining = get_available_wallet(net, request.user.id)
            
            if wallet is None:
                # No wallet available, show waiting message
                minutes = int(time_remaining // 60)
                seconds = int(time_remaining % 60)
                messages.warning(request, f'No wallet available. Please wait {minutes}m {seconds}s for a wallet to be released.')
                return redirect('crypto:finance')
            
            deposit = Deposit.objects.create(
                user=request.user,
                amount=amt,
                network=net,
                wallet_address=wallet,
                referrer=ref,
                status='pending'
            )
            
            # Store deposit info for modal
            deposit_data = {
                'amount': float(amt),
                'network': net,
                'wallet_address': wallet,
                'created_at': timezone.now().isoformat(),
                'created_timestamp': int(timezone.now().timestamp()),  # Add Unix timestamp
                'expires_at': (timezone.now() + datetime.timedelta(minutes=5)).isoformat(),
                'deposit_id': deposit.id  # Add deposit ID for status checking
            }
            request.session['last_deposit'] = deposit_data
            
            messages.success(request, f'Deposit request of ${amt} submitted. Send ${amt} to {wallet}.')
            return redirect('crypto:finance')
        
        # Local deposit submission
        elif 'local_deposit' in request.POST and local_deposit_form.is_valid():
            amount_usdt = local_deposit_form.cleaned_data['amount_usdt']
            conversion_rate = getattr(settings, 'LOCAL_PAYMENT_CONVERSION_RATE', 1600)
            amount_ngn = amount_usdt * conversion_rate
            
            # Create deposit record
            from crypto.models import LocalDeposit
            from crypto.paystack_service import PaystackService
            deposit = LocalDeposit.objects.create(
                user=request.user,
                amount_usdt=amount_usdt,
                amount_ngn=amount_ngn,
                conversion_rate=conversion_rate,
                paystack_reference=f"DEP_{uuid.uuid4().hex[:12]}"
            )
            
            # Initialize Paystack transaction immediately (no timer needed)
            callback_url = getattr(settings, 'PAYSTACK_CALLBACK_URL', 'http://127.0.0.1:8000/paystack/callback/')
            paystack_response = PaystackService.initialize_transaction(
                amount=amount_ngn,
                email=request.user.email,
                callback_url=callback_url,
                reference=deposit.paystack_reference
            )
            
            if paystack_response.get('status'):
                # Update deposit with Paystack reference
                deposit.paystack_reference = paystack_response['data']['reference']
                deposit.save(update_fields=['paystack_reference'])
                
                # Redirect to Paystack immediately (no modal)
                return redirect(paystack_response['data']['authorization_url'])
            else:
                messages.error(request, "Failed to initialize Paystack payment. Please try again.")
                return redirect('crypto:finance')
        
        # Crypto withdrawal submission
        elif 'withdrawal' in request.POST and withdrawal_form.is_valid():
            amt = withdrawal_form.cleaned_data['amount']
            net = withdrawal_form.cleaned_data['network']
            wallet = withdrawal_form.cleaned_data.get('wallet_address', '')
            if amt > profile.withdrawable_balance:
                messages.error(request, 'Insufficient withdrawable balance.')
                return redirect('crypto:finance')
            profile.withdrawable_balance -= amt
            profile.save(update_fields=['withdrawable_balance'])
            Withdrawal.objects.create(
                user=request.user,
                amount=amt,
                network=net,
                wallet_address=wallet,
                status='pending_admin_approval'
            )
            profile.last_withdrawal_at = timezone.now()
            profile.save(update_fields=['last_withdrawal_at'])
            profile.update_rank()
            messages.success(request, 'Withdrawal submitted. Admin approval required.')
            return redirect('crypto:finance')
        
        # Local withdrawal submission
        elif 'local_withdrawal' in request.POST and local_withdrawal_form.is_valid():
            amount_usdt = local_withdrawal_form.cleaned_data['amount_usdt']
            bank_name = local_withdrawal_form.cleaned_data['bank_name']
            account_number = local_withdrawal_form.cleaned_data['account_number']
            account_holder_name = local_withdrawal_form.cleaned_data['account_holder_name']
            
            conversion_rate = 1430  # ₦1430 = 1 USDT for withdrawals
            amount_ngn = amount_usdt * conversion_rate
            
            # Deduct funds immediately
            if amount_usdt > profile.withdrawable_balance:
                messages.error(request, "Insufficient balance")
                return redirect('crypto:finance')
            
            profile.withdrawable_balance -= amount_usdt
            profile.save(update_fields=['withdrawable_balance'])
            
            # Create withdrawal record
            from crypto.models import LocalWithdrawal
            withdrawal = LocalWithdrawal.objects.create(
                user=request.user,
                amount_usdt=amount_usdt,
                amount_ngn=amount_ngn,
                conversion_rate=conversion_rate,
                bank_name=bank_name,
                account_number=account_number,
                account_holder_name=account_holder_name,
                status='pending_admin_approval'
            )
            
            messages.success(request, f"Local withdrawal request of ${amount_usdt} submitted successfully. Awaiting admin approval.")
            return redirect('crypto:finance')

    ctx = {
        'profile': profile,
        'overview': {
            'total_deposits': total_deposits + total_local_deposits,
            'pending_deposits': pending_deposits + pending_local_deposits,
            'total_withdrawals': total_withdrawals + total_local_withdrawals,
            'referral_bonuses': ref_bonus,
            'daily_rewards': daily_sum,
        },
        'all_deposits': all_deposits,  # Combined and sorted deposits
        'all_withdrawals': all_withdrawals,  # Combined and sorted withdrawals
        'withdrawals': withdrawals,
        'local_withdrawals': local_withdrawals,
        'networks': NETWORKS,
        'min_deposit': MIN_DEPOSIT,
        'min_withdrawal': MIN_WITHDRAWAL,
        'deposit_form': deposit_form,
        'withdrawal_form': withdrawal_form,
        'local_deposit_form': local_deposit_form,
        'local_withdrawal_form': local_withdrawal_form,
        'last_deposit': last_deposit,
        'conversion_rate': getattr(settings, 'LOCAL_PAYMENT_CONVERSION_RATE', 1600),
    }
    return render(request, 'crypto/finance.html', ctx)
# =============================================================================

@login_required(login_url='crypto:login')
def profile_view(request):
    if request.user.is_banned:
        return redirect('crypto:login')
    profile = get_object_or_404(Profile, user=request.user)
    
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, user=request.user, instance=profile)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            # Reload the profile to get updated data
            profile.refresh_from_db()
            # Create new form with updated instance
            form = ProfileUpdateForm(user=request.user, instance=profile)
    else:
        form = ProfileUpdateForm(user=request.user, instance=profile)
    
    ctx = {'profile': profile, 'form': form, 'user': request.user}
    return render(request, 'crypto/profile.html', ctx)

# =============================================================================
# Contact Us
# =============================================================================

def contact_view(request):
    """Contact us page with links to support channels"""
    return render(request, 'crypto/contact.html')

# =============================================================================
# Local Payments
# =============================================================================

@login_required(login_url='crypto:login')
def local_deposit_view(request):
    """Handle local deposit with Paystack"""
    if request.user.is_banned:
        return redirect('crypto:login')
    
    from crypto.forms import LocalDepositForm
    from crypto.models import LocalDeposit
    from crypto.paystack_service import PaystackService
    from django.conf import settings
    
    if request.method == 'POST':
        form = LocalDepositForm(request.POST)
        if form.is_valid():
            amount_usdt = form.cleaned_data['amount_usdt']
            conversion_rate = getattr(settings, 'LOCAL_PAYMENT_CONVERSION_RATE', 1600)
            amount_ngn = amount_usdt * conversion_rate
            
            # Create deposit record
            deposit = LocalDeposit.objects.create(
                user=request.user,
                amount_usdt=amount_usdt,
                amount_ngn=amount_ngn,
                conversion_rate=conversion_rate,
                paystack_reference=f"DEP_{uuid.uuid4().hex[:12]}"
            )
            
            # Initialize Paystack transaction
            callback_url = getattr(settings, 'PAYSTACK_CALLBACK_URL', 'http://127.0.0.1:8000/paystack/callback/')
            paystack_response = PaystackService.initialize_transaction(
                amount=amount_ngn,
                email=request.user.email,
                callback_url=callback_url,
                reference=deposit.paystack_reference
            )
            
            if paystack_response.get('status'):
                deposit.paystack_response = paystack_response
                deposit.paystack_access_code = paystack_response['data']['access_code']
                deposit.save()
                
                # Redirect to Paystack payment page
                authorization_url = paystack_response['data']['authorization_url']
                return redirect(authorization_url)
            else:
                messages.error(request, f"Payment initialization failed: {paystack_response.get('message', 'Unknown error')}")
                deposit.delete()
    else:
        form = LocalDepositForm()
    
    # Get user's recent deposits
    recent_deposits = LocalDeposit.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    ctx = {
        'form': form,
        'recent_deposits': recent_deposits,
        'conversion_rate': getattr(settings, 'LOCAL_PAYMENT_CONVERSION_RATE', 1600),
    }
    return render(request, 'crypto/local_deposit.html', ctx)


@login_required(login_url='crypto:login')
def local_withdrawal_view(request):
    """Handle local withdrawal with bank details"""
    if request.user.is_banned:
        return redirect('crypto:login')
    
    from crypto.forms import LocalWithdrawalForm
    from crypto.models import LocalWithdrawal
    from django.conf import settings
    
    if request.method == 'POST':
        form = LocalWithdrawalForm(request.POST, user=request.user)
        if form.is_valid():
            amount_usdt = form.cleaned_data['amount_usdt']
            bank_name = form.cleaned_data['bank_name']
            account_number = form.cleaned_data['account_number']
            account_holder_name = form.cleaned_data['account_holder_name']
            
            conversion_rate = 1430  # ₦1430 = 1 USDT for withdrawals
            amount_ngn = amount_usdt * conversion_rate
            
            # Deduct funds immediately
            profile = request.user.profile
            if amount_usdt > profile.withdrawable_balance:
                messages.error(request, "Insufficient balance")
                return redirect('crypto:local_withdrawal')
            
            profile.withdrawable_balance -= amount_usdt
            profile.save(update_fields=['withdrawable_balance'])
            
            # Create withdrawal record
            withdrawal = LocalWithdrawal.objects.create(
                user=request.user,
                amount_usdt=amount_usdt,
                amount_ngn=amount_ngn,
                conversion_rate=conversion_rate,
                bank_name=bank_name,
                account_number=account_number,
                account_holder_name=account_holder_name,
                status='pending_admin_approval'
            )
            
            messages.success(request, f"Withdrawal request of ${amount_usdt} submitted successfully. Awaiting admin approval.")
            return redirect('crypto:local_withdrawal')
    else:
        form = LocalWithdrawalForm(user=request.user)
    
    # Get user's recent withdrawals
    recent_withdrawals = LocalWithdrawal.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    ctx = {
        'form': form,
        'recent_withdrawals': recent_withdrawals,
        'conversion_rate': getattr(settings, 'LOCAL_PAYMENT_CONVERSION_RATE', 1600),
        'available_balance': request.user.profile.withdrawable_balance,
    }
    return render(request, 'crypto/local_withdrawal.html', ctx)


@csrf_exempt
def paystack_callback_view(request):
    """Handle Paystack webhook callbacks and redirects"""
    if request.method == 'POST':
        # Handle webhook (POST request)
        import json
        from crypto.paystack_service import PaystackWebhookHandler
        
        try:
            # Log incoming webhook
            payload = json.loads(request.body)
            signature = request.headers.get('x-paystack-signature', '')
            
            print(f"DEBUG: Paystack webhook received")
            print(f"DEBUG: Event: {payload.get('event', 'unknown')}")
            print(f"DEBUG: Reference: {payload.get('data', {}).get('reference', 'unknown')}")
            print(f"DEBUG: Signature: {signature[:20]}..." if signature else "DEBUG: No signature")
            
            # Verify webhook signature (implement proper verification in production)
            if not PaystackWebhookHandler.verify_webhook_signature(request.body, signature):
                print("DEBUG: Webhook signature verification failed")
                return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=401)
            
            event = payload.get('event', '')
            print(f"DEBUG: Processing webhook event: {event}")
            
            if event == 'charge.success':
                success, message = PaystackWebhookHandler.handle_charge_success(payload)
                print(f"DEBUG: Charge success result: {success} - {message}")
                return JsonResponse({'status': 'success' if success else 'error', 'message': message})
            
            elif event == 'transfer.success':
                success, message = PaystackWebhookHandler.handle_transfer_success(payload)
                print(f"DEBUG: Transfer success result: {success} - {message}")
                return JsonResponse({'status': 'success' if success else 'error', 'message': message})
            
            elif event == 'transfer.failed':
                success, message = PaystackWebhookHandler.handle_transfer_failed(payload)
                print(f"DEBUG: Transfer failed result: {success} - {message}")
                return JsonResponse({'status': 'success' if success else 'error', 'message': message})
            
            else:
                print(f"DEBUG: Unhandled webhook event: {event}")
                return JsonResponse({'status': 'success', 'message': f'Event {event} received'})
                
        except json.JSONDecodeError as e:
            print(f"DEBUG: JSON decode error: {e}")
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"DEBUG: Webhook processing error: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'status': 'error', 'message': 'Processing error'}, status=500)
    
    elif request.method == 'GET':
        # Handle Paystack redirect after payment (GET request)
        reference = request.GET.get('reference', '')
        print(f"DEBUG: Paystack redirect received with reference: {reference}")
        
        if reference:
            try:
                from crypto.models import LocalDeposit
                from crypto.paystack_service import PaystackService
                
                deposit = LocalDeposit.objects.get(paystack_reference=reference)
                
                # Verify transaction with Paystack
                verification_response = PaystackService.verify_transaction(reference)
                
                if verification_response.get('status') and verification_response['data']['status'] == 'success':
                    deposit.status = 'paid'
                    deposit.paystack_response = verification_response
                    deposit.save()
                    
                    # Add funds to user's locked balance
                    profile = deposit.user.profile
                    profile.locked_balance += deposit.amount_usdt
                    profile.save(update_fields=['locked_balance'])
                    
                    # Update user rank
                    profile.update_rank()
                    
                    print(f"DEBUG: Payment verified successfully for reference: {reference}")
                    print(f"DEBUG: User balance updated: +${deposit.amount_usdt}")
                    
                    # Redirect back to finance page with success message
                    from django.contrib import messages
                    messages.success(request, f"Deposit of ${deposit.amount_usdt} confirmed and added to your account!")
                    return redirect('crypto:finance')
                else:
                    deposit.status = 'failed'
                    deposit.paystack_response = verification_response
                    deposit.save()
                    
                    print(f"DEBUG: Payment verification failed for reference: {reference}")
                    
                    from django.contrib import messages
                    messages.error(request, "Payment verification failed. Please contact support.")
                    return redirect('crypto:finance')
                    
            except LocalDeposit.DoesNotExist:
                print(f"DEBUG: Invalid payment reference: {reference}")
                from django.contrib import messages
                messages.error(request, "Invalid payment reference")
                return redirect('crypto:finance')
            except Exception as e:
                print(f"DEBUG: Error processing redirect: {e}")
                from django.contrib import messages
                messages.error(request, "Error processing payment verification")
                return redirect('crypto:finance')
        else:
            print(f"DEBUG: No reference provided in redirect")
            from django.contrib import messages
            messages.error(request, "No payment reference provided")
            return redirect('crypto:finance')
    
    else:
        print(f"DEBUG: Webhook received with method: {request.method}")
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


@login_required(login_url='crypto:login')
def paystack_verify_view(request):
    """Verify Paystack payment after redirect"""
    reference = request.GET.get('reference', '')
    if not reference:
        messages.error(request, "No payment reference provided")
        return redirect('crypto:local_deposit')
    
    from crypto.models import LocalDeposit
    from crypto.paystack_service import PaystackService
    
    try:
        deposit = LocalDeposit.objects.get(paystack_reference=reference)
        
        # Verify transaction with Paystack
        verification_response = PaystackService.verify_transaction(reference)
        
        if verification_response.get('status') and verification_response['data']['status'] == 'success':
            deposit.status = 'paid'
            deposit.paystack_response = verification_response
            deposit.save()
            
            # Add funds to user's locked balance
            profile = deposit.user.profile
            profile.locked_balance += deposit.amount_usdt
            profile.save(update_fields=['locked_balance'])
            
            # Update user rank
            profile.update_rank()
            
            messages.success(request, f"Deposit of ${deposit.amount_usdt} confirmed and added to your account!")
        else:
            deposit.status = 'failed'
            deposit.paystack_response = verification_response
            deposit.save()
            messages.error(request, "Payment verification failed. Please contact support.")
    
    except LocalDeposit.DoesNotExist:
        messages.error(request, "Invalid payment reference")
    
    return redirect('crypto:local_deposit')

# =============================================================================
# Referral / Promos
# =============================================================================

@login_required(login_url='crypto:login')
def referral_view(request):
    if request.user.is_banned:
        return redirect('crypto:login')
    profile = get_object_or_404(Profile, user=request.user)
    form = PromoRedeemForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['code'].strip()
        promo = PromoCode.objects.filter(code=code, status='active').first()
        if not promo:
            messages.error(request, 'Invalid or expired promo code.')
            return redirect('crypto:referral')
        if promo.expiration and promo.expiration < timezone.now():
            messages.error(request, 'Promo code expired.')
            return redirect('crypto:referral')
        if promo.usage_limit is not None and (promo.usage_count or 0) >= promo.usage_limit:
            messages.error(request, 'Usage limit reached.')
            return redirect('crypto:referral')
        if PromoRedemption.objects.filter(user=request.user, promo_code=promo).exists():
            messages.error(request, 'Already redeemed.')
            return redirect('crypto:referral')
        bonus = promo.bonus_min + (promo.bonus_max - promo.bonus_min) * Decimal(str(random.random()))
        
        # Create a deposit entry for the promo bonus with 30-day expiration
        expires_at = timezone.now() + timedelta(days=30)
        
        # Create deposit record for the promo bonus
        Deposit.objects.create(
            user=request.user,
            amount=bonus,
            network='PROMO',
            wallet_address='PROMO_BONUS',
            status='approved',
            expires_at=expires_at,
            approved_at=timezone.now()
        )
        
        # Add to locked balance (same as before)
        profile.locked_balance += bonus
        profile.save(update_fields=['locked_balance'])
        
        # Create promo redemption record
        PromoRedemption.objects.create(user=request.user, promo_code=promo, bonus_amount=bonus)
        promo.usage_count = (promo.usage_count or 0) + 1
        promo.save(update_fields=['usage_count'])
        
        # Update rank after promo redemption
        profile.update_rank()
        messages.success(request, f'Promo redeemed. Bonus ${bonus:.2f} credited (expires in 30 days).')
        return redirect('crypto:referral')
    ctx = {'profile': profile, 'form': form}
    return render(request, 'crypto/referral.html', ctx)

# =============================================================================
# Admin
# =============================================================================

# --- Dashboard ---
@login_required(login_url='crypto:login')
@admin_required
def admin_dashboard_view(request):
    from crypto.models import LocalDeposit, LocalWithdrawal
    total_users = User.objects.filter(is_staff=False).count()
    
    # Include both crypto and Paystack deposits
    crypto_deposits = Deposit.objects.filter(status='approved').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    local_deposits = LocalDeposit.objects.filter(status='paid').aggregate(s=Sum('amount_usdt'))['s'] or Decimal('0')
    total_deposits = crypto_deposits + local_deposits
    
    total_withdrawals = Withdrawal.objects.filter(status='approved').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    local_withdrawals = LocalWithdrawal.objects.filter(status='completed').aggregate(s=Sum('amount_usdt'))['s'] or Decimal('0')
    total_withdrawals = total_withdrawals + local_withdrawals
    
    # Include both crypto and Paystack pending deposits
    pending_crypto_deposits = Deposit.objects.filter(status='pending').count()
    pending_local_deposits = LocalDeposit.objects.filter(status='pending').count()
    pending_deposits = pending_crypto_deposits + pending_local_deposits
    
    pending_withdrawals = Withdrawal.objects.filter(status='pending_admin_approval').count()
    pending_local_withdrawals = LocalWithdrawal.objects.filter(status='pending_admin_approval').count()
    pending_withdrawals = pending_withdrawals + pending_local_withdrawals
    
    # Calculate total user balances
    total_locked_balance = Profile.objects.aggregate(s=Sum('locked_balance'))['s'] or Decimal('0')
    total_withdrawable_balance = Profile.objects.aggregate(s=Sum('withdrawable_balance'))['s'] or Decimal('0')
    
    ctx = {
        'total_users': total_users,
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
        'pending_deposits': pending_deposits,
        'pending_withdrawals': pending_withdrawals,
        'total_locked_balance': total_locked_balance,
        'total_withdrawable_balance': total_withdrawable_balance,
        'crypto_deposits': crypto_deposits,
        'local_deposits': local_deposits,
    }
    return render(request, 'crypto/admin/dashboard.html', ctx)

# --- Deposits ---
@login_required(login_url='crypto:login')
@admin_required
def admin_deposits_view(request):
    status = request.GET.get('status')
    deposit_type = request.GET.get('type', 'all')
    
    # Get both crypto and Paystack deposits
    crypto_deposits = Deposit.objects.select_related('user').order_by('-created_at')
    local_deposits = LocalDeposit.objects.select_related('user').order_by('-created_at')
    
    # Filter by status
    if status:
        if status == 'pending':
            crypto_deposits = crypto_deposits.filter(status='pending')
            local_deposits = local_deposits.filter(status='pending')
        elif status == 'approved':
            crypto_deposits = crypto_deposits.filter(status='approved')
            local_deposits = local_deposits.filter(status='paid')
        elif status == 'rejected':
            crypto_deposits = crypto_deposits.filter(status='rejected')
            local_deposits = local_deposits.filter(status='failed')
    
    # Filter by type
    if deposit_type == 'crypto':
        local_deposits = LocalDeposit.objects.none()
    elif deposit_type == 'paystack':
        crypto_deposits = Deposit.objects.none()
    
    # Combine and sort
    all_deposits = []
    
    # Add crypto deposits
    for deposit in crypto_deposits:
        all_deposits.append({
            'pk': deposit.id,  # Use 'pk' instead of 'id' for template compatibility
            'id': deposit.id,
            'user': deposit.user,
            'amount': deposit.amount,
            'type': 'crypto',
            'network': deposit.network,
            'wallet_address': deposit.wallet_address,
            'status': deposit.status,
            'created_at': deposit.created_at,
            'approved_at': deposit.approved_at,
            'referrer': deposit.referrer,
        })
    
    # Add Paystack deposits
    for deposit in local_deposits:
        all_deposits.append({
            'pk': deposit.id,  # Use 'pk' instead of 'id' for template compatibility
            'id': deposit.id,
            'user': deposit.user,
            'amount': deposit.amount_usdt,
            'type': 'paystack',
            'network': f'Paystack NGN (₦{deposit.amount_ngn:.2f})',
            'wallet_address': deposit.paystack_reference,
            'status': 'paid' if deposit.status == 'paid' else deposit.status,
            'created_at': deposit.created_at,
            'approved_at': deposit.paid_at,
            'referrer': deposit.referrer,
        })
    
    # Sort by created_at
    all_deposits.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render(request, 'crypto/admin/deposits.html', {'deposits': all_deposits})

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_deposit_approve_view(request, pk):
    # Try to find deposit in both models
    try:
        # First try crypto deposit
        d = get_object_or_404(Deposit, pk=pk)
        deposit_type = 'crypto'
    except:
        # Then try Paystack deposit
        d = get_object_or_404(LocalDeposit, pk=pk)
        deposit_type = 'paystack'
    
    # Check if deposit can be approved
    if deposit_type == 'crypto' and d.status != 'pending':
        messages.warning(request, "Crypto deposit is not pending.")
        return redirect('crypto:admin_deposits')
    elif deposit_type == 'paystack' and d.status != 'pending':
        messages.warning(request, "Paystack deposit is not pending.")
        return redirect('crypto:admin_deposits')
    
    profile = get_object_or_404(Profile, user=d.user)
    
    if deposit_type == 'crypto':
        # Handle crypto deposit approval
        profile.locked_balance += d.amount
        d.status = 'approved'
        d.approved_at = timezone.now()
        d.expires_at = d.expires_at or add_days(timezone.now(), LOCK_DAYS)
        d.save(update_fields=['status', 'approved_at', 'expires_at'])
        
        # Referral bonus for crypto deposit
        if d.referrer_id and d.referrer_id != d.user_id:
            bonus = d.amount * REFERRAL_PCT
            ref_profile = Profile.objects.filter(user_id=d.referrer_id).first()
            if ref_profile:
                ref_profile.locked_balance += bonus
                ref_profile.total_referrals += 1
                ref_profile.valid_referrals += 1
                ref_profile.referral_earnings += bonus
                ref_profile.save()
                Referral.objects.create(referrer_id=d.referrer_id, referee=d.user, bonus_amount=bonus, deposit=d)
                ref_profile.update_rank()
        
        messages.success(request, f"Crypto deposit {d.amount} approved.")
        
    else:
        # Handle Paystack deposit approval (manual approval for pending deposits)
        profile.locked_balance += d.amount_usdt
        d.status = 'paid'  # Change to 'paid' for consistency with webhook
        d.paid_at = timezone.now()
        d.save(update_fields=['status', 'paid_at'])
        
        # TODO: Implement referral logic for Paystack deposits if needed
        # For now, skip referral processing to avoid AttributeError
        
        messages.success(request, f"Paystack deposit {d.amount_usdt} approved.")
    
    # Update user rank
    profile.save(update_fields=['locked_balance'])
    profile.update_rank()
    
    return redirect('crypto:admin_deposits')

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_deposit_reject_view(request, pk):
    # Try to find deposit in both models
    try:
        # First try crypto deposit
        d = get_object_or_404(Deposit, pk=pk)
        deposit_type = 'crypto'
    except:
        # Then try Paystack deposit
        d = get_object_or_404(LocalDeposit, pk=pk)
        deposit_type = 'paystack'
    
    # Check if deposit can be rejected
    if deposit_type == 'crypto' and d.status != 'pending':
        messages.warning(request, "Crypto deposit is not pending.")
        return redirect('crypto:admin_deposits')
    elif deposit_type == 'paystack' and d.status != 'pending':
        messages.warning(request, "Paystack deposit is not pending.")
        return redirect('crypto:admin_deposits')
    
    if deposit_type == 'crypto':
        # Handle crypto deposit rejection
        d.status = 'rejected'
        d.approved_at = timezone.now()  # Use approved_at field for processing timestamp
        d.save(update_fields=['status', 'approved_at'])
        messages.success(request, f"Crypto deposit {d.amount} rejected.")
        
    else:
        # Handle Paystack deposit rejection
        d.status = 'failed'
        d.save(update_fields=['status'])
        messages.success(request, f"Paystack deposit {d.amount_usdt} rejected.")
    
    return redirect('crypto:admin_deposits')

# --- Withdrawals ---
@login_required(login_url='crypto:login')
@admin_required
def admin_withdrawals_view(request):
    status = request.GET.get('status')
    qs = Withdrawal.objects.select_related('user').order_by('-created_at')
    if status:
        qs = qs.filter(status=status)
    return render(request, 'crypto/admin/withdrawals.html', {'withdrawals': qs})

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_withdrawal_approve_view(request, pk):
    w = get_object_or_404(Withdrawal, pk=pk)
    if w.status not in ['pending', 'pending_admin_approval']:
        messages.warning(request, "Withdrawal is not pending.")
        return redirect('crypto:admin_withdrawals')
    w.status = 'approved'
    w.processed_at = timezone.now()
    w.save(update_fields=['status', 'processed_at'])
    messages.success(request, f"Withdrawal {w.amount} approved.")
    return redirect('crypto:admin_withdrawals')

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_withdrawal_reject_view(request, pk):
    w = get_object_or_404(Withdrawal, pk=pk)
    if w.status not in ['pending', 'pending_admin_approval']:
        messages.warning(request, "Withdrawal is not pending.")
        return redirect('crypto:admin_withdrawals')
    
    # Refund the amount back to user's withdrawable balance
    profile = get_object_or_404(Profile, user=w.user)
    profile.withdrawable_balance += w.amount
    profile.save(update_fields=['withdrawable_balance'])
    
    w.status = 'rejected'
    w.processed_at = timezone.now()
    w.save(update_fields=['status', 'processed_at'])
    
    messages.success(request, f"Withdrawal {w.amount} rejected and refunded.")
    return redirect('crypto:admin_withdrawals')

# --- Local Withdrawals ---
@login_required(login_url='crypto:login')
@admin_required
def admin_local_withdrawals_view(request):
    """Admin view to manage local withdrawal requests"""
    from crypto.models import LocalWithdrawal
    status = request.GET.get('status')
    qs = LocalWithdrawal.objects.select_related('user').order_by('-created_at')
    if status:
        qs = qs.filter(status=status)
    return render(request, 'crypto/admin/local_withdrawals.html', {'withdrawals': qs})

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_local_withdrawal_approve_view(request, pk):
    """Approve a local withdrawal and process via Paystack"""
    from crypto.models import LocalWithdrawal
    from crypto.paystack_service import PaystackService
    w = get_object_or_404(LocalWithdrawal, pk=pk)
    if w.status != 'pending_admin_approval':
        messages.warning(request, "Local withdrawal is not pending.")
        return redirect('crypto:admin_local_withdrawals')
    
    # Change status to approved first
    w.status = 'approved'
    w.processed_at = timezone.now()
    w.processed_by = request.user
    w.save(update_fields=['status', 'processed_at', 'processed_by'])
    
    # Process Paystack transfer automatically
    try:
        # Create transfer recipient
        recipient_response = PaystackService.create_transfer_recipient(
            account_number=w.account_number,
            bank_code=w.get_bank_code(),  # We'll need to add this method
            account_name=w.account_holder_name,
            description=f"Withdrawal for {w.user.email}"
        )
        
        if recipient_response.get('status'):
            recipient_code = recipient_response['data']['recipient_code']
            
            # Initiate transfer
            transfer_response = PaystackService.initiate_transfer(
                amount=float(w.amount_ngn),
                recipient_code=recipient_code,
                reason=f"CopyBloom FX Withdrawal - {w.user.email}"
            )
            
            if transfer_response.get('status'):
                w.paystack_transfer_reference = transfer_response['data']['reference']
                w.paystack_response = transfer_response
                w.save(update_fields=['paystack_transfer_reference', 'paystack_response'])
                
                messages.success(request, f"Local withdrawal of ${w.amount_usdt} approved and Paystack transfer initiated. Reference: {transfer_response['data']['reference']}")
            else:
                messages.error(request, f"Failed to initiate Paystack transfer: {transfer_response.get('message', 'Unknown error')}")
        else:
            messages.error(request, f"Failed to create Paystack recipient: {recipient_response.get('message', 'Unknown error')}")
            
    except Exception as e:
        messages.error(request, f"Error processing Paystack transfer: {str(e)}")
    
    return redirect('crypto:admin_local_withdrawals')

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_local_withdrawal_reject_view(request, pk):
    """Reject a local withdrawal and refund user balance"""
    from crypto.models import LocalWithdrawal
    w = get_object_or_404(LocalWithdrawal, pk=pk)
    if w.status != 'pending_admin_approval':
        messages.warning(request, "Local withdrawal is not pending.")
        return redirect('crypto:admin_local_withdrawals')
    
    # Refund the amount back to user's withdrawable balance
    profile = get_object_or_404(Profile, user=w.user)
    profile.withdrawable_balance += w.amount_usdt
    profile.save(update_fields=['withdrawable_balance'])
    
    # Update withdrawal status
    w.status = 'rejected'
    w.processed_at = timezone.now()
    w.save(update_fields=['status', 'processed_at'])
    
    messages.success(request, f"Local withdrawal of ${w.amount_usdt} rejected and refunded.")
    return redirect('crypto:admin_local_withdrawals')

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_local_withdrawal_complete_view(request, pk):
    """Mark a local withdrawal as completed after Paystack processing"""
    from crypto.models import LocalWithdrawal
    w = get_object_or_404(LocalWithdrawal, pk=pk)
    if w.status != 'approved':
        messages.warning(request, "Local withdrawal must be approved first.")
        return redirect('crypto:admin_local_withdrawals')
    
    # Mark as completed
    w.status = 'completed'
    w.completed_at = timezone.now()
    w.save(update_fields=['status', 'completed_at'])
    
    messages.success(request, f"Local withdrawal of ${w.amount_usdt} marked as completed.")
    return redirect('crypto:admin_local_withdrawals')

# --- Users ---
@login_required(login_url='crypto:login')
@admin_required
def admin_users_view(request):
    flt = request.GET.get('filter')
    qs = User.objects.filter(is_staff=False).order_by('-id')[:200]
    if flt == 'flagged':
        qs = qs.filter(is_flagged=True)
    elif flt == 'banned':
        qs = qs.filter(is_banned=True)
    return render(request, 'crypto/admin/users.html', {'users': qs})

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_user_flag_view(request, pk):
    u = get_object_or_404(User, pk=pk)
    if u.is_staff:
        messages.error(request, "Cannot flag admin.")
        return redirect('crypto:admin_users')
    u.is_flagged = True
    u.save(update_fields=['is_flagged'])
    messages.success(request, "User flagged.")
    return redirect('crypto:admin_users')

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_user_unflag_view(request, pk):
    u = get_object_or_404(User, pk=pk)
    u.is_flagged = False
    u.save(update_fields=['is_flagged'])
    messages.success(request, "User unflagged.")
    return redirect('crypto:admin_users')

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_user_ban_view(request, pk):
    u = get_object_or_404(User, pk=pk)
    if u.is_staff:
        messages.error(request, "Cannot ban admin.")
        return redirect('crypto:admin_users')
    u.is_banned = True
    u.is_flagged = True
    u.save(update_fields=['is_banned', 'is_flagged'])
    messages.success(request, "User banned.")
    return redirect('crypto:admin_users')

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_user_unban_view(request, pk):
    u = get_object_or_404(User, pk=pk)
    u.is_banned = False
    u.save(update_fields=['is_banned'])
    messages.success(request, "User unbanned.")
    return redirect('crypto:admin_users')

# --- Promo codes ---
@login_required(login_url='crypto:login')
@admin_required
def admin_promos_view(request):
    promos = PromoCode.objects.order_by('-created_at')
    redemptions = PromoRedemption.objects.select_related('user', 'promo_code').order_by('-created_at')[:100]
    form = PromoCodeCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Promo created.")
        return redirect('crypto:admin_promos')
    return render(request, 'crypto/admin/promos.html', {'promos': promos, 'redemptions': redemptions, 'form': form})

@login_required(login_url='crypto:login')
@admin_required
@require_POST
def admin_promo_toggle_view(request, pk):
    p = get_object_or_404(PromoCode, pk=pk)
    p.status = 'disabled' if p.status == 'active' else 'active'
    p.save(update_fields=['status'])
    messages.success(request, f"Promo {p.status}.")
    return redirect('crypto:admin_promos')
