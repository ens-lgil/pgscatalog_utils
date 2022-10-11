import logging

import polars as pl

logger = logging.getLogger(__name__)


def make_logs(scorefile: pl.LazyFrame, match_candidates: pl.LazyFrame, filter_summary: pl.LazyFrame, dataset: str):
    # summary log -> aggregated from best matches (one per scoring file line)
    # big log -> unaggregated, written to compressed gzip, possibly multiple matches per scoring file line
    summary_log, big_log = _join_match_candidates(scorefile=scorefile, matches=match_candidates,
                                                  filter_summary=filter_summary,
                                                  dataset=dataset)

    # make sure the aggregated best log matches the scoring file accession line count
    summary_count: pl.LazyFrame = (summary_log.groupby(pl.col('accession'))
                                   .agg(pl.sum('count')))
    log_count: pl.DataFrame = (scorefile.groupby("accession")
                               .agg(pl.count())
                               .join(summary_count, on='accession')).collect()

    assert (log_count.get_column('count') == log_count.get_column(
        'count_right')).all(), "Log doesn't match input scoring file"
    logger.debug("Log matches input scoring file")

    return _prettify_log(big_log), _prettify_summary(summary_log)


def make_summary_log(best_matches: pl.LazyFrame, filter_summary: pl.LazyFrame) -> pl.LazyFrame:
    """ Make an aggregated table """
    logger.debug("Aggregating best match log into a summary table")
    return (best_matches
            .groupby(['dataset', 'accession', 'match_status', 'ambiguous', 'is_multiallelic', 'match_flipped',
                      'duplicate_best_match', 'duplicate_ID'])
            .agg(pl.count())
            .join(filter_summary, how='left', on='accession'))


def _prettify_summary(df: pl.LazyFrame) -> pl.LazyFrame:
    keep_cols = ["dataset", "accession", "score_pass", "match_status", "ambiguous", "is_multiallelic",
                 "duplicate_best_match", "duplicate_ID", "count", "percent"]
    return (df.with_column((pl.col("count") / pl.sum("count") * 100)
                           .over(["dataset", "accession"])
                           .alias("percent"))
            .select(keep_cols))


def _prettify_log(df: pl.LazyFrame) -> pl.LazyFrame:
    keep_cols = ["row_nr", "accession", "chr_name", "chr_position", "effect_allele", "other_allele", "effect_weight",
                 "effect_type", "ID", "REF", "ALT", "matched_effect_allele", "match_type", "is_multiallelic",
                 "ambiguous", "duplicate_best_match", "duplicate_ID", "match_status", "dataset"]
    pretty_df = (df.select(keep_cols)
                 .select(pl.exclude("^.*_right"))
                 .sort(["accession", "row_nr", "chr_name", "chr_position", "match_status"]))
    return pretty_df


def _join_match_candidates(scorefile: pl.LazyFrame, matches: pl.LazyFrame, filter_summary: pl.LazyFrame,
                           dataset: str) -> tuple[pl.LazyFrame, pl.LazyFrame]:
    """ Join match candidates against the original scoring file """
    logger.debug("Making big logs")

    # make the summary log using the best matched candidates only
    summary_log = (scorefile.join(matches.filter(pl.col('best_match') == True),
                                  on=['row_nr', 'accession'],
                                  how='outer')  # left join would make checking line count later pointless
                   .with_column(pl.lit(dataset).alias('dataset'))
                   .select(pl.exclude("^.*_right$"))
                   .with_column(pl.col('match_status').fill_null("unmatched"))
                   .pipe(make_summary_log, filter_summary))

    # make a raw log with all match candidates included
    raw_log = (scorefile.join(matches,
                              on=['row_nr', 'accession'],
                              how='outer')
               .with_column(pl.lit(dataset).alias('dataset'))
               .select(pl.exclude("^.*_right$"))).with_column(pl.col('match_status').fill_null("unmatched"))

    return summary_log, raw_log