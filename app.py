import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="Prop Firm Monte Carlo Simulator", layout="wide")

st.title("📊 Prop Firm Challenge Simulator")
st.markdown("Analisi quantitativa e simulazione Monte Carlo basata su trade reali.")

# -----------------------------------------------------------------------------
# FASE 1 & 2: PARSING E RICOSTRUZIONE TRADE (CSV, TXT, XLSX)
# -----------------------------------------------------------------------------
def load_and_parse_file(uploaded_file):
    filename = uploaded_file.name.lower()
    
    # Se il file è un foglio Excel (.xlsx o .xls)
    if filename.endswith('.xlsx') or filename.endswith('.xls'):
        try:
            df = pd.read_excel(uploaded_file, sheet_name=0)
            return df
        except Exception as e:
            st.error(f"Errore nella lettura del file Excel: {e}")
            return None
            
    # Altrimenti gestione CSV / TXT / TSV
    bytes_data = uploaded_file.read()
    for encoding in ['utf-8', 'latin1', 'utf-16']:
        try:
            text = bytes_data.decode(encoding)
            sample = text[:2000]
            if ';' in sample:
                sep = ';'
            elif '\t' in sample:
                sep = '\t'
            else:
                sep = ','
            df = pd.read_csv(io.StringIO(text), sep=sep)
            if len(df.columns) > 1:
                return df
        except Exception:
            continue
    return None

def standardize_columns(df):
    cols = {col: str(col).lower().strip() for col in df.columns}
    
    # Priorità a 'net' o 'profit/loss'
    pnl_col = next((c for c, l in cols.items() if l == 'net'), None)
    if not pnl_col:
        pnl_col = next((c for c, l in cols.items() if any(k in l for k in ['profit', 'pnl', 'p/l', 'risultato', 'gain', 'gross'])), None)
        
    date_col = next((c for c, l in cols.items() if any(k in l for k in ['chiusura', 'close', 'date', 'time', 'data', 'timestamp'])), None)
    symbol_col = next((c for c, l in cols.items() if any(k in l for k in ['simbolo', 'symbol', 'instrument', 'strumento', 'pair'])), None)
    account_col = next((c for c, l in cols.items() if any(k in l for k in ['account', 'login', 'conto'])), None)
    comm_col = next((c for c, l in cols.items() if any(k in l for k in ['commission', 'comm', 'fee', 'commissioni'])), None)
    
    return pnl_col, date_col, symbol_col, account_col, comm_col

# -----------------------------------------------------------------------------
# SIDEBAR: PARAMETRI PROP FIRM
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ Regole Prop Firm")

preset = st.sidebar.selectbox("Carica Preset Prop Firm:", [
    "Personalizzato",
    "FTMO 100k Standard",
    "Funding Pips 100k",
    "Apex 50k Trailing"
])

if preset == "FTMO 100k Standard":
    init_cap = 100000.0
    target_prof = 10000.0
    max_total_loss = 10000.0
    drawdown_type = "Estatico"
    max_daily_loss = 5000.0
    min_days = 4
    consistency_rule = 0.0
    time_limit = 0
    cost_per_acc = 540.0
elif preset == "Funding Pips 100k":
    init_cap = 100000.0
    target_prof = 8000.0
    max_total_loss = 6000.0
    drawdown_type = "Trailing Fine Giornata (EOD)"
    max_daily_loss = 3000.0
    min_days = 0
    consistency_rule = 0.0
    time_limit = 0
    cost_per_acc = 399.0
elif preset == "Apex 50k Trailing":
    init_cap = 50000.0
    target_prof = 3000.0
    max_total_loss = 2500.0
    drawdown_type = "Trailing Intraday"
    max_daily_loss = 0.0
    min_days = 7
    consistency_rule = 0.30
    time_limit = 0
    cost_per_acc = 150.0
else:
    init_cap = st.sidebar.number_input("Capitale Iniziale ($)", value=50000.0, step=1000.0)
    target_prof = st.sidebar.number_input("Target di Profitto ($)", value=5000.0, step=500.0)
    max_total_loss = st.sidebar.number_input("Perdita Max Totale (Drawdown) ($)", value=2500.0, step=500.0)
    drawdown_type = st.sidebar.selectbox("Tipo Drawdown:", [
        "Estatico",
        "Trailing Intraday",
        "Trailing Fine Giornata (EOD)",
        "Trailing bloccato a Capitale Iniziale"
    ])
    max_daily_loss = st.sidebar.number_input("Perdita Max Giornaliera ($ - 0 se assente)", value=1000.0, step=250.0)
    min_days = st.sidebar.number_input("Giorni Minimi di Trading", value=0, step=1)
    consistency_rule = st.sidebar.slider("Consistency Rule (Max % profitto in 1 giorno, 0 = disattiva)", 0.0, 0.8, 0.0, 0.05)
    time_limit = st.sidebar.number_input("Limite di Giorni Solari (0 se illimitato)", value=0, step=5)
    cost_per_acc = st.sidebar.number_input("Costo Singolo Account ($)", value=150.0, step=10.0)

