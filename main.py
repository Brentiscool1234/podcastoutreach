import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime
import customtkinter as ctk

from src.config_manager import load_config, save_config
from src import openai_helper, browser

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CATEGORIES = [
    "Business", "Entrepreneurship", "Marketing", "Technology",
    "Health & Wellness", "Finance & Investing", "Self-Help & Personal Development",
    "Education", "Sports", "Entertainment", "True Crime",
    "Comedy", "News & Politics", "Science", "Society & Culture",
    "Arts", "Religion & Spirituality", "Kids & Family",
]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Podcast Outreach Pro")
        self.geometry("960x720")
        self.minsize(900, 680)
        self.config_data = load_config()
        self._build_layout()
        self._load_fields_from_config()

    # ─── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=180, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(self.sidebar, text="Podcast\nOutreach Pro", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=16, pady=(24, 20))

        self._sidebar_btn("⚙  Setup", 1, lambda: self._show_tab("setup"))
        self._sidebar_btn("✍  Pitch Creator", 2, lambda: self._show_tab("pitch"))
        self._sidebar_btn("🎙  Outreach", 3, lambda: self._show_tab("outreach"))
        self._sidebar_btn("📋  Activity Log", 4, lambda: self._show_tab("log"))

        version_label = ctk.CTkLabel(self.sidebar, text="v1.0", text_color="gray")
        version_label.grid(row=11, column=0, padx=16, pady=12)

        # Main content area
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.tabs = {}
        self.tabs["setup"] = self._build_setup_tab()
        self.tabs["pitch"] = self._build_pitch_tab()
        self.tabs["outreach"] = self._build_outreach_tab()
        self.tabs["log"] = self._build_log_tab()

        self._show_tab("setup")

    def _sidebar_btn(self, text, row, cmd):
        btn = ctk.CTkButton(self.sidebar, text=text, anchor="w", fg_color="transparent",
                            hover_color=("gray70", "gray30"), command=cmd)
        btn.grid(row=row, column=0, padx=12, pady=4, sticky="ew")

    def _show_tab(self, name):
        for tab in self.tabs.values():
            tab.grid_remove()
        self.tabs[name].grid(row=0, column=0, sticky="nsew", padx=16, pady=16)

    # ─── Setup Tab ─────────────────────────────────────────────────────────────

    def _build_setup_tab(self):
        frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        frame.grid_columnconfigure(1, weight=1)
        row = 0

        def section(label, r):
            ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=14, weight="bold")).grid(row=r, column=0, columnspan=2, sticky="w", pady=(16, 4))

        def field(label, r, show=None):
            ctk.CTkLabel(frame, text=label).grid(row=r, column=0, sticky="w", padx=(4, 12), pady=4)
            entry = ctk.CTkEntry(frame, show=show, width=400)
            entry.grid(row=r, column=1, sticky="ew", pady=4)
            return entry

        # OpenAI
        section("OpenAI API Key", row); row += 1
        self.e_openai_key = field("API Key", row, show="*"); row += 1

        # Matchmaker credentials
        section("Matchmaker.fm Credentials", row); row += 1
        self.e_mm_email = field("Email", row); row += 1
        self.e_mm_password = field("Password", row, show="*"); row += 1

        # Business info
        section("Business / Guest Information", row); row += 1
        self.e_company = field("Company / Your Name", row); row += 1
        self.e_website = field("Website", row); row += 1

        ctk.CTkLabel(frame, text="Description").grid(row=row, column=0, sticky="nw", padx=(4, 12), pady=4)
        self.t_description = ctk.CTkTextbox(frame, height=80)
        self.t_description.grid(row=row, column=1, sticky="ew", pady=4); row += 1

        ctk.CTkLabel(frame, text="Target Audience").grid(row=row, column=0, sticky="nw", padx=(4, 12), pady=4)
        self.t_audience = ctk.CTkTextbox(frame, height=60)
        self.t_audience.grid(row=row, column=1, sticky="ew", pady=4); row += 1

        ctk.CTkLabel(frame, text="Value Proposition").grid(row=row, column=0, sticky="nw", padx=(4, 12), pady=4)
        self.t_value_prop = ctk.CTkTextbox(frame, height=60)
        self.t_value_prop.grid(row=row, column=1, sticky="ew", pady=4); row += 1

        self.e_host_name = field("Your / Host Name", row); row += 1

        # Save button
        ctk.CTkButton(frame, text="Save Configuration", command=self._save_config).grid(
            row=row, column=0, columnspan=2, pady=20)

        return frame

    # ─── Pitch Tab ─────────────────────────────────────────────────────────────

    def _build_pitch_tab(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        # Top controls
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(top, text="Pitch Creator", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Generate Pitch", width=140, command=self._generate_pitch).pack(side="right", padx=(8, 0))
        ctk.CTkButton(top, text="Copy to Clipboard", width=140, command=self._copy_pitch).pack(side="right", padx=(8, 0))
        ctk.CTkButton(top, text="Save Pitch", width=100, command=self._save_pitch).pack(side="right")

        # Pitch text area
        ctk.CTkLabel(frame, text="Generated Pitch (editable):").grid(row=1, column=0, sticky="w", pady=(4, 2))
        self.t_pitch = ctk.CTkTextbox(frame, font=ctk.CTkFont(size=13))
        self.t_pitch.grid(row=2, column=0, sticky="nsew")

        # Refine section
        refine_frame = ctk.CTkFrame(frame)
        refine_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        refine_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(refine_frame, text="Refine Pitch", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 4))
        ctk.CTkLabel(refine_frame, text="Instructions:").grid(row=1, column=0, sticky="w", padx=12)
        self.e_refine_instructions = ctk.CTkEntry(refine_frame, placeholder_text='e.g. "Make it shorter", "Add more personality", "Emphasize ROI"')
        self.e_refine_instructions.grid(row=2, column=0, sticky="ew", padx=12, pady=4)
        ctk.CTkButton(refine_frame, text="Refine Pitch", width=120, command=self._refine_pitch).grid(
            row=2, column=1, padx=(4, 12), pady=4)

        # Status label
        self.pitch_status = ctk.CTkLabel(frame, text="", text_color="gray")
        self.pitch_status.grid(row=4, column=0, pady=4)

        return frame

    # ─── Outreach Tab ──────────────────────────────────────────────────────────

    def _build_outreach_tab(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(frame, text="Outreach", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        # Browser controls
        browser_frame = ctk.CTkFrame(frame)
        browser_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 12), padx=0)
        ctk.CTkButton(browser_frame, text="Launch Browser", width=140, command=self._launch_browser).grid(row=0, column=0, padx=8, pady=8)
        ctk.CTkButton(browser_frame, text="Fill Login & Submit", width=160, command=self._fill_login).grid(row=0, column=1, padx=4, pady=8)
        ctk.CTkButton(browser_frame, text="Check Login Status", width=160, command=self._check_login).grid(row=0, column=2, padx=4, pady=8)
        ctk.CTkButton(browser_frame, text="Close Browser", width=120, fg_color="#c0392b", hover_color="#922b21",
                      command=self._close_browser).grid(row=0, column=3, padx=(4, 8), pady=8)
        self.browser_status = ctk.CTkLabel(browser_frame, text="Browser: Not running", text_color="gray")
        self.browser_status.grid(row=0, column=4, padx=8)

        # Category filter
        filter_frame = ctk.CTkFrame(frame)
        filter_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        ctk.CTkLabel(filter_frame, text="Category Filters", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=12, pady=(10, 4))

        self.category_vars = {}
        for i, cat in enumerate(CATEGORIES):
            var = ctk.BooleanVar()
            self.category_vars[cat] = var
            cb = ctk.CTkCheckBox(filter_frame, text=cat, variable=var)
            cb.grid(row=i + 1, column=0, sticky="w", padx=12, pady=2)

        ctk.CTkButton(filter_frame, text="Search Podcasts", command=self._search_podcasts).grid(
            row=len(CATEGORIES) + 1, column=0, padx=12, pady=(8, 12), sticky="ew")

        # Results list
        results_frame = ctk.CTkFrame(frame)
        results_frame.grid(row=2, column=1, columnspan=2, sticky="nsew", padx=(0, 0), pady=(0, 8))
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(results_frame, text="Podcast Results", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        self.results_box = ctk.CTkScrollableFrame(results_frame)
        self.results_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.results_box.grid_columnconfigure(0, weight=1)

        self._podcast_rows = []

        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        return frame

    def _build_log_tab(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(top, text="Activity Log", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="Clear Log", width=90, command=self._clear_log).pack(side="right")

        self.log_box = ctk.CTkTextbox(frame, font=ctk.CTkFont(family="Courier", size=12), state="disabled")
        self.log_box.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        return frame

    # ─── Config helpers ────────────────────────────────────────────────────────

    def _load_fields_from_config(self):
        c = self.config_data
        self.e_openai_key.insert(0, c.get("openai_api_key", ""))
        self.e_mm_email.insert(0, c.get("matchmaker_email", ""))
        self.e_mm_password.insert(0, c.get("matchmaker_password", ""))
        b = c.get("business", {})
        self.e_company.insert(0, b.get("company_name", ""))
        self.e_website.insert(0, b.get("website", ""))
        self.t_description.insert("0.0", b.get("description", ""))
        self.t_audience.insert("0.0", b.get("target_audience", ""))
        self.t_value_prop.insert("0.0", b.get("value_proposition", ""))
        self.e_host_name.insert(0, b.get("host_name", ""))
        if c.get("current_pitch"):
            self.t_pitch.insert("0.0", c["current_pitch"])

    def _collect_fields(self) -> dict:
        return {
            "openai_api_key": self.e_openai_key.get().strip(),
            "matchmaker_email": self.e_mm_email.get().strip(),
            "matchmaker_password": self.e_mm_password.get(),
            "business": {
                "company_name": self.e_company.get().strip(),
                "website": self.e_website.get().strip(),
                "description": self.t_description.get("0.0", "end").strip(),
                "target_audience": self.t_audience.get("0.0", "end").strip(),
                "value_proposition": self.t_value_prop.get("0.0", "end").strip(),
                "host_name": self.e_host_name.get().strip(),
            },
            "current_pitch": self.t_pitch.get("0.0", "end").strip(),
        }

    def _save_config(self):
        self.config_data = self._collect_fields()
        save_config(self.config_data)
        self._log("Configuration saved.")
        messagebox.showinfo("Saved", "Configuration saved successfully.")

    # ─── Pitch actions ─────────────────────────────────────────────────────────

    def _generate_pitch(self):
        api_key = self.e_openai_key.get().strip()
        if not api_key:
            messagebox.showwarning("Missing API Key", "Enter your OpenAI API key in Setup first.")
            return
        business = self._collect_fields()["business"]
        if not business["company_name"]:
            messagebox.showwarning("Missing Info", "Fill in at least your Company/Name in Setup.")
            return
        self.pitch_status.configure(text="Generating pitch...", text_color="yellow")
        self._log("Generating pitch via OpenAI...")

        def run():
            try:
                pitch = openai_helper.generate_pitch(api_key, business)
                self.after(0, lambda: self._set_pitch(pitch, "Pitch generated!"))
            except Exception as e:
                self.after(0, lambda: self._pitch_error(str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _refine_pitch(self):
        api_key = self.e_openai_key.get().strip()
        if not api_key:
            messagebox.showwarning("Missing API Key", "Enter your OpenAI API key in Setup first.")
            return
        current = self.t_pitch.get("0.0", "end").strip()
        if not current:
            messagebox.showwarning("No Pitch", "Generate a pitch first before refining.")
            return
        instructions = self.e_refine_instructions.get().strip()
        if not instructions:
            messagebox.showwarning("No Instructions", "Enter refine instructions.")
            return
        self.pitch_status.configure(text="Refining pitch...", text_color="yellow")
        self._log(f"Refining pitch: {instructions}")

        def run():
            try:
                refined = openai_helper.refine_pitch(api_key, current, instructions)
                self.after(0, lambda: self._set_pitch(refined, "Pitch refined!"))
            except Exception as e:
                self.after(0, lambda: self._pitch_error(str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _set_pitch(self, text: str, status: str):
        self.t_pitch.delete("0.0", "end")
        self.t_pitch.insert("0.0", text)
        self.pitch_status.configure(text=status, text_color="green")
        self._log(status)

    def _pitch_error(self, err: str):
        self.pitch_status.configure(text=f"Error: {err}", text_color="red")
        self._log(f"Pitch error: {err}")
        messagebox.showerror("OpenAI Error", err)

    def _copy_pitch(self):
        pitch = self.t_pitch.get("0.0", "end").strip()
        if pitch:
            self.clipboard_clear()
            self.clipboard_append(pitch)
            self.pitch_status.configure(text="Copied to clipboard!", text_color="green")
            self._log("Pitch copied to clipboard.")

    def _save_pitch(self):
        self.config_data = self._collect_fields()
        save_config(self.config_data)
        self.pitch_status.configure(text="Pitch saved!", text_color="green")
        self._log("Pitch saved to config.")

    # ─── Browser actions ───────────────────────────────────────────────────────

    def _launch_browser(self):
        self.browser_status.configure(text="Browser: Launching...", text_color="yellow")
        self._log("Launching browser...")

        def run():
            ok = browser.launch_browser(lambda msg: self.after(0, lambda m=msg: self._log(m)))
            status = "Browser: Running — log in and solve captcha if needed" if ok else "Browser: Failed to launch"
            color = "green" if ok else "red"
            self.after(0, lambda: self.browser_status.configure(text=status, text_color=color))

        threading.Thread(target=run, daemon=True).start()

    def _fill_login(self):
        email = self.e_mm_email.get().strip()
        password = self.e_mm_password.get()
        if not email or not password:
            messagebox.showwarning("Missing Credentials", "Enter your Matchmaker.fm email and password in Setup.")
            return
        self._log("Filling login form...")
        threading.Thread(target=lambda: browser.fill_login(email, password,
            lambda msg: self.after(0, lambda m=msg: self._log(m))), daemon=True).start()

    def _check_login(self):
        self._log("Checking login status...")
        threading.Thread(target=lambda: browser.check_login_status(
            lambda msg: self.after(0, lambda m=msg: self._log(m))), daemon=True).start()

    def _close_browser(self):
        browser.close_browser(lambda msg: self.after(0, lambda m=msg: self._log(m)))
        self.browser_status.configure(text="Browser: Not running", text_color="gray")

    def _search_podcasts(self):
        selected = [cat for cat, var in self.category_vars.items() if var.get()]
        self._log(f"Searching podcasts (categories: {selected or 'All'})...")
        self.browser_status.configure(text="Browser: Searching...", text_color="yellow")

        def run():
            results = browser.search_podcasts(selected, lambda msg: self.after(0, lambda m=msg: self._log(m)))
            self.after(0, lambda: self._display_results(results))
            self.after(0, lambda: self.browser_status.configure(text="Browser: Running", text_color="green"))

        threading.Thread(target=run, daemon=True).start()

    def _display_results(self, results: list):
        for widget in self.results_box.winfo_children():
            widget.destroy()
        self._podcast_rows = []

        if not results:
            ctk.CTkLabel(self.results_box, text="No results found. Make sure you're logged in and try searching.",
                         text_color="gray", wraplength=300).grid(row=0, column=0, padx=12, pady=20)
            return

        for i, pod in enumerate(results):
            row_frame = ctk.CTkFrame(self.results_box)
            row_frame.grid(row=i, column=0, sticky="ew", padx=4, pady=4)
            row_frame.grid_columnconfigure(0, weight=1)

            name_label = ctk.CTkLabel(row_frame, text=pod["name"], font=ctk.CTkFont(weight="bold"), anchor="w")
            name_label.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))

            if pod.get("category"):
                ctk.CTkLabel(row_frame, text=pod["category"], text_color="#5dade2", anchor="w").grid(
                    row=1, column=0, sticky="w", padx=10, pady=(0, 1))

            if pod.get("description"):
                ctk.CTkLabel(row_frame, text=pod["description"][:180], text_color="gray",
                             anchor="w", wraplength=360).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 2))

            btn_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            btn_frame.grid(row=3, column=0, sticky="w", padx=6, pady=(4, 8))

            if pod.get("link"):
                ctk.CTkButton(btn_frame, text="Open Page", width=100,
                              command=lambda link=pod["link"]: self._open_podcast(link)).pack(side="left", padx=4)

            ctk.CTkButton(btn_frame, text="Copy Pitch", width=100,
                          command=self._copy_pitch).pack(side="left", padx=4)

            # Send Pitch button — the main automation action
            send_btn = ctk.CTkButton(
                btn_frame, text="Send Pitch", width=110,
                fg_color="#1e8449", hover_color="#145a32",
                command=lambda p=pod: self._send_pitch_to_podcast(p),
            )
            send_btn.pack(side="left", padx=4)

            self._podcast_rows.append(row_frame)

        self._log(f"Displayed {len(results)} podcast results.")

    def _open_podcast(self, link: str):
        browser.open_podcast(link, lambda msg: self.after(0, lambda m=msg: self._log(m)))

    def _send_pitch_to_podcast(self, pod: dict):
        pitch_text = self.t_pitch.get("0.0", "end").strip()
        if not pitch_text:
            messagebox.showwarning("No Pitch", "Go to the Pitch Creator tab and generate or write a pitch first.")
            return
        if not pod.get("link"):
            messagebox.showwarning("No Link", f"No profile link found for '{pod['name']}'. Open their page manually.")
            return

        # Replace common host name placeholders with the podcast/host name
        host_name = pod.get("host_name") or pod.get("name", "")
        for placeholder in ["[Host's Name]", "[Host Name]", "[host's name]", "[host name]", "[Podcast Host]"]:
            pitch_text = pitch_text.replace(placeholder, host_name)

        self.browser_status.configure(text="Browser: Sending pitch...", text_color="yellow")
        self._log(f"Starting pitch send to: {pod['name']} (host name filled: {host_name})")

        # Single approval: shown after the form is filled so the user can
        # check the form and solve any captcha before confirming submission.
        confirm_event = threading.Event()
        confirm_result = [False]

        def confirm_cb():
            self.after(0, _ask_confirm)
            confirm_event.wait(timeout=120)
            return confirm_result[0]

        def _ask_confirm():
            result = messagebox.askyesno(
                "Submit Pitch?",
                f"Pitch filled in for: {pod['name']}\n\n"
                "Solve any captcha in the browser if needed, then click YES to submit.",
            )
            confirm_result[0] = result
            confirm_event.set()

        def run():
            ok = browser.send_pitch(
                link=pod["link"],
                pitch_text=pitch_text,
                confirm_cb=confirm_cb,
                log_cb=lambda msg: self.after(0, lambda m=msg: self._log(m)),
            )
            status = "Browser: Running" if ok else "Browser: Running (pitch not sent)"
            color = "green" if ok else "orange"
            self.after(0, lambda: self.browser_status.configure(text=status, text_color=color))
            if ok:
                self.after(0, lambda: self._log(f"Pitch sent to {pod['name']} successfully."))

        threading.Thread(target=run, daemon=True).start()

    # ─── Log helpers ───────────────────────────────────────────────────────────

    def _log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("0.0", "end")
        self.log_box.configure(state="disabled")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
