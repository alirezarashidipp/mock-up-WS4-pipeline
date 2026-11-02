import re
import unicodedata
from difflib import SequenceMatcher


def normalize_name(name):
    text = unicodedata.normalize("NFKD", name or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.findall(r"[a-z0-9]+", text))


def name_match_method(supplier, candidate):
    if not candidate:
        return ""
    supplier_words = set(supplier.split())
    candidate_words = set(candidate.split())
    if supplier_words <= candidate_words or candidate_words <= supplier_words:
        return "Whole-word containment"
    if min(len(supplier), len(candidate)) < 4:
        return ""
    if SequenceMatcher(None, supplier, candidate).ratio() >= 0.8:
        return "Whole-name fuzzy similarity (threshold 0.8)"
    if len(supplier_words) == 1:
        for word in candidate_words:
            if len(word) >= 4 and SequenceMatcher(None, supplier, word).ratio() >= 0.8:
                return "Single-word fuzzy similarity (threshold 0.8)"
    return ""


def explain_candidate_match(normalized_supplier, engagement):
    """Use the same ordered name checks for retrieval and its explanation."""
    for column in ("THIRD_PARTY_NAME", "THIRD_PARTY_NORMALISED_NAME"):
        source_name = engagement.get(column, "")
        normalized_name = normalize_name(source_name)
        method = name_match_method(normalized_supplier, normalized_name)
        if method:
            return {
                "column": column,
                "source_name": source_name,
                "normalized_name": normalized_name,
                "method": method,
            }
    return None


def find_candidates(supplier_name, engagements, max_candidates=70):
    if max_candidates is not None and (type(max_candidates) is not int or max_candidates < 1):
        raise ValueError("max_candidates must be a positive integer or None.")
    supplier = normalize_name(supplier_name)
    if supplier in ("", "unknown", "n a", "none", "null", "not known", "not available"):
        return []
    # Lexical matching can miss aliases such as EY versus Ernst & Young.
    candidates = []
    for engagement in engagements:
        if explain_candidate_match(supplier, engagement):
            candidates.append(engagement)
            if max_candidates is not None and len(candidates) >= max_candidates:
                return candidates
    return candidates
