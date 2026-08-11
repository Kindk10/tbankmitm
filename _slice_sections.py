# -*- coding: utf-8 -*-
import re
from pathlib import Path

text = Path(r"C:\Users\mercury\Desktop\tbank-mitm\_extract_uq.txt").read_text(encoding="utf-8")
out = Path(r"C:\Users\mercury\Desktop\tbank-mitm\_extract_parts")
out.mkdir(exist_ok=True)

# Known section intros from previous run (search by unique Russian phrases)
section_keys = [
    ("01_popolnenie_html", "вот код элемента для плашки Пополнение"),
    ("02_popolnenie_css", "во стиль к этой плашке"),
    ("03_rekvizity_html", "вот код элемента к плашке Реквизиты"),
    ("04_receipt_window", "вот код элемента к окну открытия квитанции"),
    ("05_home_compare", "вот код элемента окна для сверки на главной"),
    ("06_home_etalon", "вот код элемента на эталонном варианте с главной"),
    ("07_receipt_sum", "вот код элемента для плашки суммы в окне квитанции"),
    ("08_receipt_rekvizity", "вот код элемента для плашки реквизиты в окне квитанции"),
    ("09_receipt_tile", "вот код элемента как на плашке на окне открытия"),
]

# Also try fuzzy finds for variants
extra_searches = [
    "вот код элемента",
    "во стиль",
    "вот стиль",
    "стиль к этой",
    "эталон",
    "сверки",
    "квитанц",
]

found = []
for key, needle in section_keys:
    pos = text.find(needle)
    found.append((pos, key, needle))

# Find ALL "вот код" / "во стиль" / "вот стиль" intros with surrounding context
pat = re.compile(r".{0,80}(?:вот код|во стиль|вот стиль).{0,120}", re.I | re.S)
matches = []
for m in pat.finditer(text):
    # skip if deep inside huge html (heuristic: look at previous 20 chars for <)
    start = m.start()
    ctx_before = text[max(0, start - 5) : start]
    snippet = m.group(0).replace("\n", " ")
    # Only keep if looks like prose intro (has colon near end or short)
    if "<div" in snippet and snippet.find("<div") < 40:
        continue
    matches.append((start, snippet[:200]))

# Deduplicate nearby matches
dedup = []
for start, snip in matches:
    if dedup and start - dedup[-1][0] < 50:
        continue
    dedup.append((start, snip))

report = ["ALL INTROS:"]
for start, snip in dedup:
    report.append(f"@{start}: {snip}")

report.append("\nSECTION KEYS:")
for pos, key, needle in found:
    report.append(f"{key}: pos={pos}")

# Slice sections between intros that were found
valid = [(pos, key, needle) for pos, key, needle in found if pos >= 0]
valid.sort()

# Also include lead
lead_end = valid[0][0] if valid else 1096
Path(out / "00_requirements_prose.txt").write_text(text[:lead_end].strip() + "\n", encoding="utf-8")

# Add end sentinel
bounds = valid + [(len(text), "END", "")]
for i in range(len(bounds) - 1):
    pos, key, needle = bounds[i]
    next_pos = bounds[i + 1][0]
    chunk = text[pos:next_pos].strip()
    # For HTML sections: save full if small, else truncate with note
    meta = f"KEY={key}\nNEEDLE={needle}\nSTART={pos}\nEND={next_pos}\nLEN={len(chunk)}\n\n"
    if len(chunk) <= 80000:
        Path(out / f"{key}.txt").write_text(meta + chunk, encoding="utf-8")
    else:
        # Keep first 25k and search for meaningful inner text labels
        labels = re.findall(r">([А-Яа-яA-Za-z0-9][^<>]{1,60})<", chunk[:100000])
        uniq = []
        for lab in labels:
            lab = lab.strip()
            if lab and lab not in uniq and not lab.startswith("http"):
                uniq.append(lab)
            if len(uniq) >= 40:
                break
        trunc = chunk[:25000] + "\n\n/* === TRUNCATED === */\n\n" + chunk[-3000:]
        Path(out / f"{key}.txt").write_text(
            meta + "INNER_LABELS=\n" + "\n".join(uniq) + "\n\n" + trunc, encoding="utf-8"
        )

# Extract any remaining prose after big dumps - look for short Cyrillic sentences
# between sections that aren't HTML
more_prose = []
for start, snip in dedup:
    # get line containing intro
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = start + 200
    line = text[start:line_end].strip()
    if line and not line.startswith("<"):
        more_prose.append(f"@{start}: {line}")

Path(out / "INTROS_REPORT.txt").write_text("\n".join(report + ["", "PROSE INTRO LINES:"] + more_prose), encoding="utf-8")

# Also dump a compact requirements-only extract by removing HTML/CSS dumps
# Keep lines that are prose intros + lead
compact = [text[:lead_end].strip(), ""]
for start, snip in dedup:
    line_end = text.find("\n", start)
    line = text[start:line_end].strip() if line_end > start else snip
    if "<a href" in line or "nojswarning" in line:
        continue
    if line.startswith("<"):
        continue
    compact.append(line)

Path(out / "COMPACT_REQUIREMENTS.txt").write_text("\n".join(compact), encoding="utf-8")
print("sections", len(valid))
print("intros", len(dedup))
print("done")
