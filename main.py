import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
from babel.numbers import format_currency
import dash
import dash_bootstrap_components as dbc

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP]
)

# --- Daten laden und vorverarbeiten ---
cols = ['EV/FV', 'TEXT_KONTO', 'TEXT_VASTELLE', 'Erfolg 2022', 'BVA 2023', 'BVA 2024']
df = pd.read_csv('dataset.csv', usecols=cols)

# Spalten umbenennen
rename_map = {
    'Erfolg 2022': '2022',
    'BVA 2023':    '2023',
    'BVA 2024':    '2024',
    'TEXT_KONTO':  'Konto',
    'TEXT_VASTELLE': 'Kostenstelle'
}
df = df.rename(columns=rename_map)

# Nur FV-Datensätze behalten und sortieren
df = (
    df[df['EV/FV'] == 'FV']
      .drop(columns=['EV/FV'])
      .sort_values(['Konto', 'Kostenstelle'])
      .reset_index(drop=True)
)

# Budget-Spalten in numerische Werte umwandeln (int)
for col in ['2022', '2023', '2024']:
    df[col] = (
        df[col]
        .astype(str)
        .str.replace(r"\.", "", regex=True)
        .str.split(',', expand=True)[0]
        .astype('int64')
    )

# Liste verfügbarer Jahre automatisch sortiert
years_options = sorted(['2022', '2023', '2024'])

# --- Kompakte Euro-Formatierung inkl. Milliarden und Billionen ---
def format_currency_compact(n, currency='EUR', locale='de_DE'):
    abs_n = abs(n)
    sign = '-' if n < 0 else ''
    if abs_n >= 1_000_000_000_000:
        val = abs_n / 1_000_000_000_000
        suffix = 'Bio.'
    elif abs_n >= 1_000_000_000:
        val = abs_n / 1_000_000_000
        suffix = 'Mrd.'
    elif abs_n >= 1_000_000:
        val = abs_n / 1_000_000
        suffix = 'Mio.'
    else:
        return format_currency(n, currency, locale=locale)
    formatted = format_currency(val, currency, locale=locale, format='#,##0.0¤')
    # Entferne das Symbol aus formatted und hänge Suffix an
    return f"{sign}{formatted.replace('€', '').strip()} {suffix} €"

# --- Layout mit kombiniertem Filterbar und ActionButtonGroup für Konten-Modus ---
app.layout = dbc.Container(fluid=True, children=[
    # Header
    dbc.Row(
        dbc.Col(html.H1("Niklas STADLER (wi24m061) Dashboard", className="text-center mb-4"), width=12)
    ),
    dbc.Row(
            dbc.Col(
                html.Ul([
                    html.Li("Welche Konten weisen die höchsten Budgetsätze auf?"),
                    html.Li("Wie verteilt sich das Budget auf die wichtigsten Kostenstellen?"),
                    html.Li("Wie hat sich der Gesamtbudgetansatz bzw. das Ergebnis entwickelt?")
                ], className="mb-4"),
                width=12
            )
        ),

    # Kombinierte Filterbar
    dbc.Row(
        dbc.Card(
            dbc.CardBody(
                dbc.Row([
                    # Jahr-Dropdown
                    dbc.Col([
                        html.Label("Budget-Jahre:"),
                        dcc.Dropdown(
                            id='year-dropdown',
                            options=[{'label': y, 'value': y} for y in years_options],
                            value=years_options,
                            multi=True,
                            clearable=False
                        )
                    ], md=4),

                    # Konten-Modus als Action ButtonGroup (RadioItems)
                    dbc.Col([
                        html.Label("Konten-Modus:"),
                        dbc.RadioItems(
                            id='top-toggle',
                            options=[
                                {'label': 'Top 10', 'value': 'top10'},
                                {'label': 'Lowest 10', 'value': 'low10'}
                            ],
                            value='top10',
                            inline=True,
                            className="btn-group",
                            inputClassName="btn-check",
                            labelClassName="btn btn-outline-primary",
                            labelCheckedClassName="active"
                        )
                    ], md=4),

                    # Reset-Button
                    dbc.Col(
                        dbc.Button("Drilldown zurücksetzen", id='clear-btn', color='warning', className='mt-4'),
                        md=4, className="text-end"
                    )
                ], align="center", justify="between")
            ),
            className="mb-4 shadow-sm"
        ),
        className="mb-4"
    ),

    # Erste zwei Diagramme nebeneinander
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id='budget-trend'))), md=6, className="mb-4 shadow-sm"),
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id='top-accounts'))), md=6, className="mb-4 shadow-sm")
    ]),

    # Treemap-Kostenstellen
    dbc.Row(
        dbc.Col(
            dbc.Card(dbc.CardBody(dcc.Graph(id='cost-centers', style={'height': '600px'}))),
            width=12
        )
    )
])

