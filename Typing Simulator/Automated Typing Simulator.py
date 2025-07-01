import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading, time
import pyautogui  # For reliable typing (handles punctuation like apostrophes)
from PIL import Image, ImageTk, ImageFilter
import keyboard  # For global hotkey detection (pause/resume)
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import speech_recognition as sr  # For voice-to-text conversion

# =============================================================================
# AutoTyperApp Class
# =============================================================================
class AutoTyperApp(ttk.Window):
    def __init__(self):
        """
        Initialize the AutoTyperApp with:
          - A blurred background image.
          - A top bar with Start, Reset, hotkey info, and Dark Mode toggle.
          - A scrollable text area for user input.
          - A slider to adjust typing delay.
          - A bottom bar with a spinner, a centered microphone button (with animation)
            for voice-to-text, and hotkey customization buttons.
        """
        # Initialize the window using ttkbootstrap's ttk.Window with the "cosmo" theme.
        super().__init__(title="Auto Typer", themename="cosmo", size=(1200, 800))
        # No window transparency is set so that the background image is fully visible.

        # ----------------------------
        # Configure Button Styles
        # ----------------------------
        self.style.configure("TButton", font=("Segoe UI", 12, "bold"))
        self.style.configure("info.TButton", font=("Segoe UI", 10), padding=2)

        # ----------------------------
        # Initialize Variables
        # ----------------------------
        self.text_to_type = ""    # The text to be typed out automatically
        self.current_index = 0     # Tracks the current position in the text
        self.delay = 0.05          # Delay between keystrokes (in seconds)
        self.is_paused = False
        self.stop_event = threading.Event()  # Signal to stop typing
        self.resume_event = threading.Event()  # Signal to resume typing
        self.resume_event.set()    # Initially, typing is not paused

        # ----------------------------
        # Global Hotkeys Setup
        # ----------------------------
        self.pause_hotkey = "esc"  # Default hotkey to pause typing
        self.resume_hotkey = "f9"  # Default hotkey to resume typing
        self.pause_hotkey_id = keyboard.add_hotkey(self.pause_hotkey, self.pause_typing)
        self.resume_hotkey_id = keyboard.add_hotkey(self.resume_hotkey, self.resume_typing)

        # ----------------------------
        # Load and Display Background Image
        # ----------------------------
        try:
            bg_img = Image.open("background.jpg")
            bg_img = bg_img.resize((1200, 800), Image.LANCZOS)
            bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=5))
            self.bg_photo = ImageTk.PhotoImage(bg_img)
        except Exception as e:
            print("Error loading background image:", e)
            self.bg_photo = None

        if self.bg_photo:
            # Place the background image behind all widgets
            bg_label = ttk.Label(self, image=self.bg_photo)
            bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            bg_label.lower()

        # ----------------------------
        # Main Frame: Container for all UI elements
        # ----------------------------
        self.main_frame = ttk.Frame(self, padding=5)
        self.main_frame.pack(fill="both", expand=True)

        # =============================================================================
        # Top Frame: Control Buttons and Hotkey Info
        # =============================================================================
        top_frame = ttk.Frame(self.main_frame, padding=5)
        top_frame.pack(side="top", fill="x")

        # "Start Typing" Button
        self.start_btn = ttk.Button(
            top_frame, text="Start Typing", command=self.start_typing,
            bootstyle="success", padding=10
        )
        self.start_btn.pack(side="left", padx=5)

        # "Reset" Button
        self.reset_btn = ttk.Button(
            top_frame, text="Reset", command=self.reset_typing,
            bootstyle="secondary", padding=10
        )
        self.reset_btn.pack(side="left", padx=5)

        # Hotkey Info Label (displays current pause/resume keys)
        self.hotkey_label = ttk.Label(
            top_frame,
            text=f"Hotkeys: Pause = {self.pause_hotkey.upper()} | Resume = {self.resume_hotkey.upper()}",
            font=("Segoe UI", 10)
        )
        self.hotkey_label.pack(side="left", padx=20)

        # Dark Mode Toggle Switch
        self.dark_mode_var = tk.BooleanVar(value=False)
        self.theme_switch = ttk.Checkbutton(
            top_frame, text="Dark Mode", variable=self.dark_mode_var,
            bootstyle="round-toggle", command=self.toggle_theme
        )
        self.theme_switch.pack(side="right", padx=5)

        # =============================================================================
        # Middle Frame: Text Area for User Input
        # =============================================================================
        text_frame = ttk.Frame(self.main_frame, padding=5)
        text_frame.pack(side="top", fill="both", expand=True)

        self.text_area = tk.Text(text_frame, wrap="word", font=("Segoe UI", 12),
                                 bd=0, highlightthickness=0)
        self.text_area.pack(side="left", fill="both", expand=True)
        text_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_area.yview)
        text_scroll.pack(side="right", fill="y")
        self.text_area.config(yscrollcommand=text_scroll.set)
        self.text_area.insert("1.0", "Paste your text here...")
        # Use a light fallback background color (transparency is not available on Windows)
        self.text_area.config(bg="#f8f8f8", fg="#333333")

        # =============================================================================
        # Slider Frame: Typing Delay Adjustment
        # =============================================================================
        slider_frame = ttk.Frame(self.main_frame, padding=5)
        slider_frame.pack(side="top", fill="x")

        fast_label = ttk.Label(slider_frame, text="Fast", font=("Segoe UI", 10))
        fast_label.pack(side="left")

        self.delay_var = tk.DoubleVar(value=self.delay)
        self.delay_slider = ttk.Scale(
            slider_frame, from_=0.01, to=0.2, variable=self.delay_var,
            length=300, command=lambda val: self.update_delay(val)
        )
        self.delay_slider.pack(side="left", padx=10)

        slow_label = ttk.Label(slider_frame, text="Slow", font=("Segoe UI", 10))
        slow_label.pack(side="left")

        self.delay_display = ttk.Label(slider_frame, text=f"{self.delay:.2f}s", font=("Segoe UI", 10))
        self.delay_display.pack(side="left", padx=10)

        # =============================================================================
        # Bottom Frame: Spinner, Microphone Button, and Hotkey Customization
        # =============================================================================
        bottom_frame = ttk.Frame(self.main_frame, padding=5)
        bottom_frame.pack(side="bottom", fill="x")
        # Set up a grid with 3 equally weighted columns
        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.columnconfigure(1, weight=1)
        bottom_frame.columnconfigure(2, weight=1)

        # Spinner (indicates typing activity) in column 0
        self.spinner = ttk.Progressbar(bottom_frame, mode="indeterminate", bootstyle="info")
        self.spinner.grid(row=0, column=0, sticky="we")
        self.spinner.forget()  # Initially hidden

        # Microphone Button (center, for voice-to-text)
        try:
            mic_img = Image.open("mic.png")
            mic_img = mic_img.resize((40, 40), Image.LANCZOS)
            self.mic_photo = ImageTk.PhotoImage(mic_img)
        except Exception as e:
            print("Error loading mic image:", e)
            self.mic_photo = None

        self.mic_active = False  # For controlling animation state
        # Use a standard tk.Button so we can change its background during animation
        if self.mic_photo:
            self.mic_button = tk.Button(bottom_frame, image=self.mic_photo,
                                        command=self.start_listening, relief="flat", bd=0)
        else:
            self.mic_button = tk.Button(bottom_frame, text="Mic",
                                        command=self.start_listening, relief="flat", bd=0)
        self.mic_button.grid(row=0, column=1, padx=5)

        # Hotkey Customization Buttons in column 2 (right)
        hotkey_frame = ttk.Frame(bottom_frame)
        hotkey_frame.grid(row=0, column=2, sticky="e")
        pause_hotkey_btn = ttk.Button(
            hotkey_frame, text="Set Pause Hotkey", command=self.set_pause_hotkey,
            bootstyle="info"
        )
        pause_hotkey_btn.pack(side="left", padx=5, pady=2)
        resume_hotkey_btn = ttk.Button(
            hotkey_frame, text="Set Resume Hotkey", command=self.set_resume_hotkey,
            bootstyle="info"
        )
        resume_hotkey_btn.pack(side="left", padx=5, pady=2)

        # Apply text area theme based on current theme settings
        self.apply_text_theme()

    # =============================================================================
    # TYPING LOGIC & SMOOTH COUNTDOWN OVERLAY
    # =============================================================================
    def update_delay(self, val):
        try:
            self.delay = float(val)
        except:
            self.delay = 0.05
        self.delay_display.config(text=f"{self.delay:.2f}s")

    def start_typing(self):
        """
        Retrieves the text from the text area and starts the smooth countdown overlay.
        Once the countdown completes, auto-typing begins.
        """
        self.text_to_type = self.text_area.get("1.0", "end-1c")
        if not self.text_to_type.strip():
            return
        self.current_index = 0
        self.stop_event.clear()
        self.resume_event.set()
        self.is_paused = False
        self.start_btn.config(state="disabled")
        self.show_countdown_overlay(10)

    def show_countdown_overlay(self, seconds):
        """
        Creates a semi-transparent black overlay with a smooth, non-modal countdown.
        The overlay updates every 100 ms and is placed in the center.
        """
        overlay = tk.Toplevel(self)
        overlay.overrideredirect(True)
        overlay.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        overlay.configure(bg="black")
        overlay.attributes("-alpha", 0.7)

        countdown_label = ttk.Label(overlay, text="", font=("Arial", 48, "bold"),
                                    foreground="white", background="black")
        countdown_label.place(relx=0.5, rely=0.5, anchor="center")

        start_time = time.time()
        end_time = start_time + seconds

        def update():
            now = time.time()
            remaining = end_time - now
            if remaining > 0:
                countdown_label.config(text=f"{remaining:.1f}")
                self.after(100, update)
            else:
                overlay.destroy()
                self.begin_typing_thread()

        update()

    def begin_typing_thread(self):
        """
        Starts the spinner animation and launches the typing thread.
        """
        self.spinner.grid()  # Ensure spinner is visible
        self.spinner.start(50)
        self.typing_thread = threading.Thread(target=self.type_text, daemon=True)
        self.typing_thread.start()
        self.after(100, self.check_typing_thread)

    def check_typing_thread(self):
        """
        Periodically checks if the typing thread is alive.
        Once typing finishes, stops the spinner and resets control buttons.
        """
        if self.typing_thread and self.typing_thread.is_alive():
            self.after(100, self.check_typing_thread)
        else:
            self.spinner.stop()
            self.spinner.forget()
            self.start_btn.config(state="normal")
            self.is_paused = False
            self.stop_event.clear()
            self.resume_event.set()
            self.current_index = 0

    def type_text(self):
        """
        Types the text from the text area character-by-character using pyautogui.
        Includes a pause mechanism controlled by hotkeys.
        """
        i = self.current_index
        n = len(self.text_to_type)
        while i < n:
            if self.stop_event.is_set():
                break
            ch = self.text_to_type[i]
            pyautogui.typewrite(ch)  # Use pyautogui for reliable punctuation typing
            time.sleep(self.delay)
            i += 1
            self.current_index = i
            # Check for pause condition
            while not self.resume_event.is_set():
                if self.stop_event.is_set():
                    break
                time.sleep(0.1)
            if self.stop_event.is_set():
                break

    # =============================================================================
    # HOTKEY & CONTROL METHODS
    # =============================================================================
    def pause_typing(self):
        """Global hotkey callback to pause typing."""
        if hasattr(self, "typing_thread") and self.typing_thread.is_alive() and not self.is_paused:
            self.is_paused = True
            self.resume_event.clear()

    def resume_typing(self):
        """Global hotkey callback to resume typing."""
        if hasattr(self, "typing_thread") and self.typing_thread.is_alive() and self.is_paused:
            self.is_paused = False
            self.resume_event.set()

    def reset_typing(self):
        """Stops the typing thread and resets the state."""
        if hasattr(self, "typing_thread") and self.typing_thread.is_alive():
            self.stop_event.set()
            self.resume_event.set()
        self.current_index = 0
        self.is_paused = False
        self.spinner.stop()
        self.spinner.forget()
        self.start_btn.config(state="normal")

    def set_pause_hotkey(self):
        """Captures a new pause hotkey from the user."""
        messagebox.showinfo("Set Hotkey", "After clicking OK, press the new PAUSE hotkey combination.")
        def capture_pause():
            new_key = keyboard.read_hotkey(suppress=True)
            keyboard.remove_hotkey(self.pause_hotkey_id)
            self.pause_hotkey = new_key
            self.pause_hotkey_id = keyboard.add_hotkey(new_key, self.pause_typing)
            self.update_hotkey_label()
        threading.Thread(target=capture_pause, daemon=True).start()

    def set_resume_hotkey(self):
        """Captures a new resume hotkey from the user."""
        messagebox.showinfo("Set Hotkey", "After clicking OK, press the new RESUME hotkey combination.")
        def capture_resume():
            new_key = keyboard.read_hotkey(suppress=True)
            keyboard.remove_hotkey(self.resume_hotkey_id)
            self.resume_hotkey = new_key
            self.resume_hotkey_id = keyboard.add_hotkey(new_key, self.resume_typing)
            self.update_hotkey_label()
        threading.Thread(target=capture_resume, daemon=True).start()

    def update_hotkey_label(self):
        """Updates the label showing the current pause/resume hotkeys."""
        self.hotkey_label.config(
            text=f"Hotkeys: Pause = {self.pause_hotkey.upper()} | Resume = {self.resume_hotkey.upper()}"
        )

    # =============================================================================
    # VOICE RECOGNITION & MICROPHONE ANIMATION
    # =============================================================================
    def start_listening(self):
        """Starts voice-to-text: listens from the microphone and appends recognized text."""
        self.mic_active = True
        self.animate_mic()  # Start mic animation
        r = sr.Recognizer()
        with sr.Microphone() as source:
            try:
                audio = r.listen(source, timeout=5)
                recognized_text = r.recognize_google(audio)
            except Exception as e:
                recognized_text = f"[Error: {e}]"
        self.mic_active = False
        self.mic_button.config(bg="SystemButtonFace")
        # Append recognized text to the text area
        self.text_area.insert("end", "\n" + recognized_text)

    def animate_mic(self):
        """Animates the microphone button by toggling its background color."""
        if self.mic_active:
            current_bg = self.mic_button.cget("background")
            new_bg = "lightblue" if current_bg == "SystemButtonFace" else "SystemButtonFace"
            self.mic_button.config(bg=new_bg)
            self.after(300, self.animate_mic)

    # =============================================================================
    # THEME & STYLING
    # =============================================================================
    def toggle_theme(self):
        """Toggles between the dark and light themes."""
        if self.dark_mode_var.get():
            self.style.theme_use("cyborg")
        else:
            self.style.theme_use("cosmo")
        self.apply_text_theme()

    def apply_text_theme(self):
        """Updates the text area colors based on the current theme."""
        theme = self.style.theme_use()
        if theme in ("cyborg", "darkly"):
            self.text_area.config(bg="#272727", fg="#ffffff")
        else:
            self.text_area.config(bg="#f8f8f8", fg="#333333")

# =============================================================================
# Main Loop
# =============================================================================
if __name__ == "__main__":
    app = AutoTyperApp()
    app.mainloop()
