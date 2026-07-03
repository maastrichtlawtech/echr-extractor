import logging
import re
from functools import lru_cache

import dateparser
import pandas as pd
from tqdm import tqdm

from .clean_ref import clean_pattern

MISSING_REFERENCE_COLUMNS = [
    "citing_id",
    "missing_references",
    "extracted_appnos",
    "casename",
    "year",
    "ref_language",
]


@lru_cache(maxsize=200000)
def parse_date_cached(text):
    """Memoized dateparser.parse for citation/judgment date strings.

    dateparser.parse dominates the edge-calculation runtime (~4ms per
    call, scanning ~190 locales), and the same date strings recur across
    thousands of citations. Case names and dates only appear in English
    or French, so the locale scan is restricted accordingly. Strings
    without a digit can never parse as a date and are skipped outright.
    """
    if not any(ch.isdigit() for ch in text):
        return None
    return dateparser.parse(text, languages=["en", "fr"])


def open_metadata(PATH_metadata):
    """
    Finds the ECHR metadata file and loads it into a dataframe

    param filename_metadata: string with path to metadata
    """
    try:
        df = pd.read_csv(PATH_metadata)  # change hard coded path
        return df
    except FileNotFoundError:
        logging.warning("File not found. Please check the path to the metadata file.")
        return False


def concat_metadata(df):
    agg_func = {
        "itemid": "first",
        "appno": "first",
        "article": "first",
        "conclusion": "first",
        "docname": "first",
        "doctype": "first",
        "doctypebranch": "first",
        "ecli": "first",
        "importance": "first",
        "judgementdate": "first",
        "languageisocode": ", ".join,
        "originatingbody": "first",
        "violation": "first",
        "nonviolation": "first",
        "extractedappno": "first",
        "scl": "first",
    }
    new_df = df.groupby("ecli").agg(agg_func)
    # print(new_df)
    return new_df


def get_language_from_metadata(df):
    df = concat_metadata(df)
    df.to_json("langisocode-nodes.json", orient="records")


def node_identifier(ecli, itemid):
    """Canonical citation-network identifier for a document.

    Prefers the ECLI; documents without one (communicated cases, CLIN
    notes) fall back to their HUDOC itemid so their citations are kept.
    Returns None when neither is available.
    """
    for value in (ecli, itemid):
        if pd.notna(value):
            value = str(value).strip()
            if value:
                return value
    return None


