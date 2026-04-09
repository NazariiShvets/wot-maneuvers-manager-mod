# -*- coding: utf-8 -*-
"""Starter mod under packages/wot-example-mod — duplicate folder and rename to add another package."""
from __future__ import absolute_import
import logging

MOD_VERSION = '{{VERSION}}'
_LOGGER = logging.getLogger(__name__)


def init():
    _LOGGER.info('[WOT_EXAMPLE] v%s — example mod loaded (packages/wot-example-mod)', MOD_VERSION)
