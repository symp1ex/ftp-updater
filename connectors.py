import logger
import sys_manager
import os
import ftplib
import time
import requests

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
        self.ftp_username = self.config["ftp"]["userdata"].get("ftp_username", "")
        self.ftp_password = self.config["ftp"]["userdata"].get("ftp_password", "")
        self.ftp_context = None

        try: self.encryption_enabled = int(self.config.get("ftp", {}).get("userdata", {}).get("encryption", 0))
        except Exception: self.encryption_enabled = 0

    # Параметры FTP сервера
    def get_ftp_userdata(self):
        try:
            if self.encryption_enabled == True:
                self.ftp_username = self.decrypt_data(self.config["ftp"]["userdata"].get("ftp_username"))
                self.ftp_password = self.decrypt_data(self.config["ftp"]["userdata"].get("ftp_password"))
                logger.updater.debug("Пользовательские данные для подключения к FTP-серверу успешно расшифрованы")
            else:
                logger.updater.warn("Шифрование пользовательских данных для подключения к FTP-серверу отключено")

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

            logger.updater.info(
                f"С FTP-сервера успешно загружен файл '{remote_file_path}' в директорию '{os.path.dirname(local_file_path)}'")
            return local_file_path, "ftp"
        except Exception:
            if attempt < max_attempts:
                logger.updater.warn(
                    f"Попытка ({attempt}) загрузить файл '{remote_file_path}' с FTP-сервера не удалась. Повторная попытка через ({timeout_update}) секунд...")
                attempt += 1
                time.sleep(timeout_update)
                return self.download_file(file_name, remote_path, timeout_update, max_attempts, attempt)
            else:
                logger.updater.error(f"Не удалось загрузить файл '{remote_file_path}' с FTP-сервера после ({max_attempts}) попыток", exc_info=True)
                self.clear_temp()
                os._exit(1)

class HttpConnection(sys_manager.ResourceManagement):
    def __init__(self):
        super().__init__()
        try: self.http_update_enabled = int(self.config.get("update", {}).get("http_update", {}).get("enabled", 0))
        except: self.http_update_enabled = 0

        try: self.ftp_mirror_update_enabled = int(
            self.config.get("update", {}).get("http_update", {}).get("ftp_mirror_update", 0))
        except: self.ftp_mirror_update_enabled = 0

        try: self.encryption_enabled = int(
            self.config.get("update", {}).get("http_update", {}).get("data_connection", {}).get("encryption", 0))
        except Exception: self.encryption_enabled = 0

        self.base_url = self.config.get("update", {}).get("http_update", {}).get("data_connection", {}).get("url", "")

    def get_url(self):
        if self.encryption_enabled == True:
            self.base_url = self.decrypt_data(self.base_url)
            logger.updater.debug("Url-адрес для загрузки обновления успешно расшифрован")
            return
        logger.updater.warning("Шифрование url-адреса отключено")

    def download_file(self, file_name, remote_path, timeout_update, max_attempts, attempt):
        temp_resources_path = os.path.dirname(self.manifest_file)

        if not os.path.exists(temp_resources_path):
            os.makedirs(temp_resources_path)
            logger.updater.debug(
                f"Создана временная директория для загрузки файлов обновления: '{temp_resources_path}'")

        local_file_path = os.path.join(temp_resources_path, file_name)

        # Убедимся, что base_url заканчивается на "/"
        if not self.base_url.endswith('/'):
            self.base_url += '/'

        url = self.base_url + os.path.basename(file_name)
        try:
            logger.updater.debug(f"Отправляем HTTP-запрос на загрузку файла '{os.path.basename(file_name)}'")
            response = requests.get(url, stream=True)

            # Проверяем успешность запроса
            if response.status_code == 200:
                logger.updater.debug(f"Код ответа: {response.status_code}")
                # Открываем файл для записи в бинарном режиме
                with open(local_file_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                logger.updater.info(
                    f"С HTTP-хранилища успешно загружен файл '{os.path.basename(file_name)}' в директорию '{os.path.dirname(local_file_path)}'")
            else:
                raise Exception(
                    f"Не удалось загрузить файл '{os.path.basename(file_name)}' с HTTP-хранилища. Код ответа: {response.status_code}")
            return local_file_path, "http"
        except Exception:
            if attempt < max_attempts:
                logger.updater.warn(
                    f"Попытка ({attempt}) загрузить файл '{os.path.basename(file_name)}' "
                    f"с HTTP-хранилища не удалась. Повторная попытка через ({timeout_update}) секунд...")
                attempt += 1
                time.sleep(timeout_update)
                return self.download_file(file_name, remote_path, timeout_update, max_attempts, attempt)
            else:
                logger.updater.error(
                    f"Не удалось загрузить файл '{os.path.basename(file_name)}' с HTTP-хранилища после "
                    f"({max_attempts}) попыток", exc_info=True)

                if self.ftp_mirror_update_enabled:
                    ftp_connect = FtpConnection()
                    ftp_connect.get_ftp_userdata()
                    local_file_path, update_method = ftp_connect.download_file(
                        file_name, remote_path, timeout_update, max_attempts, attempt=1)
                    return local_file_path, update_method
                else:
                    self.clear_temp()
                    os._exit(1)
                    