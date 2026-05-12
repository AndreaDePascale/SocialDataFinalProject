#%% Import libraries
from __future__ import annotations
from pathlib import Path
import branca.colormap as cm
import folium
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from shapely.geometry import shape

#%% Config

PANEL_PATH = Path("data/kommune_year_panel.csv")
OUT_DIR = Path("data")
OUT_DIR.mkdir(exist_ok=True)

YEAR_START, YEAR_END = 2008, 2024

# Bubble sizing — radius in pixels (folium) and approx px (plotly).
# These are mapped from |net_pct| to a [min, max] radius linearly.
BUBBLE_MIN_PX = 8
BUBBLE_MAX_PX = 36

#%% 1. Kommune-level metrics

panel = pd.read_csv(PANEL_PATH, dtype={"KommuneCode": str})
panel["KommuneCode"] = panel["KommuneCode"].str.zfill(4)

start_row = panel[panel["year"] == YEAR_START].set_index("KommuneCode")
end_row = panel[panel["year"] == YEAR_END].set_index("KommuneCode")

metrics = pd.DataFrame(index=sorted(set(start_row.index) | set(end_row.index)))
metrics.index.name = "KommuneCode"
metrics["KommuneName"] = start_row["KommuneName"]
metrics["population_start"] = start_row["population"]
metrics["population_end"] = end_row["population"]
metrics["income_start"] = start_row["average_income"]
metrics["income_end"] = end_row["average_income"]

metrics["pop_pct"] = 100 * (metrics["population_end"] - metrics["population_start"]) / metrics["population_start"]
metrics["income_pct"] = 100 * (metrics["income_end"] - metrics["income_start"]) / metrics["income_start"]

totals = panel.groupby("KommuneCode")[["openings", "closings", "net_change"]].sum()
metrics["openings_total"] = totals["openings"]
metrics["closings_total"] = totals["closings"]
metrics["net_total"] = totals["net_change"]

active_2008 = start_row["active"]
metrics["net_pct"] = np.where(
    active_2008.reindex(metrics.index) > 0,
    100 * metrics["net_total"] / active_2008.reindex(metrics.index),
    np.nan,
)
metrics = metrics.reset_index()

#%% 2. GeoJSON + centroids

geojson = requests.get(
    "https://api.dataforsyningen.dk/kommuner?format=geojson", timeout=30
).json()

# Centroid per kommune from polygon geometry
centroids = {}
for feat in geojson["features"]:
    code = feat["properties"]["kode"]
    c = shape(feat["geometry"]).centroid
    centroids[code] = (c.y, c.x)  # (lat, lon)
    feat["id"] = code

# Attach metrics to features (for choropleth hover)
metrics_by_code = metrics.set_index("KommuneCode").to_dict("index")
for feat in geojson["features"]:
    code = feat["properties"]["kode"]
    m = metrics_by_code.get(code, {})
    feat["properties"]["pop_pct"] = m.get("pop_pct")
    feat["properties"]["income_pct"] = m.get("income_pct")
    feat["properties"]["net_total"] = m.get("net_total")
    feat["properties"]["net_pct"] = m.get("net_pct")
    feat["properties"]["kommune_name"] = m.get("KommuneName") or feat["properties"].get("navn")

#%% 3. Bubble sizing helper

# Use the full range of |net_pct| across kommuner to scale radii linearly
abs_pct = metrics["net_pct"].abs().dropna()
PCT_MAX = float(abs_pct.max()) if len(abs_pct) > 0 else 1.0

def bubble_radius(net_pct: float) -> float:
    if pd.isna(net_pct):
        return BUBBLE_MIN_PX
    frac = min(abs(net_pct) / PCT_MAX, 1.0) if PCT_MAX > 0 else 0
    return BUBBLE_MIN_PX + frac * (BUBBLE_MAX_PX - BUBBLE_MIN_PX)

