import streamlit as st
import sqlite3
from datetime import datetime, timedelta, time

st.set_page_config(page_title="Tilmeldingssystem", page_icon="📅", layout="centered")

DB_NAME = "tilmeldinger.db"


# --- DATABASE SETUP ---
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS indstillinger (
            nogle TEXT PRIMARY KEY,
            vaerdi TEXT
        )
    ''')

    standard_indstillinger = [
        ('vis_antal_uger', '2'),
        ('laese_ugedag', '4'),  # 0=Mandag, 4=Fredag
        ('laese_klokkeslaet', '12:00'),
        ('laese_uger_forvejen', '0')  # 0 = ugen lige op til
    ]
    for nøgle, værdi in standard_indstillinger:
        c.execute('INSERT OR IGNORE INTO indstillinger (nogle, vaerdi) VALUES (?, ?)', (nøgle, værdi))

    conn.commit()
    conn.close()


init_db()


# --- DATABASE HJÆLPEFUNKTIONER ---
def hent_indstillinger():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT nogle, vaerdi FROM indstillinger')
    rows = c.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def gem_indstilling(nøgle, værdi):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO indstillinger (nogle, vaerdi) VALUES (?, ?)', (nøgle, str(værdi)))
    conn.commit()
    conn.close()


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


def er_uge_laest(start_dato_uge, indstillinger):
    nu = datetime.now()
    laese_ugedag = int(indstillinger.get('laese_ugedag', 4))
    laese_uger_forvejen = int(indstillinger.get('laese_uger_forvejen', 0))
    tid_str = indstillinger.get('laese_klokkeslaet', '12:00')
    timer, minutter = map(int, tid_str.split(':'))

    mandag_i_tilmeldingsuge = start_dato_uge
    mandag_i_laeseuge = mandag_i_tilmeldingsuge - timedelta(weeks=1 + laese_uger_forvejen)

    laese_deadline = datetime.combine(
        mandag_i_laeseuge + timedelta(days=laese_ugedag),
        time(timer, minutter)
    )

    return nu >= laese_deadline, laese_deadline


# --- LOGIN LOGIK ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_email" not in st.session_state:
    st.session_state["user_email"] = ""

if not st.session_state["logged_in"]:
    st.title("🔒 Log ind i Tilmeldingssystem")
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
    st.stop()

# --- HOVEDMENU OG SIDEBAR ---
st.sidebar.write(f"Logget ind som:\n**{st.session_state['user_email']}**")
if st.sidebar.button("Log ud", use_container_width=True):
    st.session_state["logged_in"] = False
    st.session_state["user_email"] = ""
    st.rerun()