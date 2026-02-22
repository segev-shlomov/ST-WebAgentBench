# websites domain
import os
import logging

logger = logging.getLogger(__name__)

REDDIT = os.environ.get("REDDIT", "")
SHOPPING = os.environ.get("SHOPPING", "")
SHOPPING_ADMIN = os.environ.get("SHOPPING_ADMIN", "")
GITLAB = os.environ.get("GITLAB", "")
WIKIPEDIA = os.environ.get("WIKIPEDIA", "")
MAP = os.environ.get("MAP", "")
HOMEPAGE = os.environ.get("HOMEPAGE", "")
IPA = os.environ.get("IPA_HOME", "")
SUITECRM = os.environ.get("SUITECRM", "")

# Validate that the required service URLs are configured
_missing = []
if not GITLAB:
    _missing.append("GITLAB")
if not SHOPPING_ADMIN:
    _missing.append("SHOPPING_ADMIN")
if not SUITECRM:
    _missing.append("SUITECRM")
if _missing:
    logger.warning(
        f"Required environment variables not set: {', '.join(_missing)}. "
        f"Copy .env.example to .env and fill in the URLs for your web app instances."
    )

ACCOUNTS = {
    "reddit": {"username": "MarvelsGrantMan136", "password": "test1234"},
    "gitlab": {"username": "byteblaze", "password": "hello1234"},
    "suitecrm": {"username":"user","password":"bitnami"},
    "shopping": {
        "username": "emma.lopez@gmail.com",
        "password": "Password.123",
    },
    "shopping_admin": {"username": "admin", "password": "admin1234"},
    "shopping_site_admin": {"username": "admin", "password": "admin1234"},
}

URL_MAPPINGS = {
    REDDIT: "http://reddit.com",
    SHOPPING: "http://onestopmarket.com",
    SHOPPING_ADMIN: "http://luma.com/admin",
    GITLAB: "http://gitlab.com",
    WIKIPEDIA: "http://wikipedia.org",
    MAP: "http://openstreetmap.org",
    HOMEPAGE: "http://homepage.com",
}
