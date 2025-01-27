import polars as pl
import logging

logger = logging.getLogger(__name__)


def complement_valid_alleles(df: pl.DataFrame, flip_cols: list[str]) -> pl.DataFrame:
    """ Improved function to complement alleles. Will only complement sequences that are valid DNA.
    """
    for col in flip_cols:
        logger.debug(f"Complementing column {col}")
        new_col = col + '_FLIP'
        df = df.with_column(
            pl.when(pl.col(col).str.contains('^[ACGT]+$'))
                .then(pl.col(col).str.replace_all("A", "V")
                           .str.replace_all("T", "X")
                           .str.replace_all("C", "Y")
                           .str.replace_all("G", "Z")
                           .str.replace_all("V", "T")
                           .str.replace_all("X", "A")
                           .str.replace_all("Y", "G")
                           .str.replace_all("Z", "C"))
                .otherwise(pl.col(col))
                .alias(new_col)
        )
    return df


def handle_multiallelic(df: pl.DataFrame, remove_multiallelic: bool, pvar: bool) -> pl.DataFrame:
    # plink2 pvar multi-alleles are comma-separated
    df: pl.DataFrame = (df.with_column(
        pl.when(pl.col("ALT").str.contains(','))
        .then(pl.lit(True))
        .otherwise(pl.lit(False))
        .alias('is_multiallelic')))

    if df['is_multiallelic'].sum() > 0:
        logger.debug("Multiallelic variants detected")
        if remove_multiallelic:
            if not pvar:
                logger.warning("--remove_multiallelic requested for bim format, which already contains biallelic "
                               "variant representations only")
            logger.debug('Dropping multiallelic variants')
            return df[~df['is_multiallelic']]
        else:
            logger.debug("Exploding dataframe to handle multiallelic variants")
            df.replace('ALT', df['ALT'].str.split(by=','))  # turn ALT to list of variants
            return df.explode('ALT')  # expand the DF to have all the variants in different rows
    else:
        logger.debug("No multiallelic variants detected")
        return df


def check_weights(df: pl.DataFrame) -> None:
    """ Checks weights for scoring file variants that could be matched (e.g. have a chr & pos) """
    weight_count = df.filter(pl.col('chr_name').is_not_null() & pl.col('chr_position').is_not_null()).groupby(['accession', 'chr_name', 'chr_position', 'effect_allele']).count()
    if any(weight_count['count'] > 1):
        logger.error("Multiple effect weights per variant per accession detected in files: {}".format(list(weight_count.filter(pl.col('count') > 1)['accession'].unique())))
        raise Exception


def _annotate_multiallelic(df: pl.DataFrame) -> pl.DataFrame:
    df.with_column(pl.when(pl.col("ALT").str.contains(',')).then(pl.lit(True)).otherwise(pl.lit(False)).alias('is_multiallelic'))