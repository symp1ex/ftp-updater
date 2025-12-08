import logger
import sys_manager
import os
import ftplib
import time

class FtpContextManager:
    def __init__(self, server, username, password):
        self.server = server
        self.username = username
        self.password = password
        self.ftp = None

    def __enter__(self):
        self.ftp = ftplib.FTP(self.server)
        self.ftp.login(self.username, self.password)
        return self.ftp

    def __exit__(self, exc_type, exc_value, traceback):
        if self.ftp:
            try: self.ftp.quit()
            except: pass

class FtpConnection(sys_manager.ResourceManagement):
    def __init__(self):
        super().__init__()
        self.ftp_server = self.config.get("ftp", {}).get("ftp_server", "")
        self.ftp_username = None
        self.ftp_password = None
        self.ftp_version = None
        self.ftp_signature = None
        self.zip_signature = None
        self.ftp_context = None

        try: self.encryption_enabled = int(self.config.get("ftp", {}).get("userdata", {}).get("encryption", 0))
        except Exception: self.encryption_enabled = 0

    # Параметры FTP сервера
    def get_ftp_userdata(self):
        try:
            if self.encryption_enabled == False:
                self.ftp_username = self.config["ftp"]["userdata"].get("ftp_username")
                self.ftp_password = self.config["ftp"]["userdata"].get("ftp_password")
                logger.updater.warn("Шифрование пользовательских данных для подключения к FTP-серверу отключено")

                self.ftp_context = lambda: FtpContextManager(
                    self.ftp_server,
                    self.ftp_username,
                    self.ftp_password
                )
            else:
                self.ftp_username = self.decrypt_data(self.config["ftp"]["userdata"].get("ftp_username"))
                self.ftp_password = self.decrypt_data(self.config["ftp"]["userdata"].get("ftp_password"))
                logger.updater.debug("Пользовательские данные для подключения к FTP-серверу успешно расшифрованы")

                self.ftp_context = lambda: FtpContextManager(
                    self.ftp_server,
                    self.ftp_username,
                    self.ftp_password
                )
        except Exception:
            logger.updater.error("Не удалось определить тип пользовательских данных для подключения к FTP-серверу",
                                 exc_info=True)
            self.clear_temp()
            os._exit(1)

    def check_ftp_version(self, file_name, remote_path, timeout_update, max_attempts, attempt):
        try:
            ftp_file_path = self.download_file(file_name, remote_path, timeout_update, max_attempts, attempt)
            if ftp_file_path:
                self.read_manifest()
                self.get_name_zip()
                # Получение версии файла на фтп
                self.ftp_version = self.manifest[self.exe_name].get("version")
                if self.ftp_version:
                    logger.updater.info(f"Версия файла на сервере: {self.ftp_version}")

                self.ftp_signature = self.manifest[self.exe_name].get("signature")
                if self.ftp_signature:
                    logger.updater.debug(f"Подпись файла на сервере: '{self.ftp_signature}'")

                if self.zip_name:
                    self.zip_signature = self.manifest[self.zip_name].get("signature")
                    if self.zip_signature:
                        logger.updater.debug(f"Подпись zip-архива на сервере: '{self.zip_signature}'")
                        return
                    logger.updater.debug(f"Подпись zip-архива на сервере: '{None}'")
        except Exception:
            logger.updater.error(f"Не удалось проверить версию файла на FTP-сервере", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def download_file(self, file_name, remote_path, timeout_update, max_attempts, attempt):
        # путь до файла на фтп с которым сравнивается версия и подпись
        remote_file_path = f"{remote_path}/{os.path.basename(file_name)}"
        try:
            temp_resources_path = os.path.dirname(self.manifest_file)

            if not os.path.exists(temp_resources_path):
                os.makedirs(temp_resources_path)
                logger.updater.debug(f"Создана временная директория для загрузки файлов обновления: '{temp_resources_path}'")

            # Создание временного файла для загрузки
            local_file_path = os.path.join(temp_resources_path, os.path.basename(remote_file_path))

            # Загрузка файла с FTP сервера
            with self.ftp_context() as ftp:
                with open(local_file_path, 'wb') as local_file:
                    ftp.retrbinary('RETR ' + remote_file_path, local_file.write)

            logger.updater.info(f"Файл '{remote_file_path}' успешно загружен в директорию '{os.path.dirname(local_file_path)}'")
            return local_file_path
        except Exception:
            if attempt < max_attempts:
                logger.updater.warn(
                    f"Попытка ({attempt}) загрузить файл '{remote_file_path}' не удалась. Повторная попытка через ({timeout_update}) секунд...")
                attempt += 1
                time.sleep(timeout_update)
                return self.download_file(file_name, remote_path, timeout_update, max_attempts, attempt)
            else:
                logger.updater.error(f"Не удалось загрузить файл '{remote_file_path}' после ({max_attempts}) попыток", exc_info=True)
                self.clear_temp()
                os._exit(1)

    def upload(self, date_path, send_timeout, max_attempts, attempt):
        try:
            with self.ftp_context() as ftp:
                for name in os.listdir(date_path):
                    localpath = os.path.join(date_path, name)
                    if os.path.isfile(localpath):
                        ftp.storbinary('STOR ' + name, open(localpath, 'rb'))
                    elif os.path.isdir(localpath):
                        try:
                            ftp.mkd(name)
                        except ftplib.error_perm as e:
                            if not e.args[0].startswith('550'):
                                raise
                        ftp.cwd(name)
                        for file in os.listdir(localpath):
                            file_path = os.path.join(localpath, file)
                            if os.path.isfile(file_path):
                                remote_file_path = os.path.join(name, file).replace("\\", "/")
                                ftp.storbinary('STOR ' + file, open(file_path, 'rb'))
                        ftp.cwd("..")
            logger.updater.info("Передача данных на сервер завершена")
            return True
        except Exception:
            if attempt < max_attempts:
                logger.updater.warn(
                    f"Попытка ({attempt}) отправки данных не удалась. Повторная попытка через ({send_timeout}) секунд...")
                attempt += 1
                time.sleep(send_timeout)
                return self.upload(date_path, send_timeout, max_attempts, attempt)
            else:
                logger.updater.error(f"Отправка данных на сервер не удалась после ({max_attempts}) попыток",
                                     exc_info=True)
