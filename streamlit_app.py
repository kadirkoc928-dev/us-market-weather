import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Profi US Market Weather & Signals", page_icon="⛈️", layout="wide")

st.title("🌤️ Profi-US-Börsenwetter & Index-Kaufsignale")
st.markdown("Dieses Tool analysiert das Wall-Street-Sentiment und gibt für jeden globalen Index eine **direkte Kauf- oder Meiden-Empfehlung** aus.")

# --- SEKTOR-ETFS ---
SEKTOREN = {
    "Technologie (XLK)": "XLK",
    "Finanzen (XLF)": "XLF",
    "Gesundheit (XLV)": "XLV",
    "Zyklischer Konsum (XLY)": "XLY",
    "Energie (XLE)": "XLE",
    "Industrie (XLI)": "XLI",
    "Basis-Konsumgüter (XLP)": "XLP",
    "Versorger (XLU)": "XLU",
    "Materialien (XLB)": "XLB",
    "Immobilien (XLRE)": "XLRE"
}

# --- ERWEITERTE AKTIEN-MATRIX ---
SEKTOR_AKTIEN = {
    "XLK": ["AAPL", "MSFT", "NVDA", "AVGO", "AMD", "QCOM", "ORCL", "CSCO", "INTU", "AMAT", "PANW", "MU", "ADI", "NOW", "LRCX"],
    "XLF": ["JPM", "BAC", "MS", "GS", "WFC", "C", "BRK-B", "BLK", "SPGI", "AXP", "V", "MA", "SCHW", "CB", "MMC"],
    "XLV": ["LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "PFE", "ABT", "DHR", "AMGN", "ISRG", "GILD", "VRTX", "REGN", "BMY"],
    "XLY": ["AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "BKNG", "TJX", "ORLY", "CMG", "MAR", "NCLH", "RCL", "F"],
    "XLE": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "HES", "HAL", "BKR", "DVN", "FANG", "WMB", "OXY"],
    "XLI": ["GE", "CAT", "UNP", "HON", "RTX", "LMT", "UPS", "BA", "DE", "MMM", "ADP", "WM", "FEDX", "NOC", "CSX"],
    "XLP": ["PG", "COST", "KO", "PEP", "WMT", "PM", "MO", "MDLZ", "CL", "KHC", "GIS", "STZ", "SYY", "EL", "KR"],
    "XLU": ["NEE", "SO", "DUK", "CEG", "AEP", "D", "EXC", "SRE", "XEL", "ED", "PEG", "WEC", "AWK", "EIX", "FE"],
    "XLB": ["LIN", "APD", "SHW", "FCX", "NUE", "ECL", "DD", "CTVA", "ALB", "NEM", "PPG", "VMC", "MLM", "CF", "MOS"],
    "XLRE": ["PLD", "AMT", "EQIX", "WELL", "O", "CCI", "PSA", "DLR", "WY", "AVB", "EQR", "VICI", "SBAC", "CBRE", "IRM"]
}

def analyze_stock_or_index(ticker, is_index_or_sector=True):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty or len(hist) < 200:
            return None
        
        close = hist['Close']
        last_close = close.iloc[-1]
        prev_close = close.iloc[-2]
        perf_24h = ((last_close - prev_close) / prev_close) * 100
        
        # EMAs
        emas = {10: 10, 20: 20, 50: 50, 100: 100, 200: 200}
        ema_score = 0
        for p in emas:
            val = close.ewm(span=p, adjust=False).mean().iloc[-1]
            if last_close > val:
                ema_score += 10
                
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        
        rsi_score = 0
        if 45 <= rsi <= 65: rsi_score = 25
        elif 30 <= rsi < 45: rsi_score = 15
        elif 65 < rsi <= 75: rsi_score = 10
        
        # MACD
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_score = 25 if macd.iloc[-1] > signal.iloc[-1] else 0
        
        score = int(ema_score + rsi_score + macd_score)
        
        # --- LOGIK FÜR DAS KAUFSIGNAL ---
        if score >= 75 and rsi < 68:
            signal_text = "🟢 JETZT KAUFEN"
        elif score >= 50 and rsi < 75:
            signal_text = "⚠️ HALTEN / WARTEN"
        else:
            signal_text = "🔴 FINGER WEG (MEIDEN)"
            
        return {
            "Ticker": ticker,
            "Kurs": round(last_close, 2),
            "Perf 24h": perf_24h,
            "RSI": round(rsi, 1),
            "Score": score,
            "Signal": signal_text
        }
    except:
        return None

# --- ENGINE ---
if st.button("📊 Institutionellen Wetterbericht & Kaufsignale laden"):
    with st.spinner("Berechne Markt-Wetter, Sektoren und generiere Kaufsignale..."):
        
        # 1. Makro-Daten ziehen
        vix_hist = yf.Ticker("^VIX").history(period="5d")
        current_vix = vix_hist['Close'].iloc[-1] if not vix_hist.empty else 15.0
        us10y_hist = yf.Ticker("^TNX").history(period="5d")
        current_us10y = (us10y_hist['Close'].iloc[-2] / 10) if not us10y_hist.empty else 4.0

        # 2. Haupt-Indizes parallel scannen
        INDIZES = {"S&P 500 (SPY)": "SPY", "Nasdaq 100 (QQQ)": "QQQ", "Russell 2000": "^RUT", "Dow Jones": "^DJI", "DAX": "^GDAXI", "Nikkei 225": "^N225"}
        index_data = {}
        total_us_score, us_count = 0, 0
        
        for name, ticker in INDIZES.items():
            res = analyze_stock_or_index(ticker)
            if res:
                index_data[name] = res
                if ticker in ["SPY", "QQQ", "^RUT", "^DJI"]:
                    total_us_score += res["Score"]
                    us_count += 1
        base_score = total_us_score // us_count if us_count > 0 else 50
        market_score = max(0, base_score - 15) if current_vix > 22 else (min(100, base_score + 10) if current_vix < 13 else base_score)

        # 3. Sektoren scannen
        sector_perf = []
        for name, ticker in SEKTOREN.items():
            res = analyze_stock_or_index(ticker)
            if res:
                sector_perf.append({"SektorName": name, "SektorTicker": ticker, "Tagesperformance": res["Perf 24h"], "Trend-Score": res["Score"]})
        df_sectors = pd.DataFrame(sector_perf).sort_values(by="Tagesperformance", ascending=False)

        # --- SEKTOR ROTATION AKTIEN FILTERUNG ---
        top_sector_id = df_sectors.iloc[0]["SektorTicker"]
        bottom_sector_id = df_sectors.iloc[-1]["SektorTicker"]
        
        aktien_zu_scannen = SEKTOR_AKTIEN[top_sector_id] + SEKTOR_AKTIEN[bottom_sector_id]
        aktien_ergebnisse = []
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(analyze_stock_or_index, t) for t in aktien_zu_scannen]
            for future in futures:
                r = future.result()
                if r: aktien_ergebnisse.append(r)
                
        df_all_stocks = pd.DataFrame(aktien_ergebnisse)
        
        df_winners = df_all_stocks[df_all_stocks["Ticker"].isin(SEKTOR_AKTIEN[top_sector_id])].sort_values(by="Score", ascending=False).head(10)
        df_losers = df_all_stocks[df_all_stocks["Ticker"].isin(SEKTOR_AKTIEN[bottom_sector_id])].sort_values(by="Score", ascending=True).head(10)

        # --- OBERFLÄCHE: METRIKEN ---
        st.subheader("🚨 Institutionelle Risiko-Kennzahlen")
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric(label=f"VIX (Angst-Index)", value=f"{round(current_vix, 2)} Pkt.")
        with m_col2:
            st.metric(label="US-Zinsen (10J Rendite)", value=f"{round(current_us10y, 3)}%")
        with m_col3:
            risk_ratio = index_data.get("Russell 2000", {}).get("Perf 24h", 0) - index_data.get("S&P 500 (SPY)", {}).get("Perf 24h", 0)
            st.metric(label="Markt-Modus", value="🚀 RISK-ON" if risk_ratio > 0.3 else ("🛡️ RISK-OFF" if risk_ratio < -0.3 else "⚖️ Neutral"))

        st.markdown("---")

        # --- MAIN WEATHER REPORT ---
        st.subheader("🇺🇸 Das kombinierte US-Börsenwetter")
        col1, col2 = st.columns([1, 2])
        with col1:
            if market_score >= 75: st.markdown("# ☀️ STRAHLENDER SONNENSCHEIN")
            elif 55 <= market_score < 75: st.markdown("# 🌤️ LEICHT BEWÖLKT")
            elif 40 <= market_score < 55: st.markdown("# 🌧️ REGENWETTER")
            else: st.markdown("# ⛈️ SCHWERES UNWETTER")
            st.info(f"**Gesamt-Sentiment: {market_score}%**")
        with col2:
            st.markdown("### 🏹 Taktischer Trading-Fahrplan für heute:")
            if market_score >= 55: st.markdown("> **FOKUS GEWINNER:** Schau dir die **Top 10 Rotations-Gewinner** an. Diese Aktien reiten die aktuelle Sektorwelle am saubersten nach oben.")
            else: st.markdown("> **VORSICHT / SHORT-FOKUS:** Defensiver Modus. Die **Top 10 Rotations-Verlierer** zeigen schwere technische Schwächen und sind stark rückschlagsgefährdet.")

        st.markdown("---")
        
        # --- GLOBALER DASHBOARD JETZT HIER OBEN ---
        st.subheader("🌐 Globales Index-Dashboard & Kaufsignale")
        st.markdown("Diese Signale basieren auf der Auswertung von RSI, MACD und allen EMAs:")
        idx_rows = [{ 
            "Index / Asset": k, 
            "Trading-Signal": v["Signal"], # Hier ist die neue Spalte!
            "Aktueller Kurs": v["Kurs"], 
            "Tagesperformance": f"{round(v['Perf 24h'], 2)}%", 
            "RSI (14d)": v["RSI"], 
            "Technischer Score": f"{v['Score']}/100" 
        } for k, v in index_data.items()]
        
        # Darstellung als interaktiver Daten-Editor für eine noch cleanere Optik
        st.data_editor(pd.DataFrame(idx_rows), use_container_width=True, disabled=True, hide_index=True)

        st.markdown("---")
        
        # --- SEKTOREN ---
        st.subheader("🔄 US-Sektoren-Analyse")
        col_sec1, col_sec2 = st.columns(2)
        with col_sec1:
            st.markdown("### 📈 Top Zuflüsse (Stärkster Sektor)")
            st.dataframe(df_sectors.head(1)[["SektorName", "Tagesperformance", "Trend-Score"]], use_container_width=True, hide_index=True)
        with col_sec2:
            st.markdown("### 📉 Top Abflüsse (Schwächster Sektor)")
            st.dataframe(df_sectors.tail(1)[["SektorName", "Tagesperformance", "Trend-Score"]], use_container_width=True, hide_index=True)

        # --- DIE 20 ROTATIONS AKTIEN ---
        st.markdown("---")
        st.subheader("🎯 Die 20 Fokus-Aktien der aktuellen Sektoren-Rotation")
        
        col_st1, col_st2 = st.columns(2)
        
        with col_st1:
            st.markdown(f"### 🚀 Top 10 Gewinner (Sektor: {df_sectors.iloc[0]['SektorName']})")
            df_winners_show = df_winners.rename(columns={"Perf 24h": "Tages-Perf", "Score": "Swing-Score"})
            df_winners_show["Tages-Perf"] = df_winners_show["Tages-Perf"].map("{:,.2f}%".format)
            df_winners_show["Trading-Link"] = df_winners_show["Ticker"].apply(lambda t: f"https://www.tradingview.com/chart/?symbol=NASDAQ:{t}")
            st.data_editor(df_winners_show, column_config={"Trading-Link": st.column_config.LinkColumn("Chart", display_text="↗ Chart")}, disabled=True, use_container_width=True, hide_index=True, height=380)
            
        with col_st2:
            st.markdown(f"### 📉 Top 10 Verlierer (Sektor: {df_sectors.iloc[-1]['SektorName']})")
            df_losers_show = df_losers.rename(columns={"Perf 24h": "Tages-Perf", "Score": "Swing-Score"})
            df_losers_show["Tages-Perf"] = df_losers_show["Tages-Perf"].map("{:,.2f}%".format)
            df_losers_show["Trading-Link"] = df_losers_show["Ticker"].apply(lambda t: f"https://www.tradingview.com/chart/?symbol=NASDAQ:{t}")
            st.data_editor(df_losers_show, column_config={"Trading-Link": st.column_config.LinkColumn("Chart", display_text="↗ Chart")}, disabled=True, use_container_width=True, hide_index=True, height=380)
