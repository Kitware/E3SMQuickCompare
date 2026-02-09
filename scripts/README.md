# QuickView Scripts

This directory contains utility scripts for maintaining and developing
QuickView.

## Scripts

### setup_tauri.sh

Prepares the Tauri desktop application for building by packaging the Python
application with PyInstaller. This creates platform-specific sidecar executables
for the Tauri app.

**Usage:**

```bash
# Run from project root (called by CI/CD workflow)
./scripts/setup_tauri.sh
```

This script:

- Creates a PyInstaller spec file
- Builds the Python application bundle
- Copies the bundle to the Tauri sidecar directory
- Prepares for Tauri desktop app compilation

**Note:** This is primarily used by the GitHub Actions workflow for automated
releases.
