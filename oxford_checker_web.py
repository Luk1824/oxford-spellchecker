import streamlit as st
import fitz  # PyMuPDF
import re
from spellchecker import SpellChecker
import io

def normalize_ligatures(text):
    ligature_map = {
        '\uFB00': 'ff',  # ﬀ
        '\uFB01': 'fi',  # ﬁ
        '\uFB02': 'fl',  # ﬂ
        '\uFB03': 'ffi', # ﬃ
        '\uFB04': 'ffl', # ﬄ
        '\uFB05': 'ft',  # ﬅ
        '\uFB06': 'st',  # ﬆ
    }
    for ligature, replacement in ligature_map.items():
        text = text.replace(ligature, replacement)
    return text

# Helper function to normalize word variants
def normalize_word(word, oxford_ize_words):
    suffixes = ['ed', 'd', 'ing', 'es', 's']
    for suffix in suffixes:
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            base = word[:-len(suffix)]
            if base in oxford_ize_words:
                return base
    return word

# Load Oxford -ize List
def load_oxford_ize_list(filename="oxford_ize_list.txt"):
    with open(filename, "r") as f:
        return set(word.strip().lower() for word in f)

# Load Medical Corrections
def load_medical_corrections(filename="oxford_medical_corrections.txt"):
    medical_corrections = {}
    with open(filename, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:  # ✅ Only accept valid lines
                american, british = parts
                medical_corrections[american.lower()] = british.lower()
    return medical_corrections

# Load Abbreviations
def load_abbreviations(filename="medical_scientific_abbreviations.txt"):
    with open(filename, "r") as f:
        return set(word.strip().lower() for word in f)

# Main checking function
def check_pdf(file, oxford_ize_words, medical_corrections, abbreviations):
    spell = SpellChecker(language="en")
    spell.word_frequency.load_text_file("words_en_gb.txt")

    pdf_bytes = file.read()
    doc = fitz.open("pdf", pdf_bytes)
    text = ""
    for page in doc:
        page_text = page.get_text()
        page_text = normalize_ligatures(page_text)
        text += page_text

    words = re.findall(r'\b\w+\b', text.lower())

    protected_words = []
    medical_issues = []
    typo_issues = []

    for word in words:
        normalized_word = normalize_word(word, oxford_ize_words)
        if normalized_word in oxford_ize_words:
            protected_words.append(word)
        elif word in medical_corrections.keys():
            medical_issues.append((word, medical_corrections[word]))
        else:
            if word.isalpha() and len(word) > 2 and word not in spell and word not in abbreviations:
                typo_issues.append(word)

    return protected_words, medical_issues, typo_issues

# Pre-load these once outside main
oxford_ize_words = load_oxford_ize_list()
medical_corrections = load_medical_corrections()
abbreviations = load_abbreviations()

# Streamlit Web App
def main():
    st.title("Oxford English PDF Spellchecker")

    st.write("Upload a PDF document to check spelling and Oxford English compliance.")

    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_file is not None:
    oxford_ize_issues, medical_issues, typo_issues = check_pdf(
        uploaded_file, oxford_ize_words, medical_corrections, abbreviations
    )

    st.success("Check completed!")

    # ❗ Oxford -ize corrections
    st.subheader("❗ Oxford -ize spelling corrections needed:")
    if oxford_ize_issues:
        for wrong, correct in oxford_ize_issues:
            st.write(f"{wrong} ➔ {correct}")
    else:
        st.write("No Oxford -ize corrections needed.")

    # ❗ Medical spelling corrections
    st.subheader("❗ Medical spelling corrections needed:")
    if medical_issues:
        for american, british in medical_issues:
            st.write(f"{american} ➔ {british}")
    else:
        st.write("No medical corrections needed.")

    # ❗ Typographical or spelling issues
    st.subheader("❗ Typographical or spelling issues:")
    if typo_issues:
        st.write(", ".join(sorted(set(typo_issues))))
    else:
        st.write("No typos detected.")

if __name__ == "__main__":
    main()
