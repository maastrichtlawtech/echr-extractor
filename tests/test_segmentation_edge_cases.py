from __future__ import annotations

import pytest

from echr_extractor.ECHR_text_segmenter import _COMPILED_PATTERNS, segment_text


EDGE_CASES = [
    {
        "id": "appendix_after_operative",
        "text": (
            "THE FACTS\n\n"
            "Some factual background with enough detail to exceed the extraction threshold.\n\n"
            "THE LAW\n\n"
            "Some legal analysis with enough detail to exceed the extraction threshold.\n\n"
            "FOR THESE REASONS\n\n"
            "The Court decides as follows.\n\n"
            "Registrar President\n\n"
            "APPENDIX\n\n"
            "No.\n\n"
            "Application no.\n\n"
            "12345/67\n\n"
            "Applicant\n\n"
            "Jane Doe\n\n"
            "Observations\n\n"
            "Additional appendix material to exceed the minimum segment length.\n"
        ),
        "present": ["operative", "appendix"],
        "absent": [],
        "startswith": {"appendix": "APPENDIX"},
    },
    {
        "id": "court_assessment_vs_alleged_violation_subheading",
        "text": (
            "SUBJECT MATTER OF THE CASE\n\n"
            "Short case summary with enough detail to exceed the segment minimum length for extraction.\n\n"
            "THE COURT’S ASSESSMENT\n\n"
            "ALLEGED VIOLATION OF ARTICLE 8 OF THE CONVENTION\n\n"
            "The Court considers the admissibility and merits of this complaint in the assessment section.\n\n"
            "FOR THESE REASONS\n\n"
            "The Court unanimously decides.\n"
        ),
        "present": ["subject_matter", "court_assessment"],
        "absent": ["complaints"],
        "startswith": {"court_assessment": "THE COURT’S ASSESSMENT"},
    },
    {
        "id": "law_vs_complaint_subheading",
        "text": (
            "THE FACTS\n\n"
            "The applicant's case history is set out here with enough detail to exceed the extraction minimum.\n\n"
            "THE LAW\n\n"
            "I. THE COMPLAINT ABOUT THE LENGTH OF THE PROCEEDINGS\n\n"
            "The Court examines this complaint within the law section rather than as a standalone complaints block.\n\n"
            "FOR THESE REASONS\n\n"
            "The Court unanimously decides.\n"
        ),
        "present": ["law"],
        "absent": ["complaints"],
        "startswith": {"law": "THE LAW"},
    },
    {
        "id": "french_partial_dissent",
        "text": (
            "EN FAIT\n\n"
            "Le contexte factuel est expose ici avec suffisamment de detail pour exceder le seuil minimal.\n\n"
            "EN DROIT\n\n"
            "La Cour examine les griefs au fond.\n\n"
            "PAR CES MOTIFS\n\n"
            "La Cour statue comme suit.\n\n"
            "J.F.K.\n"
            "S.H.N.\n\n"
            "OPINION EN PARTIE DISSIDENTE DE LA JUGE KOSKELO\n\n"
            "Je ne partage pas la solution retenue sur ce point et j'expose ci-dessous les raisons de mon vote.\n"
        ),
        "present": ["separate_opinion"],
        "absent": [],
        "startswith": {"separate_opinion": "OPINION EN PARTIE DISSIDENTE"},
    },
    {
        "id": "committee_heading_only_subject_matter",
        "text": (
            "SUBJECT MATTER OF THE CASE\n\n"
            "THE CIRCUMSTANCES OF THE CASE\n\n"
            "1. The application concerns a committee-style case summary that begins immediately.\n\n"
            "THE COURT’S ASSESSMENT\n\n"
            "The Court examines the admissibility and merits.\n"
        ),
        "present": ["subject_matter", "facts"],
        "absent": [],
        "startswith": {"subject_matter": "SUBJECT MATTER OF THE CASE"},
    },
    {
        "id": "lowercase_court_assessment_subheading_stays_in_law",
        "text": (
            "THE FACTS\n\n"
            "The factual section contains enough material to exceed the extraction threshold.\n\n"
            "THE LAW\n\n"
            "I. the court’s assessment of the facts\n\n"
            "The Court addresses the factual record as part of the law section rather than as a committee heading.\n\n"
            "FOR THESE REASONS\n\n"
            "The Court unanimously decides.\n"
        ),
        "present": ["law"],
        "absent": ["court_assessment"],
        "startswith": {"law": "THE LAW"},
    },
    {
        "id": "old_french_faits_heading",
        "text": (
            "PROCEDURE\n\n"
            "Introduction procedurale.\n\n"
            "FAITS\n\n"
            "I. LES CIRCONSTANCES DE L’ESPÈCE\n\n"
            "A. Le premier requérant\n\n"
            "Le contexte factuel est décrit ici de manière suffisamment longue pour dépasser le seuil minimal.\n\n"
            "EN DROIT\n\n"
            "La Cour examine ensuite les moyens.\n"
        ),
        "present": ["facts"],
        "absent": [],
        "startswith": {"facts": "FAITS"},
    },
    {
        "id": "french_partial_dissent_with_comma",
        "text": (
            "FAITS\n\n"
            "Le contexte factuel est décrit ici avec suffisamment de détail.\n\n"
            "EN DROIT\n\n"
            "La Cour examine ensuite les moyens.\n\n"
            "PAR CES MOTIFS\n\n"
            "La Cour statue comme suit.\n\n"
            "H. M.\n\n"
            "M.-A. E.\n\n"
            "OPINION, EN PARTIE DISSIDENTE DE M. LE JUGE PINHEIRO FARINHA\n\n"
            "Je regrette vivement de ne pouvoir partager l'opinion de la majorité.\n"
        ),
        "present": ["separate_opinion"],
        "absent": [],
        "startswith": {"separate_opinion": "OPINION, EN PARTIE DISSIDENTE"},
    },
    {
        "id": "french_mixed_partial_opinion",
        "text": (
            "EN FAIT\n\n"
            "Le contexte factuel est décrit ici avec suffisamment de détail.\n\n"
            "EN DROIT\n\n"
            "La Cour examine ensuite les moyens.\n\n"
            "PAR CES MOTIFS\n\n"
            "La Cour statue comme suit.\n\n"
            "Paraphé : F. G.\n\n"
            "Paraphé : H. P.\n\n"
            "OPINION PARTIELLEMENT CONCORDANTE\n"
            "ET PARTIELLEMENT DISSIDENTE\n"
            "DE M. LE JUGE MATSCHER\n\n"
            "Je formule ici mes motifs séparés sur la solution retenue.\n"
        ),
        "present": ["separate_opinion"],
        "absent": [],
        "startswith": {"separate_opinion": "OPINION PARTIELLEMENT CONCORDANTE"},
    },
    {
        "id": "minor_ocr_case_drift_in_law",
        "text": (
            "AS TO THE FACTS\n\n"
            "The factual section contains enough detail to exceed the extraction threshold.\n\n"
            "AS TO THE LAw\n\n"
            "I. SCOPE OF THE CASE\n\n"
            "The Court proceeds to the legal assessment under the law heading.\n\n"
            "FOR THESE REASONS\n\n"
            "The Court unanimously decides.\n"
        ),
        "present": ["law"],
        "absent": [],
        "startswith": {"law": "AS TO THE LAw"},
    },
    {
        "id": "french_joint_partial_dissent",
        "text": (
            "EN FAIT\n\n"
            "Le contexte factuel est décrit ici avec suffisamment de détail.\n\n"
            "EN DROIT\n\n"
            "La Cour examine ensuite les moyens.\n\n"
            "PAR CES MOTIFS\n\n"
            "La Cour statue comme suit.\n\n"
            "R. R.\n\n"
            "H. P.\n\n"
            "OPINION COMMUNE EN PARTIE DISSIDENTE DE MM. LES JUGES EXEMPLE ET AUTRE\n\n"
            "Nous ne pouvons pas souscrire aux conclusions de la majorité.\n"
        ),
        "present": ["separate_opinion"],
        "absent": [],
        "startswith": {"separate_opinion": "OPINION COMMUNE EN PARTIE DISSIDENTE"},
    },
    {
        "id": "french_law_subsection_violation_alleguee_stays_in_law",
        "text": (
            "EN FAIT\n\n"
            "Le contexte factuel est décrit ici avec suffisamment de détail pour dépasser le seuil minimal.\n\n"
            "EN DROIT\n\n"
            "I. SUR LA VIOLATION ALLÉGUÉE DE L'ARTICLE 6 § 1 DE LA CONVENTION\n\n"
            "Le requérant dénonce la durée de la procédure et la Cour examine ce grief dans la partie droit.\n\n"
            "PAR CES MOTIFS\n\n"
            "La Cour statue comme suit.\n"
        ),
        "present": ["law"],
        "absent": ["complaints"],
        "startswith": {"law": "EN DROIT"},
    },
    {
        "id": "old_french_opinion_separee_header",
        "text": (
            "EN FAIT\n\n"
            "Le contexte factuel est décrit ici avec suffisamment de détail.\n\n"
            "EN DROIT\n\n"
            "La Cour examine ensuite les moyens.\n\n"
            "PAR CES MOTIFS\n\n"
            "La Cour statue comme suit.\n\n"
            "R.R.\n"
            "M.-A.E.\n\n"
            "OPINION SEPAREE DE M. LE JUGE DE MEYER\n\n"
            "Mes observations au sujet des paragraphes qui précèdent sont exposées ci-dessous.\n"
        ),
        "present": ["separate_opinion"],
        "absent": [],
        "startswith": {"separate_opinion": "OPINION SEPAREE"},
    },
]


