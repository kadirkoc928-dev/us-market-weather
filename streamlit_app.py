import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="US Market Weather Report", page_icon="🌤️", layout="wide")

st.title("🌤️ US-Börsen-Wetterbericht & Markt-Sentiment")
st.markdown("Dieses Tool berechnet das globale Sentiment der wichtigsten Indizes über **RSI, MACD sowie die EMAs (10, 20, 50, 100, 200)** und analysiert Sektoren-Rotationen.")

# --- INDIZES DEFINIEREN ---
INDIZES = {
    "S&P 500 ETF (SPY)": "SPY",
    "Nasdaq 100 ETF (QQQ)": "QQQ",
    "Russell 2000 (Small Caps)": "^RUT",
    "Dow Jones Industrial": "^DJI",
    "Dax (Deutschland)": "^GDAXI",
    "Nikkei 225 (Japan)": "^N225"
}

# --- US-SEKTOREN DEFINIEREN (SPDR ETFs) ---
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

# --- BERECHNUNGS-FUNKTION FÜR SETIMENT ---
def analyze_sentiment(ticker):
    try:
        stock = yf.Ticker(ticker)
        # Wir brauchen 1 Jahr Daten, um den EMA 200 sauber zu berechnen
        hist = stock.history(period="1y")
        if hist.empty or len(hist) < 200:
            return None
        
        close = hist['Close']
        last_close = close.iloc[-1]
        prev_close = close.iloc[-2]
        perf_24h = ((last_close - prev_close) / prev_close) * 100
        
        # EMAs berechnen
        emas = {10: 10, 20: 20, 50: 50, 100: 100, 200: 200}
        ema_values = {}
        ema_score = 0
        
        for p in emas:
            ema_values[p] = close.ewm(span=p, adjust=False).mean().iloc[-1]
            if last_close > ema_values[p]:
                ema_score += (50 / 5) # Jeder EMA über dem Kurs gibt Punkte (Max 50 Punkte)
                
        # RSI berechnen
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        
        rsi_score = 0
        if 45 <= rsi <= 65: rsi_score = 25  # Stabiler Aufwärtstrend
        elif 30 <= rsi < 45: rsi_score = 15 # Leicht überverkauft / Bodenbildung
        elif 65 < rsi <= 75: rsi_score = 10 # Heiß gelaufen, aber stark
        
        # MACD berechnen
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        
        macd_score = 25 if macd.iloc[-1] > signal.iloc[-1] else 0 # Bullisch gegen Bärisch (Max 25 Punkte)
        
        # Gesamtscore (Max 100)
        total_score = int(ema_score + rsi_score + macd_score)
        
        return {
            "Kurs": round(last_close, 2),
            "Perf 24h": perf_24h,
            "RSI": round(rsi, 1),
            "Score": total_score
        }
    except:
        return None

