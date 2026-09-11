import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Admin - Tilmeldingsoversigt",
    page_icon="📊",
    layout="wide"
)

DB_NAME = "tilmeldinger.db"


# --- DATABASE FUNKTIONER ---

def hent_ugens_oversigt(uge_nr, aar):
    """Henter alle registrerede dags-tilmeldinger for en specifik uge og år."""
    conn = sqlite3.connect(DB_NAME)

    # Hent registreringer for de enkelte dage
    query_dage = '''
        SELECT 
            d.dato,
            t.bruger_id,
            d.status,
            t.antal_gaester
        FROM dags_tilstedevaerelse d
        JOIN tilmeldinger t ON d.tilmelding_id = t.id
        WHERE t.uge_nr = ? AND t.aar = ?
        ORDER BY d.dato ASC
    '''
    df_dage = pd.read_sql_query(query_dage, conn, params=(uge_nr, aar))

    # Hent brugere der har valgt "Nej" til hele ugen
    query_nej = '''
        SELECT bruger_id, oprettet_dato 
        FROM tilmeldinger 
        WHERE uge_nr = ? AND aar = ? AND er_til_stede = 'Nej'
    '''
    df_nej = pd.read_sql_query(query_nej, conn, params=(uge_nr, aar))

    conn.close()
    return df_dage, df_nej


# --- ADMIN UI ---

st.title("📊 Admin - Tilmeldingsoversigt")

# Beregn datoer for næste 2 uger
idag = datetime.now().date()
start_denne_uge = idag - timedelta(days=idag.weekday())

start_uge_1 = start_denne_uge + timedelta(weeks=1)
start_uge_2 = start_denne_uge + timedelta(weeks=2)

uge_1_info = start_uge_1.isocalendar()
uge_2_info = start_uge_2.isocalendar()

# Vælg hvilken uge du vil se overblik for
valgt_uge = st.sidebar.radio(
    "Vælg uge:",
    options=[
        f"Uge {uge_1_info[1]} (Næste uge)",
        f"Uge {uge_2_info[1]} (Om 2 uger)"
    ]
)

if "Næste uge" in valgt_uge:
    aktiv_uge_nr = uge_1_info[1]
    aktiv_aar = uge_1_info[0]
    start_dato = start_uge_1
else:
    aktiv_uge_nr = uge_2_info[1]
    aktiv_aar = uge_2_info[0]
    start_dato = start_uge_2

st.header(f"Oversigt for Uge {aktiv_uge_nr} ({aktiv_aar})")

# Hent data fra databasen
df_tilmeldinger, df_fraværende_hele_ugen = hent_ugens_oversigt(aktiv_uge_nr, aktiv_aar)

if df_tilmeldinger.empty and df_fraværende_hele_ugen.empty:
    st.info(f"Der er endnu ingen tilmeldinger registreret i databasen for uge {aktiv_uge_nr}.")
else:
    danske_navne = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag"]

    # --- 1. SAMLET ANTAL TÆLLER (METRIKKER) ---
    st.subheader("📈 Samlet antal tilstede pr. dag")
    cols = st.columns(5)

    for i in range(5):
        dag_dato = (start_dato + timedelta(days=i)).strftime("%Y-%m-%d")
        dag_str = (start_dato + timedelta(days=i)).strftime("%d/%m")
        dag_navn = danske_navne[i]

        dag_df = df_tilmeldinger[df_tilmeldinger['dato'] == dag_dato]

        tilstede_antal = len(dag_df[dag_df['status'] == 'Til stede'])
        gaester_antal = dag_df[dag_df['status'] == 'Til stede']['antal_gaester'].sum() if not dag_df.empty else 0
        totalt_antal = tilstede_antal + gaester_antal

        with cols[i]:
            st.metric(
                label=f"{dag_navn} ({dag_str})",
                value=f"{totalt_antal} pers.",
                delta=f"{tilstede_antal} ansatte + {gaester_antal} gæster" if gaester_antal > 0 else None
            )

    st.divider()

    # --- 2. DETALJERET NAVNELISTE PR. DAG ---
    st.subheader("🔍 Hvem kommer hvornår?")

    for i in range(5):
        dag_dato = (start_dato + timedelta(days=i)).strftime("%Y-%m-%d")
        dag_str = (start_dato + timedelta(days=i)).strftime("%d/%m")
        dag_navn = danske_navne[i]

        dag_df = df_tilmeldinger[df_tilmeldinger['dato'] == dag_dato]
        medarbejdere_tilstede = dag_df[dag_df['status'] == 'Til stede']
        medarbejdere_afbud = dag_df[dag_df['status'] == 'Ikke til stede']

        totalt_dag = len(medarbejdere_tilstede) + (
            medarbejdere_tilstede['antal_gaester'].sum() if not medarbejdere_tilstede.empty else 0)

        with st.expander(f"**{dag_navn} ({dag_str})** — {totalt_dag} person(er) i alt"):
            col_a, col_b = st.columns(2)

            with col_a:
                st.write("✅ **Tilmeldt:**")
                if not medarbejdere_tilstede.empty:
                    for _, row in medarbejdere_tilstede.iterrows():
                        gaeste_tekst = f" *(+ {row['antal_gaester']} gæst(er))*" if row['antal_gaester'] > 0 else ""
                        st.write(f"- {row['bruger_id']}{gaeste_tekst}")
                else:
                    st.write("*Ingen tilmeldt.*")

            with col_b:
                st.write("❌ **Meldt fraværende denne dag:**")
                if not medarbejdere_afbud.empty:
                    for _, row in medarbejdere_afbud.iterrows():
                        st.write(f"- {row['bruger_id']}")
                else:
                    st.write("*Ingen afbud registreret.*")

    # --- 3. HELT FRAVÆRENDE HELE UGEN ---
    if not df_fraværende_hele_ugen.empty:
        st.divider()
        st.subheader("🚫 Meldt helt fraværende hele ugen")
        for _, row in df_fraværende_hele_ugen.iterrows():
            st.write(f"- {row['bruger_id']}")