


import itertools
import streamlit as st
import openrouteservice as ors
import folium
from streamlit_folium import st_folium

# ----------------------------------------------------------------------------
# Paleta AUTOPORT + cores por entrega
# ----------------------------------------------------------------------------
NAVY = "#0C1B2E"; ACCENT = "#C8102E"; FG = "#0F1A2E"; FG2 = "#4B5C72"
FG3 = "#8896A8"; BORDER = "#E2E6ED"; CARD = "#FFFFFF"; CARD_ALT = "#F8FAFC"
COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444", "#06B6D4", "#6366F1", "#EC4899"]

# ----------------------------------------------------------------------------
# Configuracao da cegonha (11 posicoes, 2 pisos)
# prioridade 1 = desembarca primeiro (mais acessivel, perto da rampa)
# ----------------------------------------------------------------------------
POSICOES = [
    {"nome": "S1", "piso": "Superior", "prioridade": 11},
    {"nome": "S2", "piso": "Superior", "prioridade": 9},
    {"nome": "S3", "piso": "Superior", "prioridade": 7},
    {"nome": "S4", "piso": "Superior", "prioridade": 4},
    {"nome": "S5", "piso": "Superior", "prioridade": 2},
    {"nome": "I1", "piso": "Inferior", "prioridade": 10},
    {"nome": "I2", "piso": "Inferior", "prioridade": 8},
    {"nome": "I3", "piso": "Inferior", "prioridade": 6},
    {"nome": "I4", "piso": "Inferior", "prioridade": 5},
    {"nome": "I5", "piso": "Inferior", "prioridade": 3},
    {"nome": "I6", "piso": "Inferior", "prioridade": 1},
]
CAPACIDADE = len(POSICOES)

st.set_page_config(page_title="Rota Inteligente", page_icon="🚛", layout="wide")