# --- ENGINE STARTEN ---
if st.button("📊 Globalen Markt-Wetterbericht erstellen"):
    with st.spinner("Sammle Daten von den globalen Börsenplätzen..."):
        
        # 1. Indizes scannen
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
                    
        # Durchschnittlicher US Markt-Wetter-Score
        market_score = total_us_score // us_count if us_count > 0 else 50
        
        # 2. Sektoren scannen
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

        # --- WETTERBERICHT LOGIK ---
        st.subheader("🇺🇸 Das aktuelle US-Börsenwetter")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if market_score >= 75:
                st.markdown("# ☀️ STRAHLENDER SONNENSCHEIN")
                st.success(f"**Markt-Sentiment-Score: {market_score}%** \n\nDer Bulle rennt! Alle wichtigen EMAs (inklusive des langfristigen EMA 200) halten wie Beton. Die Indikatoren stehen auf vollen Kaufdruck.")
            elif 55 <= market_score < 75:
                st.markdown("# 🌤️ LEICHT BEWÖLKT")
                st.info(f"**Markt-Sentiment-Score: {market_score}%** \n\nSolides Handelsumfeld. Es gibt vereinzelte Gewinnmitnahmen, aber der übergeordnete Trend ist stabil. Rücksetzer an die EMAs (10/20) bieten oft gute Einstiege.")
            elif 40 <= market_score < 55:
                st.markdown("# 🌧️ REGENWETTER / SEITWÄRTS")
                st.warning(f"**Markt-Sentiment-Score: {market_score}%** \n\nDer Markt verliert an Schwung oder korrigiert. Der Kurs kämpft mit dem EMA 20 und 50. Hier ist erhöhte Cash-Quote oder defensives Trading angesagt.")
            else:
                st.markdown("# ⛈️ SCHWERES UNWETTER / CRASH-GEFAHR")
                st.error(f"**Markt-Sentiment-Score: {market_score}%** \n\nFinger weg vom Kaufen! Die Kurse sind unter den EMA 100 und EMA 200 gerauscht. Der MACD zeigt schweren Verkaufsdruck. Absicherung hat oberste Priorität.")

        with col2:
            st.markdown("### 🏹 Investitions-Empfehlung für heute:")
            if market_score >= 75:
                st.markdown("> **GRÜNES LICHT:** Heute ist ein statistisch **sehr guter Tag**, um frisches Kapital in Trendfolge- und Swing-Trading-Setups fließen zu lassen. Die Dynamik fängt dich auf.")
            elif 55 <= market_score < 75:
                st.markdown("> **PRODUKTIVER HANDELSTAG:** Gut zum Investieren, allerdings ohne Gier. Fokussiere dich auf starke Einzelwerte, die relative Stärke zum Gesamtmarkt zeigen.")
            elif 40 <= market_score < 55:
                st.markdown("> **ZURÜCKHALTUNG:** Kein idealer Tag für Neuinvestitionen. Sinnvoller ist es, bestehende Stopps nachzuziehen und auf klare charttechnische Bodenbildungen zu warten.")
            else:
                st.markdown("> **ROTES LICHT:** Extrem schlechter Tag für Käufe. Das Risiko für plötzliche Abverkaufswellen ist hoch. Besser an der Seitenlinie stehen und Cash halten.")

        st.markdown("---")
        
        # --- INDIZES REPROT ---
        st.subheader("🌐 Globales Index-Dashboard (Technischer Zustand)")
        
        idx_rows = []
        for name, data in index_data.items():
            # Kurzer Text-Zustand je nach Score
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

        # --- SEKTOREN ROTATION ---
        st.subheader("🔄 US-Sektoren-Analyse & Rotations-Radar")
        
        col_sec1, col_sec2 = st.columns(2)
        
        with col_sec1:
            st.markdown("### 📈 Gewinner-Sektoren (Hier fließt das Geld rein)")
            st.dataframe(df_sectors.head(4).style.format({"Tagesperformance": "{:,.2f}%"}), use_container_width=True)
            
        with col_sec2:
            st.markdown("### 📉 Verlierer-Sektoren (Hier ziehen sich Investoren zurück)")
            st.dataframe(df_sectors.tail(4).style.format({"Tagesperformance": "{:,.2f}%"}), use_container_width=True)
            
        # Automatische Erkennung einer Sektoren-Rotation
        st.markdown("### 🧠 Rotations-Auswertung")
        top_sector = df_sectors.iloc[0]["Sektor"]
        bottom_sector = df_sectors.iloc[-1]["Sektor"]
        
        if "Technologie" in top_sector and ("Basis-Konsumgüter" in bottom_sector or "Versorger" in bottom_sector):
            st.info(f"**Beobachtung:** Geld rotiert heute aktiv in **Risk-On (Wachstum)**. Technologie führt an, während defensive Sektoren gemieden werden. Das deutet auf gesundes, bullisches Marktvertrauen hin.")
        elif ("Versorger" in top_sector or "Basis-Konsumgüter" in top_sector) and "Technologie" in bottom_sector:
            st.warning(f"**Beobachtung:** Achtung! Es findet eine Rotation in **Risk-Off (Defensiv)** statt. Investoren flüchten aus Tech in sichere Häfen wie Versorger. Das deutet auf Angst vor einer Korrektur hin.")
        else:
            st.lightbulb(f"Aktuell führt der Sektor **{top_sector}** den Markt an, während **{bottom_sector}** relative Schwäche zeigt. Achte darauf, ob diese Dynamik über die nächsten Tage anhält!")
