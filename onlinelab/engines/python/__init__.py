"""Bootstrap code for a Python engine. """

boot = """\
from onlinelab.engines.python.runtime import PythonEngine
PythonEngine().run(port=%(port)d, code=%(code)r)
"""

def builder(port, code):
    """Build command-line for running Python engine. """
    return ["python", "-c", boot % {'port': port, 'code': code}]

