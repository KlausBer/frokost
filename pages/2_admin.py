import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, time
from app import hent_indstillinger, gem_indstilling, DB_NAME

st.title("⚙️ Administration & Overblik")

if not st.session_state.get("logged_in", False):
    st.warning("Du skal logge ind først.")
    st.stop()

cfg = hent_indstillinger()


# Hjælpefunktion til at hente data for en bestemt uge
def hent_ugens_tilmeldinger(uge_nr, aar):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Hent alle hovedtilmeldinger for den valgte uge
    c.execute('''
        SELECT id, bruger_id, er_til_stede, antal_gaester, oprettet_dato
        FROM tilmeldinger
        WHERE uge_nr = ? AND aar = ?
    ''', (uge_nr, aar))
    tilmeldinger = c.fetchall()

    # Hent dagsspecifikke tilmeldinger
    c.execute('''
        SELECT t.bruger_id, d.dato, d.status
        FROM dags_tilstedevaerelse d
        JOIN tilmeldinger t ON d.tilmelding_id = t.id
        WHERE t.uge_nr = ? AND t.aar = ?
    ''', (uge_nr, aar))
    dags_data = c.fetchall()

    conn.close()
    return tilmeldinger, dags_data


tab_oversigt, tab_indstillinger = st.tabs(["📊 Tilmeldingsoversigt", "⚙️ Systemindstillinger"])

# ==========================================
# TAB 1: OVERSIGT OVER TILMELDTE
# ==========================================
with tab_oversigt:
    st.subheader("Oversigt over tilmeldinger per uge")

    # Vælg uge der skal vises
    idag = datetime.now().date()
    start_denne_uge = idag - timedelta(days=idag.weekday())

    vis_antal_uger = int(cfg.get('vis_antal_uger', 2))

    mulige_uger = []
    for i in range(1, vis_antal_uger + 1):
        s_dato = start_denne_uge + timedelta(weeks=i)
        info = s_dato.isocalendar()
        mulige_uger.append((f"Uge {info[1]} ({s_dato.strftime('%d/%m')})", info[1], info[0], s_dato))

    valgt_uge_tekst, valgt_uge_nr, valgt_aar, valgt_start_dato = st.selectbox(
        "Vælg uge for at se tilmeldinger:",
        options=mulige_uger,
        format_func=lambda x: x[0]
    )

    tilmeldinger, dags_data = hent_ugens_tilmeldinger(valgt_uge_nr, valgt_aar)

    if not tilmeldinger:
        st.info(f"Der er endnu ingen tilmeldinger registreret for uge {valgt_uge_nr}.")
    else:
        # 1. Total opgørelse per dag
        st.markdown("### 📈 Antal tilmeldte pr. dag")

        # Opret liste af hverdage for den valgte uge
        danske_navne = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag"]
        ugedage_datoer = [valgt_start_dato + timedelta(days=i) for i in range(5)]

        # Sammentæl pr dag
        dags_tælling = {d.strftime("%Y-%m-%d"): 0 for d in ugedage_datoer}
        for bruger, dato_str, status in dags_data:
            if status == "Til stede" and dato_str in dags_tælling:
                dags_tælling[dato_str] += 1

        # Sammentæl gæster totalt
        total_gaester = sum(t[3] for t in tilmeldinger if t[2] == "Ja")

        # Vis nøgletal som cards
        cols = st.columns(5)
        for i, d in enumerate(ugedage_datoer):
            dato_key = d.strftime("%Y-%m-%d")
            ant = dags_tælling.get(dato_key, 0)
            with cols[i]:
                st.metric(label=f"{danske_navne[i]} ({d.strftime('%d/%m')})", value=f"{ant} pers.")

        st.caption(f"💡 Antal gæster angivet i alt for denne uge: **{total_gaester} gæst(er)**")

        st.divider()
        st.markdown("### 👥 Hvem kommer hvornår?")

        # Byg en overskuelig tabel over brugere og deres status per dag
        rækker = []
        for t in tilmeldinger:
            b_id, er_her, gaester, oprettet = t[1], t[2], t[3], t[4]

            bruger_row = {"Bruger / E-mail": b_id, "Status": er_her, "Gæster": gaester}

            if er_her == "Ja":
                # Hent brugerens valg for hver dag
                for d in ugedage_datoer:
                    d_str = d.strftime("%Y-%m-%d")
                    st_val = "❌ Ikke til stede"
                    for b, dato_val, status_val in dags_data:
                        if b == b_id and dato_val == d_str and status_val == "Til stede":
                            st_val = "✅ Til stede"
                            break
                    bruger_row[f"{danske_navne[(d.weekday())]} ({d.strftime('%d/%m')})"] = st_val
            else:
                for d in ugedage_datoer:
                    bruger_row[f"{danske_navne[(d.weekday())]} ({d.strftime('%d/%m')})"] = "❌ Ikke til stede"

            rækker.append(bruger_row)

        df = pd.DataFrame(rækker)
        st.dataframe(df, use_container_width=True, hide_index=True)

# ==========================================
# TAB 2: SYSTEMINDSTILLINGER
# ==========================================
with tab_indstillinger:
    ugedage_navne = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]

    with st.form("admin_settings_form"):
        st.subheader("1. Visning af uger")
        vis_uger_input = st.number_input(
            "Hvor mange uger frem skal brugerne kunne se i tilmeldingen?",
            min_value=1,
            max_value=12,
            value=int(cfg.get('vis_antal_uger', 2)),
            step=1
        )

        st.divider()
        st.subheader("2. Regler for låsning af tilmelding")

        laese_ugedag_input = st.selectbox(
            "Hvilken ugedag skal tilmeldingen låse?",
            options=list(range(7)),
            format_func=lambda x: ugedage_navne[x],
            index=int(cfg.get('laese_ugedag', 4))
        )

        nuvaerende_tid = cfg.get('laese_klokkeslaet', '12:00')
        standard_tid = time(*map(int, nuvaerende_tid.split(':')))
        laese_tid_input = st.time_input(
            "Hvilket klokkeslæt skal tilmeldingen låse på dagen?",
            value=standard_tid
        )

        laese_uger_forvejen_input = st.number_input(
            "Hvor mange uger i forvejen skal den låses?",
            min_value=0,
            max_value=6,
            value=int(cfg.get('laese_uger_forvejen', 0)),
            help="0 = låser i ugen lige før den relevante tilmeldingsuge. 1 = låser 2 uger i forvejen osv."
        )

        submit_admin = st.form_submit_button("Gem indstillinger", use_container_width=True)

        if submit_admin:
            gem_indstilling('vis_antal_uger', vis_uger_input)
            gem_indstilling('laese_ugedag', laese_ugedag_input)
            gem_indstilling('laese_klokkeslaet', laese_tid_input.strftime("%H:%M"))
            gem_indstilling('laese_uger_forvejen', laese_uger_forvejen_input)
            st.success("Indstillingerne blev gemt!")
            st.rerun()