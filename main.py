from __future__ import annotations
import os
import argparse
import time
import platform
import subprocess
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from functools import partial
from typing import cast, Callable, Any, get_args, Optional
import threading
import logging
from dotenv import load_dotenv
import youtube
import auto_adder
from colors import load_colors
colors = load_colors()

def is_valid_literal(val:str, literal_type:Any) -> bool:
    return val in get_args(literal_type)

class SubWindow:
    window:tk.Toplevel
    root:tk.Tk
    log_level:int
    log_visible:bool
    log_display:ScrolledText
    btn_width:int = 50
    padx = 5
    pady = 5

    def setup_logging(self) -> None:
        root_logger = logging.getLogger()
        self.log_level = logging.ERROR
        root_logger.setLevel(self.log_level)
        handler = TkinterLogHandler(app = self, log_level= self.log_level) #type:ignore
        root_logger.addHandler(handler)
        # Avoid adding duplicate handlers
        if not any(isinstance(h, TkinterLogHandler) for h in root_logger.handlers):
            root_logger.addHandler(handler)

    def on_close(self) -> None:
        self.window.destroy()
        self.root.destroy()

    def show_log_if_needed(self, levelno:int, msg:str) -> None:
        # Only show if severity is high enough and not already visible
        if not self.log_visible and levelno >= self.log_level:
            self.log_display.pack(padx=10, pady=10)
            self.log_visible = True

        # Append the log message
        self.log_display.insert(tk.END, msg + '\n')
        self.log_display.see(tk.END)

class TkinterLogHandler(logging.Handler):
    def __init__(self, app:SubWindow, log_level:int = logging.ERROR) -> None:
        super().__init__()
        self.app = app  # Reference to main app (which holds the widget)
        self.level_threshold = log_level

    def emit(self, record:logging.LogRecord) -> None:
        msg = self.format(record)
        self.app.log_display.after(0, self.app.show_log_if_needed, record.levelno, msg)

class ToolTip:
    def __init__(self, widget:Any, text:str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window:Optional[tk.Toplevel] = None

        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, _:Any = None) -> None:
        if self.tip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert") or (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 20

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # No window decorations
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw, text=self.text, justify='left',
            # background="#ffffe0", relief='solid', borderwidth=1,
            background=colors['yellow-1'], relief='solid', borderwidth=1,
            font=("tahoma", 8, "normal"),
            foreground=colors['fg']
        )
        label.pack(ipadx=4, ipady=2)

    def hide_tip(self, _:Any = None) -> None:
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

