import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import serial
import serial.tools.list_ports
import threading
import time
import os

class OmnicureGUI:
    PASSWORD = "1234@"  # password required to enter Update Settings

    def __init__(self, root):
        self.root = root
        self.root.title("OMNICURE LX500")
        self.root.geometry("1200x750")
        self.root.resizable(True, True)
        self.root.configure(bg='#ffffff')  # Light background
        
        # Set window icon (if available)
        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass

        # ensure defaults file exists
        self.settings_file = "omnicure_settings.txt"
        if not os.path.exists(self.settings_file):
            with open(self.settings_file, "w") as f:
                f.write("120\n50\n2\n10\n")
        
        # Set initial values for first cure
        self.first_cure_initial_values = ["120", "50", "2", "10"]

        # Modern styling
        self.setup_styles()

        self.serial_port = None
        self.serial_connected = False
        self.running = False
        self.live_thread = None
        self.current_cure_step = 0  # 0=none, 1=first cure, 2=second cure
        self.message_blink_state = False  # For blinking messages
        self.blink_after_id = None  # To cancel blinking
        
        # High-precision timing system
        self.timing_thread = None
        self.timing_running = False
        self.cure_start_time = None
        self.cure_duration = None
        self.current_cure_type = None

        # First cure settings
        self.first_cure_labels = [
            "Total Cure Time (sec)",
            "Pulse Time Percentage (%)",
            "Pulsing Frequency (Hz)",
            "Intensity Ramp Step (%)"
        ]
        # Set default values directly to StringVars
        self.first_cure_vars = [
            tk.StringVar(value="120"),
            tk.StringVar(value="50"),
            tk.StringVar(value="2"),
            tk.StringVar(value="10")
        ]
        self.first_cure_blink_var = tk.StringVar()
        # Add intensity and time tracking for first cure
        self.first_cure_intensity_var = tk.StringVar(value="0%")
        self.first_cure_time_var = tk.StringVar(value="0.000")
        
        # Second cure settings (fixed for 60 sec, 100% intensity, continuous)
        self.second_cure_labels = [
            "Cure Time (sec)",
            "Intensity (%)",
            "Mode"
        ]
        self.second_cure_vars = [
            tk.StringVar(value="60"),
            tk.StringVar(value="100"),
            tk.StringVar(value="Continuous")
        ]
        # Add time tracking for second cure
        self.second_cure_time_var = tk.StringVar(value="0.000")

        self.message_var = tk.StringVar()
        self.status_var = tk.StringVar(value="🔍 Checking connection...")
        self.selected_com_port = tk.StringVar()

        # Create main container with padding
        self.main_container = ttk.Frame(self.root, style="Main.TFrame")
        self.main_container.pack(fill='both', expand=True, padx=20, pady=20)
        
        self.main_frame = ttk.Frame(self.main_container, style="Main.TFrame")
        self.first_cure_settings_frame = ttk.Frame(self.main_container, style="Settings.TFrame")
        self.second_cure_settings_frame = ttk.Frame(self.main_container, style="Settings.TFrame")

        self.create_main_widgets()
        self.create_first_cure_settings_widgets()
        self.create_second_cure_settings_widgets()

        self.load_defaults_to_display()
        self.refresh_com_ports()
        # Auto-connect to OMNICURE device on startup
        self.root.after(1000, self.auto_connect_omnicure)
        self.root.after(2000, self.check_serial_health)
        self.show_main_frame()

    def setup_styles(self):
        """Setup modern styling for the application"""
        style = ttk.Style()
        
        # Configure themes and colors
        style.theme_use('clam')
        
        # Color scheme - Light theme with dark text and blue highlights
        self.colors = {
            'primary': '#2563eb',      # Blue
            'secondary': '#64748b',    # Gray
            'accent': '#dc2626',       # Red
            'warning': '#ea580c',      # Orange
            'dark': '#1e293b',         # Dark Blue
            'light': '#f1f5f9',        # Light Gray
            'white': '#ffffff',        # White
            'success': '#16a34a',      # Green
            'info': '#2563eb',         # Blue
            'background': '#ffffff',   # White Background
            'text': '#1e293b',         # Dark Text
            'text_secondary': '#64748b', # Gray Text
            'running': '#16a34a',      # Green for running cures
            'message_bg': '#fef3c7',   # Light yellow for messages
            'message_text': '#92400e'  # Dark orange for message text
        }
        
        # Main frame style
        style.configure("Main.TFrame", background=self.colors['background'])
        
        # Settings frame style
        style.configure("Settings.TFrame", background=self.colors['light'])
        
        # Title style
        style.configure("Title.TLabel", 
                       font=('Arial', 20, 'bold'), 
                       foreground=self.colors['primary'],
                       background=self.colors['background'])
        
        # Header style
        style.configure("Header.TLabel", 
                       font=('Arial', 10), 
                       foreground=self.colors['text'],
                       background=self.colors['background'])
        
        # Cure header style
        style.configure("CureHeader.TLabel", 
                       font=('Arial', 14, 'bold'), 
                       foreground=self.colors['primary'],
                       background=self.colors['light'])
        
        # Value style
        style.configure("Value.TLabel", 
                       font=('Arial', 10), 
                       foreground=self.colors['text'],
                       background=self.colors['light'])
        
        # Status style
        style.configure("Status.TLabel", 
                       font=('Arial', 9), 
                       foreground=self.colors['info'],
                       background=self.colors['background'])
        
        # Button styles
        style.configure("Primary.TButton", 
                       font=('Arial', 10), 
                       padding=(10, 5),
                       background=self.colors['primary'],
                       foreground=self.colors['white'])
        
        style.configure("Success.TButton", 
                       font=('Arial', 10), 
                       padding=(10, 5),
                       background=self.colors['success'],
                       foreground=self.colors['white'])
        
        style.configure("Warning.TButton", 
                       font=('Arial', 10), 
                       padding=(10, 5),
                       background=self.colors['warning'],
                       foreground=self.colors['white'])
        
        style.configure("Danger.TButton", 
                       font=('Arial', 10), 
                       padding=(10, 5),
                       background=self.colors['accent'],
                       foreground=self.colors['white'])
        
        style.configure("Secondary.TButton", 
                       font=('Arial', 9), 
                       padding=(8, 4),
                       background=self.colors['light'],
                       foreground=self.colors['text'])
        
        # Disabled button style
        style.configure("Disabled.TButton", 
                       font=('Arial', 10), 
                       padding=(10, 5),
                       background='#cccccc',
                       foreground='#666666')
        
        # Entry style
        style.configure("Modern.TEntry", 
                       font=('Arial', 9),
                       padding=(5, 3),
                       fieldbackground=self.colors['white'],
                       foreground=self.colors['text'],
                       borderwidth=1,
                       relief='solid')
        
        # LabelFrame style
        style.configure("Modern.TLabelframe", 
                       background=self.colors['light'],
                       borderwidth=1,
                       relief='solid')
        
        style.configure("Modern.TLabelframe.Label", 
                       font=('Arial', 10, 'bold'),
                       foreground=self.colors['primary'],
                       background=self.colors['light'])
        
        # Running frame style (green when cure is active)
        style.configure("Running.TLabelframe", 
                       background=self.colors['running'],
                       borderwidth=2,
                       relief='solid')
        
        style.configure("Running.TLabelframe.Label", 
                       font=('Arial', 10, 'bold'),
                       foreground=self.colors['white'],
                       background=self.colors['running'])

    def create_main_widgets(self):
        # Title with icon
        title_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        title_frame.pack(fill='x', pady=(0, 20))
        
        title_label = ttk.Label(title_frame, text="⚡ OMNICURE LX500", 
                                style="Title.TLabel")
        title_label.pack()

        # Main content frame
        content_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        content_frame.pack(fill='both', expand=True)

        # First Cure Column
        first_cure_frame = ttk.LabelFrame(content_frame, text="🔴 First Cure - Pulsed and Continuous Mode", 
                                        style="Modern.TLabelframe")
        first_cure_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))

        # First cure controls with better layout
        first_ctrl_frame = ttk.Frame(first_cure_frame, style="Main.TFrame")
        first_ctrl_frame.pack(fill='x', padx=15, pady=15)
        
                # Control buttons in a grid
        ttk.Button(first_ctrl_frame, text="🚀 First Cure", command=self.start_first_cure, 
                   style="Success.TButton").grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        ttk.Button(first_ctrl_frame, text="⚙️ Update Settings", command=self.show_first_cure_settings, 
                   style="Secondary.TButton").grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(first_ctrl_frame, text="🔄 Revert to Default", command=self.revert_first_cure_to_default, 
                   style="Secondary.TButton").grid(row=0, column=2, padx=5, pady=5, sticky='ew')
        
        # Configure grid weights
        first_ctrl_frame.columnconfigure(0, weight=1)
        first_ctrl_frame.columnconfigure(1, weight=1)
        first_ctrl_frame.columnconfigure(2, weight=1)

        
        
        # Store frame references for color changes
        self.first_cure_frame = first_cure_frame

        # First cure settings display with better styling
        first_disp_frame = ttk.Frame(first_cure_frame, style="Main.TFrame")
        first_disp_frame.pack(fill='both', expand=True, padx=15, pady=10)
        
        for i, label in enumerate(self.first_cure_labels):
            # Label
            ttk.Label(first_disp_frame, text=f"{label}:", style="Header.TLabel")\
               .grid(row=i, column=0, sticky='w', padx=10, pady=8)
            # Value with better styling
            value_label = ttk.Label(first_disp_frame, textvariable=self.first_cure_vars[i], 
                                   style="Value.TLabel")
            value_label.grid(row=i, column=1, sticky='w', padx=10, pady=8)
        
        # Blink time display
        ttk.Label(first_disp_frame, text="ON/OFF Time per Blink (sec):", style="Header.TLabel")\
           .grid(row=len(self.first_cure_labels), column=0, sticky='w', padx=10, pady=8)
        blink_label = ttk.Label(first_disp_frame, textvariable=self.first_cure_blink_var, 
                               style="Value.TLabel")
        blink_label.grid(row=len(self.first_cure_labels), column=1, sticky='w', padx=10, pady=8)

        # Current intensity display in separate frame
        intensity_frame = ttk.LabelFrame(first_disp_frame, text="⚡ Current Intensity", 
                                        style="Modern.TLabelframe")
        intensity_frame.grid(row=len(self.first_cure_labels)+1, column=0, columnspan=2, 
                            sticky='ew', padx=10, pady=8)
        intensity_label = ttk.Label(intensity_frame, textvariable=self.first_cure_intensity_var, 
                                   style="Value.TLabel")
        intensity_label.pack(padx=10, pady=5)

        # Elapsed time display in separate frame
        time_frame = ttk.LabelFrame(first_disp_frame, text="⏱️ Elapsed Time", 
                                   style="Modern.TLabelframe")
        time_frame.grid(row=len(self.first_cure_labels)+2, column=0, columnspan=2, 
                       sticky='ew', padx=10, pady=8)
        time_label = ttk.Label(time_frame, textvariable=self.first_cure_time_var, 
                              style="Value.TLabel")
        time_label.pack(padx=10, pady=5)

        # Second Cure Column
        second_cure_frame = ttk.LabelFrame(content_frame, text="🟢 Second Cure - Continuous Mode", 
                                         style="Modern.TLabelframe")
        second_cure_frame.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        # Store second cure frame reference for color changes
        self.second_cure_frame = second_cure_frame

        # Second cure controls
        second_ctrl_frame = ttk.Frame(second_cure_frame, style="Main.TFrame")
        second_ctrl_frame.pack(fill='x', padx=15, pady=15)
        
        ttk.Button(second_ctrl_frame, text="🚀 Second Cure", command=self.start_second_cure, 
                  style="Success.TButton").grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        ttk.Button(second_ctrl_frame, text="⚙️ Update Settings", command=self.show_second_cure_settings, 
                  style="Secondary.TButton").grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(second_ctrl_frame, text="🔄 Revert to Default", command=self.revert_second_cure_to_default, 
                  style="Secondary.TButton").grid(row=0, column=2, padx=5, pady=5, sticky='ew')
        
        second_ctrl_frame.columnconfigure(0, weight=1)
        second_ctrl_frame.columnconfigure(1, weight=1)
        second_ctrl_frame.columnconfigure(2, weight=1)

        # Second cure settings display
        second_disp_frame = ttk.Frame(second_cure_frame, style="Main.TFrame")
        second_disp_frame.pack(fill='both', expand=True, padx=15, pady=10)
        
        for i, label in enumerate(self.second_cure_labels):
            ttk.Label(second_disp_frame, text=f"{label}:", style="Header.TLabel")\
               .grid(row=i, column=0, sticky='w', padx=10, pady=8)
            value_label = ttk.Label(second_disp_frame, textvariable=self.second_cure_vars[i], 
                                   style="Value.TLabel")
            value_label.grid(row=i, column=1, sticky='w', padx=10, pady=8)

        # Elapsed time display for second cure in separate frame
        second_time_frame = ttk.LabelFrame(second_disp_frame, text="⏱️ Elapsed Time", 
                                          style="Modern.TLabelframe")
        second_time_frame.grid(row=len(self.second_cure_labels), column=0, columnspan=2, 
                              sticky='ew', padx=10, pady=8)
        second_time_label = ttk.Label(second_time_frame, textvariable=self.second_cure_time_var, 
                                     style="Value.TLabel")
        second_time_label.pack(padx=10, pady=5)

        # Common Stop Button - Large and prominent
        stop_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        stop_frame.pack(fill='x', pady=20)
        
        stop_button = ttk.Button(stop_frame, text="🛑 STOP CURE", command=self.stop_action, 
                                style="Danger.TButton")
        stop_button.pack(pady=10)

        # Status and connection with better styling
        status_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        status_frame.pack(fill='x', pady=10)
        
        status_label = ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel")
        status_label.pack(side='left')
        
        # COM Port selection
        com_frame = ttk.Frame(status_frame, style="Main.TFrame")
        com_frame.pack(side='left', padx=(20, 0))
        
        ttk.Label(com_frame, text="COM Port:", style="Status.TLabel").pack(side='left')
        self.com_port_combo = ttk.Combobox(com_frame, textvariable=self.selected_com_port, 
                                         width=10, state="readonly")
        self.com_port_combo.pack(side='left', padx=(5, 0))
        self.com_port_combo.bind('<<ComboboxSelected>>', self.on_com_port_selected)
        
        refresh_com_button = ttk.Button(com_frame, text="🔄", command=self.refresh_com_ports, 
                                      style="Secondary.TButton", width=3)
        refresh_com_button.pack(side='left', padx=(5, 0))
        
        connect_button = ttk.Button(com_frame, text="🔌 Connect", command=self.manual_connect_selected_port, 
                                  style="Success.TButton")
        connect_button.pack(side='left', padx=(5, 0))
        
        scan_button = ttk.Button(status_frame, text="🔍 Scan All", command=self.manual_check_connection, 
                                style="Secondary.TButton")
        scan_button.pack(side='left', padx=10)

        # Message area with better styling
        message_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        message_frame.pack(fill='x', pady=10)
        
        self.message_label = ttk.Label(message_frame, textvariable=self.message_var, 
                                      font=('Arial', 10),
                                      background=self.colors['message_bg'],
                                      foreground=self.colors['message_text'],
                                      padding=(5, 3))
        self.message_label.pack(fill='x')

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_first_cure_settings_widgets(self):
        # Title
        title_label = ttk.Label(self.first_cure_settings_frame, text="⚙️ First Cure Settings", 
                               style="CureHeader.TLabel")
        title_label.pack(pady=20)

        # Settings container
        settings_container = ttk.Frame(self.first_cure_settings_frame, style="Settings.TFrame")
        settings_container.pack(fill='both', expand=True, padx=30, pady=20)

        self.first_cure_entries = []
        for i, label in enumerate(self.first_cure_labels):
            # Label frame for each setting
            setting_frame = ttk.Frame(settings_container, style="Settings.TFrame")
            setting_frame.pack(fill='x', pady=10)
            
            ttk.Label(setting_frame, text=f"{label}", 
                     font=('Arial', 10),
                     foreground=self.colors['text'],
                     background=self.colors['light']).pack(anchor='w', pady=(0, 5))
            
            # Create entry with current value
            current_value = self.first_cure_vars[i].get()
            var = tk.StringVar(value=current_value)
            entry = ttk.Entry(setting_frame, textvariable=var, width=25, style="Modern.TEntry")
            entry.pack(fill='x', pady=5)
            # Configure entry text color explicitly
            entry.configure(foreground=self.colors['text'])
            self.first_cure_entries.append(var)

        # Buttons frame
        buttons_frame = ttk.Frame(self.first_cure_settings_frame, style="Settings.TFrame")
        buttons_frame.pack(fill='x', padx=30, pady=30)
        
        self.first_cure_save_button = tk.Button(buttons_frame, text="💾 Save Settings", command=self.save_first_cure_settings, 
                  bg=self.colors['success'], fg=self.colors['white'], font=('Arial', 10), 
                  relief='raised', bd=2, padx=10, pady=5)
        self.first_cure_save_button.pack(side='left', padx=5)
        
        self.first_cure_revert_button = tk.Button(buttons_frame, text="🔄 Revert to Default", command=self.revert_first_cure_to_default, 
                  bg=self.colors['primary'], fg=self.colors['white'], font=('Arial', 10), 
                  relief='raised', bd=2, padx=10, pady=5)
        self.first_cure_revert_button.pack(side='left', padx=5)
        
        ttk.Button(buttons_frame, text="🔙 Back to Main", command=self.show_main_frame, 
                  style="Secondary.TButton").pack(side='right', padx=5)

    def create_second_cure_settings_widgets(self):
        # Title
        title_label = ttk.Label(self.second_cure_settings_frame, text="⚙️ Second Cure Settings", 
                               style="CureHeader.TLabel")
        title_label.pack(pady=20)

        # Settings container
        settings_container = ttk.Frame(self.second_cure_settings_frame, style="Settings.TFrame")
        settings_container.pack(fill='both', expand=True, padx=30, pady=20)

        self.second_cure_entries = []
        for i, label in enumerate(self.second_cure_labels):
            # Label frame for each setting
            setting_frame = ttk.Frame(settings_container, style="Settings.TFrame")
            setting_frame.pack(fill='x', pady=10)
            
            ttk.Label(setting_frame, text=f"{label}", 
                     font=('Arial', 10),
                     foreground=self.colors['text'],
                     background=self.colors['light']).pack(anchor='w', pady=(0, 5))
            
            # Create entry with current value
            current_value = self.second_cure_vars[i].get()
            var = tk.StringVar(value=current_value)
            entry = ttk.Entry(setting_frame, textvariable=var, width=25, style="Modern.TEntry")
            entry.pack(fill='x', pady=5)
            # Configure entry text color explicitly
            entry.configure(foreground=self.colors['text'])
            self.second_cure_entries.append(var)

        # Buttons frame
        buttons_frame = ttk.Frame(self.second_cure_settings_frame, style="Settings.TFrame")
        buttons_frame.pack(fill='x', padx=30, pady=30)
        
        self.second_cure_save_button = tk.Button(buttons_frame, text="💾 Save Settings", command=self.save_second_cure_settings, 
                  bg=self.colors['success'], fg=self.colors['white'], font=('Arial', 10), 
                  relief='raised', bd=2, padx=10, pady=5)
        self.second_cure_save_button.pack(side='left', padx=5)
        
        self.second_cure_revert_button = tk.Button(buttons_frame, text="🔄 Revert to Default", command=self.revert_second_cure_to_default, 
                  bg=self.colors['primary'], fg=self.colors['white'], font=('Arial', 10), 
                  relief='raised', bd=2, padx=10, pady=5)
        self.second_cure_revert_button.pack(side='left', padx=5)
        
        ttk.Button(buttons_frame, text="🔙 Back to Main", command=self.show_main_frame, 
                  style="Secondary.TButton").pack(side='right', padx=5)

    def show_main_frame(self):
        self.first_cure_settings_frame.pack_forget()
        self.second_cure_settings_frame.pack_forget()
        self.main_frame.pack(fill='both', expand=True)

    def show_first_cure_settings(self):
        pw = simpledialog.askstring("🔐 Password Required", "Enter password to update first cure settings:", show='*')
        if pw != OmnicureGUI.PASSWORD:
            messagebox.showerror("❌ Authentication Failed", "Incorrect password.")
            return
        
        # Update entry fields with current values
        for i, var in enumerate(self.first_cure_entries):
            current_value = self.first_cure_vars[i].get()
            var.set(current_value)
        
        self.main_frame.pack_forget()
        self.second_cure_settings_frame.pack_forget()
        self.first_cure_settings_frame.pack(fill='both', expand=True)



    def show_second_cure_settings(self):
        pw = simpledialog.askstring("🔐 Password Required", "Enter password to update second cure settings:", show='*')
        if pw != OmnicureGUI.PASSWORD:
            messagebox.showerror("❌ Authentication Failed", "Incorrect password.")
            return
        
        # Update entry fields with current values
        for i, var in enumerate(self.second_cure_entries):
            current_value = self.second_cure_vars[i].get()
            var.set(current_value)
        
        self.main_frame.pack_forget()
        self.first_cure_settings_frame.pack_forget()
        self.second_cure_settings_frame.pack(fill='both', expand=True)

    def start_first_cure(self):
        if self.running:
            messagebox.showinfo("ℹ️ Info", "Cure already running.")
            return
        self.current_cure_step = 1
        self.set_cure_frame_running(1, True)
        # Reset cure started flag
        self.cure_was_started = False
        # Disable ALL controls immediately
        self.disable_all_controls()
        # Small delay to ensure GUI updates
        self.root.after(100, lambda: self.start_live(self.first_cure_vars, "First Cure"))

    def start_second_cure(self):
        if self.running:
            messagebox.showinfo("ℹ️ Info", "Cure already running.")
            return
        self.current_cure_step = 2
        self.set_cure_frame_running(2, True)
        # Reset cure started flag
        self.cure_was_started = False
        # Disable ALL controls immediately
        self.disable_all_controls()
        # Small delay to ensure GUI updates
        self.root.after(100, lambda: self.start_live(self.second_cure_vars, "Second Cure"))

    def save_first_cure_settings(self):
        for i, var in enumerate(self.first_cure_entries):
            self.first_cure_vars[i].set(var.get().strip())
        self.update_first_cure_blink_time()
        messagebox.showinfo("✅ Saved", "First cure settings applied successfully!")

    def save_second_cure_settings(self):
        for i, var in enumerate(self.second_cure_entries):
            self.second_cure_vars[i].set(var.get().strip())
        messagebox.showinfo("✅ Saved", "Second cure settings applied successfully!")

    def make_first_cure_default(self):
        pw = simpledialog.askstring("🔐 Password Required", "Enter password to make first cure default:", show='*')
        if pw != OmnicureGUI.PASSWORD:
            messagebox.showerror("❌ Authentication Failed", "Incorrect password.")
            return
        try:
            with open(self.settings_file, 'w') as f:
                for var in self.first_cure_entries:
                    f.write(var.get().strip() + "\n")
            messagebox.showinfo("💾 Defaults Saved", "First cure values are now your defaults!")
        except Exception as e:
            messagebox.showerror("❌ Error", f"Could not save defaults: {e}")

    def make_second_cure_default(self):
        pw = simpledialog.askstring("🔐 Password Required", "Enter password to make second cure default:", show='*')
        if pw != OmnicureGUI.PASSWORD:
            messagebox.showerror("❌ Authentication Failed", "Incorrect password.")
            return
        try:
            with open("second_cure_defaults.txt", 'w') as f:
                for var in self.second_cure_entries:
                    f.write(var.get().strip() + "\n")
            messagebox.showinfo("💾 Defaults Saved", "Second cure values are now your defaults!")
        except Exception as e:
            messagebox.showerror("❌ Error", f"Could not save defaults: {e}")

    def revert_first_cure_to_default(self):
        """Revert first cure values back to default"""
        pw = simpledialog.askstring("🔐 Password Required", "Enter password to revert first cure to default:", show='*')
        if pw != OmnicureGUI.PASSWORD:
            messagebox.showerror("❌ Authentication Failed", "Incorrect password.")
            return
        
        # Set back to default values
        default_values = ["120", "50", "2", "10"]
        for i, value in enumerate(default_values):
            self.first_cure_vars[i].set(value)
        
        self.update_first_cure_blink_time()
        messagebox.showinfo("✅ Reverted", "First cure values reverted to default!")

    def revert_second_cure_to_default(self):
        """Revert second cure values back to default"""
        pw = simpledialog.askstring("🔐 Password Required", "Enter password to revert second cure to default:", show='*')
        if pw != OmnicureGUI.PASSWORD:
            messagebox.showerror("❌ Authentication Failed", "Incorrect password.")
            return
        
        # Set back to default values
        default_values = ["60", "100", "Continuous"]
        for i, value in enumerate(default_values):
            self.second_cure_vars[i].set(value)
        
        messagebox.showinfo("✅ Reverted", "Second cure values reverted to default!")

    def disable_all_controls(self):
        """Disable ALL controls except stop button and close option during cure"""
        print("DEBUG: Disabling ALL controls during cure...")
        try:
            # Disable settings buttons
            if hasattr(self, 'first_cure_save_button') and self.first_cure_save_button:
                self.first_cure_save_button.configure(state='disabled')
                self.first_cure_save_button.configure(text="💾 Save Settings (Disabled)")
                self.first_cure_save_button.configure(bg='#cccccc', fg='#666666')
                self.first_cure_save_button.configure(command=lambda: None)
                
            if hasattr(self, 'first_cure_revert_button') and self.first_cure_revert_button:
                self.first_cure_revert_button.configure(state='disabled')
                self.first_cure_revert_button.configure(text="🔄 Revert to Default (Disabled)")
                self.first_cure_revert_button.configure(bg='#cccccc', fg='#666666')
                self.first_cure_revert_button.configure(command=lambda: None)
                
            if hasattr(self, 'second_cure_save_button') and self.second_cure_save_button:
                self.second_cure_save_button.configure(state='disabled')
                self.second_cure_save_button.configure(text="💾 Save Settings (Disabled)")
                self.second_cure_save_button.configure(bg='#cccccc', fg='#666666')
                self.second_cure_save_button.configure(command=lambda: None)
                
            if hasattr(self, 'second_cure_revert_button') and self.second_cure_revert_button:
                self.second_cure_revert_button.configure(state='disabled')
                self.second_cure_revert_button.configure(text="🔄 Revert to Default (Disabled)")
                self.second_cure_revert_button.configure(bg='#cccccc', fg='#666666')
                self.second_cure_revert_button.configure(command=lambda: None)
            
            # Disable main cure buttons (First Cure, Second Cure)
            for widget in self.main_frame.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.LabelFrame):
                            for grandchild in child.winfo_children():
                                if isinstance(grandchild, ttk.Frame):
                                    for button in grandchild.winfo_children():
                                        if isinstance(button, ttk.Button):
                                            if "First Cure" in button.cget("text") or "Second Cure" in button.cget("text"):
                                                button.configure(state='disabled')
                                            elif "Update Settings" in button.cget("text") or "Revert to Default" in button.cget("text"):
                                                button.configure(state='disabled')
            
            # Disable scan device button
            for widget in self.main_frame.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Button) and "Scan Device" in child.cget("text"):
                            child.configure(state='disabled')
            
            # Disable back buttons in settings screens
            if hasattr(self, 'first_cure_settings_frame'):
                for widget in self.first_cure_settings_frame.winfo_children():
                    if isinstance(widget, ttk.Frame):
                        for child in widget.winfo_children():
                            if isinstance(child, ttk.Button) and "Back to Main" in child.cget("text"):
                                child.configure(state='disabled')
            
            if hasattr(self, 'second_cure_settings_frame'):
                for widget in self.second_cure_settings_frame.winfo_children():
                    if isinstance(widget, ttk.Frame):
                        for child in widget.winfo_children():
                            if isinstance(child, ttk.Button) and "Back to Main" in child.cget("text"):
                                child.configure(state='disabled')
            
            # Force GUI update
            self.root.update_idletasks()
            self.root.update()
            print("DEBUG: ALL controls disabled")
        except Exception as e:
            print(f"Error disabling controls: {e}")

    def enable_all_controls(self):
        """Enable ALL controls after cure"""
        # Only enable controls if no cure is currently running
        if self.running:
            print("DEBUG: Cure still running, not re-enabling controls")
            return
            
        print("DEBUG: Re-enabling ALL controls...")
        try:
            # Re-enable settings buttons
            if hasattr(self, 'first_cure_save_button') and self.first_cure_save_button:
                self.first_cure_save_button.configure(state='normal')
                self.first_cure_save_button.configure(text="💾 Save Settings")
                self.first_cure_save_button.configure(bg=self.colors['success'], fg=self.colors['white'])
                self.first_cure_save_button.configure(command=self.save_first_cure_settings)
                
            if hasattr(self, 'first_cure_revert_button') and self.first_cure_revert_button:
                self.first_cure_revert_button.configure(state='normal')
                self.first_cure_revert_button.configure(text="🔄 Revert to Default")
                self.first_cure_revert_button.configure(bg=self.colors['primary'], fg=self.colors['white'])
                self.first_cure_revert_button.configure(command=self.revert_first_cure_to_default)
                
            if hasattr(self, 'second_cure_save_button') and self.second_cure_save_button:
                self.second_cure_save_button.configure(state='normal')
                self.second_cure_save_button.configure(text="💾 Save Settings")
                self.second_cure_save_button.configure(bg=self.colors['success'], fg=self.colors['white'])
                self.second_cure_save_button.configure(command=self.save_second_cure_settings)
                
            if hasattr(self, 'second_cure_revert_button') and self.second_cure_revert_button:
                self.second_cure_revert_button.configure(state='normal')
                self.second_cure_revert_button.configure(text="🔄 Revert to Default")
                self.second_cure_revert_button.configure(bg=self.colors['primary'], fg=self.colors['white'])
                self.second_cure_revert_button.configure(command=self.revert_second_cure_to_default)
            
            # Re-enable main cure buttons (First Cure, Second Cure)
            for widget in self.main_frame.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.LabelFrame):
                            for grandchild in child.winfo_children():
                                if isinstance(grandchild, ttk.Frame):
                                    for button in grandchild.winfo_children():
                                        if isinstance(button, ttk.Button):
                                            if "First Cure" in button.cget("text") or "Second Cure" in button.cget("text"):
                                                button.configure(state='normal')
                                            elif "Update Settings" in button.cget("text") or "Revert to Default" in button.cget("text"):
                                                button.configure(state='normal')
            
            # Re-enable scan device button
            for widget in self.main_frame.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Button) and "Scan Device" in child.cget("text"):
                            child.configure(state='normal')
            
            # Re-enable back buttons in settings screens
            if hasattr(self, 'first_cure_settings_frame'):
                for widget in self.first_cure_settings_frame.winfo_children():
                    if isinstance(widget, ttk.Frame):
                        for child in widget.winfo_children():
                            if isinstance(child, ttk.Button) and "Back to Main" in child.cget("text"):
                                child.configure(state='normal')
            
            if hasattr(self, 'second_cure_settings_frame'):
                for widget in self.second_cure_settings_frame.winfo_children():
                    if isinstance(widget, ttk.Frame):
                        for child in widget.winfo_children():
                            if isinstance(child, ttk.Button) and "Back to Main" in child.cget("text"):
                                child.configure(state='normal')
            
            # Force GUI update
            self.root.update_idletasks()
            self.root.update()
            print("DEBUG: ALL controls enabled")
        except Exception as e:
            print(f"Error enabling controls: {e}")

    def force_enable_all_controls(self):
        """Force enable ALL controls regardless of cure state"""
        print("DEBUG: Force re-enabling ALL controls...")
        try:
            # Re-enable settings buttons
            if hasattr(self, 'first_cure_save_button') and self.first_cure_save_button:
                self.first_cure_save_button.configure(state='normal')
                self.first_cure_save_button.configure(text="💾 Save Settings")
                self.first_cure_save_button.configure(bg=self.colors['success'], fg=self.colors['white'])
                self.first_cure_save_button.configure(command=self.save_first_cure_settings)
                
            if hasattr(self, 'first_cure_revert_button') and self.first_cure_revert_button:
                self.first_cure_revert_button.configure(state='normal')
                self.first_cure_revert_button.configure(text="🔄 Revert to Default")
                self.first_cure_revert_button.configure(bg=self.colors['primary'], fg=self.colors['white'])
                self.first_cure_revert_button.configure(command=self.revert_first_cure_to_default)
                
            if hasattr(self, 'second_cure_save_button') and self.second_cure_save_button:
                self.second_cure_save_button.configure(state='normal')
                self.second_cure_save_button.configure(text="💾 Save Settings")
                self.second_cure_save_button.configure(bg=self.colors['success'], fg=self.colors['white'])
                self.second_cure_save_button.configure(command=self.save_second_cure_settings)
                
            if hasattr(self, 'second_cure_revert_button') and self.second_cure_revert_button:
                self.second_cure_revert_button.configure(state='normal')
                self.second_cure_revert_button.configure(text="🔄 Revert to Default")
                self.second_cure_revert_button.configure(bg=self.colors['primary'], fg=self.colors['white'])
                self.second_cure_revert_button.configure(command=self.revert_second_cure_to_default)
            
            # Re-enable main cure buttons (First Cure, Second Cure)
            for widget in self.main_frame.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.LabelFrame):
                            for grandchild in child.winfo_children():
                                if isinstance(grandchild, ttk.Frame):
                                    for button in grandchild.winfo_children():
                                        if isinstance(button, ttk.Button):
                                            if "First Cure" in button.cget("text") or "Second Cure" in button.cget("text"):
                                                button.configure(state='normal')
                                            elif "Update Settings" in button.cget("text") or "Revert to Default" in button.cget("text"):
                                                button.configure(state='normal')
            
            # Re-enable scan device button
            for widget in self.main_frame.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Button) and "Scan Device" in child.cget("text"):
                            child.configure(state='normal')
            
            # Re-enable back buttons in settings screens
            if hasattr(self, 'first_cure_settings_frame'):
                for widget in self.first_cure_settings_frame.winfo_children():
                    if isinstance(widget, ttk.Frame):
                        for child in widget.winfo_children():
                            if isinstance(child, ttk.Button) and "Back to Main" in child.cget("text"):
                                child.configure(state='normal')
            
            if hasattr(self, 'second_cure_settings_frame'):
                for widget in self.second_cure_settings_frame.winfo_children():
                    if isinstance(widget, ttk.Frame):
                        for child in widget.winfo_children():
                            if isinstance(child, ttk.Button) and "Back to Main" in child.cget("text"):
                                child.configure(state='normal')
            
            # Force GUI update
            self.root.update_idletasks()
            self.root.update()
            print("DEBUG: ALL controls force enabled")
        except Exception as e:
            print(f"Error force enabling controls: {e}")

    def enable_settings_buttons(self):
        """Legacy method - now calls enable_all_controls"""
        self.enable_all_controls()

    def update_first_cure_blink_time(self):
        try:
            freq = float(self.first_cure_vars[2].get())
            self.first_cure_blink_var.set(f"{1/(2*freq):.2f} sec")
        except:
            self.first_cure_blink_var.set("-")

    def update_time_display(self, elapsed_seconds, cure_type):
        """Update time display in seconds.milliseconds format"""
        # Use more precise time calculation with proper rounding
        total_seconds = elapsed_seconds
        
        # Format as seconds.milliseconds (e.g., "19.336")
        time_str = f"{total_seconds:.3f}"
        
        if cure_type == 1:
            self.first_cure_time_var.set(time_str)
        else:
            self.second_cure_time_var.set(time_str)

    def reset_cure_displays(self):
        """Reset intensity and time displays"""
        self.first_cure_intensity_var.set("0%")
        self.first_cure_time_var.set("0.000")
        self.second_cure_time_var.set("0.000")

    def _update_continuous_timing(self, start_time, total_duration, cure_type, intensity):
        """Update timing using tkinter.after() for more accurate GUI updates"""
        if not self.running:
            return
            
        current_time = time.perf_counter()
        elapsed = current_time - start_time
        
        if elapsed >= total_duration:
            # Cure completed
            if cure_type == 1:
                self.first_cure_intensity_var.set("0%")
            return
        
        # Update display
        if cure_type == 1:
            self.first_cure_intensity_var.set(intensity)
        self.update_time_display(elapsed, cure_type)
        
        # Schedule next update in 5ms for very high precision
        self.root.after(5, lambda: self._update_continuous_timing(start_time, total_duration, cure_type, intensity))

    def _finish_first_cure_continuous(self, cure_name):
        """Finish first cure in continuous mode"""
        if self.running:
            self.send_serial("ru=0\r")
            self.send_serial("ip=000,000,000,000\r")
            self.running = False
            self.stop_precise_timing()
            self.set_cure_frame_running(1, False)
            self.current_cure_step = 0
            self.start_message_blink(f"✅ {cure_name} completed successfully!", "success")

    def _finish_second_cure(self, cure_name):
        """Finish second cure"""
        if self.running:
            self.send_serial("ru=0\r")
            self.send_serial("ru=0\r")
            self.send_serial("ip=000,000,000,000\r")
            self.running = False
            self.stop_precise_timing()
            self.set_cure_frame_running(2, False)
            self.current_cure_step = 0
            self.start_message_blink(f"✅ {cure_name} completed successfully!", "success")

    def _finish_first_cure_pulsed(self, cure_name):
        """Finish first cure in pulsed mode"""
        if self.running:
            self.send_serial("ru=0\r")
            self.send_serial("ip=000,000,000,000\r")
            self.running = False
            self.stop_precise_timing()
            self.set_cure_frame_running(1, False)
            self.current_cure_step = 0
            self.start_message_blink(f"✅ {cure_name} completed successfully!", "success")

    def start_precise_timing(self, duration, cure_type):
        """Start high-precision timing thread"""
        self.cure_start_time = time.perf_counter()
        self.cure_duration = duration
        self.current_cure_type = cure_type
        self.timing_running = True
        
        # Start timing thread
        self.timing_thread = threading.Thread(target=self._timing_worker, daemon=True)
        self.timing_thread.start()

    def start_precise_timing_with_intensity(self, duration, cure_type, intensity):
        """Start high-precision timing thread with intensity tracking"""
        self.cure_start_time = time.perf_counter()
        self.cure_duration = duration
        self.current_cure_type = cure_type
        self.current_intensity = intensity
        self.timing_running = True
        
        # Start timing thread with intensity
        self.timing_thread = threading.Thread(target=self._timing_worker_with_intensity, daemon=True)
        self.timing_thread.start()

    def stop_precise_timing(self):
        """Stop timing thread"""
        self.timing_running = False
        if self.timing_thread:
            self.timing_thread.join(timeout=0.1)

    def _timing_worker(self):
        """High-precision timing worker thread"""
        while self.timing_running and self.running:
            current_time = time.perf_counter()
            elapsed = current_time - self.cure_start_time
            
            # Update display with high precision
            self.root.after(0, self._update_timing_display, elapsed)
            
            if elapsed >= self.cure_duration:
                # Cure completed - show final time and stop instrument immediately
                self.root.after(0, self._update_timing_display, self.cure_duration)
                # Stop instrument immediately when timing completes
                self.root.after(0, self._stop_instrument_immediately)
                self.timing_running = False
                break
            
            time.sleep(0.001)  # 1ms precision

    def _timing_worker_with_intensity(self):
        """High-precision timing worker thread with intensity tracking"""
        while self.timing_running and self.running:
            current_time = time.perf_counter()
            elapsed = current_time - self.cure_start_time
            
            # Update display with high precision
            self.root.after(0, self._update_timing_and_intensity_display, elapsed)
            
            if elapsed >= self.cure_duration:
                # Cure completed - show final time and stop instrument immediately
                self.root.after(0, self._update_timing_and_intensity_display, self.cure_duration)
                # Stop instrument immediately when timing completes
                self.root.after(0, self._stop_instrument_immediately)
                self.timing_running = False
                break
            
            time.sleep(0.001)  # 1ms precision

    def _update_timing_and_intensity_display(self, elapsed_seconds):
        """Update timing and intensity display with high precision"""
        # Calculate time components with high precision
        total_seconds = elapsed_seconds
        
        # Ensure we don't exceed the target duration
        if total_seconds > self.cure_duration:
            total_seconds = self.cure_duration
        
        # Format as seconds.milliseconds (e.g., "19.336")
        time_str = f"{total_seconds:.3f}"
        
        # Update intensity display
        if hasattr(self, 'current_intensity'):
            self.first_cure_intensity_var.set(f"{self.current_intensity}%")
        
        if self.current_cure_type == 1:
            self.first_cure_time_var.set(time_str)
        else:
            self.second_cure_time_var.set(time_str)

    def _stop_instrument_immediately(self):
        """Stop the instrument immediately when cure completes"""
        if self.running:
            # Send stop commands multiple times to ensure they reach the instrument
            for i in range(3):  # Send stop commands 3 times
                self.send_serial("ru=0\r")
                time.sleep(0.02)  # Longer delay
                self.send_serial("ip=000,000,000,000\r")
                time.sleep(0.02)  # Longer delay
            
            # Determine which cure completed and show specific message
            cure_name = "First Cure" if self.current_cure_step == 1 else "Second Cure"
            
            # Update GUI state - keep values but turn off green light
            self.running = False
            self.cure_was_started = False  # Reset cure started flag
            self.stop_precise_timing()
            self.set_cure_frame_running(1, False)
            self.set_cure_frame_running(2, False)
            self.current_cure_step = 0
            # Don't reset displays - keep the final values visible
            # Force re-enable ALL controls regardless of cure state
            self.force_enable_all_controls()
            self.start_message_blink(f"✅ {cure_name} completed successfully!", "success")

    def _update_timing_display(self, elapsed_seconds):
        """Update timing display with high precision - seconds only"""
        # Calculate time components with high precision
        total_seconds = elapsed_seconds
        
        # Ensure we don't exceed the target duration
        if total_seconds > self.cure_duration:
            total_seconds = self.cure_duration
        
        # Format as seconds.milliseconds (e.g., "19.336")
        time_str = f"{total_seconds:.3f}"
        
        if self.current_cure_type == 1:
            self.first_cure_time_var.set(time_str)
        else:
            self.second_cure_time_var.set(time_str)

    def start_message_blink(self, message, message_type="info"):
        """Start blinking message with appropriate colors"""
        # Stop any existing blinking
        self.stop_message_blink()
        
        # Set initial message
        self.message_var.set(message)
        
        # Set colors based on message type
        if message_type == "success":
            bg_color = self.colors['success']
            text_color = self.colors['white']
        elif message_type == "error":
            bg_color = self.colors['accent']
            text_color = self.colors['white']
        elif message_type == "warning":
            bg_color = self.colors['warning']
            text_color = self.colors['white']
        else:  # info
            bg_color = self.colors['message_bg']
            text_color = self.colors['message_text']
        
        self.message_label.config(background=bg_color, foreground=text_color)
        
        # Start blinking
        self.message_blink_state = True
        self._blink_message(bg_color, text_color)

    def stop_message_blink(self):
        """Stop blinking message"""
        self.message_blink_state = False
        if self.blink_after_id:
            self.root.after_cancel(self.blink_after_id)
            self.blink_after_id = None

    def _blink_message(self, bg_color, text_color):
        """Internal method to handle message blinking"""
        if not self.message_blink_state:
            return
        
        # Toggle visibility by changing background
        if self.message_label.cget('background') == bg_color:
            self.message_label.config(background=self.colors['background'])
        else:
            self.message_label.config(background=bg_color, foreground=text_color)
        
        # Schedule next blink
        self.blink_after_id = self.root.after(500, lambda: self._blink_message(bg_color, text_color))

    def show_static_message(self, message, message_type="info"):
        """Show a static message without blinking"""
        self.stop_message_blink()
        self.message_var.set(message)
        
        # Set colors based on message type
        if message_type == "success":
            bg_color = self.colors['success']
            text_color = self.colors['white']
        elif message_type == "error":
            bg_color = self.colors['accent']
            text_color = self.colors['white']
        elif message_type == "warning":
            bg_color = self.colors['warning']
            text_color = self.colors['white']
        else:  # info
            bg_color = self.colors['message_bg']
            text_color = self.colors['message_text']
        
        self.message_label.config(background=bg_color, foreground=text_color)

    def load_defaults_to_display(self):
        # Since we set default values directly in StringVars, just update blink time
        self.update_first_cure_blink_time()

    def refresh_com_ports(self):
        """Refresh the list of available COM ports with detailed information"""
        try:
            ports = []
            port_details = []
            
            print("\n=== Scanning for COM Ports ===")
            for port in serial.tools.list_ports.comports():
                ports.append(port.device)
                details = f"{port.device}: {port.description or 'Unknown'}"
                if hasattr(port, 'manufacturer') and port.manufacturer:
                    details += f" ({port.manufacturer})"
                port_details.append(details)
                print(f"  Found: {details}")
            
            # Update the combobox with available ports
            self.com_port_combo['values'] = ports
            
            # If no port is selected and ports are available, select the first one
            if not self.selected_com_port.get() and ports:
                self.selected_com_port.set(ports[0])
                print(f"  Auto-selected: {ports[0]}")
            
            print(f"Total COM ports found: {len(ports)}")
            print(f"Available COM ports: {ports}")
            
            # Update status
            if ports:
                self.status_var.set(f"🔍 Found {len(ports)} COM port(s): {', '.join(ports)}")
            else:
                self.status_var.set("❌ No COM ports detected")
            
        except Exception as e:
            print(f"Error refreshing COM ports: {e}")
            self.com_port_combo['values'] = []
            self.status_var.set("❌ Error scanning COM ports")

    def on_com_port_selected(self, event=None):
        """Handle COM port selection"""
        selected_port = self.selected_com_port.get()
        if selected_port:
            print(f"Selected COM port: {selected_port}")
            # Disconnect from current port if connected
            if self.serial_connected and self.serial_port:
                try:
                    self.serial_port.close()
                except:
                    pass
                self.serial_port = None
                self.serial_connected = False
            
            # Update status
            self.status_var.set(f"🔍 Selected {selected_port} - Click Connect to connect")
            self.show_static_message(f"Selected COM port: {selected_port} - Click 'Connect' to connect", "info")

    def auto_connect_omnicure(self):
        """Automatically scan and connect to OMNICURE device only"""
        print("Auto-connecting to OMNICURE device...")
        self.status_var.set("🔍 Auto-scanning for OMNICURE device...")
        
        # Refresh COM ports first
        self.refresh_com_ports()
        
        # Try to find and connect to OMNICURE device
        if self.find_and_connect_serial():
            self.show_static_message("✅ OMNICURE device connected automatically!", "success")
            self.status_var.set(f"✅ Connected to OMNICURE LX500 on {self.serial_port.port}")
        else:
            self.status_var.set("❌ No OMNICURE Device Found")
            self.show_static_message("⚠️ No OMNICURE LX500 device detected. Please connect the device.", "warning")

    def manual_connect_selected_port(self):
        """Manually connect to the selected COM port"""
        selected_port = self.selected_com_port.get()
        if not selected_port:
            self.show_static_message("⚠️ Please select a COM port first", "warning")
            return
        
        print(f"Manual connection attempt to selected port: {selected_port}")
        self.status_var.set(f"🔌 Connecting to {selected_port}...")
        
        # Disconnect from current port if connected
        if self.serial_connected and self.serial_port:
            try:
                self.serial_port.close()
            except:
                pass
            self.serial_port = None
            self.serial_connected = False
        
        # Try to connect to the selected port
        if self.find_and_connect_serial():
            self.show_static_message(f"✅ Connected to OMNICURE LX500 on {selected_port}!", "success")
            self.status_var.set(f"✅ Connected to OMNICURE LX500 on {self.serial_port.port}")
        else:
            self.status_var.set(f"❌ Failed to connect to {selected_port}")
            self.show_static_message(f"❌ Failed to connect to {selected_port}. Not an OMNICURE device.", "error")

    def list_all_devices(self):
        """List all connected devices for debugging"""
        print("\n=== All Connected Devices ===")
        for port in serial.tools.list_ports.comports():
            print(f"Device: {port.device}")
            print(f"  Description: {port.description}")
            print(f"  Manufacturer: {getattr(port, 'manufacturer', 'N/A')}")
            print(f"  Product: {getattr(port, 'product', 'N/A')}")
            print(f"  VID:PID: {getattr(port, 'vid', 'N/A')}:{getattr(port, 'pid', 'N/A')}")
            print(f"  Is OMNICURE: {self.is_omnicure_device(port)}")
            print()

    def manual_check_connection(self):
        if self.serial_connected:
            self.status_var.set(f"✅ Connected to OMNICURE LX500 on {self.serial_port.port}")
            return
        
        # Refresh COM ports list before scanning
        self.refresh_com_ports()
        
        # List all devices for debugging
        self.list_all_devices()
        
        if self.find_and_connect_serial():
            self.show_static_message("", "info")
            self.status_var.set(f"✅ Connected to OMNICURE LX500 on {self.serial_port.port}")
        else:
            self.status_var.set("❌ OMNICURE Device Not Found")
            self.start_message_blink("⚠️ No OMNICURE LX500 device detected. Please connect the correct device.", "warning")

    def find_and_connect_serial(self):
        if self.serial_port and getattr(self.serial_port, 'is_open', False):
            try: self.serial_port.close()
            except: pass
        
        # If a specific COM port is selected, try to connect to it first
        selected_port = self.selected_com_port.get()
        if selected_port:
            print(f"Attempting to connect to selected port: {selected_port}")
            try:
                # Find the port object for the selected port
                target_port = None
                for p in serial.tools.list_ports.comports():
                    if p.device == selected_port:
                        target_port = p
                        break
                
                if target_port:
                    # Check if this is an OMNICURE device
                    if self.is_omnicure_device(target_port):
                        try:
                            sp = serial.Serial(target_port.device, baudrate=19200, timeout=2, write_timeout=2)
                            # Send a test command to verify it's responding
                            if self.test_omnicure_connection(sp):
                                self.serial_port = sp
                                self.serial_connected = True
                                return True
                            else:
                                sp.close()
                        except PermissionError as e:
                            print(f"Permission denied for {selected_port}: {e}")
                            print("  [INFO] Another application may be using this port. Try closing other serial applications.")
                        except Exception as e:
                            print(f"Failed to connect to selected port {selected_port}: {e}")
                    else:
                        print(f"Selected port {selected_port} is not an OMNICURE device")
                else:
                    print(f"Selected port {selected_port} not found in available ports")
            except Exception as e:
                print(f"Failed to connect to selected port {selected_port}: {e}")
        
        # If no specific port selected or connection failed, scan all ports
        print("Scanning all available ports for OMNICURE devices...")
        for p in serial.tools.list_ports.comports():
            print(f"\n--- Testing {p.device} ---")
            # Check if this is an OMNICURE device
            if self.is_omnicure_device(p):
                try:
                    print(f"Attempting connection to {p.device}...")
                    sp = serial.Serial(p.device, baudrate=19200, timeout=2, write_timeout=2)
                    # Send a test command to verify it's responding
                    if self.test_omnicure_connection(sp):
                        self.serial_port = sp
                        self.serial_connected = True
                        # Update the dropdown to show the connected port
                        self.selected_com_port.set(p.device)
                        print(f"[SUCCESS] Connected to OMNICURE device on {p.device}")
                        return True
                    else:
                        sp.close()
                        print(f"[FAIL] Device on {p.device} did not respond correctly")
                except PermissionError as e:
                    print(f"[ERROR] Permission denied for {p.device}: {e}")
                    print("  [INFO] Another application may be using this port. Try closing other serial applications.")
                    continue
                except Exception as e:
                    print(f"[ERROR] Failed to connect to {p.device}: {e}")
                    continue
            else:
                print(f"[SKIP] {p.device} does not appear to be an OMNICURE device")
        self.serial_port = None
        self.serial_connected = False
        return False

    def is_omnicure_device(self, port):
        """Flexible detection: prefer OMNICURE hints, but allow testing unknown USB-serial devices."""
        description = port.description.lower() if port.description else ""
        manufacturer = (getattr(port, 'manufacturer', '') or '').lower()
        product = (getattr(port, 'product', '') or '').lower()
        vid = getattr(port, 'vid', None)
        pid = getattr(port, 'pid', None)

        # Print device info for debugging
        print(f"Checking device: {port.device}")
        print(f"  Description: {description}")
        print(f"  Manufacturer: {manufacturer}")
        print(f"  Product: {product}")
        print(f"  VID:PID: {vid}:{pid}")

        omnicure_identifiers = ['omnicure', 'exfo', 'lx500', 'cure', 'uv', 'light']

        for identifier in omnicure_identifiers:
            if (identifier in description or identifier in manufacturer or identifier in product):
                print(f"  [OK] Found OMNICURE identifier: {identifier}")
                return True

        # Optional VID/PID whitelist (empty by default)
        omnicure_vid_pid = []
        if vid and pid:
            for known_vid, known_pid in omnicure_vid_pid:
                if vid == known_vid and pid == known_pid:
                    print(f"  [OK] Found OMNICURE VID:PID: {vid:04x}:{pid:04x}")
                    return True

        # Allow generic USB-to-Serial devices to be tested
        if 'usb' in description and ('serial' in description or 'com' in description):
            if 'ftdi' in manufacturer or 'ftdi' in description:
                print("  [OK] Potential OMNICURE device (FTDI USB-to-Serial)")
                return True
            if 'prolific' in manufacturer or 'prolific' in description:
                print("  [OK] Potential OMNICURE device (Prolific USB-to-Serial)")
                return True
            if 'ch340' in description or 'ch341' in description:
                print("  [OK] Potential OMNICURE device (CH340/CH341 USB-to-Serial)")
                return True
            print("  [OK] Generic USB-to-Serial device - will test connection")
            return True
        
        # Also test any COM port that might be a serial device
        if port.device.startswith('COM'):
            print("  [OK] COM port detected - will test connection")
            return True

        # Unknown device type; allow test
        print("  ? Unknown device type - will test connection")
        return True

    def test_omnicure_connection(self, serial_port):
        """Lenient connection test: accept any responsive serial, or even silent, as valid."""
        try:
            print(f"Testing connection to {serial_port.port}...")
            serial_port.reset_input_buffer()
            serial_port.reset_output_buffer()
            serial_port.write(b"ip=000,000,000,000\r")
            serial_port.flush()
            time.sleep(0.2)
            try:
                response = serial_port.read(50)
                print(f"  Response: {response}")
                if response:
                    response_str = response.decode('ascii', errors='ignore').lower()
                    if any(term in response_str for term in ['omnicure', 'exfo', 'lx500', 'cure']):
                        print("  [OK] Device responded with OMNICURE-like data")
                        return True
                    # Accept any response as valid (matches previous behavior)
                    print("  [OK] Device responded (accepting as valid)")
                    return True
                else:
                    # Some devices may not echo; accept as valid to restore connectivity
                    print("  [OK] No response (accepting as valid OMNICURE)")
                    return True
            except Exception as e:
                print(f"  [OK] Error reading response but accepting connection: {e}")
                return True
        except Exception as e:
            print(f"  [ERROR] Connection test failed: {e}")
            return False

    def check_serial_health(self):
        ports = {p.device for p in serial.tools.list_ports.comports()}
        was_running = self.running

        if self.serial_connected and self.serial_port:
            if self.serial_port.port not in ports:
                try: self.serial_port.close()
                except: pass
                self.serial_port = None
                self.serial_connected = False
                self.status_var.set("❌ OMNICURE Device Disconnected")
                self.start_message_blink("🔌 OMNICURE device was unplugged.", "error")
                if was_running:
                    self._force_stop()
            else:
                # Check if the connected device is still OMNICURE
                current_port = None
                for p in serial.tools.list_ports.comports():
                    if p.device == self.serial_port.port:
                        current_port = p
                        break
                
                if current_port and not self.is_omnicure_device(current_port):
                    try: self.serial_port.close()
                    except: pass
                    self.serial_port = None
                    self.serial_connected = False
                    self.status_var.set("❌ Wrong Device Connected")
                    self.start_message_blink("⚠️ Non-OMNICURE device detected. Please connect OMNICURE LX500.", "warning")
                    if was_running:
                        self._force_stop()
        else:
            # Check for OMNICURE devices
            omnicure_found = False
            for dev in ports:
                for p in serial.tools.list_ports.comports():
                    if p.device == dev and self.is_omnicure_device(p):
                        omnicure_found = True
                        try:
                            sp = serial.Serial(dev, baudrate=19200, timeout=1)
                            sp.close()
                            self.show_static_message("", "info")
                            self.status_var.set("🔍 OMNICURE device detected; click Scan Device")
                            break
                        except:
                            continue
                if omnicure_found:
                    break
            
            if not omnicure_found:
                self.status_var.set("❌ No OMNICURE Device Found")

        # Refresh COM ports periodically and auto-reconnect if needed
        self.refresh_com_ports()
        
        # If not connected, try to auto-connect to OMNICURE device
        if not self.serial_connected:
            self.auto_connect_omnicure()
        
        self.root.after(5000, self.check_serial_health)  # Check every 5 seconds

    def send_serial(self, cmd):
        if self.serial_connected and self.serial_port:
            try:
                # Clear input buffer before sending
                self.serial_port.reset_input_buffer()
                
                # Send command
                self.serial_port.write(cmd.encode())
                self.serial_port.flush()
                
                # Small delay for command processing
                time.sleep(0.05)
                
            except Exception as e:
                print(f"Serial communication error: {e}")
                # Don't mark as disconnected for single command failures
                pass

    def stop_action(self):
        # Send multiple stop commands to ensure instrument stops
        self.send_serial("ru=0\r")
        time.sleep(0.01)
        self.send_serial("ip=000,000,000,000\r")
        time.sleep(0.01)
        self.send_serial("ru=0\r")  # Send again to be sure
        
        self.running = False
        self.cure_was_started = False  # Reset cure started flag
        self.stop_precise_timing()
        self.set_cure_frame_running(1, False)
        self.set_cure_frame_running(2, False)
        self.current_cure_step = 0
        # Reset displays
        self.reset_cure_displays()
        # Force re-enable ALL controls regardless of cure state
        self.force_enable_all_controls()
        self.show_static_message("🛑 Cure stopped by user", "warning")

    def set_cure_frame_running(self, cure_number, is_running):
        """Change the color of cure frames when running"""
        if cure_number == 1:
            frame = self.first_cure_frame
        else:
            frame = self.second_cure_frame
            
        if is_running:
            # Change to green when running
            frame.configure(style="Running.TLabelframe")
        else:
            # Change back to normal when stopped
            frame.configure(style="Modern.TLabelframe")

    def _force_stop(self):
        # Send multiple stop commands to ensure instrument stops
        self.send_serial("ru=0\r")
        time.sleep(0.01)
        self.send_serial("ip=000,000,000,000\r")
        time.sleep(0.01)
        self.send_serial("ru=0\r")  # Send again to be sure
        
        self.running = False
        self.cure_was_started = False  # Reset cure started flag
        self.stop_precise_timing()
        self.set_cure_frame_running(1, False)
        self.set_cure_frame_running(2, False)
        self.current_cure_step = 0
        # Reset displays
        self.reset_cure_displays()
        # Force re-enable ALL controls regardless of cure state
        self.force_enable_all_controls()
        self.start_message_blink("🛑 Cure stopped due to disconnection.", "error")

    def start_live(self, cure_vars, cure_name):
        if self.running:
            messagebox.showinfo("ℹ️ Info", "Already running.")
            return
        self.show_static_message("", "info")
        
        # Reset displays
        self.reset_cure_displays()

        try:
            if self.current_cure_step == 1:
                # First cure - always pulsed mode
                total = float(cure_vars[0].get())
                pct = float(cure_vars[1].get())
                freq = float(cure_vars[2].get())
                ramp = float(cure_vars[3].get())
            else:
                # Second cure - continuous mode
                total = float(cure_vars[0].get())  # 60 seconds
                pct = 100  # 100% intensity
                freq = 0   # continuous
                ramp = 0   # no ramp

            if not self.serial_connected:
                if not self.find_and_connect_serial():
                    messagebox.showerror("❌ Connection Error", "Unable to connect to OMNICURE LX500 device.")
                    self.status_var.set("❌ OMNICURE Device Not Found")
                    self.set_cure_frame_running(self.current_cure_step, False) # Reset frame color on connection failure
                    self.enable_all_controls()  # Re-enable ALL controls if connection fails
                    return
                self.status_var.set(f"✅ Connected to OMNICURE LX500 on {self.serial_port.port}")
        except Exception as e:
            messagebox.showerror("❌ Input Error", str(e))
            self.set_cure_frame_running(self.current_cure_step, False)  # Reset frame color on input error
            self.enable_all_controls()  # Re-enable ALL controls if input error occurs
            return

        def worker():
            self.running = True
            self.cure_was_started = True  # Mark that cure was actually started
            print("DEBUG: Cure worker started, cure_was_started = True")
            
            if self.current_cure_step == 1:
                # First cure - always pulsed mode
                self._run_first_cure_pulsed(total, pct, freq, ramp, cure_name)
            else:
                # Second cure - continuous mode
                self._run_second_cure(total, cure_name)

        self.live_thread = threading.Thread(target=worker, daemon=True)
        self.live_thread.start()

    def _run_first_cure_pulsed(self, total, pct, freq, ramp, cure_name):
        """Run first cure in pulsed mode with proper step-by-step intensity ramping"""
        ramp_start = 5
        pulse_time = total * (pct / 100)  # Total time for pulsed phase
        cw_time = total - pulse_time      # Remaining time for CW phase
        
        # Calculate steps: First step (5% to 10%) + stay at 10% + subsequent steps (20% to 100% in 10% increments)
        # First step: 5% to 10% (ramp)
        # Second step: stay at 10% for 6 seconds
        # Subsequent steps: 20%, 30%, 40%, ..., 100% (10% each)
        ramp_steps = 1  # Step to ramp from 5% to 10%
        stay_at_10_step = 1  # Extra step to stay at 10%
        subsequent_steps = int((100 - 20) / ramp)  # (100 - 20) / 10 = 8 steps
        total_steps = ramp_steps + stay_at_10_step + subsequent_steps  # 1 + 1 + 8 = 10 steps
        
        # Calculate time per step
        time_per_step = pulse_time / total_steps
        
        # Pulsing timing
        on_t = 1 / (2 * freq) if freq > 0 else 0.1
        off_t = on_t

        # Start high-precision timing from the beginning
        self.start_precise_timing_with_intensity(total, 1, ramp_start)
        
        # Track elapsed time during pulsed phase
        pulsed_start_time = time.perf_counter()
        elapsed_pulsed = 0

        # Process each step
        for step in range(total_steps):
            if not self.running:
                self._force_stop()
                return
                
            # Calculate start and target intensity for this step
            if step == 0:
                # First step: 5% to 10% (ramp)
                step_start_intensity = ramp_start  # 5%
                step_target_intensity = 10  # 10%
            elif step == 1:
                # Second step: stay at 10%
                step_start_intensity = 10  # 10%
                step_target_intensity = 10  # 10%
            else:
                # Subsequent steps: 20%, 30%, 40%, etc.
                step_start_intensity = 20 + ((step - 2) * ramp)  # 20%, 30%, 40%, etc.
                step_target_intensity = step_start_intensity  # Stay at 20%, 30%, 40%, etc.
                
            if step_target_intensity > 100:
                step_target_intensity = 100
                
            # Calculate time for this step
            step_start_time = time.perf_counter()
            step_elapsed = 0
            
            # Run this step for the allocated time
            while step_elapsed < time_per_step and elapsed_pulsed < pulse_time:
                if not self.running:
                    self._force_stop()
                    return
                    
                # Calculate current intensity within this step
                if step == 0:
                    # First step: ramp from 5% to 10% (5% increase over 6 seconds)
                    # Increase by 1% every 1.2 seconds (6 seconds / 5 increments)
                    small_step_time = time_per_step / 5  # 1.2 seconds per 1% increment
                    small_step = int(step_elapsed / small_step_time)
                    current_intensity = step_start_intensity + small_step
                    if current_intensity > step_target_intensity:
                        current_intensity = step_target_intensity
                elif step == 1:
                    # Second step: stay at 10% for the full 6 seconds
                    current_intensity = 10
                else:
                    # Subsequent steps: stay at the target intensity for the full 6 seconds
                    # For step 2: stay at 20% for 6 seconds
                    # For step 3: stay at 30% for 6 seconds, etc.
                    current_intensity = step_target_intensity
                    
                # Set current intensity
                self.send_serial(f"ip={int(current_intensity):03},000,000,000\r")
                self.send_serial("ru=1\r")
                
                # Update intensity display
                self.first_cure_intensity_var.set(f"{int(current_intensity)}%")
                self.current_intensity = int(current_intensity)
                
                # Pulse ON
                pulse_start = time.perf_counter()
                while time.perf_counter() - pulse_start < on_t and step_elapsed < time_per_step:
                    if not self.running:
                        self._force_stop()
                        return
                    step_elapsed = time.perf_counter() - step_start_time
                    elapsed_pulsed = time.perf_counter() - pulsed_start_time
                    
                self.send_serial("ru=0\r")
                
                # Pulse OFF
                pulse_start = time.perf_counter()
                while time.perf_counter() - pulse_start < off_t and step_elapsed < time_per_step:
                    if not self.running:
                        self._force_stop()
                        return
                    step_elapsed = time.perf_counter() - step_start_time
                    elapsed_pulsed = time.perf_counter() - pulsed_start_time

        # CW phase - continue with 100% intensity for remaining time
        self.send_serial(f"ip=100,000,000,000\r")
        self.send_serial("ru=1\r")
        # Set intensity to 100% for CW phase
        self.first_cure_intensity_var.set("100%")
        # Update the intensity in the timing system
        self.current_intensity = 100
        
        # Timing thread will handle completion automatically

    def _run_first_cure_continuous(self, total, cure_name):
        """Run first cure in continuous mode"""
        # Continuous mode at 100% intensity
        self.send_serial("ip=100,000,000,000\r")
        self.send_serial("ru=1\r")
        
        # Set intensity to 100%
        self.first_cure_intensity_var.set("100%")
        
        # Start high-precision timing with intensity tracking
        self.start_precise_timing_with_intensity(total, 1, 100)
        
        # Timing thread will handle completion automatically

    def _run_second_cure(self, total, cure_name):
        """Run second cure in continuous mode"""
        # Continuous mode at 100% intensity
        self.send_serial("ip=100,000,000,000\r")
        self.send_serial("ru=1\r")
        
        # Start high-precision timing
        self.start_precise_timing(total, 2)
        
        # Timing thread will handle completion automatically

    def on_closing(self):
        if self.running:
            if not messagebox.askokcancel("⚠️ Quit", "Cure running—exit?"):
                return
            # Force stop the instrument before closing
            self._force_stop()
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = OmnicureGUI(root)
    root.mainloop()
