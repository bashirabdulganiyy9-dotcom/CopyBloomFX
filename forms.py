# =============================================================================
# crypto/forms.py
# =============================================================================

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import Profile, Deposit, Withdrawal, PromoCode

User = get_user_model()

NETWORKS = [
    ('USDT BEP20', 'USDT BEP20'),
    ('USDT ERC20', 'USDT ERC20'),
    ('Solana', 'Solana'),
    ('Ethereum', 'Ethereum'),
    ('BNB SmartChain', 'BNB SmartChain'),
]

MIN_DEPOSIT = 7
MIN_WITHDRAWAL = 2.5


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Email (optional)'


class LoginForm(AuthenticationForm):
    pass


class ProfileUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=False, label='Email (fallback)')
    profile_picture = forms.ImageField(
        required=False,
        label='Profile Picture',
        widget=forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control'})
    )

    class Meta:
        model = Profile
        fields = ('profile_picture',)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['email'].initial = self.user.email or ''

    def clean_profile_picture(self):
        """Validate the uploaded image and save it"""
        profile_picture = self.cleaned_data.get('profile_picture')
        
        if profile_picture:
            # Check file size (max 5MB)
            if profile_picture.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Image size should not exceed 5MB.')
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if profile_picture.content_type not in allowed_types:
                raise forms.ValidationError(
                    'Invalid file type. Please upload JPEG, PNG, GIF, or WebP images.'
                )
            
            # Check image dimensions (max 2000x2000)
            try:
                from PIL import Image
                img = Image.open(profile_picture)
                if img.width > 2000 or img.height > 2000:
                    raise forms.ValidationError(
                        'Image dimensions should not exceed 2000x2000 pixels.'
                    )
            except Exception:
                pass  # If PIL is not available or image can't be processed
        
        return profile_picture

    def save(self, commit=True):
        import os
        import uuid
        from django.conf import settings
        
        inst = super().save(commit=False)
        
        # Handle file upload manually
        profile_picture = self.cleaned_data.get('profile_picture')
        
        if profile_picture:
            # Generate unique filename
            ext = profile_picture.name.split('.')[-1]
            filename = f"{uuid.uuid4()}.{ext}"
            
            # Create upload directory if it doesn't exist
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'profile_pics')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, 'wb') as f:
                for chunk in profile_picture.chunks():
                    f.write(chunk)
            
            # Save the relative path in the TextField
            inst.profile_picture = f'profile_pics/{filename}'
        
        if commit:
            inst.save()
            
        # Update user email
        if self.user and 'email' in self.cleaned_data:
            self.user.email = self.cleaned_data.get('email', '') or ''
            self.user.save()
            
        return inst


class DepositForm(forms.Form):
    amount = forms.DecimalField(min_value=MIN_DEPOSIT, max_digits=18, decimal_places=2, label='Amount ($)')
    network = forms.ChoiceField(choices=NETWORKS, label='Network')
    referrer_code = forms.CharField(required=False, max_length=16, label='Referrer code (optional)')


class WithdrawalForm(forms.Form):
    amount = forms.DecimalField(min_value=2.5, max_digits=18, decimal_places=2, label='Amount ($)')
    network = forms.ChoiceField(choices=NETWORKS, label='Network')
    wallet_address = forms.CharField(required=False, max_length=128, label='Wallet address')


class PromoRedeemForm(forms.Form):
    code = forms.CharField(max_length=32, label='Promo code', widget=forms.TextInput(attrs={'placeholder': 'Code'}))


class LocalDepositForm(forms.Form):
    """Form for local deposit with Paystack"""
    amount_usdt = forms.DecimalField(
        min_value=Decimal('7.5'),
        max_digits=18,
        decimal_places=2,
        label='Amount (USDT)',
        widget=forms.NumberInput(attrs={'placeholder': 'Enter amount in USDT'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amount_usdt'].widget.attrs.update({'class': 'form-control'})
    
    def clean_amount_usdt(self):
        amount = self.cleaned_data.get('amount_usdt')
        if amount <= 0:
            raise forms.ValidationError("Amount must be greater than 0")
        return amount


class LocalWithdrawalForm(forms.Form):
    """Form for local withdrawal with bank details"""
    amount_usdt = forms.DecimalField(
        min_value=Decimal('2.5'),
        max_digits=18,
        decimal_places=2,
        label='Amount (USDT)',
        widget=forms.NumberInput(attrs={'placeholder': 'Enter amount in USDT'})
    )
    
    bank_name = forms.CharField(
        max_length=100,
        label='Bank Name',
        widget=forms.TextInput(attrs={'placeholder': 'e.g., Access Bank, GTBank'})
    )
    
    account_number = forms.CharField(
        max_length=20,
        label='Account Number',
        widget=forms.TextInput(attrs={'placeholder': 'Enter 10-digit account number'})
    )
    
    account_holder_name = forms.CharField(
        max_length=100,
        label='Account Holder Name',
        widget=forms.TextInput(attrs={'placeholder': 'Name as it appears on bank account'})
    )
    
    confirm_details = forms.BooleanField(
        label='I confirm that all bank details are correct. I understand that withdrawals sent to wrong accounts are irreversible.',
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Add form-control class to all fields
        for field_name, field in self.fields.items():
            if field_name != 'confirm_details':
                field.widget.attrs.update({'class': 'form-control'})
    
    def clean_amount_usdt(self):
        amount = self.cleaned_data.get('amount_usdt')
        if amount <= 0:
            raise forms.ValidationError("Amount must be greater than 0")
        
        # Check if user has sufficient balance
        if self.user and self.user.profile:
            if amount > self.user.profile.withdrawable_balance:
                raise forms.ValidationError(f"Insufficient balance. Available: ${self.user.profile.withdrawable_balance}")
        
        return amount
    
    def clean_account_number(self):
        account_number = self.cleaned_data.get('account_number')
        if not account_number.isdigit():
            raise forms.ValidationError("Account number must contain only digits")
        if len(account_number) != 10:
            raise forms.ValidationError("Account number must be exactly 10 digits")
        return account_number


# Admin forms
class PromoCodeCreateForm(forms.ModelForm):
    class Meta:
        model = PromoCode
        fields = ('code', 'bonus_min', 'bonus_max', 'expiration', 'usage_limit', 'status')
        widgets = {
            'expiration': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'usage_limit': forms.NumberInput(attrs={'placeholder': '∞'}),
        }


class AdminPasswordResetForm(forms.Form):
    user_id = forms.IntegerField(widget=forms.HiddenInput())
    new_password = forms.CharField(min_length=4, widget=forms.PasswordInput(), label='New password')
