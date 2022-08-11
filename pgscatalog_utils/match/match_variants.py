import argparse
import logging
import polars as pl
from glob import glob

from pgscatalog_utils.log_config import set_logging_level
from pgscatalog_utils.match.match import get_all_matches, check_match_rate
from pgscatalog_utils.match.read import read_target, read_scorefile
from pgscatalog_utils.match.write import write_out

logger = logging.getLogger(__name__)


def match_variants():
    args = _parse_args()

    set_logging_level(args.verbose)

    scorefile: pl.DataFrame = read_scorefile(path=args.scorefile)

    with pl.StringCache():
        n_target_files = len(glob(args.target))
        matches: list[pl.DataFrame] = []

        if n_target_files == 1:
            logger.debug("Single target variant file detected")
            matches = _match_single_target(args.target, scorefile, args.remove_multiallelic, args.remove_ambiguous)
        else:
            logger.debug("Multiple target variant files detected")
            matches = _match_multiple_targets(args.target, scorefile, args.remove_multiallelic, args.remove_ambiguous)

        dataset = args.dataset.replace('_', '-')  # underscores are delimiters in pgs catalog calculator
        check_match_rate(scorefile, matches, args.min_overlap, dataset)

    if matches.shape[0] == 0:  # this can happen if args.min_overlap = 0
        logger.error("Error: no target variants match any variants in scoring files")
        raise Exception

    write_out(matches, args.split, args.outdir, dataset)


def _match_multiple_targets(target_path, scorefile, remove_multiallelic, remove_ambiguous):
    matches = []
    for i, loc_target_current in enumerate(glob(target_path)):
        logger.debug(f'Matching scorefile(s) against target: {loc_target_current}')
        target: pl.DataFrame = read_target(path=loc_target_current,
                                           remove_multiallelic=remove_multiallelic)
        _check_target_chroms(target)
        matches.append(get_all_matches(scorefile, target, remove_ambiguous))
    return pl.concat(matches)


def _check_target_chroms(target) -> int:
    n_chrom: int = len(target['#CHROM'].unique().to_list())
    if n_chrom > 1:
        logger.critical(f"Multiple chromosomes detected in split file")
        raise Exception


def _match_single_target(target_path, scorefile, remove_multiallelic, remove_ambiguous):
    matches = []
    for chrom in scorefile['chr_name'].unique().to_list():
        target = read_target(target_path, remove_multiallelic=remove_multiallelic,
                             singie_file=True, chrom=chrom)
        if target:
            logger.debug(f"Matching chromosome {chrom}")
            matches.append(get_all_matches(scorefile, target, remove_ambiguous))

    return pl.concat(matches)


def _parse_args(args=None):
    parser = argparse.ArgumentParser(description='Match variants from a combined scoring file against target variants')
    parser.add_argument('-d', '--dataset', dest='dataset', required=True,
                        help='<Required> Label for target genomic dataset (e.g. "-d thousand_genomes")')
    parser.add_argument('-s', '--scorefiles', dest='scorefile', required=True,
                        help='<Required> Combined scorefile path (output of read_scorefiles.py)')
    parser.add_argument('-t', '--target', dest='target', required=True,
                        help='<Required> A table of target genomic variants (.bim format)')
    parser.add_argument('--split', dest='split', default=False, action='store_true',
                        help='<Optional> Split scorefile per chromosome?')
    parser.add_argument('--outdir', dest='outdir', required=True,
                        help='<Required> Output directory')
    parser.add_argument('-m', '--min_overlap', dest='min_overlap', required=True,
                        type=float, help='<Required> Minimum proportion of variants to match before error')
    parser.add_argument('--keep_ambiguous', dest='remove_ambiguous', action='store_false',
                        help='Flag to force the program to keep variants with ambiguous alleles, (e.g. A/T and G/C '
                             'SNPs), which are normally excluded (default: false). In this case the program proceeds '
                             'assuming that the genotype data is on the same strand as the GWAS whose summary '
                             'statistics were used to construct the score.'),
    parser.add_argument('--keep_multiallelic', dest='remove_multiallelic', action='store_false',
                        help='Flag to allow matching to multiallelic variants (default: false).')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='<Optional> Extra logging information')
    return parser.parse_args(args)


if __name__ == "__main__":
    match_variants()

# join matches and scorefile with keys depending on liftover
# count match type column
# matches.groupby('accession').agg([pl.count(), (pl.col('match_type') == None).sum().alias('no_match')])
