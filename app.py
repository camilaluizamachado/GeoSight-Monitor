"""
Geo-Sight — Monitoramento Territorial Automatizado
Detecção de mudanças ambientais via NDVI com Sentinel-2 (Microsoft Planetary Computer)

Instalação:
    pip install streamlit pystac-client planetary-computer rioxarray xarray numpy matplotlib folium streamlit-folium Pillow requests odc-stac odc-geo
"""

import io
import warnings
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
import folium
from streamlit_folium import st_folium
import pystac_client
import planetary_computer
import odc.stac
import datetime

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="Geo-Sight",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    section[data-testid="stSidebar"] { background-color: #161b22; }
    section[data-testid="stSidebar"] * { color: #c9d1d9 !important; }
    .geo-title {
        font-size: 2.4rem; font-weight: 800;
        background: linear-gradient(90deg, #00c6ff, #0072ff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .geo-subtitle { color: #8b949e; font-size: 1rem; margin-top: -8px; }
    [data-testid="stMetricValue"] { font-size: 2rem !important; color: #58a6ff !important; }
    [data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.85rem !important; }
    div.stButton > button {
        background: linear-gradient(90deg, #0072ff, #00c6ff);
        color: white; border: none; border-radius: 8px;
        padding: 0.6rem 1.4rem; font-weight: 700; font-size: 1rem;
        width: 100%; transition: opacity 0.2s;
    }
    div.stButton > button:hover { opacity: 0.85; }
    .info-box {
        background: #161b22; border-left: 4px solid #0072ff;
        border-radius: 6px; padding: 0.8rem 1rem; margin: 0.5rem 0;
        font-size: 0.88rem; color: #8b949e;
    }
    .warn-box {
        background: #1c1a12; border-left: 4px solid #e3b341;
        border-radius: 6px; padding: 0.8rem 1rem; margin: 0.5rem 0;
        font-size: 0.88rem; color: #c9b458;
    }
    .success-box {
        background: #0f1c14; border-left: 4px solid #3fb950;
        border-radius: 6px; padding: 0.8rem 1rem; margin: 0.5rem 0;
        font-size: 0.88rem; color: #56d364;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def buscar_item_sentinel(lat, lon, data_inicio, data_fim):
    delta = 0.15
    bbox = [lon - delta, lat - delta, lon + delta, lat + delta]
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{data_inicio}/{data_fim}",
        query={"eo:cloud_cover": {"lt": 30}},
        sortby="eo:cloud_cover",
    )
    items = list(search.items())
    if not items:
        return None
    return items[0]


def calcular_ndvi(item):
    ds = odc.stac.load(
        [item], bands=["B04", "B08"], resolution=60, bbox=item.bbox,
    )
    red = ds["B04"].isel(time=0).values.astype(float)
    nir = ds["B08"].isel(time=0).values.astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = np.where((nir + red) == 0, np.nan, (nir - red) / (nir + red))
    return ndvi


def ndvi_para_imagem(ndvi_diff):
    vmax = max(abs(np.nanpercentile(ndvi_diff, 2)), abs(np.nanpercentile(ndvi_diff, 98)), 0.1)
    fig, ax = plt.subplots(figsize=(7, 6), facecolor="#0e1117")
    im = ax.imshow(ndvi_diff, cmap=plt.cm.RdYlGn, vmin=-vmax, vmax=vmax, interpolation="nearest")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.ax.yaxis.set_tick_params(color="#8b949e")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="#c9d1d9", fontsize=8)
    cbar.set_label("ΔNDVI (Antes − Depois)", color="#c9d1d9", fontsize=9)
    ax.set_title("Mapa de Variação NDVI", color="#c9d1d9", fontsize=11, pad=10)
    ax.axis("off")
    fig.tight_layout(pad=1)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor="#0e1117", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def construir_mapa(lat, lon, png_bytes, item1):
    m = folium.Map(location=[lat, lon], zoom_start=11, tiles="CartoDB dark_matter", control_scale=True)
    encoded = "data:image/png;base64," + __import__("base64").b64encode(png_bytes).decode()
    folium.raster_layers.ImageOverlay(
        image=encoded,
        bounds=[[item1.bbox[1], item1.bbox[0]], [item1.bbox[3], item1.bbox[2]]],
        opacity=0.75, name="ΔNDVI", interactive=True,
    ).add_to(m)
    folium.Marker(
        location=[lat, lon], tooltip=f"📍 {lat:.4f}, {lon:.4f}",
        icon=folium.Icon(color="blue", icon="crosshairs", prefix="fa"),
    ).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    return m


# SIDEBAR
with st.sidebar:
    st.markdown("### 🛰️ Geo-Sight")
    st.markdown("**Parâmetros de Análise**")
    st.markdown("---")
    lat = st.number_input("🌐 Latitude", value=-3.7327, format="%.4f", step=0.01)
    lon = st.number_input("🌐 Longitude", value=-45.3648, format="%.4f", step=0.01)
    st.markdown("---")
    st.markdown("**📅 Período ANTES**")
    hoje = datetime.date.today()
    d1_inicio = st.date_input("Início", value=hoje - datetime.timedelta(days=365), key="d1i", max_value=hoje)
    d1_fim = st.date_input("Fim", value=hoje - datetime.timedelta(days=335), key="d1f", max_value=hoje)
    st.markdown("**📅 Período DEPOIS**")
    d2_inicio = st.date_input("Início", value=hoje - datetime.timedelta(days=60), key="d2i", max_value=hoje)
    d2_fim = st.date_input("Fim", value=hoje, key="d2f", max_value=hoje)
    st.markdown("---")
    processar = st.button("🔍 Processar Mudança")
    st.markdown("""
    <div class="info-box">
    Fonte: Sentinel-2 L2A via<br>
    <b>Microsoft Planetary Computer</b><br>
    Resolução: 60 m/pixel<br>
    Cobertura de nuvem: &lt; 30%
    </div>
    """, unsafe_allow_html=True)


# ÁREA PRINCIPAL
st.markdown('<div class="geo-title">🛰️ Geo-Sight</div>', unsafe_allow_html=True)
st.markdown('<div class="geo-subtitle">Monitoramento Territorial Automatizado · Detecção de Mudanças Ambientais por NDVI</div>', unsafe_allow_html=True)
st.markdown("---")

if not processar:
    col_map, col_info = st.columns([3, 1])
    with col_map:
        m = folium.Map(location=[lat, lon], zoom_start=10, tiles="CartoDB dark_matter")
        folium.Marker([lat, lon], tooltip=f"📍 {lat:.4f}, {lon:.4f}",
                      icon=folium.Icon(color="blue", icon="crosshairs", prefix="fa")).add_to(m)
        st_folium(m, width=None, height=520, returned_objects=[])
    with col_info:
        st.markdown("""
        <div class="info-box">
        <b>Como usar:</b><br><br>
        1. Defina latitude e longitude.<br><br>
        2. Escolha dois períodos (Antes e Depois).<br><br>
        3. Clique em <b>Processar Mudança</b>.
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="info-box">
        <b>Legenda ΔNDVI:</b><br>
        🟩 Verde → Vegetação <b>aumentou</b><br>
        🟥 Vermelho → Vegetação <b>diminuiu</b><br>
        🟨 Amarelo → Sem alteração
        </div>
        """, unsafe_allow_html=True)

else:
    erros = []
    if d1_fim >= d2_inicio:
        erros.append("⚠️ O período ANTES deve terminar antes do início do período DEPOIS.")
    if erros:
        for e in erros:
            st.error(e)
        st.stop()

    with st.spinner("🔍 Buscando imagens no Planetary Computer..."):
        item1 = buscar_item_sentinel(lat, lon, str(d1_inicio), str(d1_fim))
        item2 = buscar_item_sentinel(lat, lon, str(d2_inicio), str(d2_fim))

    if item1 is None:
        st.markdown('<div class="warn-box">❌ Nenhuma imagem encontrada para o período <b>ANTES</b>. Tente ampliar o intervalo de datas.</div>', unsafe_allow_html=True)
        st.stop()
    if item2 is None:
        st.markdown('<div class="warn-box">❌ Nenhuma imagem encontrada para o período <b>DEPOIS</b>. Tente ampliar o intervalo de datas.</div>', unsafe_allow_html=True)
        st.stop()

    nuvem1 = item1.properties.get("eo:cloud_cover", 0)
    nuvem2 = item2.properties.get("eo:cloud_cover", 0)
    data_img1 = item1.properties.get("datetime", "N/A")[:10]
    data_img2 = item2.properties.get("datetime", "N/A")[:10]

    with st.spinner("📡 Baixando bandas Sentinel-2 (B04 + B08)..."):
        ndvi1 = calcular_ndvi(item1)
        ndvi2 = calcular_ndvi(item2)

    h = min(ndvi1.shape[0], ndvi2.shape[0])
    w = min(ndvi1.shape[1], ndvi2.shape[1])
    ndvi1, ndvi2 = ndvi1[:h, :w], ndvi2[:h, :w]
    ndvi_diff = ndvi1 - ndvi2

    mask_valido = ~np.isnan(ndvi_diff)
    total_pixels = np.sum(mask_valido)
    pct_degradacao = 100.0 * np.sum((ndvi_diff > 0.25) & mask_valido) / total_pixels
    pct_melhora = 100.0 * np.sum((ndvi_diff < -0.25) & mask_valido) / total_pixels
    delta_medio = float(np.nanmean(ndvi_diff))

    with st.spinner("🖼️ Gerando mapa de variação NDVI..."):
        png_bytes = ndvi_para_imagem(ndvi_diff)

    st.markdown("### 📊 Insights Quantitativos")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🛰️ Data (Antes)", data_img1)
    c2.metric("🛰️ Data (Depois)", data_img2)
    c3.metric("🔴 Área Degradada", f"{pct_degradacao:.1f}%", delta=f"ΔNDVI > 0.25", delta_color="inverse")
    c4.metric("🟢 Área Recuperada", f"{pct_melhora:.1f}%", delta=f"ΔNDVI < -0.25", delta_color="normal")
    c5.metric("📈 ΔNDVI Médio", f"{delta_medio:+.3f}")

    st.markdown("---")
    col_map, col_img = st.columns([3, 2])

    with col_map:
        st.markdown("#### 🗺️ Mapa Interativo")
        mapa = construir_mapa(lat, lon, png_bytes, item1)
        st_folium(mapa, width=None, height=500, returned_objects=[])

    with col_img:
        st.markdown("#### 🎨 Raster ΔNDVI")
        st.image(png_bytes, use_column_width=True, caption="Verde = revegetação | Vermelho = degradação")
        st.markdown(f"""
        <div class="success-box">
        ✅ <b>Antes:</b> {item1.id}<br>
        🌥️ Nuvens: {nuvem1:.1f}%<br><br>
        ✅ <b>Depois:</b> {item2.id}<br>
        🌥️ Nuvens: {nuvem2:.1f}%
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🤖 Interpretação Automática")

    if pct_degradacao > 20:
        nivel, msg = "🔴 **CRÍTICO**", f"Degradação ambiental expressiva em **{pct_degradacao:.1f}%** da área. Recomenda-se inspeção de campo urgente."
    elif pct_degradacao > 10:
        nivel, msg = "🟡 **MODERADO**", f"Degradação moderada em **{pct_degradacao:.1f}%** da área. Monitoramento contínuo recomendado."
    elif pct_degradacao > 5:
        nivel, msg = "🟠 **BAIXO**", f"Pequena área degradada ({pct_degradacao:.1f}%). Pode indicar perturbação natural sazonal."
    else:
        nivel, msg = "🟢 **ESTÁVEL**", f"Cobertura vegetal estável ou em melhora. Área recuperada: {pct_melhora:.1f}%."

    st.markdown(f"**Nível de alerta:** {nivel}")
    st.markdown(msg)

    st.markdown("---")
    with st.expander("⬇️ Exportar Dados"):
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button("📥 Baixar mapa ΔNDVI (PNG)", data=png_bytes,
                file_name=f"geo_sight_{data_img1}_{data_img2}.png", mime="image/png")
        with col_dl2:
            ndvi_csv = io.StringIO()
            np.savetxt(ndvi_csv, ndvi_diff, delimiter=",", fmt="%.4f")
            st.download_button("📥 Baixar matriz ΔNDVI (CSV)", data=ndvi_csv.getvalue(),
                file_name=f"geo_sight_matrix_{data_img1}_{data_img2}.csv", mime="text/csv")
