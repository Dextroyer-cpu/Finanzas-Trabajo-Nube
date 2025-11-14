from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
import os
import io

# 🔧 CAMBIO: ahora usamos Azure Blob Storage en lugar de archivos locales
from azure.storage.blob import BlobServiceClient

# ---------------- Azure Storage Configuration ---------------- #
# 🔧 CAMBIO: obtenemos el connection string desde Azure App Service
BLOB_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION")

# 🔧 CAMBIO: nos conectamos al storage
blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
CONTAINER = "data"

def read_csv_blob(filename: str) -> pd.DataFrame:
    """
    🔧 CAMBIO: ahora todos los CSV se leen desde Azure Blob Storage.
    """
    blob = blob_service.get_blob_client(container=CONTAINER, blob=filename)
    data = blob.download_blob().readall()
    return pd.read_csv(io.BytesIO(data))

# ------- Carga de datos desde Azure Blob Storage ------- #
# 🔧 CAMBIO: todas las cargas ahora vienen del storage
tx = read_csv_blob("transactions.csv")
tx["date"] = pd.to_datetime(tx["date"])
tx["month"] = tx["month"].astype(str)

budgets = read_csv_blob("budgets.csv")
budgets["month"] = budgets["month"].astype(str)

netw = read_csv_blob("net_worth.csv")
netw["month"] = netw["month"].astype(str)

prices = read_csv_blob("investments_prices.csv")
prices["date"] = pd.to_datetime(prices["date"])

hold = read_csv_blob("investments_holdings.csv")

goals = read_csv_blob("goals.csv")
goals["due_date"] = pd.to_datetime(goals["due_date"])

# -------- Serie mensual del portafolio -------- #
port = prices.merge(hold, on="asset")
port["value"] = port["price"] * port["units"]
port["month"] = port["date"].dt.to_period("M").astype(str)
portfolio_monthly = port.groupby("month", as_index=False)["value"].sum()

# ---------------- Utilidades ---------------- #
def _latest_month() -> str:
    return sorted(tx["month"].unique())[-1]

def _ensure_native(obj: Any):
    if isinstance(obj, (np.integer, np.int64)): return int(obj)
    if isinstance(obj, (np.floating, np.float64)): return float(obj)
    if isinstance(obj, (np.bool_,)): return bool(obj)
    return obj

def _df_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    return [{k: _ensure_native(v) for k, v in r.items()} for r in df.to_dict(orient="records")]

# ---------------- FASTAPI ---------------- #
app = FastAPI(title="Personal Finance API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# -------- 1) Resumen financiero -------- #
@app.get("/summary")
def summary(month: Optional[str] = Query(default=None)):
    m = month or _latest_month()
    dfm = tx[tx["month"] == m]

    ingresos = float(dfm[dfm["type"] == "Ingreso"]["amount"].sum())
    gastos = float(dfm[dfm["type"] == "Gasto"]["amount"].sum())
    neto_mes = ingresos - gastos

    nw_row = netw.sort_values("month").iloc[-1].to_dict()

    return {
        "month": m,
        "kpis": {
            "ingresos_mes": ingresos,
            "gastos_mes": gastos,
            "neto_mes": neto_mes,
            "patrimonio_actual": float(nw_row["net_worth"]),
            "efectivo_acumulado": float(nw_row["cumulative_cash"]),
            "valor_inversiones": float(nw_row["value"]),
        },
        "waterfall": [
            {"label": "Inicio", "value": 0},
            {"label": "Ingresos", "value": ingresos},
            {"label": "Gastos", "value": -gastos},
            {"label": "Neto mes", "value": neto_mes},
        ],
        "rows_mes": int(dfm.shape[0]),
    }

# -------- 2) Donut de gastos -------- #
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
    dfm["date"] = dfm["date"].dt.date.astype(str)
    return {"month": m, "top": _df_records(dfm)}

# -------- 3) Presupuestos -------- #
@app.get("/budget_progress")
def budget_progress(month: Optional[str] = None):
    m = month or _latest_month()
    g_m = tx[(tx["month"] == m) & (tx["type"] == "Gasto")].groupby("category", as_index=False)["amount"].sum().rename(columns={"amount":"spent"})
    lim = budgets[budgets["month"] == m]
    df = lim.merge(g_m, on="category", how="left").fillna({"spent": 0.0})
    df["pct"] = (df["spent"] / df["limit"]).replace([np.inf, -np.inf], 0).fillna(0) * 100

    def color(p):
        if p <= 80: return "green"
        if p <= 100: return "amber"
        return "red"

    df["status"] = df["pct"].apply(color)
    return {"month": m, "progress": _df_records(df.sort_values("pct", ascending=False))}

# -------- 4) Patrimonio -------- #
@app.get("/net_worth_series")
def net_worth_series():
    df = netw.sort_values("month")[["month","cumulative_cash","value","net_worth"]]
    return {"series": _df_records(df)}

# -------- 5) Inversiones -------- #
@app.get("/investments_history")
def investments_history():
    df = portfolio_monthly.sort_values("month")
    base = float(df["value"].iloc[0])
    df["ret_acum"] = (df["value"] / base - 1.0) * 100
    return {"history": _df_records(df)}

@app.get("/investments_alloc")
def investments_alloc():
    last_prices = prices.sort_values("date").groupby("asset").tail(1)[["asset","price"]]
    alloc = hold.merge(last_prices, on="asset")
    alloc["value"] = alloc["units"] * alloc["price"]
    total = float(alloc["value"].sum())
    alloc["weight_pct"] = (alloc["value"] / total) * 100
    alloc = alloc.sort_values("value", ascending=False)
    return {"allocation": _df_records(alloc), "total_value": total}

# -------- 6) Metas -------- #
@app.get("/goals")
def get_goals():
    df = goals.copy()
    df["progress_pct"] = (df["current_savings"] / df["target_amount"]).clip(0,1) * 100
    df["due_date"] = df["due_date"].dt.date.astype(str)
    return {"goals": _df_records(df)}

# -------- Extras -------- #
@app.get("/transactions")
def transactions(month: Optional[str] = None, limit: int = 200):
    m = month or _latest_month()
    dfm = tx[tx["month"] == m].copy()
    dfm["date"] = dfm["date"].dt.date.astype(str)
    return {"month": m, "rows": _df_records(dfm.head(limit))}

@app.get("/")
def root():
    return {"status": "ok", "message": "API de Finanzas Personales funcionando 🚀"}