def retrieve_edges_list(df, df_unfiltered):
    """
    OPTIMIZED VERSION: Returns a dataframe consisting of 2 columns 'ecli' and 'references' which
    indicate a reference link between cases.

    params:
    df -- the node list extracted from the metadata
    df_unfiltered -- the complete dataframe from the metadata
    """
    logging.info("Pre-indexing data for fast lookups...")

    # Pre-index data for O(1) lookups instead of O(n) DataFrame filtering
    # Index by appno -> list of rows
    appno_index = {}
    for idx, row in df_unfiltered.iterrows():
        if pd.notna(row.appno):
            appnos = str(row.appno).split(";")
            for appno in appnos:
                appno = appno.strip()
                if appno:
                    if appno not in appno_index:
                        appno_index[appno] = []
                    appno_index[appno].append(idx)

    # Index by docname (normalized) -> list of rows
    docname_index = {}
    for idx, row in df_unfiltered.iterrows():
        if pd.notna(row.docname):
            docname = str(row.docname).strip().upper()
            if docname:
                if docname not in docname_index:
                    docname_index[docname] = []
                docname_index[docname].append(idx)

    # Pre-parse dates and years
    logging.info("Pre-parsing dates...")
    date_cache = {}
    year_cache = {}
    for idx, row in df_unfiltered.iterrows():
        if pd.notna(row.judgementdate):
            try:
                date = parse_date_cached(str(row.judgementdate))
                if date:
                    date_cache[idx] = date
                    year_cache[idx] = date.year
            except (ValueError, TypeError):
                pass

    # Pre-store language codes
    lang_cache = {}
    for idx, row in df_unfiltered.iterrows():
        if pd.notna(row.languageisocode):
            lang_cache[idx] = str(row.languageisocode).upper()

    # Pre-store node identifiers: prefer ECLI, fall back to itemid for
    # documents without one (communicated cases, CLIN notes). An empty
    # string must never be used — all such documents would collapse into
    # a single phantom node.
    ecli_cache = {}
    for idx, row in df_unfiltered.iterrows():
        ecli_cache[idx] = node_identifier(row.ecli, getattr(row, "itemid", None))
    ecli_cache = {idx: ident for idx, ident in ecli_cache.items() if ident}

    logging.info("Indexes created:")
    logging.info(f"  - Appno index: {len(appno_index)} entries")
    logging.info(f"  - Docname index: {len(docname_index)} entries")
    logging.info(f"  - Date cache: {len(date_cache)} entries")

    # Now process edges with fast lookups
    edges_list = []  # Collect edges in list, then convert to DataFrame at end
    count = 0
    tot_num_refs = 0
    missing_cases = []

    logging.info(f"Processing {len(df)} cases...")

    for index, item in tqdm(
        df.iterrows(),
        total=len(df),
        desc="Calculating edges",
        colour="GREEN",
        position=0,
        leave=True,
    ):
        eclis = set()
        citing_id = node_identifier(item.ecli, getattr(item, "itemid", None))

        if pd.notna(item.scl):
            ref_list = str(item.scl).split(";")
            new_ref_list = []
            for ref in ref_list:
                ref = re.sub("\n", "", ref).strip()
                if ref:
                    new_ref_list.append(ref)

            tot_num_refs += len(new_ref_list)

            for ref in new_ref_list:
                # Extract application numbers from the reference text
                # itself. The citing document's extractedappno list must
                # NOT be blended in here: it contains every application
                # number mentioned anywhere in the full text, so using it
                # per reference links each citation to every case the
                # document mentions.
                app_numbers = re.findall(r"[0-9]{3,5}\/[0-9]{2}", ref)
                app_numbers = [x.strip() for x in app_numbers if x.strip()]

                # Find matching cases
                candidate_indices = set()

                # First try by application number (fastest). Only match
                # cases whose OWN application number it is — matching
                # extractedappno here would link the citation to every
                # document that merely mentions that number.
                if app_numbers:
                    for appno in app_numbers:
                        if appno in appno_index:
                            candidate_indices.update(appno_index[appno])

                # If no matches, try by casename
                if not candidate_indices:
                    casename = get_casename(ref)
                    if casename:
                        # Normalize casename for lookup. The docname index keys
                        # are fully uppercased, so the lookup text must stay
                        # uppercase too (no "V." -> "v." style case flips, or
                        # the substring comparison below can never match).
                        patterns = clean_pattern
                        uptext = casename.upper()

                        if "BV" in uptext:
                            uptext = uptext.replace("BV", "B.V.")

                        for pattern in patterns:
                            uptext = re.sub(pattern, "", uptext)

                        uptext = re.sub(r"\[.*", "", uptext)
                        uptext = uptext.strip()

                        # Try exact match first
                        if uptext in docname_index:
                            candidate_indices.update(docname_index[uptext])
                        else:
                            # Try partial match (only if needed - this is
                            # slower). The containment must align on word
                            # boundaries: short names like "A v. POLAND"
                            # would otherwise match inside every
                            # "...a v. Poland"-suffixed docname.
                            padded_uptext = f" {uptext} "
                            matches_found = 0
                            for docname, indices in docname_index.items():
                                padded_docname = f" {docname} "
                                if (
                                    padded_uptext in padded_docname
                                    or padded_docname in padded_uptext
                                ):
                                    candidate_indices.update(indices)
                                    matches_found += len(indices)
                                    if matches_found > 100:  # Limit to prevent slowdown
                                        break

                # Filter candidates by language and year
                components = ref.split(",")
                year_from_ref = get_year_from_ref(components)

                # Determine language from reference
                if "v." in components[0]:
                    ref_lang = "ENG"
                else:
                    ref_lang = "FRE"

                # Filter candidates
                final_candidates = []
                for idx in candidate_indices:
                    # Filter by language
                    if idx in lang_cache:
                        case_lang = lang_cache[idx]
                        if ref_lang not in case_lang:
                            continue

                    # Filter by year
                    if year_from_ref > 0 and idx in year_cache:
                        if year_cache[idx] != year_from_ref:
                            continue
                    elif year_from_ref > 0:
                        # If no cached year, try parsing
                        try:
                            if idx in df_unfiltered.index:
                                row = df_unfiltered.loc[idx]
                                if pd.notna(row.judgementdate):
                                    date = parse_date_cached(str(row.judgementdate))
                                    if date and date.year != year_from_ref:
                                        continue
                        except (ValueError, TypeError, AttributeError):
                            continue

                    # Add ECLI if available
                    if idx in ecli_cache:
                        final_candidates.append(ecli_cache[idx])

                if final_candidates:
                    eclis.update(final_candidates)
                else:
                    count += 1
                    missing_cases.append(
                        {
                            "citing_id": citing_id,
                            "missing_references": ref,
                            "extracted_appnos": ";".join(app_numbers),
                            "casename": str(get_casename(ref) or "").strip(),
                            "year": year_from_ref if year_from_ref > 0 else None,
                            "ref_language": ref_lang,
                        }
                    )

            # Add edges for this case, keyed by ECLI or itemid fallback.
            # A case must not reference itself (original behavior).
            eclis.discard(citing_id)
            if eclis and citing_id:
                edges_list.append({"ecli": citing_id, "references": list(eclis)})

    logging.info(f"\nNumber of missed cases: {count}")
    logging.info(f"Total number of references: {tot_num_refs}")
    logging.info(f"Total edges found: {len(edges_list)}")

    # Convert to DataFrame
    if edges_list:
        edges = pd.DataFrame(edges_list)
        edges = edges.groupby("ecli", as_index=False).agg({"references": "sum"})
    else:
        edges = pd.DataFrame(columns=["ecli", "references"])

    # One row per (citing document, unresolved reference), with the
    # parsed components so callers can distinguish out-of-corpus
    # citations from unparseable ones and resolve them later.
    if missing_cases:
        missing_df = (
            pd.DataFrame(missing_cases)
            .drop_duplicates(subset=["citing_id", "missing_references"])
            .reset_index(drop=True)
        )
    else:
        missing_df = pd.DataFrame(columns=MISSING_REFERENCE_COLUMNS)

    return edges, missing_df


