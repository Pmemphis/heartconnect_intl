# Vercel deployment and paid services

Vercel detects the Django project from `manage.py` and `requirements.txt`. The Vercel build script runs database migrations from `scripts/vercel_migrate.py`.

## Environment variables

Keep all secrets in Vercel Project Settings → Environment Variables. Do not commit `.env` or paste credentials into chat.

Required base settings:

- `SECRET_KEY`, `DEBUG=False`, `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, and `CLOUDINARY_URL`.
- `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` for the Vercel domain and any custom domain.
- Email SMTP variables to deliver account and assignment notices.

Earner M-Pesa joining fee:

- `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_SHORTCODE`, `MPESA_PASSKEY`, `MPESA_CALLBACK_URL`, and `MPESA_ENV`.
- Set `MPESA_TRANSACTION_TYPE=CustomerBuyGoodsOnline` for a Till, or `CustomerPayBillOnline` for a Paybill.
- Set `PROVIDER_JOINING_FEE_KES` to the KES amount you choose for the $3.99 fee. Daraja STK Push charges integer KES; update this value when your conversion rate changes.
- Set `PAYOUT_USD_KES_RATE` to the USD-to-KES rate the team will use for M-Pesa and Airtel payouts. The app freezes the rate and rounded KES amount into each payout record when a booking is assigned. PayPal payouts remain in USD.

Foreign customer checkout:

- `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`. Configure a Stripe webhook at `/payments/stripe/webhook/` for `checkout.session.completed` and `checkout.session.async_payment_succeeded`.
- `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and `PAYPAL_ENV`. Use `sandbox` while testing and `live` for the production API.
- The app marks Stripe payments paid only after a signature-verified webhook. PayPal payments are captured and verified server-side after the payer returns.

## Service operations

- Customers pay the $8.50 joining fee, then pay separately for each booking.
- Earner rates are $3–$5 per chat hour and $15–$25 per two-hour Kiswahili lesson. The current setup pays the same amount to the earner as the customer’s service price.
- A paid booking appears in Django Admin. Changing it to **Assigned** creates a payout record using the earner’s chosen method and destination. Admin staff must send the payout and mark the record **Paid** with its transfer reference; M-Pesa, Airtel Money, and PayPal payouts are not sent automatically by this app yet.
- For a lesson, staff add the Google Meet (or other voice/video) URL in the booking before assigning it. The app stores and shares the link; it does not create meetings through the Google API.
- Bookings and chat schedules use East Africa Time.

## Persistent files and data

Uploaded profile photos use the private Cloudinary storage backend. Set `CLOUDINARY_URL` before accepting registrations. Vercel filesystems are ephemeral; use Neon PostgreSQL for application data and do not use SQLite in production.
