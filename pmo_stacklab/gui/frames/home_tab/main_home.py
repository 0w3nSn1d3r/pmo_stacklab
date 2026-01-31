from tkinter import ttk, filedialog
import tkinter as tk


class HomeFrame(ttk.Frame):
    def __init__(self, root):
        super().__init__(root)
        mainframe = ttk.Frame(root)

        intro = tk.Text(mainframe, width=100, height=150)
        intro.insert('HOW TO USE PMO STACKLAB HERE')

        intro.pack()
