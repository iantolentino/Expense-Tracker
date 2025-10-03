# charts.py
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import pandas as pd
from datetime import date, timedelta

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=6, height=3, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)

def plot_monthly_trend(canvas, rows):
    # rows: iterable of dicts with keys date, type, s
    if not rows:
        canvas.axes.clear()
        canvas.axes.text(0.5, 0.5, "No data", ha='center')
        canvas.draw()
        return
    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    pivot = df.pivot_table(index='date', columns='type', values='s', aggfunc='sum').fillna(0)
    canvas.axes.clear()
    pivot.plot(ax=canvas.axes)
    canvas.axes.set_title("Daily Income/Expense (last 30 days)")
    canvas.draw()

def plot_category_pie(canvas, cat_rows):
    # cat_rows: list of dict-like with category and s
    if not cat_rows:
        canvas.axes.clear()
        canvas.axes.text(0.5, 0.5, "No expense data", ha='center')
        canvas.draw()
        return
    labels = [r['category'] for r in cat_rows]
    sizes = [r['s'] for r in cat_rows]
    canvas.axes.clear()
    canvas.axes.pie(sizes, labels=labels, autopct='%1.1f%%')
    canvas.axes.set_title("Expense by Category (30 days)")
    canvas.draw()