class ConfigureSpecificAutoAdd(SubWindow):
    def __init__(self, root:tk.Tk, filepath:str) -> None:
        self.root = root
        self.window = tk.Toplevel(self.root)
        tk_root_styles(self.window)
        self.window.protocol('WM_DELETE_WINDOW', self.on_close)
        self.window.title('Configure: Auto Adder')

        self.filepath = filepath
        self.old_cfg = auto_adder.read_settings(self.filepath)
        self.new_cfg = self.old_cfg.model_copy()

        label = ttk.Label(self.window, style = 'Warning.TLabel',
            text=f"Configuration page of {self.old_cfg.global_settings.name}",
            font=("TkDefaultFont", 12, "bold")
        )
        label.pack(padx = self.padx, pady= self.pady)


        label_width = 20
        #sec 1: global configs
        global_config_section = ttk.Frame(self.window, border=0)
        global_config_section.pack(fill = 'x')
        self.cfg_name = tk.StringVar(self.window, value= self.old_cfg.global_settings.name)
        ttk.Label(global_config_section, text= 'Display name', width= label_width).grid(
            row = 0, column= 0, padx = self.padx, pady = self.pady, sticky='w'
        )
        ttk.Entry(global_config_section, textvariable= self.cfg_name, width= self.btn_width).grid(
            row = 0, column= 1, padx = self.padx, pady = self.pady
        )

        self.cfg_target_id = tk.StringVar(self.window, value= self.old_cfg.global_settings.target_playlist_id)
        ttk.Label(global_config_section, text= 'Target Playlist', width= label_width).grid(
            row = 1, column= 0, padx = self.padx, pady = self.pady, sticky='w'
        )
        ttk.Entry(global_config_section, textvariable= self.cfg_target_id, width= self.btn_width).grid(
            row = 1, column= 1, padx = self.padx, pady = self.pady
        )

        options = ['all_videos', 'full_videos_only', 'livestreams_only', 'shorts_only']
        self.cfg_selector = tk.StringVar(global_config_section, value=self.old_cfg.global_settings.selector)
        ttk.Label(global_config_section, text= 'Video filter', width= label_width).grid(
            row = 2, column= 0, padx = self.padx, pady = self.pady, sticky='w'
        )
        option_menu = ttk.OptionMenu(
            global_config_section,
            self.cfg_selector,
            self.cfg_selector.get(),
            *options
        )
        option_menu['menu'].configure(**tk_styles(option_menu['menu']))
        option_menu.grid(row = 2, column= 1, sticky= 'ew', padx = self.padx, pady = self.pady)


        separator = ttk.Separator(self.window, orient='horizontal')
        separator.pack(fill='x', padx = self.padx, pady = self.pady)
        ttk.Label(self.window, text= 'Channels added here will only be saved once you press any of the "Save" buttons.').pack(padx= 5, pady=5)


        #sec 2: add new
        add_new_frame = ttk.Frame(self.window, border=0)
        add_new_frame.pack(fill= 'x')
        self.add_new_channel_id = tk.StringVar(self.window)
        ttk.Label(add_new_frame, text= 'Channel ID / URL', width= label_width).grid(
            row = 0, column= 0, padx = self.padx, pady = self.pady, sticky='w'
        )
        ttk.Entry(add_new_frame, textvariable= self.add_new_channel_id, width= self.btn_width).grid(
            row = 0, column= 1, padx = self.padx, pady = self.pady
        )

        self.add_new_channel_name = tk.StringVar(self.window)
        ttk.Label(add_new_frame, text= 'Channel name', width= label_width).grid(
            row = 1, column= 0, padx = self.padx, pady = self.pady, sticky='w'
        )
        ttk.Entry(add_new_frame, textvariable= self.add_new_channel_name, width= self.btn_width).grid(
            row = 1, column= 1, padx = self.padx, pady = self.pady
        )

        self.add_new_selector = tk.StringVar(add_new_frame, value=self.cfg_selector.get())
        ttk.Label(add_new_frame, text= 'Video filter', width= label_width).grid(row = 2, column= 0, padx = self.padx, pady = self.pady, sticky='w')
        option_menu = ttk.OptionMenu(
            add_new_frame,
            self.add_new_selector,
            self.add_new_selector.get(),
            *options
        )
        option_menu['menu'].configure(**tk_styles(option_menu['menu']))
        option_menu.grid(row = 2, column= 1, sticky= 'ew', padx = self.padx, pady = self.pady)

        radioframe = ttk.Frame(self.window)
        radioframe.pack()
        self.add_new_log_or_add_all = tk.StringVar(self.window)
        tmp = ttk.Radiobutton(
            radioframe,
            text= 'Add new videos', value = 'Add new videos',
            variable= self.add_new_log_or_add_all,
        )
        tmp.grid(row= 0, column= 0, padx= self.padx*2, pady= self.pady)
        ToolTip(tmp, 'This will only add future uploads of this channel to your playlist, but none of the already existing videos.')
        tmp2 = ttk.Radiobutton(
            radioframe,
            text= 'Add all videos', value= 'Add all videos',
            variable= self.add_new_log_or_add_all,
        )
        tmp2.grid(row= 0, column= 1, padx= self.padx*2, pady= self.pady)
        ToolTip(tmp2, 'This will add future uploads AND all existing videos to your playlist.')


        separator = ttk.Separator(self.window, orient='horizontal')
        separator.pack(fill='x', padx = self.padx, pady = self.pady)


        ttk.Button(self.window, text= 'Save & Open file', command= self.open_file, width= self.btn_width).pack(padx= self.padx, pady= self.pady)

        self.button_frame = ttk.Frame(self.window)
        self.button_frame.pack()
        self.add_new = ttk.Button(self.button_frame, text= 'Add new channel', command= self.add_new_element, width= self.btn_width)
        self.add_new.grid(row = 0, column= 0, columnspan= 2, padx = self.padx, pady = self.pady, sticky= 'ew')

        btn1 = ttk.Button(self.button_frame, style= 'Confirm.TButton', text= 'Save & Back', command= self.save_back)
        btn2 = ttk.Button(self.button_frame, style= 'Confirm.TButton', text= 'Save & Exit', command= self.save_exit)
        btn1.grid(row = 1, column = 0, padx = self.padx, pady = self.pady, sticky= 'ew')
        btn2.grid(row = 1, column = 1, padx = self.padx, pady = self.pady, sticky= 'ew')

    def open_file(self) -> None:
        if self._save():
            if platform.system() == 'Darwin':       # macOS
                subprocess.call(('open', self.filepath))
            elif platform.system() == 'Windows':    # Windows
                os.startfile(self.filepath)
            else:                                   # linux variants
                subprocess.call(('xdg-open', self.filepath))
            time.sleep(2)
            self.on_close()
    def add_new_element(self) -> None:
        self.add_new.config(style='TButton')
        channel_id = self.add_new_channel_id.get()
        channel_name = self.add_new_channel_name.get()
        new_log_or_add = self.add_new_log_or_add_all.get()
        selector = self.add_new_selector.get()

        if not all(x for x in (channel_name, channel_id, new_log_or_add)):
            messagebox.showerror('Error: Missing fields', 'You forgot to fill in all fields and select an option for all channel-specific settings!')
            return
        c = youtube.Channel(channel_id)
        if not c.verify():
            messagebox.showerror(
                'Error: Invalid Channel ID',
                'The Channel ID you entered could not be verified and is invalid. Please enter a valid Channel ID!'
            )
            return
        if c.id in self.old_cfg.channels.keys():
            messagebox.showerror(
                'Error: Entry exists',
                'The Channel ID you entered already exists in the data and therefore cannot be added again!'
            )
            return

        if not is_valid_literal(selector, auto_adder.ChannelUploadFilter): # some shit you need to do to make mypy happy
            raise TypeError('how did we get here?') # some shit you need to do to make mypy happy
        selector = cast(auto_adder.ChannelUploadFilter, selector)
        videolist = []
        if new_log_or_add == 'Add new videos':
            videolist = [x for x in c.list_uploads(
                size = int(os.getenv('keep_video_ids', '45')),
                full_videos_only= selector == 'full_videos_only',
                livestreams_only= selector == 'livestreams_only',
                shorts_only= selector == 'shorts_only'
            )]
        elif new_log_or_add == 'Add all videos':
            pass
        else:
            raise TypeError
        new_channel = auto_adder.SettingsChannels(
            channel_name = channel_name,
            seen_video_ids = videolist,
            settings = auto_adder.PerChannelSettings(
                selector = selector
            )
        )
        self.new_cfg.channels[c.id] = new_channel
        self.add_new_channel_id.set('')
        self.add_new_channel_name.set('')
        self.add_new_selector.set(self.cfg_selector.get())
        self.add_new_log_or_add_all.set('')
        self.add_new.config(style= 'Success.TButton')
        self.add_new.after(2000, lambda: self.add_new.config(style='TButton'))

    def _save(self) -> bool:
        channel_id = self.add_new_channel_id.get()
        channel_name = self.add_new_channel_name.get()
        new_log_or_add = self.add_new_log_or_add_all.get()
        if any(x for x in (channel_name, channel_id, new_log_or_add)):
            result = messagebox.askyesno(
                'Warning: Unsaved changes',
                'Fields in the "Add Channel" section have been edited, but not saved (remember to press "Add new channel" '
                'button to confirm adding a channel)\n\nDo you want to discard these changes and save all other changes?',
                icon = 'warning'
            )
            # print(result, type(result))
            if result is True: #Wanna discard: YES
                pass
            elif result is False: #Wanna discard: NO
                return False

        target_p = youtube.Playlist(self.cfg_target_id.get())
        if not target_p.verify():
            messagebox.showerror(
                'Error: Target Playlist is invalid',
                'The entered target playlist could not be verified. Please enter a valid playlist ID or URL.'
                )


        self.new_cfg.global_settings.name = self.cfg_name.get()
        self.new_cfg.global_settings.target_playlist_id = target_p.id
        cfg_selector = cast(auto_adder.ChannelUploadFilter, self.cfg_selector.get())
        self.new_cfg.global_settings.selector = cfg_selector
        auto_adder.write_settings(self.filepath, self.new_cfg)
        return True
    def save_back(self) -> None:
        if self._save():
            self.window.destroy()
            AutoAddWindow(self.root)
    def save_exit(self) -> None:
        if self._save():
            self.on_close()

