"""
Catalogue des séries FRED et règles méthodologiques du dashboard macro US.
Tout ce qui est "configuration" est ici, pour modifier facilement sans toucher au reste.
"""

# ============================================================
# CATALOGUE DES SÉRIES
# direction: 'up' = la hausse est un signal de stress, 'down' = la baisse est un signal
# ============================================================

SERIES_CATALOG = {
    'credit_menages': {
        'DRCCLACBS':     {'name': 'Delinquency rate — Credit Cards (all banks)', 'freq': 'Q', 'direction': 'up', 'unit': '%'},
        'DRCLACBS':      {'name': 'Delinquency rate — Consumer Loans (all)',     'freq': 'Q', 'direction': 'up', 'unit': '%'},
        'DRSFRMACBS':    {'name': 'Delinquency rate — Single-Family Mortgages',  'freq': 'Q', 'direction': 'up', 'unit': '%'},
        'DRCCLT100S':    {'name': 'Delinquency rate — Credit Cards (top 100 banks)', 'freq': 'Q', 'direction': 'up', 'unit': '%'},
        'DRCCLOBS':      {'name': 'Delinquency rate — Credit Cards (small banks)', 'freq': 'Q', 'direction': 'up', 'unit': '%'},
        'TOTALSL':       {'name': 'Total Consumer Credit Outstanding',           'freq': 'M', 'direction': 'up', 'unit': 'M$'},
        'REVOLSL':       {'name': 'Revolving Consumer Credit (cartes)',          'freq': 'M', 'direction': 'up', 'unit': 'M$'},
        'PSAVERT':       {'name': 'Personal Savings Rate',                       'freq': 'M', 'direction': 'down', 'unit': '%'},
    },
    'stress_bancaire': {
        'WALCL':         {'name': 'Fed Balance Sheet (Total Assets)',            'freq': 'W', 'direction': 'up', 'unit': 'M$'},
        'RRPONTSYD':     {'name': 'Overnight Reverse Repo (RRP)',                'freq': 'D', 'direction': 'down', 'unit': 'B$'},
        'WRESBAL':       {'name': 'Bank Reserves at the Fed',                    'freq': 'W', 'direction': 'down', 'unit': 'M$'},
        'H41RESPPALDKNWW': {'name': 'Discount Window Borrowing',                 'freq': 'W', 'direction': 'up', 'unit': 'M$'},
        'TOTBKCR':       {'name': 'Bank Credit (all commercial banks)',          'freq': 'W', 'direction': 'down', 'unit': 'B$'},
        'DPSACBW027SBOG':{'name': 'Bank Deposits',                               'freq': 'W', 'direction': 'down', 'unit': 'B$'},
    },
    'liquidite': {
        'SOFR':          {'name': 'SOFR (overnight collat. rate)',               'freq': 'D', 'direction': 'up', 'unit': '%'},
        'NFCI':          {'name': 'Chicago Fed Nat. Financial Conditions Index', 'freq': 'W', 'direction': 'up', 'unit': 'idx'},
        'STLFSI4':       {'name': 'St. Louis Fed Financial Stress Index',        'freq': 'W', 'direction': 'up', 'unit': 'idx'},
        'T10Y2Y':        {'name': 'Yield Curve 10Y-2Y',                          'freq': 'D', 'direction': 'down', 'unit': '%'},
        'T10Y3M':        {'name': 'Yield Curve 10Y-3M (le plus prédictif)',      'freq': 'D', 'direction': 'down', 'unit': '%'},
        'DGS10':         {'name': '10-Year Treasury Yield',                      'freq': 'D', 'direction': 'up', 'unit': '%'},
    },
    'corporate': {
        'BAMLH0A0HYM2':  {'name': 'High Yield OAS Spread',                       'freq': 'D', 'direction': 'up', 'unit': '%'},
        'BAMLC0A0CM':    {'name': 'Investment Grade OAS Spread',                 'freq': 'D', 'direction': 'up', 'unit': '%'},
        'BAMLH0A3HYC':   {'name': 'CCC & lower High Yield OAS',                  'freq': 'D', 'direction': 'up', 'unit': '%'},
        'DRBLACBS':      {'name': 'Delinquency Rate — Business Loans',           'freq': 'Q', 'direction': 'up', 'unit': '%'},
        'BUSLOANS':      {'name': 'Commercial & Industrial Loans',               'freq': 'W', 'direction': 'down', 'unit': 'B$'},
    },
    'immobilier': {
        'DRCRELEXFACBS': {'name': 'Delinquency Rate — Commercial Real Estate',   'freq': 'Q', 'direction': 'up', 'unit': '%'},
        'DRSREACBS':     {'name': 'Delinquency Rate — Real Estate Loans',        'freq': 'Q', 'direction': 'up', 'unit': '%'},
        'MORTGAGE30US':  {'name': '30-Year Fixed Mortgage Rate',                 'freq': 'W', 'direction': 'up', 'unit': '%'},
        'CSUSHPINSA':    {'name': 'Case-Shiller National Home Price Index',      'freq': 'M', 'direction': 'down', 'unit': 'idx'},
        'PERMIT':        {'name': 'Housing Permits',                             'freq': 'M', 'direction': 'down', 'unit': 'k'},
        'HOUST':         {'name': 'Housing Starts',                              'freq': 'M', 'direction': 'down', 'unit': 'k'},
    },
    'travail': {
        'ICSA':          {'name': 'Initial Jobless Claims',                      'freq': 'W', 'direction': 'up', 'unit': 'k'},
        'CCSA':          {'name': 'Continued Claims',                            'freq': 'W', 'direction': 'up', 'unit': 'k'},
        'JTSQUR':        {'name': 'Quits Rate',                                  'freq': 'M', 'direction': 'down', 'unit': '%'},
        'JTSJOL':        {'name': 'Job Openings (JOLTS)',                        'freq': 'M', 'direction': 'down', 'unit': 'k'},
        'TEMPHELPS':     {'name': 'Temp Help Services Employment',               'freq': 'M', 'direction': 'down', 'unit': 'k'},
        'AWHAETP':       {'name': 'Avg Weekly Hours (private)',                  'freq': 'M', 'direction': 'down', 'unit': 'h'},
        'U6RATE':        {'name': 'U-6 Underemployment Rate',                    'freq': 'M', 'direction': 'up', 'unit': '%'},
    },
    'consommation': {
        'PCEC96':        {'name': 'Real Personal Consumption Expenditures',      'freq': 'M', 'direction': 'down', 'unit': 'B$'},
        'DSPIC96':       {'name': 'Real Disposable Personal Income',             'freq': 'M', 'direction': 'down', 'unit': 'B$'},
        'CES0500000003': {'name': 'Avg Hourly Earnings (private)',               'freq': 'M', 'direction': 'down', 'unit': '$'},
        'UMCSENT':       {'name': 'Univ. Michigan Consumer Sentiment',           'freq': 'M', 'direction': 'down', 'unit': 'idx'},
        'RSAFS':         {'name': 'Retail Sales (advance)',                      'freq': 'M', 'direction': 'down', 'unit': 'M$'},
    },
    'sloos': {
        'DRTSCILM':  {'name': 'SLOOS — Tightening C&I (large/middle)', 'freq': 'Q', 'direction': 'up', 'unit': '%'},
        'DRTSCIS':   {'name': 'SLOOS — Tightening C&I (small firms)',  'freq': 'Q', 'direction': 'up', 'unit': '%'},
        'DRTSCLCC':  {'name': 'SLOOS — Tightening Credit Cards',       'freq': 'Q', 'direction': 'up', 'unit': '%'},
        'DRSDCILM':  {'name': 'SLOOS — Stronger demand C&I',           'freq': 'Q', 'direction': 'down', 'unit': '%'},
    },
}

