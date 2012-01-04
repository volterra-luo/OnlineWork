"""Bootstrap code for a JavaScript engine. """

boot = """\
from onlinelab.engines.javascript.runtime import JavaScriptEngine
JavaScriptEngine().run(port=%(port)d, code=%(code)r)
"""

def builder(port, code):
    """Build command-line for running JavaScript engine. """
    return ["python", "-c", boot % {'port': port, 'code': code}]

