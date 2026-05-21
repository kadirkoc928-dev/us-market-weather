import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Profi US Market Weather", page_icon="⛈️", layout="wide")

st.title("🌤️ Profi-US-Börsenwetter & institutionelles Sentiment")
st.markdown("Dieses Tool kombiniert technische Indikatoren (RSI, MACD, EMAs) mit den wichtigsten makroökonomischen Treibern der Wall Street (**VIX, Anleiherenditen & Risk-On-Verhältnis**).")

# --- INDIZES & MAKRO-DATEN ---
INDIZES = {
    "S&P 500 ETF (SPY)": "SPY",
    "Nasdaq 100 ETF (QQQ)": "QQQ",
    "Russell 2000 (Small Caps)": "^RUT",
    "Dow Jones Industrial": "^DJI",
    "Dax (Deutschland)": "^GDAXI",
    "Nikkei 225 (Japan)": "^N225"
}

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

def analyze_sentiment(ticker):
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
        
        return {
            "Kurs": round(last_close, 2),
            "Perf 24h": perf_24h,
            "RSI": round(rsi, 1),
            "Score": int(ema_score + rsi_score + macd_score)
        }
    except:
        return None

# --- ENGINE ---
if st.button("📊 Institutionellen Wetterbericht erstellen"):
    with st.spinner("Frage Wall-Street-Daten, VIX und Staatsanleihen ab..."):
        
        # 1. Makro-Daten live ziehen
        vix_ticker = yf.Ticker("^VIX")
        vix_hist = vix_ticker.history(period="5d")
        current_vix = vix_hist['Close'].iloc[-1] if not vix_hist.empty else 15.0
        
        us10y_ticker = yf.Ticker("^TNX") # ^TNX = 10 Year Treasury Note Yield (*10)
        us10y_hist = us10y_ticker.history(period="5d")
        current_us10y = (us10y_hist['Close'].iloc[-1] / 10) if not us10y_hist.empty else 4.0

        # 2. Indizes abrufen
        index_data = {}
        total_us_score = 0
        us_count = 0
        
        for name, ticker in INDIZES.items():
            res = analyze_sentiment(ticker)
            if res:
                index_data[name] = res
                if ticker in ["SPY", "QQQ", "^RUT", "^DJI"]:
                    total_us_score += res["Score"]
                    us_count += 1
                    
        base_score = total_us_score // us_count if us_count > 0 else 50
        
        # --- INSTITUTIONELLE SCORE-ANPASSUNG (VIX-Malus/Bonus) ---
        if current_vix > 22:
            market_score = max(0, base_score - 15) # Abzug wegen hoher Panik
        elif current_vix < 13:
            market_score = min(100, base_score + 10) # Bonus wegen extremer Stabilität
        else:
            market_score = base_score

        # 3. Sektoren abrufen
        sector_perf = []
        for name, ticker in SEKTOREN.items():
            res = analyze_sentiment(ticker)
            if res:
                sector_perf.append({
                    "Sektor": name,
                    "Tagesperformance": res["Perf 24h"],
                    "Trend-Score": res["Score"]
                })
        df_sectors = pd.DataFrame(sector_perf).sort_values(by="Tagesperformance", ascending=False)

        # --- OBERFLÄCHE: METRIKEN-DASHBOARD ---
        st.subheader("🚨 Institutionelle Risiko-Kennzahlen")
        m_col1, m_col2, m_col3 = st.columns(3)
        
        with m_col1:
            vix_status = "🟢 Ruhig" if current_vix < 15 else ("🟡 Nervös" if current_vix <= 22 else "🔴 PANIK")
            st.metric(label=f"VIX (Angst-Index): {vix_status}", value=f"{round(current_vix, 2)} Pkt.", delta=f"{round(current_vix - vix_hist['Close'].iloc[-2], 2)} Pkt.", delta_color="inverse")
            
        with m_col2:
            st.metric(label="US-Zinsen (10 Jahre Staatsanleihen)", value=f"{round(current_us10y, 3)}%", delta=f"{round(current_us10y - (us10y_hist['Close'].iloc[-2]/10), 3)}%", delta_color="inverse")
            
        with m_col3:
            # Risk-On / Off Verhältnis ermitteln
            rut_perf = index_data.get("Russell 2000 (Small Caps)", {}).get("Perf 24h", 0)
            spy_perf = index_data.get("S&P 500 ETF (SPY)", {}).get("Perf 24h", 0)
            risk_ratio = rut_perf - spy_perf
            risk_text = "🚀 RISK-ON (Spekulativ stark)" if risk_ratio > 0.3 else ("🛡️ RISK-OFF (Flucht in Large Caps)" if risk_ratio < -0.3 else "⚖️ Neutrale Verteilung")
            st.metric(label="Markt-Modus", value=risk_text, delta=f"{round(risk_ratio, 2)}% Differenz")

        st.markdown("---")

        # --- MAIN WEATHER REPORT ---
        st.subheader("🇺🇸 Das kombinierte US-Börsenwetter")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if market_score >= 75:
                st.markdown("# ☀️ STRAHLENDER SONNENSCHEIN")
                st.success(f"**Gesamt-Sentiment: {market_score}%** \n\nPerfekte Bedingungen. Niedriger VIX schützt nach unten ab. Die Bullen haben die vollständige Kontrolle über die EMAs.")
            elif 55 <= market_score < 75:
                st.markdown("# 🌤️ LEICHT BEWÖLKT")
                st.info(f"**Gesamt-Sentiment: {market_score}%** \n\nDer Markt ist stabil, aber die Zinsen oder der VIX mahnen zu leichter Vorsicht. Swing-Trading läuft gut.")
            elif 40 <= market_score < 55:
                st.markdown("# 🌧️ REGENWETTER")
                st.warning(f"**Gesamt-Sentiment: {market_score}%** \n\nPreise rutschen unter wichtige EMAs. Institutionelle Händler halten sich zurück. Absichern!")
            else:
                st.markdown("# ⛈️ SCHWERES UNWETTER / REZESSIONS-ANGST")
                st.error(f"**Gesamt-Sentiment: {market_score}%** \n\nDer VIX kocht über oder die EMAs sind komplett gebrochen. Akute Gefahr für Hebel-Käufe.")

        with col2:
            st.markdown("### 🏹 Taktischer Trading-Fahrplan für heute:")
            if market_score >= 75:
                st.markdown(f"> **HEUTE AGGRESSIV:** Der Markt belohnt Risiko. Nutze Ausbrüche über den EMA 10/20 bei starken Einzelaktien. VIX bei {round(current_vix, 1)} signalisiert freie Fahrt.")
            elif 55 <= market_score < 75:
                st.markdown("> **HEUTE SELEKTIV:** Investieren ja, aber Stopp-Losses enger nachziehen. Keine gierigen Übergewichtungen vornehmen.")
            elif 40 <= market_score < 55:
                st.markdown("> **HEUTE DEFENSIV:** Reduziere die Positionsgrößen um die Hälfte. Kaufe nur, wenn Werte extrem überverkauft am Support aufschlagen.")
            else:
                st.markdown("> **HEUTE CASH HALTEN:** Institutionelle löschen Risiken. Jeder Intraday-Anstieg droht abverkauft zu werden. Fokus auf Kapitalerhalt.")

        st.markdown("---")
        
        # --- DASHBOARDS ---
        st.subheader("🌐 Globales Index-Dashboard")
        idx_rows = []
        for name, data in index_data.items():
            status = "🔥 Bullisch" if data["Score"] >= 70 else ("⚖️ Neutral" if data["Score"] >= 45 else "🚨 Bärisch")
            idx_rows.append({
                "Index / Asset": name,
                "Aktueller Kurs": data["Kurs"],
                "Tagesperformance": f"{round(data['Perf 24h'], 2)}%",
                "RSI (14d)": data["RSI"],
                "Technischer Score": f"{data['Score']}/100",
                "Zustand": status
            })
        st.table(pd.DataFrame(idx_rows))

        st.markdown("---")

        st.subheader("🔄 US-Sektoren-Analyse")
        col_sec1, col_sec2 = st.columns(2)
        with col_sec1:
            st.markdown("### 📈 Top Zuflüsse")
            st.dataframe(df_sectors.head(4).style.format({"Tagesperformance": "{:,.2f}%"}), use_container_width=True)
        with col_sec2:
            st.markdown("### 📉 Top Abflüsse")
            st.dataframe(df_sectors.tail(4).style.format({"Tagesperformance": "{:,.2f}%"}), use_container_width=True)
            
        st.markdown("### 🧠 Rotations-Auswertung")
        top_sector = df_sectors.iloc[0]["Sektor"]
        bottom_sector = df_sectors.iloc[-1]["Sektor"]
        
        if "Technologie" in top_sector and ("Basis-Konsumgüter" in bottom_sector or "Versorger" in bottom_sector):
            st.info(f"**Smart-Money-Fluss:** Großinvestoren schichten Geld in Wachstum (**{top_sector}**). Absolut gesundes Marktumfeld.")
        elif ("Versorger" in top_sector or "Basis-Konsumgüter" in top_sector) and "Technologie" in bottom_sector:
            st.warning(f"**Smart-Money-Fluss:** Institutionelle fliehen aus Wachstum und verstecken sich im defensiven Sektor (**{top_sector}**). Große Vorsicht geboten!")
        else:
            st.info(f"Aktuell führt der Sektor **{top_sector}** den Markt an, während **{bottom_sector}** relative Schwäche zeigt. Achte auf Fortsetzung dieser Bewegung.")
