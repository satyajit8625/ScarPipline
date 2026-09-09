import os
import sys
import unittest

try:
    import maya.standalone
    try:
        maya.standalone.initialize(name='python')
    except Exception:
        pass
except Exception:
    pass

if __name__ == '__main__':
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'maya')
    suite = unittest.defaultTestLoader.discover(test_dir, pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
