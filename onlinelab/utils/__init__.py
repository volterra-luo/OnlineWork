"""Common utilities for Online Lab. """

from settings import configure, Settings
from benchmarking import timed

class Args(dict):
    """Dictionary with object-like access. """

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError("'%s' is not a valid attribute" % name)