def bubble_color(net_pct: float) -> str:
    if pd.isna(net_pct) or abs(net_pct) < 1e-9:
        return "#888888"
    return "#1a9850" if net_pct > 0 else "#d73027"

def bubble_label(net_pct: float) -> str:
    if pd.isna(net_pct):
        return "n/a"
    return f"{net_pct:+.1f}%"

#%% 4. Folium map builder

def build_folium_map(value_col: str, value_label: str, output_name: str):
    m_data = metrics.dropna(subset=[value_col])
    vals = m_data[value_col]
    if (vals.min() < 0) and (vals.max() > 0):
        bound = max(abs(vals.quantile(0.05)), abs(vals.quantile(0.95)))
        vmin, vmax = -bound, bound
        colors = ["#b2182b", "#ef8a62", "#fddbc7", "#f7f7f7", "#d1e5f0", "#67a9cf", "#2166ac"]
    else:
        vmin, vmax = vals.quantile(0.05), vals.quantile(0.95)
        colors = ["#fff5f0", "#fdbb84", "#e34a33", "#b30000"] if vmin >= 0 else \
                 ["#08306b", "#4292c6", "#deebf7", "#fff5f0"]
    cmap = cm.LinearColormap(colors=colors, vmin=vmin, vmax=vmax, caption=value_label)

    fmap = folium.Map(location=[56.0, 10.5], zoom_start=7,
                      tiles="cartodbpositron", control_scale=True)

    def style_fn(feat):
        v = feat["properties"].get(value_col)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            color = "#cccccc"
        else:
            color = cmap(np.clip(v, vmin, vmax))
        return {"fillColor": color, "color": "white", "weight": 0.6, "fillOpacity": 0.75}

    # Choropleth with rich tooltip
    folium.GeoJson(
        geojson,
        style_function=style_fn,
        name="Municipalities",
        tooltip=folium.GeoJsonTooltip(
            fields=["kommune_name", value_col, "net_total", "net_pct"],
            aliases=["Kommune:", f"{value_label}:", "Net total (units):", "Net change (%):"],
            localize=True,
            sticky=False,
            labels=True,
            style="background-color: white; font-family: sans-serif; font-size: 12px;",
        ),
    ).add_to(fmap)

    # Bubble layer — one per kommune
    bubble_layer = folium.FeatureGroup(name="Net change % bubbles", show=True)
    for _, row in metrics.iterrows():
        code = row["KommuneCode"]
        if code not in centroids:
            continue
        lat, lon = centroids[code]
        r = bubble_radius(row["net_pct"])
        c = bubble_color(row["net_pct"])
        label = bubble_label(row["net_pct"])

        # The bubble itself, no interactivity (so it doesn't intercept the polygon tooltip)
        folium.CircleMarker(
            location=[lat, lon], radius=r,
            color=c, weight=1, fill=True, fill_color=c, fill_opacity=0.6,
            interactive=False,
        ).add_to(bubble_layer)

        # Text label centered on the bubble. Font size scales mildly with radius.
        font_px = max(9, min(14, int(r * 0.5)))
        icon_html = (
            f"<div style='font-size:{font_px}px; font-weight:600; color:white; "
            f"text-align:center; text-shadow: 0 0 2px rgba(0,0,0,0.6); "
            f"white-space:nowrap; transform:translate(-50%,-50%);'>"
            f"{label}</div>"
        )
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(html=icon_html, icon_size=(0, 0), icon_anchor=(0, 0)),
            interactive=False,
        ).add_to(bubble_layer)

    bubble_layer.add_to(fmap)
    cmap.add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)

    # Legend for the bubbles
    fmap.get_root().html.add_child(folium.Element(f"""
    <div style="position: fixed; bottom: 20px; left: 20px; background: white; padding: 10px;
                border: 1px solid #888; border-radius: 4px; font-size: 12px; z-index: 9999;
                max-width: 240px;">
      <b>Bubble legend</b><br>
      Size: |net change %| (max {PCT_MAX:.1f}%).<br>
      <span style="color:#1a9850;">●</span> green: positive net change<br>
      <span style="color:#d73027;">●</span> red: negative net change<br>
      <span style="color:#888888;">●</span> grey: no change / no data
    </div>
    """))

    fmap.save(str(OUT_DIR / output_name))
    print(f"  wrote {output_name}")


