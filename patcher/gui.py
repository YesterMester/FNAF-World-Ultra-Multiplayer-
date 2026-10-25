"""Point-and-click front end for the FNaF World Ultra Multiplayer patcher."""
import os
import queue
import subprocess
import sys
import threading
import traceback

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fwump import download  # noqa: E402
from fwump.merge import MergeError  # noqa: E402
from fwump.pipeline import VERSION, build  # noqa: E402


def default_base():
    home = os.path.expanduser("~")
    for sub in ("Desktop", "Documents"):
        p = os.path.join(home, sub)
        if os.path.isdir(p):
            return p
    return home


class App:
    def __init__(self, root):
        self.root = root
        root.title("FNaF World Ultra Multiplayer - Patcher v%s" % VERSION)
        root.minsize(620, 470)
        self.q = queue.Queue()
        base = default_base()

        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(root, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Combines FNaF World Ultra with the FNaF World Local Multiplayer mod.",
                  font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", **pad)

        self.mode = tk.StringVar(value="download")
        ttk.Radiobutton(frm, text="Download both games from Game Jolt for me",
                        variable=self.mode, value="download", command=self.sync).grid(
            row=1, column=0, columnspan=3, sticky="w", **pad)
        ttk.Radiobutton(frm, text="I already downloaded them:", variable=self.mode, value="local",
                        command=self.sync).grid(row=2, column=0, columnspan=3, sticky="w", **pad)

        self.ultra = tk.StringVar()
        self.mp = tk.StringVar()
        self.out = tk.StringVar(value=os.path.join(base, "FNaF World Ultra Multiplayer"))

        ttk.Label(frm, text="FNaF World Ultra folder").grid(row=3, column=0, sticky="w", **pad)
        self.e_ultra = ttk.Entry(frm, textvariable=self.ultra, width=52)
        self.e_ultra.grid(row=3, column=1, sticky="we", **pad)
        self.b_ultra = ttk.Button(frm, text="Browse...", command=self.pick_ultra)
        self.b_ultra.grid(row=3, column=2, **pad)

        ttk.Label(frm, text="Local Multiplayer .exe").grid(row=4, column=0, sticky="w", **pad)
        self.e_mp = ttk.Entry(frm, textvariable=self.mp, width=52)
        self.e_mp.grid(row=4, column=1, sticky="we", **pad)
        self.b_mp = ttk.Button(frm, text="Browse...", command=self.pick_mp)
        self.b_mp.grid(row=4, column=2, **pad)

        ttk.Label(frm, text="Save the merged game in").grid(row=5, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.out, width=52).grid(row=5, column=1, sticky="we", **pad)
        ttk.Button(frm, text="Browse...", command=self.pick_out).grid(row=5, column=2, **pad)

        self.go = ttk.Button(frm, text="Build FNaF World Ultra Multiplayer", command=self.start)
        self.go.grid(row=6, column=0, columnspan=3, pady=10)

        self.bar = ttk.Progressbar(frm, mode="determinate", maximum=100)
        self.bar.grid(row=7, column=0, columnspan=3, sticky="we", **pad)
        self.log = tk.Text(frm, height=12, width=80, state="disabled", wrap="word")
        self.log.grid(row=8, column=0, columnspan=3, sticky="nsew", **pad)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(8, weight=1)
        self.sync()
        self.root.after(100, self.poll)

    # ------------------------------------------------------------------ ui
    def sync(self):
        st = "normal" if self.mode.get() == "local" else "disabled"
        for w in (self.e_ultra, self.b_ultra, self.e_mp, self.b_mp):
            w.configure(state=st)

    def pick_ultra(self):
        d = filedialog.askdirectory(title="Folder with 'Fnaf World Ultra.exe'")
        if d:
            self.ultra.set(d)

    def pick_mp(self):
        f = filedialog.askopenfilename(title="fnaf-world-multiplayer-beta.exe",
                                       filetypes=[("Windows program", "*.exe"), ("All files", "*")])
        if f:
            self.mp.set(f)

    def pick_out(self):
        d = filedialog.askdirectory(title="Where to save the merged game")
        if d:
            self.out.set(os.path.join(d, "FNaF World Ultra Multiplayer"))

    def write(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def poll(self):
        try:
            while True:
                kind, value = self.q.get_nowait()
                if kind == "log":
                    self.write(value)
                elif kind == "progress":
                    self.bar.configure(value=value)
                elif kind == "done":
                    self.finish(value)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    # ---------------------------------------------------------------- work
    def start(self):
        out = self.out.get().strip()
        if not out:
            messagebox.showerror("Patcher", "Choose where to save the merged game.")
            return
        if self.mode.get() == "local":
            if not os.path.isfile(os.path.join(self.ultra.get(), "Fnaf World Ultra.dat")):
                messagebox.showerror("Patcher", "That folder has no 'Fnaf World Ultra.dat'.")
                return
            if not os.path.isfile(self.mp.get()):
                messagebox.showerror("Patcher", "Choose the FNaF World Local Multiplayer .exe.")
                return
        self.go.configure(state="disabled")
        threading.Thread(target=self.work, args=(out,), daemon=True).start()

    def work(self, out):
        log = lambda s: self.q.put(("log", s))

        def progress(done, total):
            if total:
                self.q.put(("progress", 100.0 * done / total))
        try:
            if self.mode.get() == "download":
                cache = os.path.join(os.path.dirname(os.path.abspath(out)), "fwum-downloads")
                ultra = download.get_ultra(cache, log, progress)
                mp = download.get_mp(cache, log, progress)
            else:
                ultra, mp = self.ultra.get(), self.mp.get()
            self.q.put(("progress", 0))
            build(ultra, mp, out, log=log)
            self.q.put(("done", out))
        except (MergeError, RuntimeError, OSError) as e:
            log("ERROR: %s" % e)
            self.q.put(("done", None))
        except Exception:
            log("ERROR:\n" + traceback.format_exc())
            self.q.put(("done", None))

    def finish(self, out):
        self.go.configure(state="normal")
        self.bar.configure(value=100 if out else 0)
        if not out:
            messagebox.showerror("Patcher", "Something went wrong - see the log.")
            return
        if messagebox.askyesno("Patcher", "Done! The merged game is in:\n%s\n\nOpen that folder now?" % out):
            open_folder(out)


def open_folder(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError:
        pass


def run_gui():
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(run_gui())
