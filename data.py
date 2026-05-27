"""
Module de téléchargement et calcul des métriques.
Utilise le cache Streamlit pour éviter de re-télécharger à chaque ouverture.
"""

import os
import pandas as pd
import numpy as np
import streamlit as st
from fredapi import Fred
from datetime import datetime
from catalog import (
    SERIES_CATALOG, REGIME_CHANGE_SERIES, NON_STATIONARY, NO_MOMENTUM_SERIES,
    PRE_COVID_REF_START, PRE_COVID_REF_END,
    ZSCORE_WINDOW_YEARS, ZSCORE_WARNING, ZSCORE_DANGER,
    DRIFT_WARNING, NBER_RECESSIONS,
)


# ============================================================
# SETUP FRED
# ============================================================

def get_fred():
    """Retourne une instance Fred avec la clé API depuis l'environnement."""
    key = os.environ.get('FRED_API_KEY')
    if not key:
        st.error("⚠️ Clé API FRED manquante. Configure FRED_API_KEY dans ton environnement.")
        st.info("Dans ton terminal avant de lancer l'app :\n```\nexport FRED_API_KEY='ta_cle_ici'\nstreamlit run app.py\n```")
        st.stop()
    return Fred(api_key=key)


# ============================================================
# TÉLÉCHARGEMENT (cache 6h)
# ============================================================

@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_all_series(start='1985-01-01'):
    """Télécharge toutes les séries FRED. Cache 6 heures."""
    fred = get_fred()
    all_data = {}
    errors = []
    
    progress = st.progress(0)
    status = st.empty()
    
    total = sum(len(v) for v in SERIES_CATALOG.values())
    count = 0
    
    for famille, series_dict in SERIES_CATALOG.items():
        for sid, meta in series_dict.items():
            count += 1
            status.text(f"Téléchargement de {sid} ({count}/{total})...")
            progress.progress(count / total)
            try:
                data = fred.get_series(sid, observation_start=start).dropna()
                if len(data) > 0:
                    all_data[sid] = data
            except Exception as e:
                errors.append((sid, str(e)))
    
    progress.empty()
    status.empty()
    
    return all_data, errors


# ============================================================
# CALCUL DES MÉTRIQUES
# ============================================================

def compute_metrics_for_series(data, sid, meta):
    """Calcule toutes les métriques pour une série."""
    if data is None or len(data) < 10:
        return None
    
    current = data.iloc[-1]
    current_date = data.index[-1]
    direction = meta['direction']
    sign = 1 if direction == 'up' else -1
    
    # Baseline pré-COVID
    precovid = data.loc[PRE_COVID_REF_START:PRE_COVID_REF_END]
    baseline = precovid.mean() if len(precovid) > 0 else np.nan
    
    # Z-score 5Y
    cutoff = current_date - pd.DateOffset(years=ZSCORE_WINDOW_YEARS)
    window = data.loc[cutoff:]
    if len(window) > 5 and window.std() > 0:
        zscore = (current - window.mean()) / window.std()
        signed_z = sign * zscore
    else:
        zscore = np.nan
        signed_z = np.nan
    
    # Drift vs baseline pré-COVID (signé)
    if pd.notna(baseline) and baseline != 0:
        raw_drift = (current - baseline) / abs(baseline) * 100
        drift_pct = sign * raw_drift
        drift_zscore_equiv = drift_pct / (DRIFT_WARNING / ZSCORE_WARNING)
    else:
        drift_pct = np.nan
        drift_zscore_equiv = np.nan
    
    # Momentum (Δ 3M et 1Y)
    try:
        val_1y = data.asof(current_date - pd.DateOffset(years=1))
        pct_1y = ((current - val_1y) / val_1y * 100) if pd.notna(val_1y) and val_1y != 0 else np.nan
    except Exception:
        pct_1y = np.nan
    try:
        val_3m = data.asof(current_date - pd.DateOffset(months=3))
        pct_3m = ((current - val_3m) / val_3m * 100) if pd.notna(val_3m) and val_3m != 0 else np.nan
    except Exception:
        pct_3m = np.nan
    
    momentum_signals = []
    if pd.notna(pct_3m):
        momentum_signals.append(sign * pct_3m * 4)
    if pd.notna(pct_1y):
        momentum_signals.append(sign * pct_1y)
    if momentum_signals:
        momentum = max(momentum_signals)
        MOMENTUM_WARNING = 20
        momentum_zscore_equiv = momentum / (MOMENTUM_WARNING / ZSCORE_WARNING)
    else:
        momentum_zscore_equiv = np.nan
    
    # Score composite final : max des dimensions valides
    candidates = []
    if pd.notna(signed_z):
        candidates.append(signed_z)
    if sid not in REGIME_CHANGE_SERIES and pd.notna(drift_zscore_equiv):
        candidates.append(drift_zscore_equiv)
    if sid not in NO_MOMENTUM_SERIES and pd.notna(momentum_zscore_equiv):
        candidates.append(momentum_zscore_equiv)
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
        'drift_zscore_equiv': drift_zscore_equiv,
        'pct_change_3m': pct_3m,
        'pct_change_1y': pct_1y,
        'momentum_zscore_equiv': momentum_zscore_equiv,
        'stress_final': stress_final,
    }


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def compute_all_metrics(_all_data_keys, all_data_hash):
    """Calcule les métriques pour toutes les séries. 
    Le hash dans la signature force le recalcul si all_data change."""
    pass  # placeholder, on utilise compute_dashboard ci-dessous