class ConfigureAutoAdd(SubWindow):
    def __init__(self, root:tk.Tk) -> None:
        self.root = root
        self.window = tk.Toplevel(self.root)
        tk_root_styles(self.window)
        self.window.protocol('WM_DELETE_WINDOW', self.on_close)
        self.window.title('Configure: Auto Adder')

        label = ttk.Label(self.window, style= 'Warning.TLabel',
            text="Auto adder: General configuration page",
            font=("TkDefaultFont", 12, "bold"),
        )
        label.pack(padx = self.padx , pady = self.pady)

        label2 = ttk.Label(self.window, text="Please choose an auto adder to configure.", anchor='center')
        label2.pack(padx = self.padx, pady= self.pady)

        cfg_path = os.path.abspath('auto_adder_config')
        self.start_buttons:list[ttk.Button] = []
        for file in os.listdir(cfg_path):
            if file == 'template.json':
                continue
            filepath = os.path.join(cfg_path, file)
            auto_adder.read_settings(filepath)
            self.add_main_button(filepath)

        separator = ttk.Separator(self.window, orient='horizontal')
        separator.pack(fill='x', padx = self.padx , pady = self.pady)

        ##### Confirm
        ttk.Button(
            self.window,
            style= 'Confirm.TButton',
            text= 'Confirm & Back',
            command= self.on_confirm,
            width= self.btn_width
        ).pack(padx = self.padx , pady = self.pady)
    def add_main_button(self, filepath:str) -> None:
        cfg = auto_adder.read_settings(filepath)
        packed = partial(self.use_main_button, filepath = filepath)
        button = ttk.Button(self.window, text= cfg.global_settings.name, command= packed, width= self.btn_width)
        self.start_buttons.append(button)
        button.pack(padx = self.padx, pady = self.pady)
    def use_main_button(self, filepath:str) -> None:
        self.window.destroy()
        ConfigureSpecificAutoAdd(self.root, filepath)
    def on_confirm(self) -> None:
        self.window.destroy()
        AutoAddWindow(self.root)

