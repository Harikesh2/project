#!/usr/bin/env python3
"""
Script to set up DynamoDB tables for the social media application.
Run this script after setting up your environment variables.
"""

import sys
import os
import logging

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.database.setup import create_all_tables

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Setting up DynamoDB tables for Social Media App...")
    print("Make sure your AWS credentials and environment variables are configured.")
    print()
    
    try:
        create_all_tables()
        print("\nDatabase setup completed successfully!")
        print("You can now start the FastAPI server.")
    except Exception as e:
        print(f"\nDatabase setup failed: {e}")
        sys.exit(1)