"""Utilities for cooperation with FEMhub distribution. """

import os
import sys

def femhub_set_paths():
    """Sets the paths automatically for FEMhub. """
    SDK_HOME_PATH = os.path.expandvars("$SPKG_LOCAL/share/onlinelab/sdk/")
    sys.path.append(SDK_HOME_PATH)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

