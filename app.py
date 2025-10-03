"""
expense_tracker.py

Modern Expense Tracker (PyQt5) with:
- Login / Register (local users, hashed passwords)
- Add Expense / Add Income with categories
- Categories management
- Monthly / Weekly summaries
- Embedded Matplotlib charts (bar / pie / trend)
- Export to CSV and PDF (reportlab)
- Optional Google Sheets sync (gspread + service account)
- Dark / Light mode toggle
- SQLite persistence

Run:
    pip install -r requirements.txt
    python expense_tracker.py

Notes:
- To enable Google Sheets sync, create a Google service account and download JSON credentials.
  Place the file and point settings to its path (GUI Setting).
"""

import sys
import os
import sqlite3
import csv
import io
import tempfile
from datetime import datetime, date, timedelta
import hashlib
import json

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QComboBox, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QDateEdit, QTabWidget, QSpinBox, QFileDialog, QDialog, QFormLayout,
    QGridLayout, QGroupBox, QCheckBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont

import pandas as pd
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Optional libraries (import if available)
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GSHEETS_AVAILABLE = True
except Exception:
    GSHEETS_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# ---------------------------
# Constants & DB initialization
# ---------------------------
APP_DB = os.path.join(os.path.dirname(__file__), "expenses.db")
DEFAULT_CATEGORIES = ["Food", "Bills", "Transport", "Entertainment", "Groceries", "Other"]

def get_db_connection():
    con = sqlite3.connect(APP_DB)
    con.row_factory = sqlite3.Row
    return con

