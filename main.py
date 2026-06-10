#!/usr/bin/env python3
"""WP Plugin Review Assistant - Main entry point."""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ui.main_window import main

if __name__ == "__main__":
    main()
