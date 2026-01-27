from tkinter import ttk, filedialog
import tkinter as tk
import frames.home as home


class HomeWindow:
    def __init__(self, root):
        root.title('UO | PMO StackLab')

        # One phase of processing per tab for clarity
        tabs = ttk.Notebook(root)

        upload_tab = home.UploadFrame(root)
        calibrate_tab = home.CalibrateFrame(root)
        stack_tab = home.StackFrame(root)
        postprocess_tab = home.PostProcessFrame(root)

        tabs.add(upload_tab, text='Upload')
        tabs.add(calibrate_tab, text='Calibrate')
        tabs.add(stack_tab, text='Stack')
        tabs.add(postprocess_tab, text='Post Process')

        # Home frame for introduction to StackLab
        home_frame = home.HomeFrame(root)
        home_frame.pack()
