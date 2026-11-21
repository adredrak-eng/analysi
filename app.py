# -*- coding: utf-8 -*-
"""
Ανάλυση αγώνων ποδοσφαίρου από CSV (μορφή football-data.co.uk)

Εγκατάσταση (μία φορά):   python -m pip install streamlit pandas
Εκτέλεση:                  python -m streamlit run app.py
"""

import base64
import html
import io
import math
import subprocess
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# ΡΥΘΜΙΣΕΙΣ ΜΟΝΤΕΛΟΥ
# ----------------------------------------------------------------------------
SHRINK_GAMES = 3      # "τραβάει" τις ομάδες με λίγους αγώνες προς τον μέσο όρο
XG_WEIGHT = 0.5       # πόσο μετράει το xG (αν υπάρχει) σε σχέση με τα γκολ
MAX_GOALS = 10        # μέγιστα γκολ ανά ομάδα στους υπολογισμούς
RECENCY = {"Κανένα": None, "Μικρό": 15, "Μεσαίο": 8, "Μεγάλο": 4}

C_HOME, C_DRAW, C_AWAY = "#22c55e", "#f59e0b", "#ef4444"
C_DC = ["#38bdf8", "#a78bfa", "#f472b6"]
C_UNDER, C_OVER = "#14b8a6", "#fb7185"
C_GG, C_NG = "#fbbf24", "#94a3b8"
C_T1, C_T2 = "#38bdf8", "#f472b6"

LABELS = {
    "1": "1", "X": "Χ", "2": "2",
    "1X": "1Χ", "X2": "Χ2", "12": "12",
    "U15": "Under 1.5", "O15": "Over 1.5",
    "U25": "Under 2.5", "O25": "Over 2.5",
    "U35": "Under 3.5", "O35": "Over 3.5",
    "U45": "Under 4.5", "O45": "Over 4.5",
    "GG": "Γκολ-Γκολ ΝΑΙ", "NG": "Γκολ-Γκολ ΟΧΙ",
}

CSS = """
<style>
.stApp {background: linear-gradient(135deg,#0f172a 0%,#1e1b4b 55%,#312e81 100%);}
.block-container {padding-top: 2rem; max-width: 1000px;}
h1,h2,h3,h4,p,label,span,div,small,li {color:#e2e8f0;}
.hero {background: linear-gradient(90deg,#6366f1,#ec4899,#f59e0b); padding: 22px 26px;
       border-radius: 20px; margin-bottom: 22px; box-shadow: 0 10px 30px rgba(0,0,0,.35);}
.hero {display:flex; justify-content:space-between; align-items:center; gap:16px; flex-wrap:wrap;}
.hero a {background:rgba(255,255,255,.22); color:#fff !important; padding:9px 16px; border-radius:12px;
         text-decoration:none; font-weight:700; white-space:nowrap; border:1px solid rgba(255,255,255,.45);}
.hero a:hover {background:rgba(255,255,255,.35);}
.hero h1 {margin:0; color:#fff; font-size: 2rem;}
.hero p {margin:6px 0 0 0; color:#fff; opacity:.92;}
.section {font-size:1.25rem; font-weight:700; margin: 22px 0 10px 0; color:#fff;}
.sub {font-size:1rem; font-weight:600; margin: 14px 0 6px 0; color:#c7d2fe;}
.card {background: rgba(255,255,255,.07); border-radius:16px; padding:16px 12px; text-align:center;
       box-shadow: 0 6px 18px rgba(0,0,0,.3); margin-bottom:10px;}
.card .lbl {font-size:.9rem; color:#cbd5e1; font-weight:600;}
.card .pct {font-size:1.9rem; font-weight:800; color:#fff; margin:4px 0;}
.card .odd {font-size:.78rem; color:#94a3b8; margin-bottom:8px;}
.bar {height:8px; background: rgba(255,255,255,.12); border-radius:6px; overflow:hidden;}
.bar div {height:100%; border-radius:6px;}
.pick {background: linear-gradient(90deg,#4f46e5,#9333ea); border-radius:16px; padding:14px 20px;
       color:#fff; margin-top:8px; margin-bottom:6px; box-shadow: 0 6px 18px rgba(0,0,0,.3);}
.pick b {color:#fde68a;}
.badge {display:inline-block; width:28px; height:28px; line-height:28px; text-align:center;
        border-radius:50%; font-weight:700; color:#fff; margin-right:4px;}
.note {background: rgba(251,191,36,.12); border-left:4px solid #fbbf24; padding:10px 14px;
       border-radius:8px; font-size:.9rem; margin:8px 0;}
.tbl {width:100%; border-collapse:collapse; font-size:.9rem; margin-top:6px;}
.tbl th {background:#3730a3; color:#fff; padding:8px; text-align:center; white-space:nowrap;}
.tbl td {padding:7px 8px; text-align:center; border-bottom:1px solid rgba(255,255,255,.08); color:#e2e8f0;}
.tbl td.l {text-align:left;}
.tbl tr.hl td {background:rgba(236,72,153,.28); color:#fff; font-weight:700;}
.good {color:#4ade80 !important; font-weight:700;}
.bad {color:#f87171 !important; font-weight:700;}
.mid {color:#fbbf24 !important; font-weight:700;}
.cmp {display:flex; align-items:center; gap:10px; margin:9px 0;}
.cmp .num {width:52px; text-align:center; font-weight:700; color:#fff;}
.cmp .md {flex:1;}
.cmp .t {text-align:center; font-size:.8rem; color:#cbd5e1; margin-bottom:3px;}
.cmp .two {display:flex; gap:4px;}
.cmp .lb, .cmp .rb {flex:1; height:8px; background:rgba(255,255,255,.12); border-radius:4px; display:flex;}
.cmp .lb {justify-content:flex-end;}
.cmp .lb span, .cmp .rb span {display:block; height:100%; border-radius:4px;}
/* Λίστες επιλογής: κλειστό κουτί */
[data-testid="stSelectbox"] [data-baseweb="select"] > div, [data-testid="stSelectbox"] div[role="combobox"] {
       background:#f8fafc !important; border:2px solid #6366f1 !important; border-radius:12px !important;}
[data-testid="stSelectbox"] * {color:#0f172a !important; -webkit-text-fill-color:#0f172a !important;
       font-weight:600 !important; cursor:pointer !important;}
[data-testid="stSelectbox"] label, [data-testid="stSelectbox"] label *,
[data-testid="stSelectbox"] [data-testid="stWidgetLabel"], [data-testid="stSelectbox"] [data-testid="stWidgetLabel"] * {
       color:#f1f5f9 !important; -webkit-text-fill-color:#f1f5f9 !important; cursor:default !important;}
[data-testid="stSelectbox"] input {caret-color:transparent !important;}
[data-testid="stSelectbox"] svg {fill:#0f172a !important;}
/* Ανοιχτή λίστα με τις ομάδες: σκούρα γράμματα σε ανοιχτό φόντο */
[data-baseweb="popover"] *, [data-baseweb="menu"] *, [role="listbox"] *, [data-testid="stSelectboxVirtualDropdown"] * {
       color:#0f172a !important; -webkit-text-fill-color:#0f172a !important;
       font-weight:600 !important; opacity:1 !important; cursor:pointer !important;}
[data-baseweb="popover"], [data-baseweb="popover"] > div, [data-baseweb="menu"], [role="listbox"],
[role="option"], [data-testid="stSelectboxVirtualDropdown"] {background:#f8fafc !important;}
[role="option"]:hover, [role="option"][aria-selected="true"] {background:#c7d2fe !important;}
/* Κουτιά αριθμών */
[data-testid="stNumberInput"] [data-baseweb="input"], [data-testid="stNumberInputContainer"] {
       background:#f8fafc !important; border:2px solid #6366f1 !important; border-radius:10px !important;}
[data-testid="stNumberInput"] input, [data-testid="stNumberInputField"] {
       color:#0f172a !important; -webkit-text-fill-color:#0f172a !important;
       background:#f8fafc !important; font-weight:600 !important;}
[data-testid="stNumberInput"] button {background:#e0e7ff !important; color:#0f172a !important;}
[data-testid="stNumberInput"] button svg {fill:#0f172a !important;}
/* Ρυθμίσεις (expander) και slider */
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * {
       color:#ffffff !important; font-weight:700 !important; opacity:1 !important;}
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] * {color:#f1f5f9 !important; opacity:1 !important;}
[data-baseweb="slider"] [role="slider"] {background:#ec4899 !important; border-color:#ec4899 !important;}
[data-testid="stFileUploaderDropzone"] {background:#1e293b; border:2px dashed #818cf8; border-radius:16px;}
[data-testid="stFileUploaderDropzone"] * {color:#e2e8f0 !important;}
[data-testid="stFileUploaderDropzone"] button {background: linear-gradient(90deg,#6366f1,#ec4899);
       color:#fff !important; border:none; border-radius:10px;}
[data-testid="stExpander"] {background:rgba(255,255,255,.05); border:1px solid #4338ca; border-radius:12px;}
[data-testid="stDownloadButton"] button {background: linear-gradient(90deg,#6366f1,#ec4899);
       color:#fff !important; border:none; border-radius:10px; width:100%;}
button[data-baseweb="tab"] {color:#cbd5e1 !important; font-weight:600;}
button[data-baseweb="tab"][aria-selected="true"] {color:#fff !important;}
[data-baseweb="tab-highlight"] {background:#ec4899 !important;}
[data-testid="stMetricValue"] {color:#fff;}
/* Κινητό */
@media (max-width: 640px) {
  .block-container {padding: 1rem 0.7rem 3rem 0.7rem;}
  .hero {padding: 16px 16px;}
  .hero h1 {font-size: 1.4rem;}
  .card .pct {font-size: 1.6rem;}
  .tbl {font-size: .8rem;}
  .tbl th, .tbl td {padding: 6px 5px;}
  .section {font-size: 1.1rem;}
}
</style>
"""


# ----------------------------------------------------------------------------
# ΦΟΡΤΩΣΗ ΑΡΧΕΙΟΥ
# ----------------------------------------------------------------------------
def _spreadsheetml(data: bytes) -> pd.DataFrame:
    """Excel 2003 XML (SpreadsheetML)"""
    root = ET.fromstring(data)
    rows = []
    for row in root.iter():
        if row.tag.split("}")[-1] != "Row":
            continue
        vals = []
        for cell in row:
            if cell.tag.split("}")[-1] != "Cell":
                continue
            for k, v in cell.attrib.items():
                if k.split("}")[-1] == "Index":
                    while len(vals) < int(v) - 1:
                        vals.append(None)
            val = None
            for ch in cell:
                if ch.tag.split("}")[-1] == "Data":
                    val = ch.text
            vals.append(val)
        rows.append(vals)
    if len(rows) < 2:
        raise ValueError("Το αρχείο XML δεν έχει πίνακα με δεδομένα.")
    header = [str(h).strip() if h is not None else f"col{i}" for i, h in enumerate(rows[0])]
    body = [(r + [None] * len(header))[:len(header)] for r in rows[1:]]
    return pd.DataFrame(body, columns=header)


