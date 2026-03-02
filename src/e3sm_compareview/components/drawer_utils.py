from e3sm_quickview.utils import js

DRAWER_TRANSITION_STYLE = "transition: none !important;"


def drawer_style(tool_name):
    return (
        f"{js.is_active(tool_name)} ? "
        f"'transform: none; {DRAWER_TRANSITION_STYLE}' : "
        f"'{DRAWER_TRANSITION_STYLE}'"
    )
