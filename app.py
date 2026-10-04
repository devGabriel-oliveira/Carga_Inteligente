# -*- coding: utf-8 -*-
"""
Rota Inteligente - ATL / Autoport (Streamlit)
=============================================
Planeja a rota da cegonha e a montagem de carga (LIFO), usando:
  - OpenRouteService (ORS): geocodificacao, matriz de distancia REAL por estrada
    e geometria do trajeto (perfil de caminhao: driving-hgv).
  - Otimizacao da ordem das entregas minimizando COMBUSTIVEL (nao so km):
        combustivel = base_L/km * km  +  extra_L/km_por_t * (peso a bordo) * km
    -> isso premia soltar carga pesada cedo (deixa a cegonha leve nos trechos longos).
  - Mapa real (folium) com o trajeto desenhado.

Como rodar:
  1) pip install -r requirements.txt
  2) crie .streamlit/secrets.toml com:  ORS_API_KEY = "sua_chave"
     (chave gratuita em https://openrouteservice.org/dev/#/signup)
  3) streamlit run app.py
"""

import itertools
import streamlit as st
import openrouteservice as ors
import folium
from streamlit_folium import st_folium

# ----------------------------------------------------------------------------
# Configuracao da cegonha (11 posicoes, 2 pisos) - mesma logica do app web
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
# Cliente ORS (chave em st.secrets)
# ----------------------------------------------------------------------------
def get_client():
    key = st.secrets.get("ORS_API_KEY", "")
    if not key:
        st.error("Falta a chave do OpenRouteService. Crie .streamlit/secrets.toml "
                 'com  ORS_API_KEY = "sua_chave"  (gratis em openrouteservice.org).')
        st.stop()
    return ors.Client(key=key)


@st.cache_data(show_spinner=False)
def geocode(texto: str):
    """Endereco/cidade -> (lon, lat). Cacheado para nao gastar chamadas repetidas."""
    cli = get_client()
    r = cli.pelias_search(text=texto, country="BRA", size=1)
    feats = r.get("features", [])
    if not feats:
        return None
    lon, lat = feats[0]["geometry"]["coordinates"]
    return (lon, lat)


@st.cache_data(show_spinner=False)
def matriz_km(coords):
    """Matriz de distancia REAL por estrada (km) entre todos os pontos. Perfil caminhao."""
    cli = get_client()
    r = cli.distance_matrix(
        locations=coords,
        profile="driving-hgv",
        metrics=["distance"],
        units="km",
    )
    return r["distances"]  # matriz NxN em km


@st.cache_data(show_spinner=False)
def geometria_rota(coords_ordenadas):
    """Geometria (GeoJSON) do trajeto por estrada passando pelos pontos na ordem dada."""
    cli = get_client()
    r = cli.directions(
        coordinates=coords_ordenadas,
        profile="driving-hgv",
        format="geojson",
    )
    return r


# ----------------------------------------------------------------------------
# Otimizacao: melhor ordem das entregas minimizando combustivel
# ----------------------------------------------------------------------------
def custo_combustivel(ordem, D, dmat, qtds, base_lpk, extra_lpk_t, peso_carro):
    """
    ordem: tupla de indices das paradas (1..n) na sequencia de visita
    D: indice do destino final na matriz
    dmat: matriz de km
    qtds: qtd de carros por indice de parada
    Retorna (litros, km_total).
    No 0 = origem.
    """
    litros = 0.0
    km = 0.0
    atual = 0  # origem
    carros_a_bordo = sum(qtds[i] for i in ordem)
    for p in ordem:
        d = dmat[atual][p]
        peso_t = carros_a_bordo * peso_carro
        litros += d * (base_lpk + extra_lpk_t * peso_t)
        km += d
        carros_a_bordo -= qtds[p]  # entrega nessa parada -> fica mais leve
        atual = p
    # trecho final ate o destino (cegonha ja vazia)
    d = dmat[atual][D]
    litros += d * base_lpk
    km += d
    return litros, km


