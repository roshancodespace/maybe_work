import sys
import os
import multiprocessing

multiprocessing.freeze_support()

if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)

from app.main import run_server

if __name__ == "__main__":
    run_server()
