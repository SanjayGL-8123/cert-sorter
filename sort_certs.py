import os
import sys
import re
import shutil
import hashlib
import asyncio
from datetime import datetime
from collections import Counter

# Safe UTF-8 console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Optional library imports with clear guidance
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    print("Notice: PyMuPDF not found. Please run with Python 3.12 (e.g., `py -3.12 sort_certs.py`).")

try:
    from PIL import Image, ExifTags
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import winocr
    HAS_WINOCR = True
except ImportError:
    HAS_WINOCR = False

# ==================== CONFIGURATION ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_FOLDER = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "Certification collect")
SUPPORTED_YEARS = ["2023", "2024", "2025", "2026", "2027"]
SPECIAL_FOLDERS = ["Duplicates", "Not Readable"]

PDF_EXT = {".pdf"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]
MONTH_REGEX = r"(?:" + "|".join(MONTH_NAMES) + r")"

KNOWN_TOPIC_YEARS = [
    ("pravidhi", "2026"),
    ("road safety", "2026"),
    ("safe & responsible", "2026"),
    ("responsible use", "2026"),
    ("cyber security awareness month", "2025"),
    ("becybersmart", "2025"),
    ("cybcadet", "2025"),
    ("cyber cadet", "2025"),
    ("blood donate second time", "2025"),
    ("police gun camp", "2025"),
    ("blood donate first time", "2024"),
    ("blood donation", "2025"),
    ("nss camp", "2024"),
    ("mybharat", "2024"),
    ("my bharat", "2024"),
    ("youth for seva", "2024"),
    ("great learning", "2025"),
    ("front end development", "2025"),
    ("copilot", "2025"),
]
# =======================================================


def setup_directories(base_folder, years):
    for folder in years + SPECIAL_FOLDERS:
        os.makedirs(os.path.join(base_folder, folder), exist_ok=True)


def safe_move(src_path, dest_folder):
    stem, ext = os.path.splitext(os.path.basename(src_path))
    target_dir = os.path.join(SOURCE_FOLDER, dest_folder)
    os.makedirs(target_dir, exist_ok=True)

    dest_path = os.path.join(target_dir, os.path.basename(src_path))
    counter = 1
    while os.path.exists(dest_path):
        if os.path.abspath(src_path) == os.path.abspath(dest_path):
            return dest_path
        dest_path = os.path.join(target_dir, f"{stem} ({counter}){ext}")
        counter += 1

    shutil.move(src_path, dest_path)
    return dest_path


def compute_file_hash(path):
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


async def get_text_and_ocr(path):
    ext = os.path.splitext(path)[1].lower()
    text = ""
    if ext == ".pdf" and HAS_FITZ:
        try:
            doc = fitz.open(path)
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
        except Exception:
            pass

    if len(text.strip()) < 30 and HAS_PIL:
        try:
            if ext == ".pdf" and HAS_FITZ:
                doc = fitz.open(path)
                if len(doc) > 0:
                    pix = doc[0].get_pixmap(dpi=150)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")
                    if HAS_WINOCR:
                        res = await winocr.recognize_pil(img, "en")
                        text += "\n" + res.text
                doc.close()
            elif ext in IMG_EXT and HAS_WINOCR:
                img = Image.open(path).convert("RGBA")
                res = await winocr.recognize_pil(img, "en")
                text = res.text
        except Exception:
            pass

    return text