def get_casename(ref):
    count = 0
    if "v." in ref:
        slice_at_versus = ref.split("v.")  # skip if typo (count how many)
    elif "c." in ref:
        slice_at_versus = ref.split("c.")
    else:
        count = count + 1
        name = ref.split(",")
        return name[0]

    num_commas = slice_at_versus[0].count(",")

    if num_commas > 0:
        num_commas = num_commas + 1
        name = ",".join(ref.split(",", num_commas)[:num_commas])
    else:
        name = ref.split(",")
        return name[0]
    return name


def get_year_from_ref(ref):
    """Fixed version that initializes date variable."""
    date = None  # Initialize date variable
    for component in ref:
        if "§" in component:
            continue
        component = re.sub("judgment of ", "", component)
        parsed_date = parse_date_cached(component)
        if parsed_date is not None:
            date = parsed_date
        elif "ECHR" in component or "CEDH" in component:
            date_str = re.sub("ECHR ", "", component)
            date_str = re.sub("CEDH ", "", date_str)
            date_str = date_str.strip()
            date_str = re.sub("-.*", "", date_str)
            date_str = re.sub(r"\s.*", "", date_str)
            date = parse_date_cached(date_str)

    try:
        if date is not None:
            return date.year
        return 0
    except (AttributeError, TypeError):
        return 0


def echr_nodes_edges(metadata_path=None, data=None):
    """
    Create nodes and edges list for the ECHR data.

    Parameters:
    - metadata_path: Path to metadata CSV file (optional if data is provided)
    - data: DataFrame with metadata (optional if metadata_path is provided)
    """
    logging.info("\n--- COLLECTING METADATA ---\n")
    if metadata_path:
        data = open_metadata(metadata_path)
        if data is False:
            return "", "", ""
    elif data is None:
        logging.warning("No dataframe data provided. Returning...")
        return "", "", ""

    logging.info("\n--- EXTRACTING NODES LIST ---\n")
    # get_language_from_metadata(nodes)

    logging.info("\n--- EXTRACTING EDGES LIST ---\n")
    edges, missing_df = retrieve_edges_list(data, data)

    # nodes.to_json(JSON_ECHR_NODES, orient="records")
    # edges.to_json(JSON_ECHR_EDGES, orient="records")
    return data, edges, missing_df
