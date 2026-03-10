import pypdf
import sys

pdf_path = "HANA Sentinel.pdf"
output_path = "HANA_Sentinel_Content.txt"

try:
    reader = pypdf.PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Successfully extracted text to {output_path}")

except Exception as e:
    print(f"Error extracting text: {e}")
    sys.exit(1)
