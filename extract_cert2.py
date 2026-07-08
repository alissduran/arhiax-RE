import sys
sys.stdout.reconfigure(encoding='utf-8')
from pypdf import PdfReader

reader = PdfReader(r"C:\Users\aliss\Downloads\certificado64640614546464261189306228pdf.pdf")
# Pages 1-2 only (index 0-1)
for i in [0, 1, 2]:
    print(f"\n{'='*70}")
    print(f"PAGINA {i+1}")
    print(f"{'='*70}")
    print(reader.pages[i].extract_text())
