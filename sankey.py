import os
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output


# get data
edu = pd.read_csv("data/HFUDD16_Final_Readable.csv")
inc = pd.read_csv("data/IFOR35_Final_Readable.csv")

# =========================================================
# 1. CLEAN DATA
# =========================================================

edu_dash = edu.copy()

text_cols = [
    "Region_Name",
    "Education_Level",
    "Socioeconomic_Status",
    "Industry_Group",
    "Age_Group"
]

for col in text_cols:
    edu_dash[col] = edu_dash[col].astype(str).str.strip()

edu_dash["Year"] = pd.to_numeric(edu_dash["Year"], errors="coerce")
edu_dash["Count"] = pd.to_numeric(edu_dash["Count"], errors="coerce")

edu_dash = edu_dash.dropna(subset=[
    "Region_Name",
    "Education_Level",
    "Socioeconomic_Status",
    "Industry_Group",
    "Age_Group",
    "Year",
    "Count"
])

edu_dash["Year"] = edu_dash["Year"].astype(int)
edu_dash = edu_dash[edu_dash["Count"] > 0].copy()


# =========================================================
# 2. SANKEY FUNCTION
# Education -> Status -> Industry -> Education
# =========================================================

def make_education_status_industry_education_sankey(
    edu,
    municipality="All municipalities",
    year=None,
    age_group="All",
    value_mode="proportion",   # "count" or "proportion"
    min_value=0,
    title_suffix=""
):
    d = edu.copy()

    if municipality != "All municipalities":
        d = d[d["Region_Name"] == municipality]

    if year is not None:
        d = d[d["Year"] == year]

    if age_group != "All":
        d = d[d["Age_Group"] == age_group]

    if d.empty:
        fig = go.Figure()
        fig.update_layout(
            title=f"No data for {municipality}",
            width=650,
            height=430
        )
        return fig

    d["Education_Level"] = d["Education_Level"].astype(str).str.strip()
    d["Socioeconomic_Status"] = d["Socioeconomic_Status"].astype(str).str.strip()
    d["Industry_Group_Clean"] = d["Industry_Group"].astype(str).str.strip()

    missing_industry = (
        d["Industry_Group_Clean"].isna()
        | (d["Industry_Group_Clean"] == "")
        | d["Industry_Group_Clean"].str.lower().isin([
            "nan",
            "none",
            "not stated",
            "not applicable"
        ])
    )

    d.loc[missing_industry, "Industry_Group_Clean"] = "No industry / not employed"

    non_employed_statuses = [
        "Unemployed",
        "Outside the labour force",
        "Enrolled in education"
    ]

    d.loc[
        d["Socioeconomic_Status"].isin(non_employed_statuses),
        "Industry_Group_Clean"
    ] = "No industry / not employed"

    # =====================================================
    # Counts vs proportions
    # =====================================================

    total_count = d["Count"].sum()

    if value_mode == "proportion":
        d["Sankey_Value"] = d["Count"] / total_count
        title_value_note = "Proportions"
        node_hovertemplate = "%{label}<br>Total share: %{value:.1%}<extra></extra>"
        link_hovertemplate = (
            "%{source.label} → %{target.label}<br>"
            "Share of total: %{value:.1%}<extra></extra>"
        )
    else:
        d["Sankey_Value"] = d["Count"]
        title_value_note = "Counts"
        node_hovertemplate = "%{label}<br>Total count: %{value:,.0f}<extra></extra>"
        link_hovertemplate = (
            "%{source.label} → %{target.label}<br>"
            "Count: %{value:,.0f}<extra></extra>"
        )

    # Duplicate education layer so Plotly does not merge start and end education nodes
    d["Education_Start"] = d["Education_Level"] + " [education start]"
    d["Education_End"] = d["Education_Level"] + " [education end]"

    # Flow 1: Education -> Status
    flow1 = (
        d.groupby(["Education_Start", "Socioeconomic_Status"], as_index=False)["Sankey_Value"]
        .sum()
        .rename(columns={
            "Education_Start": "source",
            "Socioeconomic_Status": "target",
            "Sankey_Value": "value"
        })
    )

    # Flow 2: Status -> Industry
    flow2 = (
        d.groupby(["Socioeconomic_Status", "Industry_Group_Clean"], as_index=False)["Sankey_Value"]
        .sum()
        .rename(columns={
            "Socioeconomic_Status": "source",
            "Industry_Group_Clean": "target",
            "Sankey_Value": "value"
        })
    )

    # Flow 3: Industry -> Education copy
    flow3 = (
        d.groupby(["Industry_Group_Clean", "Education_End"], as_index=False)["Sankey_Value"]
        .sum()
        .rename(columns={
            "Industry_Group_Clean": "source",
            "Education_End": "target",
            "Sankey_Value": "value"
        })
    )

    links = pd.concat([flow1, flow2, flow3], ignore_index=True)
    links = links[links["value"] > min_value].copy()

    if links.empty:
        fig = go.Figure()
        fig.update_layout(
            title=f"No links for {municipality}",
            width=650,
            height=430
        )
        return fig

    labels_raw = pd.Index(pd.concat([links["source"], links["target"]]).unique())
    label_to_id = {label: i for i, label in enumerate(labels_raw)}

    labels_display = [
        label
        .replace(" [education start]", "")
        .replace(" [education end]", "")
        for label in labels_raw
    ]

    title = f"{municipality}<br>{year} — {title_value_note}"

    if age_group != "All":
        title += f", {age_group}"

    if title_suffix:
        title += f"<br>{title_suffix}"

    fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node=dict(
            pad=4,
            thickness=6,
            line=dict(width=0.2),
            label=labels_display,
            hovertemplate=node_hovertemplate
        ),
        link=dict(
            source=links["source"].map(label_to_id),
            target=links["target"].map(label_to_id),
            value=links["value"],
            hovertemplate=link_hovertemplate
        )
    )])

    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            xanchor="center",
            font=dict(size=12)
        ),
        font_size=7,
        width=650,
        height=430,
        margin=dict(l=2, r=2, t=55, b=5)
    )

    return fig


