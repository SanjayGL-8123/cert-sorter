import os
import sys
import re
import asyncio
from collections import Counter
from datetime import datetime
import fitz  # PyMuPDF
from PIL import Image, ExifTags
import winocr

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOT_READABLE_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "Certification collect", "Not Readable")

if not os.path.exists(NOT_READABLE_DIR):
    print(f"Directory not found: {NOT_READABLE_DIR}")
    files = []
else:
    files = [f for f in os.listdir(NOT_READABLE_DIR) if os.path.isfile(os.path.join(NOT_READABLE_DIR, f))]
print(f"Total files in Not Readable: {len(files)}")

def extract_year_from_filename(name):
    match_ymd = re.findall(r"(202[0-9])(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])", name)
    if match_ymd:
        return match_ymd[0]
    ts_match = re.findall(r"\b(1[67][0-9]{8,11})\b", name)
    if ts_match:
        try:
            ts = int(ts_match[0])
            if ts > 1e11:
                ts /= 1000
            dt = datetime.fromtimestamp(ts)
            if 2020 <= dt.year <= 2027:
                return str(dt.year)
        except Exception:
            pass
    match_y = re.findall(r"\b(202[0-9])\b", name)
    if match_y:
        return match_y[0]
    return None

def extract_from_pdf(path):
    years = []
    try:
        doc = fitz.open(path)
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        if full_text.strip():
            found = re.findall(r"\b(202[0-9])\b", full_text)
            years.extend(found)
        meta = doc.metadata or {}
        for k in ['creationDate', 'modDate']:
            val = meta.get(k, '')
            if val:
                m = re.findall(r"(202[0-9])", val)
                years.extend(m)
        doc.close()
    except Exception:
        pass
    return years

def extract_from_exif(path):
    years = []
    try:
        img = Image.open(path)
        exif = img.getexif()
        if exif:
            for tag_id, val in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                if 'date' in str(tag_name).lower() or 'time' in str(tag_name).lower():
                    m = re.findall(r"(202[0-9])", str(val))
                    years.extend(m)
    except Exception:
        pass
    return years

async def ocr_image(path):
    try:
        img = Image.open(path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        res = await winocr.recognize_pil(img, 'en')
        return res.text
    except Exception as e:
        return ""

async def test_all():
    resolved = Counter()
    unresolved = []
    
    for i, f in enumerate(files):
        path = os.path.join(NOT_READABLE_DIR, f)
        ext = os.path.splitext(f)[1].lower()
        candidates = []
        
        # 1. Filename
        fn_y = extract_year_from_filename(f)
        if fn_y:
            candidates.append(fn_y)
            candidates.append(fn_y) # extra weight
            
        # 2. PDF text & metadata
        if ext == '.pdf':
            candidates.extend(extract_from_pdf(path))
            
        # 3. EXIF
        if ext in {'.jpg', '.jpeg', '.png', '.webp'}:
            candidates.extend(extract_from_exif(path))
            
        # 4. OCR if still unresolved
        if not candidates:
            if ext in {'.jpg', '.jpeg', '.png', '.webp'}:
                text = await ocr_image(path)
                found = re.findall(r"\b(202[0-9])\b", text)
                candidates.extend(found)
            elif ext == '.pdf':
                # rasterize first page to image
                try:
                    doc = fitz.open(path)
                    if len(doc) > 0:
                        pix = doc[0].get_pixmap(dpi=150)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")
                        res = await winocr.recognize_pil(img, 'en')
                        found = re.findall(r"\b(202[0-9])\b", res.text)
                        candidates.extend(found)
                    doc.close()
                except Exception:
                    pass
                    
        if candidates:
            best = Counter(candidates).most_common(1)[0][0]
            resolved[best] += 1
        else:
            unresolved.append(f)
            
    print("\nResolution results:")
    for y, count in sorted(resolved.items()):
        print(f"  {y}: {count} files")
    print(f"Still unresolved: {len(unresolved)} files")
    for u in unresolved[:20]:
        print("  -", u)

asyncio.run(test_all())
