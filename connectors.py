import logger
import sys_manager
import os
import ftplib
import time

class FtpConnection(sys_manager.ResourceManagement):
    def __init__(self):
        super().__init__()
        self.ftp_server = self.config["ftp"].get("ftp_server")
        self.ftp_username = None
        self.ftp_password = None

        try: self.encryption_enabled = int(self.config.get("ftp", {}).get("userdata", {}).get("encryption", 0))
        except Exception: self.encryption_enabled = 0

    # Параметры FTP сервера
    def get_ftp_userdata(self):
        try:
            if self.encryption_enabled == False:
                self.ftp_username = self.config["ftp"]["userdata"].get("ftp_username")
                self.ftp_password = self.config["ftp"]["userdata"].get("ftp_password")
                logger.updater.warn("Шифрование пользовтельских данных для подключения к FTP-серверу отключено")
            else:
                self.ftp_username = self.decrypt_data(self.config["ftp"]["userdata"].get("ftp_username"))
                self.ftp_password = self.decrypt_data(self.config["ftp"]["userdata"].get("ftp_password"))
                logger.updater.debug("Пользовтельские данные для подключения к FTP-серверу успешно расшифрованы")
        except Exception:
            logger.updater.error("Не удалось определить тип пользовательских данных для подключения к FTP-серверу",
                                 exc_info=True)
            self.clear_temp()
            os._exit(1)

    def check_ftp_version(self, file_name, exe_name, remote_path, timeout_update, max_attempts, attempt):
        try:
            ftp_file_path = self.download_file(file_name, remote_path, timeout_update, max_attempts, attempt)
            if ftp_file_path:
                self.read_manifest()
                # Получение версии файла на фтп
                ftp_version = self.manifest[exe_name].get("version")
                ftp_signature = self.manifest[exe_name].get("signature")
                if ftp_version:
                    logger.updater.info(f"Версия файла на сервере: {ftp_version}")
                    logger.updater.debug(f"Подпись файла на сервере: '{ftp_signature}'")
                    return ftp_version, ftp_signature
        except Exception:
            logger.updater.error(f"Не удалось проверить версию файла на FTP-сервере", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def download_file(self, file_name, remote_path, timeout_update, max_attempts, attempt):
        ftp = None
        remote_file_path = f"{remote_path}/{os.path.basename(file_name)}"  # путь до файла на фтп с которым сравнивается версия и подпись
        try:
            temp_resources_path = os.path.dirname(self.manifest_file)

            # Установка соединения с FTP сервером
            ftp = ftplib.FTP(self.ftp_server)
            ftp.login(self.ftp_username, self.ftp_password)

            if not os.path.exists(temp_resources_path):
                os.makedirs(temp_resources_path)
                logger.updater.debug(f"Создана временная директория для загрузки файлов обновления: '{temp_resources_path}'")

            # Создание временного файла для загрузки
            local_file_path = os.path.join(temp_resources_path, os.path.basename(remote_file_path))
            # Загрузка файла с FTP сервера
            with open(local_file_path, 'wb') as local_file:
                ftp.retrbinary('RETR ' + remote_file_path, local_file.write)

            logger.updater.debug(f"Файл '{remote_file_path}' успешно загружен в директорию '{os.path.dirname(local_file_path)}'")
            # Закрытие соединения с FTP сервером
            ftp.quit()

            return local_file_path
        except Exception:
            if attempt < max_attempts:
                try:
                    ftp.quit()
                except:
                    pass
                logger.updater.warn(
                    f"Попытка ({attempt}) загрузить файл '{remote_file_path}' не удалась. Повторная попытка через ({timeout_update}) секунд...")
                attempt += 1
                time.sleep(timeout_update)
                return self.download_file(file_name, remote_path, timeout_update, max_attempts, attempt)
            else:
                try:
                    ftp.quit()
                except:
                    pass
                logger.updater.error(f"Не удалось загрузить файл '{remote_file_path}' после ({max_attempts}) попыток", exc_info=True)
                self.clear_temp()
                os._exit(1)

    def upload(self, date_path, send_timeout, max_attempts, attempt):
        ftp = None
        try:
            ftp = ftplib.FTP(self.ftp_server)
            ftp.login(self.ftp_username, self.ftp_password)

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
            ftp.quit()
            logger.updater.info("Передача данных на сервер завершена")
            return True
        except Exception:
            if attempt < max_attempts:
                try:
                    ftp.quit()
                except:
                    pass
                logger.updater.warn(
                    f"Попытка ({attempt}) отправки данных не удалась. Повторная попытка через ({send_timeout}) секунд...")
                attempt += 1
                time.sleep(send_timeout)
                return self.upload(date_path, send_timeout, max_attempts, attempt)
            else:
                try:
                    ftp.quit()
                except:
                    pass
                logger.updater.error(f"Отправка данных на сервер не удалась после ({max_attempts}) попыток",
                                     exc_info=True)
