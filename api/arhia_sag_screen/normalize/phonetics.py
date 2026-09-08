"""Fonética y transliteración (Soundex + metáfono aproximado)."""
import re
import unicodedata


def transliterate(text):
    nfd = unicodedata.normalize("NFD", text or "")
    ascii_text = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return ascii_text.upper().strip()


_SOUNDEX = {
    "B": "1", "F": "1", "P": "1", "V": "1",
    "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
    "D": "3", "T": "3",
    "L": "4",
    "M": "5", "N": "5",
    "R": "6",
}


def soundex(text):
    s = re.sub(r"[^A-Z]", "", transliterate(text))
    if not s:
        return ""
    first = s[0]
    out = first
    prev = _SOUNDEX.get(first, "")
    for ch in s[1:]:
        code = _SOUNDEX.get(ch, "")
        if code and code != prev:
            out += code
        prev = code
        if len(out) == 4:
            break
    return out.ljust(4, "0")[:4]


def metaphone_approx(text):
    """Metáfono simplificado para matching hispano (determinista, no oficial)."""
    s = re.sub(r"[^A-Z]", "", transliterate(text))
    if not s:
        return ""
    s = re.sub(r"^GN", "N", s)
    s = re.sub(r"^KN", "N", s)
    s = s.replace("PH", "F").replace("LL", "Y").replace("CH", "X")
    s = re.sub(r"[AEIOU]", "A", s)
    s = re.sub(r"(.)\1+", r"\1", s)
    return s