@pytest.mark.parametrize("case", EDGE_CASES, ids=[case["id"] for case in EDGE_CASES])
def test_segmenter_handles_hardened_edge_cases(case):
    segments = segment_text(case["text"], _COMPILED_PATTERNS)

    for section in case["present"]:
        assert section in segments
        assert segments[section]

    for section in case["absent"]:
        assert section not in segments

    for section, prefix in case["startswith"].items():
        assert segments[section].startswith(prefix)


FALSE_POSITIVE_GUARDS = [
    {
        "id": "running_text_procedure_reference",
        "text": (
            "Against the Government of that State, preliminary objections and questions of procedure "
            "were raised in the present case by both the Commission and the Government. "
            "No standalone section header appears in this passage."
        ),
        "forbidden_sections": ["procedure"],
    },
    {
        "id": "running_text_law_reference",
        "text": (
            "The Court noted that every person had to respect the Constitution and the Law and not "
            "to engage in any illegal activity. This is narrative text, not a heading."
        ),
        "forbidden_sections": ["law"],
    },
    {
        "id": "running_text_facts_reference",
        "text": (
            "The final report set out its findings of the facts in the present case, but the passage "
            "here remains ordinary narrative prose rather than a section boundary."
        ),
        "forbidden_sections": ["facts"],
    },
    {
        "id": "running_text_complaint_reference",
        "text": (
            "The parties made submissions on the admissibility of the complaint in question, which "
            "related to the whole period of detention. This should not become a complaints block."
        ),
        "forbidden_sections": ["complaints"],
    },
    {
        "id": "running_text_griefs_reference",
        "text": (
            "La Cour estime en conséquence qu’en ce qui concerne les griefs relatifs aux ordonnances "
            "d’internement, le moyen tiré par le Gouvernement appelle une réponse au fond."
        ),
        "forbidden_sections": ["complaints"],
    },
    {
        "id": "running_text_annex_reference",
        "text": (
            "The full text of the Commission’s opinion and of the dissenting opinion contained in the "
            "report is reproduced as an annex to this judgment, but annex is only mentioned in passing."
        ),
        "forbidden_sections": ["appendix", "separate_opinion"],
    },
    {
        "id": "running_text_annexe_reference",
        "text": (
            "Le texte intégral de son avis et des opinions dissidentes dont il s'accompagne figure en "
            "annexe au présent arrêt; cette mention narrative ne doit pas créer une annexe."
        ),
        "forbidden_sections": ["appendix"],
    },
    {
        "id": "running_text_opinion_reference",
        "text": (
            "Under Article 51 § 2 of the Convention, the separate concurring opinion of one judge and "
            "the dissenting opinion of another were annexed to the present judgment, but no opinion "
            "header begins here."
        ),
        "forbidden_sections": ["separate_opinion", "appendix"],
    },
]


@pytest.mark.parametrize(
    "case",
    FALSE_POSITIVE_GUARDS,
    ids=[case["id"] for case in FALSE_POSITIVE_GUARDS],
)
def test_segmenter_ignores_running_text_false_positive_phrases(case):
    segments = segment_text(case["text"], _COMPILED_PATTERNS)

    for section in case["forbidden_sections"]:
        assert section not in segments
