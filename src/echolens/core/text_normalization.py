"""Normalisation des textes avant le WER et le CER (P12) : calcul pur, sans torch.

La référence et la transcription passent par la même fonction, normalize_for_wer, pour qu'une
différence d'écriture (majuscule, apostrophe courbe, « 7 h 30 » contre « sept heures trente »)
ne compte pas comme une erreur de reconnaissance. Étapes, dans l'ordre de P12 :
minuscules, apostrophes unifiées, nombres en lettres, ponctuation retirée, espaces réduits.
"""

from __future__ import annotations

import re

from num2words import num2words

FRENCH = "fr"
# Apostrophes typographiques remplacées par l'apostrophe droite (P12).
CURLY_APOSTROPHES = ("’", "‘", "ʼ", "`")
# « 7 h 30 », « 7h30 », « 7 h » : heures, puis minutes facultatives.
HOUR_PATTERN = re.compile(r"\b(\d{1,2})\s*h\s*(\d{2})?\b")
# « 1er », « 2e », « 3ème » : nombres ordinaux.
ORDINAL_PATTERN = re.compile(r"\b(\d+)(?:er|re|ère|ème|eme|e)\b")
# « 2,5 » : nombre décimal, virgule à la française.
DECIMAL_PATTERN = re.compile(r"\b(\d+),(\d+)\b")
# « % » se lit « pour cent », que le nombre soit entier (« 10 % ») ou décimal (« 2,5 % »).
PERCENT_PATTERN = re.compile(r"\s*%")
# Séparateur de milliers : « 10 000 » s'écrit en un seul nombre.
THOUSANDS_SPACE_PATTERN = re.compile(r"(\d) (?=\d{3}\b)")
INTEGER_PATTERN = re.compile(r"\d+")
# Espaces autour d'une apostrophe entre deux lettres : « c' est » devient « c'est ».
SPACED_APOSTROPHE_PATTERN = re.compile(r"(\w)\s*'\s*(\w)")
# Tout ce qui n'est ni lettre, ni chiffre, ni espace, ni apostrophe, ni trait d'union.
PUNCTUATION_PATTERN = re.compile(r"[^\w\s'-]|_")
# Apostrophe ou trait d'union qui n'est pas entre deux lettres (« - oui », « l' »).
EDGE_MARK_PATTERN = re.compile(r"(?<!\w)['-]|['-](?!\w)")
SPACES_PATTERN = re.compile(r"\s+")


def normalize_for_wer(text: str) -> str:
    """Normalise un texte français pour le WER et le CER (P12).

    Exemple : « C’ est à 7 h 30, aujourd'hui ! » devient « c'est à sept heures trente
    aujourd'hui ».
    """
    # Étape 1 : minuscules, pour que « Bonjour » et « bonjour » soient le même mot.
    lowered = text.lower()
    # Étape 2 : une seule apostrophe, collée aux deux lettres qu'elle relie.
    unified = unify_apostrophes(lowered)
    # Étape 3 : chiffres écrits en lettres, avant de retirer la ponctuation (« 2,5 », « 10 % »).
    spelled = spell_out_numbers(unified)
    # Étape 4 : ponctuation retirée, sauf l'apostrophe et le trait d'union internes.
    without_punctuation = remove_punctuation(spelled)
    # Étape 5 : espaces multiples réduits à un seul, et aucun espace au début ni à la fin.
    single_spaced = SPACES_PATTERN.sub(" ", without_punctuation)
    return single_spaced.strip()


def unify_apostrophes(text: str) -> str:
    """Remplace les apostrophes courbes par « ' » et retire les espaces autour (P12)."""
    unified = text
    for apostrophe in CURLY_APOSTROPHES:
        unified = unified.replace(apostrophe, "'")
    return SPACED_APOSTROPHE_PATTERN.sub(r"\1'\2", unified)


def spell_out_numbers(text: str) -> str:
    """Écrit en lettres les nombres en chiffres, avec num2words en français (P12).

    L'ordre compte : les heures et les formes particulières passent avant les entiers seuls,
    sinon « 7 h 30 » deviendrait « sept h trente ».
    """
    spelled = THOUSANDS_SPACE_PATTERN.sub(r"\1", text)
    spelled = HOUR_PATTERN.sub(_hour_in_words, spelled)
    spelled = PERCENT_PATTERN.sub(" pour cent", spelled)
    spelled = DECIMAL_PATTERN.sub(_decimal_in_words, spelled)
    spelled = ORDINAL_PATTERN.sub(_ordinal_in_words, spelled)
    return INTEGER_PATTERN.sub(_integer_in_words, spelled)


def remove_punctuation(text: str) -> str:
    """Retire la ponctuation ; garde l'apostrophe et le trait d'union entre deux lettres."""
    # Une ponctuation devient un espace : « lui/elle » donne bien deux mots.
    spaced = PUNCTUATION_PATTERN.sub(" ", text)
    return EDGE_MARK_PATTERN.sub(" ", spaced)


def _words(number: int) -> str:
    words: str = num2words(number, lang=FRENCH)
    return words


def _hour_in_words(match: re.Match[str]) -> str:
    hour_part = _hours_in_words(int(match.group(1)))
    minutes = match.group(2)
    if minutes is None:
        return hour_part
    return hour_part + " " + _words(int(minutes))


def _hours_in_words(hours: int) -> str:
    # « 1 h » se dit « une heure » : num2words donnerait « un ».
    if hours == 1:
        return "une heure"
    return _words(hours) + " heures"


def _decimal_in_words(match: re.Match[str]) -> str:
    integer_part = _words(int(match.group(1)))
    # Les décimales se lisent chiffre par chiffre après les zéros : « 2,05 » = deux virgule
    # zéro cinq.
    decimals = match.group(2)
    leading_zeros = len(decimals) - len(decimals.lstrip("0"))
    zero_words = ["zéro"] * leading_zeros
    rest = decimals.lstrip("0")
    if rest:
        zero_words.append(_words(int(rest)))
    return integer_part + " virgule " + " ".join(zero_words)


def _ordinal_in_words(match: re.Match[str]) -> str:
    words: str = num2words(int(match.group(1)), lang=FRENCH, to="ordinal")
    return words


def _integer_in_words(match: re.Match[str]) -> str:
    return _words(int(match.group(0)))
