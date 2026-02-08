#!/usr/bin/env python3
"""
Build script for adLibre DNS Changer
Run this on each target platform to generate the executable.
"""
import subprocess
import sys
import shutil
from pathlib import Path

# Get the directory where this script lives
SCRIPT_DIR = Path(__file__).parent.resolve()

def clean_build():
    """Remove previous build artifacts."""
    dirs_to_remove = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_remove:
        path = SCRIPT_DIR / dir_name
        if path.exists():
            shutil.rmtree(path)
            print(f"Removed {dir_name}/")

def install_dependencies():
    """Install required packages."""
    subprocess.run([
        sys.executable, '-m', 'pip', 'install', '-r', str(SCRIPT_DIR / 'requirements.txt')
    ], check=True)

def build_executable():
    """Build the executable using PyInstaller."""
    spec_file = SCRIPT_DIR / 'adlibre.spec'
    subprocess.run([
        sys.executable, '-m', 'PyInstaller',
        str(spec_file),
        '--clean',
        '--noconfirm',
        '--distpath', str(SCRIPT_DIR / 'dist'),
        '--workpath', str(SCRIPT_DIR / 'build'),
    ], check=True)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Build adLibre executable')
    parser.add_argument('--clean', action='store_true', help='Clean build artifacts only')
    parser.add_argument('--skip-deps', action='store_true', help='Skip dependency installation')
    args = parser.parse_args()

    if args.clean:
        clean_build()
        return

    print("=" * 50)
    print("Building adLibre DNS Changer")
    print("=" * 50)

    # Clean previous builds
    print("\n[1/3] Cleaning previous builds...")
    clean_build()

    # Install dependencies
    if not args.skip_deps:
        print("\n[2/3] Installing dependencies...")
        install_dependencies()
    else:
        print("\n[2/3] Skipping dependency installation...")

    # Build
    print("\n[3/3] Building executable...")
    build_executable()

    # Report results
    dist_path = SCRIPT_DIR / 'dist'
    if sys.platform == 'darwin':
        app_path = dist_path / 'adLibre.app'
        if app_path.exists():
            print(f"\n✓ Build successful!")
            print(f"  macOS app: {app_path}")
            print(f"\n  To create a DMG installer, run:")
            print(f"  hdiutil create -volname 'adLibre' -srcfolder dist/adLibre.app -ov -format UDZO dist/adLibre.dmg")
    else:
        exe_path = dist_path / 'adLibre.exe'
        if exe_path.exists():
            print(f"\n✓ Build successful!")
            print(f"  Windows executable: {exe_path}")

if __name__ == '__main__':
    main()