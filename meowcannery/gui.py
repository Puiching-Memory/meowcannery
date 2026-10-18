"""轻量桌面入口：所有按钮调用同一 CLI，不在界面里复制业务规则。"""
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import uuid
import webbrowser
from tkinter import filedialog, messagebox, ttk

from .catalog import ROOT, books, create_book, install_demo
from .export import COMPATIBLE_RANGE
from .pipeline import required_pages
from .presets import load_preset


class Workshop(ttk.Frame):
    def __init__(self, window):
        super().__init__(window, padding=24)
        self.window, self.process, self.events = window, None, queue.Queue()
        self.catalog = books()
        self.pack(fill="both", expand=True)
        window.title(f"喵罐头 · Exameow {COMPATIBLE_RANGE}")
        window.geometry("900x650")
        window.minsize(740, 520)
        style = ttk.Style(window)
        style.theme_use("clam")
        style.configure("TLabel", font=("Microsoft YaHei UI", 10))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(12, 8))
        ttk.Label(self, text="喵罐头", font=("Microsoft YaHei UI", 22, "bold")).pack(anchor="w")
        ttk.Label(self, text="选择书籍，识别扫描页，生成可导入的题库。", foreground="#586576").pack(anchor="w", pady=(4, 20))
        line = ttk.Frame(self)
        line.pack(fill="x")
        self.selection = ttk.Combobox(line, values=[b.title for b in self.catalog], state="readonly", width=35)
        self.selection.pack(side="left", fill="x", expand=True)
        if self.catalog:
            self.selection.current(0)
        else:
            self.selection.set("请先添加 PDF，或体验原创示例")
        self.selection.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        self.catalog_buttons = []
        for label, callback in (("添加 PDF", self.add_pdf), ("体验示例", self.demo)):
            button = ttk.Button(line, text=label, command=callback)
            button.pack(side="left", padx=(8, 0))
            self.catalog_buttons.append(button)
        ttk.Button(line, text="打开 Exameow", command=self.open_exameow).pack(side="right", padx=(12, 0))
        self.status = ttk.Label(self, text="", foreground="#34566D")
        self.status.pack(anchor="w", pady=(16, 6))
        self.detail = ttk.Label(self, text="", foreground="#586576", wraplength=800)
        self.detail.pack(anchor="w", pady=(0, 16))
        self.valid_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text="仅导出检查通过的题目（待核对项保留在报告中）", variable=self.valid_only).pack(anchor="w", pady=(0, 12))
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(0, 12))
        self.run_buttons = []
        for label, command in (("1  识别扫描页", "ocr"), ("2  生成题库", "build")):
            button = ttk.Button(actions, text=label, command=lambda c=command: self.run(c))
            button.pack(side="left", padx=(0, 8))
            self.run_buttons.append(button)
        self.file_buttons = []
        for label, callback in (("打开输出目录", self.open_output), ("原页核对", self.open_review)):
            button = ttk.Button(actions, text=label, command=callback)
            button.pack(side="left", padx=(0, 8))
            self.file_buttons.append(button)
        self.stop = ttk.Button(actions, text="停止任务", command=self.stop_task, state="disabled")
        self.stop.pack(side="right")
        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 12))
        self.log = tk.Text(self, background="#F5F7FA", foreground="#243447", relief="flat",
                           font=("Microsoft YaHei UI", 10), wrap="word", padx=12, pady=12, state="disabled")
        self.log.pack(fill="both", expand=True)
        ttk.Label(self, text="更换规则或添加新书：books/ 书籍配置 · rules/ 预设 · plugins/ 扩展", foreground="#687587").pack(anchor="w", pady=(12, 0))
        self.refresh()
        self.window.after(200, self.poll)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    @property
    def book(self):
        index = self.selection.current()
        return self.catalog[index] if 0 <= index < len(self.catalog) else None

    def select_book(self, book_id):
        self.catalog = books()
        self.selection.configure(values=[book.title for book in self.catalog])
        self.selection.current(next(index for index, book in enumerate(self.catalog) if book.id == book_id))
        self.refresh()

    def add_pdf(self):
        filename = filedialog.askopenfilename(parent=self.window, title="选择你的 PDF", filetypes=[("PDF", "*.pdf")])
        if not filename:
            return
        dialog = tk.Toplevel(self.window)
        dialog.title("添加资料")
        dialog.transient(self.window)
        dialog.grab_set()
        form = ttk.Frame(dialog, padding=20)
        form.pack(fill="both", expand=True)
        from pathlib import Path
        title = tk.StringVar(value=Path(filename).stem)
        subject = tk.StringVar()
        presets = {load_preset(path.stem)["name"]: path.stem for path in sorted((ROOT / "rules").glob("*.json"))}
        selected = tk.StringVar(value=load_preset("chapter_answers")["name"])
        for row, (label, variable) in enumerate((("资料名称", title), ("学科（可选）", subject))):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            ttk.Entry(form, textvariable=variable, width=38).grid(row=row, column=1, sticky="ew", pady=6)
        ttk.Label(form, text="答案版式").grid(row=2, column=0, sticky="w")
        ttk.Combobox(form, textvariable=selected, values=list(presets), state="readonly", width=36).grid(row=2, column=1)
        ttk.Label(form, text="默认处理整份 PDF。页码范围和规则可在本地 books/ 配置中调整。",
                  wraplength=400).grid(row=3, column=0, columnspan=2, pady=12)

        def save():
            try:
                book = create_book("book_" + uuid.uuid4().hex[:8], title.get(), filename,
                                   preset=presets[selected.get()], subject=subject.get())
            except (ValueError, OSError, ImportError, RuntimeError) as error:
                messagebox.showerror("无法添加资料", str(error), parent=dialog)
                return
            self.select_book(book.id)
            self.append(f"已添加资料：{book.title}。配置与识别缓存保存在本地。\n")
            dialog.destroy()

        ttk.Button(form, text="添加", command=save).grid(row=4, column=1, sticky="e")

    def demo(self):
        try:
            book = install_demo()
        except (ValueError, OSError) as error:
            messagebox.showerror("无法载入示例", str(error), parent=self.window)
            return
        self.select_book(book.id)
        self.run("build")

    def refresh(self):
        book = self.book
        for button in self.run_buttons + self.file_buttons:
            button.configure(state="normal" if book else "disabled")
        if book is None:
            self.status.configure(text="尚未添加资料")
            self.detail.configure(text="点击“添加 PDF”使用自己的资料，或点击“体验示例”直接生成原创示例题库。")
            return
        if book.id == "demo":
            self.run_buttons[0].configure(state="disabled")
        pages = required_pages(book)
        cached = sum((book.cache / f"p{p:04d}.md").exists() for p in pages)
        text = f"扫描页：{cached}/{len(pages)} 已识别"
        summary = book.output / "summary.json"
        if summary.exists():
            data = json.loads(summary.read_text(encoding="utf-8"))
            text += f"     最近导出：{data['exported']} 题" + ("（部分题库，详见报告）" if data.get("partial") else "")
        self.status.configure(text=text)
        self.detail.configure(text=("原创示例使用预先编写的文本，无需运行 OCR。" if book.id == "demo" else
                                   f"规则预设：{load_preset(book.preset)['name']}   ·   本地资料 ID：{book.id}"))

    def append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def run(self, command):
        if self.process and self.process.poll() is None:
            return
        if self.book is None:
            return
        environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        arguments = [sys.executable, "-u", "-m", "meowcannery", command, self.book.id]
        if command == "build" and self.valid_only.get():
            arguments.append("--allow-review")
        self.process = subprocess.Popen(arguments,
                                        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace", env=environment,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        process = self.process
        self.append(f"\n{self.book.title}：{'开始识别，可停止后续跑' if command == 'ocr' else '开始生成题库'}\n")
        for button in self.run_buttons:
            button.configure(state="disabled")
        for button in self.catalog_buttons:
            button.configure(state="disabled")
        self.selection.configure(state="disabled")
        self.stop.configure(state="normal")
        self.progress.start(20)

        def consume():
            for line in process.stdout:
                self.events.put(line)
            process.stdout.close()
            self.events.put(process.wait())

        threading.Thread(target=consume, daemon=True).start()

    def poll(self):
        while not self.events.empty():
            item = self.events.get_nowait()
            if isinstance(item, int):
                self.progress.stop()
                self.stop.configure(state="disabled")
                self.selection.configure(state="readonly")
                for button in self.run_buttons:
                    button.configure(state="normal")
                for button in self.catalog_buttons:
                    button.configure(state="normal")
                self.append("\n任务完成。\n" if item == 0 else "\n任务未完成，请查看以上原因及输出目录中的报告。\n")
                self.refresh()
            else:
                self.append(item)
        self.window.after(200, self.poll)

    def stop_task(self):
        if self.process and self.process.poll() is None:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                self.process.terminate()
            self.append("任务已停止，已完成的 OCR 页缓存会保留。\n")

    def open_output(self):
        if self.book is None:
            return
        self.book.output.mkdir(parents=True, exist_ok=True)
        os.startfile(self.book.output)

    def open_review(self):
        if self.book is None:
            return
        path = self.book.output / "原页核对.html"
        if path.exists():
            os.startfile(path)
        else:
            messagebox.showinfo("尚无核对报告", "请先生成一次题库，程序会同时生成核对页面。")

    def open_exameow(self):
        path = ROOT / "Exameow.exe"
        if path.exists():
            os.startfile(path)
        else:
            webbrowser.open("https://github.com/heshengtao/exameow/releases")

    def close(self):
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("停止并关闭", "当前任务仍在运行。停止任务并关闭窗口？已完成的 OCR 页会保留。"):
                return
            self.stop_task()
        self.window.destroy()


def launch():
    window = tk.Tk()
    Workshop(window)
    window.mainloop()
