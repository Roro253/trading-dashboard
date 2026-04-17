"""pytest conftest — makes office-hours/ importable.

The parent directory has a hyphen in its name, so it can't be a Python
package. We put it on sys.path and import subpackages (``scoring``,
``adapters``) directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

OFFICE_HOURS_ROOT = Path(__file__).resolve().parent.parent
if str(OFFICE_HOURS_ROOT) not in sys.path:
    sys.path.insert(0, str(OFFICE_HOURS_ROOT))
