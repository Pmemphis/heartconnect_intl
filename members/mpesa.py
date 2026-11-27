"""Minimal Daraja STK Push client. Keep credentials in environment variables."""
import base64
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen

from django.core.exceptions import ImproperlyConfigured


def _post_json(url, payload, headers=None):
    request = Request(url, data=json.dumps(payload).encode(), headers={
        'Content-Type': 'application/json', **(headers or {}),
    })
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())


def _get_json(url, headers=None):
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())


def initiate_stk_push(phone, account_reference):
    key = os.environ.get('MPESA_CONSUMER_KEY')
    secret = os.environ.get('MPESA_CONSUMER_SECRET')
    shortcode = os.environ.get('MPESA_SHORTCODE')
    passkey = os.environ.get('MPESA_PASSKEY')
    callback = os.environ.get('MPESA_CALLBACK_URL')
    if not all((key, secret, shortcode, passkey, callback)):
        raise ImproperlyConfigured('M-Pesa Daraja credentials and public callback URL must be configured.')

    base = 'https://sandbox.safaricom.co.ke' if os.environ.get('MPESA_ENV', 'sandbox') == 'sandbox' else 'https://api.safaricom.co.ke'
    auth = base64.b64encode(f'{key}:{secret}'.encode()).decode()
    token_data = _get_json(f'{base}/oauth/v1/generate?grant_type=client_credentials', {'Authorization': f'Basic {auth}'})
    timestamp = datetime.now(ZoneInfo('Africa/Nairobi')).strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(f'{shortcode}{passkey}{timestamp}'.encode()).decode()
    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': 130,
        'PartyA': phone,
        'PartyB': shortcode,
        'PhoneNumber': phone,
        'CallBackURL': callback,
        'AccountReference': account_reference[:12],
        'TransactionDesc': 'HeartConnect one-time membership',
    }
    return _post_json(f'{base}/mpesa/stkpush/v1/processrequest', payload, {
        'Authorization': f"Bearer {token_data['access_token']}"
    })