def parse_true_year(filename, text):
    clean_text = " ".join(text.split())

    # 1. Cursa platform: "Course taken between ... and Month DD, YYYY"
    cursa_match = re.findall(rf"(?:course taken between|between|until|to)\s+.*?{MONTH_REGEX}\s+\d{{1,2}},?\s*(202[3-7])", clean_text, re.IGNORECASE)
    if cursa_match:
        return cursa_match[-1]

    # 2. Microsoft Learn / Coursera: "completed ... Month DD, YYYY"
    completed_match = re.findall(rf"(?:completed|awarded|issued on:?|on:?)\s+.*?({MONTH_REGEX}\s+\d{{1,2}},?\s*(202[3-7])|\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH_REGEX}\s+(202[3-7]))", clean_text, re.IGNORECASE)
    if completed_match:
        for tup in completed_match:
            for item in tup:
                y = re.findall(r"(202[3-7])", item)
                if y:
                    return y[0]

    # 3. Explicit Named dates in text
    named_dates = re.findall(rf"\b({MONTH_REGEX}\s+\d{{1,2}},?\s*(202[3-7])|\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH_REGEX}\s+(202[3-7]))\b", clean_text, re.IGNORECASE)
    if named_dates:
        years_in_named = []
        for tup in named_dates:
            for item in tup:
                y = re.findall(r"(202[3-7])", item)
                if y:
                    years_in_named.append(y[0])
        if "2025" in years_in_named and "2026" in years_in_named:
            # Certificate completion in 2025 takes precedence over print header in 2026
            return "2025"
        elif "2025" in years_in_named:
            return "2025"
        elif "2026" in years_in_named:
            return "2026"
        elif "2024" in years_in_named:
            return "2024"

    # 4. Event / Quiz Year in text
    event_year = re.findall(r"\b(?:quiz|camp|fest|diwas|hackathon|yoga|contest|month)\s*.*?(202[3-7])\b", clean_text, re.IGNORECASE)
    if event_year:
        return event_year[0]

    # 5. Filename analysis (excluding WhatsApp Image 2026-01-14 export prefix)
    if not filename.startswith("WhatsApp Image 2026-01-14"):
        fn_match = re.findall(r"(?<!\d)(202[3-7])(?!\d)", filename)
        if fn_match:
            return fn_match[0]
        oplus = re.search(r"OplusInfoCollection_(2[3-7])(0[1-9]|1[0-2])", filename)
        if oplus:
            return f"20{oplus.group(1)}"

    # 6. WhatsApp batch received on 2026-01-14
    if filename.startswith("WhatsApp Image 2026-01-14"):
        raw_2025 = re.findall(r"(?<!\d)2025(?!\d)", clean_text)
        if raw_2025 or len(clean_text) < 30:
            return "2025"

    # 7. Topic mapping
    fn_lower = filename.lower()
    txt_lower = clean_text.lower()
    for topic, yr in KNOWN_TOPIC_YEARS:
        if topic in fn_lower or topic in txt_lower:
            return yr

    # 8. Most frequent text year
    all_years = re.findall(r"(?<!\d)(202[3-7])(?!\d)", clean_text)
    if all_years:
        return Counter(all_years).most_common(1)[0][0]

    return None


async def organize_and_rebalance():
    if not os.path.exists(SOURCE_FOLDER):
        print(f"Notice: Source folder '{SOURCE_FOLDER}' not found. Creating directory structure...")
        os.makedirs(SOURCE_FOLDER, exist_ok=True)
    setup_directories(SOURCE_FOLDER, SUPPORTED_YEARS)

    all_files = []
    # 1. Root files
    for name in os.listdir(SOURCE_FOLDER):
        p = os.path.join(SOURCE_FOLDER, name)
        if os.path.isfile(p):
            ext = os.path.splitext(name)[1].lower()
            if ext in (PDF_EXT | IMG_EXT):
                all_files.append((p, "(root)"))

    # 2. Existing folder files to re-balance
    for folder in SUPPORTED_YEARS + SPECIAL_FOLDERS:
        fdir = os.path.join(SOURCE_FOLDER, folder)
        if os.path.isdir(fdir):
            for name in os.listdir(fdir):
                p = os.path.join(fdir, name)
                if os.path.isfile(p):
                    ext = os.path.splitext(name)[1].lower()
                    if ext in (PDF_EXT | IMG_EXT):
                        all_files.append((p, folder))

    print(f"Total files in collection: {len(all_files)}")

    # Dedup check
    seen_hashes = {}
    moved_count = 0

    for p, current_folder in all_files:
        filename = os.path.basename(p)
        f_hash = compute_file_hash(p)

        if f_hash in seen_hashes and seen_hashes[f_hash] != p:
            if current_folder != "Duplicates":
                safe_move(p, "Duplicates")
                moved_count += 1
                print(f"[Duplicate] {current_folder} -> Duplicates: {filename}")
            continue
        seen_hashes[f_hash] = p

        if current_folder == "Duplicates":
            continue

        text = await get_text_and_ocr(p)
        true_year = parse_true_year(filename, text)

        if true_year and true_year != current_folder:
            safe_move(p, true_year)
            moved_count += 1
            print(f"[Relocated] {current_folder} -> {true_year}: {filename}")
        elif not true_year and current_folder not in ["Not Readable", "Duplicates"]:
            safe_move(p, "Not Readable")
            moved_count += 1
            print(f"[Uncertain] {current_folder} -> Not Readable: {filename}")

    print("\n" + "=" * 50)
    print("ALL FOLDERS CHECKED & SYNCHRONIZED")
    print("=" * 50)
    for folder in SUPPORTED_YEARS + SPECIAL_FOLDERS:
        f_path = os.path.join(SOURCE_FOLDER, folder)
        cnt = len(os.listdir(f_path)) if os.path.exists(f_path) else 0
        print(f"  Folder [{folder:12}]: {cnt} files")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(organize_and_rebalance())