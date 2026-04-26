import sys
import os

# Add backend folder to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app import app, init_med_db

init_med_db()

if __name__ == "__main__":
    app.run()