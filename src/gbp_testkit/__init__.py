"""Tests for gentoo build publisher"""

# pylint: disable=missing-class-docstring,missing-function-docstring
import logging
import unittest

import django.test
from unittest_fixtures import where

logging.basicConfig(handlers=[logging.NullHandler()])


@where(environ={"BUILD_PUBLISHER_STORAGE_PATH": "memory"})
class TestCase(unittest.TestCase):
    pass


@where(environ={"BUILD_PUBLISHER_STORAGE_PATH": "django"})
class DjangoTestCase(django.test.TestCase):
    pass