def read_table(data: bytes) -> pd.DataFrame:
    """Διαβάζει αρχείο CSV, Excel (xlsx/xls), XML ή HTML. Καταλαβαίνει τον τύπο από το περιεχόμενο."""
    head = data[:5000].lstrip(b"\xef\xbb\xbf \r\n\t")
    low = head.lower()
    try:
        if data[:2] == b"PK":
            return pd.read_excel(io.BytesIO(data), engine="openpyxl")
        if data[:4] == b"\xd0\xcf\x11\xe0":
            return pd.read_excel(io.BytesIO(data))
        if low.startswith(b"<"):
            if b"urn:schemas-microsoft-com:office:spreadsheet" in data[:5000]:
                return _spreadsheetml(data)
            if low.startswith((b"<html", b"<!doctype html", b"<table")):
                text = data.decode("utf-8", errors="replace")
                return pd.read_html(io.StringIO(text))[0]
            try:
                return pd.read_xml(io.BytesIO(data))
            except ImportError:
                return pd.read_xml(io.BytesIO(data), parser="etree")
    except ImportError:
        raise ValueError("Για αρχεία Excel/HTML χρειάζεται εγκατάσταση. Γράψε στο CMD: "
                         "python -m pip install openpyxl xlrd lxml")
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            continue
    raise ValueError("Δεν μπόρεσα να διαβάσω το αρχείο (CSV, Excel ή XML).")


def fmt_date(v):
    if v is None or v != v:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%d/%m/%Y")
    return str(v)


