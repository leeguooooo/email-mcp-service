"""Entry point for `python -m clients.mailbox_client`."""
from __future__ import annotations

import sys

from .cli import main


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
