# -*- coding: utf-8 -*-
"""Segment line-146 user_query into prose + labeled HTML/CSS dumps."""
import re
from pathlib import Path

src = Path(r"C:\Users\mercury\Desktop\tbank-mitm\_extract_uq.txt")
out_dir = Path(r"C:\Users\mercury\Desktop\tbank-mitm\_extract_parts")
out_dir.mkdir(exist_ok=True)

text = src.read_text(encoding="utf-8")

# Find prose-looking Russian lead-ins before big HTML dumps
markers = [
    "Во первых",
    "вот код элемента для плашки Пополнение",
    "во стиль к этой плашке",
    "Реквизиты",
    "квитан",
    "Трат в августе",
    "Все операции",
    "вот код",
    "вот стиль",
    "во стиль",
    "стиль к",
    "код элемента",
    "на главной",
    "скриншот",
]

# Split by transitions: Russian prose lines that introduce code
# Strategy: find all positions of "вот код" / "во стиль" / "вот стиль" / similar
intro_pat = re.compile(
    r"(?P<pre>(?:^|\n)[^\n]{0,300}?(?:вот код|во стиль|вот стиль|стиль к|код элемента|код для|html|css)[^\n]{0,200}\n)",
    re.I,
)

intros = list(intro_pat.finditer(text))
info = [f"total_len={len(text)}", f"intro_matches={len(intros)}"]
for i, m in enumerate(intros[:40]):
    snippet = m.group("pre").replace("\n", " | ")[:220]
    info.append(f"intro[{i}] @{m.start()}: {snippet}")

# Also find standalone short prose paragraphs (lines without < and not CSS-like)
# Extract first ~2500 chars of pure requirements (until first <div)
first_div = text.find("<div")
lead = text[:first_div] if first_div > 0 else text[:3000]
(out_dir / "00_lead_prose.txt").write_text(lead, encoding="utf-8")
info.append(f"first_div_at={first_div}")
info.append(f"lead_len={len(lead)}")

# Find all prose interjections between huge blocks: lines that are mostly Cyrillic and short
# Scan for sequences of Cyrillic prose not inside tags
prose_chunks = []
# Split on large HTML roots
parts = re.split(r"(?=(?:<div class=\"|<html|<style))", text)
info.append(f"split_parts={len(parts)}")

# For each part, if it starts with prose (not <), capture intro; if HTML, summarize size
summaries = []
for i, part in enumerate(parts):
    head = part[:400].replace("\n", " ")
    if part.lstrip().startswith("<"):
        # extract notable text content keywords
        titles = re.findall(r">([^<>]{2,80})</", part[:50000])
        titles = [t.strip() for t in titles if re.search(r"[А-Яа-яA-Za-z]", t)][:15]
        summaries.append(f"PART{i} HTML/CSS len={len(part)} titles={titles[:10]} head={head[:120]}")
        # Save truncated HTML (first 8k + last 1k) for key parts
        if i <= 12:
            trunc = part[:12000]
            if len(part) > 13000:
                trunc += "\n\n/* ... truncated ... */\n\n" + part[-2000:]
            (out_dir / f"part_{i:02d}_html.txt").write_text(trunc, encoding="utf-8")
    else:
        # prose
        prose = part.strip()
        if prose:
            summaries.append(f"PART{i} PROSE len={len(prose)}: {prose[:300].replace(chr(10),' ')}")
            (out_dir / f"part_{i:02d}_prose.txt").write_text(prose[:20000], encoding="utf-8")
            prose_chunks.append(prose)

# Collect all prose into one requirements file
all_prose = "\n\n====\n\n".join(prose_chunks)
(out_dir / "ALL_PROSE.txt").write_text(all_prose, encoding="utf-8")
info.append(f"prose_chunks={len(prose_chunks)}")
info.append(f"all_prose_len={len(all_prose)}")

# Search specific labels
for label in [
    "Пополнение",
    "Реквизиты",
    "Справка",
    "квитанц",
    "Трат в августе",
    "Все операции",
    "главной",
    "другого банка",
    "подсчёт",
    "подсчет",
    "доход",
    "трат",
]:
    idxs = [m.start() for m in re.finditer(re.escape(label), text)]
    info.append(f"label '{label}' count={len(idxs)} first10={idxs[:10]}")

# Extract CSS blocks that follow "стиль" intros more carefully
# Find text between prose intros and next prose
# Look for "Реквизиты" context windows
for kw in ["Реквизиты", "плашки Пополнение", "квитанц", "главной странице", "Трат в августе"]:
    pos = text.find(kw)
    if pos >= 0:
        window = text[max(0, pos - 200) : pos + 800]
        (out_dir / f"ctx_{kw[:20].replace(' ', '_')}.txt").write_text(window, encoding="utf-8")

(out_dir / "INFO.txt").write_text("\n".join(info + ["", "=== SUMMARIES ==="] + summaries), encoding="utf-8")
print("wrote", out_dir)
print("\n".join(info[:60]))
print("---")
print("\n".join(summaries[:30]))
