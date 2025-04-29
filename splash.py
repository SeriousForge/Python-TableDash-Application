# splash.py
import tkinter as tk
from PIL import Image, ImageTk

class SplashScreen(tk.Toplevel):
    def __init__(self, master, logo_path, duration, callback):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(bg='#E23724')
        self.logo_path = logo_path
        self.img = Image.open(self.logo_path).convert('RGBA')
        self.tk_img = None
        self.label = tk.Label(self, bg='#E23724')
        self.label.pack(expand=True, fill='both', padx=40, pady=40)
        self.attributes('-topmost', True)
        self.fade_in(0)
        self.callback = callback
        self.duration = duration
        self.after(0, self.center_window)

    def fade_in(self, alpha):
        if alpha > 255:
            self.after(self.duration, self.callback)
            return
        faded = self.img.copy()
        faded.putalpha(alpha)
        self.tk_img = ImageTk.PhotoImage(faded)
        self.label.configure(image=self.tk_img)
        self.after(30, self.fade_in, alpha + 15)

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')