#%% 5. Plotly map builder

def build_plotly_map(value_col: str, value_label: str, output_name: str):
    m_data = metrics.dropna(subset=[value_col]).copy()
    vals = m_data[value_col]
    if (vals.min() < 0) and (vals.max() > 0):
        bound = max(abs(vals.quantile(0.05)), abs(vals.quantile(0.95)))
        rng = (-bound, bound)
        scale = "RdBu"
    else:
        rng = (vals.quantile(0.05), vals.quantile(0.95))
        scale = "Reds" if vals.min() >= 0 else "Blues_r"

    fig = px.choropleth_map(
        m_data,
        geojson=geojson,
        locations="KommuneCode",
        featureidkey="properties.kode",
        color=value_col,
        color_continuous_scale=scale,
        range_color=rng,
        map_style="carto-positron",
        zoom=5.8, center={"lat": 56.0, "lon": 10.5},
        opacity=0.70,
        hover_name="KommuneName",
        hover_data={
            "KommuneCode": False,
            value_col: ":+.2f",
            "net_total": ":+,",
            "net_pct": ":+.2f",
        },
        labels={value_col: value_label, "net_total": "Net total (units)",
                "net_pct": "Net change (%)"},
    )

    # Build bubbles. Split into green/red/grey so legend is informative.
    bubble_rows = []
    for _, row in metrics.iterrows():
        code = row["KommuneCode"]
        if code not in centroids:
            continue
        lat, lon = centroids[code]
        np_val = row["net_pct"]
        bubble_rows.append({
            "lat": lat, "lon": lon,
            "net_pct": np_val,
            "radius": bubble_radius(np_val),
            "color": bubble_color(np_val),
            "label": bubble_label(np_val),
            "sign": ("positive" if pd.notna(np_val) and np_val > 0
                     else "negative" if pd.notna(np_val) and np_val < 0
                     else "zero / no data"),
        })
    bdf = pd.DataFrame(bubble_rows)

    for sign, color, label in [("positive", "#1a9850", "Net change ↑"),
                               ("negative", "#d73027", "Net change ↓"),
                               ("zero / no data", "#888888", "No change / no data")]:
        sub = bdf[bdf["sign"] == sign]
        if len(sub) == 0:
            continue
        # Plotly Scattermap accepts an array of sizes per marker
        fig.add_trace(go.Scattermap(
            lat=sub["lat"], lon=sub["lon"],
            mode="markers+text",
            marker=dict(size=sub["radius"] * 2,  # plotly size is diameter-ish
                        color=color, opacity=0.6),
            text=sub["label"],
            textfont=dict(size=11, color="white"),
            textposition="middle center",
            name=label,
            hoverinfo="skip",  # bubbles have no hover; polygon hover wins
        ))

    fig.update_layout(
        title=f"{value_label}, 2008–2024",
        margin=dict(l=0, r=0, t=50, b=0),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01,
                    bgcolor="rgba(255,255,255,0.85)"),
        height=750,
    )
    fig.write_html(OUT_DIR / output_name, include_plotlyjs="cdn", full_html=True)
    print(f"  wrote {output_name}")


#%% 6. Build all four mappings

build_folium_map("pop_pct", "Population change 2008–2024 (%)", "map_population_folium.html")
build_plotly_map("pop_pct", "Population change 2008–2024 (%)", "map_population_plotly.html")

build_folium_map("income_pct", "Avg income change 2008–2024 (%)", "map_income_folium.html")
build_plotly_map("income_pct", "Avg income change 2008–2024 (%)", "map_income_plotly.html")
