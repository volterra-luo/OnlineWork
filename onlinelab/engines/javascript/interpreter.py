"""Customized interpreter for JavaScript engines. """

import sys
import time

import PyV8

from ..utils.interpreter import Interpreter

class JavaScriptInterpreter(Interpreter):
    """Customized JavaScript interpreter. """

    _extensions = ['print', 'sleep']

    def __init__(self, debug=False):
        super(JavaScriptInterpreter, self).__init__(debug)

        extensions = []

        for ext in self._extensions:
            name = getattr(self, 'setup_' + ext)()
            extensions.append(name)

        self.context = PyV8.JSContext(extensions=extensions)

    @classmethod
    def setup_print(cls):
        """Setup JavaScript analog of ``print`` statement. """

        def jsext_print(*args):
            """Print values to stdout. """
            sys.stdout.write(' '.join(map(str, args)) + '\n')

        src = 'native function print(arg);'
        ext = PyV8.JSExtension('print/python', src, lambda _: jsext_print)

        return ext.name

    @classmethod
    def setup_sleep(cls):
        """Setup JavaScript analog of ``sleep`` function. """

        def jsext_sleep(amount):
            """Sleep the specified amount of time. """
            time.sleep(amount)

        src = 'native function sleep(arg);'
        ext = PyV8.JSExtension('sleep/python', src, lambda _: jsext_sleep)

        return ext.name

    def evaluate(self, source):
        """Evaluate a piece of JavaScript source code. """
        interrupted = False
        traceback = False
        result = None

        source = source.rstrip()

        try:
            self.context.enter()
            start = time.clock()

            try:
                result = self.context.eval(source, self.filename)

                if result is not None and source and source[-1] != ';':
                    sys.stdout.write(str(result) + '\n')
            except SystemExit:
                raise
            except KeyboardInterrupt:
                traceback = "Interrupted"
                interrupted = True
            except PyV8.JSError as exc:
                traceback = "%s: %s" % (exc.name, exc.message)
            except:
                traceback = self.traceback()

            end = time.clock()
        finally:
            self.context.leave()

        self.index += 1

        result = {
            'source': source,
            'index': self.index,
            'traceback': traceback,
            'interrupted': interrupted,
            'time': end - start,
        }

        return result

    def execute(self, source):
        """Execute a piece of source code in the global namespace. """
        if source is not None:
            with self.context as ctx:
                ctx.eval(str(source), self.filename)

    def complete(self, source):
        """Find all names that start with the given prefix. """
        return {
            'completions': [],
            'interrupted': False,
        }

