import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta


# ============================================================
# DATABASE
# ============================================================

DB_NAME = "dental_tracker.db"


def connect_db():
    return sqlite3.connect(DB_NAME)


def initialize_database():
    conn = connect_db()
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
            FOREIGN KEY (patient_id) REFERENCES patients(id)
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
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# DATE FUNCTIONS
# ============================================================

def calculate_due_date(last_visit, months):
    try:
        date = datetime.strptime(last_visit, "%Y-%m-%d")
        due = date + relativedelta(months=months)
        return due.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def days_until(date_string):
    try:
        due = datetime.strptime(date_string, "%Y-%m-%d").date()
        today = datetime.today().date()
        return (due - today).days
    except ValueError:
        return 99999


# ============================================================
# MAIN APPLICATION
# ============================================================

class DentalTracker:

    def __init__(self, root):
        self.root = root
        self.root.title("Dental Patient Tracker")
        self.root.geometry("1100x700")

        self.selected_patient_id = None

        self.create_interface()
        self.load_patients()
        self.update_dashboard()

    # --------------------------------------------------------
    # INTERFACE
    # --------------------------------------------------------

    def create_interface(self):

        title = tk.Label(
            self.root,
            text="Dental Patient Tracker",
            font=("Arial", 24, "bold")
        )
        title.pack(pady=15)

        # Dashboard
        dashboard = tk.Frame(self.root)
        dashboard.pack(fill="x", padx=20, pady=5)

        self.overdue_label = tk.Label(
            dashboard,
            text="Overdue: 0",
            font=("Arial", 14)
        )
        self.overdue_label.pack(side="left", padx=30)

        self.week_label = tk.Label(
            dashboard,
            text="Due this week: 0",
            font=("Arial", 14)
        )
        self.week_label.pack(side="left", padx=30)

        self.month_label = tk.Label(
            dashboard,
            text="Due this month: 0",
            font=("Arial", 14)
        )
        self.month_label.pack(side="left", padx=30)

        # Search
        search_frame = tk.Frame(self.root)
        search_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(
            search_frame,
            text="Search:"
        ).pack(side="left")

        self.search_entry = tk.Entry(search_frame, width=30)
        self.search_entry.pack(side="left", padx=10)

        tk.Button(
            search_frame,
            text="Search",
            command=self.search_patients
        ).pack(side="left")

        tk.Button(
            search_frame,
            text="Show All",
            command=self.load_patients
        ).pack(side="left", padx=5)

        # Main area
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # ----------------------------------------------------
        # LEFT: PATIENT LIST
        # ----------------------------------------------------

        left_frame = tk.Frame(main_frame)
        left_frame.pack(side="left", fill="y", padx=(0, 10))

        tk.Label(
            left_frame,
            text="Patients",
            font=("Arial", 16, "bold")
        ).pack()

        self.patient_list = tk.Listbox(
            left_frame,
            width=25,
            height=25
        )
        self.patient_list.pack(fill="y", expand=True)

        self.patient_list.bind(
            "<<ListboxSelect>>",
            self.patient_selected
        )

        button_frame = tk.Frame(left_frame)
        button_frame.pack(pady=10)

        tk.Button(
            button_frame,
            text="New Patient",
            command=self.new_patient
        ).pack(side="left", padx=3)

        tk.Button(
            button_frame,
            text="Delete",
            command=self.delete_patient
        ).pack(side="left", padx=3)

        # ----------------------------------------------------
        # RIGHT: PATIENT DETAILS
        # ----------------------------------------------------

        right_frame = tk.Frame(main_frame)
        right_frame.pack(
            side="left",
            fill="both",
            expand=True
        )

        self.patient_title = tk.Label(
            right_frame,
            text="Select a patient",
            font=("Arial", 18, "bold")
        )
        self.patient_title.pack(anchor="w")

        # Treatment needs
        tk.Label(
            right_frame,
            text="Restorative Needs",
            font=("Arial", 15, "bold")
        ).pack(anchor="w", pady=(20, 5))

        columns = (
            "tooth",
            "treatment",
            "priority",
            "status"
        )

        self.treatment_tree = ttk.Treeview(
            right_frame,
            columns=columns,
            show="headings",
            height=8
        )

        headings = {
            "tooth": "Tooth",
            "treatment": "Treatment",
            "priority": "Priority",
            "status": "Status"
        }

        for column in columns:
            self.treatment_tree.heading(
                column,
                text=headings[column]
            )

        self.treatment_tree.pack(fill="x")

        treatment_buttons = tk.Frame(right_frame)
        treatment_buttons.pack(pady=5)

        tk.Button(
            treatment_buttons,
            text="Add Treatment",
            command=self.add_treatment
        ).pack(side="left", padx=3)

        tk.Button(
            treatment_buttons,
            text="Edit Treatment",
            command=self.edit_treatment
        ).pack(side="left", padx=3)

        tk.Button(
            treatment_buttons,
            text="Delete Treatment",
            command=self.delete_treatment
        ).pack(side="left", padx=3)

        # Recall
        tk.Label(
            right_frame,
            text="Recall",
            font=("Arial", 15, "bold")
        ).pack(anchor="w", pady=(20, 5))

        recall_columns = (
            "type",
            "interval",
            "last_visit",
            "next_due",
            "status"
        )

        self.recall_tree = ttk.Treeview(
            right_frame,
            columns=recall_columns,
            show="headings",
            height=5
        )

        recall_headings = {
            "type": "Recall Type",
            "interval": "Interval",
            "last_visit": "Last Visit",
            "next_due": "Next Due",
            "status": "Status"
        }

        for column in recall_columns:
            self.recall_tree.heading(
                column,
                text=recall_headings[column]
            )

        self.recall_tree.pack(fill="x")

        recall_buttons = tk.Frame(right_frame)
        recall_buttons.pack(pady=5)

        tk.Button(
            recall_buttons,
            text="Add Recall",
            command=self.add_recall
        ).pack(side="left", padx=3)

        tk.Button(
            recall_buttons,
            text="Edit Recall",
            command=self.edit_recall
        ).pack(side="left", padx=3)

        tk.Button(
            recall_buttons,
            text="Delete Recall",
            command=self.delete_recall
        ).pack(side="left", padx=3)

    # ========================================================
    # PATIENTS
    # ========================================================

    def load_patients(self):

        self.patient_list.delete(0, tk.END)

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, patient_id
            FROM patients
            ORDER BY patient_id
        """)

        self.patient_data = cursor.fetchall()

        conn.close()

        for patient in self.patient_data:
            self.patient_list.insert(
                tk.END,
                patient[1]
            )

    def search_patients(self):

        search = self.search_entry.get().strip()

        self.patient_list.delete(0, tk.END)

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, patient_id
            FROM patients
            WHERE patient_id LIKE ?
            ORDER BY patient_id
        """, (f"%{search}%",))

        self.patient_data = cursor.fetchall()

        conn.close()

        for patient in self.patient_data:
            self.patient_list.insert(
                tk.END,
                patient[1]
            )

    def patient_selected(self, event):

        selection = self.patient_list.curselection()

        if not selection:
            return

        index = selection[0]

        self.selected_patient_id = self.patient_data[index][0]
        patient_identifier = self.patient_data[index][1]

        self.patient_title.config(
            text=f"Patient {patient_identifier}"
        )

        self.load_treatments()
        self.load_recalls()

    def new_patient(self):

        window = tk.Toplevel(self.root)
        window.title("New Patient")
        window.geometry("350x200")

        tk.Label(
            window,
            text="Internal Patient ID"
        ).pack(pady=10)

        entry = tk.Entry(window)
        entry.pack()

        def save():

            patient_id = entry.get().strip()

            if not patient_id:
                messagebox.showerror(
                    "Error",
                    "Enter a patient ID."
                )
                return

            conn = connect_db()
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO patients (patient_id)
                    VALUES (?)
                """, (patient_id,))

                conn.commit()

            except sqlite3.IntegrityError:
                messagebox.showerror(
                    "Error",
                    "That patient ID already exists."
                )
                conn.close()
                return

            conn.close()

            window.destroy()

            self.load_patients()
            self.update_dashboard()

        tk.Button(
            window,
            text="Save",
            command=save
        ).pack(pady=20)

    def delete_patient(self):

        if not self.selected_patient_id:
            return

        confirm = messagebox.askyesno(
            "Delete Patient",
            "Delete this patient and their workflow data?"
        )

        if not confirm:
            return

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM treatment_needs
            WHERE patient_id = ?
        """, (self.selected_patient_id,))

        cursor.execute("""
            DELETE FROM recalls
            WHERE patient_id = ?
        """, (self.selected_patient_id,))

        cursor.execute("""
            DELETE FROM patients
            WHERE id = ?
        """, (self.selected_patient_id,))

        conn.commit()
        conn.close()

        self.selected_patient_id = None
        self.patient_title.config(text="Select a patient")

        self.load_patients()
        self.clear_details()
        self.update_dashboard()

    # ========================================================
    # TREATMENTS
    # ========================================================

    def load_treatments(self):

        for item in self.treatment_tree.get_children():
            self.treatment_tree.delete(item)

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, tooth, treatment,
                   priority, status
            FROM treatment_needs
            WHERE patient_id = ?
        """, (self.selected_patient_id,))

        rows = cursor.fetchall()

        conn.close()

        for row in rows:
            self.treatment_tree.insert(
                "",
                tk.END,
                iid=row[0],
                values=row[1:]
            )

    def add_treatment(self):

        if not self.selected_patient_id:
            return

        self.treatment_window()

    def edit_treatment(self):

        selected = self.treatment_tree.selection()

        if not selected:
            messagebox.showwarning(
                "Select Treatment",
                "Select a treatment first."
            )
            return

        treatment_id = selected[0]

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT tooth, treatment,
                   priority, status, notes
            FROM treatment_needs
            WHERE id = ?
        """, (treatment_id,))

        data = cursor.fetchone()
        conn.close()

        self.treatment_window(
            treatment_id,
            data
        )

    def treatment_window(self, treatment_id=None, data=None):

        window = tk.Toplevel(self.root)
        window.title("Treatment")
        window.geometry("450x450")

        labels = [
            "Tooth",
            "Treatment",
            "Priority",
            "Status",
            "Notes"
        ]

        entries = []

        for i, label in enumerate(labels):

            tk.Label(
                window,
                text=label
            ).pack(anchor="w", padx=20, pady=(10, 2))

            if label in ["Priority", "Status"]:

                if label == "Priority":
                    values = ["High", "Medium", "Low"]

                else:
                    values = [
                        "Planned",
                        "Scheduled",
                        "In Progress",
                        "Completed",
                        "Referred"
                    ]

                entry = ttk.Combobox(
                    window,
                    values=values,
                    state="readonly"
                )

                entry.pack(
                    fill="x",
                    padx=20
                )

            else:

                entry = tk.Entry(window)
                entry.pack(
                    fill="x",
                    padx=20
                )

            entries.append(entry)

        if data:

            for entry, value in zip(entries, data):

                entry.insert(
                    0,
                    value if value else ""
                )

        def save():

            values = [
                entry.get().strip()
                for entry in entries
            ]

            conn = connect_db()
            cursor = conn.cursor()

            if treatment_id:

                cursor.execute("""
                    UPDATE treatment_needs
                    SET tooth = ?,
                        treatment = ?,
                        priority = ?,
                        status = ?,
                        notes = ?
                    WHERE id = ?
                """, (*values, treatment_id))

            else:

                cursor.execute("""
                    INSERT INTO treatment_needs
                    (
                        patient_id,
                        tooth,
                        treatment,
                        priority,
                        status,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.selected_patient_id,
                    *values
                ))

            conn.commit()
            conn.close()

            window.destroy()

            self.load_treatments()
            self.update_dashboard()

        tk.Button(
            window,
            text="Save",
            command=save
        ).pack(pady=20)

    def delete_treatment(self):

        selected = self.treatment_tree.selection()

        if not selected:
            return

        if not messagebox.askyesno(
            "Delete Treatment",
            "Delete this treatment need?"
        ):
            return

        treatment_id = selected[0]

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM treatment_needs
            WHERE id = ?
        """, (treatment_id,))

        conn.commit()
        conn.close()

        self.load_treatments()
        self.update_dashboard()

    # ========================================================
    # RECALLS
    # ========================================================

    def load_recalls(self):

        for item in self.recall_tree.get_children():
            self.recall_tree.delete(item)

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id,
                   recall_type,
                   interval_months,
                   last_visit,
                   next_due,
                   status
            FROM recalls
            WHERE patient_id = ?
        """, (self.selected_patient_id,))

        rows = cursor.fetchall()

        conn.close()

        for row in rows:

            self.recall_tree.insert(
                "",
                tk.END,
                iid=row[0],
                values=(
                    row[1],
                    f"{row[2]} months",
                    row[3],
                    row[4],
                    row[5]
                )
            )

    def add_recall(self):

        if not self.selected_patient_id:
            return

        self.recall_window()

    def edit_recall(self):

        selected = self.recall_tree.selection()

        if not selected:
            messagebox.showwarning(
                "Select Recall",
                "Select a recall first."
            )
            return

        recall_id = selected[0]

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT recall_type,
                   interval_months,
                   last_visit,
                   status
            FROM recalls
            WHERE id = ?
        """, (recall_id,))

        data = cursor.fetchone()

        conn.close()

        self.recall_window(
            recall_id,
            data
        )

    def recall_window(self, recall_id=None, data=None):

        window = tk.Toplevel(self.root)
        window.title("Recall")
        window.geometry("400x350")

        tk.Label(
            window,
            text="Recall Type"
        ).pack(pady=(15, 3))

        recall_type = ttk.Combobox(
            window,
            values=[
                "Perio Maintenance",
                "Prophy",
                "Periodic Exam",
                "Radiographs",
                "Post-op Follow-up",
                "Other"
            ]
        )
        recall_type.pack(fill="x", padx=20)

        tk.Label(
            window,
            text="Interval (months)"
        ).pack(pady=(15, 3))

        interval = ttk.Combobox(
            window,
            values=["3", "4", "6", "12", "18", "24", "36"]
        )
        interval.pack(fill="x", padx=20)

        tk.Label(
            window,
            text="Last Visit (YYYY-MM-DD)"
        ).pack(pady=(15, 3))

        last_visit = tk.Entry(window)
        last_visit.pack(fill="x", padx=20)

        tk.Label(
            window,
            text="Status"
        ).pack(pady=(15, 3))

        status = ttk.Combobox(
            window,
            values=[
                "Upcoming",
                "Due Soon",
                "Overdue",
                "Contacted",
                "Scheduled",
                "Completed"
            ],
            state="readonly"
        )
        status.pack(fill="x", padx=20)

        if data:

            recall_type.set(data[0])
            interval.set(str(data[1]))
            last_visit.insert(0, data[2])
            status.set(data[3])

        def save():

            try:
                months = int(interval.get())
            except ValueError:
                messagebox.showerror(
                    "Error",
                    "Interval must be a number."
                )
                return

            due_date = calculate_due_date(
                last_visit.get(),
                months
            )

            if not due_date:
                messagebox.showerror(
                    "Error",
                    "Use YYYY-MM-DD for the last visit."
                )
                return

            # Automatically determine status
            days = days_until(due_date)

            if days < 0:
                calculated_status = "Overdue"
            elif days <= 30:
                calculated_status = "Due Soon"
            else:
                calculated_status = "Upcoming"

            # Preserve manually selected workflow states
            if status.get() in [
                "Contacted",
                "Scheduled",
                "Completed"
            ]:
                calculated_status = status.get()

            conn = connect_db()
            cursor = conn.cursor()

            if recall_id:

                cursor.execute("""
                    UPDATE recalls
                    SET recall_type = ?,
                        interval_months = ?,
                        last_visit = ?,
                        next_due = ?,
                        status = ?
                    WHERE id = ?
                """, (
                    recall_type.get(),
                    months,
                    last_visit.get(),
                    due_date,
                    calculated_status,
                    recall_id
                ))

            else:

                cursor.execute("""
                    INSERT INTO recalls
                    (
                        patient_id,
                        recall_type,
                        interval_months,
                        last_visit,
                        next_due,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self.selected_patient_id,
                    recall_type.get(),
                    months,
                    last_visit.get(),
                    due_date,
                    calculated_status
                ))

            conn.commit()
            conn.close()

            window.destroy()

            self.load_recalls()
            self.update_dashboard()

        tk.Button(
            window,
            text="Save Recall",
            command=save
        ).pack(pady=20)

    def delete_recall(self):

        selected = self.recall_tree.selection()

        if not selected:
            return

        if not messagebox.askyesno(
            "Delete Recall",
            "Delete this recall?"
        ):
            return

        recall_id = selected[0]

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM recalls
            WHERE id = ?
        """, (recall_id,))

        conn.commit()
        conn.close()

        self.load_recalls()
        self.update_dashboard()

    # ========================================================
    # DASHBOARD
    # ========================================================

    def update_dashboard(self):

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT next_due
            FROM recalls
            WHERE status NOT IN ('Completed', 'Scheduled')
        """)

        recalls = cursor.fetchall()

        conn.close()

        overdue = 0
        due_week = 0
        due_month = 0

        for row in recalls:

            days = days_until(row[0])

            if days < 0:
                overdue += 1

            elif days <= 7:
                due_week += 1

            elif days <= 30:
                due_month += 1

        self.overdue_label.config(
            text=f"Overdue: {overdue}"
        )

        self.week_label.config(
            text=f"Due this week: {due_week}"
        )

        self.month_label.config(
            text=f"Due this month: {due_month}"
        )

    # ========================================================
    # CLEAR
    # ========================================================

    def clear_details(self):

        for item in self.treatment_tree.get_children():
            self.treatment_tree.delete(item)

        for item in self.recall_tree.get_children():
            self.recall_tree.delete(item)


# ============================================================
# START PROGRAM
# ============================================================

if __name__ == "__main__":

    initialize_database()

    root = tk.Tk()

    app = DentalTracker(root)

    root.mainloop()