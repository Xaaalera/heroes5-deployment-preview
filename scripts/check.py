"""Run mod checks without permitting missing dependencies to masquerade as a pass."""
import keystone, unicorn, pefile, capstone
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
result = unittest.TextTestRunner(verbosity=2).run(suite)
allowed_reason = 'Pinned game EXE is needed for the native movement oracle'
unexpected = [(str(test), reason) for test, reason in result.skipped if reason != allowed_reason]
passed = result.wasSuccessful() and not unexpected and result.testsRun > 0
print(json.dumps({'ok': passed, 'tests_run': result.testsRun, 'failures': len(result.failures),
                  'errors': len(result.errors), 'skipped': [(str(test), reason) for test, reason in result.skipped],
                  'unexpected_skips': unexpected}, ensure_ascii=True))
raise SystemExit(0 if passed else 1)
