import re
import unicodedata
from difflib import SequenceMatcher


def normalize_name(name):
    text = unicodedata.normalize("NFKD", name or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.findall(r"[a-z0-9]+", text))


def names_match(supplier, candidate):
    if not candidate:
        return False
    supplier_words = set(supplier.split())
    candidate_words = set(candidate.split())
    if supplier_words <= candidate_words or candidate_words <= supplier_words:
        return True
    if min(len(supplier), len(candidate)) < 4:
        return False
    if SequenceMatcher(None, supplier, candidate).ratio() >= 0.8:
        return True
    if len(supplier_words) == 1:
        for word in candidate_words:
            if len(word) >= 4 and SequenceMatcher(None, supplier, word).ratio() >= 0.8:
                return True
    return False


def find_candidates(supplier_name, engagements, max_candidates=70):
    if max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer.")
    supplier = normalize_name(supplier_name)
    if supplier in ("", "unknown", "n a", "none", "null", "not known", "not available"):
        return []
    # shortcut: lexical matching can miss aliases; add explicit aliases if real records need them.
    candidates = []
    for engagement in engagements:
        for column in ("THIRD_PARTY_NAME", "THIRD_PARTY_NORMALISED_NAME"):
            name = normalize_name(engagement.get(column, ""))
            if names_match(supplier, name):
                candidates.append(engagement)
                if len(candidates) >= max_candidates:
                    return candidates
                break
    return candidates
