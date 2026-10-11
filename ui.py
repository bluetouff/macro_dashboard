"""Composants visuels partagés par les applications Streamlit."""

from __future__ import annotations

from base64 import b64encode
from datetime import UTC, datetime
from html import escape
from pathlib import Path
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
        page_icon=(Path(__file__).parent / 'assets/favicon.svg').read_text(encoding='utf-8'),
        layout='wide',
        initial_sidebar_state='collapsed',
        menu_items=None,
    )


def inject_theme() -> None:
    """Injecte la charte l0g sans police, script ou tracker externe."""
    brand_font = b64encode(
        (Path(__file__).parent / 'assets' / 'fonts' / 'jetbrains-mono-latin-wght-normal.woff2').read_bytes()
    ).decode('ascii')
    st.markdown(
        f'''
<style>
@font-face {{
  font-family: "JetBrains Mono Variable";
  font-style: normal;
  font-weight: 100 800;
  font-display: swap;
  src: url("data:font/woff2;base64,{brand_font}") format("woff2");
}}
</style>
''' +
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
  --mono: "JetBrains Mono Variable", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
html { scroll-padding-top: 24px; }
html, body, [class*="css"] { font-family: var(--mono); }
.stApp {
  background: radial-gradient(ellipse at 50% 0, rgba(94,234,212,.035), transparent 600px), var(--ink);
  color: var(--paper);
  font-family: var(--mono);
  font-weight: 400;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
.stApp::before {
  content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, var(--signal), var(--accent), var(--amber));
  pointer-events: none;
}
.block-container { max-width: 1152px; padding: 28px 24px 56px; }
.stApp [data-testid="stMarkdownContainer"] { font-family: var(--mono) !important; }
header[data-testid="stHeader"], div[data-testid="stToolbar"], #MainMenu, footer:not(.site-footer) { display: none !important; }
[data-testid="stDecoration"] { display: none; }
.macro-header {
  display: flex; align-items: center; justify-content: space-between;
  gap: 24px;
  padding-bottom: 24px;
}
.brand-lockup { display: flex; align-items: center; gap: 20px; min-width: 0; }
.brand-logo {
  display: inline-flex;
  flex: none;
  align-items: baseline;
  color: var(--paper) !important;
  font-family: "JetBrains Mono Variable", ui-monospace, "SFMono-Regular", monospace;
  font-size: clamp(1.45rem, 3vw, 2rem);
  font-weight: 700;
  line-height: 1;
  letter-spacing: -.04em;
  text-decoration: none !important;
  white-space: nowrap;
}
.brand-logo .brand-0 { color: var(--signal); text-shadow: 0 0 18px rgba(94,234,212,.45); }
.brand-logo .brand-cursor {
  display: inline-block;
  margin-left: .12em;
  color: var(--accent);
  text-shadow: 0 0 18px rgba(255,77,135,.45);
  animation: brand-blink 1.05s steps(2, start) infinite;
}
@keyframes brand-blink { to { opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .brand-logo .brand-cursor { animation: none; } }
.brand-caption { font-size: 11px; line-height: 1.7; color: var(--muted); }
.brand-caption span { display: block; color: var(--signal); }
.home-link {
  display: inline-flex; align-items: center; justify-content: center; gap: 12px; min-height: 44px;
  padding: 9px 14px; border: 1px solid var(--line-strong); border-radius: 8px;
  color: var(--paper) !important; font-size: 12px; text-decoration: none !important;
}
.home-link span { color: var(--signal); }
.home-link:hover { border-color: var(--signal); color: var(--signal) !important; background: rgba(94,234,212,.04); }
.macro-nav {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px 24px;
  border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
  margin-bottom: 20px; font-size: 11px;
}
.product-name { color: var(--signal); font-size: 11px; font-weight: 600; padding: 12px 0; }
.nav-link {
  display: inline-flex; align-items: center; min-height: 44px;
  color: var(--muted) !important; font-size: 11px;
  text-decoration: none !important;
}
.nav-link:hover, .nav-link.active { color: var(--paper) !important; }
.nav-link.active { box-shadow: inset 0 -1px var(--signal); }
a:focus-visible, button:focus-visible, input:focus-visible { outline: 2px solid var(--signal); outline-offset: 4px; }
::selection { background: var(--signal); color: var(--ink); }
.hero { padding: 0 0 8px; }
.eyebrow {
  display: flex; align-items: baseline; gap: 8px;
  color: var(--signal); font-size: 10px; letter-spacing: .10em; text-transform: uppercase;
}
.eyebrow::before { content: "//"; }
.hero h1 {
  color: var(--bright); font-family: var(--mono); font-size: clamp(27px, 4vw, 40px);
  font-weight: 600; letter-spacing: -.05em; line-height: 1.25; margin: 10px 0 12px;
}
.hero h1 em { color: var(--signal); font-style: normal; font-weight: inherit; }
.hero-copy { max-width: 760px; color: var(--muted); font-size: 12px; line-height: 1.8; }
.proof-strip {
  display: flex; flex-wrap: wrap; gap: 6px 18px; align-items: center; margin-top: 18px;
  color: var(--muted); font-size: 10px; line-height: 1.7; overflow-wrap: anywhere;
}
.proof-item { display: inline-flex; gap: 7px; align-items: center; }
.proof-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--signal); box-shadow: 0 0 12px rgba(94,234,212,.55); }
.proof-strip a { color: var(--paper) !important; text-decoration: none; border-bottom: 1px solid var(--line-strong); }
.proof-strip a:hover { color: var(--signal) !important; }
.quality-banner {
  display: grid; grid-template-columns: auto 1fr auto; gap: 12px; align-items: center;
  margin: 0 0 8px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--surface);
  color: var(--muted); font-size: 10px; line-height: 1.7;
}
.quality-banner .line-icon { color: var(--signal); }
.quality-banner strong { color: var(--paper); font-weight: 600; }
.quality-status { color: var(--signal); letter-spacing: .08em; text-transform: uppercase; }
.quality-banner.stale { background: rgba(245,177,61,.04); border-color: rgba(245,177,61,.25); }
.quality-banner.stale .line-icon, .quality-banner.stale .quality-status { color: var(--amber); }
.stApp [data-testid="stMarkdownContainer"] .section-heading {
  display: flex; align-items: baseline; gap: 10px; margin: 0 0 16px;
  color: var(--paper); font-family: var(--mono); font-size: 12px;
  font-weight: 600; letter-spacing: .03em; text-transform: uppercase; line-height: 1.6;
}
.section-marker { color: var(--signal); flex-shrink: 0; }
.section-note { margin: 0 0 12px; color: var(--muted); font-size: 12px; line-height: 1.8; }
.st-key-trajectory_panel, .st-key-tensions_panel, .st-key-families_panel, .st-key-indicators_panel,
.st-key-method_panel, .st-key-faq_panel {
  min-width: 0; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 22px;
}
.st-key-summary_panels [data-testid="stColumn"] { min-width: 0; }
.st-key-summary_panels [data-testid="stHorizontalBlock"] { gap: 20px; }
.kpi-grid {
  display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 1px;
  border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: var(--line); margin-bottom: 8px;
}
.kpi-card { min-width: 0; padding: 20px 18px; background: var(--surface); }
.kpi-label { min-height: 34px; color: var(--muted); font-size: 10px; letter-spacing: .07em; line-height: 1.7; text-transform: uppercase; }
.kpi-value { min-height: 38px; margin: 10px 0 6px; color: var(--bright); font-size: 30px; font-weight: 600; line-height: 1.25; letter-spacing: -.04em; font-variant-numeric: tabular-nums; }
.kpi-card.primary .kpi-value { color: var(--signal); }
.kpi-detail { color: var(--muted); font-size: 10.5px; line-height: 1.7; }
.risk-tag { display: inline-flex; align-items: center; gap: 7px; color: var(--paper); font-size: 10px; text-transform: uppercase; letter-spacing: .06em; }
.risk-tag::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--muted); }
.risk-tag.critique::before { background: var(--danger); box-shadow: 0 0 13px rgba(255,107,114,.45); }
.risk-tag.vigilance::before { background: var(--amber); }
.risk-tag.modéré::before { background: var(--signal); }
.risk-tag.calme::before { background: #72d6a0; }
.family-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; }
.family-card { position: relative; overflow: hidden; min-height: 105px; border: 1px solid var(--line); border-radius: 8px; padding: 15px; background: var(--surface-2); }
.family-card::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 2px; background: var(--signal); transform: scaleX(var(--intensity)); transform-origin: left; opacity: .72; }
.family-name { color: var(--paper); font-size: 11px; font-weight: 600; padding-right: 64px; }
.family-meta { margin-top: 7px; color: var(--muted); font-size: 10px; }
.family-value { position: absolute; right: 15px; top: 14px; color: var(--bright); font-size: 18px; font-weight: 600; }
.insight-card, .method-card {
  border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px;
  background: var(--surface-2); color: var(--muted); font-size: 12px; line-height: 1.8;
}
.insight-card strong, .method-card strong { color: var(--paper); font-weight: 600; }
.tension-list { display: grid; }
.tension-row { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-top: 1px solid var(--line); }
.tension-row:first-child { border-top: 0; padding-top: 0; }
.tension-info { min-width: 0; }
.tension-series { color: var(--paper); font-size: 11px; }
.tension-rank { color: var(--muted); margin-right: 9px; }
.tension-name { color: var(--muted); font-size: 10px; line-height: 1.8; margin-top: 4px; overflow-wrap: anywhere; }
.tension-measure { flex-shrink: 0; text-align: right; font-variant-numeric: tabular-nums; }
.tension-measure strong { display: block; color: var(--paper); font-size: 18px; font-weight: 600; }
.tension-measure span { color: var(--muted); font-size: 10px; }
.method-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 10px; margin: 12px 0 20px; }
.method-step { border: 1px solid var(--line); border-radius: 8px; padding: 16px; background: var(--surface-2); }
.method-step .step-no { color: var(--signal); font-family: var(--mono); font-size: .63rem; letter-spacing: .12em; }
.method-step h3 { color: var(--bright); font-family: var(--mono); font-size: 13px; font-weight: 600; margin: 9px 0 7px; }
.method-step p { color: var(--muted); font-size: 12px; line-height: 1.8; margin: 0; }
.faq-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 10px; margin-top: 18px; }
.faq-card { border: 1px solid var(--line); border-radius: 8px; padding: 16px; background: var(--surface-2); color: var(--muted); font-size: 12px; line-height: 1.8; }
.faq-card strong { display: block; color: var(--bright); font-size: 12px; font-weight: 600; margin-bottom: 6px; }
.site-footer { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 20px; margin-top: 32px; padding: 24px 0 4px; border-top: 1px solid var(--line); color: var(--muted); font-size: 11px; line-height: 1.8; }
.site-footer .footer-logo { font-size: 24px; }
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
}
@media (max-width: 960px) {
  .brand-caption { display: none; }
  .family-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
  .st-key-summary_panels [data-testid="stHorizontalBlock"] { flex-direction: column; gap: 20px; }
  .st-key-summary_panels [data-testid="stColumn"] { width: 100% !important; flex: 1 1 auto !important; }
}
@media (max-width: 640px) {
  .kpi-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
  .quality-banner { grid-template-columns: auto 1fr; }
  .quality-status { grid-column: 2; }
  .method-grid, .faq-grid { grid-template-columns: 1fr; }
  .site-footer { grid-template-columns: 1fr; }
  .footer-links { text-align: left; }
  .footer-links a { margin: 0 13px 0 0; }
}
@media (max-width: 540px) {
  .block-container { padding: 22px 16px 40px; }
  .macro-header { flex-wrap: wrap; gap: 20px; padding-bottom: 20px; }
  .home-link { font-size: 11px; }
  .macro-nav { gap: 4px 18px; margin-bottom: 12px; }
  .product-name { width: 100%; padding-bottom: 0; }
  .kpi-card { padding: 16px 12px; }
  .kpi-label { font-size: 9px; }
  .kpi-value { font-size: 25px; }
  .kpi-detail { font-size: 10px; }
  .family-grid { grid-template-columns: 1fr; }
  .st-key-trajectory_panel, .st-key-tensions_panel, .st-key-families_panel, .st-key-indicators_panel,
  .st-key-method_panel, .st-key-faq_panel { padding: 18px 16px; }
}
@media (max-width: 360px) { .kpi-value { font-size: 21px; } }
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
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
    <a class="brand-logo" href="https://l0g.fr" target="_blank" rel="noopener noreferrer" aria-label="l0g.fr"><span>l</span><span class="brand-0">0</span><span>g</span><span class="brand-cursor" aria-hidden="true">_</span></a>
    <div class="brand-caption"><span>Lire les mécanismes</span>avant qu’ils deviennent l’événement</div>
  </div>
  <a class="home-link" href="https://l0g.fr" target="_blank" rel="noopener noreferrer">Retour à l0g.fr <span aria-hidden="true">↗</span></a>
