from importlib.metadata import version
from django.apps import apps as django_apps
from django.conf import settings

__version__ = version("django-auditlog")


def get_logentry_model():
    try:
        return django_apps.get_model(settings.AUDITLOG_LOGENTRY_MODEL, require_ready=False)
    except:
        pass
