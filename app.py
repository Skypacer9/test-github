"""Gradio RPG tactical watch -- Field + Character Profile. Layout only; math in engine."""

from __future__ import annotations

import html as html_lib

import gradio as gr

from backend import (
    advance_quarter,
    arm_short_demo,
    attempt_alliance,
    bootstrap_dialogue,
    character_choices,
    character_profile,
    fresh_run,
    initial_state,
    intervene_targets,
    latest_dialogue,
    merge_chat,
)
from engine.demo_flow import OPENING_CARD
from engine.figures import DEFAULT_FIGURE_ID, normalize_figure_id
from engine.geo import rollup_m4

THEME_CSS = """
/* ===== READABILITY LAW =====
   Near-black ink (#1a1208) on parchment (#F4E8D0 / #FFF8E7).
   NO gray-on-dark. NO cream-on-cream. Dropdown banned.
*/
:root {
  --ws-ink: #1a1208 !important;
  --ws-ink-soft: #2b2118 !important;
  --ws-cream: #FFF8E7 !important;
  --ws-parchment: #F4E8D0 !important;
  --ws-gold: #C9A227 !important;
  --ws-bronze: #8B5E2F !important;
  --body-text-color: #1a1208 !important;
  --block-title-text-color: #1a1208 !important;
  --block-label-text-color: #1a1208 !important;
  --block-info-text-color: #2b2118 !important;
  --input-text-color: #1a1208 !important;
  --input-background-fill: #FFF8E7 !important;
  --button-primary-text-color: #FFF8E7 !important;
  --button-secondary-text-color: #FFF8E7 !important;
  --checkbox-label-text-color: #1a1208 !important;
  --neutral-50: #FFF8E7 !important;
  --neutral-100: #F4E8D0 !important;
  --neutral-200: #E8D7B8 !important;
  --neutral-300: #C9A227 !important;
  --neutral-400: #8B5E2F !important;
  --neutral-500: #5A4228 !important;
  --neutral-600: #2b2118 !important;
  --neutral-700: #1a1208 !important;
  --neutral-800: #120E0A !important;
  --neutral-900: #0A0908 !important;
  --neutral-950: #050403 !important;
}

html, body, .gradio-container, .gradio-container .main, .gradio-container .wrap {
  background: #E8D7B8 !important;
  color: #1a1208 !important;
  font-family: "Palatino Linotype", "Book Antiqua", Georgia, serif !important;
  opacity: 1 !important;
}

/* Nuclear ink on parchment chrome only — NOT buttons / dark portraits */
.gradio-container, .gradio-container * {
  opacity: 1 !important;
}
.gradio-container label,
.gradio-container .block > .label-wrap,
.gradio-container .block > .label-wrap span,
.gradio-container .block > .label-wrap p,
.gradio-container [data-testid="block-info"],
.gradio-container [data-testid="block-title"],
.gradio-container .info,
.gradio-container .secondary-text,
.gradio-container legend,
.gradio-container .prose,
.gradio-container .prose p,
.gradio-container .prose li,
.gradio-container .markdown,
.gradio-container .markdown p,
.gradio-container h1, .gradio-container h2, .gradio-container h3,
.gradio-container .block {
  color: #1a1208 !important;
  fill: #1a1208 !important;
  opacity: 1 !important;
  -webkit-text-fill-color: #1a1208 !important;
}
/* Intentionally NO `.block *` — that beat button/portrait cream rules */

#ws-title {
  background: #F4E8D0 !important;
  border: 2px solid #8B5E2F !important;
  padding: .65rem 1rem !important;
  margin-bottom: .75rem !important;
}
#ws-title h1, #ws-title .prose h1, #ws-title * h1 {
  color: #1a1208 !important;
  -webkit-text-fill-color: #1a1208 !important;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 1.45rem !important;
  font-weight: 900 !important;
}
#ws-title p, #ws-title .prose p {
  color: #2b2118 !important;
  -webkit-text-fill-color: #2b2118 !important;
  font-weight: 700 !important;
}

/* Tabs — ink on parchment */
.gradio-container .tab-nav,
.gradio-container [role="tablist"] {
  background: #F4E8D0 !important;
  border-bottom: 2px solid #8B5E2F !important;
}
.gradio-container .tab-nav *,
.gradio-container [role="tablist"] *,
.gradio-container [role="tab"],
.gradio-container [role="tab"] * {
  color: #1a1208 !important;
  -webkit-text-fill-color: #1a1208 !important;
  font-weight: 800 !important;
  opacity: 1 !important;
  background: transparent !important;
}
.gradio-container [role="tab"][aria-selected="true"],
.gradio-container [role="tab"][aria-selected="true"] * {
  color: #8B1E1E !important;
  -webkit-text-fill-color: #8B1E1E !important;
  border-bottom: 3px solid #8B1E1E !important;
}

/* ===== BAN true <select> / Dropdown only — do NOT touch Radio chrome ===== */
.gradio-container select,
.gradio-container [data-testid="dropdown"] select,
#ws-figure-picker select {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
  max-height: 0 !important;
  overflow: hidden !important;
  pointer-events: none !important;
}

/* Radio + CheckboxGroup — parchment rows, near-black ink */
.gradio-container fieldset,
.gradio-container [data-testid="checkbox-group"],
.gradio-container [data-testid="radio"],
.gradio-container [role="radiogroup"],
.gradio-container [role="group"] {
  background: #FFF8E7 !important;
  border: 2px solid #8B5E2F !important;
  padding: .45rem !important;
}
#ws-figure-picker,
#ws-figure-picker > .wrap,
#ws-figure-picker [role="radiogroup"],
#ws-figure-picker .wrap {
  display: flex !important;
  flex-direction: column !important;
  gap: .45rem !important;
  background: #FFF8E7 !important;
  border: 3px solid #8B1E1E !important;
  padding: .55rem !important;
  min-height: 16rem !important;
}
#ws-figure-picker label,
#ws-figure-picker label *,
#ws-figure-picker span,
#ws-figure-picker p,
.gradio-container [role="radiogroup"] label,
.gradio-container [role="radiogroup"] label *,
.gradio-container [role="group"] label,
.gradio-container [role="group"] label *,
.gradio-container input[type="radio"] + span,
.gradio-container input[type="checkbox"] + span {
  color: #1a1208 !important;
  -webkit-text-fill-color: #1a1208 !important;
  font-weight: 800 !important;
  opacity: 1 !important;
  font-size: 1rem !important;
}
#ws-figure-picker label,
.gradio-container [role="radiogroup"] label,
#ws-intervene-pick label {
  display: flex !important;
  align-items: center !important;
  gap: .55rem !important;
  padding: .55rem .75rem !important;
  background: #F4E8D0 !important;
  border: 2px solid #8B5E2F !important;
  border-radius: 2px !important;
  margin: 0 !important;
  width: 100% !important;
  box-sizing: border-box !important;
  cursor: pointer !important;
}
#ws-figure-picker label:has(input:checked),
.gradio-container [role="radiogroup"] label:has(input:checked) {
  background: #FFE08A !important;
  border-color: #8B1E1E !important;
}
#ws-figure-picker input[type="radio"],
.gradio-container input[type="radio"],
.gradio-container input[type="checkbox"] {
  display: inline-block !important;
  visibility: visible !important;
  width: 1.1rem !important;
  height: 1.1rem !important;
  accent-color: #8B1E1E !important;
  flex-shrink: 0 !important;
}

/* Text inputs — parchment + ink (never a figure picker) */
.gradio-container input:not([type="radio"]):not([type="checkbox"]),
.gradio-container textarea,
.gradio-container ul.options,
.gradio-container ul.options li {
  background: #FFF8E7 !important;
  color: #1a1208 !important;
  -webkit-text-fill-color: #1a1208 !important;
  border: 2px solid #8B5E2F !important;
  font-weight: 700 !important;
  opacity: 1 !important;
}

/* Buttons — cream on dark bronze (specificity ABOVE any ink chrome rules) */
.gradio-container button,
.gradio-container button *,
.gradio-container .block button,
.gradio-container .block button *,
.gradio-container .btn,
.gradio-container .block .btn,
#ws-actions button,
#ws-actions button *,
#ws-new-run,
#ws-new-run button,
#ws-new-run * {
  background: linear-gradient(180deg, #5A4228 0%, #2A1C10 100%) !important;
  border: 2px solid #C9A227 !important;
  color: #FFF8E7 !important;
  -webkit-text-fill-color: #FFF8E7 !important;
  fill: #FFF8E7 !important;
  font-weight: 800 !important;
  letter-spacing: 0.05em !important;
  text-transform: uppercase !important;
  border-radius: 2px !important;
  min-height: 2.6rem !important;
  opacity: 1 !important;
  pointer-events: auto !important;
  cursor: pointer !important;
  box-shadow: inset 0 1px 0 rgba(255,224,138,0.35), 0 3px 0 #0A0908 !important;
}
.gradio-container button:hover,
.gradio-container button:hover *,
.gradio-container .block button:hover,
.gradio-container .block button:hover * {
  border-color: #FFE08A !important;
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
}

/* New Run — crimson, still cream text, clickable */
#ws-new-run, #ws-new-run button, button#ws-new-run, #ws-new-run * {
  width: 100% !important;
  min-height: 3.2rem !important;
  font-size: 1.15rem !important;
  font-weight: 800 !important;
  background: #8B1E1E !important;
  color: #FFF8E7 !important;
  -webkit-text-fill-color: #FFF8E7 !important;
  border: 2px solid #C9A227 !important;
  pointer-events: auto !important;
  cursor: pointer !important;
}

/* Dark portrait / nameplate / speaker — cream stays cream (above ink) */
.gradio-container .block .ws-glyph,
.gradio-container .html-container .ws-glyph,
.ws-glyph {
  color: #FFF8E7 !important;
  -webkit-text-fill-color: #FFF8E7 !important;
}
.gradio-container .block .ws-ph,
.gradio-container .html-container .ws-ph,
.ws-ph {
  color: #E8D7B8 !important;
  -webkit-text-fill-color: #E8D7B8 !important;
}
.gradio-container .block .ws-nameplate strong,
.gradio-container .html-container .ws-nameplate strong,
.ws-nameplate strong {
  color: #FFF8E7 !important;
  -webkit-text-fill-color: #FFF8E7 !important;
}
.gradio-container .block .ws-nameplate em,
.gradio-container .html-container .ws-nameplate em,
.ws-nameplate em {
  color: #FFE08A !important;
  -webkit-text-fill-color: #FFE08A !important;
}
.gradio-container .block .ws-speaker,
.gradio-container .html-container .ws-speaker,
.ws-speaker {
  color: #FFF8E7 !important;
  -webkit-text-fill-color: #FFF8E7 !important;
}

/* Radio / Checkbox — always clickable (never inherit dropdown bans) */
#ws-figure-picker,
#ws-figure-picker *,
#ws-intervene-pick,
#ws-intervene-pick *,
.gradio-container [role="radiogroup"],
.gradio-container [role="radiogroup"] *,
.gradio-container input[type="radio"],
.gradio-container input[type="checkbox"] {
  pointer-events: auto !important;
  visibility: visible !important;
  opacity: 1 !important;
}

/* Chatbot — parchment + near-black ink */
#ws-chatbot,
.gradio-container .chatbot,
.gradio-container [data-testid="chatbot"],
.gradio-container .bubble-wrap {
  background: #FFF8E7 !important;
  border: 2px solid #8B5E2F !important;
  color: #1a1208 !important;
}
#ws-chatbot *,
.gradio-container .chatbot *,
.gradio-container [data-testid="chatbot"] *,
.gradio-container .message,
.gradio-container .message *,
.gradio-container .bubble-wrap *,
.gradio-container .message-content,
.gradio-container .message-content *,
.gradio-container .bot, .gradio-container .bot *,
.gradio-container .user, .gradio-container .user *,
.gradio-container [class*="message"] *,
.gradio-container [class*="bubble"] * {
  color: #1a1208 !important;
  -webkit-text-fill-color: #1a1208 !important;
  opacity: 1 !important;
}
.gradio-container .bot,
.gradio-container .message.bot,
.gradio-container [class*="bot"] {
  background: #FFF8E7 !important;
  border: 1px solid #8B5E2F !important;
}
.gradio-container .user,
.gradio-container .message.user {
  background: #E8D7B8 !important;
}
#ws-chatbot strong, .gradio-container .chatbot strong {
  color: #0A0908 !important;
  -webkit-text-fill-color: #0A0908 !important;
  font-weight: 900 !important;
}
#ws-chatbot > label,
#ws-chatbot .label-wrap,
#ws-chatbot .label-wrap * {
  color: #1a1208 !important;
  -webkit-text-fill-color: #1a1208 !important;
  background: transparent !important;
}

#ws-canvas, #ws-profile,
.gradio-container .html-container {
  background: transparent !important;
}

/* Profile scroll + collapse — parchment frame, ink text */
#ws-profile-scroll {
  max-height: 72vh !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  padding: .45rem !important;
  border: 2px solid #8B5E2F !important;
  background: #F4E8D0 !important;
}
#ws-profile,
#ws-profile .ws-root {
  max-height: none !important;
}
#ws-cast-accordion,
#ws-dossier-accordion,
#ws-radio-panel {
  margin-bottom: .65rem !important;
  background: #FFF8E7 !important;
  border: 2px solid #8B5E2F !important;
  padding: .35rem .5rem !important;
}
#ws-cast-accordion summary,
#ws-dossier-accordion summary,
#ws-cast-accordion .label-wrap,
#ws-dossier-accordion .label-wrap,
#ws-cast-accordion .label-wrap *,
#ws-dossier-accordion .label-wrap *,
.gradio-container .accordion,
.gradio-container .accordion .label-wrap,
.gradio-container .accordion .label-wrap * {
  color: #1a1208 !important;
  -webkit-text-fill-color: #1a1208 !important;
  opacity: 1 !important;
  font-weight: 800 !important;
}
#ws-cast-list-panel {
  max-height: 10rem !important;
  overflow-y: auto !important;
}
"""

