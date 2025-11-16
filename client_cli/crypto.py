"""
Shim module that re-exports symbols from the hyphenated `client-cli/crypto.py` file.
This lets tests and other modules use imports like `from client_cli.crypto import ClientCrypto`.
"""
import importlib.util
import os

_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'client-cli', 'crypto.py'))
if not os.path.exists(_src_path):
    raise ImportError(f"Expected client-cli/crypto.py at {_src_path}")

spec = importlib.util.spec_from_file_location('client_cli._crypto_impl', _src_path)
_module = importlib.util.module_from_spec(spec)
_spec_loader = spec.loader
_spec_loader.exec_module(_module)

# Re-export commonly used symbols
for _name in dir(_module):
    if not _name.startswith('_'):
        globals()[_name] = getattr(_module, _name)

__all__ = [name for name in globals() if not name.startswith('_')]
