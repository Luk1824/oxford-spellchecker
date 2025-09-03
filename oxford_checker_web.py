import streamlit as st
import fitz  # PyMuPDF
import re
from spellchecker import SpellChecker
import io

# Normalize ligatures (e.g., ﬂ → fl)
def normalize_ligatures(text):
    ligature_map = {
        '\uFB00': 'ff',   # ﬀ
        '\uFB01': 'fi',   # ﬁ
        '\uFB02': 'fl',   # ﬂ
        '\uFB03': 'ffi',  # ﬃ
        '\uFB04': 'ffl',  # ﬄ
        '\uFB05': 'ft',   # ﬅ
        '\uFB06': 'st',   # ﬆ
    }
    for ligature, replacement in ligature_map.items():
        text = text.replace(ligature, replacement)
    return text

# Normalize verb suffixes (like randomizing → randomize)
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
    with open(filename, "r", encoding="utf-8") as f:
        return set(word.strip().lower() for word in f if word.strip())

# Load Medical Corrections
def load_medical_corrections(filename="oxford_medical_corrections.txt"):
    medical_corrections = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                american, british = parts
                medical_corrections[american.lower()] = british.lower()
    return medical_corrections

# Load Abbreviations
def load_abbreviations(filename="medical_scientific_abbreviations.txt"):
    with open(filename, "r", encoding="utf-8") as f:
        return set(word.strip().lower() for word in f if word.strip())

# Main checking function
def check_pdf(file, oxford_ize_words, medical_corrections, abbreviations):
    # Start from an empty lexicon, then load only GB/Oxford sources
    spell = SpellChecker(language=None, case_sensitive=False)
    spell.word_frequency.load_text_file("words_en_gb.txt")
    # Ensure your Oxford -ize base forms are treated as known words
    if oxford_ize_words:
        spell.word_frequency.load_words(list(oxford_ize_words))
    # Ensure the British targets of medical corrections are known
    if medical_corrections:
        spell.word_frequency.load_words(list(medical_corrections.values()))
    # If certain abbreviations are also words, mark them as known
    if abbreviations:
        spell.word_frequency.load_words(list(abbreviations))

    # Read PDF text
    pdf_bytes = file.read()
    doc = fitz.open("pdf", pdf_bytes)
    text = ""
    for page in doc:
        page_text = page.get_text()
        page_text = normalize_ligatures(page_text)
        text += page_text

    words = re.findall(r'\b\w+\b', text.lower())

    oxford_ize_issues = []
    medical_issues = []
    typo_issues = []

    # Regex to gently catch single-l forms where GB prefers double-l
    # Examples: modeling → modelling, labeled → labelled, traveler → traveller
    # This only flags when the suggested GB form exists in the GB dictionary
    double_l_pattern = re.compile(r'^([a-z]*[aeiou][a-z]*?)l(ing|ed|er|ers|y)?$')

    seen_typos = set()

    for word in words:
        if word in abbreviations:
            continue

        normalized_word = normalize_word(word, oxford_ize_words)

        # Medical spelling correction
        if word in medical_corrections:
            medical_issues.append((word, medical_corrections[word]))
            continue

        # Oxford -ise correction detection (prefer -ize when the base is in oxford list)
        if word.endswith("ise") and len(word) > 4:
            candidate = word[:-3] + "ize"
            if candidate in oxford_ize_words:
                oxford_ize_issues.append((word, candidate))
                continue

        # UK double-l guardrail (only if GB alternative is known)
        m = double_l_pattern.match(word)
        if m:
            base, suffix = m.groups()
            suffix = suffix or ""
            gb_candidate = f"{base}ll{suffix}"
            if not spell.unknown([gb_candidate]):  # only flag if GB form is a known word
                suggestion = f"{word} → {gb_candidate}"
                if suggestion not in seen_typos:
                    typo_issues.append(suggestion)
                    seen_typos.add(suggestion)
                continue

        # Typo detection using canonical API
        if word.isalpha() and len(word) > 2:
            if not spell.unknown([word]):
                continue
            # Allow normalized Oxford -ize base forms
            if normalized_word in oxford_ize_words:
                continue
            if word not in seen_typos:
                typo_issues.append(word)
                seen_typos.add(word)

    return oxford_ize_issues, medical_issues, typo_issues

# Pre-load these once
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

        # Oxford -ize corrections
        st.subheader("❗ Oxford -ize spelling corrections needed:")
        if oxford_ize_issues:
            for wrong, correct in oxford_ize_issues:
                st.write(f"{wrong} ➔ {correct}")
        else:
            st.write("No Oxford -ize corrections needed.")

        # Medical spelling corrections
        st.subheader("❗ Medical spelling corrections needed:")
        if medical_issues:
            for american, british in medical_issues:
                st.write(f"{american} ➔ {british}")
        else:
            st.write("No medical corrections needed.")

        # Typographical or spelling issues
        st.subheader("❗ Typographical or spelling issues:")
        if typo_issues:
            st.write(", ".join(sorted(set(typo_issues))))
        else:
            st.write("No typos detected.")

if __name__ == "__main__":
    main()
