import streamlit as st
import pandas as pd
import requests
import altair as alt
import plotly.express as px
import numpy as np
import re, math, datetime as dt, pandas as pd
from functools import lru_cache
import os # 


def fmt_cop(x):
    try:
        return f"${x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return x

# ============================
# Config
# ============================
# ...
API = os.environ.get("API_URL") or st.secrets.get("API_URL", "http://127.0.0.1:8000")
# API = st.secrets.get("API_URL", "http://127.0.0.1:8000")
st.set_page_config(page_title="Dashboard de Finanzas Personales", layout="wide")

# ====== Estilo "tarjeta" para tablas (st.dataframe / st.table) ======
st.markdown("""
<style>
/* Card para cualquier tabla */
div[data-testid="stDataFrame"],
div[data-testid="stTable"] {
  background: #ffffff !important;
  border: 1px solid #e9edf3 !important;
  border-radius: 12px !important;
  box-shadow: 0 2px 8px rgba(16,24,40,.06) !important;
  padding: .6rem .8rem !important;
  margin: .5rem 0 1rem 0 !important;
  transition: box-shadow .2s ease, transform .2s ease;
}

/* Elevación en hover (sutil) */
div[data-testid="stDataFrame"]:hover,
div[data-testid="stTable"]:hover {
  box-shadow: 0 6px 16px rgba(16,24,40,.12) !important;
  transform: translateY(-1px);
}

/* Cabecera más legible */
div[data-testid="stDataFrame"] thead tr th,
div[data-testid="stTable"] thead tr th {
  background: #f6f8fb !important;
  font-weight: 700 !important;
  color: #334155 !important;
  border-bottom: 1px solid #e5e7eb !important;
}

/* Celdas */
div[data-testid="stDataFrame"] tbody tr td,
div[data-testid="stTable"] tbody tr td {
  color: #111827 !important;
  border-bottom: 1px solid #f1f5f9 !important;
}

/* Index (si lo muestras) */
div[data-testid="stDataFrame"] tbody tr td:first-child {
  color: #6b7280 !important;
}

/* Bordes redondeados internos */
div[data-testid="stDataFrame"] > div {
  border-radius: 10px !important;
}

/* Scrollbar más discreta en tablas anchas */
div[data-testid="stHorizontalBlock"] ::-webkit-scrollbar {
  height: 10px; width: 10px;
}
div[data-testid="stHorizontalBlock"] ::-webkit-scrollbar-thumb {
  background: #cbd5e1; border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ============================
# Helpers
# ============================
@st.cache_data(ttl=60)
def api_get(path: str, **params):
    url = f"{API}{path}"
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=300)
def get_months():
    series = api_get("/net_worth_series")["series"]
    months = sorted({row["month"] for row in series})
    return months

@st.cache_data(ttl=60)
def get_summary(month):
    return api_get("/summary", month=month)

@st.cache_data(ttl=60)
def get_donut(month):
    return api_get("/expenses_donut", month=month)

@st.cache_data(ttl=60)
def get_top_expenses(month, n=10):
    return api_get("/top_expenses", month=month, n=n)

@st.cache_data(ttl=60)
def get_budget_progress(month):
    return api_get("/budget_progress", month=month)

@st.cache_data(ttl=300)
def get_networth():
    return api_get("/net_worth_series")["series"]

@st.cache_data(ttl=300)
def get_inv_history():
    return api_get("/investments_history")["history"]

@st.cache_data(ttl=300)
def get_inv_alloc():
    return api_get("/investments_alloc")

@st.cache_data(ttl=300)
def get_goals():
    return api_get("/goals")["goals"]

# ============================
# Sidebar / Navigation
# ============================
st.sidebar.title("📊 Finanzas Personales")
months = get_months()
def_month = months[-1] if months else None
selected_month = st.sidebar.selectbox("Mes", months, index=len(months)-1)
page = st.sidebar.radio("Vistas", [
    "1 · Resumen", "2 · Gastos", "3 · Presupuesto",
    "4 · Patrimonio", "5 · Inversiones", "6 · Metas"
])

st.sidebar.caption(f"API: {API}")

# =============================
# Encabezado principal del Dashboard con resumen
# =============================
from datetime import datetime

hoy = datetime.now().strftime("%d/%m/%Y")

# Traemos KPIs para el mes seleccionado
s_head = get_summary(selected_month)
k_head = s_head["kpis"]
balance = float(k_head["ingresos_mes"] - k_head["gastos_mes"])
saldo_txt = "Balance positivo" if balance >= 0 else "Balance negativo"
saldo_color = "#16a34a" if balance >= 0 else "#dc2626"
saldo_icon = "▲" if balance >= 0 else "▼"

st.markdown(f"""
    <style>
    .header-card {{
        background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
        color: white;
        padding: 1.3rem 2rem;
        border-radius: 12px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.15);
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
        gap: 1rem;
        flex-wrap: wrap;
    }}
    .header-left {{ display: flex; align-items: center; gap: 1rem; }}
    .header-icon {{ font-size: 2.2rem; }}
    .header-title {{ font-size: 1.45rem; font-weight: 800; line-height: 1.15; }}
    .header-sub {{ font-size: 0.95rem; opacity: 0.9; }}
    .header-date {{ font-size: 0.85rem; opacity: 0.8; margin-top: .25rem; }}

    .header-right {{ text-align: right; }}
    .pill {{
        display: inline-flex; align-items: center; gap: .5rem;
        background: rgba(255,255,255,.10);
        border: 1px solid rgba(255,255,255,.20);
        padding: .45rem .7rem; border-radius: 999px;
        font-size: .9rem;
    }}
    .pill .dot {{
        width: .55rem; height: .55rem; border-radius: 50%;
        background: {saldo_color};
        display: inline-block;
    }}
    .pill .txt {{ opacity: .95; }}

    .pill-value {{
        font-weight: 700; margin-left: .35rem;
        color: {saldo_color};
    }}

    @media (max-width: 768px) {{
        .header-title {{ font-size: 1.2rem; }}
        .header-sub {{ font-size: .85rem; }}
    }}
    </style>

    <div class="header-card">
        <div class="header-left">
            <div class="header-icon">💰</div>
            <div>
                <div class="header-title">Plataforma de Gestión de Finanzas Personales</div>
                <div class="header-sub">Análisis integral de ingresos, gastos, inversiones y metas</div>
                <div class="header-date">Actualizado al: {hoy}</div>
                <div style="margin-top:.45rem;">
                    <span class="pill">
                        <span class="dot"></span>
                        <span class="txt">{saldo_icon} {saldo_txt}:</span>
                        <span class="pill-value">{fmt_cop(balance)}</span>
                    </span>
                </div>
            </div>
        </div>
        <div class="header-right">
            <div style="font-size:0.9rem; opacity:0.85;">Mes seleccionado</div>
            <div style="font-size:1.15rem; font-weight:700;">{selected_month}</div>
            <div style="margin-top:.35rem; font-size:.9rem; opacity:.85;">
                Ingresos: <b>{fmt_cop(k_head['ingresos_mes'])}</b> ·
                Gastos: <b>{fmt_cop(k_head['gastos_mes'])}</b>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)


