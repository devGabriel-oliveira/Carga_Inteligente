# -*- coding: utf-8 -*-
"""
Rota Inteligente - ATL / Autoport (Streamlit)
=============================================
Rota real por estrada (OpenRouteService) + ordem de entrega otimizada por
combustivel + montagem de carga (Cegonha 11 / Prancha 4) + mapa + rota
alternativa + praças de pedágio (OpenStreetMap, sem valores).

Rodar:
  1) pip install -r requirements.txt
  2) .streamlit/secrets.toml com  ORS_API_KEY = "sua_chave"  (gratis em openrouteservice.org)
  3) streamlit run app.py
"""

import itertools
import math
import os
import base64
import urllib.parse
import requests
import pandas as pd
import streamlit as st
import openrouteservice as ors
import folium
from streamlit_folium import st_folium

# ---------------------------------------------------------------- paleta
NAVY="#0C1B2E"; ACCENT="#E30613"; ALT="#2563EB"; FG="#0F1A2E"; FG2="#4B5C72"
FG3="#8896A8"; BORDER="#E2E6ED"; CARD="#FFFFFF"; CARD_ALT="#F8FAFC"
COLORS=["#3B82F6","#10B981","#F59E0B","#8B5CF6","#EF4444","#06B6D4","#6366F1","#EC4899"]

UFS={"AC":"Acre","AL":"Alagoas","AP":"Amapá","AM":"Amazonas","BA":"Bahia","CE":"Ceará",
"DF":"Distrito Federal","ES":"Espírito Santo","GO":"Goiás","MA":"Maranhão","MT":"Mato Grosso",
"MS":"Mato Grosso do Sul","MG":"Minas Gerais","PA":"Pará","PB":"Paraíba","PR":"Paraná",
"PE":"Pernambuco","PI":"Piauí","RJ":"Rio de Janeiro","RN":"Rio Grande do Norte",
"RS":"Rio Grande do Sul","RO":"Rondônia","RR":"Roraima","SC":"Santa Catarina",
"SP":"São Paulo","SE":"Sergipe","TO":"Tocantins"}
UF_LIST=list(UFS.keys())

# ---------------------------------------------------------------- veiculos
POS_CEGONHA=[
    {"Posição":"S1","Piso":"Superior","Prioridade":11},{"Posição":"S2","Piso":"Superior","Prioridade":9},
    {"Posição":"S3","Piso":"Superior","Prioridade":7},{"Posição":"S4","Piso":"Superior","Prioridade":4},
    {"Posição":"S5","Piso":"Superior","Prioridade":2},{"Posição":"I1","Piso":"Inferior","Prioridade":10},
    {"Posição":"I2","Piso":"Inferior","Prioridade":8},{"Posição":"I3","Piso":"Inferior","Prioridade":6},
    {"Posição":"I4","Piso":"Inferior","Prioridade":5},{"Posição":"I5","Piso":"Inferior","Prioridade":3},
    {"Posição":"I6","Piso":"Inferior","Prioridade":1}]
POS_PRANCHA=[
    {"Posição":"P1","Piso":"Único","Prioridade":4},{"Posição":"P2","Piso":"Único","Prioridade":3},
    {"Posição":"P3","Piso":"Único","Prioridade":2},{"Posição":"P4","Piso":"Único","Prioridade":1}]
VEICULOS={"Cegonha (11 carros)":{"cap":11,"pos":POS_CEGONHA},
          "Prancha (4 carros)":{"cap":4,"pos":POS_PRANCHA}}

st.set_page_config(page_title="Rota Inteligente", layout="wide")

# ---------------------------------------------------------------- icones (Feather, MIT)
_IC={
 "truck":'<path d="M1 3h15v13H1z"/><path d="M16 8h4l3 3v5h-7V8z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
 "nav":'<polygon points="3 11 22 2 13 21 11 13 3 11"/>',
 "pin":'<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
 "layers":'<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
 "list":'<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
 "fuel":'<path d="M12 2.7l5.7 5.7a8 8 0 1 1-11.4 0z"/>',
 "dollar":'<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
 "road":'<path d="M4 19l4-14"/><path d="M20 19l-4-14"/><line x1="12" y1="6" x2="12" y2="8"/><line x1="12" y1="11" x2="12" y2="13"/><line x1="12" y1="16" x2="12" y2="18"/>',
 "map":'<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>',
 "clock":'<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
 "toll":'<rect x="3" y="10" width="18" height="10" rx="1"/><path d="M6 10V6h12v4"/><line x1="12" y1="14" x2="12" y2="16"/>',
}
def ic(name,size=18,color="currentColor",sw=2):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" '
            f'style="vertical-align:middle;flex-shrink:0">{_IC[name]}</svg>')

