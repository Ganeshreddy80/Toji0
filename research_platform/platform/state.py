import threading


class PlatformState:

    _lock = threading.Lock()
    _kernel = None

    @classmethod
    def get(cls):
        return cls._kernel

    @classmethod
    def set(cls, kernel):
        with cls._lock:
            if cls._kernel is None:
                cls._kernel = kernel
            return cls._kernel

    @classmethod
    def exists(cls):
        return cls._kernel is not None
