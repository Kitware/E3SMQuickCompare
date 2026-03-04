"""Jupyter integration for QuickCompare via jupyter-server-proxy."""

from .proxy import setup_compareview, setup_quickcompare

# Backward compatibility alias.
setup_quickview = setup_compareview

__all__ = ["setup_compareview", "setup_quickcompare", "setup_quickview"]