# ---------------------------------------------------------------- CSS
st.markdown("""
<style>
#MainMenu, footer, header[data-testid="stHeader"]{visibility:hidden;height:0;}
.block-container{padding-top:1.6rem;padding-bottom:3rem;max-width:1100px;}
.ri-header{background:#0C1B2E;border-radius:14px;padding:18px 26px;display:flex;align-items:center;
 gap:18px;margin-bottom:24px;flex-wrap:wrap;min-height:78px;box-shadow:0 2px 10px rgba(12,27,46,.12);}
.ri-logo{height:52px;width:auto;flex-shrink:0;}
.ri-mark{width:44px;height:44px;background:#E30613;border-radius:10px;display:flex;align-items:center;
 justify-content:center;font-weight:800;color:#fff;font-size:16px;flex-shrink:0;}
.ri-htext{display:flex;flex-direction:column;line-height:1.25;}
.ri-title{font-size:23px;font-weight:800;color:#fff;letter-spacing:-.2px;padding:1px 0;}
.ri-title b{color:#E30613;}
.ri-subt{font-size:12.5px;color:rgba(255,255,255,.6);font-weight:500;}
.ri-tag{margin-left:auto;font-size:11px;font-weight:700;color:rgba(255,255,255,.5);
 letter-spacing:2px;text-transform:uppercase;align-self:center;}
.ri-h{display:flex;align-items:center;gap:10px;font-size:17px;font-weight:800;color:#0C1B2E;
 margin:2px 0 16px;padding-bottom:10px;border-bottom:2px solid #F0F2F6;}
.ri-h::before{content:"";width:4px;height:20px;background:#E30613;border-radius:2px;flex-shrink:0;}
.ri-h .sub{font-weight:600;color:#8896A8;font-size:11px;margin-left:auto;text-transform:uppercase;letter-spacing:.4px;}
.ri-stats{display:flex;gap:12px;flex-wrap:wrap;margin:4px 0 18px;}
.ri-st{flex:1;min-width:140px;background:#fff;border:1px solid #E2E6ED;border-radius:14px;
 padding:15px 17px;box-shadow:0 1px 3px rgba(12,27,46,.05);}
.ri-st .top{display:flex;align-items:center;gap:7px;color:#8896A8;margin-bottom:7px;}
.ri-st .top span{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;}
.ri-st .v{font-size:25px;font-weight:800;color:#0F1A2E;letter-spacing:-.6px;line-height:1;}
.ri-st .d{font-size:11px;color:#8896A8;margin-top:5px;}
.ri-card{background:#fff;border:1px solid #E2E6ED;border-radius:14px;padding:20px;
 box-shadow:0 1px 3px rgba(12,27,46,.05);margin-bottom:18px;}
.ri-flow{display:flex;align-items:flex-start;gap:4px;overflow-x:auto;padding:4px 0;}
.ri-node{display:flex;flex-direction:column;align-items:center;gap:6px;min-width:84px;flex-shrink:0;}
.ri-circ{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 font-weight:800;color:#fff;font-size:14px;}
.ri-lbl{font-size:12px;font-weight:600;color:#4B5C72;text-align:center;line-height:1.25;}
.ri-sub{font-size:10px;color:#8896A8;font-weight:500;text-align:center;}
.ri-arrow{flex:1;min-width:22px;height:2px;background:#E2E6ED;margin-top:19px;}
.stButton>button{font-weight:700;border-radius:9px;padding:9px 18px;}
.ri-info{background:#F8FAFC;border:1px solid #E2E6ED;border-left:3px solid #C8102E;border-radius:8px;
 padding:10px 14px;font-size:12.5px;color:#4B5C72;margin-bottom:14px;}
.ri-warn{background:#FFF7ED;border:1px solid #FED7AA;border-left:3px solid #F59E0B;border-radius:8px;
 padding:10px 14px;font-size:12.5px;color:#7C4A03;margin-bottom:12px;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def _logo_uri():
    for p in ("assets/autoport_logo.png", "autoport_logo.png", "assets/logo.png"):
        if os.path.exists(p):
            with open(p, "rb") as f:
                return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    return None

_logo = _logo_uri()
_marca = f'<img src="{_logo}" class="ri-logo" alt="Autoport"/>' if _logo else '<div class="ri-mark">AP</div>'
st.markdown(f"""
<div class="ri-header">
  {_marca}
  <div class="ri-htext">
    <div class="ri-title">Rota <b>Inteligente</b></div>
    <div class="ri-subt">Rota, pedágios e montagem de carga — cegonha e prancha</div>
  </div>
  <div class="ri-tag">Autoport</div>
</div>
""", unsafe_allow_html=True)

def sec_header(icon_name, titulo, sub=""):
    sub_html=f'<span class="sub">{sub}</span>' if sub else ""
    st.markdown(f'<div class="ri-h">{ic(icon_name,18,ACCENT)}<span>{titulo}</span>{sub_html}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- ORS / IBGE
def get_client():
    key=st.secrets.get("ORS_API_KEY","")
    if not key:
        st.error('Falta a chave do OpenRouteService. Streamlit Cloud: Manage app → Settings → '
                 'Secrets → ORS_API_KEY = "sua_chave". Local: .streamlit/secrets.toml.'); st.stop()
    return ors.Client(key=key)

@st.cache_data(show_spinner=False)
def municipios(uf):
    """Lista oficial de municípios do IBGE para a UF (dropdown confiável)."""
    try:
        url=f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
        r=requests.get(url,timeout=12); r.raise_for_status()
        return sorted([m["nome"] for m in r.json()])
    except Exception:
        return None

_GEO_CACHE={}  # cache simples no processo (seguro para threads)
def geocode(cidade, uf, bairro=""):
    """Geocoding ESTRUTURADO: cidade+UF (+bairro) -> (coord, label, ok, msg).
    Valida que a UF retornada bate com a escolhida, evitando cidade errada."""
    chave=(cidade.strip().lower(), uf, bairro.strip().lower())
    if chave in _GEO_CACHE: return _GEO_CACHE[chave]
    cli=get_client()
    kw=dict(country="Brazil", region=UFS.get(uf,uf), locality=cidade)
    if bairro.strip(): kw["neighbourhood"]=bairro.strip()
    try:
        r=cli.pelias_structured(**kw)
    except Exception as e:
        return None, None, False, f"erro ao localizar ({e})"
    feats=r.get("features",[])
    if not feats:
        out=(None, None, False, "não encontrada"); _GEO_CACHE[chave]=out; return out
    f=feats[0]; props=f.get("properties",{})
    lon,lat=f["geometry"]["coordinates"]
    reg=(props.get("region_a") or "").upper(); label=props.get("label","")
    if reg and reg!=uf:
        out=((lon,lat), label, False, f"retornou {reg}, não {uf} — verifique cidade/UF")
    else:
        out=((lon,lat), label, True, label)
    _GEO_CACHE[chave]=out; return out

def geocode_paralelo(locais):
    """Geocodifica vários locais ao mesmo tempo. locais = lista de (cidade,uf,bairro)."""
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(lambda L: geocode(*L), locais))

# ---------------------------------------------------------------- distancias / rota
def hav(a,b):  # [lon,lat] -> km
    R=6371; r=math.radians
    dla=r(b[1]-a[1]); dlo=r(b[0]-a[0])
    s=math.sin(dla/2)**2+math.cos(r(a[1]))*math.cos(r(b[1]))*math.sin(dlo/2)**2
    return 2*R*math.asin(math.sqrt(s))

@st.cache_data(show_spinner=False)
def matriz_km(coords):
    r=get_client().distance_matrix(locations=coords, profile="driving-hgv",
                                   metrics=["distance"], units="km")
    return r["distances"]

@st.cache_data(show_spinner=False)
def rota_unica(coords_ord):
    """Rota principal em UMA chamada (todos os waypoints). Retorna (feats, km, horas)."""
    r=get_client().directions(coordinates=[list(c) for c in coords_ord],
                              profile="driving-hgv", format="geojson")
    f=r["features"][0]; s=f["properties"]["summary"]
    return [f], s.get("distance",0.0)/1000.0, s.get("duration",0.0)/3600.0

@st.cache_data(show_spinner=False)
def _leg(a, b, alternativa):
    """Direções de um trecho (2 pontos). Retorna (feature, dist_m, dur_s)."""
    params=dict(coordinates=[list(a),list(b)], profile="driving-hgv", format="geojson")
    if alternativa:
        params["alternative_routes"]={"target_count":2,"share_factor":0.6,"weight_factor":1.6}
    r=get_client().directions(**params)
    feats=r["features"]
    use=feats[1] if (alternativa and len(feats)>1) else feats[0]
    s=use["properties"]["summary"]
    return use, s.get("distance",0.0), s.get("duration",0.0)

def rota_por_trechos(coords_ord, alternativa=False):
    """Concatena os trechos; retorna (lista_features, dist_km, tempo_h, tem_alternativa)."""
    feats=[]; dist=0.0; dur=0.0; mudou=False
    for i in range(len(coords_ord)-1):
        try:
            f,d,t=_leg(coords_ord[i], coords_ord[i+1], alternativa)
            if alternativa:
                f0,d0,_=_leg(coords_ord[i], coords_ord[i+1], False)
                if abs(d-d0)>1: mudou=True
        except Exception:
            f,d,t=_leg(coords_ord[i], coords_ord[i+1], False)
        feats.append(f); dist+=d; dur+=t
    return feats, dist/1000.0, dur/3600.0, (mudou if alternativa else True)

def coords_da_geometria(feats):
    pts=[]
    for f in feats:
        g=f["geometry"]
        if g["type"]=="LineString": pts+=g["coordinates"]
        elif g["type"]=="MultiLineString":
            for part in g["coordinates"]: pts+=part
    return pts

# espelhos do Overpass (tenta em ordem; o principal vive sobrecarregado/bloqueado)
OVERPASS_MIRRORS=[
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

def _overpass(q):
    """Consulta Overpass tentando vários espelhos. Erra só se todos falharem."""
    erros=[]
    for url in OVERPASS_MIRRORS:
        try:
            r=requests.post(url, data={"data":q}, timeout=12,
                            headers={"User-Agent":"RotaInteligente-ATL/1.0"})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            erros.append(f"{url.split('/')[2]}: {e}")
    raise RuntimeError("Nenhum servidor Overpass respondeu. " + " | ".join(erros))

def pedagios_osm(feats, raio_km=0.5):
    """Praças de pedágio (barrier=toll_booth) do OpenStreetMap ao longo da rota.
    Retorna lista de {nome,lat,lon}. SEM valores de tarifa. Pode falhar/variar."""
    pts=coords_da_geometria(feats)
    if not pts: return []
    lons=[p[0] for p in pts]; lats=[p[1] for p in pts]
    s,w,n,e=min(lats),min(lons),max(lats),max(lons)
    q=f'[out:json][timeout:25];node["barrier"="toll_booth"]({s-0.02},{w-0.02},{n+0.02},{e+0.02});out;'
    els=_overpass(q).get("elements",[])
    # amostra os vértices para acelerar
    amostra=pts[::max(1,len(pts)//800)]
    out=[]; vistos=set()
    for el in els:
        p=[el["lon"],el["lat"]]
        if min(hav(p,c) for c in amostra)<=raio_km:
            tg=el.get("tags",{})
            nome=tg.get("name") or tg.get("operator") or "Praça de pedágio"
            chave=(round(el["lat"],3),round(el["lon"],3))
            if chave not in vistos:
                vistos.add(chave); out.append({"nome":nome,"lat":el["lat"],"lon":el["lon"]})
    return out

def fmt_tempo(h):
    tot=int(round(h*60)); return f"{tot//60}h {tot%60:02d}min"

# ---------------------------------------------------------------- otimizacao
def custo_comb(ordem, D, dmat, q, base, extra, peso):
    litros=km=0.0; atual=0; carros=sum(q[i] for i in ordem)
    for p in ordem:
        d=dmat[atual][p]; litros+=d*(base+extra*carros*peso); km+=d
        carros-=q[p]; atual=p
    d=dmat[atual][D]; litros+=d*base; km+=d
    return litros,km

def otimizar(n, D, dmat, q, base, extra, peso):
    best=None
    for perm in itertools.permutations(range(1,1+n)):
        l,k=custo_comb(perm,D,dmat,q,base,extra,peso)
        if best is None or l<best[0]: best=(l,k,perm)
    return best

def montar_carga(ordem_nomes, qpn, positions):
    pos=sorted(positions, key=lambda p:p["Prioridade"]); a=[]; i=0
    for oi,nome in enumerate(ordem_nomes,1):
        for _ in range(qpn[nome]):
            if i<len(pos):
                a.append({"pos":pos[i]["Posição"],"piso":pos[i]["Piso"],"entrega":nome,
                          "ordem_entrega":oi,"ordem_descarga":i+1}); i+=1
    return a

# ---------------------------------------------------------------- desenho veiculos
def _f(n): return f"{n:.1f}"
def _car(cx,gY,w,c):
    wr=w*0.12;h=w*0.46;bx=cx-w/2;by=gY-wr;lowT=by-h*0.5;roofT=by-h
    return (f'<circle cx="{_f(cx-w*0.27)}" cy="{_f(by)}" r="{_f(wr)}" fill="#141b29" stroke="{BORDER}" stroke-width="1"/>'
            f'<circle cx="{_f(cx+w*0.27)}" cy="{_f(by)}" r="{_f(wr)}" fill="#141b29" stroke="{BORDER}" stroke-width="1"/>'
            f'<circle cx="{_f(cx-w*0.27)}" cy="{_f(by)}" r="{_f(wr*0.45)}" fill="#44557a"/>'
            f'<circle cx="{_f(cx+w*0.27)}" cy="{_f(by)}" r="{_f(wr*0.45)}" fill="#44557a"/>'
            f'<path d="M {_f(bx)} {_f(by)} L {_f(bx)} {_f(lowT)} L {_f(bx+w*0.2)} {_f(roofT)} '
            f'L {_f(bx+w*0.78)} {_f(roofT)} L {_f(bx+w)} {_f(lowT)} L {_f(bx+w)} {_f(by)} Z" '
            f'fill="{c}" stroke="rgba(0,0,0,.18)" stroke-width="1"/>'
            f'<path d="M {_f(bx+w*0.25)} {_f(lowT)} L {_f(bx+w*0.34)} {_f(roofT+3)} L {_f(bx+w*0.47)} {_f(roofT+3)} L {_f(bx+w*0.47)} {_f(lowT)} Z" fill="#fff" opacity=".45"/>'
            f'<path d="M {_f(bx+w*0.53)} {_f(lowT)} L {_f(bx+w*0.53)} {_f(roofT+3)} L {_f(bx+w*0.66)} {_f(roofT+3)} L {_f(bx+w*0.75)} {_f(lowT)} Z" fill="#fff" opacity=".45"/>')
def _slot(p,cx,gY,w,iy,cyy,asgn):
    a=asgn.get(p["Posição"]);wr=w*0.12;h=w*0.46;topY=gY-wr-h;s=""
    if a:
        s+=_car(cx,gY,w,a["cor"])
        s+=(f'<circle cx="{_f(cx+w*0.33)}" cy="{_f(topY+12)}" r="11" fill="{NAVY}" stroke="{CARD}" stroke-width="2"/>'
            f'<text x="{_f(cx+w*0.33)}" y="{_f(topY+16)}" text-anchor="middle" font-size="11" font-weight="800" fill="#fff">{a["ord"]}</text>')
    else:
        s+=f'<rect x="{_f(cx-w/2)}" y="{_f(topY)}" width="{_f(w)}" height="{_f(gY-topY)}" rx="7" fill="none" stroke="{BORDER}" stroke-width="1.5" stroke-dasharray="5 4"/>'
    s+=f'<text x="{_f(cx)}" y="{iy}" text-anchor="middle" font-size="11" font-weight="700" fill="{FG3}">{p["Posição"]}</text>'
    s+=(f'<text x="{_f(cx)}" y="{cyy}" text-anchor="middle" font-size="11" font-weight="600" fill="{FG}">{a["cidade"]}</text>'
        if a else f'<text x="{_f(cx)}" y="{cyy}" text-anchor="middle" font-size="10" fill="{FG3}">vazio</text>')
    return s
def _centers(n,x0,x1):
    return [(x0+x1)/2] if n==1 else [x0+(x1-x0)*i/(n-1) for i in range(n)]
def _wrap(svg_inner,vb_h=452):
    return (f'<div style="background:#fff;border:1px solid {BORDER};border-radius:14px;padding:16px;overflow-x:auto;">'
            f'<svg viewBox="0 0 980 {vb_h}" style="width:100%;min-width:560px;height:auto;display:block;font-family:sans-serif;">'
            f'{svg_inner}</svg></div>')

def build_cegonha(asgn, positions):
    sup=[p for p in positions if p["Piso"]=="Superior"]; inf=[p for p in positions if p["Piso"]=="Inferior"]
    supC=_centers(len(sup),235,830); infC=_centers(len(inf),215,860); t=""
    for p,cx in zip(sup,supC): t+=_slot(p,cx,180,126,64,82,asgn)
    for p,cx in zip(inf,infC): t+=_slot(p,cx,322,118,356,374,asgn)
    frame=f"""
  <line x1="20" y1="440" x2="962" y2="440" stroke="{BORDER}" stroke-width="2"/>
  <rect x="150" y="334" width="748" height="9" rx="3" fill="{FG2}"/>
  <rect x="160" y="324" width="712" height="7" rx="2" fill="{FG3}"/>
  <rect x="198" y="182" width="650" height="7" rx="2" fill="{FG3}"/>
  <rect x="200" y="182" width="6" height="150" fill="{FG3}"/><rect x="842" y="182" width="6" height="150" fill="{FG3}"/>
  <path d="M 872 331 L 928 408" stroke="{FG3}" stroke-width="7" stroke-linecap="round"/>
  <path d="M 40 334 L 40 238 Q 40 212 66 210 L 128 206 Q 150 206 158 234 L 168 300 L 168 334 Z" fill="{NAVY}" stroke="{BORDER}" stroke-width="1.5"/>
  <rect x="58" y="224" width="56" height="36" rx="4" fill="#9ec5ff" opacity=".85"/>
  <circle cx="84" cy="406" r="30" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="84" cy="406" r="12" fill="#44557a"/>
  <circle cx="142" cy="406" r="30" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="142" cy="406" r="12" fill="#44557a"/>
  <circle cx="792" cy="406" r="30" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="792" cy="406" r="12" fill="#44557a"/>
  <circle cx="852" cy="406" r="30" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="852" cy="406" r="12" fill="#44557a"/>
  <text x="104" y="372" text-anchor="middle" font-size="10" font-weight="600" fill="{FG3}">Cabine</text>
  <text x="912" y="372" text-anchor="middle" font-size="10" font-weight="600" fill="{FG3}">Rampa</text>
  <text transform="translate(186,138) rotate(-90)" text-anchor="middle" font-size="9" font-weight="700" fill="{FG3}">SUPERIOR</text>
  <text transform="translate(150,292) rotate(-90)" text-anchor="middle" font-size="9" font-weight="700" fill="{FG3}">INFERIOR</text>
  <text x="40" y="26" font-size="13" font-weight="800" fill="{ACCENT}">AUTO<tspan fill="{NAVY}">PORT</tspan></text>"""
    return _wrap(frame+t, 452)

def build_prancha(asgn, positions):
    pos=sorted(positions, key=lambda p:p["Posição"])
    C=_centers(len(pos),250,830); t=""
    for p,cx in zip(pos,C): t+=_slot(p,cx,250,138,150,286,asgn)
    frame=f"""
  <line x1="20" y1="330" x2="962" y2="330" stroke="{BORDER}" stroke-width="2"/>
  <rect x="150" y="256" width="760" height="12" rx="3" fill="{FG2}"/>
  <rect x="160" y="250" width="745" height="6" rx="2" fill="{FG3}"/>
  <path d="M 905 256 L 950 300" stroke="{FG3}" stroke-width="7" stroke-linecap="round"/>
  <path d="M 40 256 L 40 170 Q 40 146 64 144 L 126 140 Q 148 140 156 166 L 166 230 L 166 256 Z" fill="{NAVY}" stroke="{BORDER}" stroke-width="1.5"/>
  <rect x="58" y="156" width="56" height="34" rx="4" fill="#9ec5ff" opacity=".85"/>
  <circle cx="84" cy="300" r="26" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="84" cy="300" r="10" fill="#44557a"/>
  <circle cx="138" cy="300" r="26" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="138" cy="300" r="10" fill="#44557a"/>
  <circle cx="770" cy="300" r="26" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="770" cy="300" r="10" fill="#44557a"/>
  <circle cx="828" cy="300" r="26" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="828" cy="300" r="10" fill="#44557a"/>
  <circle cx="886" cy="300" r="26" fill="#141b29" stroke="{FG3}" stroke-width="2"/><circle cx="886" cy="300" r="10" fill="#44557a"/>
  <text x="104" y="320" text-anchor="middle" font-size="10" font-weight="600" fill="{FG3}">Cabine</text>
  <text x="930" y="320" text-anchor="middle" font-size="10" font-weight="600" fill="{FG3}">Rampa</text>
  <text transform="translate(188,205) rotate(-90)" text-anchor="middle" font-size="9" font-weight="700" fill="{FG3}">PRANCHA</text>
  <text x="40" y="26" font-size="13" font-weight="800" fill="{ACCENT}">AUTO<tspan fill="{NAVY}">PORT</tspan></text>"""
    return _wrap(frame+t, 340)


# ============================================================================
# ENTRADA
# ============================================================================
def seletor_local(rotulo, uf_pad, cidade_pad, key):
    st.markdown(f"**{rotulo}**")
    c1,c2,c3=st.columns([1,2,2])
    uf=c1.selectbox("UF", UF_LIST, index=UF_LIST.index(uf_pad), key=f"{key}_uf", label_visibility="collapsed")
    muns=municipios(uf)
    if muns:
        idx=muns.index(cidade_pad) if cidade_pad in muns else 0
        cidade=c2.selectbox("Cidade", muns, index=idx, key=f"{key}_cid", label_visibility="collapsed")
    else:
        cidade=c2.text_input("Cidade", cidade_pad, key=f"{key}_cidtxt", label_visibility="collapsed",
                             placeholder="Cidade")
    bairro=c3.text_input("Bairro", "", key=f"{key}_bai", label_visibility="collapsed",
                         placeholder="Bairro (opcional)")
    return {"uf":uf,"cidade":cidade,"bairro":bairro}

with st.container(border=True):
    sec_header("nav","Planejamento de rota")
    veic_nome=st.selectbox("Tipo de veículo", list(VEICULOS.keys()))
    veic=VEICULOS[veic_nome]; CAP=veic["cap"]
    cL,cR=st.columns(2)
    with cL: origem=seletor_local("Origem","MG","Juiz de Fora","orig")
    with cR: destino=seletor_local("Destino final","MG","Juiz de Fora","dest")
    st.markdown("**Paradas de entrega** — UF, cidade, bairro (opcional) e nº de carros")
    if "paradas_df" not in st.session_state:
        st.session_state.paradas_df=pd.DataFrame([
            {"UF":"ES","Cidade":"Cariacica","Bairro":"","Carros":1},
            {"UF":"MG","Cidade":"Governador Valadares","Bairro":"","Carros":3},
            {"UF":"MG","Cidade":"Coronel Pacheco","Bairro":"","Carros":1}])
    paradas_df=st.data_editor(st.session_state.paradas_df, num_rows="dynamic", use_container_width=True,
        hide_index=True, key="editor_paradas", column_config={
            "UF":st.column_config.SelectboxColumn("UF", options=UF_LIST, width="small"),
            "Cidade":st.column_config.TextColumn("Cidade", width="large"),
            "Bairro":st.column_config.TextColumn("Bairro", width="medium"),
            "Carros":st.column_config.NumberColumn("Carros", min_value=1, max_value=11, step=1)})
    st.caption("Rota alternativa e praças de pedágio ficam como botões no resultado "
               "(não atrasam o cálculo principal).")

with st.expander("Ajustes avançados (gestor) — consumo e prioridades das posições"):
    st.markdown("**Consumo do veículo** (estima combustível e escolhe a ordem que gasta menos)")
    a1,a2,a3,a4=st.columns(4)
    base_lpk=a1.number_input("Consumo vazio (L/km)",0.1,1.0,0.33,0.01, help="Litros por km VAZIO.")
    extra_lpk_t=a2.number_input("Extra por tonelada (L/km·t)",0.0,0.05,0.004,0.001, help="L/km a mais por tonelada.")
    peso_carro=a3.number_input("Peso médio/carro (t)",0.5,3.0,1.3,0.1)
    preco_diesel=a4.number_input("Diesel (R$/L)",3.0,12.0,6.20,0.10)
    st.divider()
    st.markdown("**Prioridade das posições**")
    st.markdown('<div class="ri-info">Prioridade <b>1 = descarregada primeiro</b> (mais acessível, '
                'perto da rampa). A 1ª entrega vai para a prioridade 1, a 2ª para a 2, e assim por diante.</div>',
                unsafe_allow_html=True)
    pos_key=f"pos_{veic_nome}"
    pos_df=st.data_editor(st.session_state.get(pos_key, pd.DataFrame(veic["pos"])),
        use_container_width=True, hide_index=True, key=f"editor_{pos_key}", column_config={
            "Posição":st.column_config.TextColumn("Posição", disabled=True),
            "Piso":st.column_config.TextColumn("Piso"),
            "Prioridade":st.column_config.NumberColumn("Prioridade", min_value=1, max_value=CAP, step=1)})
    if st.button("Restaurar padrão das posições"):
        st.session_state[pos_key]=pd.DataFrame(veic["pos"]); st.rerun()
    st.session_state[pos_key]=pos_df

calcular=st.button("Calcular rota e carga", type="primary", use_container_width=True)


# ============================================================================
# CALCULO
# ============================================================================
if calcular:
    df=paradas_df.dropna(subset=["Cidade"])
    paradas=[{"uf":str(r["UF"]).strip(),"cidade":str(r["Cidade"]).strip(),
              "bairro":str(r.get("Bairro","") or "").strip(),"qtd":int(r["Carros"])}
             for _,r in df.iterrows() if str(r["Cidade"]).strip()]
    total=sum(p["qtd"] for p in paradas)
    positions=pos_df.to_dict("records")

    if not paradas:
        st.warning("Adicione ao menos uma parada."); st.stop()
    if total>CAP:
        st.error(f"Capacidade excedida: {total} carros para {CAP} do veículo {veic_nome}."); st.stop()
    if len(paradas)>9:
        st.warning("Acima de 9 paradas a força bruta fica lenta.")

    with st.spinner("Localizando endereços e calculando a rota..."):
        # geocode EM PARALELO (origem, destino e paradas de uma vez)
        locais=[(origem["cidade"],origem["uf"],origem["bairro"]),
                (destino["cidade"],destino["uf"],destino["bairro"])]+\
               [(p["cidade"],p["uf"],p["bairro"]) for p in paradas]
        geos=geocode_paralelo(locais)
        (co,lo,ok,msg),(cd,ld,okd,msgd)=geos[0],geos[1]
        cps=[g[0] for g in geos[2:]]; labels=[g[1] for g in geos[2:]]
        problemas=[]
        if not ok: problemas.append(f"Origem ({origem['cidade']}/{origem['uf']}): {msg}")
        if not okd: problemas.append(f"Destino ({destino['cidade']}/{destino['uf']}): {msgd}")
        for p,g in zip(paradas, geos[2:]):
            if not g[2]: problemas.append(f"{p['cidade']}/{p['uf']}: {g[3]}")
        if problemas:
            st.error("Verifique estas localizações (UF/cidade/bairro):\n\n- " + "\n- ".join(problemas)); st.stop()

        coords=[co]+cps+[cd]; D=len(coords)-1
        nomes=[f"{p['cidade']}/{p['uf']}" for p in paradas]; qtds=[p["qtd"] for p in paradas]
        try:
            dmat=matriz_km(coords)
        except Exception as e:
            st.error(f"Erro ao calcular distâncias (ORS): {e}"); st.stop()
        qi={j+1:qtds[j] for j in range(len(qtds))}
        litros,km,ordem=otimizar(len(paradas),D,dmat,qi,base_lpk,extra_lpk_t,peso_carro)
        _,km_so,ordem_km=otimizar(len(paradas),D,dmat,qi,base_lpk,0.0,peso_carro)
        ordem_nomes=[nomes[p-1] for p in ordem]
        qpn={nomes[j]:qtds[j] for j in range(len(nomes))}
        coords_ord=[co]+[cps[p-1] for p in ordem]+[cd]

        # rota principal em UMA chamada só
        try:
            feats_main,dist_main,tempo_main=rota_unica(coords_ord)
        except Exception as e:
            feats_main,dist_main,tempo_main=[],km,0.0
            st.warning(f"Não consegui traçar a geometria da rota: {e}")

        carga=montar_carga(ordem_nomes,qpn,positions)
        segs=[lo or origem["cidade"]]+[labels[p-1] or nomes[p-1] for p in ordem]
        if (destino["cidade"].strip().lower()!=paradas[ordem[-1]-1]["cidade"].strip().lower()):
            segs.append(ld or destino["cidade"])
        maps_url="https://www.google.com/maps/dir/"+"/".join(urllib.parse.quote(s) for s in segs)

    st.session_state["res"]={
        "veic":veic_nome,"cap":CAP,"positions":positions,
        "origem":origem,"destino":destino,"lo":lo,"ld":ld,
        "total":total,"km":km,"km_so":km_so,"reordenou":ordem!=ordem_km,
        "litros":litros,"custo":litros*preco_diesel,
        "ordem":list(ordem),"nomes":nomes,"qtds":qtds,
        "co":co,"cd":cd,"cps":cps,"coords_ord":[list(c) for c in coords_ord],
        "feats_main":feats_main,"dist_main":dist_main,"tempo_main":tempo_main,
        # alternativa e pedágios calculados sob demanda (botões no resultado)
        "feats_alt":None,"dist_alt":None,"tempo_alt":None,"tem_alt":False,
        "pedagios":None,"pedagios_erro":None,
        "carga":carga,"maps_url":maps_url,
    }


# ============================================================================
# RESULTADO
# ============================================================================
res=st.session_state.get("res")
if not res:
    st.info("Preencha o trajeto e clique em **Calcular rota e carga**."); st.stop()

ordem,nomes,qtds=res["ordem"],res["nomes"],res["qtds"]
co,cd,cps=res["co"],res["cd"],res["cps"]
dist=res["dist_main"] if res["feats_main"] else res["km"]

def stat(icon_name,v,r,d):
    return (f'<div class="ri-st"><div class="top">{ic(icon_name,15)}<span>{r}</span></div>'
            f'<div class="v">{v}</div><div class="d">{d}</div></div>')
def br(n,dec=0): return f"{n:,.{dec}f}".replace(",","X").replace(".",",").replace("X",".")
ped_txt="—"
if res["pedagios"] is not None: ped_txt=str(len(res["pedagios"]))
tempo_txt=fmt_tempo(res["tempo_main"]) if res["feats_main"] else "—"
st.markdown('<div class="ri-stats">'
    + stat("truck",res["total"],"Carros",f"capacidade {res['cap']} ({res['veic'].split()[0]})")
    + stat("road",f"{br(dist)} km","Distância","percurso real por estrada")
    + stat("clock",tempo_txt,"Tempo","estimado de direção")
    + stat("fuel",f"{br(res['litros'])} L","Combustível","estimado p/ esta rota")
    + stat("dollar",f"R$ {br(res['custo'])}","Custo diesel","litros × preço/L")
    + stat("toll",ped_txt,"Pedágios","praças na rota (sem valores)")
    + '</div>', unsafe_allow_html=True)

if res["reordenou"]:
    st.success(f"Ordem otimizada por combustível (menor distância pura seria {br(res['km_so'])} km).")

# ---- extras sob demanda (não atrasam o cálculo principal) ----
bA,bT=st.columns(2)
if bA.button("Ver rota alternativa", use_container_width=True,
             disabled=not res["feats_main"] or res["feats_alt"] is not None):
    with st.spinner("Calculando rota alternativa..."):
        try:
            fa,da,ta,tem=rota_por_trechos(res["coords_ord"], True)
            res["feats_alt"],res["dist_alt"],res["tempo_alt"],res["tem_alt"]=fa,da,ta,tem
        except Exception as e:
            res["tem_alt"]=False; res["feats_alt"]=[]; st.warning(f"Alternativa indisponível: {e}")
    st.session_state["res"]=res; st.rerun()
if bT.button("Buscar praças de pedágio", use_container_width=True,
             disabled=not res["feats_main"] or res["pedagios"] is not None):
    with st.spinner("Consultando praças de pedágio (OpenStreetMap)..."):
        try:
            res["pedagios"]=pedagios_osm(res["feats_main"]); res["pedagios_erro"]=None
        except Exception as e:
            res["pedagios"]=None; res["pedagios_erro"]=str(e)
    st.session_state["res"]=res; st.rerun()

# comparação rota principal x alternativa
if res["feats_alt"] and res["tem_alt"]:
    with st.container(border=True):
        sec_header("nav","Comparação de rotas","principal × alternativa")
        comp=[
            {"Métrica":"Distância (km)","Principal":br(res["dist_main"],1),"Alternativa":br(res["dist_alt"],1)},
            {"Métrica":"Tempo","Principal":fmt_tempo(res["tempo_main"]),"Alternativa":fmt_tempo(res["tempo_alt"])},
        ]
        st.dataframe(comp, use_container_width=True, hide_index=True)
        st.caption("Pedágios por rota com valores exigem API paga (Qualp/TollGuru). "
                   "As praças mostradas abaixo referem-se à rota principal (OpenStreetMap, sem tarifa).")
elif res.get("feats_alt") is not None and not res["tem_alt"]:
    st.caption("Não há rota alternativa relevante para este trajeto (a principal já é a melhor).")

# fluxo
with st.container(border=True):
    sec_header("nav","Rota","sequência de entrega")
    def circ(cor,dentro): return f'<div class="ri-circ" style="background:{cor}">{dentro}</div>'
    pin=ic("pin",16,"#fff")
    o_lbl=(res["origem"]["cidade"]); d_lbl=(res["destino"]["cidade"])
    flow=f'<div class="ri-node">{circ(NAVY,pin)}<div class="ri-lbl">{o_lbl}</div><div class="ri-sub">Partida</div></div>'
    for i,p in enumerate(ordem):
        flow+='<div class="ri-arrow"></div>'
        flow+=(f'<div class="ri-node">{circ(COLORS[i%8],qtds[p-1])}'
               f'<div class="ri-lbl">{nomes[p-1].split("/")[0]}</div>'
               f'<div class="ri-sub">{i+1}ª · {qtds[p-1]} veíc.</div></div>')
    flow+='<div class="ri-arrow"></div>'
    flow+=f'<div class="ri-node">{circ(NAVY,pin)}<div class="ri-lbl">{d_lbl}</div><div class="ri-sub">Destino</div></div>'
    st.markdown(f'<div class="ri-flow">{flow}</div>', unsafe_allow_html=True)

# mapa
with st.container(border=True):
    sec_header("map","Mapa do trajeto","OpenStreetMap")
    try:
        fmap=folium.Map(location=[co[1],co[0]], zoom_start=6, tiles="OpenStreetMap")
        if res["feats_alt"] and res["tem_alt"]:
            folium.GeoJson(dict(type="FeatureCollection",features=res["feats_alt"]),
                           style_function=lambda x:{"color":ALT,"weight":4,"dashArray":"8 6"},
                           name="Alternativa").add_to(fmap)
        if res["feats_main"]:
            folium.GeoJson(dict(type="FeatureCollection",features=res["feats_main"]),
                           style_function=lambda x:{"color":ACCENT,"weight":5},
                           name="Principal").add_to(fmap)
        folium.Marker([co[1],co[0]], tooltip=f"Origem: {o_lbl}",
                      icon=folium.Icon(color="darkblue",icon="home",prefix="fa")).add_to(fmap)
        for i,p in enumerate(ordem):
            c=cps[p-1]
            folium.Marker([c[1],c[0]], tooltip=f"{i+1}ª · {nomes[p-1]} ({qtds[p-1]} carros)",
                          icon=folium.DivIcon(html=f'<div style="background:{ACCENT};color:#fff;border-radius:50%;'
                                                   f'width:26px;height:26px;display:flex;align-items:center;justify-content:center;'
                                                   f'font-weight:700;font-size:12px;border:2px solid #fff">{i+1}</div>')).add_to(fmap)
        folium.Marker([cd[1],cd[0]], tooltip=f"Destino: {d_lbl}",
                      icon=folium.Icon(color="darkblue",icon="flag-checkered",prefix="fa")).add_to(fmap)
        if res["pedagios"]:
            for pg in res["pedagios"]:
                folium.Marker([pg["lat"],pg["lon"]], tooltip=f"Pedágio: {pg['nome']}",
                              icon=folium.Icon(color="orange",icon="dollar",prefix="fa")).add_to(fmap)
        st_folium(fmap, height=440, use_container_width=True, returned_objects=[])
        st.caption("Linha vermelha: rota principal. Azul tracejada: alternativa (quando houver).")
    except Exception as e:
        st.warning(f"Não foi possível desenhar o mapa ({e}). A rota foi calculada; use o Google Maps abaixo.")

# pedagios (só aparece depois que o usuário clicou em "Buscar praças de pedágio")
if res["pedagios"] is not None or res["pedagios_erro"]:
    with st.container(border=True):
        sec_header("toll","Praças de pedágio","OpenStreetMap · sem valores de tarifa")
        if res["pedagios_erro"]:
            st.markdown(f'<div class="ri-warn">Não foi possível consultar as praças agora '
                        f'({res["pedagios_erro"]}). Tente novamente.</div>', unsafe_allow_html=True)
        elif res["pedagios"]:
            st.markdown('<div class="ri-warn">Localização das praças pelo OpenStreetMap. '
                        '<b>Os valores de tarifa NÃO estão incluídos</b> — para valores confirmados é preciso '
                        'uma API paga (Qualp ou TollGuru).</div>', unsafe_allow_html=True)
            st.dataframe([{"Praça":p["nome"],"Lat":round(p["lat"],4),"Lon":round(p["lon"],4)}
                          for p in res["pedagios"]], use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhuma praça de pedágio identificada na rota (ou não mapeada no OpenStreetMap).")

# veículo (cegonha ou prancha)
with st.container(border=True):
    nome_curto=res["veic"].split()[0]
    sec_header("layers", nome_curto, "vista lateral · nº = ordem de descarga")
    asgn={r["pos"]:{"cidade":r["entrega"].split("/")[0],"ord":r["ordem_descarga"],
                    "cor":COLORS[(r["ordem_entrega"]-1)%8]} for r in res["carga"]}
    desenho=build_prancha if nome_curto=="Prancha" else build_cegonha
    st.markdown(desenho(asgn,res["positions"]), unsafe_allow_html=True)

# matriz
with st.container(border=True):
    sec_header("list","Matriz de carga","posição · piso · entrega · ordem")
    st.dataframe([{"Posição":r["pos"],"Piso":r["piso"],"Entrega":r["entrega"],
                   "Ordem entrega":r["ordem_entrega"],"Ordem descarga":r["ordem_descarga"]}
                  for r in res["carga"]], use_container_width=True, hide_index=True)

st.link_button("Abrir no Google Maps", res["maps_url"], use_container_width=True)