</header>
<nav class="macro-nav" aria-label="Navigation principale">
  <span class="product-name">US Macro Risk Monitor</span>
  <a class="nav-link {radar_active}" href="?view=radar" target="_self"{' aria-current="page"' if radar_active else ''}>Radar</a>
  <a class="nav-link {faq_active}" href="?view=faq" target="_self"{' aria-current="page"' if faq_active else ''}>Méthode &amp; FAQ</a>
  <a class="nav-link" href="{METHOD_URL}" target="_blank" rel="noopener noreferrer">Documentation</a>
</nav>
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
  <h1><em>Stress</em> <span>macro US</span></h1>
  <div class="hero-copy">Un radar méthodologique fondé sur les séries FRED, orientées dans le sens du risque et agrégées sans masquer leur couverture ni leurs limites.</div>
  <div class="proof-strip">
    <span class="proof-item">47 séries · 8 familles</span>
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
        f'<h2 class="section-heading"><span class="section-marker" aria-hidden="true">//</span>{escape(title)}</h2>'
        f'<div class="section-note">{escape(note)}</div>',
        unsafe_allow_html=True,
    )


def render_footer(metadata: dict[str, Any]) -> None:
    revision = escape(str(metadata.get('calculator_revision', 'local'))[:12])
    st.markdown(
        f"""
<footer class="site-footer">
  <a class="brand-logo footer-logo" href="https://l0g.fr" target="_blank" rel="noopener noreferrer" aria-label="l0g.fr"><span>l</span><span class="brand-0">0</span><span>g</span><span class="brand-cursor" aria-hidden="true">_</span></a>
  <span>US Macro Risk Monitor · méthode {escape(str(metadata.get('methodology_version', METHODOLOGY_VERSION)))} · calculateur {revision}</span>
  <div class="footer-links"><a href="{FRED_URL}" target="_blank" rel="noopener noreferrer">FRED</a><a href="{METHOD_URL}" target="_blank" rel="noopener noreferrer">Méthodologie</a></div>
</footer>
""",
        unsafe_allow_html=True,
    )
