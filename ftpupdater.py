import logger
import configs
import sys_manager
import connectors
import about
import argparse
import subprocess
import sys
import os
import time
import shutil
import update_flow
import update_scenarios
import log_arguments


def parse_update_mode_arguments(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--check", action="store_true")
    mode_group.add_argument("--upgrade", action="store_true")
    parser.add_argument("--cmd")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--logs-dir", dest="logs_dir")
    parser.add_argument(
        "--logs-level",
        dest="logs_level",
        type=log_arguments.parse_logs_level_cli
    )
    parser.add_argument(
        "--logs-clear",
        dest="logs_clear",
        type=log_arguments.parse_logs_clear_cli
    )

    args, _ = parser.parse_known_args(argv)
    if (args.cmd is not None or args.gui) and not args.upgrade:
        parser.error("--cmd and --gui are allowed only with --upgrade")
    if log_arguments.has_logging_overrides(args) and not (args.check or args.upgrade):
        parser.error("--logs-dir, --logs-level and --logs-clear are allowed only with --check or --upgrade")
    return args

def checking_launch_arguments():
    try:
        if "--mkey" in sys.argv:
            idx = sys.argv.index("--mkey")
            key = sys.argv[idx + 1]
            updater.create_manifest(key)
            os._exit(0)

        # HTTP
        if "--http" in sys.argv:
            idx = sys.argv.index("--http")
            url = sys.argv[idx + 1]
            updater.save_http_config(url)
            os._exit(0)

        # FTP
        ftp_server = None
        ftp_user = None
        ftp_pass = None

        if "--ftpserver" in sys.argv:
            idx = sys.argv.index("--ftpserver")
            ftp_server = sys.argv[idx + 1]

        if "--ftpuser" in sys.argv:
            idx = sys.argv.index("--ftpuser")
            ftp_user = sys.argv[idx + 1]

        if "--ftppass" in sys.argv:
            idx = sys.argv.index("--ftppass")
            ftp_pass = sys.argv[idx + 1]

        if ftp_server or ftp_user or ftp_pass:
            updater.save_ftp_config(
                ftp_server=ftp_server,
                ftp_user=ftp_user,
                ftp_pass=ftp_pass
            )
            os._exit(0)

    except (IndexError, ValueError):
        main_file = os.path.abspath(sys.argv[0])
        exe = os.path.basename(main_file)

        logger.updater.critical(
            f"Usage:\n"
            f"{exe} --mkey <signature_key> OR\n"
            f"{exe} --http <url> OR\n"
            f"{exe} --ftpserver <server>\n"
            f"{exe} --ftpuser <user>\n"
            f"{exe} --ftppass <password>"
        )
        sys.exit(1)


class Updater(sys_manager.ProcessManagement):
    def __init__(self):
        super().__init__()
        self.signature_check_disable_config = self.config.get("update", {}).get("signature_check_disable_key", "")
        self.remote_path = self.config.get("update", {}).get("ftp_path", "")  # папка на фтп с которой качаются все файлы для обновления

        try: self.max_attempts_update = int(self.config.get("update", {}).get("attempt_count", 5))  # количество попыток
        except: self.max_attempts_update = 5

        try: self.timeout_update = int(self.config.get("update", {}).get("attempt_timeout", 10))  # тайм-аут
        except: self.timeout_update = 10

        self.update_method = None
        self.new_version = None
        self.exe_signature = None
        self.zip_signature = None

    def check_new_version(
            self,
            file_name,
            remote_path,
            timeout_update,
            max_attempts,
            attempt,
            http_connection=None,
            ftp_connection=None,
            progress_callback=None):
        try:
            http_client = http_connection or http_connect
            ftp_client = ftp_connection or ftp_connect
            if self.update_method == "http":
                file_path, update_method = http_client.download_file(
                    file_name, remote_path, timeout_update, max_attempts, attempt)
                self.update_method = update_method
            else:
                file_path = ftp_client.download_file(file_name, remote_path, timeout_update, max_attempts, attempt)[0]

            if file_path:
                update_flow.emit_progress(
                    progress_callback,
                    "manifest_downloaded",
                    "Update manifest downloaded",
                    progress=36
                )
                self.read_manifest()
                update_flow.emit_progress(
                    progress_callback,
                    "manifest_parsed",
                    "Update manifest parsed",
                    progress=44
                )
                self.get_name_zip()
                # Получение версии файла на фтп
                self.new_version = self.manifest[self.exe_name].get("version")
                if self.new_version:
                    logger.updater.info(f"Server file version: {self.new_version}")

                self.exe_signature = self.manifest[self.exe_name].get("signature")
                if self.exe_signature:
                    logger.updater.debug(f"Server file signature: '{self.exe_signature}'")

                if self.zip_name:
                    self.zip_signature = self.manifest[self.zip_name].get("signature")
                    if self.zip_signature:
                        logger.updater.debug(f"Server ZIP archive signature: '{self.zip_signature}'")
                        return
                    logger.updater.debug(f"Server ZIP archive signature: '{None}'")
        except Exception:
            logger.updater.error(f"Failed to check the file version on the remote server", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def local_version(self, parent_directory, progress_callback=None):
        try:
            file_path = f"{parent_directory}\\{self.exe_name}"  # путь до локального файла с которым сравнивается версия
            logger.updater.debug(f"Getting file version information: '{os.path.abspath(file_path)}'")
            local_version = self.get_exe_version(file_path)
            if local_version:
                logger.updater.info(f"Source file version: {local_version}")
                update_flow.emit_progress(
                    progress_callback,
                    "local_version_loaded",
                    f"Source file version: {local_version}",
                    progress=26
                )
                return local_version
        except Exception:
            logger.updater.error(f"Failed to check the source file version", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def check_update(self, local_version, progress_callback=None):
        try:
            # Разбиваем версии на части и преобразуем их в числа
            parts1 = list(map(int, self.new_version.split('.')))
            parts2 = list(map(int, local_version.split('.')))

            # Сравниваем каждую часть версии, начиная с первой
            for i in range(len(parts1)):
                if parts1[i] > parts2[i]:
                    update_flow.emit_progress(
                        progress_callback,
                        "version_checked",
                        "Version comparison completed",
                        progress=50
                    )
                    return True  # Версия первого файла выше
                elif parts1[i] < parts2[i]:
                    update_flow.emit_progress(
                        progress_callback,
                        "version_checked",
                        "Version comparison completed",
                        progress=50
                    )
                    return False  # Версия первого файла ниже
            update_flow.emit_progress(
                progress_callback,
                "version_checked",
                "Version comparison completed",
                progress=50
            )
            return False  # Версии идентичны
        except Exception:
            logger.updater.error(
                f"Failed to convert file version information '{self.new_version}' "
                f"to a suitable format for comparison with '{local_version}'", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def upgrade(self, local, attempt, progress_callback=None):
        try:
            logger.updater.debug(f"Path to the previous version executable file was determined: "
                                 f"'{os.path.abspath(self.old_file)}'")
            # Проверяем и удаляем временный файл если он существует
            if os.path.exists(self.temp_old_file):
                os.remove(self.temp_old_file)
                logger.updater.debug(f"Deleted existing temporary file: '{os.path.abspath(self.temp_old_file)}'")

            os.rename(self.old_file, self.temp_old_file)
            logger.updater.debug(f"Created a backup of the executable file before the update: "
                                 f"'{os.path.abspath(self.temp_old_file)}'")
            update_flow.emit_progress(
                progress_callback,
                "backup_created",
                "Created a backup of the executable file before the update",
                progress=78
            )

            temp_new_file = os.path.join(os.path.dirname(self.manifest_file), self.exe_name)
            logger.updater.debug(f"Path to the temporary update file was determined: '{os.path.abspath(temp_new_file)}'")
            shutil.copy2(temp_new_file, self.old_file)
            logger.updater.debug(f"Temporary file '{temp_new_file}' was copied to directory "
                                 f"'{os.path.abspath(local)}'")
            update_flow.emit_progress(
                progress_callback,
                "new_file_installed",
                f"Temporary file '{temp_new_file}' was copied to directory '{os.path.abspath(local)}'",
                progress=84
            )

            if not self.signature_check_disable_config == self.signature_check_disable_key:
                logger.updater.debug(f"Checking executable file integrity: '{os.path.abspath(self.old_file)}'")
                size_file = self.get_size_file(os.path.abspath(self.old_file))
                temp_file_version = self.get_exe_version(os.path.abspath(self.old_file))
                file_hash = self.file_sha256(os.path.abspath(self.old_file))

                signature = self.sign_metadata(temp_file_version, size_file, os.path.basename(self.old_file),
                                               file_hash)

                if not signature == self.exe_signature:
                    self.restore_file()
                    raise ValueError(f"The installed file '{os.path.abspath(self.old_file)}' "
                                     f"failed the integrity check and was deleted")
                else:
                    logger.updater.info(f"Integrity check passed, file '{os.path.abspath(self.old_file)}' "
                                        f"was successfully updated")
                    update_flow.emit_progress(
                        progress_callback,
                        "installed_file_verified",
                        f"Integrity check passed, file '{os.path.abspath(self.old_file)}' was successfully updated",
                        progress=90
                    )
                    if self.zip_name:
                        self.unzip_and_get_files("..")
                        update_flow.emit_progress(
                            progress_callback,
                            "archive_extracted",
                            f"ZIP archive '{self.zip_path}' was successfully extracted",
                            progress=94
                        )
                    update_successful = True

            else:
                logger.updater.info(f"File '{os.path.abspath(self.old_file)}' was successfully updated")
                update_flow.emit_progress(
                    progress_callback,
                    "installed_file_verified",
                    f"File '{os.path.abspath(self.old_file)}' was successfully updated",
                    progress=90
                )
                if self.zip_name:
                    self.unzip_and_get_files("..")
                    update_flow.emit_progress(
                        progress_callback,
                        "archive_extracted",
                        f"ZIP archive '{self.zip_path}' was successfully extracted",
                        progress=94
                    )
                update_successful = True

            if update_successful:
                logger.updater.info("Update installed")  # Выводим сообщение только если обновление успешно
                shutil.rmtree(os.path.dirname(self.manifest_file))
                logger.updater.debug(f"Temporary directory '{os.path.dirname(self.manifest_file)}' deleted")
                os.remove(self.temp_old_file)
                logger.updater.debug(f"Executable file backup "
                                     f"'{os.path.abspath(self.temp_old_file)}' deleted")
                return True
        except Exception:
            if attempt < self.max_attempts_update:
                logger.updater.warn(
                    f"Attempt ({attempt}) to install the update failed. Retrying in "
                    f"({self.timeout_update}) seconds...")
                attempt += 1
                time.sleep(self.timeout_update)
                return self.upgrade(local, attempt, progress_callback=progress_callback)
            else:
                logger.updater.error(f"Failed to perform the update after ({self.max_attempts_update}) attempts",
                                     exc_info=True)
                shutil.rmtree(os.path.dirname(self.manifest_file))
                logger.updater.debug(f"Temporary directory '{os.path.dirname(self.manifest_file)}' deleted")
                self.clear_temp()
                os._exit(1)

    def update_run(
            self,
            temp_file_version,
            main_file_path=None,
            http_connection=None,
            ftp_connection=None,
            progress_callback=None):
        main_file_path = main_file_path or main_file
        http_client = http_connection or http_connect
        ftp_client = ftp_connection or ftp_connect
        update_successful = False

        logger.updater.debug(f"Downloaded file version: {temp_file_version}")
        if temp_file_version != self.new_version:
            logger.updater.warn(f"The downloaded file version differs from the data in 'manifest.json'; "
                                f"the update process will be interrupted")
            shutil.rmtree(os.path.dirname(self.manifest_file))
            logger.updater.debug(f"Temporary directory '{os.path.dirname(self.manifest_file)}' deleted")
            return False

        if self.zip_name:
            if self.update_method == "http":
                self.zip_path = http_client.download_file(
                    self.zip_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)[0]
            else:
                self.zip_path = ftp_client.download_file(
                    self.zip_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)[0]
            update_flow.emit_progress(
                progress_callback,
                "archive_downloaded",
                f"ZIP archive '{self.zip_name}' downloaded",
                progress=64
            )

            if not self.signature_check_disable_config == self.signature_check_disable_key:
                size_file = self.get_size_file(self.zip_path)
                file_hash = self.file_sha256(os.path.abspath(self.zip_path))
                signature = self.sign_metadata(int(size_file / len(self.zip_name)), size_file, self.zip_name, file_hash)

                if not signature == self.zip_signature:
                    logger.updater.warn(f"ZIP archive '{self.zip_name}' failed authenticity verification")
                    shutil.rmtree(os.path.dirname(self.manifest_file))
                    logger.updater.debug(f"Temporary directory '{os.path.dirname(self.manifest_file)}' deleted")
                    return False
                logger.updater.info(f"ZIP archive '{self.zip_name}' passed authenticity verification")
                update_flow.emit_progress(
                    progress_callback,
                    "archive_verified",
                    f"ZIP archive '{self.zip_name}' passed authenticity verification",
                    progress=68
                )
        try:
            if self.action_startup == True:
                update_flow.emit_progress(
                    progress_callback,
                    "startup_action_started",
                    f"'{self.startup_script}' will be started",
                    progress=70
                )
                self.action_run(self.startup_script, main_file_path, timeout=True)

            wait_stop_app = self.check_process_cycle(self.exe_name)

            if wait_stop_app != True:
                return False

            update_flow.emit_progress(
                progress_callback,
                "target_process_stopped",
                f"Process '{self.exe_name}' has exited or was not running",
                progress=74
            )

            try:
                logger.updater.info("Update started")
                update_successful = self.upgrade(
                    "..\\",
                    attempt=1,
                    progress_callback=progress_callback
                )

                if self.action_completion == True:
                    update_flow.emit_progress(
                        progress_callback,
                        "completion_action_started",
                        f"'{self.complete_script}' will be started",
                        progress=96
                    )
                    self.action_run(self.complete_script, main_file_path)

            except Exception:
                logger.updater.error(
                    f"Failed to start the update process",
                    exc_info=True
                )

                if self.action_completion == True:
                    update_flow.emit_progress(
                        progress_callback,
                        "completion_action_started",
                        f"'{self.complete_script}' will be started",
                        progress=96
                    )
                    self.action_run(self.complete_script, main_file_path)

                self.clear_temp()
                os._exit(1)

        except Exception:
            logger.updater.error(
                f"Running management scripts failed",
                exc_info=True
            )
            self.clear_temp()
            os._exit(1)

        return bool(update_successful)

    def clear_update_resources(self):
        resources_dir = os.path.dirname(self.manifest_file)
        if os.path.exists(resources_dir):
            shutil.rmtree(resources_dir)
            logger.updater.debug(f"Temporary directory '{resources_dir}' deleted")

    def main(
            self,
            main_file,
            temp_dir,
            forwarded_args=None,
            progress_callback=None,
            exit_on_complete=True,
            cleanup_on_complete=True):
        if main_file.startswith(temp_dir): # если udater запущен из временной директории, то запускаем процесс обновления
            try:
                result = update_flow.UpdateResult(False, False, "The update did not complete correctly")
                logger.updater.info(f"updater.exe started")
                logger.updater.info(f"Executable file version: {about.version}")
                logger.updater.debug(f"Working directory: '{work_directory}'")
                logger.updater.debug(f"Configuration file read: {self.config}")

                update_flow.initialize_connection(self, http_connect, ftp_connect, progress_callback=progress_callback)

                try:
                    status_update = update_flow.check_for_update(
                        self,
                        http_connect,
                        ftp_connect,
                        application_directory="..",
                        progress_callback=progress_callback
                    )

                    if status_update == True:
                        logger.updater.info("Update found")
                        update_flow.emit_progress(
                            progress_callback,
                            "update_found",
                            "Update found",
                            progress=54
                        )
                        if self.update_method == "http":
                            temp_exe_file = http_connect.download_file(
                                self.exe_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)[0]
                        else:
                            temp_exe_file = ftp_connect.download_file(
                                self.exe_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)[0]
                        update_flow.emit_progress(
                            progress_callback,
                            "update_file_downloaded",
                            f"File '{self.exe_name}' downloaded",
                            progress=60
                        )

                        size_file = self.get_size_file(temp_exe_file)
                        temp_file_version = self.get_exe_version(temp_exe_file)
                        file_hash = self.file_sha256(os.path.abspath(temp_exe_file))

                        if not self.signature_check_disable_config == self.signature_check_disable_key:
                            signature = self.sign_metadata(temp_file_version, size_file, self.exe_name, file_hash)

                            if not signature == self.exe_signature:
                                logger.updater.warn(f"File '{self.exe_name}' failed authenticity verification")
                                self.clear_update_resources()
                                result = update_flow.UpdateResult(
                                    False,
                                    False,
                                    f"File '{self.exe_name}' failed authenticity verification"
                                )
                            else:
                                logger.updater.info(f"File '{self.exe_name}' passed authenticity verification")
                                update_flow.emit_progress(
                                    progress_callback,
                                    "update_file_verified",
                                    f"File '{self.exe_name}' passed authenticity verification",
                                    progress=66
                                )
                                update_status = self.update_run(
                                    temp_file_version,
                                    main_file_path=main_file,
                                    http_connection=http_connect,
                                    ftp_connection=ftp_connect,
                                    progress_callback=progress_callback
                                )
                                if update_status:
                                    result = update_flow.completed_result(updated=True)
                        else:
                            logger.updater.warn("Warning: server file signature verification is disabled")
                            update_status = self.update_run(
                                temp_file_version,
                                main_file_path=main_file,
                                http_connection=http_connect,
                                ftp_connection=ftp_connect,
                                progress_callback=progress_callback
                            )
                            if update_status:
                                result = update_flow.completed_result(updated=True)
                    else:
                        logger.updater.info("Update not found")
                        self.clear_update_resources()
                        result = update_flow.completed_result(updated=False)

                except Exception:
                    logger.updater.error(f"Failed to perform the update", exc_info=True)
                    result = update_flow.UpdateResult(False, False, "Failed to perform the update")

                if result.success:
                    update_flow.emit_progress(
                        progress_callback,
                        "completed",
                        result.message,
                        status="completed",
                        progress=100
                    )
                elif progress_callback is not None:
                    update_flow.emit_progress(
                        progress_callback,
                        "error",
                        result.message,
                        status="error"
                    )

                if cleanup_on_complete:
                    self.clear_temp()
                if exit_on_complete:
                    os._exit(0)
                return result
            except Exception:
                logger.updater.critical(f"Unexpected interruption of the main thread occurred", exc_info=True)
                if cleanup_on_complete:
                    self.clear_temp()
                if exit_on_complete:
                    os._exit(1)
                result = update_flow.UpdateResult(False, False, "Unexpected interruption of the main thread occurred")
                update_flow.emit_progress(progress_callback, "error", result.message, status="error")
                return result
        else:
            try:
                updater_file = "updater.json" # определяем файл конфига, который нам так же нужно скопировать во временную директорию
                configs.read_config_file(updater_file, create=True)
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)
                # Копируем исполняемый файл в указанную директорию
                temp_exe = os.path.join(temp_dir, os.path.basename(main_file))
                source_file = os.path.basename(sys.argv[0])
                shutil.copy(source_file, temp_exe)
                # Копируем файл updater.json во временную директорию
                updater_temp = os.path.join(temp_dir, updater_file)
                shutil.copy(updater_file, updater_temp)
                # Запускаем копию утилиты из временной директории
                if forwarded_args:
                    subprocess.Popen([temp_exe] + forwarded_args, cwd=os.path.dirname(main_file))
                else:
                    subprocess.Popen(temp_exe, cwd=os.path.dirname(main_file))
                os._exit(0)
            except Exception:
                logger.updater.critical(f"Failed to start the update", exc_info=True)
                os._exit(1)

if __name__ == "__main__":
    ftp_connect = connectors.FtpConnection()
    http_connect = connectors.HttpConnection()
    updater = Updater()

    checking_launch_arguments()
    args = parse_update_mode_arguments(sys.argv[1:])
    main_file = os.path.abspath(sys.argv[0]) # получаем текущую директорию
    logger.updater.debug(f"Current directory: {main_file}")
    work_directory = os.getcwd()
    temp_dir = os.path.abspath("_temp")  #  получение пути к временной директории
    logger.updater.debug(f"Temporary directory: {temp_dir}")

    if args.check:
        update_scenarios.run_check_mode(
            updater,
            http_connect,
            ftp_connect,
            application_directory=os.path.abspath("..")
        )

    if main_file.startswith(temp_dir):
        if args.upgrade:
            update_scenarios.run_upgrade_mode(
                updater,
                main_file,
                temp_dir,
                command=args.cmd,
                gui=args.gui
            )
        else:
            updater.main(main_file, temp_dir)
    else:
        if args.upgrade:
            updater.main(
                main_file,
                temp_dir,
                forwarded_args=update_scenarios.build_forwarded_upgrade_args(
                    command=args.cmd,
                    gui=args.gui,
                    logs_dir=args.logs_dir,
                    logs_level=args.logs_level,
                    logs_clear=args.logs_clear
                )
            )
        else:
            updater.main(main_file, temp_dir)
