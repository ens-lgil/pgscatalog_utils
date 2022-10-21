import argparse
import logging
import os

import polars as pl

from pgscatalog_utils import config
from pgscatalog_utils.match.match_variants import log_and_write
from pgscatalog_utils.match.read import read_scorefile

logger = logging.getLogger(__name__)


def combine_matches():
    args = _parse_args()
    config.set_logging_level(args.verbose)

    config.POLARS_MAX_THREADS = args.n_threads
    os.environ['POLARS_MAX_THREADS'] = str(config.POLARS_MAX_THREADS)
    # now the environment variable, parsed argument args.n_threads, and threadpool should agree
    logger.debug(f"Setting POLARS_MAX_THREADS environment variable: {os.getenv('POLARS_MAX_THREADS')}")
    logger.debug(f"Using {config.POLARS_MAX_THREADS} threads to read CSVs")
    logger.debug(f"polars threadpool size: {pl.threadpool_size()}")

    with pl.StringCache():
        scorefile = read_scorefile(path=args.scorefile, chrom=None)  # chrom=None to read all variants
        matches = pl.concat(pl.collect_all([pl.scan_ipc(x, memory_map=False) for x in args.matches]))

        # make sure there's no duplicate variant_ids across pvars
        # processing batched chromosomes with overlapping variants might cause problems
        # e.g. chr1 1-100000, chr1 100001-500000
        n_matched = matches.filter(pl.col('match_status') == 'matched').shape[0]
        n_unique = matches.filter(pl.col('match_status') == 'matched').select(pl.col('ID')).unique().shape[0]
        assert n_matched == n_unique, "Duplicate IDs in final matches"

        dataset = args.dataset.replace('_', '-')  # _ used as delimiter in pgsc_calc
        log_and_write(matches=matches.lazy(), scorefile=scorefile, dataset=dataset, args=args)


def _parse_args(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dataset', dest='dataset', required=True,
                        help='<Required> Label for target genomic dataset')
    parser.add_argument('--min_overlap', dest='min_overlap', required=True,
                        type=float, help='<Required> Minimum proportion of variants to match before error')
    parser.add_argument('-s', '--scorefile', dest='scorefile', required=True,
                        help='<Required> Path to scorefile')
    parser.add_argument('--split', dest='split', default=True, action='store_true',
                        help='<Optional> Split scorefile per chromosome?')
    parser.add_argument('-m', '--matches', dest='matches', required=True, nargs='+',
                        help='<Required> List of match files')
    parser.add_argument('--outdir', dest='outdir', required=True,
                        help='<Required> Output directory')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='<Optional> Extra logging information')
    parser.add_argument('-n', dest='n_threads', default=1, help='<Optional> n threads for matching', type=int)
    return parser.parse_args(args)


if __name__ == "__main__":
    combine_matches()