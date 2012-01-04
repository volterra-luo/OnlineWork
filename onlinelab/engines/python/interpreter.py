"""Customized interpreter for Python engines. """

import sys
import time
import tokenize
import traceback
import rlcompleter

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from ..utils.interpreter import Interpreter

from .namespace import PythonNamespace
from .inspector import Inspector

class PythonInterpreter(Interpreter):
    """Customized Python interpreter with two-stage evaluation. """

    def __init__(self, debug=False):
        super(PythonInterpreter, self).__init__(debug)
        self.namespace = PythonNamespace()
        self.inspector = Inspector()

    def complete(self, source):
        """Get all completions for an initial source code. """
        interrupted = False

        try:
            completer = rlcompleter.Completer(self.namespace)

            matches = set([])
            state = 0

            while True:
                result = completer.complete(source, state)

                if result is not None:
                    matches.add(result)
                    state += 1
                else:
                    break

            completions = []

            for match in sorted(matches):
                if match[-1] == '(':
                    match = match[:-1]

                if '.' in match:
                    name, attrs = match.split('.', 1)
                else:
                    name, attrs = match, None

                try:
                    obj = self.namespace[name]
                except KeyError:
                    obj = None
                else:
                    if attrs is not None:
                        for attr in attrs.split('.'):
                            obj = getattr(obj, attr)

                if obj is not None:
                    info = self.inspector.get_basic_info(obj)
                else:
                    info = {'type': 'keyword'}

                completions.append({
                    'match': match,
                    'info': info,
                })
        except KeyboardInterrupt:
            completions = None
            interrupted = True

        return {
            'completions': completions,
            'interrupted': interrupted,
        }

    def evaluate(self, source):
        """Evaluate a piece of Python source code. """
        source = source.replace('\r', '').rstrip()

        # XXX: make all this SIGINT aware

        if '\n' in source:
            exec_source, eval_source = self.split(source)
        else:
            exec_source, eval_source = None, source

        eval_source += '\n'

        try:
            self.compile(eval_source, 'eval')
        except (OverflowError, SyntaxError, ValueError):
            if '\n' not in source and self.is_inspect(source):
                return self.inspect(source)

            exec_source = source
            eval_source = None

        try:
            del self.namespace['__plots__']
        except KeyError:
            pass

        interrupted = False
        traceback = False
        result = None

        start = time.clock()

        try:
            if exec_source is not None:
                try:
                    exec_code = self.compile(exec_source, 'exec')
                except (OverflowError, SyntaxError, ValueError):
                    traceback = self.syntaxerror()
                    eval_source = None
                else:
                    eval(exec_code, self.namespace)

            if eval_source is not None:
                result = eval(eval_source, self.namespace)
                sys.displayhook(result)
        except SystemExit:
            raise
        except KeyboardInterrupt:
            traceback = self.traceback()
            interrupted = True
        except:
            traceback = self.traceback()

        end = time.clock()

        try:
            plots = self.namespace['__plots__']
        except KeyError:
            plots = []

        self.index += 1

        if result is not None:
            self.namespace['_%d' % self.index] = result

            self.namespace['___'] = self.namespace.get('__')
            self.namespace['__'] = self.namespace.get('_')
            self.namespace['_'] = result

        result = {
            'source': source,
            'index': self.index,
            'time': end - start,
            'plots': plots,
            'traceback': traceback,
            'interrupted': interrupted,
        }

        return result

    def inspect(self, source):
        """Collect information about a Python object. """
        text = source
        more = False

        if text.startswith('??'):
            text = text[2:]
            more = True

        if text.endswith('??'):
            text = text[:-2]
            more = True

        if not more:
            if text.startswith('?'):
                text = text[1:]

            if text.endswith('?'):
                text = text[:-1]

        text = text.strip()

        if '.' in text:
            name, attrs = text.split('.', 1)
        else:
            name, attrs = text, None

        try:
            obj = self.namespace[name]
        except KeyError:
            obj = None
        else:
            if attrs is not None:
                for attr in attrs.split('.'):
                    try:
                        obj = getattr(obj, attr)
                    except KeyError:
                        obj = None
                        break

        if obj is not None:
            info = self.inspector.get_info(obj)
        else:
            info = None

        self.index += 1

        return {
            'source': source,
            'text': text,
            'info': info,
            'more': more,
            'index': self.index,
            'interrupted': False,
        }

    def is_inspect(self, source):
        """Return ``True`` if user requested code inspection. """
        return source.startswith('?') or source.endswith('?')

    def split(self, source):
        """Extract last logical line from multi-line source code. """
        string = StringIO(source).readline

        try:
            tokens = reversed(list(tokenize.generate_tokens(string)))
        except (OverflowError, SyntaxError, ValueError):
            return None, source

        for tok, _, (n, _), _, _ in tokens:
            if tok == tokenize.NEWLINE:
                lines = source.split('\n')

                exec_source = '\n'.join(lines[:n])
                eval_source = '\n'.join(lines[n:])

                return exec_source, eval_source
        else:
            return None, source

    def compile(self, source, mode):
        """Wrapper over Python's built-in :func:`compile` function. """
        return compile(source, self.filename, mode)

    def execute(self, source):
        """Execute a piece of source code in the global namespace. """
        if source is not None:
            eval(self.compile(source, 'exec'), self.namespace)

    def syntaxerror(self):
        """Return nicely formatted syntax error. """
        type, value, sys.last_traceback = sys.exc_info()

        sys.last_type = type
        sys.last_value = value

        if type is SyntaxError:
            try:
                msg, (dummy_filename, lineno, offset, line) = value
            except:
                pass
            else:
                value = SyntaxError(msg, (self.filename, lineno, offset, line))
                sys.last_value = value

        header = "Traceback (most recent call last):\n"

        return ''.join([header] + traceback.format_exception_only(type, value))