num_simulations = 10000
seed = 42

# -----------------------------------------------------------------------------
# FASE 1 & 3: CARICAMENTO FILE E DISPLAY STATISTICHE
# -----------------------------------------------------------------------------
uploaded_file = st.file_uploader("Carica l'export grezzo dei tuoi trade (CSV, TXT, XLSX, XLS)", type=["csv", "txt", "tsv", "xlsx", "xls"])

if uploaded_file is not None:
    df = load_and_parse_file(uploaded_file)
    if df is None:
        st.error("Impossibile leggere il file. Verifica il formato.")
        st.stop()
        
    pnl_col, date_col, symbol_col, account_col, comm_col = standardize_columns(df)
    
    st.subheader("📋 FASE 1 & 3 — Analisi Struttura File")
    
    col_a, col_b = st.columns(2)
    with col_a:
        pnl_col = st.selectbox("Seleziona Colonna Profit/Loss (PnL):", df.columns, index=list(df.columns).index(pnl_col) if pnl_col in df.columns else 0)
        date_col = st.selectbox("Seleziona Colonna Data/Ora:", df.columns, index=list(df.columns).index(date_col) if date_col in df.columns else 0)
    with col_b:
        comm_included = st.radio("Le commissioni sono già incluse nel PnL?", ["Sì", "No (Applica valore sotto)"])
        comm_value = 0.0
        if comm_included == "No (Applica valore sotto)":
            comm_value = st.number_input("Commissione fissa per trade ($):", value=2.0)

    # Pulizia dati PnL e Data
    try:
        df['PnL_Clean'] = pd.to_numeric(df[pnl_col].astype(str).str.replace(',', '.').str.extract(r'([-+]?\d*\.?\d+)')[0], errors='coerce')
        if comm_included != "Sì":
            df['PnL_Clean'] -= comm_value
        df['Date_Clean'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['PnL_Clean', 'Date_Clean']).sort_values('Date_Clean')
    except Exception as e:
        st.error(f"Errore nella conversione dei dati: {e}")
        st.stop()
        
    df['Trading_Day'] = df['Date_Clean'].dt.date
    trades = df['PnL_Clean'].values
    
    daily_trades = df.groupby('Trading_Day')['PnL_Clean'].apply(list).to_dict()
    unique_days = list(daily_trades.keys())
    trades_per_day_counts = [len(v) for v in daily_trades.values()]
    
    total_trades = len(trades)
    num_days = len(unique_days)
    win_rate = (trades > 0).mean() * 100
    avg_win = trades[trades > 0].mean() if any(trades > 0) else 0.0
    avg_loss = abs(trades[trades < 0].mean()) if any(trades < 0) else 0.0
    rr_ratio = avg_win / avg_loss if avg_loss != 0 else np.nan
    net_pnl = trades.sum()
    
    st.markdown("### 📊 Summary dello Storico")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Trade Totali", f"{total_trades}")
    c2.metric("Giorni Distinti", f"{num_days}")
    c3.metric("Win Rate", f"{win_rate:.1f}%")
    c4.metric("Rapporto R/R Reale", f"{rr_ratio:.2f}")
    c5.metric("Net PnL Totale", f"${net_pnl:,.2f}")
    
    if total_trades < 30:
        st.error("⚠️ CRITICO: Hai meno di 30 trade nello storico. Il calcolo NON è affidabile.")
    elif total_trades < 100:
        st.warning("⚠️ ATTENZIONE: Meno di 100 trade nello storico. Il risultato ha un margine di incertezza elevato.")
        
    if num_days < 5:
        st.warning(f"⚠️ ATTENZIONE: I trade sono concentrati in soli {num_days} giorni.")

    # -----------------------------------------------------------------------------
    # FASE 5: SIMULAZIONE MONTE CARLO
    # -----------------------------------------------------------------------------
    if st.button("🚀 Avvia Simulazione Monte Carlo (10.000 Challenge)", type="primary"):
        np.random.seed(seed)
        
        passed = 0
        fail_drawdown = 0
        fail_daily = 0
        fail_time = 0
        days_to_pass = []
        
        for _ in range(num_simulations):
            balance = init_cap
            peak_balance = init_cap
            
            if drawdown_type == "Estatico":
                floor = init_cap - max_total_loss
            else:
                floor = init_cap - max_total_loss
                
            day_count = 0
            is_failed = False
            is_passed = False
            
            daily_profits = []
            
            while not is_failed and not is_passed:
                day_count += 1
                
                if time_limit > 0 and day_count > time_limit:
                    fail_time += 1
                    is_failed = True
                    break
                
                num_t_today = np.random.choice(trades_per_day_counts)
                day_pnl = 0.0
                
                for _ in range(num_t_today):
                    t_res = np.random.choice(trades)
                    balance += t_res
                    day_pnl += t_res
                    
                    if drawdown_type == "Trailing Intraday":
                        if balance > peak_balance:
                            peak_balance = balance
                            new_floor = peak_balance - max_total_loss
                            if drawdown_type == "Trailing bloccato a Capitale Iniziale":
                                floor = min(init_cap, new_floor)
                            else:
                                floor = new_floor
                    
                    if balance <= floor:
                        fail_drawdown += 1
                        is_failed = True
                        break
                        
                    if max_daily_loss > 0 and day_pnl <= -max_daily_loss:
                        fail_daily += 1
                        is_failed = True
                        break
                
                if is_failed:
                    break
                    
                if drawdown_type in ["Trailing Fine Giornata (EOD)", "Estatico"]:
                    if balance > peak_balance:
                        peak_balance = balance
                        if drawdown_type == "Trailing Fine Giornata (EOD)":
                            floor = peak_balance - max_total_loss
                
                daily_profits.append(day_pnl)
                
                total_profit = balance - init_cap
                if total_profit >= target_prof:
                    if day_count < min_days:
                        continue
                        
                    if consistency_rule > 0:
                        max_single_day_pnl = max(daily_profits)
                        if max_single_day_pnl / total_profit > consistency_rule:
                            continue
                            
                    is_passed = True
                    passed += 1
                    days_to_pass.append(day_count)
                    
        # -----------------------------------------------------------------------------
        # FASE 6: RISULTATI
        # -----------------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📈 FASE 6 — Esito della Simulazione Monte Carlo")
        
        pass_rate = (passed / num_simulations) * 100
        fail_rate = 100 - pass_rate
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Probabilità di Passare", f"{pass_rate:.2f}%")
        m2.metric("Tasso di Fallimento", f"{fail_rate:.2f}%")
        m3.metric("Seed Utilizzato", f"{seed}")
        
        st.markdown("#### ❌ Cause di Fallimento")
        f1, f2, f3 = st.columns(3)
        f1.metric("Muro Drawdown Massimo Toccatto", f"{(fail_drawdown/num_simulations)*100:.1f}%")
        f2.metric("Limite Perdita Giornaliera Toccatto", f"{(fail_daily/num_simulations)*100:.1f}%")
        f3.metric("Tempo Scaduto", f"{(fail_time/num_simulations)*100:.1f}%")
        
        if days_to_pass:
            st.markdown("#### ⏱️ Giorni di Trading Necessari (Quando Passi)")
            d1, d2, d3 = st.columns(3)
            d1.metric("Caso Più Veloce", f"{int(np.min(days_to_pass))} giorni")
            d2.metric("Mediana", f"{int(np.median(days_to_pass))} giorni")
            d3.metric("90° Percentile", f"{int(np.percentile(days_to_pass, 90))} giorni")
            
        st.markdown("#### 💰 Analisi Multi-Account (Probabilità Cumulata di Passarne ALMENO Uno)")
        
        multi_data = []
        passed_prob_dec = pass_rate / 100.0
        row_highlight = None
        
        for k in range(1, 6):
            prob_at_least_one = (1 - (1 - passed_prob_dec)**k) * 100
            total_cost = k * cost_per_acc
            
            note = ""
            if prob_at_least_one >= 90.0 and row_highlight is None:
                row_highlight = k
                note = "🎯 Soglia >90% Raggiunta"
                
            multi_data.append({
                "Numero Account": k,
                "Probabilità ALMENO 1 Vinto": f"{prob_at_least_one:.2f}%",
                "Costo Totale ($)": f"${total_cost:,.2f}",
                "Note": note
            })
            
        st.table(pd.DataFrame(multi_data))
        
        risk_of_ruin = (1 - passed_prob_dec)**5 * 100
        st.write(f"**Rischio di Rovina (spendere tutti i 5 account senza passarne nessuno):** `{risk_of_ruin:.2f}%`")
        
        st.markdown("""
        #### ⚠️ Limiti del Calcolo
        1. **Resampling Indipendente:** Il campionamento casuale rompe le sequenze temporali. Nella realtà le strisce negative tendono a raggrupparsi (cluster di perdita), quindi la probabilità reale potrebbe essere leggermente inferiore.
        2. **Costanza della Strategia:** Il modello presuppone che continuerai a fare trading con la stessa size, frequenza e gestione del rischio usate nello storico.
        """)
        
        st.markdown("---")
        st.markdown("### 🎯 Verdetto Finale")
        if pass_rate > 70:
            st.success(f"**Consiglio:** Con una probabilità del {pass_rate:.1f}%, ti conviene acquistare **1 solo account** (o al massimo 2 per sicurezza).")
        elif pass_rate > 40:
            rec_acc = row_highlight if row_highlight else 3
            st.warning(f"**Consiglio:** La probabilità su singolo account è del {pass_rate:.1f}%. Ti conviene acquistare **{rec_acc} account** per superare il 90% di probabilità cumulata.")
        else:
            st.error(f"**Consiglio:** **NON COMPRARE ACCOUNT AL MOMENTO.** La probabilità di successo per tentato account è solo del {pass_rate:.1f}%. Rischio di rovina elevato.")