# ============================================================
# RÈGLES MÉTHODOLOGIQUES
# ============================================================

# Séries en mode "z-score uniquement" : drift et momentum désactivés
# (régime monétaire change, ou variables centrées zéro)
REGIME_CHANGE_SERIES = {
    # Taux d'intérêt — régime monétaire structurellement différent
    'DGS10', 'SOFR', 'MORTGAGE30US',
    # Bilan Fed et plomberie monétaire
    'WALCL', 'RRPONTSYD', 'WRESBAL',
    # Volumes nominaux (croissent avec inflation/population)
    'TOTALSL', 'REVOLSL', 'BUSLOANS', 'TOTBKCR', 'DPSACBW027SBOG',
    'PCEC96', 'DSPIC96', 'RSAFS', 'CES0500000003',
    'CSUSHPINSA',
    'PERMIT', 'HOUST',
    'JTSJOL', 'TEMPHELPS', 'ICSA', 'CCSA',
    # Variables centrées zéro (drift en % explose)
    'T10Y2Y', 'T10Y3M', 'NFCI', 'STLFSI4',
    'DRTSCILM', 'DRTSCIS', 'DRTSCLCC', 'DRSDCILM',
}

# Séries non-stationnaires : backtest sur ΔYoY, pas sur niveau
NON_STATIONARY = {
    'TOTALSL', 'REVOLSL', 'BUSLOANS', 'TOTBKCR', 'DPSACBW027SBOG',
    'WALCL', 'WRESBAL', 'RRPONTSYD',
    'TEMPHELPS', 'JTSJOL', 'ICSA', 'CCSA',
    'PERMIT', 'HOUST',
    'CSUSHPINSA', 'CES0500000003',
    'PCEC96', 'DSPIC96', 'RSAFS',
    'UMCSENT', 'AWHAETP',
}

