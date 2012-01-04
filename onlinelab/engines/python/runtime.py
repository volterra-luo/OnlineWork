"""Runtime environment for Python engines. """

from ..utils.runtime import Engine
from .interpreter import PythonInterpreter

class PythonEngine(Engine):
    """The default Python engine. """

    _interpreter = PythonInterpreter

