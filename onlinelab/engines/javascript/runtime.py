"""Runtime environment for JavaScript engines. """

from ..utils.runtime import Engine
from .interpreter import JavaScriptInterpreter

class JavaScriptEngine(Engine):
    """The default JavaScript engine. """

    _interpreter = JavaScriptInterpreter

