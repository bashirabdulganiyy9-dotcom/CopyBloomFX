# =============================================================================
# crypto/utils.py
# =============================================================================

import random
import string
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

NETWORKS = ['USDT BEP20', 'USDT ERC20', 'Solana', 'Ethereum', 'BNB SmartChain']

WALLETS = {
    'USDT BEP20': [
        '0x330901bc8ccf6476cb6a007306a5d2956c62332f',
        '0x4ec0c6d5b98f9fc47a2a99f57e7e4e8e92682c2f',
        '0x04f3a91776e43bb59c71bb2afaf0a0d858d7ffa0',
        '0xe5e310431c70a968b72b2824a71ec17224f7cd36',
        '0xd581d94e502ef97fc86b6d7bf1cba75a2c648b68',
        '0x7b578382aad4f75eeb9b08562f4949ef338c3ea9',
        '0x04c6e95e6401e1be9ab6e1c6dfaaebfeb9c9aaa6',
        '0xffd403586721ed290a44789dfc6cdb3fb97d4fd8',
        '0x2031fe72f90f288402d6cf314465e9b9dc9ed5f9',
        '0xdf86438b45043cac8322ab640c3b469d6e0cf957',
        '0x2c4065c01719234225320ca06c4601bc804eba0c',
        '0x305744150872cd3d6e4b1dae5a63d021d1ea4446',
        '0xed6599dbb67c3a19718a6d28d8790a31519d399b',
        '0x4748dd0ce03b06ee02e6a5df4367e4c9e4c4b862',
        '0xd480edb456756967705d2e26dbf184445d7c0938',
        '0xea58f94a7cc15c7889790a1a18c239ea72a6e547',
        '0xa610e35baaa56950fd0de26dd3d4b1b101a350af',
        '0x31514d9fc3dc02b53bdd093346fd2c4e7b36997c',
        '0x636ab4ec55961f8ca0ed418fa1481f3ddf090704'
        '0xabaa1040a2d07fa7a9996b71a9c8ba7362191cbc'
    ],
    'USDT ERC20': [
        '0x330901Bc8CCf6476CB6a007306a5d2956c62332F',
        '0x4ec0c6d5b98f9fc47a2a99f57e7e4e8e92682c2f',
        '0x04f3a91776e43bb59c71bb2afaf0a0d858d7ffa0',
        '0xe5e310431c70a968b72b2824a71ec17224f7cd36',
        '0xd581d94e502ef97fc86b6d7bf1cba75a2c648b68',
        '0x7b578382aad4f75eeb9b08562f4949ef338c3ea9',
        '0x04c6e95e6401e1be9ab6e1c6dfaaebfeb9c9aaa6',
        '0xffd403586721ed290a44789dfc6cdb3fb97d4fd8',
        '0x2031fe72f90f288402d6cf314465e9b9dc9ed5f9',
        '0xdf86438b45043cac8322ab640c3b469d6e0cf957',
        '0x2c4065c01719234225320ca06c4601bc804eba0c',
        '0x305744150872cd3d6e4b1dae5a63d021d1ea4446',
        '0xed6599dbb67c3a19718a6d28d8790a31519d399b',
        '0x4748dd0ce03b06ee02e6a5df4367e4c9e4c4b862',
        '0xd480edb456756967705d2e26dbf184445d7c0938',
        '0xea58f94a7cc15c7889790a1a18c239ea72a6e547',
        '0xa610e35baaa56950fd0de26dd3d4b1b101a350af',
        '0x31514d9fc3dc02b53bdd093346fd2c4e7b36997c',
        '0x636ab4ec55961f8ca0ed418fa1481f3ddf090704'
        '0xabaa1040a2d07fa7a9996b71a9c8ba7362191cbc'
    ],
    'Solana': [
        '2nGvFch9BGccSe3Xi8Pj7YuMti17dtWBaaeEJJrHoyhh',
        '8gB7aMRedkJ3qzT6vpdw4nUHCzP2dgMUrTf3dP7amrLR',
        'CuJNKvLXEKTeVXd9JxdWAovRRneVYuyFtdgXTvMps1nx',
        '8QpPjcp6AYuxx7t5B8Zc1vnCnux52r25KUkWsQzSunUA',
        'gb3BDYKUUekLjhJeVD9ymEjM1ioaDZtoofqpnQg9QQL',
        'Ex6TiDeoZ259uF9eL25gM1RaWWGpH1Y1r4pboacbbtve',
        'AZ2H2DJyFA6j9XkzGkxjxAWVieEhAuzf6pL4yhtJScbD',
        'G3Jz8CbE9faNFntV3axDcp8ysZzaGnabaJ8TwdDCJj2q',
        'E7p8BKAYHEae3gT1WDgJGEFowvMw2ct1TRQCJRNuNoS7',
        '4bYjmHk4d31MwuBP46WbnkKQ5A8v2qcs6mmLN3c6iaqM',
        'Gf7PaeEKzWKNBRavhT3Naq3g4vjt1xFRrpUYRrGo2ExR',
        '5Z8sZL7nAwzRGV6WVn4u92uWCmvowaEEtKpoQ6hpn7yE',
        'EJBWbYWmrpF82r5ecx2TAD1HYhdPBLXWDARhQEp67htk',
        'J6vE7JWrrwz5ohaaXKj7ip4LCje6bqXFLLk1oYsxEzVm',
        'BVyF6raJJ9ZqcSKZSTGcRxkYyxhZSALjas1DqX9tGktN',
        '915CCxqqGuByF9bm28WDCH3SnSHKAPgZAQ1743sxFWHi',
        'FCPVJPTkGp7r4MCtGS42ZjUSEHsUrcmwujBneAiVXAv9',
        'J5y2QkNGPi7r4YAxEwLR1CQzpak9DNAMhKzywQE2mbc1',
        'E415hckrRyzkHxCYBNbddLCT2hBhPYogEjnhZdhQ8ky',
        '4JVxpWHGQ3BZ9Qib2zrKGbdip5QEhYrMGZzR8U3tZq3x'
    ],
    'Ethereum': [
        '0x330901bc8ccf6476cb6a007306a5d2956c62332f',
        '0x4ec0c6d5b98f9fc47a2a99f57e7e4e8e92682c2f',
        '0x04f3a91776e43bb59c71bb2afaf0a0d858d7ffa0',
        '0xe5e310431c70a968b72b2824a71ec17224f7cd36',
        '0xd581d94e502ef97fc86b6d7bf1cba75a2c648b68',
        '0x7b578382aad4f75eeb9b08562f4949ef338c3ea9',
        '0x04c6e95e6401e1be9ab6e1c6dfaaebfeb9c9aaa6',
        '0xffd403586721ed290a44789dfc6cdb3fb97d4fd8',
        '0x2031fe72f90f288402d6cf314465e9b9dc9ed5f9',
        '0xdf86438b45043cac8322ab640c3b469d6e0cf957',
        '0x2c4065c01719234225320ca06c4601bc804eba0c',
        '0x305744150872cd3d6e4b1dae5a63d021d1ea4446',
        '0xed6599dbb67c3a19718a6d28d8790a31519d399b',
        '0x4748dd0ce03b06ee02e6a5df4367e4c9e4c4b862',
        '0xd480edb456756967705d2e26dbf184445d7c0938',
        '0xea58f94a7cc15c7889790a1a18c239ea72a6e547',
        '0xa610e35baaa56950fd0de26dd3d4b1b101a350af',
        '0x31514d9fc3dc02b53bdd093346fd2c4e7b36997c',
        '0x636ab4ec55961f8ca0ed418fa1481f3ddf090704',
        '0xabaa1040a2d07fa7a9996b71a9c8ba7362191cbc'
    ],
    'BNB SmartChain': [
        '0x330901bc8ccf6476cb6a007306a5d2956c62332f',
        '0x4ec0c6d5b98f9fc47a2a99f57e7e4e8e92682c2f',
        '0x04f3a91776e43bb59c71bb2afaf0a0d858d7ffa0',
        '0xe5e310431c70a968b72b2824a71ec17224f7cd36',
        '0xd581d94e502ef97fc86b6d7bf1cba75a2c648b68',
        '0x7b578382aad4f75eeb9b08562f4949ef338c3ea9',
        '0x04c6e95e6401e1be9ab6e1c6dfaaebfeb9c9aaa6',
        '0xffd403586721ed290a44789dfc6cdb3fb97d4fd8',
        '0x2031fe72f90f288402d6cf314465e9b9dc9ed5f9',
        '0xdf86438b45043cac8322ab640c3b469d6e0cf957',
        '0x2c4065c01719234225320ca06c4601bc804eba0c',
        '0x305744150872cd3d6e4b1dae5a63d021d1ea4446',
        '0xed6599dbb67c3a19718a6d28d8790a31519d399b',
        '0x4748dd0ce03b06ee02e6a5df4367e4c9e4c4b862',
        '0xd480edb456756967705d2e26dbf184445d7c0938',
        '0xea58f94a7cc15c7889790a1a18c239ea72a6e547',
        '0xa610e35baaa56950fd0de26dd3d4b1b101a350af',
        '0x31514d9fc3dc02b53bdd093346fd2c4e7b36997c',
        '0x636ab4ec55961f8ca0ed418fa1481f3ddf090704',
        '0xabaa1040a2d07fa7a9996b71a9c8ba7362191cbc'
    ],
}

PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT']

MIN_DEPOSIT = Decimal('7.5')
MIN_WITHDRAWAL = Decimal('2.5')
DAILY_REWARD = Decimal('0.10')
REFERRAL_PCT = Decimal('0.08')
LOCK_DAYS = 30


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def get_random_wallet(network):
    lst = WALLETS.get(network, WALLETS['USDT BEP20'])
    return random.choice(lst)


def get_available_wallet(network, user_id=None):
    """
    Get an available wallet address that's not currently assigned to another user.
    Wallets are assigned for 5 minutes only.
    """
    from django.core.cache import cache
    from django.utils import timezone
    import json
    
    # Get all wallets for this network
    all_wallets = WALLETS.get(network, WALLETS['USDT BEP20'])
    
    # Get current wallet assignments from cache
    assignments = cache.get('wallet_assignments', {})
    
    # Clean up expired assignments (older than 5 minutes)
    current_time = timezone.now().timestamp()
    cleaned_assignments = {}
    
    for wallet, assignment_data in assignments.items():
        assignment_time = assignment_data.get('timestamp', 0)
        if current_time - assignment_time < 300:  # 5 minutes = 300 seconds
            cleaned_assignments[wallet] = assignment_data
    
    # Update cache with cleaned assignments
    cache.set('wallet_assignments', cleaned_assignments, 300)  # Cache for 5 minutes
    
    # Find available wallets
    available_wallets = []
    for wallet in all_wallets:
        if wallet not in cleaned_assignments:
            available_wallets.append(wallet)
        elif user_id and cleaned_assignments[wallet].get('user_id') == user_id:
            # User can reuse their own assigned wallet
            available_wallets.append(wallet)
    
    # If no available wallets, wait for one to expire
    if not available_wallets:
        # Find the oldest assignment and wait for it to expire
        oldest_wallet = min(cleaned_assignments.keys(), 
                          key=lambda w: cleaned_assignments[w].get('timestamp', float('inf')))
        oldest_time = cleaned_assignments[oldest_wallet].get('timestamp', 0)
        time_remaining = 300 - (current_time - oldest_time)
        
        if time_remaining > 0:
            # Return None to indicate no wallet available
            return None, time_remaining
    
    # Assign a random available wallet
    selected_wallet = random.choice(available_wallets)
    
    # Record the assignment
    cleaned_assignments[selected_wallet] = {
        'user_id': user_id,
        'network': network,
        'timestamp': current_time
    }
    
    # Update cache
    cache.set('wallet_assignments', cleaned_assignments, 300)
    
    return selected_wallet, None


def generate_referral_code():
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(8))


def add_days(dt, n):
    return dt + timedelta(days=n)


def is_same_day(a, b):
    if not a or not b:
        return False
    return a.date() == b.date() if hasattr(a, 'date') else timezone.localtime(a).date() == timezone.localtime(b).date()
