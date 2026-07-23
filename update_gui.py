import queue
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import about

import logger
from update_flow import ProgressEvent, UpdateResult


def run_upgrade_gui(worker, close_callback):
    events = queue.Queue()
    root = tk.Tk()
    root.title(f"Updater v{about.version}")
    root.geometry("540x200")
    root.minsize(540, 200)
    root.maxsize(540, 200)

    icon_path = Path(__file__).resolve().with_name("icon.ico")

    try:
        root.iconbitmap(default=str(icon_path))
    except tk.TclError:
        logger.updater.warning(
            f"Failed to set the window icon: '{icon_path}'"
        )

    root.columnconfigure(0, weight=1)
    root.rowconfigure(4, weight=1)

    stage_var = tk.StringVar(value="Preparing the update")
    message_var = tk.StringVar(value="")
    error_var = tk.StringVar(value="")

    ttk.Label(root, textvariable=stage_var, font=("Segoe UI", 12, "bold")).grid(
        row=0, column=0, sticky="ew", padx=16, pady=(16, 6)
    )

    progress = ttk.Progressbar(root, mode="determinate", maximum=100)
    progress.grid(row=1, column=0, sticky="ew", padx=16, pady=6)

    ttk.Label(root, textvariable=message_var, wraplength=480).grid(
        row=2, column=0, sticky="ew", padx=16, pady=(6, 4)
    )

    error_label = ttk.Label(root, textvariable=error_var, wraplength=480, foreground="#b00020")
    error_label.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 4))

    close_button = ttk.Button(root, text="Close", command=lambda: close_window())
    close_button.grid(row=5, column=0, sticky="e", padx=16, pady=(0, 16))
    close_button.state(["disabled"])

    worker_done = {"value": False}
    worker_result = {"value": None}

    def publish(event):
        events.put(event)

    def run_worker():
        try:
            result = worker(publish)
            worker_result["value"] = result
            if isinstance(result, UpdateResult):
                if result.success:
                    events.put(ProgressEvent("completed", result.message, "completed", 100))
                else:
                    events.put(ProgressEvent("error", result.message, "error", None))
        except Exception:
            message = "The update failed"
            logger.updater.error(message, exc_info=True)
            worker_result["value"] = UpdateResult(False, False, message)
            events.put(ProgressEvent("error", message, "error", None))

    def apply_event(event):
        if event.step:
            stage_var.set(_stage_title(event.step))
        if event.message:
            message_var.set(event.message)
        if event.progress is not None:
            progress["value"] = event.progress

        if event.status == "error":
            worker_done["value"] = True
            error_var.set(event.message)
            close_button.state(["!disabled"])
        elif event.status == "completed":
            worker_done["value"] = True
            error_var.set("")
            progress["value"] = 100
            close_button.state(["!disabled"])

    def drain_events():
        while True:
            try:
                apply_event(events.get_nowait())
            except queue.Empty:
                break
        root.after(100, drain_events)

    def close_window():
        if not worker_done["value"]:
            message_var.set("Wait for the update to complete")
            return
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_window)

    threading.Thread(target=run_worker, daemon=True).start()
    root.after(100, drain_events)
    root.mainloop()
    close_callback(worker_result["value"])


def _stage_title(step):
    titles = {
        "connection_initialized": "Connection",
        "local_version_loaded": "Local version",
        "manifest_downloaded": "Manifest",
        "manifest_parsed": "Manifest",
        "version_checked": "Version check",
        "update_found": "Update found",
        "update_file_downloaded": "File download",
        "update_file_verified": "File verification",
        "archive_downloaded": "Archive download",
        "archive_verified": "Archive verification",
        "startup_action_started": "Startup action",
        "target_process_stopped": "Application process",
        "backup_created": "Backup",
        "new_file_installed": "File installation",
        "installed_file_verified": "Installation verification",
        "archive_extracted": "Archive extraction",
        "completion_action_started": "Completion action",
        "post_update_command_started": "Post-update command",
        "cleanup_completed": "Cleanup",
        "completed": "Completed",
        "error": "Error",
    }

    return titles.get(step, step)
