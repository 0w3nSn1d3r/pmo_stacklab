from tkinter import ttk, filedialog
import tkinter as tk
import gui.frames as frames


class HomeWindow:
    def __init__(self, root):
        root.title('UO | PMO StackLab')

        # One phase of processing per tab for clarity
        tabs = ttk.Notebook(root)

        upload_tab = frames.UploadFrame(root)
        calibrate_tab = frames.CalibrateFrame(root)
        stack_tab = frames.StackFrame(root)
        postprocess_tab = frames.PostProcessFrame(root)

        tabs.add(upload_tab, text='Upload')
        tabs.add(calibrate_tab, text='Calibrate')
        tabs.add(stack_tab, text='Stack')
        tabs.add(postprocess_tab, text='Post Process')

        # Home frame for introduction to StackLab
        home_frame = frames.HomeFrame(root)
        home_frame.pack()
