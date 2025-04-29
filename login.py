# login.py
import tkinter as tk
from tkinter import messagebox

class SignInPage(tk.Frame):
    def __init__(self, master, login_callback=None):
        super().__init__(master)
        self.master = master
        self.login_callback = login_callback
        self.pack()
        tk.Label(self, text="Email:").pack()
        self.email_entry = tk.Entry(self)
        self.email_entry.pack()
        tk.Label(self, text="Password:").pack()
        self.password_entry = tk.Entry(self, show='*')
        self.password_entry.pack()
        tk.Button(self, text="Sign In", command=self.attempt_login).pack(pady=10)

    def attempt_login(self):
        email = self.email_entry.get()
        password = self.password_entry.get()
        # The login logic is external for flexibility—use the callback if provided
        if self.login_callback and self.login_callback(email, password):
            messagebox.showinfo("Success", "Login Successful!")
            # Continue to main application here or call another callback
        else:
            messagebox.showerror("Failed", "Invalid credentials!")