"""Delete local state for a clean run."""

import shutil

from .config import DATA_DIR

shutil.rmtree(DATA_DIR, ignore_errors=True)
print(f"Removed {DATA_DIR}")
