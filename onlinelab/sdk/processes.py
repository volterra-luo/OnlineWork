"""Engine process manager for Online Lab services. """

import os
import sys
import uuid
import logging

from tornado.ioloop import IOLoop

from .runner import EngineRunner

from ..utils.settings import Settings

class ProcessManager(object):
    """Start and manage system processes for engines. """

    def __init__(self):
        self.ioloop = IOLoop.instance()
        self.settings = Settings.instance()

        self.processes = {}

    @classmethod
    def instance(cls):
        """Returns the global :class:`ProcessManager` instance. """
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance

    @classmethod
    def new_uuid(cls):
        return uuid.uuid4().hex

    def add_process(self, uuid, args, okay, fail):
        """Start new engine process using engine runner. """
        runner = EngineRunner(self, uuid, args, okay, fail)
        self.processes[uuid] = runner
        runner.start()

    def set_process(self, uuid, process):
        """Substitute engine runner with an engine process. """
        self.processes[uuid] = process

    def del_process(self, uuid):
        """Remove engine runner/process from the store. """
        del self.processes[uuid]

    def start(self, uuid, args, okay, fail):
        """Start a new engine instance (start a new process). """
        try:
            process = self.processes[uuid]
        except KeyError:
            self.add_process(uuid or self.new_uuid(), args, okay, fail)
        else:
            if process.is_starting():
                fail('starting')
            elif process.is_dead:
                self.del_process(uuid)
                fail('died')
            else:
                fail('running')

    def stop(self, uuid, args, okay, fail):
        """Stop an existing engine instance (kill a process). """
        try:
            process = self.processes[uuid]
        except KeyError:
            fail('does-not-exist')
        else:
            process.stop(args, okay, fail)

    def _apply_process(self, uuid, method, args, okay, fail):
        try:
            process = self.processes[uuid]
        except KeyError:
            fail('does-not-exist')
        else:
            if process.is_starting:
                fail('starting')
            elif process.is_dead:
                self.del_process(uuid)
                fail('died')
            else:
                getattr(process, method)(args, okay, fail)

    def stat(self, uuid, args, okay, fail):
        """Gather data about an engine process. """
        self._apply_process(uuid, 'stat', args, okay, fail)

    def complete(self, uuid, args, okay, fail):
        """Complete a piece of source code. """
        self._apply_process(uuid, 'complete', args, okay, fail)

    def evaluate(self, uuid, args, okay, fail):
        """Evaluate a piece of source code. """
        self._apply_process(uuid, 'evaluate', args, okay, fail)

    def interrupt(self, uuid, args, okay, fail):
        """Stop evaluation of specified requests. """
        self._apply_process(uuid, 'interrupt', args, okay, fail)

    def killall(self):
        """Forcibly kill all processes that belong to this manager. """
        for uuid, process in self.processes.iteritems():
            logging.warning("Forced kill of %s (pid=%s)" % (uuid, process.pid))
            process.kill()

