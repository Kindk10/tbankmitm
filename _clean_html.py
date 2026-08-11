# -*- coding: utf-8 -*-
import re
from pathlib import Path

text = Path(r"C:\Users\mercury\Desktop\tbank-mitm\_extract_uq.txt").read_text(encoding="utf-8")
out = Path(r"C:\Users\mercury\Desktop\tbank-mitm\_extract_parts")

sections = {
    "popolnenie": ("вот код элемента для плашки Пополнение, в операции поступления из другого банка:", "во стиль к этой плашке:"),
    "popolnenie_css": ("во стиль к этой плашке:", "вот код элемента к плашке Реквизиты"),
    "rekvizity": ("вот код элемента к плашке Реквизиты, в операции пополнения из другого банка:", "вот код элемента в целом операции"),
    "whole_op": ("вот код элемента в целом операции пополнения из другого банка:", "вот код элемента чека при нажатии"),
    "receipt": ("вот код элемента чека при нажатии на справку в операциях пополнения из другого банка:", "вот код элемента на операции перевода"),
    "transfer_op": ("вот код элемента на операции перевода в другой банк:", "вот код элемента для плашки Перевод"),
    "perevod_tile": ("вот код элемента для плашки Перевод в этих операциях:", "вот код элемента для плашки Реквизиты в этих переводах:"),
    "rekvizity_transfer": ("вот код элемента для плашки Реквизиты в этих переводах:", "вот код элемента ещё от плашек"),
    "more_tiles": ("вот код элемента ещё от плашек на этой странице:", None),
}

def get_chunk(start_needle, end_needle):
    s = text.find(start_needle)
    if s < 0:
        return None
    s2 = s + len(start_needle)
    if end_needle:
        e = text.find(end_needle, s2)
        if e < 0:
            e = len(text)
    else:
        e = len(text)
    return text[s2:e].strip()

# Clean HTML: take until "вот стил" / CSS var dump / <body
def html_only(chunk):
    for stopper in ["\nвот стил", "\nво стиль", "\nвот стиль", "\n    -webkit-text-size-adjust", "\n<body", "<!DOCTYPE"]:
        i = chunk.find(stopper)
        if i > 0:
            return chunk[:i].strip()
    # if chunk is body page, keep note
    return chunk

# Receipt: search for receipt-like qa types and text
receipt = get_chunk(*sections["receipt"][:2]) if False else None
receipt = get_chunk("вот код элемента чека при нажатии на справку в операциях пополнения из другого банка:", "вот код элемента на операции перевода в другой банк:")

report = []
if receipt:
    report.append(f"receipt_len={len(receipt)}")
    for pat in [
        r"receipt", r"квитан", r"справк", r"certificate", r"pdf", r"cheque", r"check",
        r"document-viewer", r"operation-document", r"cert", r"справоч",
        r"Пополнение через", r"сумма", r"Сумма", r"Дата", r"Статус",
    ]:
        found = list(re.finditer(pat, receipt, re.I))
        report.append(f"pat {pat}: count={len(found)} first={[m.start() for m in found[:5]]}")
    # Find interesting qa types
    qas = list(dict.fromkeys(re.findall(r'data-qa-type="([^"]+)"', receipt)))
    interesting = [q for q in qas if any(x in q.lower() for x in ["cert", "receipt", "doc", "pdf", "modal", "sheet", "dialog", "operation", "requisite", "amount", "header"])]
    report.append("interesting_qa sample: " + " | ".join(interesting[:60]))
    report.append(f"total_unique_qa={len(qas)}")

# Save clean HTML for key tiles
clean_map = {}
for name, (a, b) in [
    ("CLEAN_popolnenie.html", ("вот код элемента для плашки Пополнение, в операции поступления из другого банка:", "во стиль к этой плашке:")),
    ("CLEAN_rekvizity.html", ("вот код элемента к плашке Реквизиты, в операции пополнения из другого банка:", "вот код элемента в целом операции")),
    ("CLEAN_perevod.html", ("вот код элемента для плашки Перевод в этих операциях:", "вот код элемента для плашки Реквизиты в этих переводах:")),
    ("CLEAN_rekvizity_transfer.html", ("вот код элемента для плашки Реквизиты в этих переводах:", "вот код элемента ещё от плашек")),
    ("CLEAN_more_tiles.html", ("вот код элемента ещё от плашек на этой странице:", None)),
]:
    chunk = get_chunk(a, b)
    if not chunk:
        report.append(f"MISSING {name}")
        continue
    # For rekvizity, strip CSS after HTML
    h = html_only(chunk)
    # If still huge, take first div tree only until double newline + css
    if len(h) > 20000 and h.startswith("<div"):
        # cut at first "вот стил"
        for stopper in ["вот стил", "во стиль", "вот стиль", "-webkit-text-size-adjust"]:
            i = h.find(stopper)
            if i > 0:
                h = h[:i].strip()
                break
    Path(out / name).write_text(h if len(h) < 100000 else h[:50000], encoding="utf-8")
    report.append(f"{name} clean_len={len(h)}")
    clean_map[name] = h

# CSS excerpts: key computed-looking properties near end of style dumps (actual applied styles often at end)
# Extract last 2500 chars of popolnenie css and first mention of font-size/font-weight for heading
css = get_chunk("во стиль к этой плашке:", "вот код элемента к плашке Реквизиты")
if css:
    # Find properties that look element-specific (not just --tui-font-* token definitions)
    interesting_props = []
    for line in css.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("--tui-font-") or s.startswith("--tui-typography-") or s.startswith("--tui-color"):
            continue
        if any(k in s for k in ["font-size", "font-weight", "line-height", "padding", "margin", "gap", "letter-spacing", "color:", "background", "border-radius", "display:", "flex"]):
            interesting_props.append(s)
    Path(out / "CSS_popolnenie_interesting.txt").write_text("\n".join(interesting_props[:200]), encoding="utf-8")
    Path(out / "CSS_popolnenie_tail.txt").write_text(css[-4000:], encoding="utf-8")
    report.append(f"popolnenie_css_len={len(css)} interesting_props={len(interesting_props)}")

# Same for rekvizity styles inside rekvizity chunk
rek = get_chunk("вот код элемента к плашке Реквизиты, в операции пополнения из другого банка:", "вот код элемента в целом операции")
if rek:
    idx = rek.find("вот стили к этому элементу:")
    if idx < 0:
        idx = rek.find("-webkit-text-size-adjust")
    css2 = rek[idx:] if idx >= 0 else ""
    interesting_props = []
    for line in css2.split("\n"):
        s = line.strip()
        if not s or s.startswith("--tui-font-") or s.startswith("--tui-typography-"):
            continue
        if any(k in s for k in ["font-size", "font-weight", "line-height", "padding", "margin", "gap", "letter-spacing", "color:", "background", "border-radius", "display:", "flex"]):
            interesting_props.append(s)
    Path(out / "CSS_rekvizity_interesting.txt").write_text("\n".join(interesting_props[:200]), encoding="utf-8")
    Path(out / "CSS_rekvizity_tail.txt").write_text(css2[-4000:] if css2 else "", encoding="utf-8")
    # pure HTML
    html_rek = rek[:idx].strip() if idx > 0 else html_only(rek)
    Path(out / "CLEAN_rekvizity.html").write_text(html_rek, encoding="utf-8")
    report.append(f"rekvizity_html_len={len(html_rek)} css2_len={len(css2)} interesting={len(interesting_props)}")

# Image list from original message - already known
# Check screenshots folder names in lead of original json - already have paths

Path(out / "RECEIPT_SEARCH.txt").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report))
