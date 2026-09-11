import streamlit as st
from datetime import datetime, timedelta
from app import (
    hent_indstillinger,
    hent_eksisterende_tilmelding,
    gem_tilmelding_i_db,
    er_uge_laest
)

st.title("📅 Tilmeldingssystem")

if not st.session_state.get("logged_in", False):
    st.warning("Du skal logge ind først.")
    st.stop()

bruger_email = st.session_state["user_email"]
cfg = hent_indstillinger()

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

idag = datetime.now().date()
start_denne_uge = idag - timedelta(days=idag.weekday())
vis_antal_uger = int(cfg.get('vis_antal_uger', 2))

ugelige_data = []
tab_titler = []

for i in range(1, vis_antal_uger + 1):
    start_dato = start_denne_uge + timedelta(weeks=i)
    info = start_dato.isocalendar()
    ugelige_data.append((info[1], info[0], start_dato))
    tab_titler.append(f"Uge {info[1]}")

tabs = st.tabs(tab_titler)

def vis_ugentlig_formular(uge_nr, aar, start_dato):
    arbejdsdage = get_working_days_for_week(start_dato)
    gemt_data = hent_eksisterende_tilmelding(bruger_email, uge_nr, aar)

    er_laest, deadline = er_uge_laest(start_dato, cfg)

    default_er_her_idx = 0 if (not gemt_data or gemt_data["er_til_stede"] == "Ja") else 1
    default_gaester = gemt_data["antal_gaester"] if gemt_data else 0
    gemt_dags_status = gemt_data["dags_status"] if gemt_data else {}

    if er_laest:
        st.warning(f"🔒 Tilmeldingen for uge {uge_nr} lukkedes {deadline.strftime('%d/%m-%Y kl. %H:%M')}. Du kan se dine valg below, men ikke ændre dem.")
    else:
        st.caption(f"⏱️ Tilmeldingen låser: {deadline.strftime('%d/%m-%Y kl. %H:%M')}")
        if gemt_data:
            st.info("ℹ️ Dine tidligere gemte valg er indlæst below.")

    with st.form(key=f"form_uge_{uge_nr}"):
        st.subheader(f"Tilmelding for Uge {uge_nr}")

        er_her = st.radio(
            f"Er du til stede i uge {uge_nr}?",
            options=["Ja", "Nej"],
            index=default_er_her_idx,
            key=f"er_her_{uge_nr}",
            disabled=er_laest
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
                    key=f"status_{uge_nr}_{dag['iso_dato']}",
                    disabled=er_laest
                )

            st.divider()
            gaester = st.number_input(
                "Hvor mange gæster har du i alt med i denne uge?",
                min_value=0,
                max_value=20,
                value=default_gaester,
                step=1,
                key=f"gaester_{uge_nr}",
                disabled=er_laest
            )

        submit = st.form_submit_button(
            "Tilmelding er låst" if er_laest else "Gem / Opdater tilmelding",
            use_container_width=True,
            disabled=er_laest
        )

    if submit and not er_laest:
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

for tab, (uge_nr, aar, start_dato) in zip(tabs, ugelige_data):
    with tab:
        vis_ugentlig_formular(uge_nr, aar, start_dato)