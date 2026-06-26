"""Standalone segmentation helpers for ECHR Extractor.

The reusable package-facing component is intentionally DataFrame-first so it
fits naturally into the extractor workflow:

- `df` + `full_texts` from `get_echr_extra()`
- a pre-merged `corpus_df`
- a single in-memory `document` or raw `text`
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from .ECHR_text_segmenter import SECTION_NAMES, segment_echr_texts

SEGMENT_OUTPUT_COLUMNS = (
    ["itemid", "languageisocode", "ecli", "parser_mode"]
    + SECTION_NAMES
    + ["num_sections", "error"]
)

_CORPUS_REQUIRED_COLUMNS = {"itemid", "languageisocode", "fulltext"}
_OPTIONAL_CORPUS_COLUMNS = {"ecli", "doctype", "doctypebranch"}


def _records_to_dataframe(
    value: pd.DataFrame | Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    source_name: str,
) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, Mapping):
        return pd.DataFrame([dict(value)])
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return pd.DataFrame(list(value))
    raise TypeError(
        f"{source_name} must be a pandas DataFrame, a mapping, or a sequence of mappings"
    )


def _normalize_corpus_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for old, new in {
        "item_id": "itemid",
        "language": "languageisocode",
        "lang": "languageisocode",
        "full_text": "fulltext",
        "text": "fulltext",
    }.items():
        if old in df.columns and new not in df.columns:
            rename_map[old] = new

    normalized = df.rename(columns=rename_map).copy()

    if "itemid" not in normalized.columns:
        normalized["itemid"] = [f"doc-{i + 1}" for i in range(len(normalized))]
    if "languageisocode" not in normalized.columns:
        normalized["languageisocode"] = "ENG"
    else:
        normalized["languageisocode"] = normalized["languageisocode"].map(
            _normalize_language_value
        )

    for optional in _OPTIONAL_CORPUS_COLUMNS:
        if optional not in normalized.columns:
            normalized[optional] = None

    ordered = [
        column
        for column in ["itemid", "languageisocode", "ecli", "doctype", "doctypebranch", "fulltext"]
        if column in normalized.columns
    ]
    return normalized[ordered]


def _normalize_full_text_records(
    full_texts: pd.DataFrame | Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> pd.DataFrame:
    df = _records_to_dataframe(full_texts, source_name="full_texts").copy()
    rename_map = {}
    for old, new in {
        "item_id": "itemid",
        "full_text": "fulltext",
        "text": "fulltext",
        "language": "languageisocode",
        "lang": "languageisocode",
    }.items():
        if old in df.columns and new not in df.columns:
            rename_map[old] = new
    normalized = df.rename(columns=rename_map)

    if "itemid" not in normalized.columns:
        normalized["itemid"] = [f"doc-{i + 1}" for i in range(len(normalized))]
    if "ecli" not in normalized.columns:
        normalized["ecli"] = None
    if "languageisocode" in normalized.columns:
        normalized["languageisocode"] = normalized["languageisocode"].map(
            _normalize_language_value
        )

    keep_cols = [
        column
        for column in ["itemid", "languageisocode", "ecli", "fulltext"]
        if column in normalized.columns
    ]
    return normalized[keep_cols]


def _normalize_language_value(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None

    normalized = str(value).strip().upper()
    return normalized or None


def prepare_segmentation_corpus(
    *,
    corpus_df: pd.DataFrame | Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    df: pd.DataFrame | Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    full_texts: pd.DataFrame | Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    document: Mapping[str, Any] | str | None = None,
    documents: Sequence[Mapping[str, Any]] | None = None,
    itemid: str = "doc-1",
    languageisocode: str = "ENG",
    ecli: str | None = None,
    doctype: str | None = None,
    doctypebranch: str | None = None,
) -> pd.DataFrame:
    """Normalize supported segmentation inputs into a corpus DataFrame."""
    if document is not None and documents is not None:
        raise ValueError("Provide either document or documents, not both")

    if corpus_df is not None:
        return _normalize_corpus_columns(
            _records_to_dataframe(corpus_df, source_name="corpus_df")
        )

    if document is not None:
        if isinstance(document, str):
            document = {
                "itemid": itemid,
                "languageisocode": languageisocode,
                "ecli": ecli,
                "doctype": doctype,
                "doctypebranch": doctypebranch,
                "fulltext": document,
            }
        return _normalize_corpus_columns(_records_to_dataframe(document, source_name="document"))

    if documents is not None:
        return _normalize_corpus_columns(_records_to_dataframe(documents, source_name="documents"))

    if df is None and full_texts is None:
        raise ValueError(
            "Provide one of: corpus_df, document, documents, or both df and full_texts"
        )

    if df is None or full_texts is None:
        raise ValueError("Both df and full_texts are required when not using a corpus or document input")

    metadata_df = _normalize_corpus_columns(
        _records_to_dataframe(df, source_name="df")
    )
    texts_df = _normalize_full_text_records(full_texts)

    merge_keys = ["itemid"]
    if "languageisocode" in metadata_df.columns and "languageisocode" in texts_df.columns:
        merge_keys = ["itemid", "languageisocode"]

    non_key_text_columns = [column for column in texts_df.columns if column not in merge_keys]
    texts_df = texts_df[merge_keys + non_key_text_columns]
    merged = metadata_df.merge(texts_df, on=merge_keys, how="left", suffixes=("", "_text"))

    if merge_keys == ["itemid", "languageisocode"] and non_key_text_columns:
        unique_texts_by_itemid = texts_df.loc[
            ~texts_df["itemid"].duplicated(keep=False),
            ["itemid"] + non_key_text_columns,
        ]
        if not unique_texts_by_itemid.empty:
            merged = merged.merge(
                unique_texts_by_itemid,
                on="itemid",
                how="left",
                suffixes=("", "_fallback"),
            )

    for column in ["ecli", "fulltext"]:
        suffixed = f"{column}_text"
        if suffixed not in merged.columns:
            continue
        if column not in merged.columns:
            merged = merged.rename(columns={suffixed: column})
            continue
        merged[column] = merged[column].combine_first(merged[suffixed])
        merged = merged.drop(columns=[suffixed])

    for column in ["ecli", "fulltext"]:
        fallback = f"{column}_fallback"
        if fallback not in merged.columns:
            continue
        if column not in merged.columns:
            merged = merged.rename(columns={fallback: column})
            continue
        merged[column] = merged[column].combine_first(merged[fallback])
        merged = merged.drop(columns=[fallback])

    return _normalize_corpus_columns(merged)


def _normalize_result_record(record: Mapping[str, Any]) -> dict[str, Any]:
    normalized = {}
    for key in SEGMENT_OUTPUT_COLUMNS:
        value = record.get(key)
        normalized[key] = None if pd.isna(value) else value
    return normalized


def segment_document(
    text: str | None = None,
    *,
    document: Mapping[str, Any] | None = None,
    itemid: str = "doc-1",
    languageisocode: str = "ENG",
    ecli: str | None = None,
    doctype: str | None = None,
    doctypebranch: str | None = None,
    allowed_langs: tuple[str, ...] = ("ENG", "FRE"),
    min_segment_length: int = 50,
    max_text_length: int = 5_000_000,
) -> dict[str, Any]:
    """Segment a single ECHR document and return one structured result record."""
    if text is None and document is None:
        raise ValueError("Provide either text or document")

    corpus = prepare_segmentation_corpus(
        document=document if document is not None else text,
        itemid=itemid,
        languageisocode=languageisocode,
        ecli=ecli,
        doctype=doctype,
        doctypebranch=doctypebranch,
    )
    result = segment_echr_texts(
        corpus,
        allowed_langs=allowed_langs,
        min_segment_length=min_segment_length,
        max_text_length=max_text_length,
    )
    return _normalize_result_record(result.iloc[0].to_dict())


def segment_documents(
    *,
    corpus_df: pd.DataFrame | Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    df: pd.DataFrame | Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    full_texts: pd.DataFrame | Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    document: Mapping[str, Any] | str | None = None,
    documents: Sequence[Mapping[str, Any]] | None = None,
    allowed_langs: tuple[str, ...] = ("ENG", "FRE"),
    min_segment_length: int = 50,
    max_text_length: int = 5_000_000,
) -> pd.DataFrame:
    """Segment ECHR documents from path-based or variable-based inputs."""
    corpus = prepare_segmentation_corpus(
        corpus_df=corpus_df,
        df=df,
        full_texts=full_texts,
        document=document,
        documents=documents,
    )
    return segment_echr_texts(
        corpus,
        allowed_langs=allowed_langs,
        min_segment_length=min_segment_length,
        max_text_length=max_text_length,
    )
