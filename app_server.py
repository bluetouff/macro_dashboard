"""Application publique snapshots-only servie par ``us.l0g.fr``.

Le processus Streamlit ne collecte aucune donnée et ne détient aucun secret. Il
affiche uniquement un bundle atomique dont le schéma, la couverture, les
empreintes et la révision du calculateur ont été vérifiés.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import streamlit as st

from dashboard_view import render_dashboard, render_method_faq
from snapshot_contract import SnapshotBundle, SnapshotValidationError, load_snapshot_bundle
from ui import configure_page, inject_theme, query_view, render_header

LOG = logging.getLogger('macro-dashboard')
SNAPSHOTS_DIR = Path(os.environ.get('SNAPSHOTS_DIR', '/var/lib/macro_dashboard/snapshots'))


@st.cache_data(ttl=300, show_spinner=False)
def load_validated_bundle(root: str) -> SnapshotBundle:
    return load_snapshot_bundle(Path(root))


configure_page()
inject_theme()

try:
    bundle = load_validated_bundle(str(SNAPSHOTS_DIR))
except (SnapshotValidationError, OSError, ValueError) as exc:
    LOG.error('Bundle de production refusé (%s)', type(exc).__name__)
    render_header(query_view())
    st.error(
        'Le snapshot public ne satisfait pas le contrat de qualité. '
        'Les scores sont masqués pour éviter d’afficher un calcul partiel ou incohérent.'
    )
    st.stop()

if query_view() == 'faq':
    render_method_faq(bundle.metadata)
else:
    render_dashboard(bundle.current, bundle.backtest, bundle.historical, bundle.metadata)
