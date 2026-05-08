import urllib.request
import json
import pandas as pd
import plotly.express as px
import plotly.colors
import dash
from dash import dcc, html, Input, Output, ctx

# ==========================================
# 1. CONFIGURATION & DATA PREPARATION
# ==========================================
DATA_PATH = "src/Part1/data/Part1_merged_dataset.csv"
GEOJSON_URL = "https://raw.githubusercontent.com/codeforgermany/click_that_hood/main/public/data/denmark-municipalities.geojson"

df = pd.read_csv(DATA_PATH)
df['Municipality'] = df['Municipality'].str.replace(' Kommune', '', regex=False)

MIN_INCOME = df['Average Income'].min()
MAX_INCOME = df['Average Income'].max()

min_str = f"{MIN_INCOME:,.0f}".replace(",", " ")
max_str = f"{MAX_INCOME:,.0f}".replace(",", " ")

# ==========================================
# 2. GEOJSON FETCHING & ID NORMALIZATION
# ==========================================
def normalize_name(name):
    if not isinstance(name, str): return ""
    name = name.lower()
    name = name.replace("kommune", "").replace("municipality", "")
    name = name.replace("aa", "å").replace("oe", "ø").replace("ae", "æ")
    name = name.replace("-", "").replace(" ", "")
    
    if "copenhagen" in name or "københavn" in name: return "københavn"
    if name.startswith("vesthimmerland"): return "vesthimmerland"
    if name.startswith("nordfyn"): return "nordfyn"
    if name.startswith("bornholm"): return "bornholm"
    return name

with urllib.request.urlopen(GEOJSON_URL) as response:
    dk_geojson = json.loads(response.read())

csv_munis = df['Municipality'].unique()
norm_to_csv = {normalize_name(m): m for m in csv_munis}

for feature in dk_geojson['features']:
    geo_label = feature['properties'].get('name', '')
    norm_geo = normalize_name(geo_label)
    feature['id'] = norm_to_csv.get(norm_geo, geo_label)


# ==========================================
# 3. DASH APP LAYOUT
# ==========================================
app = dash.Dash(__name__)
server = app.server

BG_COLOR = "#f4f6f9"
CARD_STYLE = {
    'background-color': 'white',
    'padding': '20px',
    'border-radius': '12px',
    'box-shadow': '0 4px 10px rgba(0,0,0,0.05)',
    'display': 'flex',
    'flex-direction': 'column'
}

PLOT_CONTAINER_STYLE = {
    'flex-grow': '1', 
    'border': '1px solid #d1d5db', 
    'border-radius': '8px',        
    'padding': '10px',             
    'background-color': '#fafafa'  
}

