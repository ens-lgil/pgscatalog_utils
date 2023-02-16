import logging
import pandas as pd
import numpy as np
import os

logger = logging.getLogger(__name__)


def read_projection(loc_sscores: list[str], loc_related_ids=None):
    """
    Read PCA projection data from pgsc_calc pipeline
    :param loc_sscore: path to the result of PCA projection (.sscore format)
    :param loc_related_ids: path to newline-delimited list of IDs for related samples that can be used to filter
    :return: pandas dataframe with PC information
    """
    proj = pd.DataFrame()
    nvars = []

    for i, path in enumerate(loc_sscores):
        logger.debug("Reading PCA projection: {}".format(path))
        df = pd.read_csv(path, sep='\t')

        # Check nvars
        path_vars = path + '.vars'
        if os.path.isfile(path_vars):
            nvars.append(len(open(path_vars).read().strip().split('\n')))
        else:
            nvars.append(None)

        match (df.columns[0]):
            # handle case of #IID -> IID (happens when #FID is present)
            case '#IID':
                pass
            case '#FID':
                df.rename({'IID': '#IID'}, axis=g1, inplace=True)
                df.drop(['#FID'], axis=1,  inplace=True)
            case _:
                assert False, "Invalid columns"

        df.set_index('#IID')
        df.columns = [x.replace('_SUM', '') for x in df.columns]

        if i == 0:
            logger.debug('Initialising combined DF')
            proj = df.copy()
            aggcols = [x for x in df.columns if x.startswith('PC')]
        else:
            logger.debug('Adding to combined DF')
            proj = proj[aggcols].add(df[aggcols], fill_value=0)

    # Read/process IDs for unrelated samples (usually reference dataset)
    if loc_related_ids:
        logger.debug("Flagging related samples with: {}".format(loc_related_ids))
        proj['Unrelated'] = True
        with open(loc_related_ids, 'r') as infile:
            IDs_related = [x.strip() for x in infile.readlines()]
        proj.loc[proj.index.isin(IDs_related), 'Unrelated'] = False
    else:
        proj['Unrelated'] = np.nan

    if None in nvars:
        return proj, None
    else:
        return proj, sum(nvars)


def read_pgs(loc_sscore):
    pgs = pd.read_csv(loc_sscore, sep='\t', index_col='#IID')
    return pgs