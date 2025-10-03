# login.py
import sys
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel,
                             QLineEdit, QHBoxLayout, QPushButton, QMessageBox, QApplication)
from PyQt5.QtCore import Qt
from db import create_user, authenticate_user
import main_ui

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
        self.username_value = ""

    def login(self):
        u = self.username.text().strip()
        p = self.password.text().strip()
        if not u or not p:
            QMessageBox.warning(self, "Input", "Enter username and password")
            return
        uid = authenticate_user(u, p)
        if uid:
            self.user_id = uid
            self.username_value = u
            self.accept()
        else:
            QMessageBox.warning(self, "Login", "Invalid username or password")

    def register(self):
        u = self.username.text().strip()
        p = self.password.text().strip()
        if not u or not p:
            QMessageBox.warning(self, "Input", "Enter username and password")
            return
        uid = create_user(u, p)
        if uid:
            QMessageBox.information(self, "Register", "User created. You can now login.")
        else:
            QMessageBox.warning(self, "Register", "Username already exists.")

def main():
    app = QApplication(sys.argv)
    dlg = LoginDialog()
    if dlg.exec_() != QDialog.Accepted:
        print("Login cancelled")
        return
    user_id = dlg.user_id
    username = dlg.username_value
    # call main UI
    main_ui.run_app(user_id, username)

if __name__ == "__main__":
    main()
