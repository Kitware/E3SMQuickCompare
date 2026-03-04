"""Server proxy configuration for QuickCompare in JupyterLab."""

import os


def setup_compareview():
    """Configure jupyter-server-proxy for QuickCompare."""
    return setup_quickcompare()


def setup_quickcompare():
    """Configure jupyter-server-proxy for QuickCompare."""
    icon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "icons",
        "compareview.png",
    )

    return {
        "command": [
            "quickcompare",
            "--server",
            "--port",
            "{port}",
            "--host",
            "127.0.0.1",
        ],
        "timeout": 30,
        "launcher_entry": {
            "enabled": True,
            "title": "QuickCompare",
            "icon_path": icon_path,
            "category": "Other",
        },
        "new_browser_tab": False,
    }
