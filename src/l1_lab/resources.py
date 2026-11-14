"""Resources work both in an editable checkout and a noneditable wheel."""
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parents[1]
DATA_DIR = PACKAGE_DIR / "_data" if (PACKAGE_DIR / "_data").is_dir() else ROOT / "data"
MIGRATIONS_DIR = PACKAGE_DIR / "_migrations" if (PACKAGE_DIR / "_migrations").is_dir() else ROOT / "migrations"
LEARNING_DIR = PACKAGE_DIR / "_learning" if (PACKAGE_DIR / "_learning").is_dir() else ROOT / "docs/learning"
ARCHITECTURE_DIR = PACKAGE_DIR / "_architecture" if (PACKAGE_DIR / "_architecture").is_dir() else ROOT / "docs/architecture"
