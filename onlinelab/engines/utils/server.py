"""XML-RPC based communication layer. """

import sys

try:
    from SimpleXMLRPCServer import SimpleXMLRPCServer
except ImportError:
    from xmlrpc.server import SimpleXMLRPCServer

class EngineXMLRPCMethods(object):
    """Translation layer between engine API and an interpreter. """

    def __init__(self, interpreter):
        self.interpreter = interpreter

    def complete(self, source):
        """Complete a piece of source code. """
        return self.interpreter.complete(source)

    def evaluate(self, source):
        """Evaluate a piece of source code. """
        return self.interpreter.evaluate(source)

class EngineXMLRPCServer(SimpleXMLRPCServer):
    """XML-RPC server for handling requests from a service. """

    _methods = EngineXMLRPCMethods

    def __init__(self, port, interpreter):
        address = ('localhost', port)

        SimpleXMLRPCServer.__init__(self, address,
            logRequests=False, allow_none=True)

        self.register_instance(self._methods(interpreter))
        self.register_introspection_functions()

    def serve_forever(self, interactive=False):
        """Indefinitely serve XML RPC requests. """
        while True:
            try:
                self.handle_request()
            except KeyboardInterrupt:
                # Note that we use SIGINT for interrupting evaluation in the
                # underlying interpreter instance, so in 'interactive' mode
                # you will need to send two SIGINTs to the process (one to
                # interrupt currently evaluating code and one to stop the
                # RPC server) to terminate it.
                if interactive:
                    sys.stdout.write("\nTerminated (interactive mode)\n")
                    break

