from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# ------- Carga de datos (una vez) -------
tx = pd.read_csv(DATA_DIR / "transactions.csv", parse_dates=["date"])
tx["month"] = tx["month"].astype(str)

budgets = pd.read_csv(DATA_DIR / "budgets.csv", dtype={"month": str, "category": str, "limit": float})
netw = pd.read_csv(DATA_DIR / "net_worth.csv", dtype={"month": str})
prices = pd.read_csv(DATA_DIR / "investments_prices.csv", parse_dates=["date"])
hold = pd.read_csv(DATA_DIR / "investments_holdings.csv")
goals = pd.read_csv(DATA_DIR / "goals.csv", parse_dates=["due_date"])

# Serie de valor mensual del portafolio (a partir de prices x holdings)
port = prices.merge(hold, on="asset")
port["value"] = port["price"] * port["units"]
port["month"] = port["date"].dt.to_period("M").astype(str)
portfolio_monthly = port.groupby("month", as_index=False)["value"].sum()

# Utilidades
def _latest_month() -> str:
    # último mes presente en transacciones
    return sorted(tx["month"].unique())[-1]

def _ensure_native(obj: Any):
    if isinstance(obj, (np.integer, np.int64)): return int(obj)
    if isinstance(obj, (np.floating, np.float64)): return float(obj)
    if isinstance(obj, (np.bool_,)): return bool(obj)
    return obj

def _df_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    return [{k: _ensure_native(v) for k, v in r.items()} for r in df.to_dict(orient="records")]

# ------- App -------
app = FastAPI(title="Personal Finance API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# -------- 1) Resumen financiero + cascada (ingresos vs gastos) --------
@app.get("/summary")
def summary(month: Optional[str] = Query(default=None, description="YYYY-MM")):
    m = month or _latest_month()
    dfm = tx[tx["month"] == m]

    ingresos = float(dfm.loc[dfm["type"]=="Ingreso", "amount"].sum())
    gastos = float(dfm.loc[dfm["type"]=="Gasto", "amount"].sum())
    neto_mes = ingresos - gastos

    # KPIs de patrimonio (último net_worth disponible)
    nw_row = netw.sort_values("month").iloc[-1].to_dict()
    patrimonio = float(nw_row["net_worth"])
    cash = float(nw_row["cumulative_cash"])
    inversiones = float(nw_row["value"])

    # Datos de cascada: inicio-> ingresos (+) -> gastos (-) -> neto
    waterfall = [
        {"label": "Inicio", "value": 0},
        {"label": "Ingresos", "value": ingresos},
        {"label": "Gastos", "value": -gastos},
        {"label": "Neto mes", "value": neto_mes},
    ]

    return {
        "month": m,
        "kpis": {
            "ingresos_mes": ingresos,
            "gastos_mes": gastos,
            "neto_mes": neto_mes,
            "patrimonio_actual": patrimonio,
            "efectivo_acumulado": cash,
            "valor_inversiones": inversiones,
        },
        "waterfall": waterfall,
        "rows_mes": int(dfm.shape[0]),
    }

# -------- 2) Análisis de gastos: dona + top gastos --------
@app.get("/expenses_donut")
def expenses_donut(month: Optional[str] = None):
    m = month or _latest_month()
    dfm = tx[(tx["month"] == m) & (tx["type"] == "Gasto")]
    grp = dfm.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    return {"month": m, "donut": _df_records(grp)}

@app.get("/top_expenses")
def top_expenses(month: Optional[str] = None, n: int = 10):
    m = month or _latest_month()
    dfm = tx[(tx["month"] == m) & (tx["type"] == "Gasto")].sort_values("amount", ascending=False).head(n)
    dfm = dfm[["date","category","amount","description"]]
    dfm["date"] = pd.to_datetime(dfm["date"]).dt.date.astype(str)
    return {"month": m, "top": _df_records(dfm)}

# -------- 3) Seguimiento de presupuesto: medidores por categoría --------
@app.get("/budget_progress")
def budget_progress(month: Optional[str] = None):
    m = month or _latest_month()
    g_m = tx[(tx["month"] == m) & (tx["type"] == "Gasto")].groupby("category", as_index=False)["amount"].sum().rename(columns={"amount":"spent"})
    lim = budgets[budgets["month"] == m]
    df = lim.merge(g_m, on="category", how="left").fillna({"spent": 0.0})
    df["pct"] = (df["spent"] / df["limit"]).replace([np.inf, -np.inf], 0).fillna(0) * 100
    # Semáforo
    def color(p):
        if p <= 80: return "green"
        if p <= 100: return "amber"
        return "red"
    df["status"] = df["pct"].apply(color)
    return {"month": m, "progress": _df_records(df.sort_values("pct", ascending=False))}

# -------- 4) Evolución del patrimonio neto (serie) --------
@app.get("/net_worth_series")
def net_worth_series():
    df = netw.sort_values("month")[["month","cumulative_cash","value","net_worth"]]
    return {"series": _df_records(df)}

# -------- 5) Inversiones: resumen, histórico y treemap --------
@app.get("/investments_history")
def investments_history():
    df = portfolio_monthly.sort_values("month")
    # rendimiento acumulado vs primer valor
    base = float(df["value"].iloc[0])
    df = df.assign(
        ret_acum=(df["value"] / base - 1.0) * 100.0
    )
    return {"history": _df_records(df)}

@app.get("/investments_alloc")
def investments_alloc():
    # último precio por activo
    last_prices = prices.sort_values("date").groupby("asset").tail(1)[["asset","price"]]
    alloc = hold.merge(last_prices, on="asset")
    alloc["value"] = alloc["units"] * alloc["price"]
    total = float(alloc["value"].sum())
    alloc["weight_pct"] = (alloc["value"] / total) * 100.0
    alloc = alloc.sort_values("value", ascending=False)
    return {"allocation": _df_records(alloc), "total_value": total}

# -------- 6) Metas & Ahorros --------
@app.get("/goals")
def get_goals():
    df = goals.copy()
    df["progress_pct"] = (df["current_savings"] / df["target_amount"]).clip(0,1) * 100.0
    df["due_date"] = df["due_date"].dt.date.astype(str)
    return {"goals": _df_records(df)}

# -------- Extra: tabla cruda de transacciones por mes --------
@app.get("/transactions")
def transactions(month: Optional[str] = None, limit: int = 200):
    m = month or _latest_month()
    dfm = tx[tx["month"] == m].copy()
    dfm["date"] = dfm["date"].dt.date.astype(str)
    return {"month": m, "rows": _df_records(dfm.head(limit))}



@app.get("/")
def root():
    return {"status": "ok", "message": "API de Finanzas Personales funcionando 🚀"}
# para que cuando se abra el backend muestre API de Finanzas Personales funcionando en vez de not found