"""Serialize library transactions and their compensating file writes."""
import os
import threading
from functools import wraps

from django.conf import settings

_thread_lock = threading.RLock()


def serialized(operation):
    @wraps(operation)
    def wrapper(*args, **kwargs):
        # File locks coordinate processes; the RLock coordinates local threads.
        with _thread_lock:
            root = settings.USER_CONFIGS_ROOT
            root.mkdir(parents=True, exist_ok=True)
            with (root / '.library.lock').open('a+b') as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b'\0')
                    handle.flush()
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    return operation(*args, **kwargs)
                finally:
                    handle.seek(0)
                    if os.name == 'nt':
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return wrapper
