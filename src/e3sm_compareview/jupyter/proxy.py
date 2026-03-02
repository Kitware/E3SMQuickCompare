"""Server proxy configuration for CompareView in JupyterLab."""

import os


def setup_compareview():
    """Configure jupyter-server-proxy for CompareView."""
    icon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "icons",
        "compareview.png",
    )

    return {
        "command": [
            "compareview",
            "--server",
            "--port",
            "{port}",
            "--host",
            "127.0.0.1",
        ],
        "timeout": 30,
        "launcher_entry": {
            "enabled": True,
            "title": "CompareView",
            "icon_path": icon_path,
            "category": "Other",
        },
        "new_browser_tab": False,
    }