app.layout = html.Div(style={
    'font-family': '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', 
    'background-color': BG_COLOR, 
    'min-height': '100vh',
    'padding': '30px'
}, children=[
    
    html.H1(
        "Employment, income and education across municipalities in Denmark", 
        style={'text-align': 'center', 'color': '#2c3e50', 'margin-top': '0', 'margin-bottom': '30px', 'font-weight': '600'}
    ),
    
    html.Div(style={**CARD_STYLE, 'width': '85%', 'margin': '0 auto 30px auto', 'padding': '20px 40px'}, children=[
        html.H4("Select Timeline Year:", style={'margin': '0 0 15px 0', 'color': '#34495e', 'font-weight': '500'}),
        dcc.Slider(
            id='year-slider',
            min=df['Year'].min(),
            max=df['Year'].max(),
            value=df['Year'].max(),
            marks={str(year): {'label': str(year), 'style': {'font-size': '14px'}} for year in df['Year'].unique()},
            step=None,
            included=False
        )
    ]),

    html.Div(style={**CARD_STYLE, 'width': '95%', 'margin': '0 auto'}, children=[
        
        html.H3(
            "Geographic & Demographic Income Distribution", 
            style={'margin': '0 0 20px 0', 'color': '#2c3e50', 'text-align': 'center'}
        ),
        
        html.Div(style={
            'display': 'flex', 
            'flex-direction': 'row', 
            'height': '60vh'
        }, children=[
            
            html.Div(style={
                'display': 'flex', 
                'flex-direction': 'row', 
                'justify-content': 'space-between',
                'gap': '20px', 
                'flex-grow': '1', 
                'padding-right': '20px',
            }, children=[
                html.Div(style=PLOT_CONTAINER_STYLE, children=[
                    dcc.Graph(
                        id='dk-map',
                        style={'height': '100%'},
                        config={
                            'displaylogo': False
                        }
                    )
                ]),
                html.Div(style=PLOT_CONTAINER_STYLE, children=[
                    dcc.Graph(
                        id='ternary-plot', 
                        style={'height': '100%'},
                        config={
                            'displaylogo': False
                        }
                    )
                ])
            ]),

            html.Div(style={
                'display': 'flex',
                'flex-direction': 'column',
                'align-items': 'center',
                'justify-content': 'center',
                'width': '100px', 
                'border-left': '1px solid #eaeaea', 
                'padding-left': '20px'
            }, children=[
                html.Span("Average", style={'color': '#2c3e50', 'font-weight': '600', 'font-size': '14px'}),
                html.Span("Income", style={'color': '#2c3e50', 'font-weight': '600', 'font-size': '14px', 'margin-bottom': '15px'}),
                html.Span(f"{max_str}", style={'color': '#555', 'font-size': '13px', 'font-weight': '500'}),
                html.Span("kr", style={'color': '#555', 'font-size': '12px', 'margin-bottom': '8px'}),
                
                html.Div(style={
                    'background': 'linear-gradient(to top, #fff5f0, #fee0d2, #fcbba1, #fc9272, #fb6a4a, #ef3b2c, #cb181d, #a50f15, #67000d)',
                    'height': '300px', 
                    'width': '16px',
                    'border-radius': '10px',
                    'box-shadow': 'inset 0 1px 3px rgba(0,0,0,0.2)'
                }),
                
                html.Span("kr", style={'color': '#555', 'font-size': '12px', 'margin-top': '8px'}),
                html.Span(f"{min_str}", style={'color': '#555', 'font-size': '13px', 'font-weight': '500'})
            ])
            
        ])
    ])
])


