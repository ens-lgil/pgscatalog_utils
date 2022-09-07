import logging

import polars as pl

logger = logging.getLogger(__name__)


def make_logs(scorefile, match_candidates, filter_summary, dataset):
    big_log = (_join_match_candidates(scorefile, match_candidates, dataset)
               .pipe(_prettify_log))
    summary_log = make_summary_log(big_log, filter_summary)

    return _prettify_log(big_log), summary_log


def make_summary_log(df, filter_summary):
    """ Make an aggregated table """
    return (df.filter(pl.col('best_match') != False)
            .groupby(['dataset', 'accession', 'best_match', 'ambiguous', 'is_multiallelic', 'duplicate', 'exclude'])
            .count()
            .join(filter_summary, how='left', on='accession')).sort(['dataset', 'accession', 'score_pass'], reverse=True)


def _prettify_summary(df: pl.DataFrame):
    keep_cols = ["dataset", "accession", "score_pass", "ambiguous", "is_multiallelic", "duplicate", "count"]


def _prettify_log(df: pl.DataFrame) -> pl.DataFrame:
    keep_cols = ["row_nr", "accession", "chr_name", "chr_position", "effect_allele", "other_allele", "effect_weight",
                 "effect_type", "ID", "REF", "ALT", "matched_effect_allele", "match_type", "is_multiallelic",
                 "ambiguous", "duplicate", "best_match", "exclude", "dataset"]
    pretty_df = (df.select(keep_cols).select(pl.exclude("^.*_right")))
    return pretty_df.sort(["accession", "row_nr", "chr_name", "chr_position"])


def _join_match_candidates(scorefile: pl.DataFrame, matches: pl.DataFrame, dataset: str) -> pl.DataFrame:
    """
    Join match candidates against the original scoring file

    Uses an outer join because mltiple match candidates may exist with different match types

    Multiple match candidates will exist as extra rows in the joined dataframe
    """
    return (scorefile.join(matches, on=['row_nr', 'accession'], how='outer')
            .with_column(pl.lit(dataset).alias('dataset'))
            .select(pl.exclude("^.*_right$")))
