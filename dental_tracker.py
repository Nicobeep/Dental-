import streamlit as st
import sqlite3
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import pandas as pd
import hashlib
import secrets
import re
from pathlib import Path


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Dental Patient Tracker",
    page_icon="🦷",
    layout="wide"
)


# ============================================================
# MULTI-USER DATABASE
# ============================================================

DATA_DIR = Path("databases")
USERS_DB = Path("users.db")


def connect_users_db():
    return sqlite3.connect(USERS_DB)


def user_db_path(username):
    DATA_DIR.mkdir(exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", username.strip())
    return DATA_DIR / f"{safe}.db"


def connect_db():
    username = st.session_state.get("username")

    if not username:
        raise RuntimeError("No user is logged in.")

    return sqlite3.connect(user_db_path(username))


# ============================================================
# USER DATABASE
# ============================================================

def initialize_users_database():
    conn = connect_users_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200_000
    ).hex()

    return password_hash, salt


def verify_password(password, stored_hash, salt):
    password_hash, _ = hash_password(password, salt)

    return secrets.compare_digest(
        password_hash,
        stored_hash
    )


def create_user(username, password):
    username = username.strip()

    if not username or not password:
        return False, "Username and password are required."

    if len(username) < 3:
        return False, "Username must be at least 3 characters."

    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return False, "Username can only contain letters, numbers, _, -, and ."

    conn = connect_users_db()
    cursor = conn.cursor()

    password_hash, salt = hash_password(password)

    try:
        cursor.execute(
            """
            INSERT INTO users
            (username, password_hash, salt)
            VALUES (?, ?, ?)
            """,
            (username, password_hash, salt)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False, "That username already exists."

    conn.close()
    initialize_database_for_user(username)

    return True, "Account created."


def authenticate_user(username, password):
    username = username.strip()

    conn = connect_users_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT username, password_hash, salt
        FROM users
        WHERE username = ?
        """,
        (username,)
    )

    user = cursor.fetchone()
    conn.close()

    return bool(
        user
        and verify_password(
            password,
            user[1],
            user[2]
        )
    )


# ============================================================
# USER DATABASE TABLES
# ============================================================

def initialize_database_for_user(username):
    conn = sqlite3.connect(user_db_path(username))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT UNIQUE NOT NULL,
            notes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treatment_needs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            tooth TEXT,
            treatment TEXT,
            priority TEXT,
            status TEXT,
            notes TEXT,
            FOREIGN KEY (patient_id)
            REFERENCES patients(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recalls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            recall_type TEXT,
            interval_months INTEGER,
            last_visit TEXT,
            next_due TEXT,
            status TEXT,
            FOREIGN KEY (patient_id)
            REFERENCES patients(id)
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# DATE FUNCTIONS
# ============================================================

def calculate_due_date(last_visit, months):
    try:
        parsed = datetime.strptime(last_visit, "%Y-%m-%d")
        due = parsed + relativedelta(months=months)
        return due.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def days_until(date_string):
    try:
        due = datetime.strptime(date_string, "%Y-%m-%d").date()
        return (due - date.today()).days
    except (ValueError, TypeError):
        return 99999


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_patients(search=""):
    conn = connect_db()
    cursor = conn.cursor()

    if search.strip():
        cursor.execute(
            """
            SELECT id, patient_id, notes
            FROM patients
            WHERE patient_id LIKE ?
            ORDER BY patient_id
            """,
            (f"%{search.strip()}%",)
        )
    else:
        cursor.execute(
            """
            SELECT id, patient_id, notes
            FROM patients
            ORDER BY patient_id
            """
        )

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_treatments(patient_id):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            tooth,
            treatment,
            priority,
            status,
            notes
        FROM treatment_needs
        WHERE patient_id = ?
        ORDER BY id
        """,
        (patient_id,)
    )

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_recalls(patient_id):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            recall_type,
            interval_months,
            last_visit,
            next_due,
            status
        FROM recalls
        WHERE patient_id = ?
        ORDER BY next_due
        """,
        (patient_id,)
    )

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_due_soon_recalls():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            recalls.id,
            patients.patient_id,
            recalls.recall_type,
            recalls.next_due,
            recalls.status
        FROM recalls
        JOIN patients
            ON recalls.patient_id = patients.id
        WHERE recalls.status
            NOT IN (
                'Completed',
                'Scheduled'
            )
        ORDER BY recalls.next_due
        """
    )

    rows = cursor.fetchall()
    conn.close()

    due_recalls = []
    for row in rows:
        recall_id, patient_identifier, recall_type, next_due, status = row
        days = days_until(next_due)

        if days <= 14:
            due_recalls.append({
                "id": recall_id,
                "patient": patient_identifier,
                "type": recall_type,
                "due": next_due,
                "days": days,
                "status": status
            })

    return due_recalls


