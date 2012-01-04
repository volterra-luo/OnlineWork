"""Implementation of engine processes. """

import time
import signal
import logging
import xmlrpclib
import collections

from StringIO import StringIO

from tornado.ioloop import IOLoop
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.httputil import HTTPHeaders

import psutil

from .base import EngineBase
from . import utilities, highlight

from ..utils.settings import Settings

class EngineProcess(EngineBase):
    """Bridge between a logical engine and a physical process. """

    READY = 1
    TERMINATING = 2
    DIED = 3

    def __init__(self, manager, uuid, process, cwd, port):
        """Initialize an engine based on existing system process. """
        self.settings = Settings.instance()
        self.ioloop = IOLoop.instance()

        self.manager = manager
        self.uuid = uuid
        self.process = process
        self.cwd = cwd
        self.port = port

        self.status = self.READY

        self.util = psutil.Process(process.pid)
        self.queue = collections.deque()
        self.url = "http://localhost:%s" % port

        self.evaluating = False
        self.evaluate_timeout = None

        self.out = StringIO()
        self.err = StringIO()

        stdout = process.stdout.fileno()
        stderr = process.stderr.fileno()

        iomask = self.ioloop.READ | self.ioloop.ERROR

        self.ioloop.add_handler(stdout, self._on_stdout, iomask)
        self.ioloop.add_handler(stderr, self._on_stderr, iomask)

    def __del__(self):
        """Delete this engine's instance. """
        logging.info("%s deleted" % self.uuid)

    @property
    def is_starting(self):
        return False

    @property
    def is_dead(self):
        return self.status == self.DIED

    def _reset_io(self):
        """Close and recreate local ``stdout`` and ``stderr``. """
        self.out.close()
        self.out = StringIO()

        self.err.close()
        self.err = StringIO()

    def _read_stdout(self):
        """Transfer ``stdout`` from a PIPE to a string buffer. """
        while True:
            try:
                data = self.process.stdout.read()
                self.out.write(data)
            except IOError:
                break

    def _read_stderr(self):
        """Transfer ``stderr`` from a PIPE to a string buffer. """
        while True:
            try:
                data = self.process.stderr.read()
                self.err.write(data)
            except IOError:
                break

    def _on_stdout(self, fd, events):
        """Monitor engine's ``stdout``. """
        if events & self.ioloop.ERROR:
            self.ioloop.remove_handler(fd)

            self.cleanup_process()
            self.process.wait()

            if self.status == self.TERMINATING:
                logging.info('%s terminated' % self.uuid)
                self.okay('terminated')
                self.del_process()
            else:
                logging.info('%s died' % self.uuid)
                self.status = self.DIED
        else:
            self._read_stdout()

    def _on_stderr(self, fd, events):
        """Monitor engine's ``stderr``. """
        if events & self.ioloop.ERROR:
            self.ioloop.remove_handler(fd)
        else:
            self._read_stderr()

    @property
    def pid(self):
        return self.process.pid

    @property
    def is_running(self):
        return self.process.poll() is None

    @property
    def is_evaluating(self):
        return self.evaluating

    def stop(self, args, okay, fail):
        """Terminate this engine's process. """
        # XXX: clear the queue?
        if self.status == self.TERMINATING:
            fail('terminating')
        else:
            self.status = self.TERMINATING
            self.okay = okay
            self.fail = fail
            self.process.terminate()

    def kill(self):
        """Kill this engine process. """
        if self.status == self.READY:
            self.process.kill()

    def get_stat(self):
        """Get statistics provided by ``psutil``.  """
        cpu_percent = self.util.get_cpu_percent()
        cpu_times = self.util.get_cpu_times()
        memory_percent = self.util.get_memory_percent()
        memory_info = self.util.get_memory_info()

        user, system = cpu_times
        rss, vms = memory_info

        return {
            'cpu': { 'percent': cpu_percent, 'user': user, 'system': system },
            'memory': { 'percent': memory_percent, 'rss': rss, 'vms': vms },
        }

    def get_memory(self):
        return self.util.get_memory_info()[0]

    def stat(self, args, okay, fail):
        """Gather data about this engine's process. """
        okay(self.get_stat())

    def complete(self, args, okay, fail):
        """Complete code in this engine's process. """
        if self.evaluating:
            fail('busy')
        else:
            self._schedule(args, okay, fail)
            self._evaluate(method='complete')

    def evaluate(self, args, okay, fail):
        """Evaluate code in this engine's process. """
        self._schedule(args, okay, fail)
        self._evaluate()

    def interrupt(self, args, okay, fail):
        """Stop evaluation of a particular request or all requests. """
        if not self.evaluating:
            okay('not-evaluating')
            return

        try:
            cellid = args['cellid']
        except KeyError:
            pass
        else:
            _args, _, _ = self.evaluating

            if cellid != _args.cellid:
                for i, (_args, _okay, _) in enumerate(self.queue):
                    if cellid == _args.cellid:
                        del self.queue[i]
                        okay('interrupted')

                        result = {
                            'source': _args.source,
                            'index': None,
                            'time': 0,
                            'out': u'',
                            'err': u'',
                            'plots': [],
                            'traceback': False,
                            'interrupted': True,
                        }

                        _okay(result)
                        return

        # Now the most interesting part. To physically interrupt
        # the interpreter associated with this engine, we send
        # SIGINT to the engine's process. The process will catch
        # this signal via KeyboardInterrupt exception and return
        # partial output and information that the computation was
        # interrupted. If there are any requests pending, then
        # evaluation handler (_on_evaluate_handler) will schedule
        # next request for evaluation. This way we have only one
        # one path of data flow in all cases.

        self._interrupt()
        okay('interrupted')

    def _interrupt(self):
        """Send interruption signal to an engine process. """
        self.process.send_signal(signal.SIGINT)

    def _schedule(self, args, okay, fail):
        """Push evaluation request at the end of the queue. """
        self.queue.append((args, okay, fail))

    def _evaluate(self, method='evaluate'):
        """Evaluate next pending request if engine not busy. """
        if not self.evaluating and self.queue:
            args, okay, fail = self.evaluating = self.queue.pop()

            body = utilities.xml_encode(args.source, method)
            headers = HTTPHeaders({'Content-Type': 'application/xml'})

            request = HTTPRequest(self.url, method='POST',
                body=body, headers=headers, request_timeout=0)

            client = AsyncHTTPClient()
            client.fetch(request, self._on_evaluate_handler)

            timeout = self.settings.evaluate_timeout

            if timeout > 0:
                self.evaluate_timeout = self.ioloop.add_timeout(
                    time.time() + timeout, self._on_evaluate_timeout)

    def _on_evaluate_timeout(self):
        """Gets executed when evaluation was taking too long. """
        self._interrupt()

    def _on_evaluate_handler(self, response):
        """Handler that gets executed when evaluation finishes. """
        _, okay, fail = self.evaluating
        timeouted = False

        if self.evaluate_timeout is not None:
            try:
                self.ioloop.remove_timeout(self.evaluate_timeout)
            except ValueError:
                timeouted = True

        self.evaluating = False
        self._evaluate()

        if response.code == 200:
            try:
                result = utilities.xml_decode(response.body)
            except xmlrpclib.Fault, exc:
                fail('fault: %s' % exc)
            else:
                self._process_response(result, timeouted, okay)
        else:
            import pdb
            pdb.set_trace()
            fail('response-code: %s' % response.code)

        self._reset_io()

    def _process_response(self, result, timeouted, okay):
        """Perform final processing of evaluation results. """
        result['memory'] = self.get_stat()['memory']['rss']

        if timeouted:
            result['timeout'] = True

        self._read_stdout()
        self._read_stderr()

        result['out'] = self.out.getvalue()
        result['err'] = self.err.getvalue()

        hl = highlight.Highlight()

        traceback = result.get('traceback')

        if traceback:
            result['traceback_html'] = hl.traceback(traceback)

        info = result.get('info')

        if info is not None:
            docstring = info.get('docstring')

            if docstring is not None:
                info['docstring_html'] = hl.docstring(docstring)

            source = info.get('source')

            if source is not None:
                info['source_html'] = hl.python(source)

            args = info.get('args')

            if args is not None:
                info['args_html'] = hl.python(args)

        okay(result)