# ==========================================
# 4. DASH CALLBACKS & INTERACTIVITY
# ==========================================
@app.callback(
    [Output('dk-map', 'figure'),
     Output('ternary-plot', 'figure')],
    [Input('dk-map', 'clickData'),
     Input('dk-map', 'selectedData'),
     Input('ternary-plot', 'selectedData'),
     Input('year-slider', 'value')]
)
def update_plots(map_click, map_select, ternary_select, selected_year):
    plot_df = df[df['Year'] == selected_year].copy()

    total_ratio = plot_df['Employed_Ratio'] + plot_df['Unemployed_Ratio'] + plot_df['Enrolled_Ratio']
    plot_df['Employed_Ratio'] = plot_df['Employed_Ratio'] / total_ratio
    plot_df['Unemployed_Ratio'] = plot_df['Unemployed_Ratio'] / total_ratio
    plot_df['Enrolled_Ratio'] = plot_df['Enrolled_Ratio'] / total_ratio

    trigger_id = ctx.triggered_id
    selected_munis = plot_df['Municipality'].tolist()

    if trigger_id == 'dk-map':
        if map_select and len(map_select['points']) > 0:
            selected_munis = [p['location'] for p in map_select['points']]
        elif map_click:
            selected_munis = [map_click['points'][0]['location']]
            
    elif trigger_id == 'ternary-plot' and ternary_select:
        selected_munis = [p['customdata'][0] for p in ternary_select['points']]

    plot_df['Opacity'] = plot_df['Municipality'].apply(
        lambda x: 1.0 if x in selected_munis else 0.10
    )

    # Calculate exact colorscale hex values for tooltips
    norm_income = (plot_df['Average Income'] - MIN_INCOME) / (MAX_INCOME - MIN_INCOME)
    hover_bg_colors = plotly.colors.sample_colorscale('Reds', list(norm_income))

    # --- Generate Map ---
    fig_map = px.choropleth_map(
        plot_df, geojson=dk_geojson, locations="Municipality", 
        color="Average Income", color_continuous_scale="Reds",
        range_color=[MIN_INCOME, MAX_INCOME], map_style="carto-positron",
        zoom=5.5, center={"lat": 56.2639, "lon": 9.5018}, 
        hover_name="Municipality", 
        custom_data=['Employed_Ratio', 'Unemployed_Ratio', 'Enrolled_Ratio'] 
    )
    
    fig_map.update_traces(
        marker=dict(opacity=plot_df['Opacity'], line=dict(width=0.5, color='gray')),
        hovertemplate=(
            "<b>%{hovertext}</b><br><br>" +
            "Employed: %{customdata[0]:.1%}<br>" +
            "Unemployed: %{customdata[1]:.1%}<br>" +
            "Enrolled: %{customdata[2]:.1%}<br>" +
            "<br><b>Avg Income: %{z:,.0f} kr</b>" +
            "<extra></extra>"
        ),
        hoverlabel=dict(bgcolor=hover_bg_colors) 
    )
    
    fig_map.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0}, 
        clickmode='event+select',
        coloraxis_showscale=False, 
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        uirevision='constant'  
    )

    # --- Generate Ternary Plot ---
    fig_ternary = px.scatter_ternary(
        plot_df, a="Employed_Ratio", b="Unemployed_Ratio", c="Enrolled_Ratio",
        hover_name="Municipality", color="Average Income",
        color_continuous_scale="Reds", range_color=[MIN_INCOME, MAX_INCOME], 
        custom_data=['Municipality'],
        labels={"Employed_Ratio": "", "Unemployed_Ratio": "", "Enrolled_Ratio": ""}
    )
    
    is_selection_active = len(selected_munis) < len(plot_df)
    marker_size = 14 if is_selection_active else 9

    fig_ternary.update_traces(
        marker=dict(
            opacity=plot_df['Opacity'], size=marker_size, line=dict(width=1, color='DarkSlateGrey')
        ),
        selector=dict(type='scatterternary'),
        hovertemplate=(
            "<b>%{hovertext}</b><br><br>" +
            "Employed: %{a:.1%}<br>" +
            "Unemployed: %{b:.1%}<br>" +
            "Enrolled: %{c:.1%}<br>" +
            "<br><b>Avg Income: %{marker.color:,.0f} kr</b>" +
            "<extra></extra>"
        )
    )
    
    fig_ternary.update_layout(
        margin={"r": 60, "t": 40, "l": 60, "b": 60}, 
        coloraxis_showscale=False, 
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        uirevision='constant', 
        ternary=dict(
            aaxis=dict(title_text="", tickfont=dict(size=11, color='#555')),
            baxis=dict(title_text="", tickfont=dict(size=11, color='#555')),
            caxis=dict(title_text="", tickfont=dict(size=11, color='#555'))
        )
    )

    # Custom annotations for edges
    fig_ternary.add_annotation(text="Enrolled Ratio", x=0.5, y=-0.15, xref="paper", yref="paper", showarrow=False, font=dict(size=15, color='#2c3e50'))
    fig_ternary.add_annotation(text="Unemployed Ratio", x=0.09, y=0.55, xref="paper", yref="paper", textangle=-60, showarrow=False, font=dict(size=15, color='#2c3e50'))
    fig_ternary.add_annotation(text="Employed Ratio", x=0.91, y=0.55, xref="paper", yref="paper", textangle=60, showarrow=False, font=dict(size=15, color='#2c3e50'))

    return fig_map, fig_ternary

# ==========================================
# 5. SERVER EXECUTION
# ==========================================
if __name__ == '__main__':
    app.run(debug=True)