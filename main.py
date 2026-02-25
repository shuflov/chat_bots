"""
Main entry point for Chat Bot Conversations.

This file now simply imports and runs the server module.
Use server.py for more options (CLI-only mode, web server).

Usage:
    python main.py                    # Run web server
    python main.py --cli              # Run CLI-only mode
    python main.py --web              # Run web server explicitly
    python main.py --cli -t 10        # CLI mode with 10 turns

Or use server.py directly:
    python server.py                  # Run web server
    python server.py --cli            # Run CLI-only mode
    python server.py --help           # Show all options
"""

import sys
import os

# Check for API key early
if not os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") == "your_groq_api_key_here":
    print("Error: GROQ_API_KEY not set in .env")
    print("Get your key at: https://console.groq.com/")
    print("\nEdit .env file and add your key, then run again.")
    sys.exit(1)

# Import and run the server module
from server import main as server_main

if __name__ == "__main__":
    server_main()
