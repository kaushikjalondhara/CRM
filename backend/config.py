import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file at project root, or backend/.env if present
root_env = BASE_DIR / '.env'
backend_env = BACKEND_DIR / '.env'

if root_env.exists():
    load_dotenv(dotenv_path=root_env)
elif backend_env.exists():
    load_dotenv(dotenv_path=backend_env)
else:
    load_dotenv()


class Config:
    """Base application configuration."""

    # Flask Core Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "default_crm_secret_key_dev_mode_only")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    PORT = int(os.getenv("PORT", 5000))
    HOST = os.getenv("HOST", "127.0.0.1")

    # MySQL Database Settings
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    DB_NAME = os.getenv("DB_NAME", "crm_database")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # Uploads Configuration
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    CUSTOMER_DOCUMENTS_FOLDER = os.path.join(UPLOAD_FOLDER, "customer_documents")
    PROFILE_IMAGES_FOLDER = os.path.join(UPLOAD_FOLDER, "profile_images")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max file upload size

    # CORS Settings
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    # SMTP / Email Configuration
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "")

    # JWT Settings
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", 60))
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}
