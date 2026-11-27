"""Server-side checkout helpers for Stripe Checkout and PayPal Orders."""
import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _request_json(url, method='GET', payload=None, headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=data, headers={'Accept': 'application/json', **(headers or {})}, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode())
    except (HTTPError, URLError) as exc:
        detail = exc.read().decode(errors='replace') if isinstance(exc, HTTPError) else str(exc)
        raise ImproperlyConfigured(f'Payment provider request failed: {detail[:300]}') from exc


def create_stripe_checkout(payment, success_url, cancel_url):
    if not settings.STRIPE_SECRET_KEY:
        raise ImproperlyConfigured('Set STRIPE_SECRET_KEY in the deployment environment.')
    cents = int(payment.amount_usd * 100)
    fields = {
        'mode': 'payment',
        'success_url': success_url,
        'cancel_url': cancel_url,
        'customer_email': payment.customer.account.email,
        'client_reference_id': str(payment.pk),
        'metadata[payment_id]': str(payment.pk),
        'line_items[0][quantity]': '1',
        'line_items[0][price_data][currency]': 'usd',
        'line_items[0][price_data][unit_amount]': str(cents),
        'line_items[0][price_data][product_data][name]': payment.get_payment_type_display(),
    }
    token = base64.b64encode(f'{settings.STRIPE_SECRET_KEY}:'.encode()).decode()
    request = Request(
        'https://api.stripe.com/v1/checkout/sessions',
        data=urlencode(fields).encode(),
        headers={'Authorization': f'Basic {token}', 'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=20) as response:
            session = json.loads(response.read().decode())
    except (HTTPError, URLError) as exc:
        detail = exc.read().decode(errors='replace') if isinstance(exc, HTTPError) else str(exc)
        raise ImproperlyConfigured(f'Stripe Checkout request failed: {detail[:300]}') from exc
    payment.external_id = session['id']
    payment.checkout_url = session['url']
    payment.save(update_fields=['external_id', 'checkout_url'])
    return payment.checkout_url


def _paypal_base_url():
    return 'https://api-m.sandbox.paypal.com' if settings.PAYPAL_ENV == 'sandbox' else 'https://api-m.paypal.com'


def _paypal_access_token():
    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
        raise ImproperlyConfigured('Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in the deployment environment.')
    token = base64.b64encode(f'{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}'.encode()).decode()
    request = Request(
        f'{_paypal_base_url()}/v1/oauth2/token',
        data=b'grant_type=client_credentials',
        headers={'Authorization': f'Basic {token}', 'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())['access_token']


def create_paypal_order(payment, return_url, cancel_url):
    token = _paypal_access_token()
    result = _request_json(
        f'{_paypal_base_url()}/v2/checkout/orders',
        method='POST',
        payload={
            'intent': 'CAPTURE',
            'purchase_units': [{
                'reference_id': str(payment.pk),
                'custom_id': str(payment.pk),
                'description': payment.get_payment_type_display(),
                'amount': {'currency_code': 'USD', 'value': f'{payment.amount_usd:.2f}'},
            }],
            'application_context': {'return_url': return_url, 'cancel_url': cancel_url},
        },
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    )
    approval = next((link['href'] for link in result.get('links', []) if link.get('rel') == 'payer-action'), None)
    if not approval:
        approval = next((link['href'] for link in result.get('links', []) if link.get('rel') == 'approve'), None)
    if not approval:
        raise ImproperlyConfigured('PayPal did not return an approval link.')
    payment.external_id = result['id']
    payment.checkout_url = approval
    payment.save(update_fields=['external_id', 'checkout_url'])
    return payment.checkout_url


def capture_paypal_order(order_id):
    token = _paypal_access_token()
    return _request_json(
        f'{_paypal_base_url()}/v2/checkout/orders/{order_id}/capture',
        method='POST', payload={},
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    )
