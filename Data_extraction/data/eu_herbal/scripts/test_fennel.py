import glob
from Data_extraction.data.eu_herbal.data_extraction_scripts.extract_pdfs import read_pages, count_known_headings

files = glob.glob("data/eu_herbal/pdfs/*foeniculum*.pdf")
for path in files:
    two, _ = read_pages(path, True)
    one, _ = read_pages(path, False)
    print(path.split("\\")[-1][:90])
    print("   two-column:", count_known_headings(two), "  single-column:", count_known_headings(one))