def initialize_db():
    con = get_db_connection()
    cur = con.cursor()
    # users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password_hash TEXT,
        created_at TEXT
    )
    """)
    # transactions: type 'expense' or 'income'
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        date TEXT,
        type TEXT,
        category TEXT,
        amount REAL,
        description TEXT,
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    # categories per user
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        name TEXT,
        UNIQUE(user_id, name),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    con.commit()
    con.close()

initialize_db()

# ---------------------------
# Utility: password hashing
# ---------------------------
def hash_password(password: str, salt: bytes = None):
    """Return salt + hash as hex string; uses PBKDF2-HMAC-SHA256"""
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
    return salt.hex() + dk.hex()

def verify_password(stored_hex: str, password_attempt: str) -> bool:
    try:
        salt = bytes.fromhex(stored_hex[:32])
        stored_dk = stored_hex[32:]
        dk = hashlib.pbkdf2_hmac('sha256', password_attempt.encode('utf-8'), salt, 100_000)
        return dk.hex() == stored_dk
    except Exception:
        return False

# ---------------------------
# Login / Register Dialog
# ---------------------------
class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login or Register")
        self.resize(400,200)
        layout = QVBoxLayout()
        form = QGridLayout()
        form.addWidget(QLabel("Username:"), 0, 0)
        self.username = QLineEdit()
        form.addWidget(self.username, 0, 1)
        form.addWidget(QLabel("Password:"), 1, 0)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        form.addWidget(self.password, 1, 1)
        layout.addLayout(form)

        btns = QHBoxLayout()
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.login)
        reg_btn = QPushButton("Register")
        reg_btn.clicked.connect(self.register)
        btns.addWidget(login_btn)
        btns.addWidget(reg_btn)
        layout.addLayout(btns)
        self.setLayout(layout)
        self.user_id = None

    def login(self):
        u = self.username.text().strip()
        p = self.password.text().strip()
        if not u or not p:
            QMessageBox.warning(self, "Input", "Enter username and password")
            return
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("SELECT id, password_hash FROM users WHERE username=?", (u,))
        row = cur.fetchone()
        con.close()
        if not row:
            QMessageBox.warning(self, "Login", "User not found")
            return
        if verify_password(row["password_hash"], p):
            self.user_id = row["id"]
            self.accept()
        else:
            QMessageBox.warning(self, "Login", "Incorrect password")

    def register(self):
        u = self.username.text().strip()
        p = self.password.text().strip()
        if not u or not p:
            QMessageBox.warning(self, "Input", "Enter username and password")
            return
        con = get_db_connection()
        cur = con.cursor()
        try:
            h = hash_password(p)
            cur.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                        (u, h, datetime.utcnow().isoformat()))
            con.commit()
            uid = cur.lastrowid
            # add default categories for user
            for cat in DEFAULT_CATEGORIES:
                cur.execute("INSERT OR IGNORE INTO categories (user_id, name) VALUES (?, ?)", (uid, cat))
            con.commit()
            QMessageBox.information(self, "Register", "User created. You can now login.")
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Register", "Username already exists.")
        finally:
            con.close()

# ---------------------------
# Matplotlib canvas widget
# ---------------------------
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=3, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)

# ---------------------------
# Main Application Window
# ---------------------------
class ExpenseTrackerApp(QWidget):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.setWindowTitle("Modern Expense Tracker")
        self.showMaximized()  # full screen but still has title bar and min/max/close
        self.setFont(QFont("Segoe UI", 10))

        self.is_dark = False
        self.light_style = ""
        self.dark_style = "QWidget{background:#111; color:#eee;} QPushButton{background:#eee;color:#111;}"
        self.setStyleSheet(self.light_style)

        # Layout with tabs
        v = QVBoxLayout()
        top_row = QHBoxLayout()
        self.lbl_user = QLabel(f"User ID: {self.user_id}")
        top_row.addWidget(self.lbl_user)
        top_row.addStretch()
        self.theme_btn = QPushButton("Toggle Dark/Light")
        self.theme_btn.clicked.connect(self.toggle_theme)
        top_row.addWidget(self.theme_btn)
        v.addLayout(top_row)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_dashboard_tab(), "Dashboard")
        self.tabs.addTab(self.build_transactions_tab(), "Transactions")
        self.tabs.addTab(self.build_categories_tab(), "Categories")
        self.tabs.addTab(self.build_reports_tab(), "Reports")
        self.tabs.addTab(self.build_settings_tab(), "Settings")
        v.addWidget(self.tabs)

        self.setLayout(v)

        # initial load
        self.refresh_transactions()
        self.refresh_categories()
        self.update_dashboard()

    # ---------------- UI tabs ----------------
    def build_dashboard_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        # Summary labels
        summary_row = QHBoxLayout()
        self.lbl_month = QLabel("Month total: ₱0.00")
        self.lbl_week = QLabel("Week total: ₱0.00")
        self.lbl_balance = QLabel("Balance (income - expenses): ₱0.00")
        for lbl in (self.lbl_month, self.lbl_week, self.lbl_balance):
            lbl.setStyleSheet("font-weight:bold;")
            summary_row.addWidget(lbl)
        layout.addLayout(summary_row)

        # Chart canvas
        self.canvas = MplCanvas(self, width=8, height=4, dpi=100)
        layout.addWidget(self.canvas)

        tab.setLayout(layout)
        return tab

    def build_transactions_tab(self):
        tab = QWidget()
        g = QGridLayout()
        tab.setLayout(g)

        # Left: input form
        formbox = QGroupBox("Add Transaction")
        form = QGridLayout()
        form.addWidget(QLabel("Date:"), 0, 0)
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        form.addWidget(self.date_edit, 0, 1)
        form.addWidget(QLabel("Type:"), 1, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["expense", "income"])
        form.addWidget(self.type_combo, 1, 1)
        form.addWidget(QLabel("Category:"), 2, 0)
        self.cat_combo = QComboBox()
        form.addWidget(self.cat_combo, 2, 1)
        form.addWidget(QLabel("Amount:"), 3, 0)
        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("0.00")
        form.addWidget(self.amount_edit, 3, 1)
        form.addWidget(QLabel("Description:"), 4, 0)
        self.desc_edit = QLineEdit()
        form.addWidget(self.desc_edit, 4, 1)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_transaction)
        form.addWidget(add_btn, 5, 0, 1, 2)
        formbox.setLayout(form)
        g.addWidget(formbox, 0, 0)

        # Right: transactions table + controls
        right_box = QGroupBox("Transactions")
        rlay = QVBoxLayout()
        self.tx_table = QTableWidget(0, 6)
        self.tx_table.setHorizontalHeaderLabels(["ID","Date","Type","Category","Amount","Description"])
        self.tx_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        rlay.addWidget(self.tx_table)

        btn_row = QHBoxLayout()
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self.delete_transaction)
        btn_row.addWidget(del_btn)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_transactions)
        btn_row.addWidget(refresh_btn)
        rlay.addLayout(btn_row)
        right_box.setLayout(rlay)
        g.addWidget(right_box, 0, 1)

        return tab

    def build_categories_tab(self):
        tab = QWidget()
        v = QVBoxLayout()
        self.category_list = QComboBox()
        v.addWidget(QLabel("Categories (select to remove)"))
        v.addWidget(self.category_list)
        h = QHBoxLayout()
        self.new_cat = QLineEdit()
        self.new_cat.setPlaceholderText("New category name")
        h.addWidget(self.new_cat)
        addc = QPushButton("Add")
        addc.clicked.connect(self.add_category)
        h.addWidget(addc)
        delc = QPushButton("Remove Selected")
        delc.clicked.connect(self.remove_category)
        h.addWidget(delc)
        v.addLayout(h)
        tab.setLayout(v)
        return tab

    def build_reports_tab(self):
        tab = QWidget()
        v = QVBoxLayout()
        # Export CSV/PDF
        h = QHBoxLayout()
        export_csv_btn = QPushButton("Export CSV (all)")
        export_csv_btn.clicked.connect(self.export_csv_all)
        h.addWidget(export_csv_btn)
        export_pdf_btn = QPushButton("Export PDF Report (month)")
        export_pdf_btn.clicked.connect(self.export_pdf_month)
        h.addWidget(export_pdf_btn)
        v.addLayout(h)

        # Chart options
        chart_row = QHBoxLayout()
        chart_row.addWidget(QLabel("Chart:"))
        self.chart_type = QComboBox()
        self.chart_type.addItems(["monthly_trend","category_pie"])
        chart_row.addWidget(self.chart_type)
        draw_btn = QPushButton("Draw Chart")
        draw_btn.clicked.connect(self.draw_chart)
        chart_row.addWidget(draw_btn)
        v.addLayout(chart_row)

        tab.setLayout(v)
        return tab

    def build_settings_tab(self):
        tab = QWidget()
        v = QVBoxLayout()
        # Google Sheets sync controls
        v.addWidget(QLabel("Cloud Sync (Google Sheets)"))
        self.gs_path_edit = QLineEdit()
        self.gs_path_edit.setPlaceholderText("Path to service account JSON (optional)")
        v.addWidget(self.gs_path_edit)
        self.gs_sheet_name = QLineEdit()
        self.gs_sheet_name.setPlaceholderText("Google Sheet name (optional)")
        v.addWidget(self.gs_sheet_name)
        sync_btn = QPushButton("Sync to Google Sheets (one-way)")
        sync_btn.clicked.connect(self.sync_to_google_sheets)
        v.addWidget(sync_btn)
        # Authentication note
        v.addWidget(QLabel("Authentication: local accounts created on first run."))
        tab.setLayout(v)
        return tab

    # ---------------------------
    # Data operations
    # ---------------------------
    def refresh_categories(self):
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("SELECT name FROM categories WHERE user_id=? ORDER BY name", (self.user_id,))
        rows = [r["name"] for r in cur.fetchall()]
        if not rows:
            # seed defaults if none
            for cat in DEFAULT_CATEGORIES:
                cur.execute("INSERT OR IGNORE INTO categories (user_id, name) VALUES (?, ?)", (self.user_id, cat))
            con.commit()
            cur.execute("SELECT name FROM categories WHERE user_id=? ORDER BY name", (self.user_id,))
            rows = [r["name"] for r in cur.fetchall()]
        con.close()
        self.cat_combo.clear()
        self.category_list.clear()
        self.cat_combo.addItems(rows)
        self.category_list.addItems(rows)

    def add_category(self):
        name = self.new_cat.text().strip()
        if not name:
            QMessageBox.warning(self, "Category", "Enter a name")
            return
        con = get_db_connection()
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO categories (user_id, name) VALUES (?, ?)", (self.user_id, name))
            con.commit()
            self.new_cat.clear()
            self.refresh_categories()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Category", "Already exists")
        finally:
            con.close()

    def remove_category(self):
        name = self.category_list.currentText()
        if not name:
            return
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("DELETE FROM categories WHERE user_id=? AND name=?", (self.user_id, name))
        con.commit()
        con.close()
        self.refresh_categories()

    def add_transaction(self):
        d = self.date_edit.date().toPyDate()
        typ = self.type_combo.currentText()
        cat = self.cat_combo.currentText()
        amt_text = self.amount_edit.text().strip()
        desc = self.desc_edit.text().strip()
        try:
            amt = float(amt_text)
        except Exception:
            QMessageBox.warning(self, "Input", "Invalid amount")
            return
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO transactions (user_id, date, type, category, amount, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (self.user_id, d.isoformat(), typ, cat, amt, desc, datetime.utcnow().isoformat()))
        con.commit()
        con.close()
        self.amount_edit.clear()
        self.desc_edit.clear()
        self.refresh_transactions()
        self.update_dashboard()

    def refresh_transactions(self):
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC, id DESC", (self.user_id,))
        rows = cur.fetchall()
        con.close()
        self.tx_table.setRowCount(0)
        for r in rows:
            rowpos = self.tx_table.rowCount()
            self.tx_table.insertRow(rowpos)
            self.tx_table.setItem(rowpos, 0, QTableWidgetItem(str(r["id"])))
            self.tx_table.setItem(rowpos, 1, QTableWidgetItem(r["date"]))
            self.tx_table.setItem(rowpos, 2, QTableWidgetItem(r["type"]))
            self.tx_table.setItem(rowpos, 3, QTableWidgetItem(r["category"]))
            self.tx_table.setItem(rowpos, 4, QTableWidgetItem(f"{r['amount']:.2f}"))
            self.tx_table.setItem(rowpos, 5, QTableWidgetItem(r["description"] or ""))

    def delete_transaction(self):
        sel = self.tx_table.currentRow()
        if sel < 0:
            QMessageBox.warning(self, "Delete", "Select a transaction")
            return
        txid = int(self.tx_table.item(sel, 0).text())
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (txid, self.user_id))
        con.commit()
        con.close()
        self.refresh_transactions()
        self.update_dashboard()

    # ---------------------------
    # Dashboard summary & charts
    # ---------------------------
    def update_dashboard(self):
        # compute monthly and weekly totals and balance
        today = date.today()
        first_of_month = today.replace(day=1)
        week_start = today - timedelta(days=today.weekday())  # Monday

        con = get_db_connection()
        cur = con.cursor()
        cur.execute("""
            SELECT type, SUM(amount) as s FROM transactions
            WHERE user_id=? AND date BETWEEN ? AND ?
            GROUP BY type
        """, (self.user_id, first_of_month.isoformat(), today.isoformat()))
        month_sums = {r["type"]: r["s"] or 0 for r in cur.fetchall()}

        cur.execute("""
            SELECT type, SUM(amount) as s FROM transactions
            WHERE user_id=? AND date BETWEEN ? AND ?
            GROUP BY type
        """, (self.user_id, week_start.isoformat(), today.isoformat()))
        week_sums = {r["type"]: r["s"] or 0 for r in cur.fetchall()}

        # totals
        month_income = month_sums.get("income", 0.0)
        month_expense = month_sums.get("expense", 0.0)
        week_income = week_sums.get("income", 0.0)
        week_expense = week_sums.get("expense", 0.0)

        balance = (month_income - month_expense)
        self.lbl_month.setText(f"Month total: ₱{month_expense:.2f} expenses / ₱{month_income:.2f} income")
        self.lbl_week.setText(f"Week total: ₱{week_expense:.2f} expenses / ₱{week_income:.2f} income")
        self.lbl_balance.setText(f"Balance (month): ₱{balance:.2f}")

        # draw monthly trend chart last 30 days
        self.draw_chart(default="monthly_trend")

    def draw_chart(self, default=None):
        ctype = self.chart_type.currentText() if hasattr(self, "chart_type") else default
        if ctype is None:
            ctype = "monthly_trend"
        # fetch last 30 days
        today = date.today()
        start = today - timedelta(days=29)
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("""
            SELECT date, type, SUM(amount) as s FROM transactions
            WHERE user_id=? AND date BETWEEN ? AND ?
            GROUP BY date, type
        """, (self.user_id, start.isoformat(), today.isoformat()))
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=rows[0].keys()) if rows else pd.DataFrame(columns=["date","type","s"])
        if df.empty:
            self.canvas.axes.clear()
            self.canvas.axes.text(0.5,0.5,"No data", ha='center')
            self.canvas.draw()
            return

        df['date'] = pd.to_datetime(df['date'])
        pivot = df.pivot_table(index='date', columns='type', values='s', aggfunc='sum').fillna(0)
        if ctype == "monthly_trend":
            self.canvas.axes.clear()
            pivot.plot(ax=self.canvas.axes)
            self.canvas.axes.set_title("Daily Income/Expense (last 30 days)")
            self.canvas.draw()
        elif ctype == "category_pie":
            # last 30 days category totals
            cur.execute("""
                SELECT category, SUM(amount) as s FROM transactions
                WHERE user_id=? AND date BETWEEN ? AND ? AND type='expense'
                GROUP BY category
            """, (self.user_id, start.isoformat(), today.isoformat()))
            cats = cur.fetchall()
            if not cats:
                self.canvas.axes.clear()
                self.canvas.axes.text(0.5,0.5,"No expense data", ha='center')
                self.canvas.draw()
                return
            labels = [r["category"] for r in cats]
            sizes = [r["s"] for r in cats]
            self.canvas.axes.clear()
            self.canvas.axes.pie(sizes, labels=labels, autopct='%1.1f%%')
            self.canvas.axes.set_title("Expense by Category (30 days)")
            self.canvas.draw()

    # ---------------------------
    # Export & reporting
    # ---------------------------
    def export_csv_all(self):
        con = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM transactions WHERE user_id=? ORDER BY date desc", con, params=(self.user_id,))
        con.close()
        if df.empty:
            QMessageBox.information(self, "Export", "No data to export")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if not save_path:
            return
        df.to_csv(save_path, index=False)
        QMessageBox.information(self, "Export", f"Exported {len(df)} rows to {save_path}")

    def export_pdf_month(self):
        if not REPORTLAB_AVAILABLE:
            QMessageBox.warning(self, "PDF", "reportlab not installed. Install reportlab to enable PDF report.")
            return
        today = date.today()
        first = today.replace(day=1)
        con = get_db_connection()
        df = pd.read_sql_query("""
            SELECT date, type, category, amount, description FROM transactions
            WHERE user_id=? AND date BETWEEN ? AND ? ORDER BY date
        """, con, params=(self.user_id, first.isoformat(), today.isoformat()))
        con.close()
        if df.empty:
            QMessageBox.information(self, "PDF", "No data for current month")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Save PDF report", "", "PDF Files (*.pdf)")
        if not save_path:
            return
        # generate a basic PDF
        c = canvas.Canvas(save_path, pagesize=letter)
        width, height = letter
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, height - 50, f"Expense Report for {first.strftime('%B %Y')}")
        c.setFont("Helvetica", 10)
        y = height - 80
        for idx, row in df.iterrows():
            line = f"{row['date']} | {row['type']} | {row['category']} | ₱{row['amount']:.2f} | {row['description']}"
            c.drawString(40, y, line[:120])
            y -= 14
            if y < 80:
                c.showPage()
                y = height - 50
        c.save()
        QMessageBox.information(self, "PDF", f"Saved PDF: {save_path}")

    # ---------------------------
    # Google Sheets sync (optional)
    # ---------------------------
    def sync_to_google_sheets(self):
        if not GSHEETS_AVAILABLE:
            QMessageBox.warning(self, "Google Sheets", "gspread/oauth2client not installed.")
            return
        creds_path = self.gs_path_edit.text().strip()
        sheet_name = self.gs_sheet_name.text().strip()
        if not creds_path or not sheet_name:
            QMessageBox.warning(self, "Google Sheets", "Provide credentials path and sheet name.")
            return
        # create dataframe
        con = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM transactions WHERE user_id=? ORDER BY date", con, params=(self.user_id,))
        con.close()
        try:
            scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
            client = gspread.authorize(creds)
            try:
                sheet = client.open(sheet_name).sheet1
            except Exception:
                sheet = client.create(sheet_name).sheet1
            # clear and update
            sheet.clear()
            sheet.insert_row(list(df.columns), 1)
            for idx, row in df.iterrows():
                sheet.insert_row(list(row.astype(str).values), idx+2)
            QMessageBox.information(self, "Google Sheets", "Synced to sheet.")
        except Exception as e:
            QMessageBox.critical(self, "Google Sheets", f"Sync failed: {e}")

    # ---------------------------
    # OCR and text export
    # ---------------------------
    def save_first_page_text(self):
        # simple text extract using PyPDF2
        path = self.get_selected_transaction_file()
        QMessageBox.information(self, "Not Implemented", "This demo saves first page text via reader.extract_text(). Use advanced OCR if needed.")
        # left as exercise

    # ---------------------------
    # Helpers
    # ---------------------------
    def get_selected_transaction_file(self):
        # utility placeholder
        return None

    def toggle_theme(self):
        if self.is_dark:
            self.setStyleSheet(self.light_style)
            self.is_dark = False
        else:
            self.setStyleSheet(self.dark_style)
            self.is_dark = True

# ---------------------------
# Entry point
# ---------------------------
def main():
    app = QApplication(sys.argv)

    # Login dialog
    login = LoginDialog()
    if login.exec_() != QDialog.Accepted:
        print("Login cancelled")
        return
    user_id = login.user_id
    # Launch main app
    window = ExpenseTrackerApp(user_id)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
