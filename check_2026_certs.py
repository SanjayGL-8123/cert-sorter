import os
import sys
import re
import fitz
from PIL import Image
import winocr
import asyncio

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_2026 = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "Certification collect", "2026")

MONTHS = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

async def inspect_2026():
    if not os.path.exists(DIR_2026):
        print(f"Directory not found: {DIR_2026}")
        return

    files = sorted(os.listdir(DIR_2026))
    print(f"Total files in 2026: {len(files)}")
    
    for f in files:
        p = os.path.join(DIR_2026, f)
        ext = os.path.splitext(f)[1].lower()
        text = ""
        
        if ext == '.pdf':
            doc = fitz.open(p)
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
        elif ext in {'.jpg', '.jpeg', '.png', '.webp'}:
            img = Image.open(p).convert("RGBA")
            res = await winocr.recognize_pil(img, 'en')
            text = res.text
            
        # Clean text
        text_clean = " ".join(text.split())
        
        # Look for explicit dates like DD Month YYYY or Month DD, YYYY or DD/MM/YYYY
        date_patterns = re.findall(rf"\b(?:\d{{1,2}}\s+{MONTHS}\s+(202[0-9])|{MONTHS}\s+\d{{1,2}},?\s*(202[0-9])|\d{{1,2}}[-/]\d{{1,2}}[-/](202[0-9]))\b", text, re.IGNORECASE)
        # Flatten
        explicit_years = [y for tup in date_patterns for y in tup if y]
        
        all_2025 = len(re.findall(r"\b2025\b", text))
        all_2026 = len(re.findall(r"\b2026\b", text))
        all_2024 = len(re.findall(r"\b2024\b", text))
        
        # Check if filename has 2025
        fn_2025 = "2025" in f
        
        print(f"FILE: {f}")
        print(f"  Explicit date years: {explicit_years} | count 2024:{all_2024}, 2025:{all_2025}, 2026:{all_2026} | fn_2025: {fn_2025}")
        if all_2025 > 0 and (all_2025 >= all_2026 or explicit_years == ['2025'] or fn_2025):
            print(f"  >>> POTENTIAL 2025 CERTIFICATE! Preview: {text_clean[:180]}")
        print("-" * 50)

asyncio.run(inspect_2026())