def otimizar(n_paradas, D, dmat, qtds, base_lpk, extra_lpk_t, peso_carro):
    """Forca bruta (exato) para ate ~9 paradas. Retorna melhor ordem por combustivel."""
    idx_paradas = list(range(1, 1 + n_paradas))
    melhor = None
    for perm in itertools.permutations(idx_paradas):
        litros, km = custo_combustivel(perm, D, dmat, qtds, base_lpk, extra_lpk_t, peso_carro)
        if melhor is None or litros < melhor[0]:
            melhor = (litros, km, perm)
    return melhor  # (litros, km, ordem)


# ----------------------------------------------------------------------------
# LIFO: distribui carros nas posicoes conforme a ordem de entrega
# ----------------------------------------------------------------------------
def montar_carga(ordem_paradas_nomes, qtds_por_nome):
    posicoes = sorted(POSICOES, key=lambda p: p["prioridade"])
    atribuicoes = []
    i = 0
    for ordem_idx, nome in enumerate(ordem_paradas_nomes, start=1):
        for _ in range(qtds_por_nome[nome]):
            if i < len(posicoes):
                atribuicoes.append({
                    "Posição": posicoes[i]["nome"],
                    "Piso": posicoes[i]["piso"],
                    "Entrega": nome,
                    "Ordem entrega": ordem_idx,
                    "Ordem descarga": i + 1,
                })
                i += 1
    return atribuicoes


# ============================================================================
# UI
# ============================================================================
st.title("🚛 Rota Inteligente — ATL / Autoport")
st.caption("Rota por estrada + montagem de carga LIFO, otimizada por combustível.")

with st.sidebar:
    st.header("⚙️ Parâmetros de consumo")
    base_lpk = st.number_input("Consumo base (vazio), L/km", 0.1, 1.0, 0.33, 0.01)
    extra_lpk_t = st.number_input("Extra por tonelada, L/km·t", 0.0, 0.05, 0.004, 0.001,
                                  help="Quanto a mais o caminhao gasta por tonelada embarcada.")
    peso_carro = st.number_input("Peso médio por carro (t)", 0.5, 3.0, 1.3, 0.1)
    st.divider()
    preco_diesel = st.number_input("Preço do diesel (R$/L)", 3.0, 12.0, 6.20, 0.10)

col_in, col_out = st.columns([1, 1.3])

with col_in:
    st.subheader("Trajeto")
    origem = st.text_input("Origem", "Juiz de Fora/MG")
    destino = st.text_input("Destino final", "Juiz de Fora/MG")

    st.markdown("**Paradas de entrega**")
    if "paradas" not in st.session_state:
        st.session_state.paradas = [
            {"cidade": "Cariacica/ES", "qtd": 1},
            {"cidade": "Governador Valadares/MG", "qtd": 3},
            {"cidade": "Coronel Pacheco/MG", "qtd": 1},
        ]
    for i, p in enumerate(st.session_state.paradas):
        c1, c2, c3 = st.columns([3, 1, 0.5])
        p["cidade"] = c1.text_input("Cidade", p["cidade"], key=f"c{i}", label_visibility="collapsed")
        p["qtd"] = c2.number_input("Qtd", 1, CAPACIDADE, p["qtd"], key=f"q{i}", label_visibility="collapsed")
        if c3.button("✕", key=f"x{i}") and len(st.session_state.paradas) > 1:
            st.session_state.paradas.pop(i)
            st.rerun()
    if st.button("➕ Adicionar parada"):
        st.session_state.paradas.append({"cidade": "", "qtd": 1})
        st.rerun()

    calcular = st.button("Calcular rota e carga", type="primary", use_container_width=True)

