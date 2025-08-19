#!/usr/bin/env python3
"""
Test ScreenAlert logging setup
"""

# Import the setup_logging function
import sys
import os
sys.path.append('.')

from screenalert import setup_logging, get_app_data_dir
import logging

def test_logging():
    """Test that logging is working properly"""
    print("Testing ScreenAlert logging setup...")
    
    # Setup logging
    log_path = setup_logging()
    print(f"Log file created at: {log_path}")
    
    # Test various log levels
    logging.debug("This is a debug message")
    logging.info("This is an info message")
    logging.warning("This is a warning message")
    logging.error("This is an error message")
    
    # Check if log file exists and has content
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            content = f.read()
            print(f"Log file content ({len(content)} characters):")
            print("-" * 50)
            print(content)
            print("-" * 50)
    else:
        print("ERROR: Log file was not created!")
    
    # Show log directory
    log_dir = os.path.dirname(log_path)
    print(f"\nLog directory: {log_dir}")
    print("Files in log directory:")
    for file in os.listdir(log_dir):
        file_path = os.path.join(log_dir, file)
        size = os.path.getsize(file_path)
        print(f"  {file} ({size} bytes)")

if __name__ == "__main__":
    test_logging()