FACCTION = {
    "qin": {"glyph": "\u79e6", "color": "var(--ws-qin)", "label": "Qin"},
    "chu": {"glyph": "\u695a", "color": "var(--ws-chu)", "label": "Chu"},
    "qi": {"glyph": "\u9f4a", "color": "var(--ws-qi)", "label": "Qi"},
    "zhao": {"glyph": "\u8d99", "color": "#8AA0B8", "label": "Zhao"},
    "han": {"glyph": "\u97d3", "color": "#A09080", "label": "Han"},
    "wei": {"glyph": "\u9b4f", "color": "#90A090", "label": "Wei"},
    "yan": {"glyph": "\u71d5", "color": "#8090A8", "label": "Yan"},
}


def _esc(s: object) -> str:
    return html_lib.escape(str(s))


def _bar(label: str, value: float, color: str, *, vmax: float = 1.0) -> str:
    v = max(0.0, min(float(vmax), float(value)))
    pct = 100.0 * v / vmax if vmax else 0.0
    shown = f"{v:.0f}" if vmax == 100 else f"{v:.2f}"
    return (
        '<div class="ws-meter">'
        f'<div class="ws-meter-label"><span>{_esc(label)}</span><span>{shown}</span></div>'
        f'<div class="ws-meter-track"><div class="ws-meter-fill" style="width:{pct:.1f}%;background:{color};"></div></div>'
        "</div>"
    )