# ----------------------------------------------------------------------------
# CSS (visual AUTOPORT)
# ----------------------------------------------------------------------------
st.markdown("""
<style>
#MainMenu, footer {visibility:hidden;}
.block-container {padding-top:1rem; max-width:1100px;}
.ri-header{background:#0C1B2E;border-radius:12px;padding:14px 20px;display:flex;
  align-items:center;gap:12px;margin-bottom:18px;}
.ri-mark{width:34px;height:34px;background:#C8102E;border-radius:8px;display:flex;
  align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:13px;}
.ri-title{font-size:20px;font-weight:800;color:#fff;letter-spacing:-.3px;}
.ri-title b{color:#C8102E;}
.ri-tag{margin-left:auto;font-size:11px;font-weight:700;color:rgba(255,255,255,.45);
  letter-spacing:2px;text-transform:uppercase;}
.ri-card{background:#fff;border:1px solid #E2E6ED;border-radius:12px;padding:18px 20px;
  box-shadow:0 1px 3px rgba(12,27,46,.05);margin-bottom:16px;}
.ri-card h3{font-size:14px;font-weight:700;color:#0F1A2E;margin:0 0 12px;}
.ri-stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;}
.ri-st{flex:1;min-width:120px;background:#fff;border:1px solid #E2E6ED;border-radius:12px;
  padding:14px 16px;box-shadow:0 1px 3px rgba(12,27,46,.05);}
.ri-st .v{font-size:26px;font-weight:800;color:#0F1A2E;letter-spacing:-.5px;}
.ri-st .l{font-size:11px;font-weight:600;color:#8896A8;text-transform:uppercase;letter-spacing:.4px;}
.ri-flow{display:flex;align-items:flex-start;gap:4px;overflow-x:auto;padding:6px 0;}
.ri-node{display:flex;flex-direction:column;align-items:center;gap:5px;min-width:78px;flex-shrink:0;}
.ri-circ{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-weight:800;color:#fff;font-size:13px;}
.ri-lbl{font-size:11px;font-weight:600;color:#4B5C72;text-align:center;line-height:1.2;}
.ri-sub{font-size:10px;color:#8896A8;font-weight:500;}
.ri-arrow{flex:1;min-width:20px;height:2px;background:#E2E6ED;margin-top:17px;}
div[data-testid="stMetricValue"]{font-size:24px;}
.stButton>button{font-weight:700;border-radius:8px;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="ri-header">
  <div class="ri-mark">AP</div>
  <div class="ri-title">Rota <b>Inteligente</b></div>
  <div class="ri-tag">Autoport</div>
</div>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Cliente ORS
# ----------------------------------------------------------------------------
def get_client():
    key = st.secrets.get("ORS_API_KEY", "")
    if not key:
        st.error("Falta a chave do OpenRouteService. No Streamlit Cloud: Manage app → "
                 'Settings → Secrets → ORS_API_KEY = "sua_chave". Local: .streamlit/secrets.toml.')
        st.stop()
    return ors.Client(key=key)


@st.cache_data(show_spinner=False)
def geocode(texto):
    cli = get_client()
    r = cli.pelias_search(text=texto, country="BRA", size=1)
    feats = r.get("features", [])
    if not feats:
        return None
    lon, lat = feats[0]["geometry"]["coordinates"]
    return (lon, lat)


@st.cache_data(show_spinner=False)
def matriz_km(coords):
    cli = get_client()
    r = cli.distance_matrix(locations=coords, profile="driving-hgv",
                            metrics=["distance"], units="km")
    return r["distances"]


@st.cache_data(show_spinner=False)
def geometria_rota(coords_ordenadas):
    cli = get_client()
    return cli.directions(coordinates=coords_ordenadas, profile="driving-hgv", format="geojson")


# ----------------------------------------------------------------------------
# Otimizacao por combustivel
# ----------------------------------------------------------------------------
def custo_combustivel(ordem, D, dmat, qtds, base_lpk, extra_lpk_t, peso_carro):
    litros = 0.0; km = 0.0; atual = 0
    carros = sum(qtds[i] for i in ordem)
    for p in ordem:
        d = dmat[atual][p]
        litros += d * (base_lpk + extra_lpk_t * carros * peso_carro)
        km += d
        carros -= qtds[p]
        atual = p
    d = dmat[atual][D]
    litros += d * base_lpk
    km += d
    return litros, km


def otimizar(n_paradas, D, dmat, qtds, base_lpk, extra_lpk_t, peso_carro):
    melhor = None
    for perm in itertools.permutations(range(1, 1 + n_paradas)):
        litros, km = custo_combustivel(perm, D, dmat, qtds, base_lpk, extra_lpk_t, peso_carro)
        if melhor is None or litros < melhor[0]:
            melhor = (litros, km, perm)
    return melhor


# ----------------------------------------------------------------------------
# LIFO
# ----------------------------------------------------------------------------
def montar_carga(ordem_nomes, qtds_por_nome):
    posicoes = sorted(POSICOES, key=lambda p: p["prioridade"])
    atrib = []; i = 0
    for ordem_idx, nome in enumerate(ordem_nomes, start=1):
        for _ in range(qtds_por_nome[nome]):
            if i < len(posicoes):
                atrib.append({"pos": posicoes[i]["nome"], "piso": posicoes[i]["piso"],
                              "entrega": nome, "ordem_entrega": ordem_idx, "ordem_descarga": i + 1})
                i += 1
    return atrib


# ----------------------------------------------------------------------------
# Desenho da cegonha (SVG) - vista lateral, visual AUTOPORT
# ----------------------------------------------------------------------------
def _f(n): return f"{n:.1f}"

def _car(cx, gY, w, c):
    wr = w * 0.12; h = w * 0.46; bx = cx - w / 2; by = gY - wr; lowT = by - h * 0.5; roofT = by - h
    return (
        f'<circle cx="{_f(cx-w*0.27)}" cy="{_f(by)}" r="{_f(wr)}" fill="#141b29" stroke="{BORDER}" stroke-width="1"/>'
        f'<circle cx="{_f(cx+w*0.27)}" cy="{_f(by)}" r="{_f(wr)}" fill="#141b29" stroke="{BORDER}" stroke-width="1"/>'
        f'<circle cx="{_f(cx-w*0.27)}" cy="{_f(by)}" r="{_f(wr*0.45)}" fill="#44557a"/>'
        f'<circle cx="{_f(cx+w*0.27)}" cy="{_f(by)}" r="{_f(wr*0.45)}" fill="#44557a"/>'
        f'<path d="M {_f(bx)} {_f(by)} L {_f(bx)} {_f(lowT)} L {_f(bx+w*0.2)} {_f(roofT)} '
        f'L {_f(bx+w*0.78)} {_f(roofT)} L {_f(bx+w)} {_f(lowT)} L {_f(bx+w)} {_f(by)} Z" '
        f'fill="{c}" stroke="rgba(0,0,0,.18)" stroke-width="1"/>'
        f'<path d="M {_f(bx+w*0.25)} {_f(lowT)} L {_f(bx+w*0.34)} {_f(roofT+3)} L {_f(bx+w*0.47)} {_f(roofT+3)} L {_f(bx+w*0.47)} {_f(lowT)} Z" fill="#fff" opacity=".45"/>'
        f'<path d="M {_f(bx+w*0.53)} {_f(lowT)} L {_f(bx+w*0.53)} {_f(roofT+3)} L {_f(bx+w*0.66)} {_f(roofT+3)} L {_f(bx+w*0.75)} {_f(lowT)} Z" fill="#fff" opacity=".45"/>'
    )

def _slot(p, cx, gY, w, above, asgn):
    a = asgn.get(p["nome"])
    wr = w * 0.12; h = w * 0.46; topY = gY - wr - h
    s = ""
    if a:
        s += _car(cx, gY, w, a["cor"])
        s += (f'<circle cx="{_f(cx+w*0.33)}" cy="{_f(topY+12)}" r="11" fill="{NAVY}" stroke="{CARD}" stroke-width="2"/>'
              f'<text x="{_f(cx+w*0.33)}" y="{_f(topY+16)}" text-anchor="middle" font-size="11" font-weight="800" fill="#fff">{a["ord"]}</text>')
    else:
        s += f'<rect x="{_f(cx-w/2)}" y="{_f(topY)}" width="{_f(w)}" height="{_f(gY-topY)}" rx="7" fill="none" stroke="{BORDER}" stroke-width="1.5" stroke-dasharray="5 4"/>'
    iy = 64 if above else 356
    cyy = 82 if above else 374
    s += f'<text x="{_f(cx)}" y="{iy}" text-anchor="middle" font-size="11" font-weight="700" fill="{FG3}">{p["nome"]}</text>'
    if a:
        s += f'<text x="{_f(cx)}" y="{cyy}" text-anchor="middle" font-size="11" font-weight="600" fill="{FG}">{a["cidade"]}</text>'
    else:
        s += f'<text x="{_f(cx)}" y="{cyy}" text-anchor="middle" font-size="10" fill="{FG3}">vazio</text>'
    return s

def _centers(n, x0, x1):
    if n == 1:
        return [(x0 + x1) / 2]
    return [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]

def build_cegonha(asgn):
    sup = [p for p in POSICOES if p["piso"] == "Superior"]
    inf = [p for p in POSICOES if p["piso"] == "Inferior"]
    supC = _centers(len(sup), 235, 830)
    infC = _centers(len(inf), 215, 860)
    truck = ""
    for p, cx in zip(sup, supC):
        truck += _slot(p, cx, 180, 126, True, asgn)
    for p, cx in zip(inf, infC):
        truck += _slot(p, cx, 322, 118, False, asgn)
    return f"""
<div style="background:#fff;border:1px solid {BORDER};border-radius:12px;padding:16px;overflow-x:auto;">
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


# ============================================================================
# UI
# ============================================================================
with st.sidebar:
    st.header("Parâmetros de consumo")
    base_lpk = st.number_input("Consumo base (vazio), L/km", 0.1, 1.0, 0.33, 0.01)
    extra_lpk_t = st.number_input("Extra por tonelada, L/km·t", 0.0, 0.05, 0.004, 0.001,
                                  help="Litros/km a mais por tonelada embarcada.")
    peso_carro = st.number_input("Peso médio por carro (t)", 0.5, 3.0, 1.3, 0.1)
    st.divider()
    preco_diesel = st.number_input("Preço do diesel (R$/L)", 3.0, 12.0, 6.20, 0.10)

st.markdown('<div class="ri-card"><h3>Planejamento de rota</h3>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
origem = c1.text_input("Origem", "Juiz de Fora/MG")
destino = c2.text_input("Destino final", "Juiz de Fora/MG")

st.markdown("**Paradas de entrega**")
if "paradas" not in st.session_state:
    st.session_state.paradas = [
        {"cidade": "Cariacica/ES", "qtd": 1},
        {"cidade": "Governador Valadares/MG", "qtd": 3},
        {"cidade": "Coronel Pacheco/MG", "qtd": 1},
    ]
for i, p in enumerate(st.session_state.paradas):
    a, b, d = st.columns([4, 1, 0.6])
    p["cidade"] = a.text_input("Cidade", p["cidade"], key=f"c{i}", label_visibility="collapsed",
                               placeholder="Cidade/UF")
    p["qtd"] = b.number_input("Qtd", 1, CAPACIDADE, p["qtd"], key=f"q{i}", label_visibility="collapsed")
    if d.button("✕", key=f"x{i}") and len(st.session_state.paradas) > 1:
        st.session_state.paradas.pop(i); st.rerun()
cc1, cc2 = st.columns([1, 3])
if cc1.button("➕ Adicionar parada"):
    st.session_state.paradas.append({"cidade": "", "qtd": 1}); st.rerun()
calcular = cc2.button("Calcular rota e carga", type="primary", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

if calcular:
    paradas = [p for p in st.session_state.paradas if p["cidade"].strip()]
    total = sum(p["qtd"] for p in paradas)
    if not paradas:
        st.warning("Adicione ao menos uma parada."); st.stop()
    if total > CAPACIDADE:
        st.error(f"Capacidade excedida: {total} carros para {CAPACIDADE} posições."); st.stop()
    if len(paradas) > 9:
        st.warning("Acima de 9 paradas a força bruta fica lenta — considere OR-Tools.")

    with st.spinner("Geocodificando e calculando rota real por estrada..."):
        nomes = [p["cidade"] for p in paradas]
        qtds = [p["qtd"] for p in paradas]
        coord_o = geocode(origem); coord_d = geocode(destino)
        coord_p = [geocode(n) for n in nomes]
        if None in [coord_o, coord_d] or None in coord_p:
            st.error("Não consegui geocodificar algum endereço. Use o formato Cidade/UF."); st.stop()
        coords = [coord_o] + coord_p + [coord_d]
        D = len(coords) - 1
        dmat = matriz_km(coords)
        qtds_idx = {j + 1: qtds[j] for j in range(len(qtds))}
        litros, km, ordem = otimizar(len(paradas), D, dmat, qtds_idx, base_lpk, extra_lpk_t, peso_carro)
        _, km_so, ordem_km = otimizar(len(paradas), D, dmat, qtds_idx, base_lpk, 0.0, peso_carro)
        ordem_nomes = [nomes[p - 1] for p in ordem]
        qtds_por_nome = {nomes[j]: qtds[j] for j in range(len(nomes))}
        coords_ord = [coord_o] + [coord_p[p - 1] for p in ordem] + [coord_d]
        try:
            geo = geometria_rota(coords_ord)
        except Exception as e:
            geo = None
            st.info(f"Rota calculada, mas não consegui desenhar a geometria: {e}")

    # ----- métricas -----
    custo = litros * preco_diesel
    st.markdown(f"""
    <div class="ri-stats">
      <div class="ri-st"><div class="v">{total}</div><div class="l">Carros</div></div>
      <div class="ri-st"><div class="v">{km:,.0f} km</div><div class="l">Distância (estrada)</div></div>
      <div class="ri-st"><div class="v">{litros:,.0f} L</div><div class="l">Combustível</div></div>
      <div class="ri-st"><div class="v">R$ {custo:,.0f}</div><div class="l">Custo diesel</div></div>
    </div>
    """.replace(",", "."), unsafe_allow_html=True)

    if ordem != ordem_km:
        st.success(f"Ordem por combustível otimizada (vs. {km_so:,.0f} km da menor distância pura).".replace(",", "."))

    # ----- fluxo da rota -----
    def circ(color, inner):
        return f'<div class="ri-circ" style="background:{color}">{inner}</div>'
    flow = f'<div class="ri-node">{circ(NAVY,"●")}<div class="ri-lbl">{origem.split("/")[0]}</div><div class="ri-sub">Partida</div></div>'
    for i, p in enumerate(ordem):
        cor = COLORS[i % 8]
        flow += '<div class="ri-arrow"></div>'
        flow += (f'<div class="ri-node">{circ(cor, qtds[p-1])}'
                 f'<div class="ri-lbl">{nomes[p-1].split("/")[0]}</div>'
                 f'<div class="ri-sub">{i+1}ª · {qtds[p-1]} veíc.</div></div>')
    flow += '<div class="ri-arrow"></div>'
    flow += f'<div class="ri-node">{circ(NAVY,"●")}<div class="ri-lbl">{destino.split("/")[0]}</div><div class="ri-sub">Destino</div></div>'
    st.markdown(f'<div class="ri-card"><h3>Rota</h3><div class="ri-flow">{flow}</div></div>', unsafe_allow_html=True)

    # ----- mapa real -----
    st.markdown('<div class="ri-card"><h3>Mapa do trajeto</h3>', unsafe_allow_html=True)
    fmap = folium.Map(location=[coord_o[1], coord_o[0]], zoom_start=6, tiles="cartodbpositron")
    if geo:
        folium.GeoJson(geo, style_function=lambda x: {"color": ACCENT, "weight": 4}).add_to(fmap)
    folium.Marker([coord_o[1], coord_o[0]], tooltip=f"Origem: {origem}",
                  icon=folium.Icon(color="darkblue", icon="play")).add_to(fmap)
    for i, p in enumerate(ordem):
        c = coord_p[p - 1]
        folium.Marker([c[1], c[0]], tooltip=f"{i+1}ª · {nomes[p-1]} ({qtds[p-1]} carros)",
                      icon=folium.DivIcon(html=f'<div style="background:{ACCENT};color:#fff;border-radius:50%;'
                                               f'width:24px;height:24px;display:flex;align-items:center;'
                                               f'justify-content:center;font-weight:700;font-size:12px">{i+1}</div>')).add_to(fmap)
    folium.Marker([coord_d[1], coord_d[0]], tooltip=f"Destino: {destino}",
                  icon=folium.Icon(color="darkblue", icon="flag")).add_to(fmap)
    st_folium(fmap, height=420, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ----- cegonha (desenho) -----
    carga = montar_carga(ordem_nomes, qtds_por_nome)
    asgn = {}
    for row in carga:
        asgn[row["pos"]] = {"cidade": row["entrega"].split("/")[0], "ord": row["ordem_descarga"],
                            "cor": COLORS[(row["ordem_entrega"] - 1) % 8]}
    st.markdown('<div class="ri-card"><h3>Cegonha &nbsp;<span style="font-weight:500;color:#8896A8;font-size:11px">vista lateral · nº = ordem de descarga</span></h3>', unsafe_allow_html=True)
    st.markdown(build_cegonha(asgn), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ----- matriz de carga -----
    st.markdown('<div class="ri-card"><h3>Matriz de carga</h3>', unsafe_allow_html=True)
    tabela = [{"Posição": r["pos"], "Piso": r["piso"], "Entrega": r["entrega"],
               "Ordem entrega": r["ordem_entrega"], "Ordem descarga": r["ordem_descarga"]} for r in carga]
    st.dataframe(tabela, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ----- Google Maps -----
    segs = [origem] + ordem_nomes + ([destino] if destino.strip().lower() != ordem_nomes[-1].strip().lower() else [])
    import urllib.parse
    url = "https://www.google.com/maps/dir/" + "/".join(urllib.parse.quote(s) for s in segs)
    st.link_button("Abrir no Google Maps", url)
else:
    st.info("Preencha o trajeto e clique em **Calcular rota e carga**.")
