import contextlib
import time
from contextvars import ContextVar
from functools import partial

from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save

from auditlog import get_logentry_model
LogEntry = get_logentry_model()


auditlog_value = ContextVar("auditlog_value")
auditlog_disabled = ContextVar("auditlog_disabled", default=False)


@contextlib.contextmanager
def set_extra_data(context_data):
    """Connect a signal receiver with current user attached."""
    # Initialize thread local storage
    context_data["signal_duid"] = ("set_actor", time.time())
    auditlog_value.set(context_data)

    # Connect signal for automatic logging
    set_extra_data = partial(
        _set_extra_data,
        signal_duid=context_data["signal_duid"],
    )
    pre_save.connect(
        set_extra_data,
        sender=LogEntry,
        dispatch_uid=context_data["signal_duid"],
        weak=False,
    )

    try:
        yield
    finally:
        try:
            auditlog = auditlog_value.get()
        except LookupError:
            pass
        else:
            pre_save.disconnect(sender=LogEntry, dispatch_uid=auditlog["signal_duid"])


def set_actor(auditlog, instance, sender):
    auth_user_model = get_user_model()
    if (
        sender == LogEntry
        and isinstance(auditlog["user"], auth_user_model)
        and instance.actor is None
    ):
        instance.actor = auditlog["user"]
        instance.actor_email = getattr(auditlog["user"], "email", None)


def _set_extra_data(sender, instance, signal_duid, **kwargs):
    """Signal receiver with extra 'user' and 'signal_duid' kwargs.

    This function becomes a valid signal receiver when it is curried with the actor and a dispatch id.
    """
    try:
        auditlog = auditlog_value.get()
    except LookupError:
        pass
    else:
        if signal_duid != auditlog["signal_duid"]:
            return

        set_actor(auditlog, instance, sender)

        for key in auditlog:
            if hasattr(LogEntry, key):
                if callable(auditlog[key]):
                    setattr(instance, key, auditlog[key]())
                else:
                    setattr(instance, key, auditlog[key])


@contextlib.contextmanager
def disable_auditlog():
    token = auditlog_disabled.set(True)
    try:
        yield
    finally:
        try:
            auditlog_disabled.reset(token)
        except LookupError:
            pass
