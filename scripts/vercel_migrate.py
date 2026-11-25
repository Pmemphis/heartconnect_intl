"""Run migrations against Neon's direct URL during Vercel builds."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


database_url = os.environ.get('DATABASE_URL_UNPOOLED') or os.environ.get('DATABASE_URL')
if not database_url:
    raise RuntimeError('Set DATABASE_URL_UNPOOLED or DATABASE_URL in the Vercel environment.')

os.environ['DATABASE_URL'] = database_url
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from django.core.management import execute_from_command_line

execute_from_command_line(['manage.py', 'migrate', '--noinput'])
