import logger
import sys_manager
import os
import ftplib
import requests
import update_flow

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
            try:
                if exc_type is not None and issubclass(exc_type, update_flow.UpdateCancelled):
                    self.ftp.close()
                else:
                    self.ftp.quit()
            except: pass

class FtpConnection(sys_manager.ResourceManagement):
    def __init__(self):
        super().__init__()
        self.ftp_server = self.config.get("ftp", {}).get("ftp_server", "")
        self.ftp_username = self.config.get("ftp", {}).get("userdata", {}).get("ftp_username", "")
        self.ftp_password = self.config.get("ftp", {}).get("userdata", {}).get("ftp_password", "")
        self.ftp_context = None

        try: self.encryption_enabled = int(self.config.get("ftp", {}).get("userdata", {}).get("encryption", 0))
        except Exception: self.encryption_enabled = 0

    # Параметры FTP сервера
    def get_ftp_userdata(self):
        try:
            if self.encryption_enabled == True:
                self.ftp_username = self.decrypt_data(self.config["ftp"]["userdata"].get("ftp_username"))
                self.ftp_password = self.decrypt_data(self.config["ftp"]["userdata"].get("ftp_password"))
                logger.updater.debug("User credentials for connecting to the FTP server were successfully decrypted")
            else:
                logger.updater.warn("Encryption of user credentials for connecting to the FTP server is disabled")

            self.ftp_context = lambda: FtpContextManager(
                self.ftp_server,
                self.ftp_username,
                self.ftp_password
            )
        except Exception:
            logger.updater.error("Failed to determine the type of user credentials for connecting to the FTP server",
                                 exc_info=True)
            self.clear_temp()
            os._exit(1)

    def download_file(
            self,
            file_name,
            remote_path,
            timeout_update,
            max_attempts,
            attempt,
            cancel_event=None):
        # путь до файла на фтп с которым сравнивается версия и подпись
        remote_file_path = f"{remote_path}/{os.path.basename(file_name)}"
        try:
            update_flow.check_cancelled(cancel_event)
            temp_resources_path = os.path.dirname(self.manifest_file)

            if not os.path.exists(temp_resources_path):
                os.makedirs(temp_resources_path)
                logger.updater.debug(f"Created a temporary directory for downloading update files: '{temp_resources_path}'")

            # Создание временного файла для загрузки
            local_file_path = os.path.join(temp_resources_path, os.path.basename(remote_file_path))

            # Загрузка файла с FTP сервера
            with self.ftp_context() as ftp:
                with open(local_file_path, 'wb') as local_file:
                    def write_chunk(chunk):
                        update_flow.check_cancelled(cancel_event)
                        local_file.write(chunk)

                    ftp.retrbinary('RETR ' + remote_file_path, write_chunk)

            update_flow.check_cancelled(cancel_event)
            logger.updater.info(
                f"File '{remote_file_path}' was successfully downloaded from the FTP server to '{os.path.dirname(local_file_path)}'")
            return local_file_path, "ftp"
        except update_flow.UpdateCancelled:
            try:
                os.remove(local_file_path)
            except (FileNotFoundError, UnboundLocalError):
                pass
            raise
        except Exception:
            if attempt < max_attempts:
                logger.updater.warn(
                    f"Attempt ({attempt}) to download file '{remote_file_path}' from the FTP server failed. Retrying in ({timeout_update}) seconds...")
                attempt += 1
                update_flow.wait_or_cancel(cancel_event, timeout_update)
                return self.download_file(
                    file_name,
                    remote_path,
                    timeout_update,
                    max_attempts,
                    attempt,
                    cancel_event=cancel_event
                )
            else:
                logger.updater.error(f"Failed to download file '{remote_file_path}' from the FTP server after ({max_attempts}) attempts", exc_info=True)
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
            logger.updater.debug("URL for downloading the update was successfully decrypted")
            return
        logger.updater.warning("URL encryption is disabled")

    def download_file(
            self,
            file_name,
            remote_path,
            timeout_update,
            max_attempts,
            attempt,
            cancel_event=None):
        temp_resources_path = os.path.dirname(self.manifest_file)

        if not os.path.exists(temp_resources_path):
            os.makedirs(temp_resources_path)
            logger.updater.debug(
                f"Created a temporary directory for downloading update files: '{temp_resources_path}'")

        local_file_path = os.path.join(temp_resources_path, file_name)

        # Убедимся, что base_url заканчивается на "/"
        if not self.base_url.endswith('/'):
            self.base_url += '/'

        url = self.base_url + os.path.basename(file_name)
        response = None
        try:
            update_flow.check_cancelled(cancel_event)
            logger.updater.debug(f"Sending an HTTP request to download file '{os.path.basename(file_name)}'")
            response = requests.get(url, stream=True)
            update_flow.check_cancelled(cancel_event)

            # Проверяем успешность запроса
            if response.status_code == 200:
                logger.updater.debug(f"Response code: {response.status_code}")
                # Открываем файл для записи в бинарном режиме
                with open(local_file_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        update_flow.check_cancelled(cancel_event)
                        if chunk:
                            file.write(chunk)
                update_flow.check_cancelled(cancel_event)
                logger.updater.debug(
                    f"File '{os.path.basename(file_name)}' was successfully downloaded from HTTP storage to '{os.path.dirname(local_file_path)}'")
            else:
                raise Exception(
                    f"Failed to download file '{os.path.basename(file_name)}' from HTTP storage. Response code: {response.status_code}")
            return local_file_path, "http"
        except update_flow.UpdateCancelled:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            try:
                os.remove(local_file_path)
            except FileNotFoundError:
                pass
            raise
        except Exception:
            if attempt < max_attempts:
                logger.updater.warn(
                    f"Attempt ({attempt}) to download file '{os.path.basename(file_name)}' "
                    f"from HTTP storage failed. Retrying in ({timeout_update}) seconds...")
                attempt += 1
                update_flow.wait_or_cancel(cancel_event, timeout_update)
                return self.download_file(
                    file_name,
                    remote_path,
                    timeout_update,
                    max_attempts,
                    attempt,
                    cancel_event=cancel_event
                )
            else:
                logger.updater.error(
                    f"Failed to download file '{os.path.basename(file_name)}' from HTTP storage after "
                    f"({max_attempts}) attempts", exc_info=True)

                if self.ftp_mirror_update_enabled:
                    ftp_connect = FtpConnection()
                    ftp_connect.get_ftp_userdata()
                    local_file_path, update_method = ftp_connect.download_file(
                        file_name,
                        remote_path,
                        timeout_update,
                        max_attempts,
                        attempt=1,
                        cancel_event=cancel_event
                    )
                    return local_file_path, update_method
                else:
                    self.clear_temp()
                    os._exit(1)
                    
