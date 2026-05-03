"""
wsgi.py - Production entry point for Gunicorn / Render
"""
import sys
import os

# Add backend to Python path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app import app, init_all_dbs

# Initialise all databases on startup
init_all_dbs()
