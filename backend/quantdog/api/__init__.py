"""API module (Flask).

Scaffold-only: minimal app factory and a health endpoint.
"""

# pyright: reportUnknownVariableType=false

from .app import create_app

__all__ = [
    "create_app",
]
