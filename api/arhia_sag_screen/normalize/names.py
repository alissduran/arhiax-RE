"""Normalización de nombres y claves de búsqueda."""
import re

from .phonetics import transliterate, soundex, metaphone_approx


def normalize_name(name):
    return re.sub(r"\s+", " ", transliterate(name)).strip()


def token_sort(name):
    return " ".join(sorted(normalize_name(name).split()))


def search_keys(name):
    n = normalize_name(name)
    keys = {n}
    if n:
        keys.add(soundex(n))
        keys.add(metaphone_approx(n))
        keys.add(re.sub(r"[AEIOU]", "", n))
    return tuple(k for k in keys if k)
