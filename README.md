# Rota Inteligente — ATL / Autoport (Streamlit)

Planeja a rota da cegonha e a montagem de carga (LIFO) usando **distância real por
estrada** e otimização da ordem de entrega por **combustível** (não só por km).

## O que ele faz

- **Geocodifica** origem, paradas e destino (OpenRouteService / perfil de caminhão).
- Calcula a **matriz de distância real por estrada** entre todos os pontos.
- Acha a **melhor ordem de entrega minimizando combustível**:
  `litros = base_L/km · km + extra_L/km·t · (peso a bordo) · km`
  → solta carga pesada cedo = cegonha leve nos trechos longos.
- Desenha o **trajeto real no mapa** (folium).
- Monta a **carga LIFO** nas 11 posições (2 pisos).

## Rodar local

```bash
pip install -r requirements.txt
# chave gratuita em https://openrouteservice.org/dev/#/signup
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # e cole sua chave
streamlit run app.py
```

Abre em http://localhost:8501

## Parâmetros (barra lateral)

| Campo | O que é | Padrão |
|---|---|---|
| Consumo base (vazio) | litros por km com a cegonha vazia | 0,33 L/km |
| Extra por tonelada | litros/km a mais por tonelada embarcada | 0,004 L/km·t |
| Peso médio por carro | usado para converter carros → toneladas | 1,3 t |
| Preço do diesel | para estimar o custo em R$ | 6,20 R$/L |

Ajuste esses números com o consumo real da sua frota para a estimativa ficar fiel.

## Limites e escala

- **Otimização**: força bruta exata até ~9 paradas. Acima disso, troque por
  **Google OR-Tools** (VRP) — a lógica de custo (`custo_combustivel`) já está isolada
  e pode ser reaproveitada.
- **ORS grátis**: ~2.000 rotas/dia e ~500 matrizes/dia. Se passar disso, auto-hospede
  **OSRM + VROOM** (grátis, só o servidor) ou use chave paga.

## Deploy

- **Protótipo**: [Streamlit Community Cloud](https://streamlit.io/cloud) (grátis).
  ⚠️ É público por padrão — coloque a chave em *Secrets* do painel, não no repositório.
- **Operação interna da ATL**: hospede num servidor da empresa (Docker) com
  autenticação, para não expor dados de rota. Exemplo:
  ```bash
  docker run -p 8501:8501 -v $PWD:/app -w /app python:3.12 \
    bash -c "pip install -r requirements.txt && streamlit run app.py --server.port 8501"
  ```

## Próximos passos possíveis

- Reaproveitar o **desenho da cegonha (SVG)** do app web em vez da tabela LIFO.
- Janela de tempo por entrega, múltiplos veículos, restrição de altura/peso por posição.
- Botão "Abrir no Google Maps" com a ordem já otimizada.