with col_out:
    if calcular:
        paradas = [p for p in st.session_state.paradas if p["cidade"].strip()]
        total = sum(p["qtd"] for p in paradas)
        if not paradas:
            st.warning("Adicione ao menos uma parada.")
            st.stop()
        if total > CAPACIDADE:
            st.error(f"Capacidade excedida: {total} carros para {CAPACIDADE} posições.")
            st.stop()
        if len(paradas) > 9:
            st.warning("Acima de 9 paradas a força bruta fica lenta — considere OR-Tools.")

        with st.spinner("Geocodificando e calculando rota real..."):
            # pontos: 0 = origem, 1..n = paradas, ultimo = destino
            nomes = [p["cidade"] for p in paradas]
            qtds = [p["qtd"] for p in paradas]
            coord_origem = geocode(origem)
            coord_dest = geocode(destino)
            coord_paradas = [geocode(n) for n in nomes]

            if None in [coord_origem, coord_dest] or None in coord_paradas:
                st.error("Não consegui geocodificar algum endereço. Revise os nomes (use Cidade/UF).")
                st.stop()

            coords = [coord_origem] + coord_paradas + [coord_dest]
            D = len(coords) - 1
            dmat = matriz_km(coords)

            # indice de qtd alinhado com a matriz (parada j -> indice j na matriz = j)
            qtds_idx = {j + 1: qtds[j] for j in range(len(qtds))}

            litros, km, ordem = otimizar(
                len(paradas), D, dmat, qtds_idx, base_lpk, extra_lpk_t, peso_carro
            )
            # comparacao: ordem so por km (sem peso)
            _, km_so, ordem_km = otimizar(
                len(paradas), D, dmat, qtds_idx, base_lpk, 0.0, peso_carro
            )

            ordem_nomes = [nomes[p - 1] for p in ordem]
            qtds_por_nome = {nomes[j]: qtds[j] for j in range(len(nomes))}

            # geometria para o mapa (origem -> paradas na ordem -> destino)
            coords_ord = [coord_origem] + [coord_paradas[p - 1] for p in ordem] + [coord_dest]
            try:
                geo = geometria_rota(coords_ord)
            except Exception as e:
                geo = None
                st.info(f"Trajeto calculado, mas não consegui desenhar a geometria: {e}")

        # ---- metricas ----
        custo = litros * preco_diesel
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Carros", total)
        m2.metric("Distância (estrada)", f"{km:,.0f} km")
        m3.metric("Combustível", f"{litros:,.0f} L")
        m4.metric("Custo diesel", f"R$ {custo:,.0f}")

        if ordem != ordem_km:
            st.success(f"Ordem por **combustível** economiza carga×km vs. ordem só por distância "
                       f"({km:,.0f} km vs {km_so:,.0f} km de menor distância pura).")

        # ---- ordem ----
        st.markdown("**Sequência de entrega (otimizada por combustível):**")
        seq = " → ".join([f"{origem.split('/')[0]}"] +
                         [f"{i+1}. {n.split('/')[0]} ({qtds_por_nome[n]})" for i, n in enumerate(ordem_nomes)] +
                         [f"{destino.split('/')[0]} (destino)"])
        st.write(seq)

        # ---- mapa ----
        centro = [coord_origem[1], coord_origem[0]]
        fmap = folium.Map(location=centro, zoom_start=6, tiles="cartodbpositron")
        if geo:
            folium.GeoJson(geo, style_function=lambda x: {"color": "#C8102E", "weight": 4}).add_to(fmap)
        folium.Marker([coord_origem[1], coord_origem[0]], tooltip=f"Origem: {origem}",
                      icon=folium.Icon(color="darkblue", icon="play")).add_to(fmap)
        for i, p in enumerate(ordem):
            c = coord_paradas[p - 1]
            folium.Marker([c[1], c[0]], tooltip=f"{i+1}ª · {nomes[p-1]} ({qtds[p-1]} carros)",
                          icon=folium.DivIcon(html=f'<div style="background:#C8102E;color:#fff;'
                                                   f'border-radius:50%;width:24px;height:24px;'
                                                   f'display:flex;align-items:center;justify-content:center;'
                                                   f'font-weight:700;font-size:12px">{i+1}</div>')).add_to(fmap)
        folium.Marker([coord_dest[1], coord_dest[0]], tooltip=f"Destino: {destino}",
                      icon=folium.Icon(color="darkblue", icon="flag")).add_to(fmap)
        st_folium(fmap, height=420, use_container_width=True)

        # ---- carga LIFO ----
        st.markdown("**Montagem de carga (LIFO):**")
        carga = montar_carga(ordem_nomes, qtds_por_nome)
        st.dataframe(carga, use_container_width=True, hide_index=True)
    else:
        st.info("Preencha o trajeto e clique em **Calcular rota e carga**.")
