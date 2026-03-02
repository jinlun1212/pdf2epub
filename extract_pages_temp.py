import PyPDF2

reader = PyPDF2.PdfReader('c:/Users/ljina/OneDrive - Micron Technology, Inc/Desktop/pdf2epub-main/options_futures_and_other_derivatives_11th.pdf')
pages = [26, 219, 222, 362, 373, 707, 785]
for p in pages:
    text = reader.pages[p-1].extract_text()
    print(f'=== PDF PAGE {p} ===')
    print(text)
    print()
    print(f'=== END PAGE {p} ===')
    print()
