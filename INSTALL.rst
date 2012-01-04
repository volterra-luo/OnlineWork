
Installing OnlineWork SDK
===========================

OnlineWork SDK is available only from its ``git`` repository
hosted at GitHub. To get a copy of this repository, issue::

    $ git clone git://github.com/volterra-luo/OnlineWork.git

Prerequisites
=============

OnlineWork runs under any Unix-like operating system that implements
non-blocking polling functionality, e.g. ``epoll`` (Linux), ``kqueue``
(BSD) or ``select`` (universal, worst case scenario). To obtain best
performance, Linux operating system distribution with ``epoll`` support
should be used (kernel 2.6 or better is required).

The required packages for Online Lab are:

* Python >= 2.6 (http://www.python.org)
* Tornado >= 1.1 (http://www.tornadoweb.org)
* Django >= 1.1 (http://www.djangoproject.com)

and smaller, but not less important, are:

* argparse (http://code.google.com/p/argparse)
* lockfile (http://pypi.python.org/pypi/lockfile)
* daemon (http://pypi.python.org/pypi/python-daemon)
* psutil (http://code.google.com/p/psutil)
* pycurl (http://pycurl.sourceforge.net)
* docutils (http://docutils.sourceforge.net)

For example, in Ubuntu Lucid issue::

    $ sudo apt-get install python python-django python-argparse python-lockfile python-daemon python-psutil python-pycurl python-docutils python-pygments

to get those packages installed. Note that Tornado didn't manage to get
into software package management systems yet (e.g. apt-get or portage),
so you have to install it manually, either by downloading its source
code tarball from Tornado's website::

    $ wget http://github.com/downloads/facebook/tornado/tornado-1.1.tar.gz

or by cloning its ``git`` repository that is hosted at GitHub. Make sure
that all required packages are available on ``PYTHONPATH`` before running
OnlineWork.

If you use Python 2.7 or better, then you don't need to install argparse
module, because it is included in Python standard library since 2.7 (see
PEP 389 for details).


Setting up OnlineWork
=====================

Suppose OnlineWork's repository was cloned into ``/home/lab``::

    $ cd /home/lab/OnlineWork

We have to create a work environment for the SDK::

    $ bin/onlinelab sdk init --home=../home --ui-path=ui

``onlinelab`` script automatically adds current directory to ``PYTHONPATH``
so you don't have to worry about module visibility issues. The directories
with work environments will contain some configuration files and additional
subdirectories for storing runtime data (logs, PID files, blobs, etc.), a
database is created and user interface (UI) is set up.

Running OnlineWork
==================

Now open a terminal and run the following command::

    $ bin/onlinelab sdk start --no-daemon --home=../home

This will start a server listening on localhost:8000. Now go to your
browser (preferably Firefox or Chrome) and redirect to::

    http://localhost:8000

Login screen will appear, where you can create an account and finally
proceed to OnlineWork's desktop. Click 'Help' icon to show a tutorial
about main features of the system.

If you are not interested in watching the output from OnlineWork, then
you may consider running it as a daemon (just remove ``--no-daemon``
from the command above). In this case, you still will be able to read
the logs that are stored in OnlineWork's home directory.

To stop OnlineWork SDK simply press ``Ctrl+C`` the terminal or issue
the following command::

    $ bin/onlinelab sdk stop --home=../home

Known issues
============

If Online Lab starts fine, but you can't evaluate anything and logs tell
you the following::

    Traceback (most recent call last):
      File "<string>", line 1, in <module>
    ImportError: No module named onlinelab.engines.python.runtime

then most probably it means that OnlineWork wasn't installed in a system
wide location and thus is not visible in OnlineWork engines. To fix this
make sure you run OnlineWork from its source directory or install it in
globally visible location, like ``/usr/lib``. OnlineWork engines are run
in a detached environment which doesn't inherit any settings by default
(e.g. if OnlineWork was installed in ``~/.local``, then this directory
won't be available on PYTHONPATH in an engine, unless explicitly specified
in SDK's configuration file).

Extending PYTHONPATH
====================

If you have auxiliary Python modules that you would like to expose in
OnlineWork (e.g. SymPy) and those modules aren't available on system-wide
``PYTHONPATH`` for some reason (e.g. you would like to expose a certain
branch of a development repository), then add paths to those modules via
``--python-path`` command-line option, e.g.::

    $ bin/onlinelab sdk start --python-path=/devel/sympy

assuming that SymPy's module is located in ``/devel/sympy``. You can also
use colon-syntax to add multiple paths::

    $ bin/onlinelab sdk start --python-path=/devel/sympy:../numpy

You can also add multiple ``--python-path`` options and/or store them in
SDK's configuration file.

Importing Sage worksheets
===========================

Go to http://localhost:8000, open Browser and click 'Import'. Copy
plain text from Sage worksheet, e.g.::

    {{{id=0|
    some code
    ///
    output
    }}}

and click 'OK'. A new window will appear with all cells imported.
