"""Base classes for core request handlers. """

import logging

from time import time
from datetime import datetime

import tornado.escape

from ..auth import DjangoMixin

from ...utils.api import APIRequestHandler
from ...utils.settings import Settings

class WebHandler(DjangoMixin, APIRequestHandler):
    """Base class for user <-> core APIs (client/async). """

    def initialize(self):
        """Setup internal configuration of this handler. """
        self.config = Settings.instance()

