# Vercel deployment preparation

Vercel detects this Django project directly from `manage.py` and `requirements.txt`; a custom `api/` wrapper or `vercel.json` is not needed.

## Before the first deployment

1. Push the project to the Git provider connected to Vercel and import it as a Django project.
2. Provision Neon PostgreSQL and add its pooled connection string as `DATABASE_URL` and its direct connection string as `DATABASE_URL_UNPOOLED` in Vercel. Use separate Neon branches for Preview and Production.
3. Add a unique `SECRET_KEY` and set `DEBUG=False` in Vercel. Set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` for the Vercel URL and any custom domain.
4. Add `CLOUDINARY_URL` from Cloudinary's API environment settings. The upload backend saves profile images as private assets and issues short-lived signed download URLs.
5. Configure email delivery with `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL`.
6. Configure Daraja credentials and set `MPESA_CALLBACK_URL` to the deployed HTTPS URL ending in `/payments/mpesa/callback/`. Start with sandbox credentials.
7. Vercel runs `scripts/vercel_migrate.py` during each build. It uses Neon's direct connection URL for migrations; make sure each Vercel environment points to the intended Neon branch.

## Member photos must use persistent storage

Uploaded profile images use the custom Cloudinary storage backend when `CLOUDINARY_URL` is configured. It stores originals as private Cloudinary assets and generates short-lived signed URLs. Set `CLOUDINARY_URL` in Vercel before accepting registrations. If importing existing member records, migrate their old local image files into Cloudinary and update the stored file names before switching traffic.

Static assets are collected from `STATIC_ROOT` and served by Vercel. Do not use SQLite for Vercel production data; this project now requires `DATABASE_URL` outside local debug mode.

## Chat infrastructure

When real-time chat is added, use a hosted realtime service or a separately managed WebSocket service. Store conversations and messages in PostgreSQL; do not rely on process memory or local files.
