import about
import configs
import logger
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
import os
import time
import subprocess
import sys
import hashlib
import win32api
import stat
import zipfile
import update_flow

class ResourceManagement:
    signature_check_disable_key = "aTdW<<9XyeqNM*LS2<"
    signature_public_key = bytes.fromhex("4d37cceab50a53ad61f43535754423cd1ecf9ff0c98ebf4ee8db9ade72df9d51")
    crypto_key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM='

    config_file = os.path.join(about.work_directory, "updater.json")
    manifest_file = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "_resources", "manifest.json")

    def __init__(self):
        self.config = configs.read_config_file(self.config_file, create=True)
        self.exe_name = self.config.get("update", {}).get("exe_name")
        self.old_file = os.path.join("..", self.exe_name)
        self.temp_old_file = os.path.join("..", f"{self.exe_name}._tmp")
        self.zip_name = None
        self.zip_path = None
        self.zip_files_list = None
        self.manifest = None

    def read_manifest(self):
        self.manifest = configs.read_config_file(self.manifest_file)
        logger.updater.debug(f"Data read from file '{os.path.abspath(self.manifest_file)}': {self.manifest}")

    def get_exe_version(self, file_path):
        try:
            info = win32api.GetFileVersionInfo(file_path, '\\')
            version = info['FileVersionMS'] >> 16, info['FileVersionMS'] & 0xFFFF, info['FileVersionLS'] >> 16, info[
                'FileVersionLS'] & 0xFFFF
            logger.updater.debug(f"File metadata read from '{os.path.abspath(file_path)}': {info}")
            return '.'.join(map(str, version))
        except Exception:
            logger.updater.error(f"Failed to check file version: '{os.path.abspath(file_path)}'", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def get_file_metadata(self, file_path, field):  # получение конкретного поля из метаданных исполняемого файла
        try:
            language, codepage = win32api.GetFileVersionInfo(file_path, '\\VarFileInfo\\Translation')[0]
            stringfileinfo = u'\\StringFileInfo\\%04X%04X\\%s' % (
            language, codepage, field)  # конкретное поле LegalCopyright
            result = win32api.GetFileVersionInfo(file_path, stringfileinfo)
            logger.updater.debug(f"Successfully read field '{field}' for file '{file_path}': '{result}'")
        except Exception:
            logger.updater.error(f"Failed to get the file description from the FTP server", exc_info=True)
            result = "unknown"
        return result

    def get_size_file(self, file_path):
        try:
            file_stats = os.stat(file_path)
            size = file_stats[stat.ST_SIZE]
            logger.updater.debug(f"Downloaded file size '{file_path}': {size}")
            return size
        except Exception:
            logger.updater.error(f"Failed to get file size: '{os.path.abspath(file_path)}'", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def get_name_zip(self):
        base_name = self.exe_name.split('.')[0]  # получаем 'file'
        key = f"{base_name}.zip"  # создаем новую строку 'file.zip'

        try:
            # Прямая проверка ключа
            if key in self.manifest:
                self.zip_name = key
                logger.updater.debug(f"Key '{key}' found in '{self.manifest_file}'")
                return True
            logger.updater.debug(f"Key '{key}' not found in '{self.manifest_file}'")
            return False
        except Exception:
            logger.updater.error(f"Error while searching for key '{key}' in {self.manifest_file}", exc_info=True)
            return False

    def restore_file(self):
        try:
            time.sleep(1)
            os.remove(self.old_file)
            time.sleep(1)
            os.rename(self.temp_old_file, self.old_file)
            time.sleep(1)
            logger.updater.info(f"Backup of file '{os.path.abspath(self.old_file)}' was successfully restored")
        except Exception:
            logger.updater.critical(f"Failed to restore backup of file '{os.path.abspath(self.old_file)}'",
                                    exc_info=True)

    def rollback_cancelled_update(self):
        if not getattr(self, "_backup_created_for_update", False):
            return True

        if not os.path.exists(self.temp_old_file):
            logger.updater.critical(
                f"Failed to restore backup of file '{os.path.abspath(self.old_file)}': backup not found"
            )
            return False

        try:
            os.replace(self.temp_old_file, self.old_file)
            self._backup_created_for_update = False
            logger.updater.info(
                f"Backup of file '{os.path.abspath(self.old_file)}' was restored after update cancellation"
            )
            return True
        except Exception:
            logger.updater.critical(
                f"Failed to restore backup of file '{os.path.abspath(self.old_file)}' after update cancellation",
                exc_info=True
            )
            return False

    def unzip_and_get_files(self, extract_path, cancel_event=None, progress_callback=None):
        self.zip_files_list = []
        try:
            update_flow.check_cancelled(cancel_event)
            # Открываем zip архив
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                # Получаем список всех файлов в архиве
                for file_info in zip_ref.infolist():
                    if not file_info.filename.endswith('/'):  # Пропускаем директории
                        self.zip_files_list.append(file_info.filename)
                # Распаковываем архив
                logger.updater.debug(f"File list read from the archive: '{self.zip_files_list}'")
                update_flow.check_cancelled(cancel_event)
                update_flow.emit_progress(
                    progress_callback,
                    "non_cancellable",
                    "The update can no longer be safely cancelled",
                    progress=90
                )
                zip_ref.extractall(extract_path)
                logger.updater.info(f"ZIP archive '{self.zip_path}' was successfully extracted to '{os.path.abspath(extract_path)}'")
        except update_flow.UpdateCancelled:
            raise
        except Exception:
            logger.updater.error(f"Error while extracting archive '{self.zip_path}'", exc_info=True)
            self.restore_file()
            raise

    def file_sha256(self, path, chunk_size=1024 * 1024, cancel_event=None):
        sha256 = hashlib.sha256()
        logger.updater.debug(f"Calculating SHA-256 for file: '{path}'")
        try:
            update_flow.check_cancelled(cancel_event)
            with open(path, "rb") as f:
                while True:
                    update_flow.check_cancelled(cancel_event)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    sha256.update(chunk)
            update_flow.check_cancelled(cancel_event)
            file_hash = str(sha256.hexdigest())
            logger.updater.debug(f"SHA-256 calculated successfully: {file_hash}")
            return file_hash
        except update_flow.UpdateCancelled:
            raise
        except Exception:
            logger.updater.error(f"Failed to calculate SHA-256 for file: '{path}'", exc_info=True)
            return None

    def clear_temp(self):
        #pass
        try:
            main_file = os.path.abspath(sys.argv[0])
            temp_dir = os.path.dirname(main_file)
            if os.path.basename(temp_dir).lower() != "_temp":
                resources_dir = os.path.dirname(self.manifest_file)
                if os.path.exists(resources_dir):
                    import shutil
                    shutil.rmtree(resources_dir)
                    logger.updater.debug(f"Temporary directory '{resources_dir}' deleted")
                return
            # Команда для удаления файла
            command = f"timeout /t 7 > nul && rd /q/s \"{temp_dir}\""
            working_directory = os.path.dirname(os.path.dirname(temp_dir))
            # Выполняем команду в отдельном процессе
            subprocess.Popen(command, shell=True, cwd=working_directory)
            logger.updater.debug(f"Command sent to clean up the temporary directory: '{os.path.abspath(temp_dir)}'")
        except Exception:
            logger.updater.error(f'Failed to clean up the temporary directory', exc_info=True)
            os._exit(1)

    def verify_metadata(self, signature, key1, key2, key3, key4):
        try:
            metadata = f"{key1}:{key2}:{key3}:{key4}"

            public_key = Ed25519PublicKey.from_public_bytes(
                self.signature_public_key
            )

            public_key.verify(
                bytes.fromhex(signature),
                metadata.encode()
            )

            return True

        except InvalidSignature:
            return False

        except Exception:
            logger.updater.error(
                "Failed to verify the signature of the downloaded file",
                exc_info=True
            )
            self.clear_temp()
            os._exit(1)

    # дешифровка параметров подключения из updater.json
    def decrypt_data(self, encrypted_data):
        try:
            cipher = Fernet(self.crypto_key)
            decrypted_data = cipher.decrypt(encrypted_data).decode()
            return decrypted_data
        except Exception:
            logger.updater.error(f"Server authentication failed", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def encrypt_data(self, data):
        try:
            cipher = Fernet(self.crypto_key)
            encrypted_data = cipher.encrypt(data.encode())
            return encrypted_data
        except Exception:
            logger.updater.error("Failed to encrypt data", exc_info=True)
            os._exit(1)

    def create_manifest(self, key):
        try:
            private_key = Ed25519PrivateKey.from_private_bytes(
                bytes.fromhex(key)
            )
        except Exception:
            logger.updater.error(
                "Failed to read the private signature key",
                exc_info=True
            )
            os._exit(1)

        def signed(key1, key2, key3, key4):
            try:
                metadata = f"{key1}:{key2}:{key3}:{key4}"
                signature = private_key.sign(
                    metadata.encode()
                ).hex()
            except Exception:
                logger.updater.error("Failed to get the signature for the file", exc_info=True)
                signature = "None"
            return signature

        try:
            exe_name_0 = self.exe_name.split('.')[0]  # получаем 'file'
            zip_name = f"{exe_name_0}.zip"  # создаем новую строку 'file.zip'
        except Exception:
            logger.updater.error("Failed to get the archive name", exc_info=True)
            zip_name = False

        try:
            version_exe = self.get_exe_version(self.exe_name)
            size_exe = self.get_size_file(self.exe_name)

            file_hash = self.file_sha256(os.path.abspath(self.exe_name))
            if not file_hash:
                logger.updater.warning("'manifest.json' will not be generated")
                return

            signed_exe = signed(version_exe, size_exe, self.exe_name, file_hash)

            try:
                file_stats = os.stat(zip_name)
                size_zip = file_stats[stat.ST_SIZE]
                zip_file = True
            except Exception:
                logger.updater.warning(f"Archive {zip_name} not found")
                zip_file = False

            if zip_file:
                file_hash = self.file_sha256(os.path.abspath(zip_name))
                if not file_hash:
                    logger.updater.warning("'manifest.json' will not be generated")
                    return

                signed_zip = signed(int(size_zip / len(zip_name)), size_zip, zip_name, file_hash)

                manifest_data = {
                    self.exe_name: {
                        "version": version_exe,
                        "signature": signed_exe
                    },
                    zip_name: {
                        "signature": signed_zip
                    }
                }
            else:
                manifest_data = {
                    self.exe_name: {
                        "version": version_exe,
                        "signature": signed_exe
                    }
                }

            configs.write_json_file("manifest.json", manifest_data)
        except Exception:
            logger.updater.error("Failed to create 'manifest.json'", exc_info=True)
            os._exit(1)

    def save_http_config(self, url):
        try:
            if not url:
                logger.updater.warning("Server address is not specified")
                os._exit(1)

            encrypted_url = self.encrypt_data(url).decode()

            self.config["update"]["http_update"]["data_connection"]["url"] = encrypted_url
            self.config["update"]["http_update"]["data_connection"]["encryption"] = True

            configs.write_json_file(
                self.config_file,
                self.config
            )

            logger.updater.info("URL was successfully saved in the configuration")
            os._exit(0)

        except Exception:
            logger.updater.error(
                "Failed to save HTTP URL",
                exc_info=True
            )
            os._exit(1)

    def save_ftp_config(self, ftp_server=None, ftp_user=None, ftp_pass=None):
        try:
            logger.updater.debug("FTP setup mode started")

            if ftp_server:
                self.config["ftp"]["ftp_server"] = ftp_server

            if ftp_user:
                self.config["ftp"]["userdata"]["ftp_username"] = \
                    self.encrypt_data(ftp_user).decode()

            if ftp_pass:
                self.config["ftp"]["userdata"]["ftp_password"] = \
                    self.encrypt_data(ftp_pass).decode()

            if ftp_user or ftp_pass:
                self.config["ftp"]["userdata"]["encryption"] = True

            configs.write_json_file(
                self.config_file,
                self.config
            )

            logger.updater.info("FTP configuration was successfully saved")

        except Exception:
            logger.updater.error(
                "Failed to save FTP configuration",
                exc_info=True
            )
            os._exit(1)

class ProcessManagement(ResourceManagement):
    def __init__(self):
        super().__init__()
        self.startup_script = self.config.get("actions", {}).get("at_startup", {}).get("file_name", "stop.bat")
        self.complete_script = self.config.get("actions", {}).get("at_completion", {}).get("file_name", "start.bat")

        try: self.action_startup = int(self.config.get("actions", {}).get("at_startup", {}).get("enabled", 0))
        except Exception: self.action_startup = 0

        try: self.action_completion = int(self.config.get("actions", {}).get("at_completion", {}).get("enabled", 0))
        except Exception: self.action_completion = 0

        try: self.action_timeout = int(self.config.get("actions", {}).get("at_startup", {}).get("timeout", 15))
        except Exception: self.action_timeout = 15

    def action_run(self, file_name, main_file, timeout=False):
        try:
            file_path = os.path.join(os.path.dirname(main_file), "..\\", file_name)
        except Exception:
            logger.updater.error(f"Failed to determine path to '{file_name}'", exc_info=True)

        try:
            logger.updater.info(f"'{os.path.normpath(file_path)}' will be started")
            if timeout:
                logger.updater.info(f"Work will continue in ({self.action_timeout}) seconds")
            subprocess.Popen(file_path)
        except Exception:
            logger.updater.error(f"Failed to start '{file_path}'", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def check_process(self, file_name):
        try:
            command_str = f'tasklist | findstr /i "{file_name}" >nul'

            result = subprocess.run(
                command_str,
                shell=True,
                capture_output=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False
            )

            if result.returncode == 0:
                logger.updater.debug(f"Process '{file_name}' is active")
                return True
            elif result.returncode == 1:
                logger.updater.debug(f"Process '{file_name}' is inactive")
                return False
            else:
                # Если returncode не 0 или 1, это указывает на ошибку выполнения команды
                logger.updater.warning(
                    f"CMD command execution error for process '{file_name}'. Return code: {result.returncode}",)
                return None

        except FileNotFoundError:
            # Это исключение может возникнуть, если 'cmd.exe' или одна из команд
            # ('tasklist', 'findstr') не найдена в системном PATH.
            logger.updater.error( f"CMD command or its components (tasklist/findstr) were not found. "
                                                 f"Make sure they are available in the system PATH.", exc_info=True)
            return None
        except Exception:
            logger.updater.error(
                f"Failed to get process status for '{file_name}' via CMD (tasklist|findstr)", exc_info=True)
            return None

    def check_process_cycle(self, exe_name, cancel_event=None):
        count_attempt = int(self.action_timeout / 5 + 1)

        try:
            logger.updater.info(f"Checking process activity for '{exe_name}'")
            for attempt in range(count_attempt):
                update_flow.check_cancelled(cancel_event)
                process_found = self.check_process(exe_name)

                if process_found is True:
                    logger.updater.debug(f"Next check in (5) seconds.")
                    update_flow.wait_or_cancel(cancel_event, 5)
                    continue

                if process_found is False:
                    logger.updater.info(f"Process '{exe_name}' has exited or was not running")
                    return True

                logger.updater.warning(
                    f"Failed to determine the state of process '{exe_name}'; "
                    f"the update process will be interrupted"
                )
                return False
            logger.updater.warn(
                f"Process '{exe_name}' remains active for ({self.action_timeout}) seconds; "
                f"the update process will be interrupted")
            return False
        except update_flow.UpdateCancelled:
            raise
        except Exception:
            logger.updater.error(f"Failed to track process state for '{exe_name}'", exc_info=True)
            self.clear_temp()
            os._exit(1)
