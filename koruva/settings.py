import sys
from contextlib import suppress
from email.utils import parseaddr
from pathlib import Path

import sentry_sdk
from environs import Env
from marshmallow.validate import Email, OneOf
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

with suppress(ImportError):
    import django_stubs_ext

    # Monkeypatching Django, so stubs will work for all generics,
    # see: https://github.com/typeddjango/django-stubs
    django_stubs_ext.monkeypatch()

# 0. Setup
# --------------------------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

APPS_DIR = BASE_DIR / "koruva"

env = Env()
env.read_env(Path(BASE_DIR, ".env").as_posix())

# We should strive to only have two possible runtime scenarios: either `DEBUG`
# is True or it is False. `DEBUG` should be only true in development, and
# False when deployed, whether it's a production environment.
DEBUG = env.bool("DEBUG", default=False)

PROD = not DEBUG

# 1. Django Core Settings
# -----------------------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/4.0/ref/settings/

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS", default=["*"] if not PROD else ["localhost"], subcast=str
)

ASGI_APPLICATION = "koruva.asgi.application"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}
if PROD:
    # https://grantjenks.com/docs/diskcache/tutorial.html#djangocache
    CACHES["default"] = {
        "BACKEND": "diskcache.DjangoCache",
        "LOCATION": env.str("CACHE_LOCATION", default=".diskcache"),
        "TIMEOUT": 300,
        "SHARDS": 8,
        "DATABASE_TIMEOUT": 0.010,  # 10 milliseconds
        "OPTIONS": {"size_limit": 2**30},  # 1 gigabyte
    }

CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=PROD)

DATABASES = {
    "default": env.dj_db_url("DATABASE_URL", default="sqlite:///db.sqlite3"),
    "tasks_db": env.dj_db_url(
        "TASKS_DATABASE_URL", default="sqlite:///tasks_db.sqlite3"
    ),
}
# https://docs.djangoproject.com/en/dev/ref/databases/#database-is-locked-errors
# DATABASES["tasks_db"]["OPTIONS"]["timeout"] = 5
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    # https://gcollazo.com/optimal-sqlite-settings-for-django/
    DATABASES["default"]["OPTIONS"] = {
        "transaction_mode": "IMMEDIATE",
        "init_command": (
            "PRAGMA foreign_keys=ON;"
            "PRAGMA journal_mode = WAL;"
            "PRAGMA synchronous = NORMAL;"
            "PRAGMA busy_timeout = 5000;"
            "PRAGMA temp_store = MEMORY;"
            "PRAGMA mmap_size = 134217728;"
            "PRAGMA journal_size_limit = 67108864;"
            "PRAGMA cache_size = 2000;"
        ),
    }
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"]["ATOMIC_REQUESTS"] = True
    if PROD and env.bool("ENABLE_PG_CONN_POOL", default=False):
        DATABASES["default"]["OPTIONS"] = {
            "pool": {
                "min_size": env.int("PG_CONN_POOL_MIN_SIZE", default=2),
                "max_size": env.int("PG_CONN_POOL_MAX_SIZE", default=4),
                "timeout": env.int("PG_CONN_POOL_TIMEOUT", default=10),
            }
        }

DATABASE_ROUTERS = ["koruva.core.db_routers.DBTaskRouter"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DEFAULT_FROM_EMAIL = env.str(
    "DEFAULT_FROM_EMAIL",
    default="tobidegnon@proton.me",
    validate=lambda v: Email()(parseaddr(v)[1]),
)

EMAIL_BACKEND = (
    "anymail.backends.amazon_ses.EmailBackend"
    if PROD
    else "django.core.mail.backends.console.EmailBackend"
)

FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.forms",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "crispy_forms",
    "crispy_tailwind",
    "django_htmx",
    "django_litestream",
    "django_tailwind_cli",
    "django_tasks",
    "django_tasks.backends.database",
    "falco",
    "health_check",
    "health_check.cache",
    "health_check.contrib.migrations",
    "health_check.db",
    "health_check.storage",
    "heroicons",
    "template_partials",
    "unique_user_email",
]

LOCAL_APPS = [
    "koruva.core",
]

if not PROD:
    # Development only apps
    THIRD_PARTY_APPS = [
        "django_extensions",
        "debug_toolbar",
        "whitenoise.runserver_nostatic",
        "django_browser_reload",
        "django_fastdev",
        # "django_watchfiles", # currently not working when html files are changed
        *THIRD_PARTY_APPS,
    ]

INSTALLED_APPS = LOCAL_APPS + THIRD_PARTY_APPS + DJANGO_APPS

if not PROD:
    INTERNAL_IPS = [
        "127.0.0.1",
        "10.0.2.2",
    ]

LANGUAGE_CODE = "en-us"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain_console": {
            "format": "%(levelname)s %(message)s",
        },
        "verbose": {
            "format": "%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["stdout"],
            "level": env.log_level("DJANGO_LOG_LEVEL", default="INFO"),
        },
        "koruva": {
            "handlers": ["stdout"],
            "level": env.log_level("KORUVA_LOG_LEVEL", default="INFO"),
        },
    },
}

MEDIA_ROOT = env.path("MEDIA_ROOT", default=APPS_DIR / "media")

MEDIA_URL = "/media/"

