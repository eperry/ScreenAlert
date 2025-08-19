#!/usr/bin/env python3
"""
Script to verify that the application version matches the latest git tag.
This can be run manually or as part of a release process.
"""

import subprocess
import sys
import os

def get_git_version():
    """Get version from latest git tag"""
    try:
        result = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'], 
                              capture_output=True, text=True, cwd=os.path.dirname(__file__) or '.')
        if result.returncode == 0 and result.stdout.strip():
            version = result.stdout.strip()
            return version[1:] if version.startswith('v') else version
    except Exception as e:
        print(f"Error getting git version: {e}")
    return None

def get_app_version():
    """Get version from the application"""
    try:
        # Import the module to get the detected version
        sys.path.insert(0, os.path.dirname(__file__) or '.')
        import screenalert
        return screenalert.APP_VERSION
    except Exception as e:
        print(f"Error getting app version: {e}")
    return None

def main():
    git_version = get_git_version()
    app_version = get_app_version()
    
    print(f"Git tag version: {git_version}")
    print(f"App version: {app_version}")
    
    if git_version and app_version and git_version == app_version:
        print("✅ Versions match!")
        return 0
    else:
        print("❌ Version mismatch!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