# ============================
# 1) Resumen Financiero
# ============================
if page.startswith("1"):
    st.title("1 · Resumen financiero")
    # Ajuste de estilo responsivo para métricas
    st.markdown("""
        <style>
        /* =============================
        🎨 Tarjetas de métricas financieras
        ============================= */

        /* Contenedor general de métricas */
        div[data-testid="stHorizontalBlock"] > div {
            background: #f8f9fa !important;
            border-radius: 12px !important;
            padding: 1rem !important;
            margin: 0.4rem !important;
            box-shadow: 0px 2px 5px rgba(0,0,0,0.08) !important;
            transition: all 0.2s ease-in-out !important;
        }

        /* Efecto hover sutil */
        div[data-testid="stHorizontalBlock"] > div:hover {
            background: #ffffff !important;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.15) !important;
            transform: translateY(-2px) !important;
        }

        /* Valor de la métrica (número) */
        [data-testid="stMetricValue"] {
            font-size: clamp(1rem, 1.6vw, 1.8rem) !important;
            font-weight: 700 !important;
            color: #1a1a1a !important;
            text-align: center !important;
        }

        /* Etiqueta (nombre) */
        [data-testid="stMetricLabel"] {
            font-size: clamp(0.7rem, 1vw, 1rem) !important;
            color: #555 !important;
            font-weight: 600 !important;
            text-align: center !important;
            margin-bottom: 0.5rem !important;
        }

        /* Delta (variación) */
        [data-testid="stMetricDelta"] {
            font-size: clamp(0.65rem, 0.9vw, 0.85rem) !important;
            font-weight: 500 !important;
            color: #2e7d32 !important;
            text-align: center !important;
        }

        /* Alineación y espaciado del contenedor */
        div[data-testid="metric-container"] {
            text-align: center !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0.4rem 0.2rem !important;
        }

        /* Ajuste para pantallas pequeñas */
        @media (max-width: 768px) {
            div[data-testid="stHorizontalBlock"] > div {
                margin: 0.2rem !important;
                padding: 0.7rem !important;
            }
            [data-testid="stMetricValue"] {
                font-size: 1rem !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    s = get_summary(selected_month)
    k = s["kpis"]

    # KPIs en formato COP
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Ingresos (mes)", fmt_cop(k["ingresos_mes"]))
    c2.metric("Gastos (mes)", fmt_cop(k["gastos_mes"]))
    c3.metric("Neto (mes)", fmt_cop(k["neto_mes"]))
    c4.metric("Patrimonio actual", fmt_cop(k["patrimonio_actual"]))
    c5.metric("Efectivo acumulado", fmt_cop(k["efectivo_acumulado"]))
    c6.metric("Valor inversiones", fmt_cop(k["valor_inversiones"]))

    # -------- Gráfico de cascada: ingresos vs gastos --------
    wf = pd.DataFrame(s["waterfall"])
    
    name_map = {
        "Inicio": "Inicio",
        "Ingresos": "Ingresos",
        "Gastos": "Gastos",
        "Neto mes": "Neto del mes",
    }
    wf["etapa"] = wf["label"].map(name_map)
    wf["color"] = np.where(wf["value"] >= 0, "#4caf50", "#f44336")

    base = (
        alt.Chart(wf)
        .mark_bar()
        .encode(
            x=alt.X("etapa:N", title=None),
            y=alt.Y("value:Q", axis=alt.Axis(title="COP", format=",.0f")),
            color=alt.Color("color:N", legend=None, scale=None),
            tooltip=[
                alt.Tooltip("etapa:N", title="Etapa"),
                alt.Tooltip("value:Q", title="Monto", format=",.0f"),
            ],
        )
        .properties(height=320, title=f"Cascada: ingresos vs gastos ({s['month']})")
    )

    labels = (
        base.mark_text(dy=-10, color="#111")
        .encode(text=alt.Text("value:Q", format=",.0f"))
    )

    st.altair_chart(base + labels, use_container_width=True)
    st.caption(f"Registros del mes: {s['rows_mes']}")

# ============================
# 2) Análisis de Gastos
# ============================
elif page.startswith("2"):
    st.title("2 · Análisis de gastos")
    donut_raw = pd.DataFrame(get_donut(selected_month)["donut"])  # category, amount

    col1, col2 = st.columns([1,1])

    if not donut_raw.empty:
        # --- Dona con nombres en español y COP en hover ---
        df_donut = donut_raw.rename(columns={"category":"Categoría","amount":"Monto"})
        fig = px.pie(
            df_donut, names="Categoría", values="Monto", hole=0.55
        )
        # mostrar porcentaje + label en el centro
        fig.update_traces(textposition="inside", textinfo="percent+label")
        # hover con COP
        fig.update_traces(hovertemplate="<b>%{label}</b><br>Monto: %{value:,.0f}<br>% %{percent}<extra></extra>")
        col1.plotly_chart(fig, use_container_width=True)

        # --- Top N (tabla) con COP ---
        topn = st.slider("Top N gastos", 5, 30, 10, 1)
        top = pd.DataFrame(get_top_expenses(selected_month, n=topn)["top"])
        if not top.empty:
            top = top.rename(columns={
                "date": "Fecha",
                "category": "Categoría",
                "amount": "Monto ($)",
                "description": "Descripción"
            })
            top["Monto ($)"] = top["Monto ($)"].apply(fmt_cop)

            col2.subheader(f"Top {topn} gastos del mes")
            # alineación a la derecha para la columna de dinero
            styled_top = (
                top.style
                   .set_properties(subset=["Monto ($)"], **{"text-align":"right"})
                   .set_table_styles([{"selector":"th","props":[("text-align","right")]}])
            )
            col2.dataframe(styled_top, use_container_width=True)
        else:
            col2.info("No hay gastos registrados para este mes.")

        # --- Barras por categoría con eje en COP ---
        bars = (
            alt.Chart(df_donut)
              .mark_bar()
              .encode(
                  x=alt.X("Monto:Q", title="Gasto (COP)", axis=alt.Axis(format=",.0f")),
                  y=alt.Y("Categoría:N", sort="-x", title="Categoría"),
                  tooltip=[ "Categoría", alt.Tooltip("Monto:Q", title="Monto", format=",.0f") ]
              )
              .properties(title="Gasto por categoría", height=420)
        )
        st.altair_chart(bars, use_container_width=True)

    else:
        st.info("No hay gastos en el mes seleccionado.")

# ============================
# 3) Seguimiento de Presupuesto
# ============================
elif page.startswith("3"):
    st.title("3 · Seguimiento de presupuesto")
    prog = pd.DataFrame(get_budget_progress(selected_month)["progress"])  # month, category, limit, spent, pct, status
    st.caption("Verde ≤80%, Amarillo 80–100%, Rojo >100%")

    # Aviso de categorías excedidas
    over = prog[prog["pct"] > 100]
    if not over.empty:
        st.error("¡Categorías excedidas! " + ", ".join(over["category"].tolist()))

    # --- Tabla con estilos ---
    # Renombrar y preparar
    prog_disp = prog[["category", "limit", "spent", "status", "pct"]].rename(columns={
        "category": "Categoría",
        "limit": "Límite",
        "spent": "Gasto",
        "status": "Estado",
        "pct": "% Uso"
    }).copy()

    # Guardamos el status real para colorear y escondemos el texto en la celda
    status_vals = prog_disp["Estado"].tolist()
    prog_disp["Estado"] = ""  # ocultar texto, solo se verá el color

    # Estilos por color
    bg = {
        "green": "background-color: #C8E6C9; color: #1B5E20; font-weight: 600;",   # verde suave
        "amber": "background-color: #FFE082; color: #6D4C41; font-weight: 600;",   # ámbar
        "red":   "background-color: #FFCDD2; color: #B71C1C; font-weight: 600;",   # rojo suave
    }

    def style_estado(_col):
        # devuelve un estilo por cada fila según el status original
        return [bg.get(s, "") for s in status_vals]

    styled = (
        prog_disp.style
            .format({"Límite": fmt_cop, "Gasto": fmt_cop, "% Uso": "{:.1f}%"})
            .apply(style_estado, subset=["Estado"])
    )

    st.dataframe(styled, use_container_width=True, hide_index=True)

    # --- Barra horizontal de % uso con líneas guía 80% y 100% ---
    base = alt.Chart(prog).transform_calculate(
        pct_fmt="format(datum.pct, '.1f') + '%'"
    )

    bars = base.mark_bar().encode(
        x=alt.X("pct:Q", title="% del límite usado", axis=alt.Axis(format=".1f")),
        y=alt.Y("category:N", sort="-x", title="Categoría"),
        color=alt.Color("status:N",
            scale=alt.Scale(domain=["green","amber","red"],
                            range=["#4caf50","#ffc107","#f44336"]),
            legend=None
        ),
        tooltip=[
            alt.Tooltip("category:N", title="Categoría"),
            alt.Tooltip("spent:Q",   title="Gasto",  format=",.0f"),
            alt.Tooltip("limit:Q",   title="Límite", format=",.0f"),
            alt.Tooltip("pct:Q",     title="% Uso",  format=".1f")
        ]
    ).properties(height=520, title=f"Uso de presupuesto por categoría ({selected_month})")

    # Líneas guía en 80% y 100%
    rule80 = alt.Chart(pd.DataFrame({"x":[80]})).mark_rule(color="#ffc107", strokeDash=[6,4]).encode(x="x:Q")
    rule100= alt.Chart(pd.DataFrame({"x":[100]})).mark_rule(color="#f44336", strokeDash=[6,4]).encode(x="x:Q")

    st.altair_chart(bars + rule80 + rule100, use_container_width=True)

# ============================
# 4) Evolución del Patrimonio Neto
# ============================
elif page.startswith("4"):
    st.title("4 · Evolución del patrimonio neto")
    series = pd.DataFrame(get_networth())

    if not series.empty:
        # Asegurar que los nombres de columnas son correctos y numéricos
        series = series[["month", "cumulative_cash", "value", "net_worth"]].fillna(0)
        series[["cumulative_cash", "value", "net_worth"]] = series[["cumulative_cash", "value", "net_worth"]].astype(float)
        
        # Convertir datos a formato largo (melt en vez de transform_fold)
        # --- Renombrar claves a español para la leyenda ---
        rename_series = {
            "cumulative_cash": "Efectivo acumulado",
            "value": "Valor inversiones",
            "net_worth": "Patrimonio neto",
        }
        df_melt = series.melt(id_vars="month", var_name="tipo", value_name="monto")
        df_melt["tipo"] = df_melt["tipo"].map(rename_series)

        # Colores consistentes
        domain = ["Efectivo acumulado", "Patrimonio neto", "Valor inversiones"]
        range_ = ["#1976d2", "#64b5f6", "#e53935"]  # azul, celeste, rojo

        # Eje Y en formato miles (D3 usa coma como separador)
        chart = (
            alt.Chart(df_melt)
            .mark_line(point=True)
            .encode(
                x=alt.X("month:N", title="Mes"),
                y=alt.Y("monto:Q", axis=alt.Axis(title="COP", format=",.0f")),  # 1,234,567
                color=alt.Color("tipo:N", title="Componente",
                                scale=alt.Scale(domain=domain, range=range_)),
                tooltip=["month", "tipo", alt.Tooltip("monto:Q", format=",.0f")],
            )
            .properties(height=420, title="Serie mensual: efectivo, inversiones y patrimonio")
        )
        st.altair_chart(chart, use_container_width=True)


        # === Resumen numérico y variaciones ===
        # Ordenar por mes como fecha real
        series["_dt"] = pd.to_datetime(series["month"] + "-01")
        series = series.sort_values("_dt").reset_index(drop=True)

        # Deltas mes a mes
        for col in ["cumulative_cash", "value", "net_worth"]:
            series[f"{col}_diff"] = series[col].diff()
            # evitar división por cero
            series[f"{col}_pct"] = (series[f"{col}_diff"] / series[col].shift(1)).replace([np.inf, -np.inf], 0) * 100

        last = series.iloc[-1]
        prev = series.iloc[-2] if len(series) > 1 else None

        st.subheader("Resumen del último mes")
        c1, c2, c3 = st.columns(3)

        def fmt(num): 
            return f"{num:,.0f}"

        def delta_str(cur, dif):
            if pd.isna(dif):
                return "N/A"
            sign = "+" if dif >= 0 else ""
            return f"{sign}{dif:,.0f}"

        # Métricas con delta vs mes anterior
        c1.metric("Efectivo acumulado", fmt(last["cumulative_cash"]), 
                delta=None if prev is None else delta_str(last["cumulative_cash"], last["cumulative_cash_diff"]))
        c2.metric("Valor de inversiones", fmt(last["value"]), 
                delta=None if prev is None else delta_str(last["value"], last["value_diff"]))
        c3.metric("Patrimonio neto", fmt(last["net_worth"]), 
                delta=None if prev is None else delta_str(last["net_worth"], last["net_worth_diff"]))

        st.markdown("### Tabla mensual con variaciones (Δ y %Δ)")
        # ---- Tabla con nombres en español, COP y alineación derecha ----
        tbl = series[[
            "month",
            "cumulative_cash", "cumulative_cash_diff", "cumulative_cash_pct",
            "value", "value_diff", "value_pct",
            "net_worth", "net_worth_diff", "net_worth_pct",
        ]].rename(columns={
            "month": "Mes",
            "cumulative_cash": "Efectivo",
            "cumulative_cash_diff": "Δ Efectivo",
            "cumulative_cash_pct": "%Δ Efectivo",
            "value": "Inversiones",
            "value_diff": "Δ Inversiones",
            "value_pct": "%Δ Inversiones",
            "net_worth": "Patrimonio",
            "net_worth_diff": "Δ Patrimonio",
            "net_worth_pct": "%Δ Patrimonio",
        })

        # Formato moneda colombiana
        def fmt_cop(x):
            try:
                return f"${x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                return x

        money_cols = ["Efectivo","Δ Efectivo","Inversiones","Δ Inversiones","Patrimonio","Δ Patrimonio"]
        pct_cols   = ["%Δ Efectivo","%Δ Inversiones","%Δ Patrimonio"]

        # Styler para formato + alineación derecha
        styled_tbl = (
            tbl.style
            .format({**{c: fmt_cop for c in money_cols},
                        **{c: (lambda v: "-" if pd.isna(v) else f"{v:.2f}%") for c in pct_cols}})
            .set_properties(subset=money_cols + pct_cols, **{"text-align": "right"})
            .set_table_styles([{"selector": "th", "props": [("text-align", "right")]}])
        )

        st.dataframe(styled_tbl, use_container_width=True)

        # (Opcional) descarga de la tabla en CSV
        csv_bytes = series.drop(columns=["_dt"]).to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Descargar serie de patrimonio (CSV)", data=csv_bytes, file_name="net_worth_series_with_deltas.csv", mime="text/csv")

    else:
        st.warning("No hay datos de patrimonio neto disponibles.")

# ============================
# 5) Dashboard de Inversiones
# ============================
elif page.startswith("5"):
    st.title("5 · Inversiones")
    hist = pd.DataFrame(get_inv_history())  # month, value, ret_acum
    alloc = get_inv_alloc()
    aldf = pd.DataFrame(alloc["allocation"])  # asset, units, price, value, weight_pct

    c1, c2 = st.columns([1.4, 1])

    # KPIs (formato COP y %)
    base = float(hist["value"].iloc[0]) if len(hist) else 1.0
    last_val = float(hist["value"].iloc[-1]) if len(hist) else 0.0
    last_ret = float(hist["ret_acum"].iloc[-1]) if len(hist) else 0.0
    c1.metric("Valor actual del portafolio", fmt_cop(last_val))
    c2.metric("Retorno acumulado", f"{last_ret:.2f}%")

    # Línea del valor del portafolio (eje en miles)
    line = (
        alt.Chart(hist)
        .mark_line(point=True)
        .encode(
            x=alt.X("month:N", title="Mes"),
            y=alt.Y("value:Q", axis=alt.Axis(title="COP", format=",.0f")),
            tooltip=[
                "month",
                alt.Tooltip("value:Q", title="Valor", format=",.0f"),
                alt.Tooltip("ret_acum:Q", title="% Acumulado", format=".2f"),
            ],
        )
        .properties(height=350, title="Evolución del valor del portafolio")
    )
    st.altair_chart(line, use_container_width=True)

    # -------- Asignación de activos (treemap + tabla) --------
    st.subheader("Asignación de activos")
    if not aldf.empty:
        # Mapeo de nombres a español
        name_map = {
            "ETF_Global": "ETF Global",
            "Bono_Gov": "Bono del Gobierno",
            "Accion_Tec": "Acción Tech",
            "Fondo_Inmobiliario": "Fondo Inmobiliario",
        }
        aldf["Activo"] = aldf["asset"].map(name_map).fillna(aldf["asset"])

        # Hover: COP y %
        aldf["Valor_str"] = aldf["value"].map(fmt_cop)
        aldf["Peso_str"]  = aldf["weight_pct"].map(lambda x: f"{x:.2f}%")

        tree = px.treemap(
            aldf,
            path=["Activo"], values="value",
            hover_data=["Valor_str", "Peso_str"],
        )
        tree.update_traces(
            hovertemplate="<b>%{label}</b><br>Valor: %{customdata[0]}<br>Peso: %{customdata[1]}<extra></extra>"
        )
        st.plotly_chart(tree, use_container_width=True)

        # Tabla formateada y alineada
        aldisp = (
            aldf[["Activo","price","units","value","weight_pct"]]
            .rename(columns={"price":"Precio","units":"Unidades","value":"Valor","weight_pct":"Peso %"})
        )
        styled_alloc = (
            aldisp.style
                .format({"Precio": fmt_cop, "Unidades": "{:.2f}", "Valor": fmt_cop, "Peso %": "{:.2f}%"})
                .set_properties(subset=["Precio","Unidades","Valor","Peso %"], **{"text-align":"right"})
                .set_table_styles([{"selector":"th","props":[("text-align","right")]}])
        )
        st.dataframe(styled_alloc, use_container_width=True)
    else:
        st.info("No hay datos de asignación.")

    # -------- Resumen y variaciones mensuales --------
    st.subheader("Resumen y variaciones mensuales")
    if not hist.empty:
        # Tipos y orden por mes real
        hist["value"] = hist["value"].astype(float)
        hist["_dt"] = pd.to_datetime(hist["month"] + "-01")
        hist = hist.sort_values("_dt").reset_index(drop=True)

        # Δ y %Δ mensual
        hist["value_diff"] = hist["value"].diff()
        hist["ret_month"] = hist["value"].pct_change() * 100

        # KPIs (último dato)
        last = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else None

        def fmt_delta_cop(x):
            if pd.isna(x):
                return "N/A"
            sign = "+" if x >= 0 else "-"
            return f"{sign}{fmt_cop(abs(x))}"

        k1, k2, k3 = st.columns(3)
        k1.metric(
            "Valor actual del portafolio",
            fmt_cop(last["value"]),
            None if prev is None else fmt_delta_cop(last["value_diff"]),
        )
        k2.metric("Retorno mensual", "-" if pd.isna(last["ret_month"]) else f"{last['ret_month']:.2f}%")
        k3.metric("Retorno acumulado", f"{last['ret_acum']:.2f}%")

        # Barras de retorno mensual (verde/rojo)
        bars_df = hist[["month", "ret_month"]].copy()
        bars_df["color"] = np.where(bars_df["ret_month"] >= 0, "#4caf50", "#f44336")
        bars = (
            alt.Chart(bars_df)
            .mark_bar()
            .encode(
                x=alt.X("month:N", title="Mes"),
                y=alt.Y("ret_month:Q", title="Retorno mensual (%)", axis=alt.Axis(format=".2f")),
                color=alt.Color("color:N", scale=None, legend=None),
                tooltip=["month", alt.Tooltip("ret_month:Q", title="Retorno", format=".2f")],
            )
            .properties(height=280, title="Retorno mensual del portafolio")
        )
        st.altair_chart(bars, use_container_width=True)

        # Tabla mensual formateada y alineada
        st.markdown("### Tabla mensual (valor, Δ y %Δ)")
        tbl = hist[["month", "value", "value_diff", "ret_month", "ret_acum"]].rename(
            columns={
                "month": "Mes",
                "value": "Valor",
                "value_diff": "Δ Valor",
                "ret_month": "%Δ Mensual",
                "ret_acum": "% Acumulado",
            }
        )

        money_cols = ["Valor", "Δ Valor"]
        pct_cols = ["%Δ Mensual", "% Acumulado"]

        styled_inv = (
            tbl.style
            .format(
                {**{c: fmt_cop for c in money_cols},
                 **{c: (lambda v: "-" if pd.isna(v) else f"{v:.2f}%") for c in pct_cols}}
            )
            .set_properties(subset=money_cols + pct_cols, **{"text-align": "right"})
            .set_table_styles([{"selector": "th", "props": [("text-align", "right")]}])
        )
        st.dataframe(styled_inv, use_container_width=True)

        # Descarga CSV
        csv_inv = hist.drop(columns=["_dt"]).to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar histórico de inversiones (CSV)",
            data=csv_inv,
            file_name="investments_history_with_deltas.csv",
            mime="text/csv",
        )
    else:
        st.info("No hay datos históricos de inversiones.")

# ============================
# 6) Metas y Ahorros
# ============================
else:
    st.title("6 · Metas y ahorros")
    goals = pd.DataFrame(get_goals())

    if goals.empty:
        st.info("Sin metas registradas.")
    else:
        # Tabla resumen en COP y alineada a la derecha
        tbl = goals[["goal","target_amount","current_savings","progress_pct","due_date"]].rename(columns={
            "goal":"Meta", "target_amount":"Objetivo ($)", "current_savings":"Ahorro actual ($)",
            "progress_pct":"% Progreso", "due_date":"Fecha objetivo"
        })
        styled_tbl = (
            tbl.style
               .format({"Objetivo ($)": fmt_cop, "Ahorro actual ($)": fmt_cop, "% Progreso": "{:.1f}%"})
               .set_properties(subset=["Objetivo ($)","Ahorro actual ($)","% Progreso"], **{"text-align":"right"})
               .set_table_styles([{"selector":"th","props":[("text-align","right")]}])
        )
        st.dataframe(styled_tbl, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Progreso por meta")

        # ---------- IMPORTANTE: TODO lo que sigue va DENTRO del for -----------
        for i, row in goals.iterrows():

            # clave segura para widgets (evita choques si hay espacios/acentos)
            slug = re.sub(r"\W+", "_", str(row["goal"])).lower()
            safe = f"{i}_{slug}"

            objetivo = float(row["target_amount"])
            actual   = float(row["current_savings"])
            avance   = float(row["progress_pct"])
            restante = max(0.0, objetivo - actual)

            with st.container(border=True):
                st.markdown(f"### {row['goal']}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Objetivo ($)", fmt_cop(objetivo))
                c2.metric("Ahorro actual ($)", fmt_cop(actual))
                c3.metric("Avance", f"{avance:.1f}%")
                st.progress(min(1.0, avance/100.0))
                st.caption(f"Fecha objetivo declarada: {row['due_date']}")

                # --- Simuladores (dos pestañas) ---
                with st.expander("Simuladores"):
                    tab1, tab2 = st.tabs(["💵 Aportar cada mes", "🗓️ Cumplir en una fecha"])

                    # ---------------------------
                    # Tab 1: Aportar cada mes
                    # ---------------------------
                    with tab1:
                        cA1, cA2 = st.columns([1,1])

                        aporte = cA1.number_input(
                            f"Aporte mensual para '{row['goal']}' ($COP)",
                            min_value=0.0, value=0.0, step=50_000.0, format="%.2f",
                            key=f"aporte_{safe}"
                        )
                        meses_sim = cA2.number_input(
                            "Simular avance en N meses",
                            min_value=1, value=6, step=1, key=f"meses_{safe}"
                        )

                        if aporte <= 0:
                            st.info("Ingresa un aporte mensual > 0 para simular.")
                        else:
                            # ¿En cuántos meses llego?
                            meses_necesarios = math.ceil(restante / aporte) if restante > 0 else 0
                            hoy_primero = pd.Timestamp(dt.date.today().replace(day=1))
                            fecha_estimada = (hoy_primero + pd.DateOffset(months=meses_necesarios)).date() \
                                             if meses_necesarios > 0 else dt.date.today()

                            # Proyección en N meses (aunque no llegue)
                            ahorro_proj = actual + aporte * meses_sim
                            progreso_proj = min(100.0, (ahorro_proj / objetivo) * 100.0)

                            st.markdown(f"**Con {fmt_cop(aporte)}/mes:**")
                            st.write(f"- Alcanzas la meta en **{meses_necesarios}** mes(es) (≈ **{fecha_estimada}**).")
                            st.write(f"- Proyección en **{meses_sim}** mes(es): ahorro **{fmt_cop(ahorro_proj)}** → avance **{progreso_proj:.1f}%**.")
                            st.progress(min(1.0, progreso_proj/100.0))

                    # ---------------------------
                    # Tab 2: Cumplir en una fecha
                    # ---------------------------
                    with tab2:
                        default_fecha = (pd.Timestamp(dt.date.today().replace(day=1)) + pd.DateOffset(months=6)).date()
                        fecha_deseada = st.date_input(
                            "Elige la fecha en la que quieres cumplir la meta",
                            value=default_fecha,
                            key=f"fecha_{safe}"
                        )

                        hoy_primero = pd.Timestamp(dt.date.today().replace(day=1))
                        fecha_ts = pd.Timestamp(fecha_deseada)
                        diff = (fecha_ts.year - hoy_primero.year) * 12 + (fecha_ts.month - hoy_primero.month)
                        meses_rest = max(0, int(diff))

                        if meses_rest <= 0:
                            st.info("Elige una fecha futura para calcular el aporte mensual necesario.")
                        else:
                            aporte_necesario = (restante / meses_rest) if restante > 0 else 0.0
                            ahorro_proj = actual + aporte_necesario * meses_rest
                            progreso_proj = min(100.0, (ahorro_proj / objetivo) * 100.0)

                            st.markdown(
                                f"Para cumplir el **{fecha_deseada}** necesitas aportar **{fmt_cop(aporte_necesario)} / mes** "
                                f"durante **{meses_rest}** mes(es)."
                            )
                            st.write(f"Proyección a esa fecha: ahorro **{fmt_cop(ahorro_proj)}** → avance **{progreso_proj:.1f}%**.")
                            st.progress(min(1.0, progreso_proj/100.0))