# https://docs.djangoproject.com/en/dev/topics/http/middleware/
# https://docs.djangoproject.com/en/dev/ref/middleware/#middleware-ordering
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # order doesn't matter
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]
if not PROD:
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.common.CommonMiddleware") + 1,
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )
    MIDDLEWARE.append("django_browser_reload.middleware.BrowserReloadMiddleware")

ROOT_URLCONF = "koruva.urls"

SECRET_KEY = env.str(
    "SECRET_KEY", default="django-insecure-lk3SMcJvaRirTsppaiUqVhS-aF_5h86Bl0NiTn--Frg"
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=PROD
)

SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=PROD)

# https://docs.djangoproject.com/en/dev/ref/middleware/#http-strict-transport-security
# 2 minutes to start with, will increase as HSTS is tested
# example of production value: 60 * 60 * 24 * 7 = 604800 (1 week)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 2) if PROD else 0

# https://noumenal.es/notes/til/django/csrf-trusted-origins/
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=PROD)

SERVER_EMAIL = env.str(
    "SERVER_EMAIL",
    default=DEFAULT_FROM_EMAIL,
    validate=lambda v: Email()(parseaddr(v)[1]),
)

SESSION_COOKIE_SECURE = PROD

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
if PROD and env.bool("USE_S3", default=False):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": env.str("AWS_ACCESS_KEY_ID", default=None),
            "bucket_name": env.str("AWS_STORAGE_BUCKET_NAME", default=None),
            "region_name": env.str("AWS_S3_REGION_NAME", default=None),
            "secret_key": env.str("AWS_SECRET_ACCESS_KEY", default=None),
        },
    }

# https://nickjanetakis.com/blog/django-4-1-html-templates-are-cached-by-default-with-debug-true
DEFAULT_LOADERS = [
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]

CACHED_LOADERS = [("django.template.loaders.cached.Loader", DEFAULT_LOADERS)]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(APPS_DIR / "templates")],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "builtins": [
                "template_partials.templatetags.partials",
                "heroicons.templatetags.heroicons",
            ],
            "debug": DEBUG,
            "loaders": [
                (
                    "template_partials.loader.Loader",
                    DEFAULT_LOADERS if DEBUG else CACHED_LOADERS,
                )
            ],
        },
    },
]

TIME_ZONE = "UTC"

USE_I18N = False

USE_TZ = True

WSGI_APPLICATION = "koruva.wsgi.application"

# 2. Django Contrib Settings
# -----------------------------------------------------------------------------------------------

# django.contrib.auth
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
if not PROD:
    AUTH_PASSWORD_VALIDATORS = []

# django.contrib.staticfiles
STATIC_ROOT = APPS_DIR / "staticfiles"

STATIC_URL = "/static/"

STATICFILES_DIRS = [APPS_DIR / "static/public"]

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

# 3. Third Party Settings
# -------------------------------------------------------------------------------------------------

# django-allauth
ACCOUNT_LOGIN_METHODS = {"email"}

ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https" if PROD else "http"

ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]

ACCOUNT_LOGOUT_REDIRECT_URL = "account_login"

ACCOUNT_SESSION_REMEMBER = True

ACCOUNT_UNIQUE_EMAIL = True

LOGIN_REDIRECT_URL = "home"

# django-anymail
if PROD:
    ANYMAIL = {
        "AMAZON_SES_CLIENT_PARAMS": {
            "aws_access_key_id": env.str("AWS_ACCESS_KEY_ID", default=None),
            "aws_secret_access_key": env.str("AWS_SECRET_ACCESS_KEY", default=None),
            "region_name": env.str("AWS_S3_REGION_NAME", default=None),
        }
    }

# django-crispy-forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"

CRISPY_TEMPLATE_PACK = "tailwind"

# django-debug-toolbar
DEBUG_TOOLBAR_CONFIG = {
    "DISABLE_PANELS": [
        "debug_toolbar.panels.redirects.RedirectsPanel",
        "debug_toolbar.panels.profiling.ProfilingPanel",
    ],
    "SHOW_TEMPLATE_CONTEXT": True,
    "SHOW_COLLAPSED": True,
    "UPDATE_ON_FETCH": True,
    "ROOT_TAG_EXTRA_ATTRS": "hx-preserve",
}

# django-litestream
LITESTREAM = {
    "config_file": BASE_DIR / "litestream.yml",
}

# django-tasks
TASKS = {
    "default": {
        "BACKEND": "django_tasks.backends.database.DatabaseBackend",
        "OPTIONS": {"database": "tasks_db"},
    }
}

# django-tailwind-cli
TAILWIND_CLI_SRC_CSS = APPS_DIR / "static/src/css/source.css"
TAILWIND_CLI_VERSION = "4.1.11"

# sentry
if PROD and (SENTRY_DSN := env.url("SENTRY_DSN", default=None)):
    sentry_sdk.init(
        dsn=SENTRY_DSN.geturl(),
        environment=env.str(
            "SENTRY_ENV",
            default="development",
            validate=OneOf(["development", "production"]),
        ),
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(event_level=None, level=None),
        ],
        send_default_pii=True,
    )

# 4. Project Settings
# -----------------------------------------------------------------------------------------------------

ADMIN_URL = env.str("ADMIN_URL", default="admin/")
DEFAULT_PAGE_SIZE = 20
CACHE_TIME_FAVICON = 60 * 60 * 24  # one day
CACHE_TIME_ROBOTS_TXT = CACHE_TIME_FAVICON
CACHE_TIME_SECURITY_TXT = CACHE_TIME_FAVICON
