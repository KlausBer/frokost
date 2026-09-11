import streamlit as st
import sqlite3
from datetime import datetime, timedelta

st.set_page_config(page_title="Tilmeldingssystem", page_icon="📅", layout="centered")

# --- DATABASE SETUP ---
DB_NAME = "tilmeldinger.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tilmeldinger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bruger_id TEXT,
            uge_nr INTEGER,
            aar INTEGER,
            er_til_stede TEXT,
            antal_gaester INTEGER,
            oprettet_dato DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(bruger_id, uge_nr, aar)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS dags_tilstedevaerelse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tilmelding_id INTEGER,
            dato DATE,
            status TEXT,
            FOREIGN KEY (tilmelding_id) REFERENCES tilmeldinger (id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()


init_db()


# --- HJÆLPEFUNKTIONER TIL DATABASE ---

def hent_eksisterende_tilmelding(bruger_id, uge_nr, aar):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT id, er_til_stede, antal_gaester 
        FROM tilmeldinger 
        WHERE bruger_id = ? AND uge_nr = ? AND aar = ?
    ''', (bruger_id, uge_nr, aar))
    hoved = c.fetchone()

    if not hoved:
        conn.close()
        return None

    tilmelding_id, er_til_stede, antal_gaester = hoved

    c.execute('''
        SELECT dato, status 
        FROM dags_tilstedevaerelse 
        WHERE tilmelding_id = ?
    ''', (tilmelding_id,))
    dags_rows = c.fetchall()
    conn.close()

    dags_status = {row[0]: row[1] for row in dags_rows}
    return {
        "er_til_stede": er_til_stede,
        "antal_gaester": antal_gaester,
        "dags_status": dags_status
    }


def gem_tilmelding_i_db(bruger_id, uge_nr, aar, er_her, gaester, dags_status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO tilmeldinger (bruger_id, uge_nr, aar, er_til_stede, antal_gaester)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(bruger_id, uge_nr, aar) DO UPDATE SET
                er_til_stede = excluded.er_til_stede,
                antal_gaester = excluded.antal_gaester,
                oprettet_dato = CURRENT_TIMESTAMP
        ''', (bruger_id, uge_nr, aar, er_her, gaester))

        c.execute('SELECT id FROM tilmeldinger WHERE bruger_id = ? AND uge_nr = ? AND aar = ?',
                  (bruger_id, uge_nr, aar))
        tilmelding_id = c.fetchone()[0]

        c.execute('DELETE FROM dags_tilstedevaerelse WHERE tilmelding_id = ?', (tilmelding_id,))

        if er_her == "Ja":
            for dato, status in dags_status.items():
                c.execute('''
                    INSERT INTO dags_tilstedevaerelse (tilmelding_id, dato, status)
                    VALUES (?, ?, ?)
                ''', (tilmelding_id, dato, status))

        conn.commit()
        return True
    except Exception as e:
        st.error(f"Fejl ved gemning i database: {e}")
        return False
    finally:
        conn.close()


# --- SESSION STATE FOR LOGIN ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_email" not in st.session_state:
    st.session_state["user_email"] = ""

# --- 1. LOGIN SKÆRM (VISES HVIS MAN IKKE ER LOGGET IND) ---
if not st.session_state["logged_in"]:
    st.title("🔒 Log ind i Tilmeldingssystem")
    st.write("Indtast din e-mail for at logge ind og se eller ændre dine tilmeldinger.")

    with st.form("login_form"):
        input_email = st.text_input("E-mailadresse:")
        submit_login = st.form_submit_button("Log ind", use_container_width=True)

        if submit_login:
            if input_email and "@" in input_email:
                st.session_state["logged_in"] = True
                st.session_state["user_email"] = input_email.strip().lower()
                st.rerun()
            else:
                st.error("Indtast venligst en gyldig e-mail.")

    # Stopper koden her, så resten af appen ikke vises før man er logget ind
    st.stop()

# --- 2. HOVEDAPP (VISES KUN NÅR MAN ER LOGGET IND) ---

