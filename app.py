# -*- coding: utf-8 -*-
"""
Rota Inteligente - ATL / Autoport (Streamlit)
=============================================
Rota real por estrada (OpenRouteService) + ordem de entrega otimizada por
combustivel + montagem de carga LIFO (11 posicoes, 2 pisos) + mapa + cegonha.

Rodar:
  1) pip install -r requirements.txt
  2) .streamlit/secrets.toml com  ORS_API_KEY = "sua_chave"
     (gratis em https://openrouteservice.org/dev/#/signup)
  3) streamlit run app.py
"""

import itertools
import urllib.parse
import pandas as pd
import streamlit as st
import openrouteservice as ors
import folium
from streamlit_folium import st_folium

# ---------------------------------------------------------------- paleta
NAVY = "#0C1B2E"; ACCENT = "#C8102E"; FG = "#0F1A2E"; FG2 = "#4B5C72"
FG3 = "#8896A8"; BORDER = "#E2E6ED"; CARD = "#FFFFFF"; CARD_ALT = "#F8FAFC"
COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444", "#06B6D4", "#6366F1", "#EC4899"]

# ---------------------------------------------------------------- posicoes padrao
# prioridade 1 = descarrega primeiro (mais acessivel, perto da rampa)
POSICOES_PADRAO = [
    {"Posição": "S1", "Piso": "Superior", "Prioridade": 11},
    {"Posição": "S2", "Piso": "Superior", "Prioridade": 9},
    {"Posição": "S3", "Piso": "Superior", "Prioridade": 7},
    {"Posição": "S4", "Piso": "Superior", "Prioridade": 4},
    {"Posição": "S5", "Piso": "Superior", "Prioridade": 2},
    {"Posição": "I1", "Piso": "Inferior", "Prioridade": 10},
    {"Posição": "I2", "Piso": "Inferior", "Prioridade": 8},
    {"Posição": "I3", "Piso": "Inferior", "Prioridade": 6},
    {"Posição": "I4", "Piso": "Inferior", "Prioridade": 5},
    {"Posição": "I5", "Piso": "Inferior", "Prioridade": 3},
    {"Posição": "I6", "Piso": "Inferior", "Prioridade": 1},
]
CAPACIDADE = len(POSICOES_PADRAO)

PARADAS_PADRAO = pd.DataFrame([
    {"Cidade": "Cariacica/ES", "Carros": 1},
    {"Cidade": "Governador Valadares/MG", "Carros": 3},
    {"Cidade": "Coronel Pacheco/MG", "Carros": 1},
])

st.set_page_config(page_title="Rota Inteligente", layout="wide")

# ---------------------------------------------------------------- icones (SVG livre, Feather - MIT)
_IC = {
    "truck": '<path d="M1 3h15v13H1z"/><path d="M16 8h4l3 3v5h-7V8z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
    "nav": '<polygon points="3 11 22 2 13 21 11 13 3 11"/>',
    "pin": '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    "list": '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "fuel": '<path d="M12 2.7l5.7 5.7a8 8 0 1 1-11.4 0z"/>',
    "dollar": '<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "road": '<path d="M4 19l4-14"/><path d="M20 19l-4-14"/><line x1="12" y1="6" x2="12" y2="8"/><line x1="12" y1="11" x2="12" y2="13"/><line x1="12" y1="16" x2="12" y2="18"/>',
    "map": '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>',
}
def ic(name, size=18, color="currentColor", sw=2):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" '
            f'style="vertical-align:middle;flex-shrink:0">{_IC[name]}</svg>')

