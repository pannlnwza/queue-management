#!/bin/bash
pip install -r requirements.txt

# Install and build Tailwind styles
python manage.py tailwind install
python manage.py tailwind build

# Collect static files
python manage.py collectstatic --noinput

# Apply database migrations
python manage.py makemigrations --noinput
python manage.py migrate --noinput