@app.callback(
    Output('top-accounts', 'figure'),
    Input('year-dropdown', 'value'),
    Input('top-toggle', 'value'),
    Input('top-accounts', 'clickData'),
    Input('cost-centers', 'clickData'),
    Input('clear-btn', 'n_clicks')
)
def update_top_accounts(selected_years, mode, accountClick, costClick, clear_clicks):
    ctx = dash.callback_context
    prop = ctx.triggered[0]['prop_id'] if ctx.triggered else None

    if prop and prop.startswith('clear-btn'):
        accountClick = None
        costClick    = None
    elif prop and prop.startswith('cost-centers.clickData'):
        accountClick = None

    years = sorted(selected_years)
    if costClick:
        ks = costClick['points'][0]['label']
        df_filtered = df[df['Kostenstelle'] == ks]
    else:
        df_filtered = df

    df_sum = df_filtered.groupby('Konto', as_index=False)[years].sum()
    df_sum['Summe'] = df_sum[years].sum(axis=1)
    df_top = (df_sum.nlargest(10, 'Summe') if mode=='top10'
              else df_sum.nsmallest(10, 'Summe'))
    df_top['Label'] = df_top['Summe'].apply(format_currency_compact)

    selected_konto = accountClick['points'][0]['y'] if accountClick else None
    # Standard blau, hervorgehoben rot
    colors = ['red' if k==selected_konto else '#636efa' for k in df_top['Konto']]

    title_suffix = f" für {ks}" if costClick else ""
    fig = px.bar(
        df_top, x='Summe', y='Konto', orientation='h',
        title=(
            f"Konten ({'Top 10' if mode=='top10' else 'Lowest 10'}) "
            f"Budget ({', '.join(years)}){title_suffix}"
        ),
        labels={'Konto':'Konto','Summe':'Budget-Summe'}
    )
    fig.update_traces(marker_color=colors, text=df_top['Label'], textposition='auto')
    fig.update_layout(xaxis=dict(showticklabels=False, showgrid=False, zeroline=False))
    return fig

@app.callback(
    Output('cost-centers', 'figure'),
    Input('year-dropdown', 'value'),
    Input('top-accounts', 'clickData'),
    Input('clear-btn', 'n_clicks')
)
def update_cost_centers(selected_years, accountClick, clear_clicks):
    ctx = dash.callback_context
    if ctx.triggered and ctx.triggered[0]['prop_id'].startswith('clear-btn'):
        accountClick = None

    years = sorted(selected_years)
    if accountClick:
        konto = accountClick['points'][0]['y']
        df_filter = df[df['Konto'] == konto]
    else:
        df_filter = df

    df_cc = df_filter.groupby('Kostenstelle', as_index=False)[years].sum()
    df_cc['Summe'] = df_cc[years].sum(axis=1)
    df_cc = df_cc.sort_values('Summe', ascending=False).head(10)
    df_cc['Label'] = df_cc['Summe'].apply(format_currency_compact)

    title = (
        f"Kostenstellen für {konto}" if accountClick
        else f"Budget-Verteilung auf Kostenstellen ({', '.join(years)})"
    )

    # Discrete colors, damit auch bei nur einem Eintrag eine Farbe auftaucht
    fig = px.treemap(
        df_cc,
        path=['Kostenstelle'],
        values='Summe',
        title=title,
        custom_data=['Label'],
        color='Kostenstelle',  # Kategorie-basiert färben
        color_discrete_sequence=px.colors.qualitative.Plotly
    )
    fig.update_traces(
        texttemplate='%{label}<br>%{customdata[0]}',
        hovertemplate='%{label}: %{customdata[0]}'
    )
    fig.update_layout(height=600)
    return fig


@app.callback(
    Output('budget-trend', 'figure'),
    Input('year-dropdown', 'value'),
    Input('cost-centers', 'clickData'),
    Input('top-accounts', 'clickData'),
    Input('clear-btn', 'n_clicks')
)
def update_budget_trend(selected_years, costClick, accountClick, clear_clicks):
    ctx = dash.callback_context
    prop = ctx.triggered[0]['prop_id'] if ctx.triggered else None

    # Clear-Knopf: beides zurücksetzen
    if prop and prop.startswith('clear-btn'):
        costClick    = None
        accountClick = None
    # Klick in Top-Accounts: Kostenstellen-Drilldown zurücksetzen
    elif prop and prop.startswith('top-accounts.clickData'):
        costClick = None
    # Klick in Kostenstellen: Konto-Drilldown zurücksetzen
    elif prop and prop.startswith('cost-centers.clickData'):
        accountClick = None

    years = sorted(selected_years)
    # Priorität: Konto → Kostenstelle → Gesamt
    if accountClick:
        kont = accountClick['points'][0]['y']
        df_trend = df[df['Konto'] == kont]
        title    = f"Konto-Entwicklung {kont}"
    elif costClick:
        ks = costClick['points'][0]['label']
        df_trend = df[df['Kostenstelle'] == ks]
        title    = f"Kostenstellen-Entwicklung {ks}"
    else:
        df_trend = df
        title    = f"Gesamtbudget-Entwicklung ({', '.join(years)})"

    total = pd.DataFrame({
        'Jahr':   years,
        'Budget': [df_trend[y].sum() for y in years]
    })
    total['Hover'] = total['Budget'].apply(format_currency_compact)

    fig = px.line(total, x='Jahr', y='Budget', title=title)
    fig.update_traces(
        mode='markers+lines',
        hovertemplate='%{x}: %{customdata}',
        customdata=total['Hover']
    )
    tick_vals  = total['Budget']
    tick_texts = total['Budget'].apply(format_currency_compact)
    fig.update_layout(yaxis=dict(tickmode='array', tickvals=tick_vals, ticktext=tick_texts))
    return fig

# --- Server starten ---
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80)