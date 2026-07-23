import os
import subprocess
import sys

import logger
import update_flow


def build_forwarded_upgrade_args(
        command=None,
        gui=False,
        logs_dir=None,
        logs_level=None,
        logs_clear=None):
    forwarded_args = ["--upgrade"]
    if command is not None:
        forwarded_args.extend(["--cmd", command])
    if gui:
        forwarded_args.append("--gui")
    if logs_dir is not None:
        forwarded_args.extend(["--logs-dir", logs_dir])
    if logs_level is not None:
        forwarded_args.extend(["--logs-level", logs_level])
    if logs_clear is not None:
        forwarded_args.extend(["--logs-clear", str(logs_clear)])
    return forwarded_args


def application_directory_from_temp_process():
    return os.path.abspath("..")


def cleanup_and_exit(updater, exit_code):
    try:
        updater.clear_temp()
    finally:
        os._exit(exit_code)


def run_check_mode(updater, http_connection, ftp_connection, application_directory):
    update_flow.initialize_connection(updater, http_connection, ftp_connection)
    has_update = update_flow.check_for_update(
        updater,
        http_connection,
        ftp_connection,
        application_directory=application_directory
    )
    updater.clear_update_resources()

    sys.stdout.write("true\n" if has_update else "false\n")
    sys.stdout.flush()
    os._exit(0)


def run_exit_command(updater, command, application_directory, progress_callback=None):
    if not command:
        return True

    message = f"The command will be executed before updater exits: '{command}'"
    logger.updater.info(message)
    update_flow.emit_progress(
        progress_callback,
        "post_update_command_started",
        message,
        progress=98
    )

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        subprocess.Popen(
            ["cmd.exe", "/d", "/c", command],
            cwd=application_directory,
            creationflags=creation_flags,
        )
        return True
    except Exception:
        error_message = f"Failed to execute the command before updater exits: '{command}'"
        updater.post_update_error_message = error_message
        logger.updater.error(error_message, exc_info=True)
        update_flow.emit_progress(
            progress_callback,
            "error",
            error_message,
            status="error"
        )
        return False


def run_upgrade_mode(updater, main_file, temp_dir, command=None, gui=False):
    application_directory = application_directory_from_temp_process()

    if gui:
        import update_gui

        def worker(progress_callback):
            return updater.main(
                main_file,
                temp_dir,
                progress_callback=progress_callback,
                exit_on_complete=False,
                cleanup_on_complete=False
            )

        def close_callback(result):
            exit_code = 0
            try:
                if result is None or not result.success:
                    exit_code = 1
                elif result.updated and command:
                    if not run_exit_command(updater, command, application_directory):
                        exit_code = 1
            finally:
                cleanup_and_exit(updater, exit_code)

        update_gui.run_upgrade_gui(worker, close_callback)
        return

    result = updater.main(
        main_file,
        temp_dir,
        exit_on_complete=False,
        cleanup_on_complete=False
    )

    exit_code = 0
    try:
        if not result.success:
            exit_code = 1
        elif result.updated and command:
            if not run_exit_command(updater, command, application_directory):
                exit_code = 1
    finally:
        cleanup_and_exit(updater, exit_code)


def run_post_update_command(updater, command, application_directory, progress_callback=None):
    return run_exit_command(
        updater,
        command,
        application_directory,
        progress_callback=progress_callback
    )
