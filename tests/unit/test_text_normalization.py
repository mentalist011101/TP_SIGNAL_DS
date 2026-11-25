import pytest

from echolens.core.text_normalization import normalize_for_wer


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Exemples de P12 (docs/specification.md, docs/protocole.md § 7).
        ("c' est", "c'est"),
        ("7 h 30", "sept heures trente"),
        ("Bonjour, Docteur !", "bonjour docteur"),
        ("A de la fièvre depuis 36 heures.", "a de la fièvre depuis trente-six heures"),
        # Apostrophes : courbe unifiée, interne gardée.
        ("Aujourd’hui", "aujourd'hui"),
        ("aujourd'hui", "aujourd'hui"),
        ("L’ homme", "l'homme"),
        # Trait d'union interne gardé, trait d'union isolé retiré.
        ("peut-être", "peut-être"),
        ("- Oui - non", "oui non"),
        # Ponctuation remplacée par un espace : deux mots restent deux mots.
        ("lui / elle", "lui elle"),
        ("lui/elle", "lui elle"),
        ("Je ne comprends pas; nous sommes là.", "je ne comprends pas nous sommes là"),
        # Espaces réduits.
        ("  trop   d'espaces  ", "trop d'espaces"),
        ("", ""),
    ],
)
def test_p12_examples_and_edge_cases(text: str, expected: str) -> None:
    assert normalize_for_wer(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("7h30", "sept heures trente"),
        ("à 7 h", "à sept heures"),
        ("1 h 05", "une heure cinq"),
        ("36 heures", "trente-six heures"),
        ("21 jours", "vingt et un jours"),
        ("le 1er janvier", "le premier janvier"),
        ("le 3e étage", "le troisième étage"),
        ("2,5 litres", "deux virgule cinq litres"),
        ("2,05", "deux virgule zéro cinq"),
        ("10 %", "dix pour cent"),
        ("2,5 %", "deux virgule cinq pour cent"),
        ("10 000 habitants", "dix mille habitants"),
    ],
)
def test_numbers_are_written_in_words(text: str, expected: str) -> None:
    assert normalize_for_wer(text) == expected


def test_reference_and_transcription_of_the_same_sentence_match() -> None:
    reference = "Rendez-vous à 7 h 30, c' est urgent."
    transcription = "Rendez-vous à sept heures trente. C’est urgent !"
    assert normalize_for_wer(reference) == normalize_for_wer(transcription)
