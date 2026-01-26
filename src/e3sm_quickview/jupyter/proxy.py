"""Server proxy configuration for QuickView in JupyterLab."""

import os


def setup_quickview():
    """Configure jupyter-server-proxy for QuickView.

    Returns a dictionary with the server process configuration that
    jupyter-server-proxy uses to launch and proxy QuickView.
    """
    icon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "icons",
        "quickview.png",
    )

    return {
        "command": [
            "quickview",
            "--server",
            "--port",
            "{port}",
            "--host",
            "127.0.0.1",
        ],
        "timeout": 30,
        "launcher_entry": {
            "enabled": True,
            "title": "QuickView",
            "icon_path": icon_path,
            "category": "Other",
        },
        "new_browser_tab": False,
    }
