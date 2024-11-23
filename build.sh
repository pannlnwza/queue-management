#!/bin/bash

# Ensure pip is up-to-date
python3 -m pip install --upgrade pip

# Install dependencies from requirements.txt
pip3 install -r requirements.txt

# Install Tailwind CSS and build assets (if applicable)
python3 manage.py tailwind install
python3 manage.py tailwind build

# Collect static files
python3 manage.py collectstatic --noinput

# Make migrations and apply them
python3 manage.py makemigrations --noinput
python3 manage.py migrate --noinput