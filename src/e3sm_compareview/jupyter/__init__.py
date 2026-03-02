"""Jupyter integration for CompareView via jupyter-server-proxy."""

from .proxy import setup_compareview

# Backward compatibility alias.
setup_quickview = setup_compareview

__all__ = ["setup_compareview", "setup_quickview"]
