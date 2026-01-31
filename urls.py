# =============================================================================
# crypto/urls.py
# =============================================================================

from django.urls import path
from . import views

app_name = 'crypto'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('finance/', views.finance_view, name='finance'),
    path('profile/', views.profile_view, name='profile'),
    path('contact/', views.contact_view, name='contact'),
    path('local-deposit/', views.local_deposit_view, name='local_deposit'),
    path('local-withdrawal/', views.local_withdrawal_view, name='local_withdrawal'),
    path('paystack/callback/', views.paystack_callback_view, name='paystack_callback'),
    path('paystack/verify/', views.paystack_verify_view, name='paystack_verify'),
    path('referral/', views.referral_view, name='referral'),
    path('daily-reward/', views.daily_reward_view, name='daily_reward'),
    path('copy-trade-simulate/', views.copy_trade_simulate_view, name='copy_trade_simulate'),
    path('check-deposit-status/', views.check_deposit_status_view, name='check_deposit_status'),
    path('clear-deposit-session/', views.clear_deposit_session_view, name='clear_deposit_session'),
    path('test-webhook/', views.test_webhook_view, name='test_webhook'),
    path('webhook-status/', views.webhook_status_view, name='webhook_status'),
    path('test-paystack/', views.test_paystack_view, name='test_paystack'),
    path('public-test-paystack/', views.public_test_paystack_view, name='public_test_paystack'),
    path('paystack-test/', views.paystack_test_page_view, name='paystack_test_page'),
    # Admin
    path('admin/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin/deposits/', views.admin_deposits_view, name='admin_deposits'),
    path('admin/deposits/<int:pk>/approve/', views.admin_deposit_approve_view, name='admin_deposit_approve'),
    path('admin/deposits/<int:pk>/reject/', views.admin_deposit_reject_view, name='admin_deposit_reject'),
    path('admin/withdrawals/', views.admin_withdrawals_view, name='admin_withdrawals'),
    path('admin/withdrawals/<int:pk>/approve/', views.admin_withdrawal_approve_view, name='admin_withdrawal_approve'),
    path('admin/withdrawals/<int:pk>/reject/', views.admin_withdrawal_reject_view, name='admin_withdrawal_reject'),
    path('admin/local-withdrawals/', views.admin_local_withdrawals_view, name='admin_local_withdrawals'),
    path('admin/local-withdrawals/<int:pk>/approve/', views.admin_local_withdrawal_approve_view, name='admin_local_withdrawal_approve'),
    path('admin/local-withdrawals/<int:pk>/reject/', views.admin_local_withdrawal_reject_view, name='admin_local_withdrawal_reject'),
    path('admin/local-withdrawals/<int:pk>/complete/', views.admin_local_withdrawal_complete_view, name='admin_local_withdrawal_complete'),
    path('admin/promos/', views.admin_promos_view, name='admin_promos'),
    path('admin/promos/<int:pk>/toggle/', views.admin_promo_toggle_view, name='admin_promo_toggle'),
    path('admin/users/', views.admin_users_view, name='admin_users'),
    path('admin/users/<int:pk>/flag/', views.admin_user_flag_view, name='admin_user_flag'),
    path('admin/users/<int:pk>/unflag/', views.admin_user_unflag_view, name='admin_user_unflag'),
    path('admin/users/<int:pk>/ban/', views.admin_user_ban_view, name='admin_user_ban'),
    path('admin/users/<int:pk>/unban/', views.admin_user_unban_view, name='admin_user_unban'),
]