# =========================================================
# 3. DASH OPTIONS
# =========================================================

municipalities = ["All municipalities"] + sorted(edu_dash["Region_Name"].dropna().unique())
age_groups = ["All"] + sorted(edu_dash["Age_Group"].dropna().unique())

years = sorted(edu_dash["Year"].dropna().astype(int).unique())
initial_year = years[-1]


# =========================================================
# 4. DASH APP
# =========================================================

app = Dash(__name__)

app.layout = html.Div(
    style={
        "fontFamily": "Arial, sans-serif",
        "maxWidth": "1350px",
        "margin": "0 auto",
        "padding": "6px"
    },
    children=[
        html.H2(
            "Municipality comparison: Education → Status → Industry → Education",
            style={
                "textAlign": "center",
                "fontSize": "18px",
                "marginBottom": "6px"
            }
        ),

        html.Div(
            style={
                "display": "grid",
                "gridTemplateColumns": "1fr 1fr 0.8fr 0.8fr",
                "gap": "10px",
                "fontSize": "12px",
                "marginBottom": "8px"
            },
            children=[
                html.Div([
                    html.Label("Municipality A"),
                    dcc.Dropdown(
                        id="municipality-a",
                        options=[{"label": m, "value": m} for m in municipalities],
                        value="Lyngby-Taarbæk" if "Lyngby-Taarbæk" in municipalities else municipalities[0],
                        clearable=False,
                        style={"fontSize": "12px"}
                    )
                ]),

                html.Div([
                    html.Label("Municipality B"),
                    dcc.Dropdown(
                        id="municipality-b",
                        options=[{"label": m, "value": m} for m in municipalities],
                        value="Kolding" if "Kolding" in municipalities else municipalities[1],
                        clearable=False,
                        style={"fontSize": "12px"}
                    )
                ]),

                html.Div([
                    html.Label("Age group"),
                    dcc.Dropdown(
                        id="age-group-dropdown",
                        options=[{"label": a, "value": a} for a in age_groups],
                        value="All",
                        clearable=False,
                        style={"fontSize": "12px"}
                    )
                ]),

                html.Div([
                    html.Label("Value mode"),
                    dcc.RadioItems(
                        id="value-mode",
                        options=[
                            {"label": "Counts", "value": "count"},
                            {"label": "Proportions", "value": "proportion"}
                        ],
                        value="proportion",
                        inline=False,
                        style={"fontSize": "12px"}
                    )
                ])
            ]
        ),

        html.Div(
            style={
                "fontSize": "12px",
                "marginBottom": "4px"
            },
            children=[
                html.Label("Year"),
                dcc.Slider(
                    id="year-slider",
                    min=years[0],
                    max=years[-1],
                    step=None,
                    value=initial_year,
                    marks={
                        int(y): {
                            "label": str(y),
                            "style": {"fontSize": "10px"}
                        }
                        for y in years
                    },
                    tooltip={
                        "placement": "bottom",
                        "always_visible": False
                    }
                )
            ]
        ),

        html.Div(
            style={
                "display": "grid",
                "gridTemplateColumns": "1fr 1fr",
                "gap": "4px"
            },
            children=[
                dcc.Graph(
                    id="sankey-a",
                    config={"displayModeBar": False, "responsive": True},
                    style={"height": "450px"}
                ),
                dcc.Graph(
                    id="sankey-b",
                    config={"displayModeBar": False, "responsive": True},
                    style={"height": "450px"}
                )
            ]
        )
    ]
)


# =========================================================
# 5. UPDATE BOTH SANKEYS
# =========================================================

@app.callback(
    Output("sankey-a", "figure"),
    Output("sankey-b", "figure"),
    Input("municipality-a", "value"),
    Input("municipality-b", "value"),
    Input("year-slider", "value"),
    Input("age-group-dropdown", "value"),
    Input("value-mode", "value")
)
def update_comparison(muni_a, muni_b, year, age_group, value_mode):
    fig_a = make_education_status_industry_education_sankey(
        edu=edu_dash,
        municipality=muni_a,
        year=int(year),
        age_group=age_group,
        value_mode=value_mode,
        min_value=0
    )

    fig_b = make_education_status_industry_education_sankey(
        edu=edu_dash,
        municipality=muni_b,
        year=int(year),
        age_group=age_group,
        value_mode=value_mode,
        min_value=0
    )

    return fig_a, fig_b


# =========================================================
# 6. SERVER FOR DEPLOYMENT
# =========================================================

server = app.server

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8051))
    app.run(host="0.0.0.0", port=port, debug=False)