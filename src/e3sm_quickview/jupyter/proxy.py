"""Server proxy configuration for QuickView in JupyterLab."""

from pathlib import Path


def setup_quickview():
    """Configure jupyter-server-proxy for QuickView.

    Returns a dictionary with the server process configuration that
    jupyter-server-proxy uses to launch and proxy QuickView.
    """
    icon_path = Path(__file__).with_name("icons") / "web.svg"

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
            "title": "E3SM QuickView",
            "icon_path": str(icon_path.resolve()),
            "category": "Other",
        },
        "new_browser_tab": False,
    }
