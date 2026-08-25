from dataclasses import dataclass
import time
from typing import Callable, Optional

import logger


@dataclass(frozen=True)
class ProgressEvent:
    step: str
    message: str
    status: str = "running"
    progress: Optional[int] = None


@dataclass(frozen=True)
class UpdateResult:
    success: bool
    updated: bool
    message: str
    cancelled: bool = False


class UpdateCancelled(Exception):
    pass


def check_cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise UpdateCancelled("The update was cancelled")


def wait_or_cancel(cancel_event, timeout):
    if cancel_event is None:
        time.sleep(timeout)
        return
    if cancel_event.wait(timeout):
        raise UpdateCancelled("The update was cancelled")


class ProgressReporter:
    def __init__(self, callback: Optional[Callable[[ProgressEvent], None]] = None):
        self.callback = callback
        self.progress = 0

    def emit(self, step, message, status="running", progress=None):
        if progress is None:
            progress = self.progress
        else:
            progress = max(self.progress, min(progress, 100))
            self.progress = progress
        emit_progress(self.callback, step, message, status, progress)


def emit_progress(callback, step, message, status="running", progress=None):
    if callback is None:
        return
    callback(ProgressEvent(
        step=step,
        message=message,
        status=status,
        progress=progress
    ))


def initialize_connection(updater, http_connection, ftp_connection, progress_callback=None):
    if http_connection.http_update_enabled == True:
        updater.update_method = "http"
        http_connection.get_url()
        if http_connection.ftp_mirror_update_enabled == True:
            ftp_connection.get_ftp_userdata()
    else:
        updater.update_method = "ftp"
        ftp_connection.get_ftp_userdata()

    message = "Connection for update initialized"
    logger.updater.debug(message)
    emit_progress(progress_callback, "connection_initialized", message, progress=8)


def check_for_update(
        updater,
        http_connection,
        ftp_connection,
        application_directory,
        progress_callback=None,
        cancel_event=None):
    message = "Checking for updates"
    logger.updater.info(message)

    check_cancelled(cancel_event)
    local_version = updater.local_version(
        application_directory,
        progress_callback=progress_callback,
        cancel_event=cancel_event
    )
    updater.check_new_version(
        updater.manifest_file,
        updater.remote_path,
        updater.timeout_update,
        updater.max_attempts_update,
        attempt=1,
        http_connection=http_connection,
        ftp_connection=ftp_connection,
        progress_callback=progress_callback,
        cancel_event=cancel_event
    )
    check_cancelled(cancel_event)
    return updater.check_update(
        local_version,
        progress_callback=progress_callback,
        cancel_event=cancel_event
    )


def completed_result(updated):
    if updated:
        return UpdateResult(True, True, "The update has been completed successfully")
    return UpdateResult(True, False, "Update not found")
