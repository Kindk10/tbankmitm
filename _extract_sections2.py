# -*- coding: utf-8 -*-
import re
from pathlib import Path

text = Path(r"C:\Users\mercury\Desktop\tbank-mitm\_extract_uq.txt").read_text(encoding="utf-8")
out = Path(r"C:\Users\mercury\Desktop\tbank-mitm\_extract_parts")

# Exact intros
needles = [
    ("01_popolnenie_tile", "вот код элемента для плашки Пополнение, в операции поступления из другого банка:"),
    ("02_popolnenie_style", "во стиль к этой плашке:"),
    ("03_rekvizity_tile", "вот код элемента к плашке Реквизиты, в операции пополнения из другого банка:"),
    ("04_popolnenie_whole_op", "вот код элемента в целом операции пополнения из другого банка:"),
    ("05_receipt_check", "вот код элемента чека при нажатии на справку в операциях пополнения из другого банка:"),
    ("06_transfer_op", "вот код элемента на операции перевода в другой банк:"),
    ("07_perevod_tile", "вот код элемента для плашки Перевод в этих операциях:"),
    ("08_rekvizity_transfer", "вот код элемента для плашки Реквизиты в этих переводах:"),
    ("09_more_tiles", "вот код элемента ещё от плашек на этой странице:"),
]

found = []
for key, needle in needles:
    pos = text.find(needle)
    print(f"{key}: {pos}")
    found.append((pos, key, needle))

# Also search style intros
for alt in ["во стиль к этой плашке:", "вот стиль к этой плашке:", "стиль к этой плашке:"]:
    print("alt", alt, text.find(alt))

valid = sorted([(p, k, n) for p, k, n in found if p >= 0])
bounds = valid + [(len(text), "END", "")]

def summarize_html(chunk, max_labels=50):
    labels = []
    for m in re.finditer(r">([^<>]{1,80})<", chunk):
        lab = m.group(1).strip()
        if not lab:
            continue
        if lab.startswith(("http", "var(", "calc(", "--", "{", "}")):
            continue
        if re.fullmatch(r"[\d\s\.,\u00a0₽+\-:%]+", lab):
            # keep money-like
            if "₽" in lab or re.search(r"\d", lab):
                pass
            else:
                continue
        if lab not in labels:
            labels.append(lab)
        if len(labels) >= max_labels:
            break
    qa = list(dict.fromkeys(re.findall(r'data-qa-type="([^"]+)"', chunk)))[:40]
    return labels, qa

report = []
for i in range(len(bounds) - 1):
    pos, key, needle = bounds[i]
    next_pos = bounds[i + 1][0]
    # content after the needle line
    start = pos + len(needle)
    chunk = text[start:next_pos].strip()
    labels, qa = summarize_html(chunk)
    report.append(f"=== {key} len={len(chunk)} ===")
    report.append(f"needle: {needle}")
    report.append("LABELS: " + " | ".join(labels[:30]))
    report.append("QA: " + " | ".join(qa[:25]))
    # Save useful excerpt: if starts with <div take first 6k chars of HTML;
    # if body/iframe take first 3k + search for key visible strings
    if chunk.startswith("<div") or chunk.startswith("<button") or chunk.startswith("<section"):
        excerpt = chunk[:8000]
    elif chunk.startswith("<body") or chunk.startswith("<!DOCTYPE") or chunk.startswith("<html"):
        excerpt = chunk[:4000]
        # also pull style tag snippets related to receipt
    else:
        # likely CSS starting after "во стиль"
        excerpt = chunk[:6000]
    Path(out / f"{key}.txt").write_text(
        f"KEY={key}\nLEN={len(chunk)}\nNEEDLE={needle}\n\nLABELS:\n"
        + "\n".join(labels)
        + "\n\nQA:\n"
        + "\n".join(qa)
        + "\n\nEXCERPT:\n"
        + excerpt,
        encoding="utf-8",
    )

# Home typography: search for Трат near HTML in later? or only in lead
for kw in ["Трат в августе", "Все операции", "molecule-spendings", "spendings", "cashflow", "expenses"]:
    idxs = [m.start() for m in re.finditer(kw, text)]
    report.append(f"kw {kw}: {idxs[:15]}")

# Check if style section exists between popolnenie html and rekvizity
if text.find("во стиль к этой плашке:") >= 0:
    p = text.find("во стиль к этой плашке:")
    report.append(f"style_intro_at={p}")
    # content until next вот код
    nxt = text.find("вот код элемента", p + 10)
    style_chunk = text[p + len("во стиль к этой плашке:"):nxt].strip()
    Path(out / "02b_popolnenie_css_excerpt.txt").write_text(style_chunk[:10000], encoding="utf-8")
    report.append(f"style_chunk_len={len(style_chunk)}")

# Between rekvizity and whole op - is there style?
p3 = text.find("вот код элемента к плашке Реквизиты")
# look for style mention between 03 and 04
seg = text[p3:valid[3][0] if len(valid) > 3 else p3 + 100000]
style_mentions = [m.start() for m in re.finditer(r"стиль", seg)]
report.append(f"стиль mentions in rekvizity section relative: count={len(style_mentions)}")

# Extract compact CSS custom properties that look intentional (not full dump) - first 80 lines after style intro
Path(out / "SECTIONS_REPORT.txt").write_text("\n".join(report), encoding="utf-8")
print("ok", len(valid))