def clean_results(df: pd.DataFrame) -> pd.DataFrame:

    rename = {"Home": "HomeTeam", "Away": "AwayTeam", "HG": "FTHG", "AG": "FTAG", "Res": "FTR"}
    for old, new in rename.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})

    needed = ["HomeTeam", "AwayTeam", "FTHG", "FTAG"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError("Λείπουν βασικές στήλες: " + ", ".join(missing))

    df["FTHG"] = pd.to_numeric(df["FTHG"], errors="coerce")
    df["FTAG"] = pd.to_numeric(df["FTAG"], errors="coerce")
    df = df.dropna(subset=needed).copy()
    df["HomeTeam"] = df["HomeTeam"].astype(str).str.strip()
    df["AwayTeam"] = df["AwayTeam"].astype(str).str.strip()

    if "Date" in df.columns:
        df["_date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
        df = df.sort_values("_date", kind="stable")
    else:
        df["_date"] = pd.NaT
    return df.reset_index(drop=True)


LEAGUES = {
    "E0": "Αγγλία · Premier League", "E1": "Αγγλία · Championship", "E2": "Αγγλία · League One",
    "E3": "Αγγλία · League Two", "EC": "Αγγλία · Conference",
    "SC0": "Σκωτία · Premiership", "SC1": "Σκωτία · Championship", "SC2": "Σκωτία · League One",
    "SC3": "Σκωτία · League Two",
    "D1": "Γερμανία · Bundesliga", "D2": "Γερμανία · 2. Bundesliga",
    "I1": "Ιταλία · Serie A", "I2": "Ιταλία · Serie B",
    "SP1": "Ισπανία · La Liga", "SP2": "Ισπανία · La Liga 2",
    "F1": "Γαλλία · Ligue 1", "F2": "Γαλλία · Ligue 2",
    "N1": "Ολλανδία · Eredivisie", "B1": "Βέλγιο · Pro League",
    "P1": "Πορτογαλία · Primeira Liga", "T1": "Τουρκία · Süper Lig", "G1": "Ελλάδα · Super League",
}


def league_label(code):
    return LEAGUES.get(str(code).strip().upper(), str(code))


def read_sheets(data: bytes) -> dict:
    """Excel με πολλά φύλλα (ένα ανά πρωτάθλημα): επιστρέφει όλα τα φύλλα. Αλλιώς ένα μόνο."""
    try:
        if data[:2] == b"PK":
            return dict(pd.read_excel(io.BytesIO(data), engine="openpyxl", sheet_name=None))
        if data[:4] == b"\xd0\xcf\x11\xe0":
            return dict(pd.read_excel(io.BytesIO(data), sheet_name=None))
    except ImportError:
        raise ValueError("Για αρχεία Excel χρειάζεται εγκατάσταση. Γράψε στο CMD: "
                         "python -m pip install openpyxl xlrd lxml")
    return {"": read_table(data)}


def split_leagues(name, raw):
    raw = raw.dropna(how="all")
    if "Div" in raw.columns and raw["Div"].nunique() > 1:
        return [(str(k).strip(), g) for k, g in raw.groupby("Div")]
    if "League" in raw.columns and raw["League"].nunique() > 1:
        key = raw["League"].astype(str)
        if "Country" in raw.columns:
            key = raw["Country"].astype(str) + " · " + key
        return [(str(k).strip(), g) for k, g in raw.groupby(key)]
    key = str(name).strip()
    if not key:
        key = str(raw["Div"].dropna().iloc[0]) if "Div" in raw.columns and raw["Div"].notna().any() else "Αρχείο"
    return [(key, raw)]


@st.cache_data(show_spinner=False)
def load_leagues(data: bytes) -> dict:
    """Επιστρέφει {κωδικός πρωταθλήματος: πίνακας αγώνων}"""
    out, skipped = {}, []
    for name, raw in read_sheets(data).items():
        for key, part in split_leagues(name, raw):
            try:
                d = clean_results(part)
            except Exception as e:
                skipped.append(f"{key or 'φύλλο'}: {e}")
                continue
            if "Season" in d.columns and d["Season"].nunique() > 1:
                latest = sorted(d["Season"].dropna().unique(), key=str)[-1]
                d = d[d["Season"] == latest].reset_index(drop=True)
            if len(d) > 0:
                out[key] = d
            else:
                skipped.append(f"{key or 'φύλλο'}: κανένας αγώνας με αποτέλεσμα")
    if not out:
        raise ValueError("Δεν βρέθηκαν αγώνες με αποτελέσματα. Τι δοκίμασα → " + " | ".join(skipped[:6]))
    return out


# ----------------------------------------------------------------------------
# ΜΟΝΤΕΛΟ (Poisson με επίθεση / άμυνα ανά ομάδα)
# ----------------------------------------------------------------------------
def _num(df, col):
    return pd.to_numeric(df[col], errors="coerce")


def goal_vectors(df, use_xg):
    hv = df["FTHG"].astype(float)
    av = df["FTAG"].astype(float)
    used = False
    if use_xg and {"HxG", "AxG"}.issubset(df.columns):
        hxg, axg = _num(df, "HxG"), _num(df, "AxG")
        if hxg.notna().mean() > 0.8 and axg.notna().mean() > 0.8:
            hv = (1 - XG_WEIGHT) * hv + XG_WEIGHT * hxg.fillna(hv)
            av = (1 - XG_WEIGHT) * av + XG_WEIGHT * axg.fillna(av)
            used = True
    return hv, av, used


def simple_vectors(df, hcol, acol):
    if not {hcol, acol}.issubset(df.columns):
        return None
    h, a = _num(df, hcol), _num(df, acol)
    if h.notna().mean() < 0.8 or a.notna().mean() < 0.8:
        return None
    return h.fillna(h.mean()), a.fillna(a.mean())


def card_vectors(df):
    base = simple_vectors(df, "HY", "AY")
    if base is None:
        return None
    hv, av = base
    if {"HR", "AR"}.issubset(df.columns):
        hv = hv + _num(df, "HR").fillna(0)
        av = av + _num(df, "AR").fillna(0)
    return hv, av


def build_ratings(df, hv, av, half_life=None, k=SHRINK_GAMES):
    rw = df["_w"].astype(float) if "_w" in df.columns else pd.Series(1.0, index=df.index)
    wsum = float(rw.sum())
    if wsum <= 0:
        return None
    lg_home = float((hv * rw).sum() / wsum)
    lg_away = float((av * rw).sum() / wsum)
    lg_avg = (lg_home + lg_away) / 2
    if lg_avg <= 0:
        return None
    long = pd.concat([
        pd.DataFrame({"team": df["HomeTeam"], "gf": hv, "ga": av, "ord": df.index, "rw": rw}),
        pd.DataFrame({"team": df["AwayTeam"], "gf": av, "ga": hv, "ord": df.index, "rw": rw}),
    ], ignore_index=True)
    long["ago"] = long.groupby("team")["ord"].rank(ascending=False, method="first") - 1
    decay = 0.5 ** (long["ago"] / half_life) if half_life else 1.0
    long["w"] = decay * long["rw"]
    long["gfw"] = long["gf"] * long["w"]
    long["gaw"] = long["ga"] * long["w"]
    g = long.groupby("team").agg(n=("w", "sum"), games=("w", "size"),
                                 gf=("gfw", "sum"), ga=("gaw", "sum"))
    g["att"] = ((g["gf"] + k * lg_avg) / (g["n"] + k)) / lg_avg
    g["dfn"] = ((g["ga"] + k * lg_avg) / (g["n"] + k)) / lg_avg
    return g, lg_home, lg_away


def expected_pair(df, vectors, home, away, half_life):
    if vectors is None:
        return None
    res = build_ratings(df, vectors[0], vectors[1], half_life)
    if res is None:
        return None
    r, lgh, lga = res
    lh = lgh * r.loc[home, "att"] * r.loc[away, "dfn"]
    la = lga * r.loc[away, "att"] * r.loc[home, "dfn"]
    return float(lh), float(la)


def poisson_pmf(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def poisson_cdf(k, lam):
    return sum(poisson_pmf(i, lam) for i in range(int(k) + 1))


def score_matrix(lh, la):
    ph = [poisson_pmf(i, lh) for i in range(MAX_GOALS + 1)]
    pa = [poisson_pmf(j, la) for j in range(MAX_GOALS + 1)]
    m = [[ph[i] * pa[j] for j in range(MAX_GOALS + 1)] for i in range(MAX_GOALS + 1)]
    tot = sum(sum(r) for r in m)
    return [[x / tot for x in r] for r in m]


def probs_from_lambdas(lh, la):
    m = score_matrix(lh, la)
    p = {k: 0.0 for k in ("1", "X", "2", "U15", "U25", "U35", "U45", "GG")}
    scores = []
    for i, row in enumerate(m):
        for j, pr in enumerate(row):
            scores.append((pr, i, j))
            if i > j:
                p["1"] += pr
            elif i == j:
                p["X"] += pr
            else:
                p["2"] += pr
            t = i + j
            for line, key in ((1, "U15"), (2, "U25"), (3, "U35"), (4, "U45")):
                if t <= line:
                    p[key] += pr
            if i > 0 and j > 0:
                p["GG"] += pr
    p["1X"], p["X2"], p["12"] = p["1"] + p["X"], p["X"] + p["2"], p["1"] + p["2"]
    for n in ("15", "25", "35", "45"):
        p["O" + n] = 1 - p["U" + n]
    p["NG"] = 1 - p["GG"]
    scores.sort(reverse=True)
    return p, scores[:5]


def analyse(df, home, away, use_xg, half_life):
    hv, av, used_xg = goal_vectors(df, use_xg)
    ratings, lgh, lga = build_ratings(df, hv, av, half_life)
    lh = float(lgh * ratings.loc[home, "att"] * ratings.loc[away, "dfn"])
    la = float(lga * ratings.loc[away, "att"] * ratings.loc[home, "dfn"])
    p, top = probs_from_lambdas(lh, la)
    return {"p": p, "lh": lh, "la": la, "top": top, "ratings": ratings, "used_xg": used_xg}


# ----------------------------------------------------------------------------
# ΠΙΝΑΚΕΣ ΚΑΙ ΣΤΑΤΙΣΤΙΚΑ ΑΠΟ ΤΟ ΑΡΧΕΙΟ
# ----------------------------------------------------------------------------
def league_table(df):
    rows = {}
    for r in df.itertuples():
        for team, gf, ga in ((r.HomeTeam, r.FTHG, r.FTAG), (r.AwayTeam, r.FTAG, r.FTHG)):
            t = rows.setdefault(team, [0, 0, 0, 0, 0, 0])   # P, W, D, L, GF, GA
            t[0] += 1
            t[4] += gf
            t[5] += ga
            if gf > ga:
                t[1] += 1
            elif gf == ga:
                t[2] += 1
            else:
                t[3] += 1
    out = []
    for team, (pl, w, d, l, gf, ga) in rows.items():
        out.append([team, pl, w, d, l, int(gf), int(ga), int(gf - ga), w * 3 + d])
    out.sort(key=lambda x: (-x[8], -x[7], -x[5]))
    return out


def points_series(df, team):
    pts, cur = [0], 0
    for r in df.itertuples():
        if r.HomeTeam == team:
            gf, ga = r.FTHG, r.FTAG
        elif r.AwayTeam == team:
            gf, ga = r.FTAG, r.FTHG
        else:
            continue
        cur += 3 if gf > ga else (1 if gf == ga else 0)
        pts.append(cur)
    return pts


def team_avg(df, team, col_home, col_away):
    if col_home not in df.columns or col_away not in df.columns:
        return None
    h = pd.to_numeric(df.loc[df["HomeTeam"] == team, col_home], errors="coerce")
    a = pd.to_numeric(df.loc[df["AwayTeam"] == team, col_away], errors="coerce")
    v = pd.concat([h, a]).dropna()
    return float(v.mean()) if len(v) else None


# ----------------------------------------------------------------------------
# ΕΜΦΑΝΙΣΗ (HTML)
# ----------------------------------------------------------------------------
def esc(x):
    return html.escape(str(x))


def card(label, prob, color):
    odds = 1 / max(prob, 1e-6)
    return (
        f'<div class="card" style="border-top:6px solid {color}">'
        f'<div class="lbl">{esc(label)}</div>'
        f'<div class="pct">{prob * 100:.1f}%</div>'
        f'<div class="odd">Δίκαιη απόδοση: {odds:.2f}</div>'
        f'<div class="bar"><div style="width:{prob * 100:.0f}%;background:{color}"></div></div>'
        f'</div>'
    )


def strength_label(p):
    if p >= 0.70:
        return "Ισχυρή ένδειξη"
    if p >= 0.55:
        return "Μέτρια ένδειξη"
    return "Αδύναμη ένδειξη"


def html_table(headers, rows, hl_rows=(), left=(0,)):
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for idx, r in enumerate(rows):
        cls = ' class="hl"' if idx in hl_rows else ""
        tds = "".join(
            f'<td class="l">{c}</td>' if j in left else f"<td>{c}</td>" for j, c in enumerate(r)
        )
        body += f"<tr{cls}>{tds}</tr>"
    return (f'<div style="overflow-x:auto"><table class="tbl"><thead><tr>{th}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def form_badges(df, team, n=5):
    games = df[(df["HomeTeam"] == team) | (df["AwayTeam"] == team)].tail(n)
    out = ""
    for _, r in games.iterrows():
        gf, ga = (r["FTHG"], r["FTAG"]) if r["HomeTeam"] == team else (r["FTAG"], r["FTHG"])
        letter, color = ("Ν", C_HOME) if gf > ga else (("Ι", C_DRAW) if gf == ga else ("Η", C_AWAY))
        out += f'<span class="badge" style="background:{color}">{letter}</span>'
    return out or "—"


def compare_row(label, a, b):
    mx = max(a, b, 1e-9)
    return (
        f'<div class="cmp"><div class="num">{a:.2f}</div><div class="md">'
        f'<div class="t">{esc(label)}</div><div class="two">'
        f'<div class="lb"><span style="width:{a / mx * 100:.0f}%;background:{C_T1}"></span></div>'
        f'<div class="rb"><span style="width:{b / mx * 100:.0f}%;background:{C_T2}"></span></div>'
        f'</div></div><div class="num">{b:.2f}</div></div>'
    )


def points_chart(series):
    """series: [(όνομα, [τιμές], χρώμα), ...] -> εικόνα SVG (base64) για st.markdown"""
    W, H, pl, pr, pt, pb = 640, 250, 40, 16, 30, 32
    n = max(len(v) for _, v, _ in series)
    ymax = max(max(v) for _, v, _ in series) or 1
    ymax = int(math.ceil(ymax / 3.0) * 3) or 3

    def X(i):
        return pl + (W - pl - pr) * (i / max(n - 1, 1))

    def Y(v):
        return H - pb - (H - pt - pb) * (v / ymax)

    s = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Arial, sans-serif">'
    for k in range(5):
        v = ymax * k / 4
        s += (f'<line x1="{pl}" y1="{Y(v):.1f}" x2="{W - pr}" y2="{Y(v):.1f}" stroke="#ffffff" stroke-opacity="0.12"/>'
              f'<text x="{pl - 6}" y="{Y(v) + 4:.1f}" font-size="11" fill="#cbd5e1" text-anchor="end">{v:.0f}</text>')
    step = max(1, n // 10)
    for i in range(0, n, step):
        s += f'<text x="{X(i):.1f}" y="{H - 10}" font-size="11" fill="#cbd5e1" text-anchor="middle">{i}</text>'
    lx = pl
    for name, vals, color in series:
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
        s += f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round"/>'
        for i, v in enumerate(vals):
            s += f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.5" fill="{color}"/>'
        s += (f'<rect x="{lx}" y="8" width="12" height="12" rx="3" fill="{color}"/>'
              f'<text x="{lx + 18}" y="19" font-size="13" fill="#ffffff">{esc(name)}</text>')
        lx += 190
    s += "</svg>"
    b64 = base64.b64encode(s.encode("utf-8")).decode()
    return f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;border-radius:12px"/>'


def totals_rows(lam):
    lines = sorted({math.floor(lam) + d + 0.5 for d in (-2, -1, 0, 1, 2)})
    rows = []
    for line in lines:
        if line <= 0:
            continue
        pu = poisson_cdf(int(line - 0.5), lam)
        po = 1 - pu
        rows.append([f"{line:g}", f"{pu * 100:.1f}%", f"{1 / max(pu, 1e-6):.2f}",
                     f"{po * 100:.1f}%", f"{1 / max(po, 1e-6):.2f}"])
    return rows


def totals_block(title, pair, home, away):
    st.markdown(f'<div class="sub">{title}</div>', unsafe_allow_html=True)
    lh, la = pair
    a, b, c = st.columns(3)
    a.metric(home, f"{lh:.2f}")
    b.metric(away, f"{la:.2f}")
    c.metric("Σύνολο", f"{lh + la:.2f}")
    st.markdown(
        html_table(["Γραμμή", "Under", "Δίκαιη απόδ.", "Over", "Δίκαιη απόδ."], totals_rows(lh + la), left=()),
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# ΑΝΑΛΥΣΗ ΟΛΗΣ ΤΗΣ ΑΓΩΝΙΣΤΙΚΗΣ (fixtures.csv με αποδόσεις)
# ----------------------------------------------------------------------------
BOOKS = [("Avg", "Μέσος όρος αγοράς"), ("Max", "Μέγιστες αποδόσεις αγοράς"), ("B365", "Bet365"),
         ("PS", "Pinnacle"), ("BW", "Betway"), ("WH", "William Hill"), ("VC", "BetVictor"),
         ("BF", "Betfair"), ("IW", "Interwetten"), ("1XB", "1xBet")]


def _odd(row, col):
    try:
        v = float(row.get(col))
    except (TypeError, ValueError):
        return None
    return v if (v == v and v > 1.0) else None


@st.cache_data(show_spinner=False)
def load_fixtures(data: bytes) -> pd.DataFrame:
    fx = read_table(data)
    for old, new in {"Home": "HomeTeam", "Away": "AwayTeam"}.items():
        if old in fx.columns and new not in fx.columns:
            fx = fx.rename(columns={old: new})
    if not {"HomeTeam", "AwayTeam"}.issubset(fx.columns):
        raise ValueError("Λείπουν οι στήλες HomeTeam / AwayTeam.")
    fx = fx.dropna(subset=["HomeTeam", "AwayTeam"]).copy()
    fx["HomeTeam"] = fx["HomeTeam"].astype(str).str.strip()
    fx["AwayTeam"] = fx["AwayTeam"].astype(str).str.strip()
    return fx.reset_index(drop=True)


def fixture_odds(row, book):
    """Αποδόσεις ενός αγώνα από το fixtures: 1Χ2, Over/Under 2.5 και (προσεγγιστικά) διπλή ευκαιρία."""
    if not row or not book:
        return {}
    oh, od, oa = _odd(row, book + "H"), _odd(row, book + "D"), _odd(row, book + "A")
    odds = {"1": oh, "X": od, "2": oa,
            "O25": _odd(row, book + ">2.5"), "U25": _odd(row, book + "<2.5")}
    if oh and od:
        odds["1X"] = 1 / (1 / oh + 1 / od)
    if od and oa:
        odds["X2"] = 1 / (1 / od + 1 / oa)
    if oh and oa:
        odds["12"] = 1 / (1 / oh + 1 / oa)
    return {k: v for k, v in odds.items() if v}


def devig(odds):
    # δεκαδικές αποδόσεις -> πιθανότητες χωρίς το περιθώριο του στοιχηματικού (κανονικοποίηση)
    if any(o is None or o != o or o <= 1.0 for o in odds):
        return None
    inv = [1 / o for o in odds]
    s = sum(inv)
    return [x / s for x in inv]


def market_probs(odds):
    out = {}
    t = devig([odds.get("1"), odds.get("X"), odds.get("2")])
    if t:
        out["1"], out["X"], out["2"] = t
        out["1X"], out["X2"], out["12"] = t[0] + t[1], t[1] + t[2], t[0] + t[2]
    u = devig([odds.get("U25"), odds.get("O25")])
    if u:
        out["U25"], out["O25"] = u
    return out


def blend_probs(p, mkt, w):
    q = dict(p)
    if w <= 0 or not mkt:
        return q
    for k, v in mkt.items():
        if k in q:
            q[k] = (1 - w) * p[k] + w * v
    return q


def market_prefix(df):
    # προτιμά τις αποδόσεις κλεισίματος (πιο αξιόπιστες), μετά τις μέσες, μετά της Bet365
    for pref in ("AvgC", "Avg", "B365C", "B365"):
        if {pref + "H", pref + "D", pref + "A"}.issubset(df.columns):
            return pref
    return None


def compare_1x2(mk):
    M = mk[["m1", "mX", "m2"]].to_numpy(dtype=float)
    K = mk[["k1", "kX", "k2"]].to_numpy(dtype=float)
    idx = mk["out"].map({"1": 0, "X": 1, "2": 2}).to_numpy()
    Y = np.eye(3)[idx]

    def metrics(w):
        P = (1 - w) * M + w * K
        brier = float(((P - Y) ** 2).sum(axis=1).mean())
        ll = float(-np.log(np.clip(P[np.arange(len(P)), idx], 1e-9, 1)).mean())
        acc = float((P.argmax(axis=1) == idx).mean())
        return brier, ll, acc
    return metrics


def compare_ou(mk):
    sub = mk.dropna(subset=["ku"])
    if len(sub) < 10:
        return None, 0
    m = sub["mu"].to_numpy(dtype=float)
    k = sub["ku"].to_numpy(dtype=float)
    y = sub["under"].to_numpy(dtype=float)

    def metrics(w):
        P = (1 - w) * m + w * k
        brier = float(((P - y) ** 2).mean())
        ll = float(-np.log(np.clip(np.where(y > 0.5, P, 1 - P), 1e-9, 1)).mean())
        acc = float(((P >= 0.5) == (y > 0.5)).mean())
        return brier, ll, acc
    return metrics, len(sub)


def render_compare_table(title, metrics, n):
    ws = (0.0, 0.25, 0.5, 0.75, 1.0)
    vals = [metrics(w) for w in ws]
    best_i = min(range(len(ws)), key=lambda i: vals[i][0])
    names = ["Μόνο μοντέλο", "25% αγορά", "50% αγορά", "75% αγορά", "Μόνο αγορά"]
    rows = [[names[i], f"{vals[i][0]:.4f}", f"{vals[i][1]:.4f}", f"{vals[i][2] * 100:.1f}%"] for i in range(len(ws))]
    st.markdown(f'<div class="sub">{title} ({n} αγώνες)</div>', unsafe_allow_html=True)
    st.markdown(html_table(["Πηγή πιθανοτήτων", "Σφάλμα (Brier)", "Σφάλμα (log)", "Πέτυχε"], rows,
                           hl_rows={best_i}), unsafe_allow_html=True)
    grid = [i / 20 for i in range(21)]
    bw = min(grid, key=lambda w: metrics(w)[0])
    if vals[4][0] < vals[0][0]:
        verdict = "Η αγορά προβλέπει καλύτερα από το μοντέλο (αναμενόμενο)."
    else:
        verdict = "Το μοντέλο τα πάει καλύτερα από την αγορά σε αυτό το δείγμα. Με λίγους αγώνες μπορεί να είναι τύχη."
    st.markdown(f'<div class="pick">{verdict}<br>Καλύτερο βάρος αγοράς για αυτά τα δεδομένα: '
                f'<b>{bw * 100:.0f}%</b></div>', unsafe_allow_html=True)


def available_books(fx):
    return [(k, n) for k, n in BOOKS
            if {k + "H", k + "D", k + "A"}.issubset(fx.columns) and fx[k + "H"].notna().any()]


def filter_fixtures(fx, df, teams):
    if "Div" in fx.columns and "Div" in df.columns and df["Div"].nunique() == 1:
        fx = fx[fx["Div"] == df["Div"].dropna().iloc[0]]
    return fx[fx["HomeTeam"].isin(teams) & fx["AwayTeam"].isin(teams)].reset_index(drop=True)


def find_fixture(fx, home, away):
    if fx is None or fx.empty:
        return None
    sub = fx[(fx["HomeTeam"] == home) & (fx["AwayTeam"] == away)]
    if sub.empty:
        return None
    if "Date" in sub.columns:
        d = pd.to_datetime(sub["Date"], dayfirst=True, errors="coerce")
        if d.notna().any():
            sub = sub.loc[[d.idxmax()]]
    return sub.iloc[-1].to_dict()


def build_model_df(df_cur, code, prev_sets, old_w):
    """Τρέχουσα σεζόν + (προαιρετικά) περσινές, με μικρότερο βάρος στις παλιές."""
    cur = df_cur.copy()
    cur["_w"] = 1.0
    cur["_cur"] = True
    olds = []
    for pl in prev_sets:
        key = code if code in pl else (next(iter(pl)) if len(pl) == 1 else None)
        if key is not None:
            olds.append(pl[key])
    if not olds:
        return cur
    olds.sort(key=lambda d: d["_date"].max() if d["_date"].notna().any() else pd.Timestamp.min)
    parts = []
    for i, d in enumerate(olds):
        d = d.copy()
        d["_w"] = old_w ** (len(olds) - i)
        d["_cur"] = False
        parts.append(d)
    return pd.concat(parts + [cur], ignore_index=True)


def venue_stats(df, team, venue):
    if venue == "H":
        g = df[df["HomeTeam"] == team]
        gf, ga = g["FTHG"], g["FTAG"]
    else:
        g = df[df["AwayTeam"] == team]
        gf, ga = g["FTAG"], g["FTHG"]
    n = len(g)
    if n == 0:
        return None
    w, d_ = int((gf > ga).sum()), int((gf == ga).sum())
    badges = ""
    for x, y in zip(gf.tail(5), ga.tail(5)):
        letter, color = ("Ν", C_HOME) if x > y else (("Ι", C_DRAW) if x == y else ("Η", C_AWAY))
        badges += f'<span class="badge" style="background:{color}">{letter}</span>'
    return [n, w, d_, n - w - d_, f"{gf.mean():.2f}", f"{ga.mean():.2f}",
            f"{(3 * w + d_) / n:.2f}", badges or "—"]


@st.cache_data(show_spinner=False)
def run_backtest(df, use_xg, half_life, min_prior=3):
    """Προβλέπει κάθε αγώνα της τρέχουσας σεζόν μόνο με όσα ήταν γνωστά πριν από αυτόν."""
    cur = df["_cur"] if "_cur" in df.columns else pd.Series(True, index=df.index)
    book = None
    for k in ("Avg", "B365"):
        if {k + "H", k + "D", k + "A"}.issubset(df.columns):
            book = k
            break
    mpref = market_prefix(df)
    counts, recs, bets, mrows = {}, [], [], []
    for i in range(len(df)):
        r = df.iloc[i]
        h, a = r["HomeTeam"], r["AwayTeam"]
        ch, ca = counts.get(h, 0), counts.get(a, 0)
        counts[h], counts[a] = ch + 1, ca + 1
        if i < 20 or ch < min_prior or ca < min_prior or not bool(cur.iloc[i]):
            continue
        sub = df.iloc[:i]
        hv, av, _ = goal_vectors(sub, use_xg)
        res = build_ratings(sub, hv, av, half_life)
        if res is None:
            continue
        ratings, lgh, lga = res
        if h not in ratings.index or a not in ratings.index:
            continue
        lh = float(lgh * ratings.loc[h, "att"] * ratings.loc[a, "dfn"])
        la = float(lga * ratings.loc[a, "att"] * ratings.loc[h, "dfn"])
        p, _top = probs_from_lambdas(lh, la)
        hg, ag = int(r["FTHG"]), int(r["FTAG"])
        tot = hg + ag
        out = "1" if hg > ag else ("X" if hg == ag else "2")

        if mpref:
            mo = devig([_odd(r, mpref + "H"), _odd(r, mpref + "D"), _odd(r, mpref + "A")])
            if mo:
                ou = devig([_odd(r, mpref + "<2.5"), _odd(r, mpref + ">2.5")])
                mrows.append({"m1": p["1"], "mX": p["X"], "m2": p["2"], "k1": mo[0], "kX": mo[1], "k2": mo[2],
                              "out": out, "mu": p["U25"], "ku": ou[0] if ou else np.nan,
                              "under": 1.0 if tot <= 2 else 0.0})

        pk = max(("1", "X", "2"), key=lambda k: p[k])
        recs.append(("1Χ2", p[pk], pk == out))
        dcs = {"1X": out in ("1", "X"), "X2": out in ("X", "2"), "12": out in ("1", "2")}
        pk = max(dcs, key=lambda k: p[k])
        recs.append(("Διπλή ευκαιρία", p[pk], dcs[pk]))
        for n, line in (("45", 4), ("25", 2)):
            pu = p["U" + n]
            if pu >= 0.5:
                recs.append((f"Under/Over {line + 0.5}", pu, tot <= line))
            else:
                recs.append((f"Under/Over {line + 0.5}", 1 - pu, tot > line))
        pg = p["GG"]
        both = hg > 0 and ag > 0
        recs.append(("Γκολ-Γκολ", pg if pg >= 0.5 else 1 - pg, both if pg >= 0.5 else not both))

        if book:
            for k, col in (("1", book + "H"), ("X", book + "D"), ("2", book + "A")):
                o = _odd(r, col)
                if o and p[k] >= 0.30 and p[k] * o - 1 >= 0.05:
                    bets.append((o - 1) if out == k else -1.0)
    return pd.DataFrame(recs, columns=["market", "prob", "hit"]), bets, book, pd.DataFrame(mrows), mpref


def render_accuracy(dfm, use_xg, half_life, code):
    st.markdown('<div class="section">🧪 Πόσο σωστό είναι το μοντέλο;</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="note">Το πρόγραμμα «προβλέπει» κάθε αγώνα που έχει ήδη παιχτεί, χρησιμοποιώντας '
        'μόνο όσα ήταν γνωστά πριν από αυτόν, και συγκρίνει με το πραγματικό αποτέλεσμα. '
        'Έτσι βλέπεις πόσο να το εμπιστεύεσαι.</div>', unsafe_allow_html=True)
    if not st.checkbox("▶️ Τρέξε τον έλεγχο (παίρνει λίγα δευτερόλεπτα)", key=f"bt_{code}"):
        return
    with st.spinner("Κάνω τον έλεγχο, περίμενε λίγο..."):
        recs, bets, book, mk, mpref = run_backtest(dfm, use_xg, half_life)
    if recs.empty:
        st.info("Δεν υπάρχουν αρκετοί αγώνες για έλεγχο. Ξαναδοκίμασε όταν έχουν παιχτεί περισσότερες αγωνιστικές.")
        return
    n = int((recs["market"] == "1Χ2").sum())
    if n < 30:
        st.markdown(f'<div class="note">⚠️ Μόνο {n} αγώνες στον έλεγχο, οπότε τα ποσοστά είναι αβέβαια.</div>',
                    unsafe_allow_html=True)
    rows = []
    for m, g in recs.groupby("market", sort=False):
        hit, avgp = float(g["hit"].mean()), float(g["prob"].mean())
        diff = hit - avgp
        if diff >= -0.03:
            verdict = '<span class="good">✅ Αξιόπιστο</span>'
        elif diff >= -0.08:
            verdict = '<span class="mid">➖ Λίγο αισιόδοξο</span>'
        else:
            verdict = '<span class="bad">⚠️ Αισιόδοξο</span>'
        rows.append([m, len(g), f"{hit * 100:.1f}%", f"{avgp * 100:.1f}%", f"{diff * 100:+.1f}", verdict])
    st.markdown(html_table(["Αγορά", "Αγώνες", "Πέτυχε", "Έλεγε (μέσος όρος)", "Διαφορά", "Κρίση"], rows),
                unsafe_allow_html=True)
    st.caption("«Πέτυχε» είναι πόσο συχνά βγήκε η πιο πιθανή επιλογή. «Έλεγε» είναι η μέση πιθανότητα που έδινε "
               "το μοντέλο. Αν το «Πέτυχε» είναι πολύ χαμηλότερο, το μοντέλο είναι υπερβολικά σίγουρο.")

    st.markdown('<div class="section">⚖️ Μοντέλο ή αγορά;</div>', unsafe_allow_html=True)
    if mk.empty:
        st.info("Το αρχείο δεν έχει αποδόσεις για τους αγώνες που παίχτηκαν, οπότε δεν γίνεται σύγκριση με την αγορά.")
    else:
        kind = "κλεισίματος" if mpref.endswith("C") else "προ του αγώνα"
        st.markdown(f'<div class="note">Συγκρίνω τις πιθανότητες του μοντέλου με αυτές της αγοράς '
                    f'(αποδόσεις {kind}, {mpref}, χωρίς το περιθώριο του στοιχηματικού) και με συνδυασμούς τους. '
                    f'Μικρότερο σφάλμα σημαίνει καλύτερες προβλέψεις.</div>', unsafe_allow_html=True)
        render_compare_table("1Χ2", compare_1x2(mk), len(mk))
        mou, nou = compare_ou(mk)
        if mou is not None:
            render_compare_table("Under/Over 2.5", mou, nou)
        st.caption("Σφάλμα Brier: πόσο κοντά ήταν οι πιθανότητες στο αποτέλεσμα (0 = τέλειο, μικρότερο = καλύτερο). "
                   "Το «καλύτερο βάρος» είναι το βάρος αγοράς στο «Συνδυασμός με την αγορά» των Ρυθμίσεων.")

    sel_mk = st.selectbox("Δες ανά επίπεδο εμπιστοσύνης για:", list(recs["market"].unique()), key=f"bt_mk_{code}")
    g = recs[recs["market"] == sel_mk]
    brows = []
    for lo, hi, name in ((0, 0.5, "κάτω από 50%"), (0.5, 0.6, "50-60%"), (0.6, 0.7, "60-70%"),
                         (0.7, 0.8, "70-80%"), (0.8, 1.01, "80% και πάνω")):
        sub = g[(g["prob"] >= lo) & (g["prob"] < hi)]
        if len(sub) > 0:
            brows.append([name, len(sub), f"{sub['prob'].mean() * 100:.1f}%", f"{sub['hit'].mean() * 100:.1f}%"])
    if brows:
        st.markdown(html_table(["Πιθανότητα που έδινε", "Αγώνες", "Έλεγε", "Πέτυχε"], brows),
                    unsafe_allow_html=True)

    st.markdown('<div class="section">💰 Αν έπαιζες τα «value» 1Χ2</div>', unsafe_allow_html=True)
    if bets:
        profit = sum(bets)
        st.markdown(
            f'<div class="pick">{len(bets)} στοιχήματα (1 μονάδα το καθένα) · '
            f'κέρδος <b>{profit:+.1f} μονάδες</b> · απόδοση επένδυσης <b>{profit / len(bets) * 100:+.1f}%</b></div>',
            unsafe_allow_html=True)
        st.caption("Με κριτήριο αναμενόμενο κέρδος τουλάχιστον 5% και πιθανότητα μοντέλου τουλάχιστον 30%, "
                   f"με τις αποδόσεις του αρχείου ({book}). Είναι προσέγγιση και με λίγους αγώνες δεν είναι ασφαλές "
                   "συμπέρασμα.")
    else:
        st.info("Δεν βρέθηκαν value στοιχήματα στο παρελθόν με αυτά τα κριτήρια, ή το αρχείο δεν έχει αποδόσεις.")


def render_fixtures(dfm, fx, book, use_xg, half_life, w_mkt=0.0):
    st.markdown('<div class="section">📅 Ανάλυση όλης της αγωνιστικής</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="note">Το αρχείο αγωνιστικής (fixtures) το ανεβάζεις στο πάνω μέρος της σελίδας. '
        'Κατέβασέ το από εδώ: '
        '<a href="https://football-data.co.uk/fixtures.csv" target="_blank" rel="noopener noreferrer" '
        'style="color:#fde68a">CSV</a> · '
        '<a href="https://football-data.co.uk/fixtures.xlsx" target="_blank" rel="noopener noreferrer" '
        'style="color:#fde68a">Excel</a></div>', unsafe_allow_html=True)
    if fx is None:
        st.info("Δεν έχεις ανεβάσει αρχείο αγωνιστικής (το δεύτερο κουτί στο πάνω μέρος).")
        return
    if fx.empty:
        st.warning("Δεν βρέθηκαν στο fixtures αγώνες με ομάδες του πρωταθλήματος που διάλεξες. "
                   "Ίσως το πρωτάθλημα δεν έχει αγώνες αυτή την περίοδο ή τα ονόματα των ομάδων διαφέρουν.")
        return

    if "Date" in fx.columns:
        dates = pd.to_datetime(fx["Date"], dayfirst=True, errors="coerce")
        if dates.notna().any():
            only_up = st.checkbox("Μόνο επερχόμενοι αγώνες", value=True, key="fx_only_upcoming")
            if only_up:
                upcoming = dates >= pd.Timestamp.today().normalize()
                if upcoming.any():
                    fx = fx[upcoming]
                else:
                    st.warning(
                        f"Όλοι οι αγώνες του αρχείου έχουν ήδη παιχτεί (ο τελευταίος στις "
                        f"{dates.max():%d/%m/%Y}). Τα νέα αρχεία ανεβαίνουν την Παρασκευή το απόγευμα "
                        f"(αγώνες Σαββατοκύριακου) και την Τρίτη το απόγευμα (αγώνες μέσα στην εβδομάδα). "
                        f"Κατέβασε ξανά το αρχείο τότε, ή βγάλε το τικ από το κουτί για να δεις τους παλιούς αγώνες.")
                    return
    if book is None:
        st.info("Το αρχείο δεν έχει αποδόσεις. Θα δεις μόνο τις πιθανότητες του μοντέλου.")

    hv, av, _ = goal_vectors(dfm, use_xg)
    ratings, lgh, lga = build_ratings(dfm, hv, av, half_life)
    recs = []
    for row in fx.to_dict("records"):
        h, a = row["HomeTeam"], row["AwayTeam"]
        if h == a or h not in ratings.index or a not in ratings.index:
            continue
        lh = float(lgh * ratings.loc[h, "att"] * ratings.loc[a, "dfn"])
        la = float(lga * ratings.loc[a, "att"] * ratings.loc[h, "dfn"])
        pm, _top = probs_from_lambdas(lh, la)
        odds = fixture_odds(row, book)
        p = blend_probs(pm, market_probs(odds), w_mkt)
        recs.append({"date": fmt_date(row.get("Date")), "home": h, "away": a,
                     "p": p, "pm": pm, "odds": odds})
    if not recs:
        st.warning("Δεν μπόρεσα να υπολογίσω κανέναν αγώνα του αρχείου.")
        return

    st.markdown(f'<div class="section">📋 Όλοι οι αγώνες ({len(recs)})</div>', unsafe_allow_html=True)
    rows, csv_rows = [], []
    for r in recs:
        p = r["p"]
        best = max(("1", "X", "2"), key=lambda k: p[k])
        cells = []
        for k in ("1", "X", "2"):
            txt = f"{p[k] * 100:.0f}%"
            cells.append(f'<span class="good">{txt}</span>' if k == best else txt)
        rows.append([esc(r["date"]), esc(r["home"]), esc(r["away"])] + cells +
                    [f"{p[k] * 100:.0f}%" for k in ("1X", "X2", "U25", "O25", "U45")])
        csv_rows.append({"Ημερομηνία": r["date"], "Γηπεδούχος": r["home"], "Φιλοξενούμενος": r["away"],
                         **{LABELS[k] + " %": round(p[k] * 100, 1)
                            for k in ("1", "X", "2", "1X", "X2", "U25", "O25", "U45")}})
    st.markdown(html_table(["Ημ/νία", "Γηπεδούχος", "Φιλοξενούμενος", "1", "Χ", "2", "1Χ", "Χ2",
                            "Under 2.5", "Over 2.5", "Under 4.5"], rows, left=(0, 1, 2)),
                unsafe_allow_html=True)

    st.markdown('<div class="section">🔝 Κορυφαίοι αγώνες ανά αγορά</div>', unsafe_allow_html=True)
    keys = list(LABELS.keys())
    c1, c2 = st.columns(2)
    mk = c1.selectbox("Αγορά", keys, index=keys.index("U45"), format_func=lambda k: LABELS[k], key="fx_market")
    topn = c2.slider("Πόσους αγώνες να δείξω", 3, 15, 5, key="fx_topn")
    ranked = sorted(recs, key=lambda r: -r["p"][mk])[:topn]
    trows = []
    for r in ranked:
        pk, o = r["p"][mk], r["odds"].get(mk)
        trows.append([f'{esc(r["home"])} - {esc(r["away"])}', esc(r["date"]), f"{pk * 100:.1f}%",
                      f"{1 / max(pk, 1e-6):.2f}", f"{o:.2f}" if o else "-",
                      f"{(pk * o - 1) * 100:+.1f}%" if o else "-"])
    st.markdown(html_table(["Αγώνας", "Ημ/νία", "Πιθανότητα", "Δίκαιη απόδ.", "Απόδοση", "Αναμ. κέρδος"],
                           trows, left=(0,)), unsafe_allow_html=True)

    if book:
        st.markdown('<div class="section">💰 Οι καλύτερες αποδόσεις (value)</div>', unsafe_allow_html=True)
        min_ev = st.slider("Ελάχιστο αναμενόμενο κέρδος (%)", 0, 30, 5, key="fx_min_ev") / 100
        min_p = st.slider("Ελάχιστη πιθανότητα μοντέλου (%)", 0, 80, 30, key="fx_min_p") / 100
        found = []
        for r in recs:
            for k, o in r["odds"].items():
                if o and o > 1 and r["p"][k] >= min_p:
                    ev = r["p"][k] * o - 1
                    if ev >= min_ev:
                        found.append((ev, r, k, o))
        found.sort(key=lambda x: -x[0])
        if found:
            vrows = [[f'{esc(r["home"])} - {esc(r["away"])}', LABELS[k], f'{r["p"][k] * 100:.1f}%',
                      f"{o:.2f}", f'<span class="good">{ev * 100:+.1f}%</span>']
                     for ev, r, k, o in found[:40]]
            st.markdown(html_table(["Αγώνας", "Αγορά", "Μοντέλο", "Απόδοση", "Αναμ. κέρδος"], vrows),
                        unsafe_allow_html=True)
        else:
            st.info("Δεν βρέθηκε value με αυτά τα φίλτρα. Δοκίμασε να χαμηλώσεις τα όρια.")
        st.caption("Οι αποδόσεις διπλής ευκαιρίας υπολογίζονται από τις 1Χ2 (προσέγγιση). "
                   "Το «value» με χαμηλή πιθανότητα είναι συχνά λάθος του μοντέλου, γι' αυτό υπάρχει φίλτρο.")

    st.download_button("📥 Αποθήκευση αγωνιστικής σε Excel (CSV)",
                       data=pd.DataFrame(csv_rows).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name="agonistiki.csv", mime="text/csv", key="fx_download")


# ----------------------------------------------------------------------------
# ΕΦΑΡΜΟΓΗ
# ----------------------------------------------------------------------------
FD_BASE = "https://www.football-data.co.uk"


def http_get(url, timeout=25):
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36", "Accept": "text/csv,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def season_code(start_year):
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def fetch_football_auto(n_prev=1):
    """Κατεβάζει από το football-data.co.uk: τρέχουσα σεζόν, περσινές και fixtures με αποδόσεις."""
    from concurrent.futures import ThreadPoolExecutor
    today = pd.Timestamp.today()
    y0 = today.year if today.month >= 7 else today.year - 1
    jobs = [(k, lg) for k in range(n_prev + 1) for lg in LEAGUES]

    def one(job):
        k, lg = job
        try:
            data = http_get(f"{FD_BASE}/mmz4281/{season_code(y0 - k)}/{lg}.csv")
            return job, clean_results(read_table(data)), None
        except Exception as e:
            return job, None, e

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(one, jobs))
    fx, fx_err = None, None
    try:
        fx = load_fixtures(http_get(f"{FD_BASE}/fixtures.csv"))
    except Exception as e:
        fx_err = e
    seasons = [dict() for _ in range(n_prev + 1)]
    failed, first_err = [], None
    for (k, lg), d, e in results:
        if d is not None and len(d) > 0:
            seasons[k][lg] = d
        else:
            failed.append(f"{lg} {season_code(y0 - k)}")
            first_err = first_err or e
    if not seasons[0]:
        raise RuntimeError(f"Δεν κατέβηκε κανένα πρωτάθλημα ({type(first_err).__name__}: {first_err})")
    return {"leagues": seasons[0], "prev_sets": [s for s in seasons[1:] if s], "fx": fx,
            "fx_err": None if fx_err is None else f"{type(fx_err).__name__}: {fx_err}",
            "failed": failed, "season": f"{y0}-{str(y0 + 1)[2:]}", "when": today.strftime("%d/%m %H:%M")}


def rank_safe(legs, W, cap, k=6.0):
    # legs: λίστα από dict: name, family, kind, mask (True/False για το μοντέλο), hist (True/False ανά παλιό αγώνα),
    # mkt (πιθανότητα αγοράς ή None). W: πίνακας πιθανοτήτων σκορ (ποδόσφαιρο) ή None (προσομοίωση).
    def prob(mask):
        return float(W[mask].sum()) if W is not None else float(np.mean(mask))
    for L in legs:
        L["pm"] = prob(L["mask"])
        L["hits"] = int(np.sum(L["hist"]))
    n = len(legs[0]["hist"]) if legs else 0

    def make(name, family, typ, pm_, hits, mkt):
        hs = (hits + k * pm_) / (n + k) if n > 0 else pm_
        return {"name": name, "family": family, "type": typ, "pm": pm_, "hits": hits, "n": n, "mkt": mkt,
                "safe": min(pm_, hs, mkt if mkt is not None else 1.0)}
    cands = [make(L["name"], L["family"], "Μονό", L["pm"], L["hits"], L["mkt"]) for L in legs]
    for i in range(len(legs)):
        for j in range(i + 1, len(legs)):
            a, b = legs[i], legs[j]
            if a["kind"] == b["kind"]:
                continue
            pj = prob(a["mask"] & b["mask"])
            if pj >= min(a["pm"], b["pm"]) - 1e-9:
                continue   # η μία επιλογή περιέχει την άλλη
            hits = int(np.sum(a["hist"] & b["hist"]))
            fam = " + ".join(sorted([a["family"], b["family"]]))
            cands.append(make(f'{a["name"]} + {b["name"]}', fam, "Κομπίνα", pj, hits, None))
    best = {}
    for r in cands:
        if 0 < r["safe"] <= cap and (r["family"] not in best or r["safe"] > best[r["family"]]["safe"]):
            best[r["family"]] = r
    return sorted(best.values(), key=lambda r: -r["safe"])


def render_safe_rows(rows, min_odds):
    if not rows:
        st.info(f"Δεν βρέθηκε επιλογή με δίκαιη απόδοση πάνω από {min_odds:.2f}. Χαμήλωσε την ελάχιστη απόδοση.")
        return
    top = rows[0]
    st.markdown(
        f'<div class="pick">🥇 Πιο ασφαλής πρόταση: <b>{esc(top["name"])}</b> ({top["type"]})<br>'
        f'Ασφάλεια: <b>{top["safe"] * 100:.1f}%</b> · δίκαιη απόδοση περίπου <b>{1 / top["safe"]:.2f}</b></div>',
        unsafe_allow_html=True)
    table = [[r["type"], esc(r["name"]), f'{r["pm"] * 100:.1f}%',
              f'{r["hits"]}/{r["n"]}' if r["type"] == "Μονό" or r["n"] else "-",
              f'{r["mkt"] * 100:.1f}%' if r["mkt"] is not None else "-",
              f'<b>{r["safe"] * 100:.1f}%</b>', f'{1 / r["safe"]:.2f}'] for r in rows[:12]]
    st.markdown(html_table(["Τύπος", "Επιλογή", "Μοντέλο", "Ιστορικό", "Αγορά", "Ασφάλεια", "Δίκαιη απόδ."],
                           table, hl_rows={0}, left=(0, 1)), unsafe_allow_html=True)
    st.caption("Η «Ασφάλεια» είναι η μικρότερη από τρεις εκτιμήσεις: το μοντέλο, το ιστορικό των δύο ομάδων "
               "(τελευταίοι 10 αγώνες της γηπεδούχου στην έδρα και 10 της φιλοξενούμενης εκτός, με λίγη εξομάλυνση) "
               "και την αγορά, όταν υπάρχουν αποδόσεις. Δείχνω την καλύτερη επιλογή ανά κατηγορία. "
               "Ασφαλές δεν σημαίνει βέβαιο: ακόμα και ένα 90% χάνεται 1 στις 10 φορές.")


def render_safe_bets(home, away, lh, la, dfm, mkt):
    st.markdown('<div class="section">🛡️ Πιο ασφαλή στοιχήματα για τον αγώνα</div>', unsafe_allow_html=True)
    st.markdown('<div class="note">Εδώ βρίσκεις τις πιο ασφαλείς επιλογές, μονές και κομπίνες (δύο επιλογές μαζί, '
                'π.χ. 1Χ + Under 4.5). Δεν με νοιάζει αν η απόδοση είναι χαμηλή, εκτός από το όριο που βάζεις παρακάτω '
                'για να μην προτείνω στοιχήματα που δεν υπάρχουν στο στοιχηματικό.</div>', unsafe_allow_html=True)
    min_odds = st.slider("Ελάχιστη απόδοση που θεωρείς λογική (π.χ. 1.08)", 1.01, 1.50, 1.08, 0.01,
                         key="safe_min_odds")
    M = np.array(score_matrix(lh, la))
    n = M.shape[0]
    H, A = np.indices((n, n))
    hh = dfm[dfm["HomeTeam"] == home].tail(10)
    aa = dfm[dfm["AwayTeam"] == away].tail(10)
    hg = np.concatenate([hh["FTHG"].to_numpy(float), aa["FTHG"].to_numpy(float)])
    ag = np.concatenate([hh["FTAG"].to_numpy(float), aa["FTAG"].to_numpy(float)])

    def leg(name, family, kind, fn, mkey=None):
        return {"name": name, "family": family, "kind": kind, "mask": fn(H, A), "hist": fn(hg, ag),
                "mkt": mkt.get(mkey) if mkey else None}
    legs = [leg("1Χ", "Διπλή ευκαιρία", "RES", lambda h, a: h >= a, "1X"),
            leg("Χ2", "Διπλή ευκαιρία", "RES", lambda h, a: a >= h, "X2"),
            leg("12", "Διπλή ευκαιρία", "RES", lambda h, a: h != a, "12"),
            leg(f"Νίκη {home}", "Νίκη", "RES", lambda h, a: h > a, "1"),
            leg(f"Νίκη {away}", "Νίκη", "RES", lambda h, a: a > h, "2")]
    for s in (1, 2):
        legs.append(leg(f"{home} +{s}.5 (δεν χάνει με {s + 1}+)", "Handicap γηπεδούχου", "RES",
                        lambda h, a, s=s: (h - a) >= -s))
        legs.append(leg(f"{away} +{s}.5 (δεν χάνει με {s + 1}+)", "Handicap φιλοξενούμενου", "RES",
                        lambda h, a, s=s: (a - h) >= -s))
    for L in (2.5, 3.5, 4.5, 5.5):
        legs.append(leg(f"Under {L:g}", "Under", "TOT", lambda h, a, L=L: (h + a) < L, "U25" if L == 2.5 else None))
    legs.append(leg("Over 1.5", "Over", "TOT", lambda h, a: (h + a) >= 2))
    legs.append(leg("Γκολ-Γκολ ΝΑΙ", "Γκολ-Γκολ", "BT", lambda h, a: (h > 0) & (a > 0)))
    legs.append(leg("Γκολ-Γκολ ΟΧΙ", "Γκολ-Γκολ", "BT", lambda h, a: (h == 0) | (a == 0)))
    render_safe_rows(rank_safe(legs, M, 1 / min_odds), min_odds)


def main():
    st.set_page_config(page_title="Ανάλυση Αγώνων", page_icon="⚽", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="hero"><div><h1>⚽ Ανάλυση Αγώνων</h1>'
        '<p>Ανέβασε το CSV του πρωταθλήματος, διάλεξε γηπεδούχο και φιλοξενούμενο '
        'και δες πιθανότητες, value, κόρνερ, κάρτες και βαθμολογία.</p></div>'
        '<a href="https://football-data.co.uk/" target="_blank" rel="noopener noreferrer">'
        '🌐 Κατέβασε αρχεία CSV</a></div>',
        unsafe_allow_html=True,
    )

    allowed = ["csv", "xlsx", "xls", "xml", "txt"]
    st.markdown('<div class="section">⚡ Αυτόματη ενημέρωση (ένα κουμπί)</div>', unsafe_allow_html=True)
    st.markdown('<div class="note">Πάτα το κουμπί και το πρόγραμμα κατεβάζει μόνο του από το football-data.co.uk '
                'τα αποτελέσματα της τρέχουσας σεζόν, τις περσινές και την αγωνιστική με τις αποδόσεις. '
                'Δεν χρειάζεται να ανεβάσεις αρχεία.</div>', unsafe_allow_html=True)
    n_prev = st.select_slider("Πόσες περσινές σεζόν να φορτώσω", options=[0, 1, 2], value=1, key="fb_nprev")
    a1, a2 = st.columns(2)
    if a1.button("⬇️ Ενημέρωση όλων", key="fb_auto_btn"):
        try:
            with st.spinner("Κατεβάζω από το football-data.co.uk (παίρνει λίγα δευτερόλεπτα)..."):
                st.session_state["fb_auto"] = fetch_football_auto(n_prev)
        except Exception as e:
            st.error(f"Δεν μπόρεσα να κατεβάσω αυτόματα. {e}. Χρησιμοποίησε τα κουτιά ανεβάσματος παρακάτω.")
    if a2.button("🗑️ Σβήσε τα αυτόματα δεδομένα", key="fb_auto_clear"):
        st.session_state.pop("fb_auto", None)
    auto = st.session_state.get("fb_auto")
    if auto is not None:
        fxn = 0 if auto["fx"] is None else len(auto["fx"])
        st.success(f"Φορτώθηκαν {len(auto['leagues'])} πρωταθλήματα (σεζόν {auto['season']}), "
                   f"{len(auto['prev_sets'])} περσινές σεζόν και {fxn} γραμμές στην αγωνιστική. "
                   f"Ενημερώθηκε: {auto['when']}.")
        if auto["failed"]:
            st.caption("Δεν βρέθηκαν (συνήθως δεν έχουν ξεκινήσει ακόμα): " + ", ".join(auto["failed"][:14]))
        if auto["fx_err"]:
            st.warning(f"Η αγωνιστική δεν κατέβηκε ({auto['fx_err']}). Μπορείς να την ανεβάσεις με το δεύτερο κουτί.")

    st.markdown('<div class="sub">Ή ανέβασε αρχεία με το χέρι (έχουν προτεραιότητα)</div>', unsafe_allow_html=True)
    up = st.file_uploader("📂 1) Αρχείο αποτελεσμάτων (το Excel της σεζόν με όλα τα πρωταθλήματα, ή ένα CSV)",
                          type=allowed)
    st.markdown(
        '<div style="font-size:.85rem;margin:-6px 0 10px 0">Βρες το Excel της σεζόν εδώ: '
        '<a href="https://football-data.co.uk/data.php" target="_blank" rel="noopener noreferrer" '
        'style="color:#fde68a">football-data.co.uk/data.php</a></div>', unsafe_allow_html=True)
    fx_up = st.file_uploader("📂 2) Αρχείο αγωνιστικής και αποδόσεων (fixtures, CSV ή Excel)",
                             type=allowed, key="fixtures_upload")
    st.markdown(
        '<div style="font-size:.85rem;margin:-6px 0 10px 0">Κατέβασέ το από εδώ: '
        '<a href="https://football-data.co.uk/fixtures.csv" target="_blank" rel="noopener noreferrer" '
        'style="color:#fde68a">CSV</a> · '
        '<a href="https://football-data.co.uk/fixtures.xlsx" target="_blank" rel="noopener noreferrer" '
        'style="color:#fde68a">Excel</a> (ανανεώνεται Παρασκευή και Τρίτη απόγευμα)</div>', unsafe_allow_html=True)
    with st.expander("➕ Προαιρετικό: περσινές σεζόν (περισσότερα δεδομένα στην αρχή της χρονιάς)"):
        prev_files = st.file_uploader("Ανέβασε το Excel ή CSV της προηγούμενης σεζόν (μπορείς και παλαιότερες)",
                                      type=allowed, accept_multiple_files=True, key="prev_upload")
    if up is None and auto is None:
        st.info("Πάτα «Ενημέρωση όλων» ή ανέβασε το αρχείο αποτελεσμάτων (Excel ή CSV από το football-data.co.uk).")
        return

    if up is not None:
        try:
            with st.spinner("Διαβάζω το αρχείο, περίμενε λίγο..."):
                leagues = load_leagues(up.getvalue())
        except Exception as e:
            st.error(f"Πρόβλημα με το αρχείο ({type(e).__name__}): {e}")
            return
    else:
        leagues = auto["leagues"]

    fx_all, fx_sig = None, "0"
    if fx_up is not None:
        try:
            fx_all = load_fixtures(fx_up.getvalue())
            fx_sig = str(len(fx_up.getvalue()))
        except Exception as e:
            st.error(f"Πρόβλημα με το αρχείο αγωνιστικής: {e}")
    elif auto is not None and auto["fx"] is not None:
        fx_all, fx_sig = auto["fx"], auto["when"]
    prev_sets = []
    for pf in (prev_files or []):
        try:
            with st.spinner("Διαβάζω την περσινή σεζόν..."):
                prev_sets.append(load_leagues(pf.getvalue()))
        except Exception as e:
            st.error(f"Πρόβλημα με το περσινό αρχείο ({pf.name}): {e}")
    if not prev_sets and auto is not None:
        prev_sets = list(auto["prev_sets"])

    codes = list(leagues.keys())
    if len(codes) > 1:
        st.markdown('<div class="section">🌍 Διάλεξε πρωτάθλημα</div>', unsafe_allow_html=True)
        code = st.selectbox("🏆 Πρωτάθλημα", codes, format_func=league_label)
    else:
        code = codes[0]
    df = leagues[code]
    if "Season" in df.columns and df["Season"].notna().any():
        st.caption(f"Σεζόν στο αρχείο: {df['Season'].iloc[-1]}")

    teams = sorted(set(df["HomeTeam"]) | set(df["AwayTeam"]))
    if len(teams) < 2 or len(df) < 5:
        st.error("Το αρχείο έχει πολύ λίγα δεδομένα για ανάλυση.")
        return
    fx_league = filter_fixtures(fx_all, df, teams) if fx_all is not None else None

    c1, c2, c3 = st.columns(3)
    c1.metric("Αγώνες", len(df))
    c2.metric("Ομάδες", len(teams))
    c3.metric("Μ.Ο. γκολ/αγώνα", f"{(df['FTHG'] + df['FTAG']).mean():.2f}")

    st.markdown('<div class="section">🏟️ Διάλεξε αγώνα</div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    home = a.selectbox("🏠 Γηπεδούχος", teams, index=0, key=f"home_{code}")
    away = b.selectbox("✈️ Φιλοξενούμενος", teams, index=1, key=f"away_{code}")
    if home == away:
        st.warning("Διάλεξε διαφορετικές ομάδες.")
        return

    with st.expander("⚙️ Ρυθμίσεις μοντέλου"):
        rec_name = st.select_slider(
            "Βάρος πρόσφατης φόρμας (οι πιο πρόσφατοι αγώνες μετράνε περισσότερο)",
            options=list(RECENCY.keys()), value="Κανένα")
        use_xg = st.checkbox("Χρήση xG (αν υπάρχει στο αρχείο)", value=True)
        old_w = 0.5
        if prev_sets:
            old_w = st.select_slider("Βάρος των αγώνων από περσινές σεζόν", options=[0.25, 0.5, 0.75],
                                     value=0.5, format_func=lambda x: f"{int(x * 100)}%")
        book = None
        if fx_league is not None and not fx_league.empty:
            avail = available_books(fx_league)
            if avail:
                bnames = dict(avail)
                book = st.selectbox("Αποδόσεις από (για το Value και την Αγωνιστική)", [k for k, _ in avail],
                                    format_func=lambda k: bnames[k], key="book_pick")
        w_mkt = st.select_slider("Συνδυασμός με την αγορά: βάρος των αποδόσεων στην τελική πιθανότητα",
                                 options=[0.0, 0.25, 0.5, 0.75], value=0.0, format_func=lambda x: f"{int(x * 100)}%")
        st.caption("Με 0% βλέπεις μόνο το μοντέλο. Αν υπάρχουν αποδόσεις (αυτόματα από το fixtures ή γραμμένες από "
                   "σένα), μπαίνουν στη μίξη για 1Χ2, διπλή ευκαιρία και Under/Over 2.5. Στην καρτέλα Ακρίβεια "
                   "φαίνεται ποιο βάρος βγάζει τα καλύτερα αποτελέσματα.")
    half_life = RECENCY[rec_name]

    dfm = build_model_df(df, code, prev_sets, old_w)
    n_old = int((~dfm["_cur"]).sum())
    if n_old:
        st.caption(f"Το μοντέλο χρησιμοποιεί και {n_old} αγώνες από προηγούμενες σεζόν.")

    res = analyse(dfm, home, away, use_xg, half_life)
    p_model, lh, la = res["p"], res["lh"], res["la"]
    p = p_model
    ratings = res["ratings"]

    n_h, n_a = int(ratings.loc[home, "games"]), int(ratings.loc[away, "games"])
    if min(n_h, n_a) < 5:
        st.markdown(
            f'<div class="note">⚠️ Λίγα δεδομένα: {esc(home)} {n_h} αγώνες, {esc(away)} {n_a} αγώνες. '
            f'Η ανάλυση είναι πιο αβέβαιη στην αρχή της σεζόν.</div>',
            unsafe_allow_html=True,
        )

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
        ["🎯 Ανάλυση", "💰 Value", "🚩 Κόρνερ/Κάρτες", "📊 Ομάδες", "🏆 Βαθμολογία", "📅 Αγωνιστική",
         "🧪 Ακρίβεια", "🛡️ Ασφαλή"])

    # ------------------------------------------------------------------ VALUE
    odds_in = {}
    with tab2:
        st.markdown('<div class="section">💰 Έλεγχος value</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="note">Αν έχεις ανεβάσει το fixtures, οι αποδόσεις συμπληρώνονται μόνες τους. Αλλιώς γράψε αυτές που βλέπεις στο στοιχηματικό. '
            'Άφησε 0 εκεί που δεν σε ενδιαφέρει. Το πρόγραμμα δείχνει αν η απόδοση είναι '
            'μεγαλύτερη από τη «δίκαιη» του μοντέλου.</div>', unsafe_allow_html=True)
        fx_row = find_fixture(fx_league, home, away)
        auto = fixture_odds(fx_row, book)
        if fx_all is not None:
            if auto:
                st.markdown(
                    f'<div class="note">✅ Οι αποδόσεις συμπληρώθηκαν από το fixtures '
                    f'({esc(fmt_date(fx_row.get("Date")))}). Μπορείς να τις αλλάξεις.</div>',
                    unsafe_allow_html=True)
            else:
                st.info("Ο αγώνας δεν βρέθηκε στο fixtures (ή δεν έχει αποδόσεις). Γράψε τις αποδόσεις με το χέρι.")
        sig = f"{book}_{fx_sig}"
        groups = [
            ("1Χ2", ["1", "X", "2"]),
            ("Διπλή ευκαιρία", ["1X", "X2", "12"]),
            ("Under / Over", ["U15", "O15", "U25", "O25", "U35", "O35", "U45", "O45"]),
            ("Γκολ-Γκολ", ["GG", "NG"]),
        ]
        for title, keys in groups:
            st.markdown(f'<div class="sub">{title}</div>', unsafe_allow_html=True)
            ncol = 4 if len(keys) > 3 else len(keys)
            cols = st.columns(ncol)
            for idx, k in enumerate(keys):
                odds_in[k] = cols[idx % ncol].number_input(
                    LABELS[k], min_value=0.0, max_value=1000.0, value=round(float(auto.get(k) or 0.0), 2),
                    step=0.05, format="%.2f", key=f"odd_{k}_{home}_{away}_{sig}")

    mkt = market_probs(odds_in)
    p = blend_probs(p_model, mkt, w_mkt)

    # ------------------------------------------------------------------ ΑΝΑΛΥΣΗ
    with tab1:
        if w_mkt > 0:
            if mkt:
                st.markdown(
                    f'<div class="note">Οι πιθανότητες 1Χ2, διπλής ευκαιρίας και Under/Over 2.5 είναι συνδυασμός: '
                    f'{int((1 - w_mkt) * 100)}% μοντέλο + {int(w_mkt * 100)}% αγορά. Τα ακριβή σκορ και οι υπόλοιπες '
                    f'αγορές είναι μόνο από το μοντέλο.</div>', unsafe_allow_html=True)
            else:
                st.info("Έβαλες βάρος αγοράς αλλά δεν υπάρχουν αποδόσεις για αυτόν τον αγώνα. Δες την καρτέλα Value.")
        st.markdown('<div class="section">🎯 Αναμενόμενο σκορ</div>', unsafe_allow_html=True)
        best = res["top"][0]
        st.markdown(
            f'<div class="pick">Αναμενόμενα γκολ: <b>{esc(home)} {lh:.2f}</b> - <b>{la:.2f} {esc(away)}</b> '
            f'(σύνολο {lh + la:.2f})<br>Πιθανότερο ακριβές σκορ: <b>{best[1]}-{best[2]}</b></div>',
            unsafe_allow_html=True)

        st.markdown('<div class="section">1️⃣ ❎ 2️⃣  Αποτέλεσμα (1Χ2)</div>', unsafe_allow_html=True)
        x1, x2, x3 = st.columns(3)
        x1.markdown(card(f"1 · {home}", p["1"], C_HOME), unsafe_allow_html=True)
        x2.markdown(card("Χ · Ισοπαλία", p["X"], C_DRAW), unsafe_allow_html=True)
        x3.markdown(card(f"2 · {away}", p["2"], C_AWAY), unsafe_allow_html=True)
        opts = {"1": p["1"], "Χ": p["X"], "2": p["2"]}
        k1 = max(opts, key=opts.get)
        st.markdown(f'<div class="pick">Πιο πιθανό: <b>{k1}</b> ({opts[k1] * 100:.1f}%) · '
                    f'{strength_label(opts[k1])}</div>', unsafe_allow_html=True)

        st.markdown('<div class="section">🛡️ Διπλή ευκαιρία</div>', unsafe_allow_html=True)
        d1, d2, d3 = st.columns(3)
        d1.markdown(card("1Χ", p["1X"], C_DC[0]), unsafe_allow_html=True)
        d2.markdown(card("Χ2", p["X2"], C_DC[1]), unsafe_allow_html=True)
        d3.markdown(card("12", p["12"], C_DC[2]), unsafe_allow_html=True)
        dc = {"1Χ": p["1X"], "Χ2": p["X2"], "12": p["12"]}
        k2 = max(dc, key=dc.get)
        st.markdown(f'<div class="pick">Ασφαλέστερη επιλογή: <b>{k2}</b> ({dc[k2] * 100:.1f}%) · '
                    f'{strength_label(dc[k2])}</div>', unsafe_allow_html=True)

        st.markdown('<div class="section">⚽ Under / Over γκολ</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for col, n in zip(cols, ("15", "25", "35", "45")):
            col.markdown(card(LABELS["U" + n], p["U" + n], C_UNDER), unsafe_allow_html=True)
        cols = st.columns(4)
        for col, n in zip(cols, ("15", "25", "35", "45")):
            col.markdown(card(LABELS["O" + n], p["O" + n], C_OVER), unsafe_allow_html=True)
        ku = "Under 4.5" if p["U45"] >= 0.5 else "Over 4.5"
        kp = max(p["U45"], 1 - p["U45"])
        st.markdown(f'<div class="pick">Για το 4.5: <b>{ku}</b> ({kp * 100:.1f}%) · '
                    f'{strength_label(kp)}</div>', unsafe_allow_html=True)

        st.markdown('<div class="section">🥅 Γκολ-Γκολ (BTTS)</div>', unsafe_allow_html=True)
        g1, g2 = st.columns(2)
        g1.markdown(card("Γκολ-Γκολ ΝΑΙ", p["GG"], C_GG), unsafe_allow_html=True)
        g2.markdown(card("Γκολ-Γκολ ΟΧΙ", p["NG"], C_NG), unsafe_allow_html=True)

        st.markdown('<div class="section">🔢 Τα 5 πιθανότερα σκορ</div>', unsafe_allow_html=True)
        rows = [[f"{i}-{j}", f"{pr * 100:.1f}%", f"{1 / pr:.1f}"] for pr, i, j in res["top"]]
        st.markdown(html_table(["Σκορ", "Πιθανότητα", "Δίκαιη απόδοση"], rows, left=()),
                    unsafe_allow_html=True)

    with tab2:
        rows = []
        for k in LABELS:
            o = odds_in.get(k, 0.0)
            if o and o > 1.0:
                pf, pm_ = p[k], p_model[k]
                ev = pf * o - 1
                if ev >= 0.05:
                    verdict = '<span class="good">✅ Value</span>'
                elif ev > -0.05:
                    verdict = '<span class="mid">➖ Οριακό</span>'
                else:
                    verdict = '<span class="bad">❌ Όχι value</span>'
                mk_txt = f"{mkt[k] * 100:.1f}%" if k in mkt else "-"
                rows.append([LABELS[k], f"{pm_ * 100:.1f}%", mk_txt, f"{pf * 100:.1f}%", f"{o:.2f}",
                             f"{ev * 100:+.1f}%", verdict])
        st.markdown('<div class="section">📋 Αποτέλεσμα ελέγχου</div>', unsafe_allow_html=True)
        if rows:
            st.markdown(html_table(
                ["Αγορά", "Μοντέλο", "Αγορά (χωρίς περιθώριο)", "Τελική", "Η απόδοσή σου", "Αναμ. κέρδος", "Κρίση"],
                rows), unsafe_allow_html=True)
            st.caption("Αναμενόμενο κέρδος = τελική πιθανότητα × απόδοση − 1. Η «Αγορά» είναι η πιθανότητα που βγαίνει "
                       "από τις αποδόσεις αφού αφαιρεθεί το περιθώριο του στοιχηματικού (υπάρχει για 1Χ2, διπλή "
                       "ευκαιρία και Under/Over 2.5). Η «Τελική» είναι μίξη μοντέλου και αγοράς, με το βάρος των "
                       "Ρυθμίσεων. Με 0% η τελική είναι μόνο το μοντέλο.")
        else:
            st.info("Γράψε τουλάχιστον μία απόδοση (πάνω από 1.00) για να δεις τον έλεγχο.")

    # ------------------------------------------------------------------ ΚΟΡΝΕΡ / ΚΑΡΤΕΣ
    with tab3:
        corners = expected_pair(dfm, simple_vectors(dfm, "HC", "AC"), home, away, half_life)
        cards = expected_pair(dfm, card_vectors(dfm), home, away, half_life)
        if corners is None and cards is None:
            st.info("Το αρχείο δεν έχει στήλες για κόρνερ (HC, AC) ή κάρτες (HY, AY).")
        else:
            st.markdown('<div class="section">🚩 Κόρνερ</div>', unsafe_allow_html=True)
            if corners:
                totals_block("Αναμενόμενα κόρνερ", corners, home, away)
            else:
                st.info("Δεν βρέθηκαν στατιστικά κόρνερ στο αρχείο.")
            st.markdown('<div class="section">🟨 Κάρτες (κίτρινες + κόκκινες)</div>', unsafe_allow_html=True)
            if cards:
                totals_block("Αναμενόμενες κάρτες", cards, home, away)
            else:
                st.info("Δεν βρέθηκαν στατιστικά καρτών στο αρχείο.")
            st.caption("Προσέγγιση με μοντέλο Poisson. Για τις κάρτες παίζει μεγάλο ρόλο και ο διαιτητής, "
                       "που δεν υπάρχει στο μοντέλο.")

    # ------------------------------------------------------------------ ΟΜΑΔΕΣ
    with tab4:
        st.markdown('<div class="section">📈 Φόρμα (τελευταίοι 5 αγώνες)</div>', unsafe_allow_html=True)
        f1, f2 = st.columns(2)
        f1.markdown(f"**{esc(home)}**", unsafe_allow_html=True)
        f1.markdown(form_badges(df, home), unsafe_allow_html=True)
        f2.markdown(f"**{esc(away)}**", unsafe_allow_html=True)
        f2.markdown(form_badges(df, away), unsafe_allow_html=True)

        st.markdown('<div class="section">🏠✈️ Φόρμα εντός / εκτός έδρας</div>', unsafe_allow_html=True)
        vrows, vhl = [], set()
        for team, venue, label, relevant in ((home, "H", "εντός", True), (home, "A", "εκτός", False),
                                             (away, "H", "εντός", False), (away, "A", "εκτός", True)):
            s = venue_stats(df, team, venue)
            if s:
                if relevant:
                    vhl.add(len(vrows))
                vrows.append([f"{esc(team)} ({label})"] + s)
        if vrows:
            st.markdown(html_table(["Ομάδα", "Αγ", "Ν", "Ι", "Η", "Γκολ υπέρ", "Γκολ κατά", "Βαθμοί/αγώνα",
                                    "Τελευταίοι 5"], vrows, hl_rows=vhl, left=(0,)), unsafe_allow_html=True)
            st.caption("Φωτισμένες οι γραμμές που αφορούν αυτόν τον αγώνα: γηπεδούχος εντός, φιλοξενούμενος εκτός.")

        st.markdown('<div class="section">⚔️ Σύγκριση ομάδων (μέσος όρος ανά αγώνα)</div>',
                    unsafe_allow_html=True)
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;font-weight:700">'
            f'<span style="color:{C_T1}">● {esc(home)}</span>'
            f'<span style="color:{C_T2}">{esc(away)} ●</span></div>', unsafe_allow_html=True)
        specs = [("Γκολ υπέρ", "FTHG", "FTAG"), ("Γκολ κατά", "FTAG", "FTHG"), ("xG υπέρ", "HxG", "AxG"),
                 ("Σουτ", "HS", "AS"), ("Σουτ εντός στόχου", "HST", "AST"), ("Κόρνερ", "HC", "AC"),
                 ("Φάουλ", "HF", "AF"), ("Κίτρινες κάρτες", "HY", "AY")]
        bars = ""
        for label, ch, ca in specs:
            va, vb = team_avg(df, home, ch, ca), team_avg(df, away, ch, ca)
            if va is not None and vb is not None:
                bars += compare_row(label, va, vb)
        st.markdown(bars or "Δεν υπάρχουν αρκετά στατιστικά στο αρχείο.", unsafe_allow_html=True)

        st.markdown('<div class="section">📉 Βαθμοί ανά αγωνιστική</div>', unsafe_allow_html=True)
        st.markdown(points_chart([(home, points_series(df, home), C_T1),
                                  (away, points_series(df, away), C_T2)]), unsafe_allow_html=True)

        st.markdown('<div class="section">🤝 Αμοιβαίοι αγώνες στο αρχείο</div>', unsafe_allow_html=True)
        h2h = dfm[((dfm["HomeTeam"] == home) & (dfm["AwayTeam"] == away))
                  | ((dfm["HomeTeam"] == away) & (dfm["AwayTeam"] == home))]
        if h2h.empty:
            st.write("Δεν υπάρχουν στο αρχείο.")
        else:
            rows = [[esc(fmt_date(r["Date"])) if "Date" in h2h.columns else "-", esc(r["HomeTeam"]),
                     f'{int(r["FTHG"])}-{int(r["FTAG"])}', esc(r["AwayTeam"])]
                    for _, r in h2h.iterrows()]
            st.markdown(html_table(["Ημ/νία", "Γηπεδούχος", "Σκορ", "Φιλοξενούμενος"], rows, left=(1, 3)),
                        unsafe_allow_html=True)

    # ------------------------------------------------------------------ ΒΑΘΜΟΛΟΓΙΑ
    with tab5:
        st.markdown('<div class="section">🏆 Βαθμολογία από το αρχείο</div>', unsafe_allow_html=True)
        lt = league_table(df)
        rows = [[i + 1, esc(r[0])] + r[1:] for i, r in enumerate(lt)]
        hl = {i for i, r in enumerate(lt) if r[0] in (home, away)}
        st.markdown(html_table(["#", "Ομάδα", "Αγ", "Ν", "Ι", "Η", "ΓΥ", "ΓΚ", "ΔΓ", "Βαθμ"],
                               rows, hl_rows=hl, left=(1,)), unsafe_allow_html=True)
        st.caption("Ταξινόμηση: βαθμοί, διαφορά γκολ, γκολ υπέρ. Με φωτισμό οι δύο ομάδες του αγώνα.")

    with tab6:
        render_fixtures(dfm, fx_league, book, use_xg, half_life, w_mkt)

    with tab7:
        render_accuracy(dfm, use_xg, half_life, code)

    with tab8:
        render_safe_bets(home, away, lh, la, dfm, mkt)

    # ------------------------------------------------------------------ ΑΠΟΘΗΚΕΥΣΗ
    st.markdown('<div class="section">💾 Αποθήκευση ανάλυσης</div>', unsafe_allow_html=True)
    table = []
    for k in LABELS:
        o = odds_in.get(k, 0.0) or 0.0
        row = {"Αγορά": LABELS[k], "Πιθανότητα %": round(p[k] * 100, 1),
               "Μοντέλο %": round(p_model[k] * 100, 1),
               "Δίκαιη απόδοση": round(1 / max(p[k], 1e-6), 2),
               "Απόδοση στοιχηματικού": round(o, 2) if o > 1 else "",
               "Αναμενόμενο κέρδος %": round((p[k] * o - 1) * 100, 1) if o > 1 else ""}
        table.append(row)
    out_df = pd.DataFrame(table)
    csv_bytes = out_df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")

    lines = [f"ΑΝΑΛΥΣΗ: {home} - {away}",
             f"Αναμενόμενα γκολ: {home} {lh:.2f} - {la:.2f} {away}",
             f"Πιθανότερο σκορ: {res['top'][0][1]}-{res['top'][0][2]}", ""]
    for r in table:
        extra = f" | απόδοση {r['Απόδοση στοιχηματικού']} | κέρδος {r['Αναμενόμενο κέρδος %']}%" \
            if r["Απόδοση στοιχηματικού"] != "" else ""
        lines.append(f"{r['Αγορά']}: {r['Πιθανότητα %']}% (δίκαιη {r['Δίκαιη απόδοση']}){extra}")
    lines += ["", "Στατιστική εκτίμηση, όχι εγγύηση αποτελέσματος."]
    txt_bytes = "\n".join(lines).encode("utf-8")

    safe = f"{home}_vs_{away}".replace(" ", "_")
    s1, s2 = st.columns(2)
    s1.download_button("📥 Αποθήκευση σε Excel (CSV)", data=csv_bytes,
                       file_name=f"{safe}.csv", mime="text/csv")
    s2.download_button("📄 Αποθήκευση ως κείμενο", data=txt_bytes,
                       file_name=f"{safe}.txt", mime="text/plain")

    st.caption(
        "Η ανάλυση βασίζεται σε στατιστικό μοντέλο (Poisson) πάνω στα γκολ"
        + (" και τα xG" if res["used_xg"] else "")
        + " του αρχείου. Δείχνει πιθανότητες, όχι βέβαιο αποτέλεσμα."
    )


def _running_in_streamlit():
    try:
        from streamlit.runtime import exists
        return exists()
    except Exception:
        return False


if _running_in_streamlit():
    main()
elif __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
