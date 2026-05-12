#%% Import libraries
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from scipy import stats as sp_stats

#%% Load and prepare data
PANEL_PATH = Path("data/kommune_year_panel.csv")

panel = pd.read_csv(PANEL_PATH, dtype={"KommuneCode": str})
panel["KommuneCode"] = panel["KommuneCode"].str.zfill(4)

geojson = requests.get(
    "https://api.dataforsyningen.dk/kommuner?format=geojson", timeout=30
).json()

#%% Compute one-row-per-kommune summary
def first_last(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Return first-year and last-year values per kommune for a given column."""
    first = df.sort_values("year").groupby("KommuneCode").first()[col].rename(f"{col}_start")
    last = df.sort_values("year").groupby("KommuneCode").last()[col].rename(f"{col}_end")
    return pd.concat([first, last], axis=1)

agg = pd.concat([
    first_last(panel, "active"),
    first_last(panel, "population"),
    first_last(panel, "average_income"),
    panel.groupby("KommuneCode")[["openings", "closings", "net_change"]].sum(),
    panel.groupby("KommuneCode")["KommuneName"].first(),
], axis=1).reset_index()

# Percent changes (guard against zero-stock kommuner)
agg["active_pct"] = np.where(
    agg["active_start"] > 0,
    100 * (agg["active_end"] - agg["active_start"]) / agg["active_start"],
    np.nan,
)
agg["pop_pct"] = 100 * (agg["population_end"] - agg["population_start"]) / agg["population_start"]
agg["income_pct"] = 100 * (agg["average_income_end"] - agg["average_income_start"]) / agg["average_income_start"]



#%% Scatter: net unit change vs population change

scatter_df = agg.dropna(subset=["active_pct", "pop_pct", "population_start"]).copy()

# Correlation + simple OLS line
r, p = sp_stats.pearsonr(scatter_df["active_pct"], scatter_df["pop_pct"])
slope, intercept = np.polyfit(scatter_df["active_pct"], scatter_df["pop_pct"], 1)
x_line = np.linspace(scatter_df["active_pct"].min(), scatter_df["active_pct"].max(), 100)
y_line = slope * x_line + intercept

# Construct the scatter plot with Plotly
fig5 = px.scatter(
    scatter_df,
    x="active_pct", y="pop_pct",
    size="population_start", color="KommuneName",
    hover_name="KommuneName",
    hover_data={
        "active_start": ":,", "active_end": ":,",
        "population_start": ":,", "population_end": ":,",
        "net_change": ":+,",
        "active_pct": ":+.1f", "pop_pct": ":+.1f",
        "KommuneName": False,
    },
    labels={
        "active_pct": "Active production units, % change 2008→2024",
        "pop_pct": "Population, % change 2008→2024",
    },
    size_max=40,
)
fig5.add_trace(go.Scatter(
    x=x_line, y=y_line, mode="lines",
    line=dict(color="black", dash="dash", width=2),
    name=f"OLS: y = {slope:.2f}x + {intercept:.2f}",
    hoverinfo="skip",
))
fig5.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)
fig5.add_vline(x=0, line_dash="dot", line_color="gray", opacity=0.5)
fig5.update_layout(
    title=(f"Do municipalities with more production units gain population?<br>"
           f"<sub>Pearson r = {r:.3f}, p = {p:.3g}, n = {len(scatter_df)}. "
           f"Dot size = 2008 population.</sub>"),
    template="plotly_white", showlegend=False, height=650,
)
# Quadrant labels
xr = scatter_df["active_pct"].abs().max() * 0.9
yr = scatter_df["pop_pct"].abs().max() * 0.9
for x, y, txt in [(xr, yr, "units ↑ pop ↑"), (-xr, yr, "units ↓ pop ↑"),
                  (-xr, -yr, "units ↓ pop ↓"), (xr, -yr, "units ↑ pop ↓")]:
    fig5.add_annotation(x=x, y=y, text=f"<i>{txt}</i>", showarrow=False,
                        font=dict(size=11, color="gray"), opacity=0.6)
fig5.write_html("data/scatter_units_vs_population.html",
                include_plotlyjs="cdn", full_html=True)