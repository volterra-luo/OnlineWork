
import shutil

class EngineBase(object):
    """Base class for engine management classes. """

    def cleanup_process(self):
        """Remove all data allocated for a process. """
        shutil.rmtree(self.cwd)

    def del_process(self):
        """Remove an engine process from the supervisor. """
        self.manager.del_process(self.uuid)

