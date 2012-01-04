"""Bootstrap code for a Python 3 engine. """

boot = """\
from onlinelab.engines.python3.runtime import Python3Engine
Python3Engine().run(port=%(port)d, code=%(code)r)
"""

def builder(port, code):
    """Build command-line for running Python 3 engine. """
    return ["python3", "-c", boot % {'port': port, 'code': code}]

