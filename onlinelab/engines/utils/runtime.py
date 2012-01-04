"""Common tools for building Python-managed engines. """

import os
import sys

from .server import EngineXMLRPCServer

class Stream(object):
    """Emulate unbuffered UTF-8 encoded stream. """

    def __init__(self, stream):
        """Initialize an instance from a RAW stream, e.g. stdout. """
        self.stream = stream

    def write(self, data):
        """Unbuffered write of UTF-8 encoded data to a stream. """
        if isinstance(data, unicode):
            data = data.encode('utf-8')

        self.stream.write(data)
        self.stream.flush()

    def __getattr__(self, attr):
        """Pass through attributes of the underlying stream. """
        return getattr(self.stream, attr)

class Engine(object):
    """Base class for Python-managed engines. """

    _transport = EngineXMLRPCServer
    _interpreter = None

    def __init__(self, interpreter=None):
        if interpreter is None:
            self.interpreter = self._interpreter()
        else:
            self.interpreter = interpreter

    def setup_io(self):
        """Redefine stdout and stderr for our purpose. """
        sys.stdout = Stream(sys.stdout)
        sys.stderr = Stream(sys.stderr)

    def notify_ready(self):
        """Notify a service that an engine is running. """
        sys.stdout.write('OK (pid=%s)\n' % os.getpid())
        sys.stdout.flush()

    def run(self, port, code=None, interactive=False):
        """Run a Python engine on the given port. """
        server = self._transport(port, self.interpreter)
        self.interpreter.execute(code)
        self.notify_ready()
        self.setup_io()
        server.serve_forever(interactive)

