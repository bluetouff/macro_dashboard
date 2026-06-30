#!/usr/bin/env python3
"""
snapshot_builder.py — Script de génération des snapshots macro.

Exécuté par cron chaque jour à 6h.
Télécharge les données FRED, calcule tous les scores et indicateurs,
écrit les résultats dans /var/lib/macro_dashboard/snapshots/.

L'app Streamlit lit uniquement ces snapshots — elle n'a JAMAIS accès à la clé FRED.

Usage:
    /opt/macro_dashboard/venv/bin/python /opt/macro_dashboard/snapshot_builder.py
"""

import os
import sys
import logging
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
from fredapi import Fred


# ============================================================
# CONFIG — Chargement de /etc/macro_dashboard/env
# ============================================================

def load_env(env_file='/etc/macro_dashboard/env'):
    """Charge un fichier .env minimal (KEY=VALUE par ligne, # pour commentaires)."""
    env = {}
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    except PermissionError:
        sys.exit(f"ERREUR: Permissions insuffisantes pour lire {env_file}")
    except FileNotFoundError:
        sys.exit(f"ERREUR: Fichier {env_file} non trouvé")
    return env


ENV = load_env()
FRED_API_KEY = ENV.get('FRED_API_KEY')
SNAPSHOTS_DIR = Path(ENV.get('SNAPSHOTS_DIR', '/var/lib/macro_dashboard/snapshots'))
LOG_DIR = Path(ENV.get('LOG_DIR', '/var/log/macro_dashboard'))

if not FRED_API_KEY:
    sys.exit("ERREUR: FRED_API_KEY manquant dans /etc/macro_dashboard/env")

SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# LOGGING
# ============================================================

LOG_FILE = LOG_DIR / 'builder.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger('snapshot_builder')


# ============================================================
# IMPORT DU CATALOGUE DEPUIS LE PROJET
# ============================================================

# Le script est dans /opt/macro_dashboard, le catalogue aussi
sys.path.insert(0, str(Path(__file__).parent))
from catalog import (
    SERIES_CATALOG, REGIME_CHANGE_SERIES, NON_STATIONARY, NO_MOMENTUM_SERIES,
    PRE_COVID_REF_START, PRE_COVID_REF_END,
    ZSCORE_WINDOW_YEARS, ZSCORE_WARNING, ZSCORE_DANGER,
    DRIFT_WARNING, NBER_RECESSIONS,
)


# ============================================================
# TÉLÉCHARGEMENT FRED
# ============================================================

def fetch_series(fred, sid, start='1985-01-01'):
    try:
        data = fred.get_series(sid, observation_start=start).dropna()
        return data if len(data) > 0 else None
    except Exception as e:
        log.warning(f"Échec téléchargement {sid}: {e}")
        return None


def fetch_all(fred, start='1985-01-01'):
    log.info(f"Téléchargement de {sum(len(v) for v in SERIES_CATALOG.values())} séries FRED depuis {start}")
    all_data = {}
    errors = []
    for famille, sdict in SERIES_CATALOG.items():
        for sid, meta in sdict.items():
            data = fetch_series(fred, sid, start)
            if data is not None:
                all_data[sid] = data
            else:
                errors.append(sid)
    log.info(f"Téléchargées: {len(all_data)} / {sum(len(v) for v in SERIES_CATALOG.values())} (échecs: {len(errors)})")
    if errors:
        log.warning(f"Séries en échec: {errors}")
    return all_data


# ============================================================
# CALCUL DES MÉTRIQUES (live snapshot)
# ============================================================

