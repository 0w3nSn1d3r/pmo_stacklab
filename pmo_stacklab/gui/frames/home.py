from tkinter import ttk, filedialog
import tkinter as tk


class UploadFrame(ttk.Frame):
    def __init__(self, root):
        super().__init__(root)

        mainframe = ttk.Frame(root)
        buttonframe = ttk.Frame(mainframe)

        filter_count = tk.StringVar()
        select_filtercount = ttk.Spinbox(
            buttonframe, from_=1, to=5, textvariable=filter_count)

        uploadfilters_button = ttk.Button(
            buttonframe, text='Upload Filter Folders', command=lambda: self.upload_filters(filter_count))

    def upload_filters(self, filter_count):
        # Prompt upload for each filter
        for i in range(filter_count):
            folder_var = tk.StringVar()
            filter_folder = filedialog.askdirectory(
                title=f'({i}) Select Folder Containing Image Files of Same Filter (.FITS)'
            )


class CalibrateFrame(ttk.Frame):
    def __init__(self, root):
        super().__init__(root)

        mainframe = ttk.Frame(root)


class StackFrame(ttk.Frame):
    def __init__(self, root):
        super().__init__(root)

        mainframe = ttk.Frame(root)
