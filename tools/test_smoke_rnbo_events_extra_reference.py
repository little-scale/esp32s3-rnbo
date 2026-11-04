# SPDX-License-Identifier: MIT
"""Expose original RNBO event reference tests to the portable tools suite."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location(
    'smoke_rnbo_events_extra_tests',Path(__file__).resolve().parents[1]/'tests/fixtures/smoke/rnbo-events-extra/test_reference.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ExtraEventsReferenceTests=module.ExtraEventsReferenceTests

if __name__=='__main__':unittest.main()
