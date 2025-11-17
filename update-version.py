#!/usr/bin/env python3
"""
Script to update the fallback version in screenalert.py to match the latest git tag.
Run this script before building/releasing to ensure the fallback version is current.
"""

import subprocess
import sys
import os
import re

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

def update_fallback_version(version):
    """Update the fallback version in screenalert.py"""
    script_path = os.path.join(os.path.dirname(__file__), 'screenalert.py')
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match the fallback version line
        pattern = r'(# Fallback version if git tag detection fails\s+return\s+)"[\d\.]+"'
        replacement = rf'\1"{version}"'
        
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✅ Updated fallback version to {version}")
            return True
        else:
            print(f"⚠️  No changes needed (already {version})")
            return False
            
    except Exception as e:
        print(f"❌ Error updating file: {e}")
        return False

def main():
    git_version = get_git_version()
    
    if not git_version:
        print("❌ Could not determine version from git tags")
        return 1
    
    print(f"Git tag version: {git_version}")
    
    if update_fallback_version(git_version):
        print(f"✅ Fallback version updated successfully")
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
