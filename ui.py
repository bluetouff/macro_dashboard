"""Composants visuels partagés par les applications Streamlit."""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from typing import Any

import streamlit as st

from catalog import METHODOLOGY_VERSION

METHOD_URL = 'https://l0g.fr/methodologie/us-macro/'
FRED_URL = 'https://fred.stlouisfed.org/'

ICONS = {
    'activity': '<path d="M3 12h3l2.2-5.2 4 10.4L15 10h6"/>',
    'archive': '<path d="M4 7h16v13H4z"/><path d="M3 3h18v4H3zM9 11h6"/>',
    'book': '<path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H11v18H7.5A3.5 3.5 0 0 0 4 23.5z"/><path d="M20 5.5A3.5 3.5 0 0 0 16.5 2H13v18h3.5a3.5 3.5 0 0 1 3.5 3.5z"/>',
    'grid': '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
    'layers': '<path d="m12 2 9 5-9 5-9-5z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/>',
    'pulse': '<path d="M4 13h3l2-7 4 12 2-7 2 2h3"/><circle cx="12" cy="12" r="10"/>',
    'shield': '<path d="M12 3 20 6v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6z"/><path d="m8.5 12 2.2 2.2 4.8-5"/>',
    'table': '<path d="M3 5h18v14H3zM3 10h18M9 5v14"/>',
    'trend': '<path d="m3 17 6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
}


def icon(name: str, *, size: int = 20) -> str:
    """Retourne une icône SVG locale, sans ressource tierce."""
    paths = ICONS.get(name, ICONS['activity'])
    return (
        f'<svg class="line-icon" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="1.45" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{paths}</svg>'
    )


def configure_page() -> None:
    st.set_page_config(
        page_title='US Macro Risk Monitor · l0g',
        layout='wide',
        initial_sidebar_state='collapsed',
        menu_items=None,
    )


