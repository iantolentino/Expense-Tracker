import pandas as pd
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from datetime import date
import sqlite3
import os

# Optional reportlab for PDF
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

APP_DB = os.path.join(os.path.dirname(__file__), "expenses.db")

def get_db_connection():
    con = sqlite3.connect(APP_DB)
    con.row_factory = sqlite3.Row
    return con


# ---------------------------
# Export CSV (all transactions)
# ---------------------------
def export_transactions_csv(user_id, parent=None):
    con = get_db_connection()
    df = pd.read_sql_query(
        "SELECT * FROM transactions WHERE user_id=? ORDER BY date desc",
        con,
        params=(user_id,),
    )
    con.close()

    if df.empty:
        QMessageBox.information(parent, "Export", "No data to export")
        return

    save_path, _ = QFileDialog.getSaveFileName(parent, "Save CSV", "", "CSV Files (*.csv)")
    if not save_path:
        return

    df.to_csv(save_path, index=False)
    QMessageBox.information(parent, "Export", f"Exported {len(df)} rows to {save_path}")


# ---------------------------
# Export PDF (current month report)
# ---------------------------
def export_pdf_month(user_id, parent=None):
    if not REPORTLAB_AVAILABLE:
        QMessageBox.warning(parent, "PDF", "reportlab not installed. Install it to enable PDF reports.")
        return

    today = date.today()
    first = today.replace(day=1)

    con = get_db_connection()
    df = pd.read_sql_query(
        """
        SELECT date, type, category, amount, description FROM transactions
        WHERE user_id=? AND date BETWEEN ? AND ? ORDER BY date
        """,
        con,
        params=(user_id, first.isoformat(), today.isoformat()),
    )
    con.close()

    if df.empty:
        QMessageBox.information(parent, "PDF", "No data for current month")
        return

    save_path, _ = QFileDialog.getSaveFileName(parent, "Save PDF report", "", "PDF Files (*.pdf)")
    if not save_path:
        return

    c = canvas.Canvas(save_path, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 50, f"Expense Report for {first.strftime('%B %Y')}")
    c.setFont("Helvetica", 10)

    y = height - 80
    for _, row in df.iterrows():
        line = f"{row['date']} | {row['type']} | {row['category']} | ₱{row['amount']:.2f} | {row['description']}"
        c.drawString(40, y, line[:120])  # truncate long text
        y -= 14
        if y < 80:
            c.showPage()
            y = height - 50

    c.save()
    QMessageBox.information(parent, "PDF", f"Saved PDF: {save_path}")
