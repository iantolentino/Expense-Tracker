# Expense Tracker with Balance

## Overview
This Expense Tracker application allows users to manage their expenses and income efficiently. It provides a user-friendly interface to add, view, and delete financial records while calculating the remaining balance.

## Features
- **Add and Delete Expenses**: Track your spending by adding and removing expenses.
- **Add and Delete Income**: Record your income sources and amounts.
- **Balance Calculation**: Automatically calculates and displays the remaining balance based on total income and expenses.
- **Database Storage**: Utilizes SQLite for persistent storage of expenses and income records.

## Requirements
- Python 3.x
- Tkinter (included with Python)
- `tkcalendar` library (install via pip: `pip install tkcalendar`)
- SQLite (included with Python)

## Getting Started
1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install Dependencies**:
   ```bash
   pip install tkcalendar
   ```

3. **Run the Application**:
   ```bash
   python expense_tracker.py
   ```

## Usage
- **Add Expense**: Fill in the date, category, amount, and description, then click "Add Expense".
- **Delete Expense**: Select an expense from the list and click "Delete Expense".
- **Add Income**: Fill in the income date, source, and amount, then click "Add Income".
- **Delete Income**: Select an income entry from the list and click "Delete Income".
- **View Balance**: The remaining balance is displayed at the bottom of the window.

## License
This project is licensed under the MIT License. See the LICENSE file for details.

## Acknowledgments
- This application uses the Tkinter library for the GUI and SQLite for database management.