def inject_theme() -> None:
    """Injecte la charte l0g sans police, script ou tracker externe."""
    st.markdown(
        """
<style>
:root {
  color-scheme: dark;
  --ink: #0c0d10;
  --surface: #121419;
  --surface-2: #171a20;
  --surface-soft: rgba(255,255,255,.018);
  --line: rgba(255,255,255,.10);
  --line-strong: rgba(255,255,255,.20);
  --paper: #e7e9ee;
  --bright: #f5f6f8;
  --muted: #8b909b;
  --signal: #5eead4;
  --accent: #ff4d87;
  --amber: #f5b13d;
  --danger: #ff6b72;
  --sans: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
html, body, [class*="css"] { font-family: var(--sans); }
.stApp {
  background:
    radial-gradient(circle at 18% -10%, rgba(94,234,212,.055), transparent 34rem),
    radial-gradient(circle at 92% 4%, rgba(255,77,135,.04), transparent 30rem),
    var(--ink);
  color: var(--paper);
  font-family: var(--sans);
  font-weight: 420;
  -webkit-font-smoothing: antialiased;
}
.block-container { max-width: 1320px; padding: 1.15rem 2.2rem 3.5rem; }
header[data-testid="stHeader"], div[data-testid="stToolbar"], #MainMenu, footer { display: none !important; }
[data-testid="stDecoration"] { display: none; }
.macro-header {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 24px;
  min-height: 86px;
  padding: 12px 0 17px;
  border-bottom: 1px solid var(--line);
}
.brand-lockup { display: flex; align-items: center; gap: 15px; min-width: 0; }
.brand-logo {
  color: var(--bright) !important;
  font-family: var(--mono);
  font-size: clamp(1.85rem, 3vw, 2.5rem);
  font-weight: 570;
  line-height: 1;
  letter-spacing: -.08em;
  text-decoration: none !important;
  white-space: nowrap;
}
.brand-logo .cursor { color: var(--signal); }
.brand-rule { width: 1px; height: 36px; background: var(--line-strong); }
.product-name { color: var(--paper); font-size: .78rem; font-weight: 520; letter-spacing: .13em; text-transform: uppercase; }
.product-scope { color: var(--muted); font-family: var(--mono); font-size: .64rem; margin-top: 4px; }
.signal-mark { color: var(--signal); width: 106px; opacity: .86; }
.signal-mark svg { width: 100%; height: 32px; display: block; }
.macro-nav { display: flex; align-items: center; justify-content: flex-end; gap: 7px; }
.nav-link {
  color: var(--muted) !important;
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 7px 11px;
  font-family: var(--mono);
  font-size: .65rem;
  text-decoration: none !important;
  transition: border-color .15s ease, color .15s ease, background .15s ease;
}
.nav-link:hover, .nav-link.active { color: var(--bright) !important; border-color: var(--line-strong); background: rgba(255,255,255,.025); }
.hero { padding: 48px 0 24px; max-width: 900px; }
.eyebrow {
  display: flex; align-items: center; gap: 9px;
  color: var(--signal); font-family: var(--mono); font-size: .66rem; letter-spacing: .14em; text-transform: uppercase;
}
.eyebrow::before { content: ""; width: 22px; height: 1px; background: currentColor; }
.hero h1 {
  color: var(--bright); font-family: var(--sans); font-size: clamp(2.15rem, 5vw, 4.4rem);
  font-weight: 430; letter-spacing: -.052em; line-height: .98; margin: 14px 0 18px;
}
.hero h1 em { color: var(--signal); font-style: normal; font-weight: 430; }
.hero-copy { max-width: 760px; color: var(--muted); font-size: clamp(.92rem, 1.5vw, 1.08rem); line-height: 1.65; }
.proof-strip {
  display: flex; flex-wrap: wrap; gap: 7px 18px; align-items: center; margin-top: 22px;
  color: var(--muted); font-family: var(--mono); font-size: .64rem;
}
.proof-item { display: inline-flex; gap: 7px; align-items: center; }
.proof-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--signal); box-shadow: 0 0 12px rgba(94,234,212,.55); }
.proof-strip a { color: var(--paper) !important; text-decoration: none; border-bottom: 1px solid var(--line-strong); }
.proof-strip a:hover { color: var(--signal) !important; }
.quality-banner {
  display: grid; grid-template-columns: auto 1fr auto; gap: 12px; align-items: center;
  margin: 6px 0 26px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 11px;
  background: linear-gradient(90deg, rgba(94,234,212,.045), rgba(255,255,255,.008));
  color: var(--muted); font-family: var(--mono); font-size: .67rem;
}
.quality-banner .line-icon { color: var(--signal); }
.quality-banner strong { color: var(--paper); font-weight: 520; }
.quality-status { color: var(--signal); letter-spacing: .08em; text-transform: uppercase; }
.quality-banner.stale { background: rgba(245,177,61,.04); border-color: rgba(245,177,61,.25); }
.quality-banner.stale .line-icon, .quality-banner.stale .quality-status { color: var(--amber); }
.section-heading {
  display: flex; align-items: center; gap: 11px; margin: 44px 0 8px;
  color: var(--bright); font-family: var(--sans); font-size: clamp(1.15rem, 2vw, 1.48rem); font-weight: 470; letter-spacing: -.022em;
}
.section-heading .icon-shell {
  display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px;
  border: 1px solid var(--line); border-radius: 9px; color: var(--signal); background: var(--surface);
}
.section-note { margin: 0 0 18px 46px; color: var(--muted); font-size: .76rem; line-height: 1.55; }
.kpi-grid {
  display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 1px;
  border: 1px solid var(--line); border-radius: 13px; overflow: hidden; background: var(--line);
  box-shadow: 0 26px 80px rgba(0,0,0,.16);
}
.kpi-card { min-width: 0; min-height: 132px; padding: 18px 17px 16px; background: linear-gradient(145deg, var(--surface), rgba(18,20,25,.92)); }
.kpi-card.primary { background: linear-gradient(145deg, rgba(94,234,212,.09), var(--surface)); }
.kpi-label { color: var(--muted); font-family: var(--mono); font-size: .61rem; letter-spacing: .1em; line-height: 1.35; text-transform: uppercase; }
.kpi-value { margin: 13px 0 7px; color: var(--bright); font-family: var(--mono); font-size: clamp(1.45rem, 2.4vw, 2rem); font-weight: 490; letter-spacing: -.045em; font-variant-numeric: tabular-nums; }
.kpi-card.primary .kpi-value { color: var(--signal); }
.kpi-detail { color: var(--muted); font-size: .69rem; line-height: 1.4; }
.risk-tag { display: inline-flex; align-items: center; gap: 7px; color: var(--paper); font-family: var(--mono); font-size: .66rem; text-transform: uppercase; letter-spacing: .08em; }
.risk-tag::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--muted); }
.risk-tag.critique::before { background: var(--danger); box-shadow: 0 0 13px rgba(255,107,114,.45); }
.risk-tag.vigilance::before { background: var(--amber); }
.risk-tag.modéré::before { background: var(--signal); }
.risk-tag.calme::before { background: #72d6a0; }
.family-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; }
.family-card { position: relative; overflow: hidden; min-height: 105px; border: 1px solid var(--line); border-radius: 11px; padding: 15px 15px 13px; background: var(--surface-soft); }
.family-card::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 2px; background: var(--signal); transform: scaleX(var(--intensity)); transform-origin: left; opacity: .72; }
.family-name { color: var(--paper); font-size: .78rem; font-weight: 470; }
.family-meta { margin-top: 7px; color: var(--muted); font-family: var(--mono); font-size: .62rem; }
.family-value { position: absolute; right: 15px; top: 14px; color: var(--bright); font-family: var(--mono); font-size: 1.18rem; font-weight: 470; }
.insight-card, .method-card {
  border: 1px solid var(--line); border-radius: 12px; padding: 17px 18px;
  background: var(--surface-soft); color: var(--muted); font-size: .8rem; line-height: 1.62;
}
.insight-card strong, .method-card strong { color: var(--paper); font-weight: 520; }
.method-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 10px; margin: 12px 0 20px; }
.method-step { border: 1px solid var(--line); border-radius: 11px; padding: 16px; background: var(--surface-soft); }
.method-step .step-no { color: var(--signal); font-family: var(--mono); font-size: .63rem; letter-spacing: .12em; }
.method-step h3 { color: var(--bright); font-size: .92rem; font-weight: 480; margin: 9px 0 7px; }
.method-step p { color: var(--muted); font-size: .75rem; line-height: 1.55; margin: 0; }
.faq-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 10px; margin-top: 18px; }
.faq-card { border: 1px solid var(--line); border-radius: 11px; padding: 17px 18px; background: var(--surface-soft); color: var(--muted); font-size: .79rem; line-height: 1.58; }
.faq-card strong { display: block; color: var(--bright); font-size: .85rem; font-weight: 500; margin-bottom: 6px; }
.site-footer { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 20px; margin-top: 54px; padding: 24px 0 4px; border-top: 1px solid var(--line); color: var(--muted); font-family: var(--mono); font-size: .61rem; }
.site-footer .footer-logo { color: var(--bright) !important; font-size: 1.12rem; font-weight: 560; text-decoration: none !important; letter-spacing: -.07em; }
.site-footer .footer-logo span { color: var(--signal); }
.footer-links { text-align: right; }
.footer-links a { color: var(--muted) !important; text-decoration: none; margin-left: 13px; }
.footer-links a:hover { color: var(--signal) !important; }
div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 11px; overflow: hidden; }
div[data-testid="stDataFrame"] * { font-family: var(--mono) !important; font-size: .72rem !important; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }
.stTabs [data-baseweb="tab"] { height: 34px; border: 1px solid transparent; border-radius: 999px; color: var(--muted); font-family: var(--mono); font-size: .65rem; padding: 0 11px; }
.stTabs [aria-selected="true"] { color: var(--bright) !important; border-color: var(--line-strong) !important; background: rgba(255,255,255,.025) !important; }
details { border-color: var(--line) !important; }
div[data-testid="stAlert"] { border-radius: 11px; border-color: var(--line); background: var(--surface); }
a { color: var(--signal); }
@media (max-width: 1100px) {
  .kpi-grid { grid-template-columns: repeat(3,minmax(0,1fr)); }
  .family-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
}
@media (max-width: 760px) {
  .block-container { padding: .55rem 1rem 2.5rem; }
  .macro-header { grid-template-columns: 1fr auto; gap: 10px; }
  .signal-mark { display: none; }
  .macro-nav { grid-column: 1 / -1; justify-content: flex-start; border-top: 1px solid var(--line); padding-top: 9px; }
  .brand-rule { height: 30px; }
  .product-name { font-size: .67rem; }
  .product-scope { display: none; }
  .hero { padding: 34px 0 20px; }
  .hero h1 { font-size: clamp(2.15rem, 12vw, 3.25rem); }
  .quality-banner { grid-template-columns: auto 1fr; }
  .quality-status { grid-column: 2; }
  .kpi-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
  .kpi-card { min-height: 116px; }
  .family-grid, .method-grid, .faq-grid { grid-template-columns: 1fr; }
  .section-note { margin-left: 0; }
  .site-footer { grid-template-columns: 1fr; }
  .footer-links { text-align: left; }
  .footer-links a { margin: 0 13px 0 0; }
}
@media (max-width: 410px) {
  .brand-logo { font-size: 1.85rem; }
  .brand-lockup { gap: 10px; }
  .kpi-grid { grid-template-columns: 1fr; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def query_view() -> str:
    """N'accepte que les deux vues publiques documentées."""
    raw: Any = st.query_params.get('view', 'radar')
    value = raw[0] if isinstance(raw, list) and raw else raw
    return 'faq' if str(value).lower() == 'faq' else 'radar'


def render_header(view: str) -> None:
    radar_active = 'active' if view == 'radar' else ''
    faq_active = 'active' if view == 'faq' else ''
    st.markdown(
        f"""
<header class="macro-header">
  <div class="brand-lockup">
    <a class="brand-logo" href="https://l0g.fr" target="_blank" rel="noopener noreferrer" aria-label="l0g.fr">l0g<span class="cursor">_</span></a>
    <span class="brand-rule" aria-hidden="true"></span>
    <div><div class="product-name">US Macro Risk Monitor</div><div class="product-scope">47 séries · 8 familles · source FRED</div></div>
  </div>
  <div class="signal-mark" aria-hidden="true">
    <svg viewBox="0 0 116 32" fill="none"><path d="M1 17h19l7-11 9 21 9-17 9 12 9-8 8 3h44" stroke="currentColor" stroke-width="1.35"/><circle cx="115" cy="17" r="2.5" fill="currentColor"/></svg>
  </div>
  <nav class="macro-nav" aria-label="Navigation principale">
    <a class="nav-link {radar_active}" href="?view=radar">Radar</a>
    <a class="nav-link {faq_active}" href="?view=faq">Méthode &amp; FAQ</a>
    <a class="nav-link" href="{METHOD_URL}" target="_blank" rel="noopener noreferrer">Documentation</a>
  </nav>
</header>
""",
        unsafe_allow_html=True,
    )


def render_hero(metadata: dict[str, Any]) -> None:
    generated = parse_generated_at(metadata)
    generated_label = generated.astimezone().strftime('%d/%m/%Y · %H:%M') if generated else 'non daté'
    revision = escape(str(metadata.get('calculator_revision', 'local'))[:12])
    coverage = f"{metadata.get('n_series_loaded', '?')}/{metadata.get('n_series_expected', '?')}"
    st.markdown(
        f"""
<section class="hero">
  <div class="eyebrow">Macro risk intelligence · États-Unis</div>
  <h1>Lire le stress macro.<br><em>Mesurer, pas prédire.</em></h1>
  <div class="hero-copy">Un radar méthodologique fondé sur les séries FRED, orientées dans le sens du risque et agrégées sans masquer leur couverture ni leurs limites.</div>
  <div class="proof-strip">
    <span class="proof-item"><span class="proof-dot"></span> données {escape(str(metadata.get('source', 'FRED')))}</span>
    <span class="proof-item">snapshot {escape(generated_label)}</span>
    <span class="proof-item">couverture {escape(coverage)}</span>
    <span class="proof-item">méthode v{escape(str(metadata.get('methodology_version', METHODOLOGY_VERSION)))}</span>
    <span class="proof-item">calculateur <code>{revision}</code></span>
  </div>
</section>
""",
        unsafe_allow_html=True,
    )


def parse_generated_at(metadata: dict[str, Any]) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(metadata.get('generated_at', '')).replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def render_quality_banner(metadata: dict[str, Any], *, stale_after_hours: int = 30) -> bool:
    generated = parse_generated_at(metadata)
    age_hours = (datetime.now(UTC) - generated.astimezone(UTC)).total_seconds() / 3600 if generated else float('inf')
    stale = age_hours > stale_after_hours
    state = 'stale' if stale else ''
    status = 'À ACTUALISER' if stale else 'CONTRAT NOMINAL'
    age = 'inconnue' if generated is None else f'{max(age_hours, 0):.1f} h'
    local_mode = metadata.get('delivery_mode') == 'local-live'
    text = (
        'Session locale : le catalogue FRED complet a été collecté avant calcul.'
        if local_mode
        else (
            'Le dernier bundle dépasse la fenêtre de fraîcheur. Les scores restent affichés avec cet avertissement.'
            if stale
            else 'Schéma, couverture, empreintes de fichiers et révision du calculateur ont été vérifiés avant affichage.'
        )
    )
    if local_mode:
        status = 'SESSION LOCALE'
    st.markdown(
        f"""
<div class="quality-banner {state}">
  {icon('shield', size=19)}
  <div><strong>Qualité des données.</strong> {escape(text)} Âge du snapshot : {escape(age)}.</div>
  <div class="quality-status">{status}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    return stale


def section_heading(title: str, note: str, icon_name: str) -> None:
    st.markdown(
        f'<div class="section-heading"><span class="icon-shell">{icon(icon_name)}</span>{escape(title)}</div>'
        f'<div class="section-note">{escape(note)}</div>',
        unsafe_allow_html=True,
    )


def render_footer(metadata: dict[str, Any]) -> None:
    revision = escape(str(metadata.get('calculator_revision', 'local'))[:12])
    st.markdown(
        f"""
<footer class="site-footer">
  <a class="footer-logo" href="https://l0g.fr" target="_blank" rel="noopener noreferrer">l0g<span>_</span></a>
  <span>US Macro Risk Monitor · méthode {escape(str(metadata.get('methodology_version', METHODOLOGY_VERSION)))} · calculateur {revision}</span>
  <div class="footer-links"><a href="{FRED_URL}" target="_blank" rel="noopener noreferrer">FRED</a><a href="{METHOD_URL}" target="_blank" rel="noopener noreferrer">Méthodologie</a></div>
</footer>
""",
        unsafe_allow_html=True,
    )