# Séries où le momentum (ΔYoY pct_change) n'a pas de sens (cross-zero)
NO_MOMENTUM_SERIES = {
    'T10Y2Y', 'T10Y3M', 'NFCI', 'STLFSI4',
    'RRPONTSYD', 'WALCL', 'WRESBAL',
    'SOFR', 'DGS10',
    'DRTSCILM', 'DRTSCIS', 'DRTSCLCC', 'DRSDCILM',
}

# ============================================================
# CONSTANTES NUMÉRIQUES
# ============================================================

PRE_COVID_START = '1985-01-01'
PRE_COVID_END = '2019-12-31'
PRE_COVID_REF_START = '2015-01-01'
PRE_COVID_REF_END = '2019-12-31'
ZSCORE_WINDOW_YEARS = 5
ZSCORE_WARNING = 1.5
ZSCORE_DANGER = 2.5
DRIFT_WARNING = 25  # %
DRIFT_DANGER = 50   # %
MOMENTUM_WARNING = 20  # %
STRESS_COMPONENT_WEIGHTS = {
    'zscore': 0.50,
    'drift': 0.25,
    'momentum': 0.25,
}
FALSE_POSITIVE_WARNING_LEVEL = ZSCORE_WARNING
FALSE_POSITIVE_PENALTY = 1.0
FALSE_POSITIVE_BUFFER_MONTHS = 12

# ============================================================
# RÉCESSIONS NBER (pour backtest)
# ============================================================

import pandas as pd

NBER_RECESSIONS = [
    pd.Timestamp('1990-07-01'),
    pd.Timestamp('2001-03-01'),
    pd.Timestamp('2007-12-01'),
    pd.Timestamp('2020-02-01'),
]

NBER_RECESSION_PERIODS = [
    ('1990-07-01', '1991-03-01'),
    ('2001-03-01', '2001-11-01'),
    ('2007-12-01', '2009-06-01'),
    ('2020-02-01', '2020-04-01'),
]

# ============================================================
# AFFICHAGE
# ============================================================

FAMILY_LABELS = {
    'credit_menages': 'Crédit ménages',
    'stress_bancaire': 'Stress bancaire',
    'liquidite': 'Liquidité',
    'corporate': 'Corporate',
    'immobilier': 'Immobilier',
    'travail': 'Travail',
    'consommation': 'Consommation',
    'sloos': 'SLOOS',
}

FAMILY_ICONS = {
    'credit_menages': '💳',
    'stress_bancaire': '🏦',
    'liquidite': '💧',
    'corporate': '🏭',
    'immobilier': '🏘️',
    'travail': '👔',
    'consommation': '🛒',
    'sloos': '📋',
}
