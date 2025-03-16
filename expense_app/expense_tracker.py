import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import sqlite3  # Import sqlite3 for database operations
from tkcalendar import DateEntry  # Import DateEntry from tkcalendar

# fix the design
# Initialize main tkinter window
root = tk.Tk()
root.title("Expense Tracker with Balance")

# Center the window
def center_window(width, height):
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

center_window(600, 600)

# Create or connect to the database
conn = sqlite3.connect('finance_tracker.db')
c = conn.cursor()

# Create tables for expenses and income
c.execute('''
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY,
    date TEXT,
    category TEXT,
    amount REAL,
    description TEXT
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY,
    date TEXT,
    source TEXT,
    amount REAL
)
''')

conn.commit()

# Function to calculate and display balance
def calculate_balance():
    c.execute("SELECT SUM(amount) FROM income")
    total_income = c.fetchone()[0] or 0  # Get total income, default to 0 if None
    c.execute("SELECT SUM(amount) FROM expenses")
    total_expenses = c.fetchone()[0] or 0  # Get total expenses, default to 0 if None
    balance = total_income - total_expenses
    balance_label.config(text=f"Remaining Balance: P{balance:.2f}")

# Function to add an expense
def add_expense():
    date = date_entry.get_date()
    category = category_entry.get()
    amount = amount_entry.get()
    description = description_entry.get()

    if not date or not category or not amount:
        messagebox.showwarning("Input Error", "Please fill in all fields!")
        return

    c.execute("INSERT INTO expenses (date, category, amount, description) VALUES (?, ?, ?, ?)",
              (date, category, float(amount), description))
    conn.commit()
    view_expenses()
    calculate_balance()  # Update balance after adding expense

# Function to view expenses
def view_expenses():
    expense_listbox.delete(0, tk.END)  # Clear the listbox
    c.execute("SELECT * FROM expenses")
    for row in c.fetchall():
        expense_listbox.insert(tk.END, row)

# Function to delete an expense
def delete_expense():
    selected_item = expense_listbox.curselection()
    if not selected_item:
        messagebox.showwarning("Selection Error", "No expense selected!")
        return
    expense_id = expense_listbox.get(selected_item)[0]
    c.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    view_expenses()
    calculate_balance()  # Update balance after deleting expense

# Function to add income
def add_income():
    date = income_date_entry.get_date()
    source = income_source_entry.get()
    amount = income_amount_entry.get()

    if not date or not source or not amount:
        messagebox.showwarning("Input Error", "Please fill in all fields!")
        return

    c.execute("INSERT INTO income (date, source, amount) VALUES (?, ?, ?)",
              (date, source, float(amount)))
    conn.commit()
    view_income()
    calculate_balance()  # Update balance after adding income

# Function to view income
def view_income():
    income_listbox.delete(0, tk.END)  # Clear the listbox
    c.execute("SELECT * FROM income")
    for row in c.fetchall():
        income_listbox.insert(tk.END, row)

# Function to delete income
def delete_income():
    selected_item = income_listbox.curselection()
    if not selected_item:
        messagebox.showwarning("Selection Error", "No income selected!")
        return
    income_id = income_listbox.get(selected_item)[0]
    c.execute("DELETE FROM income WHERE id=?", (income_id,))
    conn.commit()
    view_income()
    calculate_balance()  # Update balance after deleting income

# Input fields for expenses
tk.Label(root, text="Date:").grid(row=0, column=0)
date_entry = DateEntry(root, width=12, background='darkblue', foreground=' white', borderwidth=2)
date_entry.grid(row=0, column=1)

tk.Label(root, text="Category:").grid(row=1, column=0)
category_entry = tk.Entry(root)
category_entry.grid(row=1, column=1)

tk.Label(root, text="Amount:").grid(row=2, column=0)
amount_entry = tk.Entry(root)
amount_entry.grid(row=2, column=1)

tk.Label(root, text="Description:").grid(row=3, column=0)
description_entry = tk.Entry(root)
description_entry.grid(row=3, column=1)

# Buttons for expense management
tk.Button(root, text="Add Expense", command=add_expense).grid(row=4, column=0)
tk.Button(root, text="Delete Expense", command=delete_expense).grid(row=4, column=1)

# Listbox to display expenses
expense_listbox = tk.Listbox(root, width=50)
expense_listbox.grid(row=5, column=0, columnspan=2)

# Label for expenses
tk.Label(root, text="Expenses:").grid(row=5, column=2)

# Input fields for income
tk.Label(root, text="Income Date:").grid(row=6, column=0)
income_date_entry = DateEntry(root, width=12, background='darkblue', foreground='white', borderwidth=2)
income_date_entry.grid(row=6, column=1)

tk.Label(root, text="Source:").grid(row=7, column=0)
income_source_entry = tk.Entry(root)
income_source_entry.grid(row=7, column=1)

tk.Label(root, text="Income Amount:").grid(row=8, column=0)
income_amount_entry = tk.Entry(root)
income_amount_entry.grid(row=8, column=1)

# Buttons for income management
tk.Button(root, text="Add Income", command=add_income).grid(row=9, column=0)
tk.Button(root, text="Delete Income", command=delete_income).grid(row=9, column=1)

# Listbox to display income
income_listbox = tk.Listbox(root, width=50)
income_listbox.grid(row=10, column=0, columnspan=2)

# Label for income
tk.Label(root, text="Income:").grid(row=10, column=2)

# Label to display balance
balance_label = tk.Label(root, text="Remaining Balance: $0.00", font=("Helvetica", 12))
balance_label.grid(row=11, column=0, columnspan=2)

# View existing expenses and income
view_expenses()
view_income()
calculate_balance()  # Initial balance calculation

# Run the application
root.mainloop()

# Close the database connection
conn.close()