# ---------------------------------------------------------------- CSS
st.markdown("""
<style>
#MainMenu, footer, header[data-testid="stHeader"] {visibility:hidden; height:0;}
.block-container {padding-top:1.6rem; padding-bottom:3rem; max-width:1080px;}
/* cabecalho */
.ri-header{background:#0C1B2E;border-radius:14px;padding:20px 24px;display:flex;
  align-items:center;gap:14px;margin-bottom:22px;flex-wrap:wrap;min-height:72px;}
.ri-mark{width:40px;height:40px;background:#C8102E;border-radius:9px;display:flex;
  align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:15px;flex-shrink:0;}
.ri-htext{display:flex;flex-direction:column;line-height:1.25;}
.ri-title{font-size:22px;font-weight:800;color:#fff;letter-spacing:-.2px;padding:1px 0;}
.ri-title b{color:#C8102E;}
.ri-subt{font-size:12px;color:rgba(255,255,255,.55);font-weight:500;}
.ri-tag{margin-left:auto;font-size:11px;font-weight:700;color:rgba(255,255,255,.45);
  letter-spacing:2px;text-transform:uppercase;align-self:flex-start;}
/* titulos de secao */
.ri-h{display:flex;align-items:center;gap:9px;font-size:15px;font-weight:700;color:#0F1A2E;
  margin:2px 0 14px;}
.ri-h .sub{font-weight:500;color:#8896A8;font-size:11px;margin-left:auto;}
/* metricas */
.ri-stats{display:flex;gap:14px;flex-wrap:wrap;margin:4px 0 18px;}
.ri-st{flex:1;min-width:150px;background:#fff;border:1px solid #E2E6ED;border-radius:14px;
  padding:16px 18px;box-shadow:0 1px 3px rgba(12,27,46,.05);}
.ri-st .top{display:flex;align-items:center;gap:7px;color:#8896A8;margin-bottom:8px;}
.ri-st .top span{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;}
.ri-st .v{font-size:27px;font-weight:800;color:#0F1A2E;letter-spacing:-.6px;line-height:1;}
.ri-st .d{font-size:11px;color:#8896A8;margin-top:5px;}
/* fluxo rota */
.ri-card{background:#fff;border:1px solid #E2E6ED;border-radius:14px;padding:20px;
  box-shadow:0 1px 3px rgba(12,27,46,.05);margin-bottom:18px;}
.ri-flow{display:flex;align-items:flex-start;gap:4px;overflow-x:auto;padding:4px 0;}
.ri-node{display:flex;flex-direction:column;align-items:center;gap:6px;min-width:84px;flex-shrink:0;}
.ri-circ{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-weight:800;color:#fff;font-size:14px;}
.ri-lbl{font-size:12px;font-weight:600;color:#4B5C72;text-align:center;line-height:1.25;}
.ri-sub{font-size:10px;color:#8896A8;font-weight:500;text-align:center;}
.ri-arrow{flex:1;min-width:22px;height:2px;background:#E2E6ED;margin-top:19px;}
.stButton>button{font-weight:700;border-radius:9px;padding:9px 18px;}
.ri-info{background:#F8FAFC;border:1px solid #E2E6ED;border-left:3px solid #C8102E;
  border-radius:8px;padding:10px 14px;font-size:12.5px;color:#4B5C72;margin-bottom:14px;}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="ri-header">
  <div class="ri-mark">AP</div>
  <div class="ri-htext">
    <div class="ri-title">Rota <b>Inteligente</b></div>
    <div class="ri-subt">Planejamento de rota e montagem de carga — cegonha</div>
  </div>
  <div class="ri-tag">Autoport</div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- ORS
def get_client():
    key = st.secrets.get("ORS_API_KEY", "")
    if not key:
        st.error('Falta a chave do OpenRouteService. No Streamlit Cloud: Manage app → Settings → '
                 'Secrets → ORS_API_KEY = "sua_chave". Local: .streamlit/secrets.toml.')
        st.stop()
    return ors.Client(key=key)

@st.cache_data(show_spinner=False)
def geocode(texto):
    r = get_client().pelias_search(text=texto, country="BRA", size=1)
    feats = r.get("features", [])
    if not feats:
        return None
    lon, lat = feats[0]["geometry"]["coordinates"]
    return (lon, lat)

@st.cache_data(show_spinner=False)
def matriz_km(coords):
    r = get_client().distance_matrix(locations=coords, profile="driving-hgv",
                                     metrics=["distance"], units="km")
    return r["distances"]

@st.cache_data(show_spinner=False)
def geometria_rota(coords_ord):
    return get_client().directions(coordinates=coords_ord, profile="driving-hgv", format="geojson")


# ---------------------------------------------------------------- otimizacao
def custo_combustivel(ordem, D, dmat, qtds, base, extra, peso):
    litros = km = 0.0; atual = 0; carros = sum(qtds[i] for i in ordem)
    for p in ordem:
        d = dmat[atual][p]
        litros += d * (base + extra * carros * peso); km += d
        carros -= qtds[p]; atual = p
    d = dmat[atual][D]; litros += d * base; km += d
    return litros, km

def otimizar(n, D, dmat, qtds, base, extra, peso):
    melhor = None
    for perm in itertools.permutations(range(1, 1 + n)):
        l, k = custo_combustivel(perm, D, dmat, qtds, base, extra, peso)
        if melhor is None or l < melhor[0]:
            melhor = (l, k, perm)
    return melhor

def montar_carga(ordem_nomes, qtds_por_nome, positions):
    posicoes = sorted(positions, key=lambda p: p["Prioridade"])
    atrib = []; i = 0
    for ordem_idx, nome in enumerate(ordem_nomes, start=1):
        for _ in range(qtds_por_nome[nome]):
            if i < len(posicoes):
                atrib.append({"pos": posicoes[i]["Posição"], "piso": posicoes[i]["Piso"],
                              "entrega": nome, "ordem_entrega": ordem_idx, "ordem_descarga": i + 1})
                i += 1
    return atrib


# ---------------------------------------------------------------- desenho da cegonha
def _f(n): return f"{n:.1f}"
def _car(cx, gY, w, c):
    wr=w*0.12; h=w*0.46; bx=cx-w/2; by=gY-wr; lowT=by-h*0.5; roofT=by-h
    return (f'<circle cx="{_f(cx-w*0.27)}" cy="{_f(by)}" r="{_f(wr)}" fill="#141b29" stroke="{BORDER}" stroke-width="1"/>'
            f'<circle cx="{_f(cx+w*0.27)}" cy="{_f(by)}" r="{_f(wr)}" fill="#141b29" stroke="{BORDER}" stroke-width="1"/>'
            f'<circle cx="{_f(cx-w*0.27)}" cy="{_f(by)}" r="{_f(wr*0.45)}" fill="#44557a"/>'
            f'<circle cx="{_f(cx+w*0.27)}" cy="{_f(by)}" r="{_f(wr*0.45)}" fill="#44557a"/>'
            f'<path d="M {_f(bx)} {_f(by)} L {_f(bx)} {_f(lowT)} L {_f(bx+w*0.2)} {_f(roofT)} '
            f'L {_f(bx+w*0.78)} {_f(roofT)} L {_f(bx+w)} {_f(lowT)} L {_f(bx+w)} {_f(by)} Z" '
            f'fill="{c}" stroke="rgba(0,0,0,.18)" stroke-width="1"/>'
            f'<path d="M {_f(bx+w*0.25)} {_f(lowT)} L {_f(bx+w*0.34)} {_f(roofT+3)} L {_f(bx+w*0.47)} {_f(roofT+3)} L {_f(bx+w*0.47)} {_f(lowT)} Z" fill="#fff" opacity=".45"/>'
            f'<path d="M {_f(bx+w*0.53)} {_f(lowT)} L {_f(bx+w*0.53)} {_f(roofT+3)} L {_f(bx+w*0.66)} {_f(roofT+3)} L {_f(bx+w*0.75)} {_f(lowT)} Z" fill="#fff" opacity=".45"/>')
def _slot(p, cx, gY, w, above, asgn):
    a = asgn.get(p["Posição"]); wr=w*0.12; h=w*0.46; topY=gY-wr-h; s=""
    if a:
        s += _car(cx, gY, w, a["cor"])
        s += (f'<circle cx="{_f(cx+w*0.33)}" cy="{_f(topY+12)}" r="11" fill="{NAVY}" stroke="{CARD}" stroke-width="2"/>'
              f'<text x="{_f(cx+w*0.33)}" y="{_f(topY+16)}" text-anchor="middle" font-size="11" font-weight="800" fill="#fff">{a["ord"]}</text>')
    else:
        s += f'<rect x="{_f(cx-w/2)}" y="{_f(topY)}" width="{_f(w)}" height="{_f(gY-topY)}" rx="7" fill="none" stroke="{BORDER}" stroke-width="1.5" stroke-dasharray="5 4"/>'
    iy = 64 if above else 356; cyy = 82 if above else 374
    s += f'<text x="{_f(cx)}" y="{iy}" text-anchor="middle" font-size="11" font-weight="700" fill="{FG3}">{p["Posição"]}</text>'
    s += (f'<text x="{_f(cx)}" y="{cyy}" text-anchor="middle" font-size="11" font-weight="600" fill="{FG}">{a["cidade"]}</text>'
          if a else f'<text x="{_f(cx)}" y="{cyy}" text-anchor="middle" font-size="10" fill="{FG3}">vazio</text>')
    return s
def _centers(n, x0, x1):
    return [(x0 + x1) / 2] if n == 1 else [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]
def build_cegonha(asgn, positions):
    sup = [p for p in positions if p["Piso"] == "Superior"]
    inf = [p for p in positions if p["Piso"] == "Inferior"]
    supC = _centers(len(sup), 235, 830); infC = _centers(len(inf), 215, 860)
    truck = ""
    for p, cx in zip(sup, supC): truck += _slot(p, cx, 180, 126, True, asgn)
    for p, cx in zip(inf, infC): truck += _slot(p, cx, 322, 118, False, asgn)
    return f"""
<div style="background:#fff;border:1px solid {BORDER};border-radius:14px;padding:16px;overflow-x:auto;margin-bottom:4px;">
<svg viewBox="0 0 980 452" style="width:100%;min-width:620px;height:auto;display:block;font-family:sans-serif;">
  <line x1="20" y1="440" x2="962" y2="440" stroke="{BORDER}" stroke-width="2"/>
  <rect x="150" y="334" width="748" height="9" rx="3" fill="{FG2}"/>
  <rect x="160" y="324" width="712" height="7" rx="2" fill="{FG3}"/>
  <rect x="198" y="182" width="650" height="7" rx="2" fill="{FG3}"/>
  <rect x="200" y="182" width="6" height="150" fill="{FG3}"/>
  <rect x="842" y="182" width="6" height="150" fill="{FG3}"/>
  <rect x="520" y="189" width="5" height="135" fill="{FG3}" opacity=".5"/>
  <path d="M 872 331 L 928 408" stroke="{FG3}" stroke-width="7" stroke-linecap="round"/>
  <path d="M 40 334 L 40 238 Q 40 212 66 210 L 128 206 Q 150 206 158 234 L 168 300 L 168 334 Z" fill="{NAVY}" stroke="{BORDER}" stroke-width="1.5"/>
  <rect x="58" y="224" width="56" height="36" rx="4" fill="#9ec5ff" opacity=".85"/>
  <rect x="34" y="316" width="10" height="16" rx="2" fill="{FG3}"/>
  <circle cx="84" cy="406" r="30" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="84" cy="406" r="12" fill="#44557a"/>
  <circle cx="142" cy="406" r="30" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="142" cy="406" r="12" fill="#44557a"/>
  <circle cx="792" cy="406" r="30" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="792" cy="406" r="12" fill="#44557a"/>
  <circle cx="852" cy="406" r="30" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="852" cy="406" r="12" fill="#44557a"/>
  <text x="104" y="372" text-anchor="middle" font-size="10" font-weight="600" fill="{FG3}">Cabine</text>
  <text x="912" y="372" text-anchor="middle" font-size="10" font-weight="600" fill="{FG3}">Rampa</text>
  <text transform="translate(186,138) rotate(-90)" text-anchor="middle" font-size="9" font-weight="700" fill="{FG3}" letter-spacing="1">SUPERIOR</text>
  <text transform="translate(150,292) rotate(-90)" text-anchor="middle" font-size="9" font-weight="700" fill="{FG3}" letter-spacing="1">INFERIOR</text>
  <text x="40" y="26" font-size="13" font-weight="800" fill="{ACCENT}">AUTO<tspan fill="{NAVY}">PORT</tspan></text>
  {truck}
</svg></div>
"""

def sec_header(icon_name, titulo, sub=""):
    sub_html = f'<span class="sub">{sub}</span>' if sub else ""
    st.markdown(f'<div class="ri-h">{ic(icon_name,18,ACCENT)}<span>{titulo}</span>{sub_html}</div>',
                unsafe_allow_html=True)


# ============================================================================
# ENTRADA
# ============================================================================
with st.container(border=True):
    sec_header("nav", "Planejamento de rota")
    c1, c2 = st.columns(2)
    origem = c1.text_input("Origem", "Juiz de Fora/MG", help="Ponto de partida. Use Cidade/UF.")
    destino = c2.text_input("Destino final", "Juiz de Fora/MG", help="Onde a viagem termina. Use Cidade/UF.")
    st.markdown("**Paradas de entrega** — cidade e quantos carros descem em cada uma")
    paradas_df = st.data_editor(
        st.session_state.get("paradas_df", PARADAS_PADRAO), num_rows="dynamic",
        use_container_width=True, hide_index=True, key="editor_paradas",
        column_config={
            "Cidade": st.column_config.TextColumn("Cidade", help="Cidade/UF", width="large"),
            "Carros": st.column_config.NumberColumn("Carros", min_value=1, max_value=CAPACIDADE, step=1),
        })

# ----- ajustes avancados (gestor) -----
with st.expander("Ajustes avançados (gestor) — consumo e prioridades das posições"):
    st.markdown("**Consumo da cegonha** (usado para estimar combustível e escolher a ordem que gasta menos)")
    a1, a2, a3, a4 = st.columns(4)
    base_lpk = a1.number_input("Consumo vazio (L/km)", 0.1, 1.0, 0.33, 0.01,
                               help="Litros por km com a cegonha VAZIA.")
    extra_lpk_t = a2.number_input("Extra por tonelada (L/km·t)", 0.0, 0.05, 0.004, 0.001,
                                  help="Litros/km a mais por tonelada embarcada. É o 'custo do peso'.")
    peso_carro = a3.number_input("Peso médio/carro (t)", 0.5, 3.0, 1.3, 0.1,
                                 help="Converte carros em toneladas.")
    preco_diesel = a4.number_input("Diesel (R$/L)", 3.0, 12.0, 6.20, 0.10)

    st.divider()
    st.markdown("**Prioridade das posições** — em que ordem cada posição é descarregada")
    st.markdown('<div class="ri-info">Prioridade <b>1 = descarregada primeiro</b> '
                '(posição mais acessível, perto da rampa). <b>11 = descarregada por último</b>. '
                'A 1ª entrega da rota vai para a posição de prioridade 1, a 2ª para a prioridade 2, e assim por diante.</div>',
                unsafe_allow_html=True)
    pos_df = st.data_editor(
        st.session_state.get("pos_df", pd.DataFrame(POSICOES_PADRAO)),
        use_container_width=True, hide_index=True, key="editor_pos",
        column_config={
            "Posição": st.column_config.TextColumn("Posição", disabled=True),
            "Piso": st.column_config.SelectboxColumn("Piso", options=["Superior", "Inferior"]),
            "Prioridade": st.column_config.NumberColumn("Prioridade", min_value=1, max_value=CAPACIDADE, step=1,
                                                        help="1 = descarrega primeiro"),
        })
    if st.button("Restaurar padrão das posições"):
        st.session_state["pos_df"] = pd.DataFrame(POSICOES_PADRAO)
        st.rerun()
    st.session_state["pos_df"] = pos_df

calcular = st.button("Calcular rota e carga", type="primary", use_container_width=True)


# ============================================================================
# CALCULO (so no clique; salva em session_state p/ nao sumir no rerun do mapa)
# ============================================================================
if calcular:
    df = paradas_df.dropna(subset=["Cidade"])
    paradas = [{"cidade": str(r["Cidade"]).strip(), "qtd": int(r["Carros"])}
               for _, r in df.iterrows() if str(r["Cidade"]).strip()]
    total = sum(p["qtd"] for p in paradas)
    positions = pos_df.to_dict("records")

    if not paradas:
        st.warning("Adicione ao menos uma parada."); st.stop()
    if total > CAPACIDADE:
        st.error(f"Capacidade excedida: {total} carros para {CAPACIDADE} posições."); st.stop()
    if len(paradas) > 9:
        st.warning("Acima de 9 paradas a força bruta fica lenta — considere OR-Tools.")

    with st.spinner("Geocodificando e calculando rota real por estrada..."):
        nomes = [p["cidade"] for p in paradas]; qtds = [p["qtd"] for p in paradas]
        coord_o = geocode(origem); coord_d = geocode(destino)
        coord_p = [geocode(n) for n in nomes]
        if None in [coord_o, coord_d] or None in coord_p:
            st.error("Não consegui localizar algum endereço. Use o formato Cidade/UF."); st.stop()
        coords = [coord_o] + coord_p + [coord_d]; D = len(coords) - 1
        try:
            dmat = matriz_km(coords)
        except Exception as e:
            st.error(f"Erro ao calcular distâncias no OpenRouteService: {e}"); st.stop()
        qi = {j + 1: qtds[j] for j in range(len(qtds))}
        litros, km, ordem = otimizar(len(paradas), D, dmat, qi, base_lpk, extra_lpk_t, peso_carro)
        _, km_so, ordem_km = otimizar(len(paradas), D, dmat, qi, base_lpk, 0.0, peso_carro)
        ordem_nomes = [nomes[p - 1] for p in ordem]
        qpn = {nomes[j]: qtds[j] for j in range(len(nomes))}
        coords_ord = [coord_o] + [coord_p[p - 1] for p in ordem] + [coord_d]
        try:
            geo = geometria_rota(coords_ord)
        except Exception:
            geo = None
        carga = montar_carga(ordem_nomes, qpn, positions)
        segs = [origem] + ordem_nomes + ([destino] if destino.strip().lower() != ordem_nomes[-1].strip().lower() else [])
        maps_url = "https://www.google.com/maps/dir/" + "/".join(urllib.parse.quote(s) for s in segs)

    st.session_state["res"] = {
        "origem": origem, "destino": destino, "total": total, "km": km, "litros": litros,
        "custo": litros * preco_diesel, "reordenou": ordem != ordem_km, "km_so": km_so,
        "ordem": list(ordem), "nomes": nomes, "qtds": qtds,
        "coord_o": coord_o, "coord_d": coord_d, "coord_p": coord_p, "geo": geo,
        "carga": carga, "maps_url": maps_url, "positions": positions,
    }


# ============================================================================
# RESULTADO (renderiza do session_state; sobrevive aos reruns)
# ============================================================================
res = st.session_state.get("res")
if not res:
    st.info("Preencha o trajeto e clique em **Calcular rota e carga**.")
    st.stop()

origem, destino = res["origem"], res["destino"]
ordem, nomes, qtds = res["ordem"], res["nomes"], res["qtds"]
coord_o, coord_d, coord_p, geo = res["coord_o"], res["coord_d"], res["coord_p"], res["geo"]

# ----- métricas (com descrição) -----
def stat(icon_name, valor, rotulo, desc):
    return (f'<div class="ri-st"><div class="top">{ic(icon_name,15)}<span>{rotulo}</span></div>'
            f'<div class="v">{valor}</div><div class="d">{desc}</div></div>')
km_fmt = f'{res["km"]:,.0f}'.replace(",", "."); lit_fmt = f'{res["litros"]:,.0f}'.replace(",", ".")
cst_fmt = f'{res["custo"]:,.0f}'.replace(",", ".")
st.markdown('<div class="ri-stats">'
            + stat("truck", res["total"], "Carros", "total de veículos na cegonha")
            + stat("road", f"{km_fmt} km", "Distância", "percurso real por estrada, origem→destino")
            + stat("fuel", f"{lit_fmt} L", "Combustível", "litros estimados para esta rota")
            + stat("dollar", f"R$ {cst_fmt}", "Custo diesel", "litros × preço do diesel")
            + '</div>', unsafe_allow_html=True)

if res["reordenou"]:
    st.success(f'Ordem otimizada por combustível (menor distância pura seria {res["km_so"]:,.0f} km).'.replace(",", "."))

with st.expander("Como interpretar estes números"):
    st.markdown(
        "- **Carros**: total de veículos embarcados nesta viagem (máx. 11).\n"
        "- **Distância**: quilômetros reais por estrada somando origem → todas as paradas → destino.\n"
        "- **Combustível**: litros estimados, considerando que a cegonha gasta mais quando está mais pesada.\n"
        "- **Custo diesel**: o combustível acima multiplicado pelo preço por litro.\n\n"
        "A **ordem das entregas** é escolhida para gastar o mínimo de combustível — por isso às vezes "
        "vale descarregar cedo uma parada próxima, para rodar mais leve nos trechos longos.")

# ----- fluxo da rota -----
with st.container(border=True):
    sec_header("nav", "Rota", "sequência de entrega")
    def circ(cor, dentro): return f'<div class="ri-circ" style="background:{cor}">{dentro}</div>'
    pin = ic("pin", 16, "#fff")
    flow = f'<div class="ri-node">{circ(NAVY, pin)}<div class="ri-lbl">{origem.split("/")[0]}</div><div class="ri-sub">Partida</div></div>'
    for i, p in enumerate(ordem):
        flow += '<div class="ri-arrow"></div>'
        flow += (f'<div class="ri-node">{circ(COLORS[i % 8], qtds[p-1])}'
                 f'<div class="ri-lbl">{nomes[p-1].split("/")[0]}</div>'
                 f'<div class="ri-sub">{i+1}ª · {qtds[p-1]} veíc.</div></div>')
    flow += '<div class="ri-arrow"></div>'
    flow += f'<div class="ri-node">{circ(NAVY, pin)}<div class="ri-lbl">{destino.split("/")[0]}</div><div class="ri-sub">Destino</div></div>'
    st.markdown(f'<div class="ri-flow">{flow}</div>', unsafe_allow_html=True)

# ----- mapa real -----
with st.container(border=True):
    sec_header("map", "Mapa do trajeto", "OpenStreetMap")
    try:
        fmap = folium.Map(location=[coord_o[1], coord_o[0]], zoom_start=6, tiles="OpenStreetMap")
        if geo:
            folium.GeoJson(geo, style_function=lambda x: {"color": ACCENT, "weight": 4}).add_to(fmap)
        folium.Marker([coord_o[1], coord_o[0]], tooltip=f"Origem: {origem}",
                      icon=folium.Icon(color="darkblue", icon="home", prefix="fa")).add_to(fmap)
        for i, p in enumerate(ordem):
            c = coord_p[p - 1]
            folium.Marker([c[1], c[0]], tooltip=f"{i+1}ª · {nomes[p-1]} ({qtds[p-1]} carros)",
                          icon=folium.DivIcon(html=f'<div style="background:{ACCENT};color:#fff;border-radius:50%;'
                                                   f'width:26px;height:26px;display:flex;align-items:center;'
                                                   f'justify-content:center;font-weight:700;font-size:12px;'
                                                   f'border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.3)">{i+1}</div>')).add_to(fmap)
        folium.Marker([coord_d[1], coord_d[0]], tooltip=f"Destino: {destino}",
                      icon=folium.Icon(color="darkblue", icon="flag-checkered", prefix="fa")).add_to(fmap)
        st_folium(fmap, height=430, use_container_width=True, returned_objects=[])
    except Exception as e:
        st.warning(f"Não foi possível desenhar o mapa agora ({e}). "
                   "A rota e a ordem foram calculadas normalmente — use o botão do Google Maps abaixo.")

# ----- cegonha -----
with st.container(border=True):
    sec_header("layers", "Cegonha", "vista lateral · nº = ordem de descarga")
    asgn = {r["pos"]: {"cidade": r["entrega"].split("/")[0], "ord": r["ordem_descarga"],
                       "cor": COLORS[(r["ordem_entrega"] - 1) % 8]} for r in res["carga"]}
    st.markdown(build_cegonha(asgn, res["positions"]), unsafe_allow_html=True)

# ----- matriz de carga -----
with st.container(border=True):
    sec_header("list", "Matriz de carga", "posição · piso · entrega · ordem")
    tabela = [{"Posição": r["pos"], "Piso": r["piso"], "Entrega": r["entrega"],
               "Ordem entrega": r["ordem_entrega"], "Ordem descarga": r["ordem_descarga"]} for r in res["carga"]]
    st.dataframe(tabela, use_container_width=True, hide_index=True)

st.link_button("Abrir no Google Maps", res["maps_url"], use_container_width=True)
