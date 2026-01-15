from tkinter import ttk, filedialog
import tkinter as tk
from frames.home import UploadFrame, CalibrateFrame, StackFrame


class HomeWindow:
    def __init__(self, root):
        root.title('PMO StackLab | Home')

        # One phase of processing per tab for clarity
        tabs = ttk.Notebook(root)

        uploadtab = UploadFrame(root)
        calibratetab = CalibrateFrame(root)
        stacktab = StackFrame(root)

        tabs.add(uploadtab, text='Upload')
        tabs.add(calibratetab, text='Calibrate')
        tabs.add(stacktab, text='Stack')