def get_dashboard_counts():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT next_due
        FROM recalls
        WHERE status
            NOT IN (
                'Completed',
                'Scheduled'
            )
        """
    )

    recalls = cursor.fetchall()
    conn.close()

    overdue = 0
    due_week = 0
    due_month = 0

    for (next_due,) in recalls:
        days = days_until(next_due)
        if days < 0:
            overdue += 1
        elif days <= 7:
            due_week += 1
        elif days <= 30:
            due_month += 1

    return overdue, due_week, due_month


def patient_exists(patient_id):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id
        FROM patients
        WHERE patient_id = ?
        """,
        (patient_id,)
    )

    result = cursor.fetchone()
    conn.close()
    return result is not None


# ============================================================
# SESSION STATE
# ============================================================

def initialize_session_state():
    defaults = {
        "selected_patient_id": None,
        "selected_treatment_id": None,
        "selected_recall_id": None,
        "show_add_patient": False,
        "show_treatment_form": False,
        "show_recall_form": False,
        "editing_treatment": False,
        "editing_recall": False,
        "notification_shown": False,
        "confirm_delete_patient": False
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ============================================================
# INITIALIZATION
# ============================================================

initialize_users_database()
initialize_session_state()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


# ============================================================
# LOGIN
# ============================================================

if not st.session_state.authenticated:
    st.title("Dental Patient Tracker")
    st.caption("Sign in to access your own patient database.")

    login_tab, create_tab = st.tabs(["Log In", "Create Account"])

    with login_tab:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Log In", type="primary", use_container_width=True):
            if authenticate_user(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username.strip()
                initialize_database_for_user(st.session_state.username)
                st.session_state.selected_patient_id = None
                st.session_state.notification_shown = False
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with create_tab:
        new_username = st.text_input("Choose a username", key="create_username")
        new_password = st.text_input("Choose a password", type="password", key="create_password")
        confirm_password = st.text_input("Confirm password", type="password", key="confirm_password")

        if st.button("Create Account", use_container_width=True):
            if new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                success, message = create_user(new_username, new_password)
                if success:
                    st.success("Account created. You can now log in.")
                else:
                    st.error(message)

    st.stop()


# ============================================================
# INITIALIZE CURRENT USER DATABASE
# ============================================================

initialize_database_for_user(st.session_state.username)


# ============================================================
# DIALOG MODAL FOR RECALLS (Fixed Pop-up Window)
# ============================================================

@st.dialog("⚠️ Urgent Recalls Requiring Attention")
def show_recall_modal(recalls):
    st.warning("The following patient recalls require immediate follow-up:")

    overdue = [r for r in recalls if r["days"] < 0]
    upcoming = [r for r in recalls if r["days"] >= 0]

    if overdue:
        st.subheader("Overdue")
        for r in overdue:
            st.markdown(f"• **Patient {r['patient']}** — {r['type']} (Due: `{r['due']}`)")

    if upcoming:
        st.subheader("Due Soon")
        for r in upcoming:
            st.markdown(f"• **Patient {r['patient']}** — {r['type']} (Due: `{r['due']}`)")

    if st.button("Acknowledge & Close", type="primary", use_container_width=True):
        st.session_state.notification_shown = True
        st.rerun()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.write(f"**Logged in as:** {st.session_state.username}")

    if st.button("Log Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.selected_patient_id = None
        st.session_state.selected_treatment_id = None
        st.session_state.selected_recall_id = None
        st.session_state.show_treatment_form = False
        st.session_state.show_recall_form = False
        st.session_state.notification_shown = False
        st.rerun()


# ============================================================
# TITLE
# ============================================================

st.title("Dental Patient Tracker")


# ============================================================
# RECALL POPUP MODAL TRIGGER
# ============================================================

due_soon_recalls = get_due_soon_recalls()

if due_soon_recalls and not st.session_state.notification_shown:
    show_recall_modal(due_soon_recalls)


# ============================================================
# DASHBOARD
# ============================================================

overdue, due_week, due_month = get_dashboard_counts()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Overdue", overdue)

with col2:
    st.metric("Due this week", due_week)

with col3:
    st.metric("Due this month", due_month)

st.divider()


# ============================================================
# SEARCH
# ============================================================

search = st.text_input("Search patients", placeholder="Enter internal patient ID...")
patients = get_patients(search)


# ============================================================
# NEW PATIENT
# ============================================================

with st.expander("New Patient", expanded=st.session_state.show_add_patient):
    patient_identifier = st.text_input("Internal Patient ID", key="new_patient_identifier")

    if st.button("Save Patient", type="primary"):
        patient_identifier = patient_identifier.strip()

        if not patient_identifier:
            st.error("Enter a patient ID.")
        elif patient_exists(patient_identifier):
            st.error("That patient ID already exists.")
        else:
            conn = connect_db()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO patients (patient_id)
                VALUES (?)
                """,
                (patient_identifier,)
            )

            conn.commit()
            new_id = cursor.lastrowid
            conn.close()

            st.session_state.selected_patient_id = new_id
            st.success("Patient added.")
            st.rerun()


# ============================================================
# MAIN LAYOUT
# ============================================================

left, right = st.columns([1, 3])


# ============================================================
# LEFT — PATIENT LIST
# ============================================================

with left:
    st.subheader("Patients")

    if not patients:
        st.info("No patients found.")
    else:
        for db_id, patient_identifier, _ in patients:
            selected = (db_id == st.session_state.selected_patient_id)

            if st.button(
                patient_identifier,
                key=f"patient_{db_id}",
                use_container_width=True,
                type="primary" if selected else "secondary"
            ):
                st.session_state.selected_patient_id = db_id
                st.session_state.selected_treatment_id = None
                st.session_state.selected_recall_id = None
                st.session_state.show_treatment_form = False
                st.session_state.show_recall_form = False
                st.rerun()

    st.divider()

    if st.session_state.selected_patient_id:
        if st.button("Delete Patient", use_container_width=True):
            st.session_state.confirm_delete_patient = True

        if st.session_state.get("confirm_delete_patient", False):
            st.warning("Delete this patient and their workflow data?")
            confirm_col, cancel_col = st.columns(2)

            with confirm_col:
                if st.button("Yes, Delete", type="primary"):
                    patient_id = st.session_state.selected_patient_id
                    conn = connect_db()
                    cursor = conn.cursor()

                    cursor.execute("DELETE FROM treatment_needs WHERE patient_id = ?", (patient_id,))
                    cursor.execute("DELETE FROM recalls WHERE patient_id = ?", (patient_id,))
                    cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,))

                    conn.commit()
                    conn.close()

                    st.session_state.selected_patient_id = None
                    st.session_state.confirm_delete_patient = False
                    st.rerun()

            with cancel_col:
                if st.button("Cancel"):
                    st.session_state.confirm_delete_patient = False
                    st.rerun()


# ============================================================
# RIGHT — PATIENT DETAILS
# ============================================================

with right:
    selected_patient_id = st.session_state.selected_patient_id

    if not selected_patient_id:
        st.info("Select a patient to view details.")
    else:
        selected_patient = next(
            (patient for patient in patients if patient[0] == selected_patient_id),
            None
        )

        if selected_patient:
            patient_identifier = selected_patient[1]
        else:
            all_patients = get_patients()
            selected_patient = next(
                (patient for patient in all_patients if patient[0] == selected_patient_id),
                None
            )
            patient_identifier = selected_patient[1] if selected_patient else "Unknown"

        st.header(f"Patient {patient_identifier}")

        # ====================================================
        # RESTORATIVE NEEDS
        # ====================================================
        st.subheader("Restorative Needs")

        treatments = get_treatments(selected_patient_id)

        if treatments:
            treatment_df = pd.DataFrame([
                {
                    "ID": row[0],
                    "Tooth": row[1] or "",
                    "Treatment": row[2] or "",
                    "Priority": row[3] or "",
                    "Status": row[4] or "",
                }
                for row in treatments
            ])

            st.dataframe(
                treatment_df.drop(columns=["ID"]),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No restorative needs recorded.")

        treatment_ids = [row[0] for row in treatments]

        selected_treatment = st.selectbox(
            "Select treatment",
            options=["None"] + treatment_ids,
            format_func=lambda x: (
                "None" if x == "None"
                else next(
                    (f"Tooth {row[1]} — {row[2]}" for row in treatments if row[0] == x),
                    str(x)
                )
            ),
            key="treatment_selector"
        )

        button1, button2, button3 = st.columns(3)

        with button1:
            if st.button("Add Treatment", use_container_width=True):
                st.session_state.show_treatment_form = True
                st.session_state.editing_treatment = False
                st.session_state.selected_treatment_id = None
                st.rerun()

        with button2:
            if st.button("Edit Treatment", disabled=(selected_treatment == "None"), use_container_width=True):
                st.session_state.show_treatment_form = True
                st.session_state.editing_treatment = True
                st.session_state.selected_treatment_id = selected_treatment
                st.rerun()

        with button3:
            if st.button("Delete Treatment", disabled=(selected_treatment == "None"), use_container_width=True):
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM treatment_needs WHERE id = ?", (selected_treatment,))
                conn.commit()
                conn.close()
                st.session_state.selected_treatment_id = None
                st.rerun()

        # ====================================================
        # TREATMENT FORM
        # ====================================================
        if st.session_state.show_treatment_form:
            treatment_id = st.session_state.selected_treatment_id
            existing = None

            if treatment_id:
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT tooth, treatment, priority, status, notes
                    FROM treatment_needs
                    WHERE id = ?
                    """,
                    (treatment_id,)
                )
                existing = cursor.fetchone()
                conn.close()

            st.markdown("---")
            st.subheader("Edit Treatment" if treatment_id else "Add Treatment")

            default_tooth = existing[0] if existing else ""
            default_treatment = existing[1] if existing else ""
            default_priority = existing[2] if existing else "Medium"
            default_status = existing[3] if existing else "Planned"
            default_notes = existing[4] if existing else ""

            tooth = st.text_input("Tooth", value=default_tooth, key=f"treatment_tooth_{treatment_id}")
            treatment = st.text_input("Treatment", value=default_treatment, key=f"treatment_name_{treatment_id}")

            priority_options = ["High", "Medium", "Low"]
            priority = st.selectbox(
                "Priority",
                priority_options,
                index=priority_options.index(default_priority) if default_priority in priority_options else 1,
                key=f"treatment_priority_{treatment_id}"
            )

            status_options = ["Planned", "Scheduled", "In Progress", "Completed", "Referred"]
            status = st.selectbox(
                "Status",
                status_options,
                index=status_options.index(default_status) if default_status in status_options else 0,
                key=f"treatment_status_{treatment_id}"
            )

            notes = st.text_area("Notes", value=default_notes, key=f"treatment_notes_{treatment_id}")

            save_col, cancel_col = st.columns(2)

            with save_col:
                if st.button("Save Treatment", type="primary", use_container_width=True):
                    conn = connect_db()
                    cursor = conn.cursor()

                    if treatment_id:
                        cursor.execute(
                            """
                            UPDATE treatment_needs
                            SET tooth = ?, treatment = ?, priority = ?, status = ?, notes = ?
                            WHERE id = ?
                            """,
                            (tooth.strip(), treatment.strip(), priority, status, notes.strip(), treatment_id)
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO treatment_needs
                            (patient_id, tooth, treatment, priority, status, notes)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (selected_patient_id, tooth.strip(), treatment.strip(), priority, status, notes.strip())
                        )

                    conn.commit()
                    conn.close()

                    st.session_state.show_treatment_form = False
                    st.session_state.selected_treatment_id = None
                    st.success("Treatment saved.")
                    st.rerun()

            with cancel_col:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.show_treatment_form = False
                    st.session_state.selected_treatment_id = None
                    st.rerun()
