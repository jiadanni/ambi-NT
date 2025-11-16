import os
import sys

# Shim package that points to the existing `client-cli` directory (hyphenated)
_here = os.path.abspath(os.path.dirname(__file__))
_alt = os.path.abspath(os.path.join(_here, '..', 'client-cli'))

# Ensure import machinery will search the hyphenated directory when resolving submodules
if _alt not in sys.path:
    sys.path.insert(0, _alt)

__all__ = []
