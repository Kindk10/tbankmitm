"""Собрать sbpfinaltbanksend.pdf из ближайшего receipt_*.pdf (whiteout полей)."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import func


def main():
    path = func.build_blank_receipt_template()
    if not path:
        print("FAIL: blank template not built")
        sys.exit(1)
    print("OK:", path)
    sys.exit(0)


if __name__ == "__main__":
    main()