def _portrait_block(aid: str, agent: dict, large: bool = False) -> str:
    home = agent.get("home_court") or aid
    meta = FACCTION.get(
        home, {"glyph": aid[:1].upper(), "color": "var(--ws-gold)", "label": aid}
    )
    intent = agent.get("intention_label") or agent.get("intention", "?")
    size = "160px" if large else "120px"
    return (
        f'<div class="ws-char" data-asset="assets/portraits/{_esc(home)}.png">'
        f'<div class="ws-portrait" style="width:{size};height:{size};border-color:{meta["color"]};">'
        f'<span class="ws-glyph">{meta["glyph"]}</span>'
        '<span class="ws-ph">CC placeholder</span></div>'
        f'<div class="ws-nameplate" style="border-color:{meta["color"]};">'
        f'<strong>{_esc(agent.get("name", meta["label"]))}</strong>'
        f"<em>{_esc(intent)}</em></div></div>"
    )


def _shared_style() -> str:
    return """
<style>
  /* Parchment panels + near-black ink — high contrast FE/Apothecary */
  .ws-root {
    color: #1a1208 !important;
    font-family: "Palatino Linotype", "Book Antiqua", "Segoe UI", serif;
    background: #F4E8D0;
    border: 2px solid #8B5E2F;
    padding: .85rem 1rem 1rem 1rem;
    border-radius: 2px;
  }
  .ws-root, .ws-root * { opacity: 1 !important; }
  .ws-top {
    display:flex; justify-content:space-between; align-items:baseline;
    border-bottom:2px solid #2b2118; padding-bottom:.4rem; margin-bottom:.75rem;
  }
  .ws-top h2 { margin:0; color:#1a1208 !important; letter-spacing:.08em; font-size:1.2rem; font-weight:800; }
  .ws-top .era { color:#2b2118 !important; font-size:.85rem; font-weight:700; }
  .ws-pathway {
    margin-bottom:.5rem; color:#2b2118 !important; font-size:.78rem;
    letter-spacing:.06em; text-transform:uppercase; font-weight:800;
  }
  .ws-meso { display:grid; grid-template-columns:repeat(4,1fr); gap:.55rem; margin-bottom:.85rem; }
  @media (max-width:900px){
    .ws-meso{grid-template-columns:1fr 1fr;}
    .ws-cast{grid-template-columns:1fr !important;}
    .ws-profile{grid-template-columns:1fr !important;}
  }
  .ws-cast {
    display:grid;
    grid-template-columns:repeat(3, minmax(0, 1fr));
    gap:.85rem;
    margin-bottom:.75rem;
    align-items:stretch;
  }
  .ws-cast > .ws-panel-card {
    display:flex;
    flex-direction:column;
    min-width:0;
    height:100%;
    box-sizing:border-box;
  }
  .ws-cast .ws-meters { flex:1 1 auto; display:flex; flex-direction:column; gap:.1rem; }
  .ws-cast .ws-flavor {
    min-height:2.6em; margin:.35rem 0 .15rem 0; font-size:.72rem;
    letter-spacing:.04em; text-transform:uppercase; font-weight:800; color:#2b2118 !important;
  }
  .ws-cast .ws-packets {
    min-height:2.4em; margin-top:auto; padding-top:.25rem;
    display:flex; flex-wrap:wrap; align-content:flex-start;
  }
  .ws-profile { display:grid; grid-template-columns:200px 1fr; gap:1rem; }
  .ws-char { text-align:center; }
  .ws-portrait {
    margin:0 auto .45rem auto; border:3px solid #C9A227; border-radius:3px;
    background: linear-gradient(155deg, #3A2A1A, #15100C),
      repeating-linear-gradient(45deg,#2C2218 0 7px,#1A140E 7px 14px);
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    box-shadow: 0 0 0 1px rgba(139,94,47,.5), 0 8px 24px rgba(0,0,0,.35);
  }
  .ws-glyph { font-size:2.4rem; color:#FFF8E7 !important; line-height:1; text-shadow:0 2px 0 #0A0908; font-weight:800; }
  .ws-ph { font-size:.55rem; letter-spacing:.1em; text-transform:uppercase; color:#E8D7B8 !important; margin-top:.25rem; font-weight:700; }
  /* Dark nameplates: cream / white text */
  .ws-nameplate {
    display:inline-block; min-width:70%; padding:.28rem .55rem;
    border:2px solid #E0B84E; background:linear-gradient(180deg,#2A1C10,#120E0A);
    border-radius:2px;
  }
  .ws-nameplate strong { display:block; color:#FFF8E7 !important; letter-spacing:.08em; font-size:.95rem; font-weight:800; }
  .ws-nameplate em { display:block; color:#FFE08A !important; font-style:normal; font-size:.78rem; letter-spacing:.04em; text-transform:uppercase; font-weight:700; }
  .ws-meter { margin:.35rem 0; }
  .ws-meter-label {
    display:flex; justify-content:space-between; font-size:.78rem;
    color:#1a1208 !important; margin-bottom:.12rem; font-weight:800;
  }
  .ws-meter-track { height:12px; background:#D9C7A5; border:1px solid #2b2118; overflow:hidden; }
  .ws-meter-fill { height:100%; transition:width .35s ease; }
  .ws-dialogue {
    margin-top:.55rem; border:3px solid #2b2118; border-radius:3px;
    background:#FFF8E7; overflow:hidden;
  }
  .ws-speaker {
    display:inline-block; margin:.55rem 0 0 .7rem; padding:.15rem .65rem;
    background:linear-gradient(180deg,#3A2830,#1E1418); border:2px solid #C4899C;
    color:#FFF8E7 !important; font-weight:800; letter-spacing:.06em; font-size:.8rem; text-transform:uppercase;
  }
  .ws-line { padding:.55rem .85rem .8rem .85rem; color:#1a1208 !important; font-size:1rem; line-height:1.5; min-height:3.2rem; font-weight:600; }
  .ws-panel-card {
    background:#FFF8E7; border:2px solid #8B5E2F; border-radius:2px; padding:.75rem;
    color:#1a1208 !important;
  }
  /* Ink on panel text — but do NOT blanket * (stomps cream glyph/nameplate) */
  .ws-panel-card .ws-sec,
  .ws-panel-card .ws-trust-row,
  .ws-panel-card .ws-meter-label,
  .ws-panel-card .ws-flavor,
  .ws-panel-card .ws-chip { color:#1a1208 !important; }
  .ws-panel-card .ws-glyph { color:#FFF8E7 !important; }
  .ws-panel-card .ws-ph { color:#E8D7B8 !important; }
  .ws-panel-card .ws-nameplate strong { color:#FFF8E7 !important; }
  .ws-panel-card .ws-nameplate em { color:#FFE08A !important; }
  .ws-panel-card .ws-speaker { color:#FFF8E7 !important; }
  .ws-chip {
    display:inline-block; margin:.15rem; padding:.12rem .45rem;
    border:1px solid #2b2118; background:#E8D7B8; color:#1a1208 !important;
    font-size:.72rem; letter-spacing:.04em; font-weight:800;
  }
  .ws-trust-row {
    font-size:.8rem; color:#1a1208 !important; display:flex;
    justify-content:space-between; margin:.2rem 0; font-weight:700;
  }
  .ws-sec {
    color:#2b2118 !important; font-size:.8rem; letter-spacing:.08em;
    margin-bottom:.35rem; font-weight:800; text-transform:uppercase;
  }
</style>"""


