# Production Deployment Guide

## Prerequisites
- Linux / Windows Server
- Python 3.10+
- MySQL 8.0+ / MariaDB
- Gunicorn WSGI Server

## Running with Gunicorn WSGI
```bash
gunicorn -c backend/gunicorn_conf.py backend.app:app
```

## Environment File Setup (`.env`)
```ini
FLASK_ENV=production
PORT=5000
SECRET_KEY=generate_a_random_32_byte_secret_key_here
DB_HOST=localhost
DB_PORT=3306
DB_NAME=crm_database
DB_USER=crm_user
DB_PASSWORD=strong_password_here
```