def compute_metrics(data, sid, meta):
    if data is None or len(data) < 10:
        return None
    current = data.iloc[-1]
    current_date = data.index[-1]
    direction = meta['direction']
    sign = 1 if direction == 'up' else -1

    precovid = data.loc[PRE_COVID_REF_START:PRE_COVID_REF_END]
    baseline = precovid.mean() if len(precovid) > 0 else np.nan

    cutoff = current_date - pd.DateOffset(years=ZSCORE_WINDOW_YEARS)
    window = data.loc[cutoff:]
    if len(window) > 5 and window.std() > 0:
        zscore = (current - window.mean()) / window.std()
        signed_z = sign * zscore
    else:
        zscore = np.nan
        signed_z = np.nan

    if pd.notna(baseline) and baseline != 0:
        raw_drift = (current - baseline) / abs(baseline) * 100
        drift_pct = sign * raw_drift
        drift_z = drift_pct / (DRIFT_WARNING / ZSCORE_WARNING)
    else:
        drift_pct = np.nan
        drift_z = np.nan

    try:
        v1y = data.asof(current_date - pd.DateOffset(years=1))
        pct_1y = ((current - v1y) / v1y * 100) if pd.notna(v1y) and v1y != 0 else np.nan
    except Exception:
        pct_1y = np.nan
    try:
        v3m = data.asof(current_date - pd.DateOffset(months=3))
        pct_3m = ((current - v3m) / v3m * 100) if pd.notna(v3m) and v3m != 0 else np.nan
    except Exception:
        pct_3m = np.nan

    mom_signals = []
    if pd.notna(pct_3m):
        mom_signals.append(sign * pct_3m * 4)
    if pd.notna(pct_1y):
        mom_signals.append(sign * pct_1y)
    if mom_signals:
        momentum = max(mom_signals)
        mom_z = momentum / (20 / ZSCORE_WARNING)
    else:
        mom_z = np.nan

    candidates = []
    if pd.notna(signed_z):
        candidates.append(signed_z)
    if sid not in REGIME_CHANGE_SERIES and pd.notna(drift_z):
        candidates.append(drift_z)
    if sid not in NO_MOMENTUM_SERIES and pd.notna(mom_z):
        candidates.append(mom_z)
    stress_final = max(candidates) if candidates else np.nan

    return {
        'series_id': sid,
        'name': meta['name'],
        'freq': meta['freq'],
        'unit': meta['unit'],
        'direction': direction,
        'date': current_date,
        'current': current,
        'baseline_precovid': baseline,
        'zscore_5y': zscore,
        'signed_zscore': signed_z,
        'drift_vs_precovid_pct': drift_pct,
        'drift_zscore_equiv': drift_z,
        'pct_change_3m': pct_3m,
        'pct_change_1y': pct_1y,
        'momentum_zscore_equiv': mom_z,
        'stress_final': stress_final,
    }


# ============================================================
# BACKTEST PRÉDICTIF
# ============================================================

def historical_zscore(series, target_date, sid, window_years=5):
    if series is None or len(series) < 50:
        return np.nan
    available = series.loc[:target_date]
    if len(available) < 24:
        return np.nan

    if sid in NON_STATIONARY:
        try:
            yoy = available.pct_change(periods=12, fill_method=None).dropna()
            if len(yoy) < 24:
                return np.nan
            current_val = yoy.asof(target_date)
            if pd.isna(current_val):
                return np.nan
            cutoff = target_date - pd.DateOffset(years=window_years)
            window = yoy.loc[cutoff:target_date]
            if len(window) < 5 or window.std() == 0:
                return np.nan
            return (current_val - window.mean()) / window.std()
        except Exception:
            return np.nan
    else:
        try:
            current_val = available.asof(target_date)
            if pd.isna(current_val):
                return np.nan
        except Exception:
            return np.nan
        cutoff = target_date - pd.DateOffset(years=window_years)
        window = available.loc[cutoff:target_date]
        if len(window) < 5 or window.std() == 0:
            return np.nan
        return (current_val - window.mean()) / window.std()


def compute_predictive_power(all_data):
    horizons = [3, 6, 12]
    results = []
    for famille, sdict in SERIES_CATALOG.items():
        for sid, meta in sdict.items():
            if sid not in all_data:
                continue
            sign = 1 if meta['direction'] == 'up' else -1
            scores = {h: [] for h in horizons}
            for rec_date in NBER_RECESSIONS:
                for h in horizons:
                    target = rec_date - pd.DateOffset(months=h)
                    z = historical_zscore(all_data[sid], target, sid)
                    if pd.notna(z):
                        scores[h].append(sign * z)
            row = {'series_id': sid, 'name': meta['name'], 'famille': famille,
                   'mode': 'ΔYoY' if sid in NON_STATIONARY else 'niveau'}
            for h in horizons:
                row[f'avg_z_{h}m'] = np.mean(scores[h]) if scores[h] else np.nan
                row[f'n_obs_{h}m'] = len(scores[h])
            results.append(row)
    bt = pd.DataFrame(results)
    bt['pred_power'] = bt[['avg_z_3m', 'avg_z_6m', 'avg_z_12m']].mean(axis=1)
    return bt


def power_to_weight(power):
    if pd.isna(power): return 1.0
    if power >= 1.5: return 3.0
    if power >= 0.8: return 2.5
    if power >= 0.4: return 2.0
    if power >= 0.0: return 1.5
    if power >= -0.5: return 1.0
    return 0.5


