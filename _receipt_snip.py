# -*- coding: utf-8 -*-
import re
from pathlib import Path

text = Path(r"C:\Users\mercury\Desktop\tbank-mitm\_extract_uq.txt").read_text(encoding="utf-8")
out = Path(r"C:\Users\mercury\Desktop\tbank-mitm\_extract_parts")

start = text.find("вот код элемента чека при нажатии на справку в операциях пополнения из другого банка:")
end = text.find("вот код элемента на операции перевода в другой банк:")
receipt = text[start:end]

# Extract around mobile-ib-pdf and bottom-sheet
snippets = []
for needle in [
    'data-qa-type="mobile-ib-pdf"',
    'data-qa-type="mobile-ib-pdf-bottomSheet"',
    'data-qa-type="mobile-ib-pdf-name"',
    'data-qa-type="tui/bottom-sheet"',
    'data-qa-type="mobile-pumba-detail-sheet"',
    "квитан",
    "certificate",
    "Пополнение через",
]:
    pos = receipt.find(needle)
    snippets.append(f"\n===== {needle} @{pos} =====\n")
    if pos >= 0:
        snippets.append(receipt[max(0, pos - 300): pos + 2500])

# Also extract a structural outline of pdf-related nodes with short content
pdf_blocks = []
for m in re.finditer(r'data-qa-type="(mobile-ib-pdf[^"]*)"[^>]*>', receipt):
    qa = m.group(1)
    frag = receipt[m.start(): m.start() + 800]
    # visible text nearby
    texts = re.findall(r">([^<>]{1,60})<", frag)
    pdf_blocks.append(f"{qa}: texts={texts[:8]}")

Path(out / "RECEIPT_SNIPPETS.txt").write_text("\n".join(snippets), encoding="utf-8")
Path(out / "RECEIPT_PDF_OUTLINE.txt").write_text("\n".join(pdf_blocks), encoding="utf-8")

# Image paths from original line - extract from parent message
# Already known from first peek
images = """
1 screenshot: etalon home tile typography (Трат в августе)
2 screenshot: current broken home tile typography
3 screenshot: (context - likely related)
4 screenshot: broken other-bank operation
5 screenshot: current broken receipt/справка
6 screenshot: expected receipt/справка
"""
print("pdf_blocks", len(pdf_blocks))
print("\n".join(pdf_blocks[:30]))
print("snippets_file_written")
