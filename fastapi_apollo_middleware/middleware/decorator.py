from functools import wraps


def cached_method(func):
    """
    Use cache method in Python Class
    :return: cache data
    """

    @wraps(func)
    def inner(self, *args, **kwargs):
        if not hasattr(self, "_cache_result"):
            # Miss the cache
            func.result = func(self, *args, **kwargs)
            setattr(self.__class__, "_cache_result", func.result)
            setattr(self, "_cache_result", func.result)
            return self._cache_result
        else:
            # Hit the cache
            func(self, *args, **kwargs)
            return self._cache_result

    return inner
