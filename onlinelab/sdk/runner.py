"""Facility for starting engine processes. """

import re
import os
import sys
import time
import fcntl
import shutil
import socket
import logging

from subprocess import Popen, PIPE
from tornado.ioloop import IOLoop

from .base import EngineBase
from .engine import EngineProcess

from ..utils.settings import Settings

class RunnerError(Exception):
    """Represents an engine startup error. """

    def __init__(self, error):
        self.error = error

class EngineRunner(EngineBase):
    """A class for starting engine processes. """

    _re = re.compile(r"^.*?OK \(pid=(?P<pid>\d+)\)")

    def __init__(self, manager, uuid, args, okay, fail):
        self.settings = Settings.instance()
        self.ioloop = IOLoop.instance()
        self.manager = manager
        self.uuid = uuid
        self.args = args
        self._okay = okay
        self._fail = fail
        self.process = None
        self.timeouted = False
        self.terminating = False
        self.preexec_fn = None

    @property
    def pid(self):
        if self.process is not None:
            return self.process.pid
        else:
            return None

    @property
    def is_starting(self):
        return True

    def cleanup_refs(self):
        """Make sure we don't leave cyclic references. """
        self.settings = None
        self.ioloop = None
        self.manager = None
        self._okay = None
        self._fail = None

    def okay(self, *args):
        """Respond with "OK" status. """
        self._okay(*args)
        self.cleanup_refs()

    def fail(self, *args):
        """Respond with "ERROR" status. """
        self._fail(*args)
        self.cleanup_refs()

    def start(self):
        """Start an engine process. """
        try:
            self.setup_engine()
            self.setup_cwd()
            self.setup_env()
            self.setup_process()
            self.setup_pipes()
            self.setup_handlers()
        except RunnerError as exc:
            self.manager.del_process(self.uuid)
            self.fail(exc.error)

    def stop(self, args, okay, fail):
        """Terminate a starting engine process. """
        self.process.terminate()
        self.terminating = True
        okay('terminated')

    def kill(self):
        """Kill a starting engine process. """
        self.process.kill()

    @classmethod
    def set_nonblocking(cls, fd, nonblocking=True):
        """Set non-blocking property on a file descriptor. """
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)

        if nonblocking:
            fl |=   os.O_NONBLOCK
        else:
            fl &= (~os.O_NONBLOCK) & 0xFFFFFFFF

        fcntl.fcntl(fd, fcntl.F_SETFL, fl)

    @classmethod
    def find_port(cls):
        """Find a free socket port. """
        sock = socket.socket()
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        del sock
        return port

    def _get_engine(self, args):
        """Return engine metadata. """
        if 'engine' in args:
            engine = args['engine']

            if engine is not None:
                if isinstance(engine, basestring):
                    return {'name': engine}
                elif isinstance(engine, dict):
                    if 'name' not in engine:
                        engine['name'] = 'python'
                    return engine

        return {'name': 'python'}

    def setup_engine(self):
        """Build engine startup command-line. """
        engine = self._get_engine(self.args)
        namespace = {}

        if isinstance(engine['name'], basestring):
            name = engine['name'].lower()
        else:
            raise RunnerError('bad-engine')

        if name not in self.settings.engines:
            raise RunnerError('bad-engine')

        try:
            exec "from onlinelab.engines.%s import builder" % name in namespace
        except ImportError:
            raise RunnerError('bad-engine')

        self.port = self.find_port()
        builder = namespace['builder']

        try:
            code = engine['code']
        except KeyError:
            code = None

        self.command = builder(self.port, code)

    def setup_cwd(self):
        """Create a working directory for an engine. """
        # Create a directory for a process that we will spawn in a moment. If
        # it already exists, make sure it is empty (just remove it and create
        # once again).

        self.cwd = cwd = os.path.join(self.settings.data_path, self.uuid)

        if os.path.exists(cwd):
            shutil.rmtree(cwd)

        os.mkdir(cwd)

    def setup_env(self):
        """Create an hardened environment for an engine. """
        if self.settings.environ is True:
            self.env = env = dict(os.environ)
        else:
            self.env = env = {}

            for key, value in self.settings.environ.iteritems():
                if value is True:
                    try:
                        value = os.environ[key]
                    except KeyError:
                        continue

                env[key] = value

        PYTHONPATH = self.settings.get_PYTHONPATH()

        try:
            path = env['PYTHONPATH']
        except KeyError:
            try:
                path = os.environ['PYTHONPATH']
            except KeyError:
                path = None

        if path:
            PYTHONPATH += os.pathsep + path

        env['PYTHONPATH'] = PYTHONPATH

        # As we know the home directory for our engine, lets now hack Python's
        # site.py and tell it where is should look for extra modules (.local)
        # and make some other modules happy (e.g. matplotlib).

        env['HOME'] = env['PYTHONUSERBASE'] = self.cwd

    def setup_process(self):
        """Create an engine process. """
        # Lets start the engine's process. We must close all non-standard file
        # descriptors (via 'close_fds'), because otherwise IOLoop will hang.
        # When the process will be ready to handle requests from the client, it
        # will tell us this by sending a single line of well formatted output.

        self.process = Popen(self.command, preexec_fn=self.preexec_fn, cwd=self.cwd,
            env=self.env, close_fds=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)

    def setup_pipes(self):
        """Make sure that stdout and stderr are non-blocking. """
        stdout = self.process.stdout.fileno()
        stderr = self.process.stderr.fileno()

        self.set_nonblocking(stdout)
        self.set_nonblocking(stderr)

    def setup_handlers(self):
        """Setup timeout and communication handlers. """
        deadline = time.time() + self.settings.engine_timeout
        iomask = self.ioloop.READ | self.ioloop.ERROR

        self.timeout = self.ioloop.add_timeout(deadline, self._on_timeout)
        self.ioloop.add_handler(self.process.stdout.fileno(), self._on_pipe, iomask)

    def _on_timeout(self):
        """Gets executed when a process was starting too long. """
        self.process.kill()
        self.timeouted = True

    def _on_pipe(self, fd, events):
        """Gets executed when a process communicates with us. """
        if events & self.ioloop.ERROR:
            self._on_error(fd, events)
        else:
            self._on_read(fd, events)

    def _on_error(self, fd, events):
        """Get executed when error occurred during engine startup. """
        self.cleanup_handlers(fd)

        try:
            out = self.process.stdout.read()
            if out: sys.stdout.write(out)
        except IOError:
            pass

        try:
            err = self.process.stderr.read()
            if err: sys.stdout.write(err)
        except IOError:
            pass

        self.cleanup_process()
        self.del_process()

        self.process.wait()

        if self.terminating:
            self.okay('terminated')
        else:
            if self.timeouted:
                self.fail('timeout')
            else:
                self.fail('died')

    def _on_read(self, fd, events):
        """Get executed when starting engine communicated with us. """
        try:
            output = self.process.stdout.read()
        except IOError:
            return

        result = self._re.match(output)

        if result is None:
            sys.stdout.write(output)
            return

        self.cleanup_handlers(fd)

        engine = EngineProcess(self.manager, self.uuid, self.process, self.cwd, self.port)
        self.manager.set_process(self.uuid, engine)

        logging.info("Started new engine process (pid=%s)" % engine.pid)

        self.okay({'status': 'started', 'uuid': self.uuid, 'memory': engine.get_memory()})

    def cleanup_handlers(self, fd):
        """Remove timeout and communication handlers. """
        try:
            self.ioloop.remove_timeout(self.timeout)
        except ValueError:
            pass

        self.ioloop.remove_handler(fd)

