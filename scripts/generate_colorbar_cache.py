#!/usr/bin/env python3
"""
Standalone script to generate colorbar cache for CompareView.
This script generates base64-encoded PNG images for all supported colormaps
in both normal and inverted forms.

Usage:
    python generate_colorbar_cache.py > colorbar_cache_output.py
"""

import sys

from paraview.simple import GetColorTransferFunction, GetLookupTableNames

from e3sm_quickview.presets import COLOR_BLIND_SAFE
from e3sm_quickview.utils.color import build_colorbar_image

noncvd = [
    {
        "text": "Rainbow Desat.",
        "value": "Rainbow Desaturated",
    },
    {
        "text": "Yellow-Gray-Blue",
        "value": "Yellow - Gray - Blue",
    },
    {
        "text": "Blue Orange (div.)",
        "value": "Blue Orange (divergent)",
    },
    {
        "text": "Cool to Warm (Ext.)",
        "value": "Cool to Warm (Extended)",
    },
    {
        "text": "Black-Body Rad.",
        "value": "Black-Body Radiation",
    },
    {
        "text": "Blue-Green-Orange",
        "value": "Blue - Green - Orange",
    },
]

cvd = [
    {
        "text": "Inferno (matplotlib)",
        "value": "Inferno (matplotlib)",
    },
    {
        "text": "Viridis (matplotlib)",
        "value": "Viridis (matplotlib)",
    },
]

# Load CVD-safe presets exposed by the package.
try:
    existing = GetLookupTableNames()
    for name in sorted(COLOR_BLIND_SAFE):
        if name in existing:
            cvd.append({"text": name.title(), "value": name})
except Exception as e:
    print(f"# Error loading presets: {e}", file=sys.stderr)

# Combine all colormaps
all_colormaps = cvd + noncvd

print("# Auto-generated colorbar cache")
print("# Generated using generate_colorbar_cache.py")
print()
print("COLORBAR_CACHE = {")

for colormap in all_colormaps:
    colormap_name = colormap["value"]
    print(f'    "{colormap_name}": {{')

    try:
        # Get the color transfer function
        lut = GetColorTransferFunction("dummy_var")
        lut.ApplyPreset(colormap_name, True)

        # Generate normal colorbar
        normal_image = build_colorbar_image(lut, log_scale=False, invert=False)
        print(f'        "normal": "{normal_image}",')

        # Invert the transfer function
        lut.InvertTransferFunction()

        # Generate inverted colorbar
        inverted_image = build_colorbar_image(lut, log_scale=False, invert=False)
        print(f'        "inverted": "{inverted_image}",')

        # Reset for next iteration
        lut.InvertTransferFunction()  # Revert back to normal

    except Exception as e:
        print(f"# Error processing {colormap_name}: {e}", file=sys.stderr)
        print('        "normal": "",')
        print('        "inverted": "",')

    print("    },")

print("}")