def render_field(state: dict | None) -> str:
    s = state or initial_state()
    q = int(s.get("quarter_in_year") or (((int(s.get("quarter", 1)) - 1) % 4) + 1))
    year = int(s.get("year", -260))
    tick = int(s.get("tick", 0))
    era = f"Q{q} · {abs(year)} BCE · tick {tick}"
    agents = s.get("agents") or {}
    speaker, line = latest_dialogue(s)
    eng = s.get("_engine") or {}
    ended = bool(eng.get("run_ended") or s.get("run_ended"))
    end = eng.get("end_screen") or s.get("end_screen")
    m4_live = s.get("m4") or {}
    m1_live = s.get("m1") or {}
    m4 = rollup_m4()  # static table labels; live scalars prefer projection
    who = s.get("who_vs_qin") or ""

    opening = ""
    if tick == 0 and not eng.get("opening_seen"):
        opening = (
            f'<div class="ws-panel-card" style="margin-bottom:.75rem;border-color:#8B1E1E;">'
            f'<div class="ws-sec">{_esc(OPENING_CARD["title"])}</div>'
            f'<div style="font-size:.9rem;font-weight:600;line-height:1.45;">{_esc(OPENING_CARD["body"])}</div>'
            f'<div class="ws-pathway" style="margin-top:.4rem;">anti-Qin = holding coalition vs Qin existential pressure '
            f"(Changping / Ying-fall prior) — not friendship with Qin.</div></div>"
        )

    end_html = ""
    if ended and end:
        dead = ", ".join(end.get("dead_edges") or []) or "none"
        end_html = (
            f'<div class="ws-panel-card" style="margin-bottom:.75rem;border-color:#8B1E1E;">'
            f'<div class="ws-sec">{_esc(end.get("title", "SOFT-LOCK"))}</div>'
            f'<div style="font-weight:800;">pathway = {_esc(end.get("pathway"))}</div>'
            f'<div style="font-size:.88rem;font-weight:600;margin:.35rem 0;">{_esc(end.get("pathway_blurb"))}</div>'
            f'<div style="font-size:.82rem;">{_esc(end.get("reason"))}</div>'
            f'<div class="ws-trust-row"><span>dead edges</span><span>{_esc(dead[:120])}</span></div>'
            f'<div style="font-size:.78rem;margin-top:.35rem;">{_esc(end.get("who_note"))}</div></div>'
        )

    meso = "".join(
        [
            _bar("qin_pressure", float(s.get("qin_pressure", 0)), "#8B1E1E", vmax=100),
            _bar(
                "alliance_cohesion",
                float(s.get("alliance_cohesion", 0)),
                "#1F5F6F",
                vmax=100,
            ),
            _bar(
                "shared_identity",
                float(s.get("shared_identity", 0)),
                "#3D5C3D",
                vmax=100,
            ),
            _bar(
                "cascade_armed",
                float(s.get("cascade_armed", 0)),
                "#7A4058",
                vmax=6,
            ),
        ]
    )

    # Equal 3-column court panels: same meter set + flavor slot + packet row
    court_flavor = {
        "qin": "Qin = pressure source (fa · tianxia)",
        "chu": "Chu = Daoist–aristocratic patron net",
        "qi": "Qi = Guanzi / isolation · Withhold lean",
    }
    cast = ""
    for aid in ("qin", "chu", "qi"):
        ag = dict(agents.get(aid) or {"name": aid.title(), "intention": "?"})
        ag["intention_label"] = ag.get("intention_label") or ag.get("intention", "?")
        meters = (
            '<div class="ws-meters">'
            + _bar("resentment", float(ag.get("resentment", 0)), "#8B1E1E")
            + _bar("status_threat", float(ag.get("status_threat", 0)), "#7A4058")
            + _bar("betrayal_memory", float(ag.get("betrayal_memory", 0)), "#aa6666")
            + _bar("fear_of_qin", float(ag.get("fear_of_qin", 0)), "#886688")
            + "</div>"
        )
        packets = "".join(
            f'<span class="ws-chip">{_esc(p)}</span>' for p in (ag.get("packets") or [])[:4]
        ) or '<span class="ws-chip">no packets</span>'
        cast += (
            f'<div class="ws-panel-card" data-court="{aid}">'
            f"{_portrait_block(aid, ag)}"
            f"{meters}"
            f'<div class="ws-flavor">{_esc(court_flavor[aid])}</div>'
            f'<div class="ws-packets">{packets}</div>'
            f"</div>"
        )

    ft = s.get("featured_trust") or {}
    trust_html = "".join(
        f'<div class="ws-trust-row"><span>{_esc(k)}</span><span>{float(v):.2f}</span></div>'
        for k, v in ft.items()
    )
    m4_html = "".join(
        f'<div class="ws-trust-row"><span>{_esc(n.label)}</span>'
        f'<span>def {n.defense_mod:.2f} · march {n.march_cost:.2f}</span></div>'
        for n in list(rollup_m4().to_dict()["table"].values())[:6]
        if False
    )
    # Use geo table directly
    from engine.geo import M4_TABLE

    m4_html = "".join(
        f'<div class="ws-trust-row"><span>{_esc(n.label)}</span>'
        f"<span>def {n.defense_mod:.2f} · levy {n.levy_mod:.2f}</span></div>"
        for n in M4_TABLE.values()
    )
    def_mod = float(m4_live.get("defense_mod", m4.defense_mod))
    proj = float(m4_live.get("qin_projection", m4.qin_projection))
    levy_v = float(m4_live.get("levy_capacity", m4.levy_capacity))
    famine_v = float(m1_live.get("famine_shock", m4_live.get("famine_shock", 0.0)))
    m4_html += (
        f'<div class="ws-trust-row"><span>rollup defense / projection</span>'
        f"<span>{def_mod:.2f} / {proj:.2f}</span></div>"
        f'<div class="ws-trust-row"><span>M1 levy / famine</span>'
        f"<span>{levy_v:.2f} / {famine_v:.2f}</span></div>"
        f'<div style="font-size:.72rem;font-weight:600;margin-top:.25rem;">'
        f"M4 coarse scalars + M1 famine haircut — not GIS.</div>"
    )

    # M2 Adoption Meter + military (live DAG — unlock ≠ fieldable)
    m2 = s.get("m2") or {}
    mil = m2.get("military") or {}
    adopt = m2.get("adoption_mean") or {}
    m2_html = (
        _bar("adoption_meter (mean)", float(s.get("adoption_meter") or m2.get("adoption_meter") or 0), "#3D5C3D")
        + _bar("qin military", float(s.get("military_qin") or m2.get("qin_mil") or mil.get("qin") or 0), "#8B1E1E")
        + _bar(
            "coalition military",
            float(s.get("military_coalition") or m2.get("coalition_mil") or 0),
            "#1F5F6F",
        )
        + _bar(
            "qin mil advantage",
            max(0.0, float(s.get("qin_mil_advantage") or m2.get("qin_mil_advantage") or 0)),
            "#7A4058",
        )
    )
    for sid in ("qin", "chu", "qi"):
        m2_html += (
            f'<div class="ws-trust-row"><span>{sid} adopt / mil</span>'
            f"<span>{float(adopt.get(sid, 0)):.2f} / {float(mil.get(sid, 0)):.2f}</span></div>"
        )
    for row in (m2.get("rows") or [])[:6]:
        m2_html += (
            f'<div class="ws-trust-row"><span>{_esc(row.get("label"))}</span>'
            f'<span>Q {float(row.get("qin_adopted", 0)):.2f} · '
            f'C {float(row.get("chu_adopted", 0)):.2f} · '
            f'Qi {float(row.get("qi_adopted", 0)):.2f}</span></div>'
        )
    m2_html += (
        '<div style="font-size:.72rem;font-weight:600;margin-top:.25rem;">'
        "M2 DAG + Adoption Meter — unlock ≠ fieldable; Qin logistics ≠ metallurgy apex.</div>"
    )

    # Event log dashboard: faction Δ + recent episode rows
    run_d = s.get("run_deltas") or {}
    fac = run_d.get("factions") or {}
    delta_html = ""
    for aid in ("qin", "chu", "qi"):
        d = fac.get(aid) or {}
        bits = ", ".join(f"{k} {v:+.2f}" for k, v in list(d.items())[:4]) or "—"
        delta_html += f'<div class="ws-trust-row"><span>{_esc(aid)} Δ</span><span>{_esc(bits)}</span></div>'
    meso_d = run_d.get("meso") or {}
    delta_html += (
        f'<div class="ws-trust-row"><span>meso Δ pressure/cohesion</span>'
        f"<span>{float(meso_d.get('qin_pressure', 0)):+.1f} / {float(meso_d.get('cohesion', 0)):+.1f}</span></div>"
    )
    episode = s.get("episode") or []
    ep_rows = ""
    for row in list(episode)[-8:]:
        if not isinstance(row, dict):
            continue
        tid = row.get("tick", "?")
        eid = row.get("event_id") or row.get("action") or "event"
        msg = row.get("message") or row.get("text") or row.get("summary") or ""
        if not msg and row.get("speaker"):
            msg = f"{row.get('speaker')}: {row.get('line') or ''}"
        ep_rows += (
            f'<div class="ws-trust-row"><span>t{_esc(tid)} · {_esc(eid)}</span>'
            f"<span>{_esc(str(msg)[:90])}</span></div>"
        )
    if not ep_rows:
        ep_rows = '<div class="ws-trust-row"><span>episode</span><span>empty — Advance to log</span></div>'

    return f"""
{_shared_style()}
<div class="ws-root">
  <div class="ws-top"><h2>Warring States -- Tactical Field</h2><span class="era">{_esc(era)}</span></div>
  {opening}{end_html}
  <div class="ws-pathway">
    pathway_soft · {_esc(s.get('pathway_soft', 'other'))} · quorum_ok={_esc(s.get('quorum_ok'))}
    · {_esc(who)}
    {(' · ' + _esc(s.get('pathway_reading'))) if s.get('pathway_reading') else ''}
  </div>
  <div class="ws-meso">{meso}</div>
  <div class="ws-cast">{cast}</div>
  <div class="ws-panel-card" style="margin-bottom:.65rem;">
    <div class="ws-sec">M4 GEO (pass / corridor / levy) — feeds Qin pressure + defense</div>
    {m4_html}
  </div>
  <div class="ws-panel-card" style="margin-bottom:.65rem;">
    <div class="ws-sec">M2 TECH — Adoption Meter + military strength (feeds pressure / quorum / lock)</div>
    {m2_html}
  </div>
  <div class="ws-panel-card" style="margin-bottom:.65rem;">
    <div class="ws-sec">DYADIC TRUST (featured)</div>
    {trust_html}
  </div>
  <div class="ws-panel-card" style="margin-bottom:.65rem;">
    <div class="ws-sec">EVENT LOG DASHBOARD — FACTION Δ + RECENT EPISODE</div>
    {delta_html}
    <div class="ws-sec" style="margin-top:.55rem;">RECENT EPISODE</div>
    {ep_rows}
  </div>
  <div class="ws-dialogue">
    <div class="ws-speaker">{_esc(speaker)}</div>
    <div class="ws-line">{_esc(line)}</div>
  </div>
</div>"""


