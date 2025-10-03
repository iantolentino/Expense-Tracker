# main_ui.py (with sidebar navigation)
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QDateEdit, QComboBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QApplication,
    QMessageBox, QStyle, QListWidget, QListWidgetItem, QStackedWidget
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont
from datetime import date, timedelta
import pandas as pd

from db import (add_transaction, list_transactions, delete_transaction,
                get_categories, add_category, remove_category, get_summary, get_db_connection)
from charts import MplCanvas, plot_monthly_trend, plot_category_pie
from export_utils import export_transactions_csv, export_pdf_month


class ExpenseTrackerApp(QWidget):
    def __init__(self, user_id: int, username: str = ""):
        super().__init__()
        self.user_id = user_id
        self.username = username
        self.setWindowTitle(f"Expense Tracker — {username or ('User ' + str(user_id))}")
        self.resize(1200, 700)
        self.setFont(QFont("Segoe UI", 10))

        # Themes
        self.is_dark = False
        self.light_style = """
            QWidget { font-family: 'Segoe UI'; font-size: 11pt; }
            QListWidget {
                background-color: #2C3E50; color: #ecf0f1;
                border: none;
            }
            QListWidget::item {
                padding: 12px;
            }
            QListWidget::item:selected {
                background: #34495E; font-weight: bold;
            }
        """
        self.dark_style = """
            QWidget { background: #121212; color: #eee; font-family: 'Segoe UI'; font-size: 11pt; }
            QListWidget {
                background-color: #1E1E1E; color: #ccc;
                border: none;
            }
            QListWidget::item {
                padding: 12px;
            }
            QListWidget::item:selected {
                background: #333; color: #fff; font-weight: bold;
            }
        """
        self.setStyleSheet(self.light_style)

        # Main layout (sidebar + content)
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(180)
        self.sidebar.setFont(QFont("Segoe UI", 10))
        self.sidebar.addItem(QListWidgetItem("📊 Dashboard"))
        self.sidebar.addItem(QListWidgetItem("💰 Transactions"))
        self.sidebar.addItem(QListWidgetItem("🏷 Categories"))
        self.sidebar.addItem(QListWidgetItem("📑 Reports"))
        self.sidebar.addItem(QListWidgetItem("⚙ Settings"))
        self.sidebar.currentRowChanged.connect(self.switch_page)
        main_layout.addWidget(self.sidebar)

        # Top bar
        right_panel = QVBoxLayout()
        top_row = QHBoxLayout()
        self.lbl_user = QLabel(f"User: {self.username or user_id}")
        self.lbl_user.setStyleSheet("font-weight: bold; font-size: 12pt;")
        top_row.addWidget(self.lbl_user)
        top_row.addStretch()
        self.theme_btn = QPushButton("🌙 Theme")
        self.theme_btn.clicked.connect(self.toggle_theme)
        top_row.addWidget(self.theme_btn)
        right_panel.addLayout(top_row)

        # Stacked pages
        self.pages = QStackedWidget()
        self.page_dashboard = self.build_dashboard_page()
        self.page_transactions = self.build_transactions_page()
        self.page_categories = self.build_categories_page()
        self.page_reports = self.build_reports_page()
        self.page_settings = self.build_settings_page()

        self.pages.addWidget(self.page_dashboard)
        self.pages.addWidget(self.page_transactions)
        self.pages.addWidget(self.page_categories)
        self.pages.addWidget(self.page_reports)
        self.pages.addWidget(self.page_settings)

        right_panel.addWidget(self.pages)
        main_layout.addLayout(right_panel)

        # Default
        self.sidebar.setCurrentRow(0)
        self.refresh_categories()
        self.refresh_transactions()
        self.update_dashboard()

    # --- Sidebar navigation ---
    def switch_page(self, index):
        self.pages.setCurrentIndex(index)

    # --- Dashboard ---
    def build_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        summary_row = QHBoxLayout()
        self.lbl_month = QLabel("Month total: ₱0.00")
        self.lbl_week = QLabel("Week total: ₱0.00")
        self.lbl_balance = QLabel("Balance: ₱0.00")
        for lbl in (self.lbl_month, self.lbl_week, self.lbl_balance):
            lbl.setStyleSheet("font-weight:bold; font-size: 12pt; padding: 6px;")
            summary_row.addWidget(lbl)
        layout.addLayout(summary_row)
        self.canvas = MplCanvas(self, width=8, height=4, dpi=100)
        layout.addWidget(self.canvas)
        page.setLayout(layout)
        return page

    # --- Transactions ---
    def build_transactions_page(self):
        page = QWidget()
        g = QGridLayout()
        page.setLayout(g)

        # Left: input form
        formbox = QGroupBox("➕ Add Transaction")
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
        add_btn = QPushButton(self.style().standardIcon(QStyle.SP_DialogApplyButton), "Add")
        add_btn.clicked.connect(self.add_transaction)
        form.addWidget(add_btn, 5, 0, 1, 2)
        formbox.setLayout(form)
        g.addWidget(formbox, 0, 0)

        # Right: transactions table
        right_box = QGroupBox("📋 Transactions")
        rlay = QVBoxLayout()

        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search transactions...")
        self.search_bar.textChanged.connect(self.filter_transactions)
        rlay.addWidget(self.search_bar)

        self.tx_table = QTableWidget(0, 6)
        self.tx_table.setHorizontalHeaderLabels(["ID","Date","Type","Category","Amount","Description"])
        self.tx_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        rlay.addWidget(self.tx_table)

        btn_row = QHBoxLayout()
        del_btn = QPushButton(self.style().standardIcon(QStyle.SP_TrashIcon), "Delete")
        del_btn.clicked.connect(self.delete_transaction)
        btn_row.addWidget(del_btn)
        refresh_btn = QPushButton(self.style().standardIcon(QStyle.SP_BrowserReload), "Refresh")
        refresh_btn.clicked.connect(self.refresh_transactions)
        btn_row.addWidget(refresh_btn)
        rlay.addLayout(btn_row)
        right_box.setLayout(rlay)
        g.addWidget(right_box, 0, 1)
        return page

    # --- Categories ---
    def build_categories_page(self):
        page = QWidget()
        v = QVBoxLayout()
        self.category_list = QComboBox()
        v.addWidget(QLabel("Categories"))
        v.addWidget(self.category_list)
        h = QHBoxLayout()
        self.new_cat = QLineEdit()
        self.new_cat.setPlaceholderText("➕ New category")
        h.addWidget(self.new_cat)
        addc = QPushButton("Add")
        addc.clicked.connect(self.add_category)
        h.addWidget(addc)
        delc = QPushButton("Remove")
        delc.clicked.connect(self.remove_category)
        h.addWidget(delc)
        v.addLayout(h)
        page.setLayout(v)
        return page

    # --- Reports ---
    def build_reports_page(self):
        page = QWidget()
        v = QVBoxLayout()
        h = QHBoxLayout()
        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.clicked.connect(self.export_csv_all)
        h.addWidget(export_csv_btn)
        export_pdf_btn = QPushButton("Export PDF (month)")
        export_pdf_btn.clicked.connect(self.export_pdf_month)
        h.addWidget(export_pdf_btn)
        v.addLayout(h)
        chart_row = QHBoxLayout()
        chart_row.addWidget(QLabel("Chart:"))
        self.chart_type = QComboBox()
        self.chart_type.addItems(["monthly_trend","category_pie"])
        chart_row.addWidget(self.chart_type)
        draw_btn = QPushButton("Draw Chart")
        draw_btn.clicked.connect(self.draw_chart)
        chart_row.addWidget(draw_btn)
        v.addLayout(chart_row)
        page.setLayout(v)
        return page

    # --- Settings ---
    def build_settings_page(self):
        page = QWidget()
        v = QVBoxLayout()
        v.addWidget(QLabel("Cloud Sync (Google Sheets) — optional"))
        self.gs_path_edit = QLineEdit()
        self.gs_path_edit.setPlaceholderText("Path to service account JSON")
        v.addWidget(self.gs_path_edit)
        self.gs_sheet_name = QLineEdit()
        self.gs_sheet_name.setPlaceholderText("Google Sheet name")
        v.addWidget(self.gs_sheet_name)
        sync_btn = QPushButton("Sync to Google Sheets")
        sync_btn.clicked.connect(self.sync_to_google_sheets)
        v.addWidget(sync_btn)
        v.addWidget(QLabel("Authentication: local accounts only."))
        page.setLayout(v)
        return page

    # --- CRUD / Data ---
    def refresh_categories(self):
        cats = get_categories(self.user_id)
        self.cat_combo.clear()
        self.category_list.clear()
        self.cat_combo.addItems(cats)
        self.category_list.addItems(cats)

    def add_category(self):
        name = self.new_cat.text().strip()
        if not name:
            QMessageBox.warning(self, "Category", "Enter a name")
            return
        ok = add_category(self.user_id, name)
        if not ok:
            QMessageBox.warning(self, "Category", "Already exists")
        self.new_cat.clear()
        self.refresh_categories()

    def remove_category(self):
        name = self.category_list.currentText()
        if not name:
            return
        remove_category(self.user_id, name)
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
        add_transaction(self.user_id, d.isoformat(), typ, cat, amt, desc)
        self.amount_edit.clear()
        self.desc_edit.clear()
        self.refresh_transactions()
        self.update_dashboard()

    def refresh_transactions(self):
        rows = list_transactions(self.user_id)
        self.all_rows = rows
        self.populate_table(rows)

    def filter_transactions(self, text):
        if not hasattr(self, "all_rows"):
            return
        text = text.lower()
        filtered = [r for r in self.all_rows if text in str(r).lower()]
        self.populate_table(filtered)

    def populate_table(self, rows):
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
        delete_transaction(self.user_id, txid)
        self.refresh_transactions()
        self.update_dashboard()

    # --- Dashboard & charts ---
    def update_dashboard(self):
        today = date.today()
        first_of_month = today.replace(day=1)
        week_start = today - timedelta(days=today.weekday())
        month_sums = get_summary(self.user_id, first_of_month.isoformat(), today.isoformat())
        week_sums = get_summary(self.user_id, week_start.isoformat(), today.isoformat())
        month_income = month_sums.get("income", 0.0)
        month_expense = month_sums.get("expense", 0.0)
        week_income = week_sums.get("income", 0.0)
        week_expense = week_sums.get("expense", 0.0)
        balance = (month_income - month_expense)
        self.lbl_month.setText(f"Month: ₱{month_expense:.2f} spent / ₱{month_income:.2f} income")
        self.lbl_week.setText(f"Week: ₱{week_expense:.2f} spent / ₱{week_income:.2f} income")
        self.lbl_balance.setText(f"Balance: ₱{balance:.2f}")
        self.draw_chart(default="monthly_trend")

    def draw_chart(self, default=None):
        ctype = self.chart_type.currentText() if hasattr(self, "chart_type") else default
        if ctype is None:
            ctype = "monthly_trend"
        today = date.today()
        start = today - timedelta(days=29)
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("""
            SELECT date, type, SUM(amount) as s FROM transactions
            WHERE user_id=? AND date BETWEEN ? AND ?
            GROUP BY date, type
        """, (self.user_id, start.isoformat(), today.isoformat()))
        rows = [dict(r) for r in cur.fetchall()]
        if ctype == "monthly_trend":
            plot_monthly_trend(self.canvas, rows)
        elif ctype == "category_pie":
            cur.execute("""
                SELECT category, SUM(amount) as s FROM transactions
                WHERE user_id=? AND date BETWEEN ? AND ? AND type='expense'
                GROUP BY category
            """, (self.user_id, start.isoformat(), today.isoformat()))
            cats = [dict(r) for r in cur.fetchall()]
            plot_category_pie(self.canvas, cats)
        con.close()

    # --- Export ---
    def export_csv_all(self):
        export_transactions_csv(self.user_id, self)

    def export_pdf_month(self):
        export_pdf_month(self.user_id, self)

    # --- Settings ---
    def sync_to_google_sheets(self): 
        QMessageBox.information(self, "Google Sheets", "Sync optional. Requires gspread & oauth2client + JSON key.")

    def toggle_theme(self):
        if self.is_dark:
            self.setStyleSheet(self.light_style)
            self.is_dark = False
        else:
            self.setStyleSheet(self.dark_style)
            self.is_dark = True


# Runner
def run_app(user_id: int, username: str = ""):
    app = QApplication(sys.argv)
    window = ExpenseTrackerApp(user_id, username)
    window.show()
    sys.exit(app.exec_())
