"""
tiktic - Personal resale ticket monitor for sold-out shows.

This package is intentionally written with exceptional comments and clean
architecture so it can serve as a learning resource for Python developers
interested in real-world CLI tools, async I/O, data modeling, and respectful
web automation.

Core philosophy (baked into every module):
- CashorTrade is the highest-value source for staying near face value.
- Notifications are strictly gated by a hard price cap.
- Every listing ever seen is recorded forever (full history is sacred).
- Decisions are rich (price + reason + outcome) to enable future learning.
- The code should teach. If a new Python developer can't understand *why*
  something is done a certain way, we failed.

See README.md for usage and architecture overview.
"""

__version__ = "0.1.0"