def render_profile(state: dict | None, agent_id: str) -> str:
    s = state or initial_state()
    aid = normalize_figure_id(agent_id)
    prof = character_profile(s, aid)
    if prof.get("error"):
        return f"<div class='ws-root'>{_esc(prof['error'])}</div>"

    home = prof.get("home_court") or aid
    intent = prof.get("intention") or {}
    ag_stub = {
        "name": prof.get("name"),
        "intention": intent.get("current", "?"),
        "intention_label": intent.get("label") or intent.get("current", "?"),
        "home_court": home,
    }
    bf = prof["big_five"]
    st = prof["state"]
    ocean = "".join(
        [
            _bar("openness", bf["openness"], "#3D5C3D"),
            _bar("conscientiousness", bf["conscientiousness"], "#1F5F6F"),
            _bar("extraversion", bf["extraversion"], "#C9A227"),
            _bar("agreeableness", bf["agreeableness"], "#7A4058"),
            _bar("neuroticism", bf["neuroticism"], "#8B1E1E"),
        ]
    )
    state_bars = "".join(
        [
            _bar("resentment", st["resentment"], "#8B5E2F"),
            _bar("fear_of_qin", st["fear_of_qin"], "#886688"),
            _bar("betrayal_memory", st["betrayal_memory"], "#aa6666"),
            _bar("status_threat", st["status_threat"], "#7A4058"),
            _bar("perceived_threat", st["perceived_threat"], "#997755"),
            _bar("withholding_threshold", st["withholding_threshold"], "#3D5C3D"),
        ]
    )
    meso = "".join(
        [
            _bar("qin_pressure", float(prof["qin_pressure"]), "#8B1E1E", vmax=100),
            _bar(
                "alliance_cohesion",
                float(prof["alliance_cohesion"]),
                "#1F5F6F",
                vmax=100,
            ),
            _bar(
                "shared_identity",
                float(prof["shared_identity"]),
                "#3D5C3D",
                vmax=100,
            ),
            _bar(
                "cascade_armed", float(prof["cascade_armed"]), "#7A4058", vmax=6
            ),
        ]
    )
    weights = prof.get("packet_weights") or {}
    packets = "".join(
        f'<span class="ws-chip">{_esc(p)} {float(weights.get(p, 0)):.0%}</span>'
        for p in (prof.get("packets") or [])
    )
    weight_bars = "".join(
        _bar(k, float(v), "#3D5C3D") for k, v in sorted(weights.items(), key=lambda x: -x[1])
    )
    base_schools = prof.get("base_schools") or {}
    base_bars = "".join(
        _bar(k, float(v), "#8B5E2F")
        for k, v in (
            ("legalism", base_schools.get("legalism", 0)),
            ("mohism", base_schools.get("mohism", 0)),
            ("daoism", base_schools.get("daoism", 0)),
            ("confucianism", base_schools.get("confucianism", 0)),
        )
    )
    dyadic = "".join(
        f'<div class="ws-trust-row"><span>{_esc(k)}</span><span>{float(v):.2f}</span></div>'
        for k, v in sorted((prof.get("dyadic_trust") or {}).items())
    )
    ideo = prof.get("ideology") or {}
    ideo_bars = "".join(_bar(k, float(v), "#3D5C3D") for k, v in ideo.items())
    anchors = "".join(
        f'<div style="font-size:.72rem;font-weight:600;margin:.15rem 0;">• {_esc(a)}</div>'
        for a in (prof.get("shiji_anchors") or [])[:4]
    )
    zh = prof.get("name_zh") or ""
    role = prof.get("role_label") or ""

    return f"""
{_shared_style()}
<div class="ws-root">
  <div class="ws-top"><h2>Character Profile</h2><span class="era">tick {int(prof.get('tick',0))} · {_esc(prof.get('pathway_soft'))}</span></div>
  <div class="ws-pathway">{_esc(zh)} · {_esc(role)} · home court {_esc(home)} · confidence={_esc(prof.get('confidence'))}</div>
  <div class="ws-profile">
    <div class="ws-panel-card">
      {_portrait_block(aid, ag_stub, large=True)}
      <div style="margin-top:.5rem;font-size:.82rem;color:#1a1208;line-height:1.45;font-weight:600;">{_esc(prof.get('dossier',''))}</div>
      <div class="ws-sec" style="margin-top:.55rem;">STICKY INTENTION (home court)</div>
      <div style="font-size:.95rem;color:#1a1208;font-weight:700;">{_esc(intent.get('label') or intent.get('current'))}</div>
      <div class="ws-trust-row"><span>engine id</span><span>{_esc(intent.get('current'))}</span></div>
      <div class="ws-trust-row"><span>sticky_until</span><span>{_esc(intent.get('sticky_until'))}</span></div>
      <div class="ws-sec" style="margin-top:.45rem;">FOUR BASE SCHOOLS (rolled from mix)</div>
      {base_bars}
      <div class="ws-sec" style="margin-top:.45rem;">PACKETS / SYNCRETISMS (many mixes)</div>
      <div>{packets}</div>
      {weight_bars}
      <div style="font-size:.72rem;font-weight:600;margin-top:.35rem;">{_esc(prof.get('syncretism_note',''))}</div>
    </div>
    <div>
      <div class="ws-panel-card" style="margin-bottom:.65rem;"><div class="ws-sec">OCEAN (figure JSON prior)</div>{ocean}</div>
      <div class="ws-panel-card" style="margin-bottom:.65rem;"><div class="ws-sec">STATE LAYER (live home court)</div>{state_bars}</div>
      <div class="ws-panel-card" style="margin-bottom:.65rem;"><div class="ws-sec">MESO / MACRO</div>{meso}</div>
      <div class="ws-panel-card" style="margin-bottom:.65rem;"><div class="ws-sec">TRUST (interstate + chu_court spokes)</div>{dyadic or '<div class="ws-trust-row">none</div>'}</div>
      <div class="ws-panel-card" style="margin-bottom:.65rem;"><div class="ws-sec">SHIJI ANCHORS</div>{anchors or '—'}</div>
      <div class="ws-panel-card"><div class="ws-sec">COURT IDEOLOGY DIALS</div>{ideo_bars}</div>
    </div>
  </div>
</div>"""


