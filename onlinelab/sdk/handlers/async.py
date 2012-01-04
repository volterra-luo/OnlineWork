"""Implementation of ``AsyncHandler``. """

from .base import WebHandler
from ..processes import ProcessManager

from ...utils import jsonrpc
from ...utils import Args

class AsyncHandler(WebHandler):
    """Handle method calls to be executed on an engine. """

    def on_okay(self, result):
        """Gets executed when engine method call succeeded. """
        if isinstance(result, basestring):
            self.return_api_result({'status': result})
        else:
            self.return_api_result(result)

    def on_fail(self, error=None):
        """Gets executed when engine method call failed. """
        self.return_api_error(error)

    def call(self, method, uuid, args):
        """Call ``method`` with ``args`` on a process manager. """
        manager = ProcessManager.instance()
        getattr(manager, method)(uuid, args, self.on_okay, self.on_fail)

    @jsonrpc.method
    def RPC__Engine__init(self, uuid=None, engine=None):
        """Process 'start' method call from a client. """
        self.call('start', uuid, Args(engine=engine))

    @jsonrpc.method
    def RPC__Engine__kill(self, uuid):
        """Process 'stop' method call from a client. """
        self.call('stop', uuid, Args())

    @jsonrpc.method
    def RPC__Engine__stat(self, uuid):
        """Process 'stat' method call from a client. """
        self.call('stat', uuid, Args())

    @jsonrpc.method
    def RPC__Engine__complete(self, uuid, source):
        """Process 'complete' method call from a client. """
        self.call('complete', uuid, Args(source=source))

    @jsonrpc.method
    def RPC__Engine__evaluate(self, uuid, source, cellid=None):
        """Process 'evaluate' method call from a client. """
        self.call('evaluate', uuid, Args(source=source, cellid=cellid))

    @jsonrpc.method
    def RPC__Engine__interrupt(self, uuid, cellid=None):
        """Process 'interrupt' method call from a client. """
        self.call('interrupt', uuid, Args(cellid=cellid))