class CreateNewAutoAdd(SubWindow):
    def __init__(self, root:tk.Tk) -> None:
        self.root = root
        self.window = tk.Toplevel(self.root)
        tk_root_styles(self.window)
        self.window.protocol('WM_DELETE_WINDOW', self.on_close)
        self.window.title('Create: Auto Adder')

        self.entry_width = 80
        self.label_width = 15
        textfield_frame = ttk.Frame(self.window)
        textfield_frame.pack(fill = 'x')

        ttk.Label(textfield_frame, text= 'Filename:', width= self.label_width).grid(row = 0, column= 0, sticky='w', padx= self.padx, pady= self.pady)
        self.filename_var = tk.StringVar(self.window)

        fn_frame = ttk.Frame(textfield_frame)
        ttk.Entry(fn_frame, textvariable = self.filename_var, width=self.entry_width-len('.json')).pack(side = 'left')
        ttk.Label(fn_frame, text= '.json').pack(side = 'right')
        fn_frame.grid(row = 0, column = 1, padx= self.padx, pady= self.pady)

        ttk.Label(textfield_frame, text= 'Display name:', width= self.label_width).grid(
            row = 1, column= 0, sticky='w', padx= self.padx, pady= self.pady
        )
        self.name_var = tk.StringVar(self.window)
        ttk.Entry(textfield_frame, textvariable = self.name_var, width= self.entry_width).grid(
            row = 1, column = 1, padx= self.padx, pady= self.pady
        )

        ttk.Label(textfield_frame, text= 'Target Playlist:', width= self.label_width).grid(
            row = 2, column= 0, sticky='w', padx= self.padx, pady= self.pady
        )
        self.target_playlist_var = tk.StringVar(self.window)
        ttk.Entry(textfield_frame, textvariable= self.target_playlist_var, width= self.entry_width).grid(
            row = 2, column = 1, padx= self.padx, pady= self.pady
        )


        options = ['All Videos', 'Full Videos only', 'Livestreams only', 'Shorts only']
        self.selector = tk.StringVar(textfield_frame, value=options[0])
        ttk.Label(textfield_frame, text= 'Video filter:', width= self.label_width).grid(
            row = 3, column= 0, padx = self.padx, pady = self.pady, sticky='w'
        )
        option_menu = ttk.OptionMenu(
            textfield_frame,
            self.selector,
            self.selector.get(),
            *options
        )
        option_menu['menu'].configure(**tk_styles(option_menu['menu']))
        option_menu.grid(
            row = 3, column= 1, padx = self.padx, pady = self.pady, sticky='ew'
        )

        separator = ttk.Separator(self.window, orient='horizontal')
        separator.pack(fill='x', padx = self.padx, pady = self.pady)

        self.button_frame = ttk.Frame(self.window)
        self.button_frame.pack()
        btn1 = ttk.Button(self.button_frame, style= 'Confirm.TButton', text= 'Confirm', command= self.on_confirm, width= self.btn_width//2)
        btn2 = ttk.Button(self.button_frame, style= 'Exit.TButton', text= 'Cancel', command= self.on_cancel, width= self.btn_width//2)
        btn1.grid(row = 0, column = 0, padx = self.padx, pady = self.pady, sticky= 'ew')
        btn2.grid(row = 0, column = 1, padx = self.padx, pady = self.pady, sticky= 'ew')

    def on_confirm(self) -> None:
        if not self.filename_var.get():
            messagebox.showerror('Error', 'Please enter a filename for the new auto adder.')
            return
        if not self.name_var.get():
            messagebox.showerror('Error', 'Please enter a name for the new auto adder.')
            return
        if not self.target_playlist_var.get():
            messagebox.showerror('Error', 'Please enter the target playlist for the new auto adder.')
            return
        fn = self.filename_var.get() + '.json'
        name = self.name_var.get()
        target = self.target_playlist_var.get()
        p = youtube.Playlist(target)
        if not p.verify():
            messagebox.showerror('Error', 'The target playlist entered is invalid.')
            return
        if os.path.isfile(f'auto_adder_config/{fn}'):
            messagebox.showerror('Error', 'The filename entered already exists, please enter a different one.')
            return

        selector = str(
            self.selector.get() #type:ignore
        ).lower().replace(' ', '_')
        selector = cast(auto_adder.ChannelUploadFilter, selector)
        auto_adder.create(filename= fn, name= name, target_playlist_id= p.id, selector= selector)

        messagebox.showinfo('Success', 'New auto adder successfully created!')

        self.window.destroy()
        AutoAddWindow(self.root)
    def on_cancel(self) -> None:
        self.window.destroy()
        AutoAddWindow(self.root)

class AutoAddWindow(SubWindow): #pylint:disable=too-many-instance-attributes
    def __init__(self, root:tk.Tk, rundirectly:bool = False) -> None:
        self.root = root
        self.window = tk.Toplevel(self.root)
        tk_root_styles(self.window)
        self.window.protocol('WM_DELETE_WINDOW', self.on_close)
        self.window.title('Auto Adder')
        self.worker:threading.Thread
        self.stop_event:threading.Event = threading.Event()
        self.rundirectly = rundirectly

        label = ttk.Label(self.window, style= 'TLabel',
            text="Auto adder",
            font=("TkDefaultFont", 12, "bold"),
        )
        label.pack(padx= self.padx, pady= self.pady)

        self.disabled_buttons:list[ttk.Button]

        self.menubar = tk.Menu(self.window)
        self.menubar.config()
        self.window.config(menu = self.menubar)
        config_menubar = tk.Menu(self.menubar)
        config_menubar.config(**tk_styles(self.menubar))
        config_menubar.add_command(
            label= 'Create new Auto Adder',
            command= self.create_new_auto_adder
        )
        config_menubar.add_command(
            label= 'Configure Existing Auto Adder',
            command= self.config_auto_adder
        )
        self.menubar.add_cascade(
            label= 'Config',
            menu= config_menubar,
            # underline= 0
        )

        label = ttk.Label(self.window, text="Please choose an auto adder to run.", anchor='center')
        label.pack(padx = self.padx, pady= self.pady)

        cfg_path = os.path.abspath('auto_adder_config')
        self.start_buttons:list[tuple[ttk.Button, Callable, Optional[bool]]] = []
        for file in os.listdir(cfg_path):
            if file == 'template.json':
                continue
            filepath = os.path.join(cfg_path, file)
            auto_adder.read_settings(filepath)
            self.add_main_button(filepath)

        self.progressbar:ttk.Progressbar #is actually created later
        self.progress_label:ttk.Label

        self.log_display = ScrolledText(self.window, height=10)
        self.log_visible = False
        self.setup_logging()

        ttk.Separator(self.window, orient='horizontal').pack(fill='x', padx=self.padx, pady=self.pady)

        self.run_all_button = ttk.Button(self.window, text= 'Run All', command= self.run_all, width= self.btn_width)
        self.run_all_button.pack(padx=self.padx, pady=self.pady)


        self.progressbar = ttk.Progressbar(self.window, length=300, mode='determinate')
        self.progress_label = ttk.Label(self.window, text= "Initializing", anchor='center', justify='center')


        if self.rundirectly is True:
            self.run_all_button.invoke()
            self.window.after(1000, self.auto_exit)
            # self.window.after(1000, self.auto_exit)
            # self.worker.join()
            # for button, _, success in self.start_buttons:
            #     pass

    def auto_exit(self) -> None:
        if self.worker.is_alive():
            self.window.after(1000, self.auto_exit)
        else:
            if self.rundirectly is True and all(result is True for _, _, result in self.start_buttons):
                self.on_close()
                print('auto exited')
            else:
                print('Cant auto exit')

    def on_close(self) -> None:
        self.stop_event.set()
        return super().on_close()

    def create_new_auto_adder(self) -> None:
        self.window.destroy()
        CreateNewAutoAdd(self.root)

    def config_auto_adder(self) -> None:
        self.window.destroy()
        ConfigureAutoAdd(self.root)

    def run_all(self) -> None:
        self.disable_buttons()
        self.worker = threading.Thread(target= self._run_all)
        self.stop_event = threading.Event()
        self.worker.start()
    def cancel_thread(self) -> None:
        self.stop_event.set()
    def _run_all(self) -> None:
        for i, (button, func, _) in enumerate(self.start_buttons):
            result = func(button= button, use_threading= False)
            # result = True
            self.start_buttons[i] = (self.start_buttons[i][0], self.start_buttons[i][1], result)
            if result is True:
                pass
            elif result is False:
                break
        self.enable_buttons()

    def disable_buttons(self) -> None:
        self.disabled_buttons = [btn for btn, _, _ in self.start_buttons]
        for button in self.disabled_buttons:
            button.config(state= 'disabled')
        max_index = self.menubar.index('end')
        assert max_index
        for i in range(max_index+1):
            self.menubar.entryconfig(i, state = 'disabled')
        self.run_all_button.config(command = self.cancel_thread, text = 'Cancel', style='Exit.TButton')
    def enable_buttons(self) -> None:
        for button in self.disabled_buttons:
            button.config(state= 'normal')
        max_index = self.menubar.index('end')
        assert max_index
        for i in range(max_index+1):
            self.menubar.entryconfig(i, state = 'normal')
        self.run_all_button.config(command = self.run_all, text = 'Run All', style='TButton')

    def add_main_button(self, filepath:str) -> None:
        cfg = auto_adder.read_settings(filepath)
        button = ttk.Button(self.window, text= cfg.global_settings.name, width= self.btn_width)
        packed = partial(self.use_main_button, filepath = filepath, button = button)
        button.config(command= packed)
        self.start_buttons.append((button, packed, None))
        button.pack(padx= self.padx, pady= self.pady)
    def use_main_button(self, filepath:str, button:ttk.Button, use_threading:bool = True) -> None | bool:
        self.disable_buttons()
        if use_threading:
            self.worker = threading.Thread(target = self._use_main_button, args= (filepath, button), daemon=True)
            self.stop_event = threading.Event()
            self.worker.start()
            return None
        return self._use_main_button(filepath, button)
    def _use_main_button(self, filepath: str, button:ttk.Button) -> bool:
        try:
            button.config(style = 'Working.TButton')
            self.progressbar.pack(fill='x', padx= self.padx, pady= self.pady)
            self.progress_label.pack(padx= self.padx, pady= self.pady)
            for msg, progress, total in auto_adder.process(filepath, self.stop_event):
                self.window.after(0, self._update_progress, msg, progress, total)
            button.config(style= 'Success.TButton')
            self.enable_buttons()
            result = True
            self.progressbar.pack_forget()
            self.progress_label.pack_forget()
            return result
        except auto_adder.ThreadStopped:
            button.config(style = 'Failure.TButton')
            self.enable_buttons()
            return False
        except youtube.UnskippableException:
            logging.error('Unskippable exception caught - exiting.')
            return False

    def _update_progress(self, msg:str, progress:int, total:int) -> None:
        self.progressbar['maximum'] = total
        self.progressbar['value'] = progress+1
        self.progress_label.config(text=f"{progress+1} / {total} - {msg}")




class AddToPlaylistWindow(SubWindow): #pylint:disable=too-many-instance-attributes
    def __init__(self, root:tk.Tk) -> None:
        self.root = root
        self.window = tk.Toplevel(self.root)
        tk_root_styles(self.window)
        self.window.protocol('WM_DELETE_WINDOW', self.on_close)
        self.window.title('Add to playlist')
        # self.window.minsize(400, 0)
        self.entry_width = 80
        self.label_width = 20

        ttk.Label(
            self.window,
            text= 'Please select your options for adding something to a playlist.'
        ).pack(anchor='w', padx=self.padx, pady=self.pady)

        ttk.Separator(self.window, orient='horizontal').pack(fill='x', padx=self.padx, pady=self.pady)

        ##### Source options section
        ttk.Label(self.window, text = 'From where do you want to add videos?').pack(anchor='w', padx=self.padx, pady=self.pady)
        selection_section = ttk.Frame(self.window)
        # self.src_video_id, self.src_playlist_id, self.src_channel_id = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.choices = ('Video', 'Playlist', 'Channel Uploads')
        self.selection_map = {name: number for number, name in enumerate(self.choices)}
        self.sources:dict[str, tk.StringVar] = {}
        self.selection_entries:dict[str, ttk.Entry] = {}
        self.selection = tk.IntVar(value= 0)
        selection_section.columnconfigure(0, minsize= 160)
        selection_section.columnconfigure(1, weight=1)
        for i, name in enumerate(self.choices):
            ttk.Radiobutton(
                selection_section,
                text= name.ljust(self.label_width),
                variable= self.selection,
                value=self.selection_map[name],
                command= self.update_entries
            ).grid(row = i, column = 0, sticky='w', padx=self.padx, pady=self.pady)
            self.sources[name] = tk.StringVar()
            self.selection_entries[name] = ttk.Entry(
                selection_section,
                textvariable= self.sources[name],
                state= 'disabled' if self.selection.get() != self.selection_map[name] else 'normal',
                width= self.entry_width
            )
            self.selection_entries[name].grid(row = i, column= 1, sticky= 'ew', padx=self.padx, pady=self.pady)
        selection_section.pack(anchor='w', fill= 'x', expand= True)

        # --- Channel uploads filter options (only visible when 'Channel Uploads' is selected) ---
        self.playlist_filter_frame = ttk.Frame(self.window)
        self.playlist_filter_options = [
            ("all videos", 0),
            ("full videos only", 1),
            ("livestreams only", 2),
            ("shorts only", 3)
        ]
        self.playlist_filter_var = tk.IntVar(value=0)
        self.playlist_filter_buttons = []
        for i, (label, val) in enumerate(self.playlist_filter_options):
            rb = ttk.Radiobutton(
                self.playlist_filter_frame,
                text=label,
                variable=self.playlist_filter_var,
                value=val
            )
            rb.grid(row=0, column=i, sticky='w', padx= (0,6), pady = self.pady)
            self.playlist_filter_buttons.append(rb)

        self.separator_above_target = ttk.Separator(self.window, orient='horizontal')
        self.separator_above_target.pack(fill='x', padx= self.padx, pady= self.pady)

        ##### Target options section
        self.target_section_label = ttk.Label(self.window, text = 'Where do these videos get added?')
        self.target_section_label.pack(anchor='w', padx= self.padx, pady= self.pady)
        self.target_section = ttk.Frame(self.window, width= 400)
        self.target_section.columnconfigure(0, minsize= 160)
        self.target_section.columnconfigure(1, weight= 1)

        ttk.Label(self.target_section, text= 'Playlist ID:').grid(row= 0, column= 0, sticky='w', padx= self.padx, pady= self.pady)
        self.target_playlist_id = tk.StringVar()
        ttk.Entry(self.target_section, textvariable= self.target_playlist_id).grid(row= 0, column= 1,sticky='ew', padx= self.padx, pady= self.pady)
        self.target_section.pack(fill='x', expand= True)


        ##### Logging field
        # Create and pack the log display
        self.log_display = ScrolledText(self.window, height = 10)
        self.log_visible = False
        self.setup_logging()

        ttk.Separator(self.window, orient='horizontal').pack(fill='x', padx=self.padx, pady=self.pady)

        ##### Confirm
        # ttk.Button(self.window, text= 'Confirm', command= self.on_confirm, width= self.btn_width).pack(padx= self.padx, pady= self.pady)
        self.button_frame = ttk.Frame(self.window)
        self.button_frame.pack()
        btn1 = ttk.Button(self.button_frame, style= 'Confirm.TButton', text= 'Confirm', command= self.on_confirm, width= self.btn_width//2)
        btn2 = ttk.Button(self.button_frame, style= 'Exit.TButton', text= 'Cancel', command= self.on_cancel, width= self.btn_width//2)
        btn1.grid(row = 0, column = 0, padx = self.padx, pady = self.pady, sticky= 'ew')
        btn2.grid(row = 0, column = 1, padx = self.padx, pady = self.pady, sticky= 'ew')

    def update_entries(self) -> None:
        for name, entry in self.selection_entries.items():
            if self.selection.get() != self.selection_map[name]:
                entry.config(state = 'disabled')
            else:
                entry.config(state = 'normal')

        # Show/hide playlist filter radiobuttons above target_section
        if self.selection.get() == self.selection_map['Channel Uploads']:
            self.playlist_filter_frame.pack(anchor='w', padx = self.padx, before=self.separator_above_target)
        else:
            self.playlist_filter_frame.pack_forget()

    def on_cancel(self) -> None:
        self.window.destroy()
        self.root.deiconify()
    def on_confirm(self) -> None:
        source = self.choices[self.selection.get()]
        src_id = self.sources[source].get()
        target_id = self.target_playlist_id.get()
        if not src_id:
            messagebox.showerror('ERROR', f'No source {source} ID given. Please enter one before confirming.')
            return
        elif not target_id:
            messagebox.showerror('ERROR', 'No target playlist ID given. Please enter one before confirming.')
            return

        target = youtube.Playlist(target_id)
        if not target.verify():
            messagebox.showerror('ERROR', 'The entered target Playlist ID is invalid. Please enter a valid ID!')
            return

        match source:
            case 'Video':
                v = youtube.Video(src_id)
                if not v.verify():
                    messagebox.showerror('ERROR', 'The entered source Video ID is invalid. Please enter a valid ID!')
                    return
                success = youtube.add_video_to_playlist(src_video_id= v.id, target_playlist = target)
            case 'Playlist':
                p = youtube.Playlist(src_id)
                if not p.verify():
                    messagebox.showerror('ERROR', 'The entered source Playlist ID is invalid. Please enter a valid ID!')
                    return
                success = youtube.add_playlist_to_playlist(src_playlist= p, target_playlist= target)
            case 'Channel Uploads':
                c = youtube.Channel(src_id)
                if not c.verify():
                    messagebox.showerror('ERROR', 'The entered source Channel ID is invalid. Please enter a valid ID!')
                    return
                success = youtube.add_channeluploads_to_playlist(
                    src_channel= c,
                    target_playlist = target,
                    full_videos_only = self.playlist_filter_var.get() == 1,
                    livestreams_only = self.playlist_filter_var.get() == 2,
                    shorts_only = self.playlist_filter_var.get() == 3
                )
        if success:
            messagebox.showinfo(
                'Adding video(s) was successfull!',
                'All videos have been successfully added to your target playlist!'
            )
            self.window.destroy()
            self.root.deiconify()
        else:
            messagebox.showerror(
                'Adding video(s) was unsuccessfull!',
                'Unfortunately, there has been an issue with adding all videos to your target playlist :('
            )


class RemovePlaylistEntriesUpToIndex(SubWindow): #pylint:disable=too-many-instance-attributes
    def __init__(self, root:tk.Tk) -> None:
        self.root = root
        self.window = tk.Toplevel(self.root)
        tk_root_styles(self.window)
        self.window.protocol('WM_DELETE_WINDOW', self.on_close)
        self.window.title('Remove Playlist entries up to index')
        # self.window.minsize(400, 0)
        self.entry_width = 80
        self.label_width = 20

        ##### Source options section
        self.source_section_label = ttk.Label(self.window, text = "What's the playlist you want to target?")
        self.source_section_label.pack(anchor='w', padx= self.padx, pady= self.pady)
        self.source_section = ttk.Frame(self.window, width= 400)
        self.source_section.columnconfigure(0, minsize= 160)
        self.source_section.columnconfigure(1, weight= 1)

        ttk.Label(self.source_section, text= 'Playlist ID:').grid(row= 0, column= 0, sticky='w', padx= self.padx, pady= self.pady)
        self.source_playlist_id = tk.StringVar()
        ttk.Entry(self.source_section, textvariable= self.source_playlist_id, width= self.entry_width).grid(
            row= 0, column= 1,sticky='ew', padx= self.padx, pady= self.pady
        )
        self.index = tk.IntVar()
        ttk.Label(self.source_section, text= 'Remove this many videos:').grid(row= 1, column= 0, sticky='w', padx= self.padx, pady= self.pady)
        ttk.Spinbox(self.source_section, textvariable= self.index, from_ = 1, to = 5000).grid(
            row = 1, column= 1, sticky='ew', padx= self.padx, pady= self.pady
        )

        self.source_section.pack(fill='x', expand= True)


        ##### Logging field
        # Create and pack the log display
        self.log_display = ScrolledText(self.window, height = 10)
        self.log_visible = False
        self.setup_logging()

        ttk.Separator(self.window, orient='horizontal').pack(fill='x', padx=self.padx, pady=self.pady)

        ##### Confirm
        # ttk.Button(self.window, text= 'Confirm', command= self.on_confirm, width= self.btn_width).pack(padx= self.padx, pady= self.pady)
        self.button_frame = ttk.Frame(self.window)
        self.button_frame.pack()
        btn1 = ttk.Button(self.button_frame, style= 'Confirm.TButton', text= 'Confirm', command= self.on_confirm, width= self.btn_width//2)
        btn2 = ttk.Button(self.button_frame, style= 'Exit.TButton', text= 'Cancel', command= self.on_cancel, width= self.btn_width//2)
        btn1.grid(row = 0, column = 0, padx = self.padx, pady = self.pady, sticky= 'ew')
        btn2.grid(row = 0, column = 1, padx = self.padx, pady = self.pady, sticky= 'ew')

    def on_cancel(self) -> None:
        self.window.destroy()
        self.root.deiconify()
    def on_confirm(self) -> None:
        source_id = self.source_playlist_id.get()
        if not source_id:
            messagebox.showerror('ERROR', 'No source playlist ID given. Please enter one before confirming.')
            return

        source = youtube.Playlist(source_id)
        if not source.verify():
            messagebox.showerror('ERROR', 'The entered source Playlist ID is invalid. Please enter a valid ID!')
            return

        index = self.index.get()
        if index <= 0:
            messagebox.showerror('ERROR', 'You need to remove atleast 1 video!')
            return

        success = True
        for i, video_elem in enumerate(source.yield_elements(['id'])):
            video_count = i+1
            if video_count > index:
                break
            vp_id = video_elem['id']
            success = bool(success * source.remove_video(video_playlist_id= vp_id))

        if success:
            messagebox.showinfo(
                'Removing video(s) was successfull!',
                'All videos have been successfully removed from your target playlist!'
            )
            self.window.destroy()
            self.root.deiconify()
        else:
            messagebox.showerror(
                'Removing video(s) was unsuccessfull!',
                'Unfortunately, there has been an issue with removing all videos from your target playlist :('
            )


class MainMenu:
    def __init__(self, root:tk.Tk) -> None:
        self.root = root
        tk_root_styles(self.root)
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)
        self.root.title('YouTube manager')
        self.btn_width:int = 50

        ttk.Button(
            root,
            text= 'Add to Playlist',
            command= self.add_to_playlist_window,
            width= self.btn_width
        ).pack(padx= 5, pady= 5)
        ttk.Button(
            root,
            text= 'Auto Playlist Adder',
            command= self.auto_add_window,
            width= self.btn_width
        ).pack(padx= 5, pady= 5)
        ttk.Button(
            root,
            text= 'Remove Playlist entries up to index',
            command= self.remove_playlist_entries,
            width= self.btn_width
        ).pack(padx= 5, pady= 5)

    def add_to_playlist_window(self) -> None:
        self.root.withdraw()
        AddToPlaylistWindow(self.root)
    def auto_add_window(self) -> None:
        self.root.withdraw()
        AutoAddWindow(self.root)
    def remove_playlist_entries(self) -> None:
        self.root.withdraw()
        RemovePlaylistEntriesUpToIndex(self.root)
    def on_close(self) -> None:
        self.root.destroy()

def tk_styles(element:tk.Menu) -> dict:
    if isinstance(element, tk.Menu):
        return {
            'background': colors['bg-3'],
            'foreground': colors['fg'],
            'activebackground': colors['blue-2'],
            'relief': 'flat'
        }
    raise TypeError('Styling for this class is not defined.')

def tk_root_styles(root:tk.Tk|tk.Toplevel) -> None:
    # custom_title_bar(root)
    root.config(
        bg = colors['bg-3']
    )
def custom_title_bar(root: tk.Tk | tk.Toplevel, title: str = 'testing') -> None:
    def start_move(event:Any) -> None:
        root._offset_x = event.x_root - root.winfo_x() #type:ignore #pylint:disable=protected-access
        root._offset_y = event.y_root - root.winfo_y() #type:ignore #pylint:disable=protected-access
    def do_move(event:Any) -> None:
        x = event.x_root - root._offset_x #type:ignore #pylint:disable=protected-access
        y = event.y_root - root._offset_y #type:ignore #pylint:disable=protected-access
        root.geometry(f'+{x}+{y}')
    def stop_move(_:Any) -> None:
        root._offset_x = 0 #type:ignore #pylint:disable=protected-access
        root._offset_y = 0 #type:ignore #pylint:disable=protected-access
    def close_button_on_enter(_:Any) -> None:
        close_button['background'] = colors['red-4']
    def close_button_on_leave(_:Any) -> None:
        close_button['background'] = colors['bg-3']

    # hPyT.title_bar.hide(root) #moving window induces ghosting

    title_bar = ttk.Frame(root, style='Titlebar.TFrame')
    title_bar.pack(fill='x', side='top')

    title_label = ttk.Label(title_bar, text=title, style="TitleBar.TLabel")
    title_label.pack(side="left", padx=10)

    close_button = tk.Button(title_bar,
        text='X',
        command=root.destroy,
        foreground= colors['fg'],
        background= colors['bg-3'],
        activeforeground= colors['fg'],
        activebackground= colors['red-2'],
        borderwidth= 0,
        width= 6
    )
    close_button.bind("<Enter>", close_button_on_enter)
    close_button.bind("<Leave>", close_button_on_leave)
    close_button.pack(side='right')

    title_bar.bind("<ButtonRelease-1>", stop_move)
    title_bar.bind("<Button-1>", start_move)
    title_bar.bind("<B1-Motion>", do_move)
    title_label.bind("<ButtonRelease-1>", stop_move)
    title_label.bind("<Button-1>", start_move)
    title_label.bind("<B1-Motion>", do_move)
def ttk_styles(root:tk.Tk) -> None:
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('TButton',
        background = colors['bg-6'],
        foreground = colors['fg'],
    )
    style.map('TButton',
        background=[("active", colors['bg-8']), ("pressed", colors['bg-7']), ('disabled', colors['bg-3'])],
        foreground=[("active", colors['fg']), ("pressed", colors['fg']), ('disabled', colors['fg-disabled'])]
    )

    style.configure('Confirm.TButton',
        background = colors['bg-6'],
        foreground = colors['fg'],
    )
    style.map('Confirm.TButton',
        background=[("active", colors['green-2']), ("pressed", colors['green-4'])],
        foreground=[("active", colors['fg']), ("pressed", colors['fg'])]
    )

    style.configure('Exit.TButton',
        background = colors['bg-6'],
        foreground = colors['fg'],
    )
    style.map('Exit.TButton',
        background=[("active", colors['red-3']), ("pressed", colors['red-4'])],
        foreground=[("active", colors['fg']), ("pressed", colors['fg'])]
    )

    style.configure('Working.TButton',
        background = colors['blue-3'],
        foreground = colors['fg'],
    )
    style.map('Working.TButton',
        background=[("active", colors['blue-4']), ("pressed", colors['blue-4']), ('disabled', colors['blue-4'])],
        foreground=[("active", colors['fg']), ("pressed", colors['fg']), ('disabled', colors['fg-disabled'])]
    )

    style.configure('Success.TButton',
        background = colors['green-3'],
        foreground = colors['fg'],
    )
    style.map('Success.TButton',
        background=[("active", colors['green-4']), ("pressed", colors['green-4']), ('disabled', colors['green-2'])],
        foreground=[("active", colors['fg']), ("pressed", colors['fg']), ('disabled', colors['fg-disabled'])]
    )

    style.configure('Failure.TButton',
        background = colors['red-3'],
        foreground = colors['fg'],
    )
    style.map('Failure.TButton',
        background=[("active", colors['red-4']), ("pressed", colors['red-4']), ('disabled', colors['red-2'])],
        foreground=[("active", colors['fg']), ("pressed", colors['fg']), ('disabled', colors['fg-disabled'])]
    )

    #Label
    style.configure('TLabel',
        background = colors['bg-3'],
        foreground = colors['fg'],
    )
    style.configure('Warning.TLabel',
        background = colors['bg-3'],
        foreground = colors['red-4'],
    )

    #Radiobutton
    style.configure('TRadiobutton',
        background = colors['bg-3'],
        foreground = colors['fg'],
        indicatorcolor = colors['bg-3'],
        focuscolor = ""
    )
    style.map('TRadiobutton',
        background=[("active", colors['bg-3']), ("pressed", colors['bg-3'])],
        foreground=[("active", colors['fg']), ("pressed", colors['fg'])]
    )

    #Frame
    style.configure('TFrame',
        background = colors['bg-3'],
        foreground = colors['fg'],
    )
    style.configure('Titlebar.TFrame',
        background = colors['bg-3'],
        foreground = colors['fg'],
    )

    #Entry
    style.configure("TEntry",
        foreground = colors['fg'],
        fieldbackground= colors['bg-6'],
    )
    style.map('TEntry',
        fieldbackground=[("focus", colors['bg-6']), ("disabled", colors['bg-3'])],
        foreground=[("focus", colors['fg'])]
    )

    #OptionMenu
    style.configure('TMenubutton',
        foreground = colors['fg'],
        background= colors['bg-6'],
    )
    style.map('TMenubutton',
        background=[("active", colors['bg-8']), ("disabled", colors['bg-3'])],
        foreground=[("active", colors['fg'])]
    )

    #Progressbar
    tmp_color = colors['green-2']
    style.configure('TProgressbar',
        throughcolor = tmp_color,
        lightcolor = tmp_color,
        darkcolor = tmp_color,
        background= tmp_color,
    )



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-aaa', '--automaticautoadder',
        action='store_true',
        help= 'Runs the auto adder immediately, starts all and exits automatically if no errors were detected.'
    )
    args = parser.parse_args()

    youtube.Youtube() #verifies credentials
    root = tk.Tk()
    ttk_styles(root)
    MainMenu(root)

    if args.automaticautoadder is True:
        root.withdraw()
        AutoAddWindow(root, True)

    root.mainloop()

if __name__ == '__main__':
    load_dotenv()
    main()