# ============================================================
# RECONSTRUCTION HISTORIQUE MENSUELLE
# ============================================================

def reconstruct_historical(all_data, weights_map):
    log.info("Reconstruction mensuelle historique 1990 → now...")
    start = pd.Timestamp('1990-01-01')
    end = pd.Timestamp(datetime.now().strftime('%Y-%m-01'))
    dates = pd.date_range(start, end, freq='MS')
    history = []
    for d in dates:
        rows = []
        for famille, sdict in SERIES_CATALOG.items():
            for sid, meta in sdict.items():
                if sid not in all_data:
                    continue
                z = historical_zscore(all_data[sid], d, sid)
                if pd.notna(z):
                    sign = 1 if meta['direction'] == 'up' else -1
                    rows.append({'famille': famille, 'signed_z': sign * z,
                                 'weight': weights_map.get(sid, 1.0)})
        if not rows:
            continue
        dft = pd.DataFrame(rows)
        gs = (dft['signed_z'] * dft['weight']).sum() / dft['weight'].sum()
        fam = dft.groupby('famille').apply(
            lambda g: (g['signed_z'] * g['weight']).sum() / g['weight'].sum()
        ).to_dict()
        history.append({'date': d, 'global': gs,
                        **{f'fam_{k}': v for k, v in fam.items()}})
    log.info(f"Reconstruction: {len(history)} points mensuels")
    return pd.DataFrame(history).set_index('date')


# ============================================================
# MAIN
# ============================================================

def main():
    started = datetime.now()
    log.info("=" * 60)
    log.info(f"DÉBUT — snapshot builder @ {started:%Y-%m-%d %H:%M:%S}")

    try:
        fred = Fred(api_key=FRED_API_KEY)
        all_data = fetch_all(fred)

        if not all_data:
            log.error("Aucune série téléchargée — abandon")
            sys.exit(2)

        # 1. Snapshot du jour (live)
        log.info("Calcul du snapshot live...")
        rows = []
        for famille, sdict in SERIES_CATALOG.items():
            for sid, meta in sdict.items():
                if sid in all_data:
                    m = compute_metrics(all_data[sid], sid, meta)
                    if m:
                        m['famille'] = famille
                        rows.append(m)
        df_snap = pd.DataFrame(rows)
        log.info(f"Snapshot: {len(df_snap)} séries")

        # 2. Backtest et pondération empirique
        log.info("Backtest sur 4 récessions NBER...")
        bt = compute_predictive_power(all_data)
        power_map = dict(zip(bt['series_id'], bt['pred_power']))
        df_snap['power_empirique'] = df_snap['series_id'].map(power_map)
        df_snap['weight'] = df_snap['power_empirique'].apply(power_to_weight)
        df_snap['stress_weighted'] = df_snap['stress_final'] * df_snap['weight']

        weights_map = {sid: power_to_weight(p) for sid, p in power_map.items()}

        # 3. Reconstruction historique
        hist_df = reconstruct_historical(all_data, weights_map)

        # 4. Persistance des fichiers
        snap_date = datetime.now().strftime('%Y-%m-%d')

        # Fichiers "current" — toujours écrasés, lus par l'app
        df_snap.to_parquet(SNAPSHOTS_DIR / 'current_snapshot.parquet', index=False)
        bt.to_parquet(SNAPSHOTS_DIR / 'current_backtest.parquet', index=False)
        hist_df.to_parquet(SNAPSHOTS_DIR / 'historical.parquet')

        # Archives datées — pour construire un historique des snapshots eux-mêmes
        archive_dir = SNAPSHOTS_DIR / 'archive'
        archive_dir.mkdir(exist_ok=True)
        df_snap.to_parquet(archive_dir / f'snapshot_{snap_date}.parquet', index=False)

        # Fichier de métadonnées pour l'app (savoir quand le dernier refresh)
        meta = {
            'last_update': datetime.now().isoformat(),
            'n_series': len(df_snap),
            'n_errors': sum(len(v) for v in SERIES_CATALOG.values()) - len(df_snap),
            'data_start': '1985-01-01',
            'historical_points': len(hist_df),
        }
        pd.Series(meta).to_json(SNAPSHOTS_DIR / 'metadata.json')

        duration = (datetime.now() - started).total_seconds()
        log.info(f"SUCCÈS — durée: {duration:.1f}s")
        log.info(f"Fichiers écrits dans {SNAPSHOTS_DIR}/")
        log.info("=" * 60)

    except Exception as e:
        log.error(f"ERREUR FATALE: {e}")
        log.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
