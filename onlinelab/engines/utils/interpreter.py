"""Common tools for building Python-managed interpreters. """

import sys
import traceback

class Interpreter(object):
    """Base class for Python-managed interpreters. """

    filename = '<online-lab>'

    def __init__(self, debug=False):
        self.debug = debug
        self.index = 0

    def traceback(self):
        """Return nicely formatted most recent traceback. """
        type, value, tb = sys.exc_info()
        return ''.join(traceback.format_exception(type, value, tb.tb_next))