# Toplinje med brugerinfo og log ud-knap
col1, col2 = st.columns([3, 1])
with col1:
    st.write(f"Logget ind som: **{st.session_state['user_email']}**")
with col2:
    if st.button("Log ud", use_container_width=True):
        st.session_state["logged_in"] = False
        st.session_state["user_email"] = ""
        st.rerun()

st.divider()
st.title("📅 Tilmeldingssystem")

bruger_email = st.session_state["user_email"]


def get_working_days_for_week(start_of_week):
    dage = []
    danske_navne = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag"]
    for i in range(5):
        dato = start_of_week + timedelta(days=i)
        dage.append({
            "navn": danske_navne[i],
            "dato_str": dato.strftime("%d/%m"),
            "iso_dato": dato.strftime("%Y-%m-%d")
        })
    return dage


# Beregn datoer for næste 2 uger
idag = datetime.now().date()
start_denne_uge = idag - timedelta(days=idag.weekday())

start_uge_1 = start_denne_uge + timedelta(weeks=1)
start_uge_2 = start_denne_uge + timedelta(weeks=2)

uge_1_info = start_uge_1.isocalendar()
uge_2_info = start_uge_2.isocalendar()

tab1, tab2 = st.tabs([f"Uge {uge_1_info[1]} (Næste uge)", f"Uge {uge_2_info[1]} (Om 2 uger)"])


def vis_ugentlig_formular(uge_nr, aar, start_dato):
    arbejdsdage = get_working_days_for_week(start_dato)

    # Hent gemte data fra databasen for denne bruger og uge
    gemt_data = hent_eksisterende_tilmelding(bruger_email, uge_nr, aar)

    default_er_her_idx = 0 if (not gemt_data or gemt_data["er_til_stede"] == "Ja") else 1
    default_gaester = gemt_data["antal_gaester"] if gemt_data else 0
    gemt_dags_status = gemt_data["dags_status"] if gemt_data else {}

    if gemt_data:
        st.info("ℹ️ Du har tidligere gemt en tilmelding for denne uge. Dine valg er indlæst nedenfor.")

    with st.form(key=f"form_uge_{uge_nr}"):
        st.subheader(f"Tilmelding for Uge {uge_nr}")

        er_her = st.radio(
            f"Er du til stede i uge {uge_nr}?",
            options=["Ja", "Nej"],
            index=default_er_her_idx,
            key=f"er_her_{uge_nr}"
        )

        dags_status = {}
        gaester = 0

        if er_her == "Ja":
            st.divider()
            st.write("### Angiv din tilstedeværelse:")

            for dag in arbejdsdage:
                label = f"{dag['navn']} ({dag['dato_str']})"
                tidligere_status = gemt_dags_status.get(dag['iso_dato'], "Til stede")
                default_dag_idx = 0 if tidligere_status == "Til stede" else 1

                dags_status[dag['iso_dato']] = st.radio(
                    f"{label}:",
                    options=["Til stede", "Ikke til stede"],
                    index=default_dag_idx,
                    horizontal=True,
                    key=f"status_{uge_nr}_{dag['iso_dato']}"
                )

            st.divider()
            gaester = st.number_input(
                "Hvor mange gæster har du i alt med i denne uge?",
                min_value=0,
                max_value=20,
                value=default_gaester,
                step=1,
                key=f"gaester_{uge_nr}"
            )

        submit = st.form_submit_button("Gem / Opdater tilmelding", use_container_width=True)

    if submit:
        succes = gem_tilmelding_i_db(
            bruger_id=bruger_email,
            uge_nr=uge_nr,
            aar=aar,
            er_her=er_her,
            gaester=gaester,
            dags_status=dags_status
        )
        if succes:
            st.success(f"Din tilmelding for uge {uge_nr} er gemt!")
            st.rerun()


with tab1:
    vis_ugentlig_formular(uge_1_info[1], uge_1_info[0], start_uge_1)

with tab2:
    vis_ugentlig_formular(uge_2_info[1], uge_2_info[0], start_uge_2)