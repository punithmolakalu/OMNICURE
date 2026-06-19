import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import serial  # type: ignore
import serial.tools.list_ports  # type: ignore
import threading
import time
import json
import os
import sys
import ctypes

class OmnicureGUI:
    PASSWORD = "1234@"  # password required for second cure settings
    FIRST_CURE_START_INTENSITY = 1

    def __init__(self, root):
        self.root = root
        self.root.title("OMNICURE LX500")
        self.root.geometry("1200x750")
        self.root.resizable(True, True)
        self.root.configure(bg='#ffffff')  # Light background
        self.root.lift()  # Bring window to front
        self.root.attributes('-topmost', True)  # Keep on top initially
        self.root.after_idle(lambda: self.root.attributes('-topmost', False))  # Then allow normal behavior
        
        self.app_logo_image = None

        # Modern styling
        self.setup_styles()
        self._setup_app_icon()

        self.serial_port = None
        self.serial_connected = False
        self.running = False
        self.live_thread = None
        self.cure_finishing = False
        self.current_cure_step = 0  # 0=none, 1=first cure, 2=second cure
        self.message_blink_state = False  # For blinking messages
        self.blink_after_id = None  # To cancel blinking
        
        # High-precision timing system
        self.timing_thread = None
        self.timing_running = False
        self.cure_start_time = None
        self.cure_duration = None
        self.current_cure_type = None

        # First cure settings (lensing station step workflow)
        self.first_cure_settings_file = self._get_lensing_settings_path()
        self.connection_settings_file = self._get_connection_settings_path()
        self._loading_first_cure_settings = False
        self.first_cure_total_var = tk.StringVar(value="")
        self.first_cure_stay_var = tk.StringVar(value="")
        self.first_cure_steps_summary_var = tk.StringVar(value="")
        self.first_cure_step_vars = []
        self.first_cure_step_rows = []
        self.first_cure_steps_table = None
        self.first_cure_step_count_var = tk.StringVar(value="(1)")
        self.first_cure_add_step_button = None
        self.first_cure_remove_step_button = None
        self.first_cure_save_button = None
        self.first_cure_total_entry = None
        self.first_cure_intensity_var = tk.StringVar(value="0%")
        self.first_cure_time_var = tk.StringVar(value="0.000")
        self._init_first_cure_settings()
        
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

    def _get_asset_path(self, filename):
        if getattr(sys, 'frozen', False):
            base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, filename)

    def _setup_app_icon(self):
        if sys.platform == 'win32':
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    'Metrohm.OMNICURE.LX500.Lensing'
                )
            except Exception:
                pass

        icon_path = self._get_asset_path("lx500_icon.png")
        if os.path.exists(icon_path):
            try:
                self.app_logo_image = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, self.app_logo_image)
            except Exception:
                self.app_logo_image = None

        if sys.platform == 'win32':
            ico_path = self._get_asset_path("lx500_icon.ico")
            if os.path.exists(ico_path):
                try:
                    self.root.iconbitmap(default=ico_path)
                except Exception:
                    pass

    def _get_lensing_settings_path(self):
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "lensing_gui_settings.json")

    def _get_connection_settings_path(self):
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "connection_settings.json")

    def _load_saved_com_port(self):
        try:
            if os.path.exists(self.connection_settings_file):
                with open(self.connection_settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return str(data.get("saved_com_port", "")).strip()
        except Exception:
            pass
        return ""

    def _save_com_port_to_file(self, port):
        try:
            with open(self.connection_settings_file, "w", encoding="utf-8") as f:
                json.dump({"saved_com_port": port}, f, indent=2)
        except Exception as e:
            messagebox.showerror("❌ Error", f"Could not save COM port: {e}")
            return False
        return True

    def save_com_port_settings(self):
        port = self.selected_com_port.get().strip()
        if not port:
            messagebox.showwarning("⚠️ No Port Selected", "Please select a COM port first.")
            return
        if self._save_com_port_to_file(port):
            messagebox.showinfo("✅ Saved", f"COM port {port} saved. App will use this port on startup.")

    def _default_first_cure_step_data(self):
        return {
            "intensity": str(self.FIRST_CURE_START_INTENSITY),
            "on_time": "",
            "off_time": "",
            "increment": "1",
        }

    def _init_first_cure_settings(self):
        self._loading_first_cure_settings = True
        self._load_first_cure_settings_from_file()
        self._build_first_cure_step_vars(self._stored_first_cure_steps)
        self._loading_first_cure_settings = False
        self._recalculate_computed_stay()
        self._update_first_cure_display_summary()

    def _load_first_cure_settings_from_file(self):
        default_steps = [self._default_first_cure_step_data()]
        try:
            if os.path.exists(self.first_cure_settings_file):
                with open(self.first_cure_settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                total = str(data.get("total_cure_time", "")).strip()
                steps = data.get("steps", default_steps) or default_steps
                cleaned = []
                for step in steps:
                    cleaned.append({
                        "intensity": str(step.get("intensity", "")).strip(),
                        "on_time": str(step.get("on_time", "")).strip(),
                        "off_time": str(step.get("off_time", "")).strip(),
                        "increment": str(step.get("increment", "1")).strip() or "1",
                    })
                if not cleaned:
                    cleaned = default_steps
                cleaned[0]["intensity"] = str(self.FIRST_CURE_START_INTENSITY)
                self.first_cure_total_var.set(total)
                self._stored_first_cure_steps = cleaned
                return
        except Exception:
            pass
        self.first_cure_total_var.set("")
        self._stored_first_cure_steps = default_steps

    def _build_first_cure_step_vars(self, steps_data):
        self.first_cure_step_vars = []
        for step in steps_data:
            step_vars = {
                "intensity": tk.StringVar(value=step.get("intensity", "")),
                "on_time": tk.StringVar(value=step.get("on_time", "")),
                "off_time": tk.StringVar(value=step.get("off_time", "")),
                "increment": tk.StringVar(value=step.get("increment", "1") or "1"),
            }
            step_vars["intensity"].trace_add("write", self._on_first_cure_setting_changed)
            step_vars["on_time"].trace_add("write", self._on_first_cure_setting_changed)
            step_vars["off_time"].trace_add("write", self._on_first_cure_setting_changed)
            step_vars["increment"].trace_add("write", self._on_first_cure_setting_changed)
            self.first_cure_step_vars.append(step_vars)
        if self.first_cure_step_vars:
            self.first_cure_step_vars[0]["intensity"].set(str(self.FIRST_CURE_START_INTENSITY))
        self.first_cure_total_var.trace_add("write", self._on_first_cure_setting_changed)

    def _on_first_cure_setting_changed(self, *_args):
        if self._loading_first_cure_settings:
            return
        if self.first_cure_step_vars:
            self.first_cure_step_vars[0]["intensity"].set(str(self.FIRST_CURE_START_INTENSITY))
        self._recalculate_computed_stay()
        self._persist_first_cure_settings()
        self._update_first_cure_display_summary()

    def _persist_first_cure_settings(self):
        steps = []
        for step in self.first_cure_step_vars:
            steps.append({
                "intensity": step["intensity"].get().strip(),
                "on_time": step["on_time"].get().strip(),
                "off_time": step["off_time"].get().strip(),
                "increment": step["increment"].get().strip() or "1",
            })
        if steps:
            steps[0]["intensity"] = str(self.FIRST_CURE_START_INTENSITY)
        data = {
            "total_cure_time": self.first_cure_total_var.get().strip(),
            "steps": steps,
        }
        try:
            with open(self.first_cure_settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _format_first_cure_time_value(self, seconds):
        if abs(seconds - round(seconds)) < 0.0005:
            return str(int(round(seconds)))
        return f"{seconds:.3f}".rstrip("0").rstrip(".")

    def _parse_first_cure_steps_only(self):
        if not self.first_cure_step_vars:
            raise ValueError("Please configure at least one cure step.")

        steps = []
        start_intensity = self.FIRST_CURE_START_INTENSITY
        for i, step in enumerate(self.first_cure_step_vars, start=1):
            intensity_raw = step["intensity"].get().strip()
            on_raw = step["on_time"].get().strip()
            off_raw = step["off_time"].get().strip()
            inc_raw = step["increment"].get().strip() or "1"
            if not on_raw or not off_raw:
                raise ValueError(f"Please enter ON and OFF time for step {i}.")
            if i > 1 and not intensity_raw:
                raise ValueError(f"Please enter intensity for step {i}.")
            intensity = float(intensity_raw if intensity_raw else str(start_intensity))
            on_time = float(on_raw)
            off_time = float(off_raw)
            increment = float(inc_raw)
            if on_time <= 0 or off_time <= 0 or increment <= 0:
                raise ValueError(f"Step {i} values must be greater than zero.")
            steps.append({
                "intensity": intensity,
                "on_time": on_time,
                "off_time": off_time,
                "increment": increment,
            })

        steps.sort(key=lambda s: s["intensity"])
        if steps[0]["intensity"] != start_intensity:
            raise ValueError(f"First step intensity must be {start_intensity}%.")
        for i in range(1, len(steps)):
            if steps[i]["intensity"] <= steps[i - 1]["intensity"]:
                raise ValueError(
                    f"Step intensities must increase (e.g. {start_intensity}, 10, 20)."
                )
        return steps

    def _estimate_ramp_pulse_time(self, steps):
        sequence = self._build_first_cure_pulse_sequence(steps)
        return sum(on_t + off_t for _, on_t, off_t in sequence)

    def _recalculate_computed_stay(self):
        total_raw = self.first_cure_total_var.get().strip()
        if not total_raw:
            self.first_cure_stay_var.set("")
            return
        try:
            total = float(total_raw)
            if total <= 0:
                self.first_cure_stay_var.set("Invalid total time")
                return
            steps = self._parse_first_cure_steps_only()
            ramp_time = self._estimate_ramp_pulse_time(steps)
            stay = total - ramp_time
            if stay < 0:
                self.first_cure_stay_var.set(
                    f"Invalid (ramp {self._format_first_cure_time_value(ramp_time)}s > total)"
                )
            else:
                self.first_cure_stay_var.set(self._format_first_cure_time_value(stay))
        except ValueError as exc:
            self.first_cure_stay_var.set(str(exc))
        except Exception:
            self.first_cure_stay_var.set("")

    def _update_first_cure_display_summary(self):
        lines = []
        for i, step in enumerate(self.first_cure_step_vars, start=1):
            intensity = step["intensity"].get().strip() or "-"
            on_time = step["on_time"].get().strip() or "-"
            off_time = step["off_time"].get().strip() or "-"
            increment = step["increment"].get().strip() or "1"
            lines.append(
                f"Step {i}: {intensity}% | ON {on_time}s | OFF {off_time}s | +{increment}%"
            )
        summary = "\n".join(lines) if lines else "No steps configured"
        self.first_cure_steps_summary_var.set(summary)

    def _parse_first_cure_settings(self):
        total_raw = self.first_cure_total_var.get().strip()
        if not total_raw:
            raise ValueError("Please enter Total Cure Time (sec)")
        total_time = float(total_raw)
        if total_time <= 0:
            raise ValueError("Total cure time must be greater than zero.")

        steps = self._parse_first_cure_steps_only()
        ramp_time = self._estimate_ramp_pulse_time(steps)
        stay_at_100 = total_time - ramp_time
        if stay_at_100 < 0:
            raise ValueError(
                f"Total time ({total_time:g}s) is shorter than ramp time "
                f"({ramp_time:g}s). Increase total time or reduce step ON/OFF times."
            )

        return total_time, stay_at_100, steps

    def _build_first_cure_pulse_sequence(self, steps):
        sequence = []
        for i in range(len(steps)):
            step = steps[i]
            if i + 1 < len(steps):
                next_step = steps[i + 1]
                current = step["intensity"] + step["increment"] if i > 0 else step["intensity"]
                while current < next_step["intensity"]:
                    sequence.append((current, step["on_time"], step["off_time"]))
                    current += step["increment"]
                sequence.append((
                    next_step["intensity"],
                    next_step["on_time"],
                    next_step["off_time"],
                ))
            else:
                if len(steps) == 1:
                    current = step["intensity"]
                else:
                    current = step["intensity"] + step["increment"]
                while current < 100:
                    sequence.append((current, step["on_time"], step["off_time"]))
                    current += step["increment"]
                if not sequence or sequence[-1][0] != 100:
                    sequence.append((100, step["on_time"], step["off_time"]))
        return sequence

    def _estimate_first_cure_duration(self, total_time):
        return total_time

    def _update_first_cure_step_count(self):
        self.first_cure_step_count_var.set(f"({len(self.first_cure_step_vars)})")

    def _rebuild_first_cure_step_rows(self):
        if not self.first_cure_steps_table:
            return

        for row in self.first_cure_step_rows:
            for widget in row.get("widgets", []):
                widget.destroy()
        self.first_cure_step_rows = []

        entry_width = 10
        for index, step in enumerate(self.first_cure_step_vars):
            grid_row = index + 1
            widgets = []

            step_label = ttk.Label(
                self.first_cure_steps_table,
                text=f"{index + 1}.",
                width=4,
                font=('Arial', 10),
                background=self.colors['light'],
            )
            step_label.grid(row=grid_row, column=0, padx=(0, 4), pady=2, sticky="w")
            widgets.append(step_label)

            intensity_entry = ttk.Entry(
                self.first_cure_steps_table,
                textvariable=step["intensity"],
                width=entry_width,
                style="Modern.TEntry",
            )
            intensity_entry.grid(row=grid_row, column=1, padx=4, pady=2, sticky="ew")
            widgets.append(intensity_entry)

            on_entry = ttk.Entry(
                self.first_cure_steps_table,
                textvariable=step["on_time"],
                width=entry_width,
                style="Modern.TEntry",
            )
            on_entry.grid(row=grid_row, column=2, padx=4, pady=2, sticky="ew")
            widgets.append(on_entry)

            off_entry = ttk.Entry(
                self.first_cure_steps_table,
                textvariable=step["off_time"],
                width=entry_width,
                style="Modern.TEntry",
            )
            off_entry.grid(row=grid_row, column=3, padx=4, pady=2, sticky="ew")
            widgets.append(off_entry)

            inc_entry = ttk.Entry(
                self.first_cure_steps_table,
                textvariable=step["increment"],
                width=entry_width,
                style="Modern.TEntry",
            )
            inc_entry.grid(row=grid_row, column=4, padx=4, pady=2, sticky="ew")
            widgets.append(inc_entry)

            if index == 0:
                intensity_entry.configure(state="readonly")

            self.first_cure_step_rows.append({
                "widgets": widgets,
                "entries": [intensity_entry, on_entry, off_entry, inc_entry],
            })

        for col in range(1, 5):
            self.first_cure_steps_table.columnconfigure(col, weight=1, uniform="cure_step_col")

        self._update_first_cure_step_count()

        if self.first_cure_add_step_button:
            state = "normal" if not self.running else "disabled"
            self.first_cure_add_step_button.configure(state=state)
        if self.first_cure_remove_step_button:
            if self.running or len(self.first_cure_step_vars) <= 1:
                self.first_cure_remove_step_button.configure(state="disabled")
            else:
                self.first_cure_remove_step_button.configure(state="normal")

    def _add_first_cure_step(self):
        if self.running:
            return
        new_step = {
            "intensity": tk.StringVar(value=""),
            "on_time": tk.StringVar(value=""),
            "off_time": tk.StringVar(value=""),
            "increment": tk.StringVar(value="1"),
        }
        for var in new_step.values():
            var.trace_add("write", self._on_first_cure_setting_changed)
        self.first_cure_step_vars.append(new_step)
        self._rebuild_first_cure_step_rows()
        self._persist_first_cure_settings()
        self._update_first_cure_display_summary()

    def _remove_last_first_cure_step(self):
        if self.running or len(self.first_cure_step_vars) <= 1:
            return
        self.first_cure_step_vars.pop()
        self._rebuild_first_cure_step_rows()
        self._persist_first_cure_settings()
        self._update_first_cure_display_summary()

    def create_main_widgets(self):
        title_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        title_frame.pack(fill='x', pady=(0, 20))

        title_row = ttk.Frame(title_frame, style="Main.TFrame")
        title_row.pack()
        if self.app_logo_image:
            ttk.Label(title_row, image=self.app_logo_image, background=self.colors['background'])\
                .pack(side='left', padx=(0, 12))
        ttk.Label(title_row, text="OMNICURE LX500", style="Title.TLabel").pack(side='left')

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
        
        # Configure grid weights
        first_ctrl_frame.columnconfigure(0, weight=1)
        first_ctrl_frame.columnconfigure(1, weight=1)

        
        
        # Store frame references for color changes
        self.first_cure_frame = first_cure_frame

        # First cure settings display with better styling
        first_disp_frame = ttk.Frame(first_cure_frame, style="Main.TFrame")
        first_disp_frame.pack(fill='both', expand=True, padx=15, pady=10)

        ttk.Label(first_disp_frame, text="Total Cure Time (sec):", style="Header.TLabel")\
            .grid(row=0, column=0, sticky='w', padx=10, pady=8)
        ttk.Label(first_disp_frame, textvariable=self.first_cure_total_var, style="Value.TLabel")\
            .grid(row=0, column=1, sticky='w', padx=10, pady=8)

        ttk.Label(first_disp_frame, text="Stay at 100% Time (sec, auto):", style="Header.TLabel")\
            .grid(row=1, column=0, sticky='w', padx=10, pady=8)
        ttk.Label(first_disp_frame, textvariable=self.first_cure_stay_var, style="Value.TLabel")\
            .grid(row=1, column=1, sticky='w', padx=10, pady=8)

        ttk.Label(first_disp_frame, text="Cure Steps:", style="Header.TLabel")\
            .grid(row=2, column=0, sticky='nw', padx=10, pady=8)
        ttk.Label(
            first_disp_frame,
            textvariable=self.first_cure_steps_summary_var,
            style="Value.TLabel",
            justify='left'
        ).grid(row=2, column=1, sticky='w', padx=10, pady=8)

        # Current intensity display in separate frame
        intensity_frame = ttk.LabelFrame(first_disp_frame, text="⚡ Current Intensity", 
                                        style="Modern.TLabelframe")
        intensity_frame.grid(row=3, column=0, columnspan=2, 
                            sticky='ew', padx=10, pady=8)
        intensity_label = ttk.Label(intensity_frame, textvariable=self.first_cure_intensity_var, 
                                   style="Value.TLabel")
        intensity_label.pack(padx=10, pady=5)

        # Elapsed time display in separate frame
        time_frame = ttk.LabelFrame(first_disp_frame, text="⏱️ Elapsed Time", 
                                   style="Modern.TLabelframe")
        time_frame.grid(row=4, column=0, columnspan=2, 
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

        save_port_button = ttk.Button(com_frame, text="💾 Save Port", command=self.save_com_port_settings,
                                  style="Secondary.TButton")
        save_port_button.pack(side='left', padx=(5, 0))
        
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
        title_label = ttk.Label(self.first_cure_settings_frame, text="⚙️ First Cure Settings",
                               style="CureHeader.TLabel")
        title_label.pack(pady=20)

        settings_container = ttk.Frame(self.first_cure_settings_frame, style="Settings.TFrame")
        settings_container.pack(fill='both', expand=True, padx=30, pady=10)

        total_frame = ttk.Frame(settings_container, style="Settings.TFrame")
        total_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(total_frame, text="Total Cure Time (sec)",
                 font=('Arial', 10),
                 foreground=self.colors['text'],
                 background=self.colors['light']).pack(anchor='w', pady=(0, 5))
        self.first_cure_total_entry = ttk.Entry(total_frame, textvariable=self.first_cure_total_var,
                                               width=25, style="Modern.TEntry")
        self.first_cure_total_entry.pack(fill='x', pady=5)

        stay_frame = ttk.Frame(settings_container, style="Settings.TFrame")
        stay_frame.pack(fill='x', pady=(0, 15))
        ttk.Label(stay_frame, text="Stay at 100% Time (sec, auto-calculated)",
                 font=('Arial', 10),
                 foreground=self.colors['text'],
                 background=self.colors['light']).pack(anchor='w', pady=(0, 5))
        ttk.Label(stay_frame, textvariable=self.first_cure_stay_var,
                 font=('Arial', 10, 'bold'),
                 foreground=self.colors['primary'],
                 background=self.colors['light']).pack(anchor='w', pady=5)

        steps_header_bar = ttk.Frame(settings_container, style="Settings.TFrame")
        steps_header_bar.pack(fill='x', pady=(10, 5))
        ttk.Label(steps_header_bar, text="Cure Steps",
                 font=('Arial', 10, 'bold'),
                 foreground=self.colors['text'],
                 background=self.colors['light']).pack(side='left')
        ttk.Label(steps_header_bar, textvariable=self.first_cure_step_count_var,
                 font=('Arial', 10, 'bold'),
                 foreground=self.colors['text'],
                 background=self.colors['light']).pack(side='left', padx=(4, 8))
        self.first_cure_add_step_button = ttk.Button(
            steps_header_bar,
            text="+",
            width=3,
            command=self._add_first_cure_step,
            style="Secondary.TButton",
        )
        self.first_cure_add_step_button.pack(side='left', padx=(0, 2))
        self.first_cure_remove_step_button = ttk.Button(
            steps_header_bar,
            text="−",
            width=3,
            command=self._remove_last_first_cure_step,
            style="Secondary.TButton",
        )
        self.first_cure_remove_step_button.pack(side='left')

        self.first_cure_steps_table = ttk.Frame(settings_container, style="Settings.TFrame")
        self.first_cure_steps_table.pack(fill='x', pady=(0, 10))

        headers = ["Step", "Intensity", "ON Time", "OFF Time", "Increment"]
        for col, label in enumerate(headers):
            ttk.Label(
                self.first_cure_steps_table,
                text=label,
                font=('Arial', 9, 'bold'),
                foreground=self.colors['text'],
                background=self.colors['light'],
            ).grid(row=0, column=col, padx=4, pady=(0, 6), sticky='ew')

        buttons_frame = ttk.Frame(self.first_cure_settings_frame, style="Settings.TFrame")
        buttons_frame.pack(fill='x', padx=30, pady=20)

        self.first_cure_save_button = tk.Button(
            buttons_frame,
            text="💾 Save Settings",
            command=self.save_first_cure_settings,
            bg=self.colors['success'],
            fg=self.colors['white'],
            font=('Arial', 10),
            relief='raised',
            bd=2,
            padx=10,
            pady=5,
        )
        self.first_cure_save_button.pack(side='left', padx=5)

        ttk.Label(
            buttons_frame,
            text="Settings also save automatically when you change values.",
            font=('Arial', 9),
            foreground=self.colors['text_secondary'],
            background=self.colors['light'],
        ).pack(side='left', padx=10)

        ttk.Button(buttons_frame, text="🔙 Back to Main", command=self.show_main_frame,
                  style="Secondary.TButton").pack(side='right', padx=5)

        self._rebuild_first_cure_step_rows()

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
        self._persist_first_cure_settings()
        self._update_first_cure_display_summary()
        self.first_cure_settings_frame.pack_forget()
        self.second_cure_settings_frame.pack_forget()
        self.main_frame.pack(fill='both', expand=True)

    def show_first_cure_settings(self):
        self._rebuild_first_cure_step_rows()
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
        self.root.after(100, lambda: self.start_live("First Cure"))

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
        self.root.after(100, lambda: self.start_live("Second Cure"))

    def save_first_cure_settings(self):
        self._persist_first_cure_settings()
        self._update_first_cure_display_summary()
        messagebox.showinfo("✅ Saved", "First cure settings saved successfully!")

    def save_second_cure_settings(self):
        for i, var in enumerate(self.second_cure_entries):
            self.second_cure_vars[i].set(var.get().strip())
        messagebox.showinfo("✅ Saved", "Second cure settings applied successfully!")

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

    def _set_first_cure_settings_state(self, state):
        if self.first_cure_total_entry:
            self.first_cure_total_entry.configure(state=state)
        if self.first_cure_save_button:
            if state == 'normal' and not self.running:
                self.first_cure_save_button.configure(state='normal')
            else:
                self.first_cure_save_button.configure(state='disabled')
        if self.first_cure_add_step_button:
            if state == 'normal' and not self.running:
                self.first_cure_add_step_button.configure(state='normal')
            else:
                self.first_cure_add_step_button.configure(state='disabled')
        if self.first_cure_remove_step_button:
            if state == 'normal' and not self.running and len(self.first_cure_step_vars) > 1:
                self.first_cure_remove_step_button.configure(state='normal')
            else:
                self.first_cure_remove_step_button.configure(state='disabled')
        for row in self.first_cure_step_rows:
            for entry in row.get("entries", []):
                if entry.cget('state') == 'readonly':
                    continue
                entry.configure(state=state)

    def disable_all_controls(self):
        """Disable ALL controls except stop button and close option during cure"""
        print("DEBUG: Disabling ALL controls during cure...")
        try:
            self._set_first_cure_settings_state('disabled')

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
        except Exception:
            pass

    def enable_all_controls(self):
        """Enable ALL controls after cure"""
        # Only enable controls if no cure is currently running
        if self.running:
            return
            
        try:
            self._set_first_cure_settings_state('normal')

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
        except Exception:
            pass

    def force_enable_all_controls(self):
        """Force enable ALL controls regardless of cure state"""
        try:
            self._set_first_cure_settings_state('normal')

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
        except Exception:
            pass

    def enable_settings_buttons(self):
        """Legacy method - now calls enable_all_controls"""
        self.enable_all_controls()

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
                self.root.after(0, self._update_timing_and_intensity_display, self.cure_duration)
                if self.current_cure_type != 1:
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

    def _stop_lamp_to_zero(self):
        """Turn lamp off and set intensity to 0% without closing serial connection."""
        for _ in range(5):
            self.send_serial("ru=0\r")
            time.sleep(0.03)
            self.send_serial("ip=000,000,000,000\r")
            time.sleep(0.03)
        self.first_cure_intensity_var.set("0%")
        if hasattr(self, 'current_intensity'):
            self.current_intensity = 0

    def _complete_cure_successfully(self, cure_name):
        """Finish cure: lamp off, 0% intensity, static message, stay connected."""
        if self.cure_finishing or not self.running:
            return
        self.cure_finishing = True
        self.stop_message_blink()
        self._stop_lamp_to_zero()
        self.running = False
        self.cure_was_started = False
        self.stop_precise_timing()
        self.set_cure_frame_running(1, False)
        self.set_cure_frame_running(2, False)
        self.current_cure_step = 0
        self.force_enable_all_controls()
        self.show_static_message(f"✅ {cure_name} completed successfully!", "success")
        self.cure_finishing = False
        if self._is_serial_link_alive():
            self.status_var.set(f"✅ Connected to OMNICURE LX500 on {self.serial_port.port}")

    def _stop_instrument_immediately(self):
        """Stop the instrument when cure completes (second cure / legacy path)."""
        if self.running:
            cure_name = "First Cure" if self.current_cure_step == 1 else "Second Cure"
            self._complete_cure_successfully(cure_name)

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

    def refresh_com_ports(self):
        """Refresh the list of available COM ports with detailed information"""
        try:
            ports = []
            for port in serial.tools.list_ports.comports():
                ports.append(port.device)
            
            # Update the combobox with available ports
            self.com_port_combo['values'] = ports

            saved_port = self._load_saved_com_port()
            if saved_port and saved_port in ports:
                self.selected_com_port.set(saved_port)
            elif not self.selected_com_port.get() and ports:
                self.selected_com_port.set(ports[0])
            
            if self.serial_connected and self.serial_port:
                self.status_var.set(f"✅ Connected to OMNICURE LX500 on {self.serial_port.port}")
            elif ports:
                self.status_var.set(f"🔍 Found {len(ports)} COM port(s): {', '.join(ports)}")
            else:
                self.status_var.set("❌ No COM ports detected")
            
        except Exception:
            self.com_port_combo['values'] = []
            self.status_var.set("❌ Error scanning COM ports")

    def on_com_port_selected(self, event=None):
        """Handle COM port selection without disconnecting."""
        selected_port = self.selected_com_port.get()
        if selected_port:
            if self.serial_connected and self.serial_port and self.serial_port.port == selected_port:
                self.status_var.set(f"✅ Connected to OMNICURE LX500 on {selected_port}")
            else:
                self.status_var.set(f"🔍 Selected {selected_port} - Click Connect to connect")
                self.show_static_message(
                    f"Selected COM port: {selected_port} - Click 'Connect' to connect",
                    "info",
                )

    def auto_connect_omnicure(self):
        """Connect on startup using saved COM port only."""
        self.refresh_com_ports()
        saved_port = self._load_saved_com_port()
        if saved_port:
            self.selected_com_port.set(saved_port)
            self.status_var.set(f"🔌 Connecting to saved port {saved_port}...")
            if self.find_and_connect_serial(saved_port_only=True):
                self.show_static_message(f"✅ Connected to saved port {saved_port}", "success")
                self.status_var.set(f"✅ Connected to OMNICURE LX500 on {self.serial_port.port}")
            else:
                self.status_var.set(f"❌ Could not connect to saved port {saved_port}")
                self.show_static_message(
                    f"⚠️ Could not connect to saved port {saved_port}. Check device and click Connect.",
                    "warning",
                )
        else:
            self.status_var.set("🔍 Select COM port, Connect, then Save Port")
            self.show_static_message(
                "Select COM port, click Connect, then Save Port to remember it.",
                "info",
            )

    def manual_connect_selected_port(self):
        """Manually connect to the selected COM port"""
        selected_port = self.selected_com_port.get()
        if not selected_port:
            self.show_static_message("⚠️ Please select a COM port first", "warning")
            return
        
        print(f"Manual connection attempt to selected port: {selected_port}")
        self.status_var.set(f"🔌 Connecting to {selected_port}...")

        if (
            self.serial_connected
            and self.serial_port
            and getattr(self.serial_port, 'is_open', False)
            and self.serial_port.port == selected_port
        ):
            self.show_static_message(f"✅ Already connected to {selected_port}", "success")
            self.status_var.set(f"✅ Connected to OMNICURE LX500 on {selected_port}")
            return

        if self.serial_connected and self.serial_port:
            try:
                self.serial_port.close()
            except Exception:
                pass
            self.serial_port = None
            self.serial_connected = False
        
        if self.find_and_connect_serial(saved_port_only=True):
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

    def find_and_connect_serial(self, saved_port_only=False):
        selected_port = self.selected_com_port.get()

        if self._is_serial_link_alive():
            if not selected_port or self.serial_port.port == selected_port:
                return True

        if self._is_serial_link_alive() and selected_port and self.serial_port.port != selected_port:
            try:
                self.serial_port.close()
            except Exception:
                pass
            self.serial_port = None
            self.serial_connected = False
        
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

            if saved_port_only:
                self.serial_port = None
                self.serial_connected = False
                return False
        
        if saved_port_only:
            return False

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

        omnicure_identifiers = ['omnicure', 'exfo', 'lx500', 'cure', 'uv', 'light']

        for identifier in omnicure_identifiers:
            if (identifier in description or identifier in manufacturer or identifier in product):
                return True

        # Optional VID/PID whitelist (empty by default)
        omnicure_vid_pid = []
        if vid and pid:
            for known_vid, known_pid in omnicure_vid_pid:
                if vid == known_vid and pid == known_pid:
                    return True

        # Allow generic USB-to-Serial devices to be tested
        if 'usb' in description and ('serial' in description or 'com' in description):
            return True
        
        # Also test any COM port that might be a serial device
        if port.device.startswith('COM'):
            return True

        # Unknown device type; allow test
        return True

    def test_omnicure_connection(self, serial_port):
        """Lenient connection test: accept any responsive serial, or even silent, as valid."""
        try:
            serial_port.reset_input_buffer()
            serial_port.reset_output_buffer()
            serial_port.write(b"ip=000,000,000,000\r")
            serial_port.flush()
            time.sleep(0.2)
            try:
                response = serial_port.read(50)
                if response:
                    response_str = response.decode('ascii', errors='ignore').lower()
                    if any(term in response_str for term in ['omnicure', 'exfo', 'lx500', 'cure']):
                        return True
                    # Accept any response as valid (matches previous behavior)
                    return True
                else:
                    # Some devices may not echo; accept as valid to restore connectivity
                    return True
            except Exception:
                return True
        except Exception:
            return False

    def _is_serial_link_alive(self):
        if not self.serial_connected or not self.serial_port:
            return False
        if not getattr(self.serial_port, 'is_open', False):
            return False
        try:
            _ = self.serial_port.in_waiting
            return True
        except Exception:
            return False

    def _mark_serial_disconnected(self, status_message, blink_message, stop_cure=False):
        """Close serial only when the link is actually lost."""
        try:
            if self.serial_port:
                self.serial_port.close()
        except Exception:
            pass
        self.serial_port = None
        self.serial_connected = False
        self.status_var.set(status_message)
        self.start_message_blink(blink_message, "error")
        if stop_cure and self.running:
            self._abort_cure_keep_connection_message()

    def _abort_cure_keep_connection_message(self):
        """Stop an in-progress cure without claiming serial disconnected."""
        self._stop_lamp_to_zero()
        self.running = False
        self.cure_was_started = False
        self.stop_precise_timing()
        self.set_cure_frame_running(1, False)
        self.set_cure_frame_running(2, False)
        self.current_cure_step = 0
        self.force_enable_all_controls()
        self.reset_cure_displays()

    def check_serial_health(self):
        if self._is_serial_link_alive():
            self.status_var.set(f"✅ Connected to OMNICURE LX500 on {self.serial_port.port}")
            self.refresh_com_ports()
            self.root.after(10000, self.check_serial_health)
            return

        was_running = self.running
        if self.serial_connected:
            self._mark_serial_disconnected(
                "❌ OMNICURE Device Disconnected",
                "🔌 OMNICURE device was unplugged.",
                stop_cure=was_running,
            )
        else:
            saved_port = self._load_saved_com_port()
            if saved_port:
                ports = {p.device for p in serial.tools.list_ports.comports()}
                if saved_port in ports:
                    self.selected_com_port.set(saved_port)
                    if self.find_and_connect_serial(saved_port_only=True):
                        self.status_var.set(f"✅ Connected to OMNICURE LX500 on {saved_port}")
                    else:
                        self.status_var.set(f"❌ Could not connect to saved port {saved_port}")
                else:
                    self.status_var.set(f"❌ Saved port {saved_port} not available")
            else:
                self.status_var.set("🔍 Select COM port, Connect, then Save Port")

        self.refresh_com_ports()
        self.root.after(10000, self.check_serial_health)

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
                
            except Exception:
                # Don't mark as disconnected for single command failures
                pass

    def stop_action(self):
        self.stop_message_blink()
        self.cure_finishing = True
        self._stop_lamp_to_zero()
        self.running = False
        self.cure_was_started = False
        self.stop_precise_timing()
        self.set_cure_frame_running(1, False)
        self.set_cure_frame_running(2, False)
        self.current_cure_step = 0
        self.reset_cure_displays()
        self.force_enable_all_controls()
        self.cure_finishing = False
        self.show_static_message("🛑 Cure stopped by user", "warning")
        if self._is_serial_link_alive():
            self.status_var.set(f"✅ Connected to OMNICURE LX500 on {self.serial_port.port}")

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
        """Legacy name: stop cure on unexpected abort; keeps serial open if still alive."""
        self._abort_cure_keep_connection_message()
        if not self._is_serial_link_alive():
            self.show_static_message("🛑 Cure stopped — device connection lost.", "error")
        else:
            self.show_static_message("🛑 Cure stopped.", "warning")
            if self.serial_port:
                self.status_var.set(f"✅ Connected to OMNICURE LX500 on {self.serial_port.port}")

    def start_live(self, cure_name):
        if self.running:
            messagebox.showinfo("ℹ️ Info", "Already running.")
            return
        self.show_static_message("", "info")
        self.cure_finishing = False
        
        # Reset displays
        self.reset_cure_displays()

        try:
            if self.current_cure_step == 1:
                total_time, stay_at_100, first_cure_steps = self._parse_first_cure_settings()
            else:
                # Second cure - continuous mode
                total = float(self.second_cure_vars[0].get())  # 60 seconds
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
            
            if self.current_cure_step == 1:
                self._run_first_cure_pulsed(first_cure_steps, stay_at_100, total_time, cure_name)
            else:
                # Second cure - continuous mode
                self._run_second_cure(total, cure_name)

        self.live_thread = threading.Thread(target=worker, daemon=True)
        self.live_thread.start()

    def _run_first_cure_pulsed(self, steps, stay_at_100_time, total_time, cure_name):
        """Run first cure: ramp 1%→100% pulsing, then pulse at 100% for remaining time."""
        sequence = self._build_first_cure_pulse_sequence(steps)
        last_on = steps[-1]["on_time"]
        last_off = steps[-1]["off_time"]

        self.first_cure_intensity_var.set("0%")
        self.current_intensity = 0
        self.start_precise_timing_with_intensity(total_time, 1, self.FIRST_CURE_START_INTENSITY)

        for intensity, on_time, off_time in sequence:
            if not self.running:
                return

            self.send_serial(f"ip={int(intensity):03},000,000,000\r")
            self.first_cure_intensity_var.set(f"{int(intensity)}%")
            self.current_intensity = int(intensity)

            self.send_serial("ru=1\r")
            on_start = time.perf_counter()
            while time.perf_counter() - on_start < on_time:
                if not self.running:
                    return

            self.send_serial("ru=0\r")
            off_start = time.perf_counter()
            while time.perf_counter() - off_start < off_time:
                if not self.running:
                    return

        if stay_at_100_time > 0:
            self.send_serial("ip=100,000,000,000\r")
            self.first_cure_intensity_var.set("100%")
            self.current_intensity = 100

            hold_start = time.perf_counter()
            while self.running and not self.cure_finishing:
                if time.perf_counter() - hold_start >= stay_at_100_time:
                    break

                self.send_serial("ru=1\r")
                on_start = time.perf_counter()
                while time.perf_counter() - on_start < last_on:
                    if not self.running or time.perf_counter() - hold_start >= stay_at_100_time:
                        break

                if not self.running or time.perf_counter() - hold_start >= stay_at_100_time:
                    break

                self.send_serial("ru=0\r")
                off_start = time.perf_counter()
                while time.perf_counter() - off_start < last_off:
                    if not self.running or time.perf_counter() - hold_start >= stay_at_100_time:
                        break

        if self.running:
            self.root.after(0, lambda: self._complete_cure_successfully("First Cure"))

    def _run_first_cure_continuous(self, total, cure_name):
        """Run first cure in continuous mode"""
        # Continuous mode at 100% intensity - keep it ON continuously
        self.send_serial("ip=100,000,000,000\r")
        self.send_serial("ru=1\r")
        
        # Set intensity to 100%
        self.first_cure_intensity_var.set("100%")
        self.current_intensity = 100
        
        # Start high-precision timing with intensity tracking
        self.start_precise_timing_with_intensity(total, 1, 100)
        
        # Keep UV head ON continuously for the full duration - no pulsing, no blinking
        start_time = time.perf_counter()
        while self.running:
            elapsed = time.perf_counter() - start_time
            
            # Check if time is complete
            if elapsed >= total:
                break
            
            # Continuously keep UV head ON - send command periodically to ensure it stays ON
            self.send_serial("ru=1\r")
            time.sleep(0.1)  # Small delay to avoid flooding serial port
        
        # Timing thread will handle final stop automatically

    def _run_second_cure(self, total, cure_name):
        """Run second cure in continuous mode"""
        # Get intensity from settings (default 100%)
        intensity = float(self.second_cure_vars[1].get())  # Intensity setting
        
        # Set intensity and turn on UV head - keep it ON continuously
        intensity_str = f"{int(intensity):03}"
        self.send_serial(f"ip={intensity_str},000,000,000\r")
        self.send_serial("ru=1\r")
        
        # Start timing
        self.start_precise_timing(total, 2)
        
        # Keep UV head ON continuously for the full duration - no pulsing, no blinking
        start_time = time.perf_counter()
        while self.running:
            elapsed = time.perf_counter() - start_time
            
            # Check if time is complete
            if elapsed >= total:
                break
            
            # Continuously keep UV head ON - send command periodically to ensure it stays ON
            self.send_serial("ru=1\r")
            time.sleep(0.1)  # Small delay to avoid flooding serial port
        
        # Timing thread will handle final stop automatically

    def on_closing(self):
        if self.running:
            if not messagebox.askokcancel("⚠️ Quit", "Cure running—exit?"):
                return
            self.stop_action()
        elif self._is_serial_link_alive():
            self._stop_lamp_to_zero()
        self._persist_first_cure_settings()
        if self.serial_port:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = OmnicureGUI(root)
    # Ensure window is visible
    root.update()
    root.deiconify()  # Make sure window is not minimized
    root.lift()  # Bring to front
    root.attributes('-topmost', True)
    root.after(100, lambda: root.attributes('-topmost', False))
    root.mainloop()
