import os
import sys
import re
import hashlib
from collections import Counter
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    from PIL import Image, ExifTags
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

FOLDER = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "Certification collect")

print(f"Scanning directory: {FOLDER}")
if not os.path.exists(FOLDER):
    print("Folder does not exist.")
    sys.exit(1)

total_files = 0
folder_counts = {}

for root, dirs, files in os.walk(FOLDER):
    rel = os.path.relpath(root, FOLDER)
    folder_name = rel if rel != "." else "(root)"
    valid_files = [f for f in files if os.path.splitext(f)[1].lower() in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}]
    if valid_files:
        folder_counts[folder_name] = len(valid_files)
        total_files += len(valid_files)

print("=" * 45)
print(f"Total Certification Files Found: {total_files}")
print("=" * 45)
for f_name, cnt in sorted(folder_counts.items()):
    print(f"  📁 {f_name:20}: {cnt} files")
print("=" * 45)