def compute_dashboard(all_data):
    """Construit le DataFrame complet du dashboard à partir des données téléchargées."""
    rows = []
    for famille, series_dict in SERIES_CATALOG.items():
        for sid, meta in series_dict.items():
            if sid in all_data:
                m = compute_metrics_for_series(all_data[sid], sid, meta)
                if m:
                    m['famille'] = famille
                    rows.append(m)
    return pd.DataFrame(rows)


# ============================================================
# BACKTEST HISTORIQUE — Power prédictif de chaque série
# ============================================================

def historical_zscore(series, target_date, sid, window_years=5):
    """Z-score à target_date sans look-ahead, en mode niveau ou ΔYoY."""
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


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def compute_predictive_power(_all_data, all_data_keys):
    """Backteste chaque série sur les 4 récessions NBER. Cache 24h (lent)."""
    horizons = [3, 6, 12]
    results = []
    
    for famille, series_dict in SERIES_CATALOG.items():
        for sid, meta in series_dict.items():
            if sid not in _all_data:
                continue
            direction = meta['direction']
            sign = 1 if direction == 'up' else -1
            
            scores_by_horizon = {h: [] for h in horizons}
            for rec_date in NBER_RECESSIONS:
                for h in horizons:
                    target = rec_date - pd.DateOffset(months=h)
                    z = historical_zscore(_all_data[sid], target, sid)
                    if pd.notna(z):
                        scores_by_horizon[h].append(sign * z)
            
            row = {
                'series_id': sid,
                'name': meta['name'],
                'famille': famille,
                'mode': 'ΔYoY' if sid in NON_STATIONARY else 'niveau',
            }
            for h in horizons:
                row[f'avg_z_{h}m'] = np.mean(scores_by_horizon[h]) if scores_by_horizon[h] else np.nan
                row[f'n_obs_{h}m'] = len(scores_by_horizon[h])
            results.append(row)
    
    bt = pd.DataFrame(results)
    bt['pred_power'] = bt[['avg_z_3m', 'avg_z_6m', 'avg_z_12m']].mean(axis=1)
    bt['n_min'] = bt[['n_obs_3m', 'n_obs_6m', 'n_obs_12m']].min(axis=1)
    return bt


def power_to_weight(power):
    """Convertit le pred_power historique en poids empirique."""
    if pd.isna(power):
        return 1.0
    if power >= 1.5: return 3.0
    if power >= 0.8: return 2.5
    if power >= 0.4: return 2.0
    if power >= 0.0: return 1.5
    if power >= -0.5: return 1.0
    return 0.5


def apply_weights(df, bt):
    """Ajoute les poids empiriques et le score pondéré."""
    power_map = dict(zip(bt['series_id'], bt['pred_power']))
    df = df.copy()
    df['power_empirique'] = df['series_id'].map(power_map)
    df['weight'] = df['power_empirique'].apply(power_to_weight)
    df['stress_weighted'] = df['stress_final'] * df['weight']
    return df


# ============================================================
# SCORES AGRÉGÉS
# ============================================================

def family_scores(df):
    """Calcule le score pondéré par famille."""
    def wfam(g):
        w = g['weight']
        s = g['stress_final']
        return (s * w).sum() / w.sum() if w.sum() > 0 else np.nan
    fam = df.groupby('famille').apply(wfam).rename('score')
    maxes = df.groupby('famille')['stress_final'].max().rename('max')
    counts = df.groupby('famille').size().rename('n')
    return pd.concat([fam, maxes, counts], axis=1).sort_values('score', ascending=False)


def global_score(df):
    """Score global pondéré."""
    w = df['weight']
    s = df['stress_final']
    return (s * w).sum() / w.sum() if w.sum() > 0 else np.nan


def status_emoji(score, warning=ZSCORE_WARNING, danger=ZSCORE_DANGER):
    if pd.isna(score): return '⚪'
    if score >= danger: return '🔴'
    if score >= warning: return '🟡'
    return '🟢'


def status_color(score, warning=ZSCORE_WARNING, danger=ZSCORE_DANGER):
    """Couleur hex pour KPI cards."""
    if pd.isna(score): return '#888888'
    if score >= danger: return '#c03028'
    if score >= warning: return '#e0a020'
    if score > 0: return '#5a8a3a'
    return '#2a7a4a'


# ============================================================
# RECONSTRUCTION HISTORIQUE (cache 24h)
# ============================================================

@st.cache_data(ttl=24 * 3600, show_spinner=False)
def reconstruct_historical_score(_all_data, all_data_keys, weights_map):
    """Reconstruit le score global mensuel depuis 1990. Cache 24h."""
    start = pd.Timestamp('1990-01-01')
    end = pd.Timestamp(datetime.now().strftime('%Y-%m-01'))
    dates = pd.date_range(start, end, freq='MS')
    
    history = []
    for d in dates:
        rows = []
        for famille, series_dict in SERIES_CATALOG.items():
            for sid, meta in series_dict.items():
                if sid not in _all_data:
                    continue
                z = historical_zscore(_all_data[sid], d, sid)
                if pd.notna(z):
                    direction = meta['direction']
                    sign = 1 if direction == 'up' else -1
                    weight = weights_map.get(sid, 1.0)
                    rows.append({
                        'famille': famille,
                        'signed_z': sign * z,
                        'weight': weight,
                    })
        if not rows:
            continue
        dft = pd.DataFrame(rows)
        # Score global
        gs = (dft['signed_z'] * dft['weight']).sum() / dft['weight'].sum()
        # Scores par famille
        fam_scores = dft.groupby('famille').apply(
            lambda g: (g['signed_z'] * g['weight']).sum() / g['weight'].sum()
        ).to_dict()
        history.append({
            'date': d,
            'global': gs,
            **{f'fam_{k}': v for k, v in fam_scores.items()},
        })
    
    return pd.DataFrame(history).set_index('date')