# Short Radio labels only — never Dropdown; never bare "chu"; never huge engine labels
RADIO_FIGURES: list[tuple[str, str]] = [
    ("Kaolie — King of Chu", "kaolie"),
    ("Chunshen — Chu patron", "chunshen"),
    ("Chu nobility — clients", "chu_nobility"),
    ("Ying Zheng — King of Qin", "ying_zheng"),
    ("Li Si — Qin chancellor", "li_si"),
    ("King Jian — Qi isolationist", "king_jian"),
]


def build_ui() -> gr.Blocks:
    # HARD RULE: never instantiate gr.Dropdown — Profile is Radio of exactly 6 figures.
    radio_choices = list(RADIO_FIGURES)
    assert len(radio_choices) == 6, radio_choices
    assert all(vid != "chu" for _lab, vid in radio_choices)
    # Sanity: engine still exposes 6 ids (layout does not use engine's long labels)
    engine_ids = {vid for _lab, vid in character_choices(None)}
    assert {vid for _lab, vid in radio_choices} == engine_ids, (radio_choices, engine_ids)

    with gr.Blocks(css=THEME_CSS, title="Warring States -- RPG Watch") as demo:
        gr.Markdown(
            "# Warring States -- RPG Tactical Watch\n"
            "Anti-Qin coalition watch · Contribute/Withhold/Defect vs Qin pressure · named figures",
            elem_id="ws-title",
        )
        # Field actions use figure_id State — do NOT require Profile Radio in same request
        state = gr.State(initial_state())
        figure_id = gr.State(DEFAULT_FIGURE_ID)

        with gr.Tabs():
            with gr.Tab("Field"):
                canvas = gr.HTML(value=render_field(initial_state()), elem_id="ws-canvas")
                btn_new = gr.Button(
                    "NEW RUN — reset world / clear soft-lock",
                    variant="primary",
                    elem_id="ws-new-run",
                    size="lg",
                )
                intervene_pick = gr.CheckboxGroup(
                    choices=["qin", "chu", "qi"],
                    value=["chu"],
                    label="Intervene targets (Qin / Chu / Qi — multi-select)",
                    info="Qin = delay probe; Chu/Qi = sticky Contribute to anti-Qin coalition",
                    elem_id="ws-intervene-pick",
                )
                with gr.Row(elem_id="ws-actions"):
                    btn_advance = gr.Button("Advance Quarter", variant="primary")
                    btn_intervene = gr.Button("Intervene selected", elem_id="ws-intervene-btn")
                    btn_alliance = gr.Button("Attempt Alliance")
                with gr.Row(elem_id="ws-actions"):
                    btn_short = gr.Button("Short Demo (mechanisms only — no Q-count end)")
                chatbot = gr.Chatbot(
                    value=bootstrap_dialogue(),
                    type="messages",
                    label="Chronicle — coalition stances (not Qin friendship)",
                    height=220,
                    elem_id="ws-chatbot",
                    allow_tags=False,
                )

            with gr.Tab("Character Profile"):
                with gr.Column(elem_id="ws-profile-scroll"):
                    # Radio ALWAYS visible (not inside Accordion) — 6 figures, never Dropdown
                    with gr.Group(elem_id="ws-radio-panel"):
                        gr.Markdown(
                            "### Cast Radio — 6 figures (not a dropdown)",
                            elem_id="ws-cast-heading",
                        )
                        picker = gr.Radio(
                            choices=radio_choices,
                            value=DEFAULT_FIGURE_ID,
                            label="Select figure — Radio only (6)",
                            elem_id="ws-figure-picker",
                            interactive=True,
                            type="value",
                        )
                    with gr.Accordion(
                        "Cast id map (click to collapse)",
                        open=False,
                        elem_id="ws-cast-accordion",
                    ):
                        cast_list_html = (
                            '<div class="ws-root" id="ws-cast-list">'
                            '<div class="ws-sec">NAMED CAST (6) — Radio values</div>'
                            + "".join(
                                '<div class="ws-trust-row"><span>{0}</span>'
                                "<span>{1}</span></div>".format(
                                    html_lib.escape(lab), html_lib.escape(vid)
                                )
                                for lab, vid in radio_choices
                            )
                            + "</div>"
                        )
                        gr.HTML(value=cast_list_html, elem_id="ws-cast-list-panel")
                    with gr.Accordion(
                        "Figure dossier (click to collapse / minimize)",
                        open=True,
                        elem_id="ws-dossier-accordion",
                    ):
                        profile = gr.HTML(
                            value=render_profile(initial_state(), DEFAULT_FIGURE_ID),
                            elem_id="ws-profile",
                        )
                        refresh = gr.Button("Refresh profile from WorldState")

        def _pick_id(pick) -> str:
            return normalize_figure_id(pick)

        def _norm_targets(targets) -> list[str]:
            if targets is None:
                return []
            if isinstance(targets, str):
                t = targets.strip().lower()
                return [t] if t in ("qin", "chu", "qi") else []
            out: list[str] = []
            for t in list(targets):
                tid = str(t or "").strip().lower()
                if tid in ("qin", "chu", "qi") and tid not in out:
                    out.append(tid)
            return out

        def _pack(new_state, chat, fid):
            aid = _pick_id(fid)
            return (
                new_state,
                aid,
                render_field(new_state),
                chat,
                render_profile(new_state, aid),
                aid,
            )

        def _after(action, s, h, fid):
            result = action(s if s is not None else initial_state())
            # backend actions may return (state, msgs) or (state, msgs, err)
            new_state, msgs = result[0], result[1]
            return _pack(new_state, merge_chat(h, msgs), fid)

        def _do_intervene(s, h, fid, targets):
            cleaned = _norm_targets(targets)

            def act(raw):
                return intervene_targets(raw, cleaned)

            return _after(act, s, h, fid)

        def _short_demo(s, h, fid):
            new_state = arm_short_demo(s if s is not None else initial_state(), 8)
            chat = merge_chat(
                h,
                [
                    {
                        "role": "assistant",
                        "content": (
                            "**Chronicler** — Short Demo: Advance + Intervene focus. "
                            "No Q-count end — soft-lock only from mechanisms. New Run resets."
                        ),
                    }
                ],
            )
            return _pack(new_state, chat, fid)

        def _new_run(s, h, fid):
            return _pack(fresh_run(), bootstrap_dialogue(), fid)

        def _advance(s, h, fid):
            return _after(advance_quarter, s, h, fid)

        def _alliance(s, h, fid):
            return _after(attempt_alliance, s, h, fid)

        _out = [state, figure_id, canvas, chatbot, profile, picker]

        btn_intervene.click(
            _do_intervene,
            inputs=[state, chatbot, figure_id, intervene_pick],
            outputs=_out,
        )
        btn_advance.click(_advance, inputs=[state, chatbot, figure_id], outputs=_out)
        btn_alliance.click(_alliance, inputs=[state, chatbot, figure_id], outputs=_out)
        btn_short.click(_short_demo, inputs=[state, chatbot, figure_id], outputs=_out)
        btn_new.click(_new_run, inputs=[state, chatbot, figure_id], outputs=_out)

        def _on_pick(s, p):
            aid = _pick_id(p)
            return aid, render_profile(s if s is not None else initial_state(), aid), aid

        picker.change(
            _on_pick,
            inputs=[state, picker],
            outputs=[figure_id, profile, picker],
        )
        refresh.click(
            _on_pick,
            inputs=[state, picker],
            outputs=[figure_id, profile, picker],
        )

        demo.load(
            lambda: (
                DEFAULT_FIGURE_ID,
                DEFAULT_FIGURE_ID,
                render_profile(initial_state(), DEFAULT_FIGURE_ID),
            ),
            inputs=None,
            outputs=[figure_id, picker, profile],
        )

    return demo



if __name__ == "__main__":
    build_ui().launch(server_name="127.0.0.1", server_port=7860, show_error=True)
