import logger
import configs
import sys_manager
import connectors
import about
import subprocess
import sys
import os
import time
import shutil

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

    def check_new_version(self, file_name, remote_path, timeout_update, max_attempts, attempt):
        try:
            if self.update_method == "http":
                file_path, update_method = http_connect.download_file(
                    file_name, remote_path, timeout_update, max_attempts, attempt)
                self.update_method = update_method
            else:
                file_path = ftp_connect.download_file(file_name, remote_path, timeout_update, max_attempts, attempt)[0]

            if file_path:
                self.read_manifest()
                self.get_name_zip()
                # Получение версии файла на фтп
                self.new_version = self.manifest[self.exe_name].get("version")
                if self.new_version:
                    logger.updater.info(f"Версия файла на сервере: {self.new_version}")

                self.exe_signature = self.manifest[self.exe_name].get("signature")
                if self.exe_signature:
                    logger.updater.debug(f"Подпись файла на сервере: '{self.exe_signature}'")

                if self.zip_name:
                    self.zip_signature = self.manifest[self.zip_name].get("signature")
                    if self.zip_signature:
                        logger.updater.debug(f"Подпись zip-архива на сервере: '{self.zip_signature}'")
                        return
                    logger.updater.debug(f"Подпись zip-архива на сервере: '{None}'")
        except Exception:
            logger.updater.error(f"Не удалось проверить версию файла на удалённом сервере", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def local_version(self, parent_directory):
        try:
            file_path = f"{parent_directory}\\{self.exe_name}"  # путь до локального файла с которым сравнивается версия
            logger.updater.debug(f"Получаем информацию о версии файла: '{os.path.abspath(file_path)}'")
            local_version = self.get_exe_version(file_path)
            if local_version:
                logger.updater.info(f"Версия исходного файла: {local_version}")
                return local_version
        except Exception:
            logger.updater.error(f"Не удалось проверить версию исходного файла", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def check_update(self, local_version):
        try:
            # Разбиваем версии на части и преобразуем их в числа
            parts1 = list(map(int, self.new_version.split('.')))
            parts2 = list(map(int, local_version.split('.')))

            # Сравниваем каждую часть версии, начиная с первой
            for i in range(len(parts1)):
                if parts1[i] > parts2[i]:
                    return True  # Версия первого файла выше
                elif parts1[i] < parts2[i]:
                    return False  # Версия первого файла ниже
            return False  # Версии идентичны
        except Exception:
            logger.updater.error(
                f"Не удалось преобразовать информацию о версии файла '{self.new_version}' "
                f"в подходящий формат для сравнения с '{local_version}'", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def upgrade(self, local, attempt):
        try:
            logger.updater.debug(f"Определён путь к исполняемому файлу предыдущей версии: "
                                 f"'{os.path.abspath(self.old_file)}'")
            # Проверяем и удаляем временный файл если он существует
            if os.path.exists(self.temp_old_file):
                os.remove(self.temp_old_file)
                logger.updater.debug(f"Удален существующий временный файл: '{os.path.abspath(self.temp_old_file)}'")

            os.rename(self.old_file, self.temp_old_file)
            logger.updater.debug(f"Сделана резервная копия исполняемого файла перед обновлением: "
                                 f"'{os.path.abspath(self.temp_old_file)}'")

            temp_new_file = os.path.join(os.path.dirname(self.manifest_file), self.exe_name)
            logger.updater.debug(f"Определён путь к временному файлу обновления: '{os.path.abspath(temp_new_file)}'")
            shutil.copy2(temp_new_file, self.old_file)
            logger.updater.debug(f"Временный файл '{temp_new_file}' был скопирован в директорию "
                                 f"'{os.path.abspath(local)}'")

            if not self.signature_check_disable_config == self.signature_check_disable_key:
                logger.updater.debug(f"Проверяем целостность исполняемого файла: '{os.path.abspath(self.old_file)}'")
                size_file = self.get_size_file(os.path.abspath(self.old_file))
                temp_file_version = self.get_exe_version(os.path.abspath(self.old_file))
                originalfilename = self.get_file_metadata(os.path.abspath(self.old_file), "OriginalFilename")

                signature = self.sign_metadata(temp_file_version, size_file, os.path.basename(self.old_file),
                                               originalfilename)

                if not signature == self.exe_signature:
                    self.restore_file()
                    raise ValueError(f"Установленный файл '{os.path.abspath(self.old_file)}' "
                                     f"не прошёл проверку целостности и был удалён")
                else:
                    logger.updater.info(f"Проверка целостности пройдена, файл '{os.path.abspath(self.old_file)}' "
                                        f"успешно обновлён")
                    if self.zip_name:
                        self.unzip_and_get_files("..")
                    update_successful = True

            else:
                logger.updater.info(f"Файл '{os.path.abspath(self.old_file)}' успешно обновлён")
                if self.zip_name:
                    self.unzip_and_get_files("..")
                update_successful = True

            if update_successful:
                logger.updater.info("Обновление установлено")  # Выводим сообщение только если обновление успешно
                shutil.rmtree(os.path.dirname(self.manifest_file))
                logger.updater.debug(f"Временная директория '{os.path.dirname(self.manifest_file)}' удалена")
                os.remove(self.temp_old_file)
                logger.updater.debug(f"Резервная копия исполняемого файла "
                                     f"'{os.path.abspath(self.temp_old_file)}' удалена")
                return
        except Exception:
            if attempt < self.max_attempts_update:
                logger.updater.warn(
                    f"Попытка ({attempt}) установить обновление, не удалась. Повторная попытка через "
                    f"({self.timeout_update}) секунд...")
                attempt += 1
                time.sleep(self.timeout_update)
                return self.upgrade(local, attempt)
            else:
                logger.updater.error(f"Не удалось произвести обновление после ({self.max_attempts_update}) попыток",
                                     exc_info=True)
                shutil.rmtree(os.path.dirname(self.manifest_file))
                logger.updater.debug(f"Временная директория '{os.path.dirname(self.manifest_file)}' удалена")
                self.clear_temp()
                os._exit(1)

    def update_run(self, temp_file_version):
        logger.updater.debug(f"Версия загруженного файла: {temp_file_version}")
        if temp_file_version != self.new_version:
            logger.updater.warn(f"Версия загруженного файла отличается от данных 'manifest.json', "
                                f"процесс обновления будет прерван")
            shutil.rmtree(os.path.dirname(self.manifest_file))
            logger.updater.debug(f"Временная директория '{os.path.dirname(self.manifest_file)}' удалена")
            return

        if self.zip_name:
            if self.update_method == "http":
                self.zip_path = http_connect.download_file(
                    self.zip_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)[0]
            else:
                self.zip_path = ftp_connect.download_file(
                    self.zip_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)[0]

            if not self.signature_check_disable_config == self.signature_check_disable_key:
                size_file = self.get_size_file(self.zip_path)
                signature = self.sign_metadata(int(size_file / len(self.zip_name)), size_file,
                                               self.zip_name,
                                               "originalfilename")
                if not signature == self.zip_signature:
                    logger.updater.warn(f"Zip-архив '{self.zip_name}' не прошёл проверку подлинности")
                    shutil.rmtree(os.path.dirname(self.manifest_file))
                    logger.updater.debug(f"Временная директория '{os.path.dirname(self.manifest_file)}' удалена")
                    return
                logger.updater.info(f"Для zip-архива '{self.zip_name}' успешно пройдена проверка подлинноcти")
        try:
            if self.action_startup == True:
                self.action_run(self.startup_script, main_file, timeout=True)
                wait_stop_app = self.check_process_cycle(self.exe_name)

                if wait_stop_app == True:
                    try:
                        logger.updater.info("Начато обновление")
                        self.upgrade("..\\", attempt=1)

                        if self.action_completion == True:
                            self.action_run(self.complete_script, main_file)
                    except Exception:
                        logger.updater.error(f"Не удалось запустить процесс обновления", exc_info=True)

                        if self.action_completion == True:
                            self.action_run(self.complete_script, main_file)

                        self.clear_temp()
                        os._exit(1)
            else:
                if self.action_completion == True:
                    self.action_run(self.complete_script, main_file)
        except Exception:
            logger.updater.error(f"Запуск скриптов управления завершился ошибкой", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def main(self, main_file, temp_dir):
        if main_file.startswith(temp_dir): # если udater запущен из временной директории, то запускаем процесс обновления
            try:
                logger.updater.info(f"updater.exe запущен")
                logger.updater.info(f"Версия исполняемого файла: {about.version}")
                logger.updater.debug(f"Рабочая директория: '{work_directory}'")
                logger.updater.debug(f"Прочитан файл конфигурации: {self.config}")

                if http_connect.http_update_enabled == True:
                    self.update_method = "http"
                    http_connect.get_url()
                    if http_connect.ftp_mirror_update_enabled == True:
                        ftp_connect.get_ftp_userdata()
                else:
                    self.update_method = "ftp"
                    ftp_connect.get_ftp_userdata()

                try:
                    logger.updater.info("Проверяется наличие обновлений")
                    local_version = self.local_version("..")
                    # тут обновляем ftp_version и ftp_signature в ftp_connect
                    self.check_new_version(self.manifest_file, self.remote_path, self.timeout_update,
                                                  self.max_attempts_update, attempt=1)
                    status_update = self.check_update(local_version)

                    if status_update == True:
                        logger.updater.info("Найдено обновление")
                        if self.update_method == "http":
                            temp_exe_file = http_connect.download_file(
                                self.exe_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)[0]
                        else:
                            temp_exe_file = ftp_connect.download_file(
                                self.exe_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)[0]

                        size_file = self.get_size_file(temp_exe_file)
                        temp_file_version = self.get_exe_version(temp_exe_file)
                        originalfilename = self.get_file_metadata(temp_exe_file, "OriginalFilename")

                        if not self.signature_check_disable_config == self.signature_check_disable_key:
                            signature = self.sign_metadata(temp_file_version, size_file, self.exe_name,
                                                           originalfilename)
                            if not signature == self.exe_signature:
                                logger.updater.warn(f"Файл '{self.exe_name}' не прошёл проверку подлинности")
                                shutil.rmtree(os.path.dirname(self.manifest_file))
                                logger.updater.debug(f"Временная директория "
                                                     f"'{os.path.dirname(self.manifest_file)}' удалена")
                            else:
                                logger.updater.info(f"Для файла '{self.exe_name}' успешно пройдена проверка подлинноcти")
                                self.update_run(temp_file_version)
                        else:
                            logger.updater.warn("Внимание, проверка подписи файла на сервере выключена")
                            self.update_run(temp_file_version)
                    else:
                        logger.updater.info("Обновление не найдено")
                        shutil.rmtree(os.path.dirname(self.manifest_file))
                        logger.updater.debug(f"Временная директория '{os.path.dirname(self.manifest_file)}' удалена")

                except Exception:
                    logger.updater.error(f"Не удалось произвести обновление", exc_info=True)
                self.clear_temp()
                os._exit(0)
            except Exception:
                logger.updater.critical(f"Произошло нештатное прерывание основного потока", exc_info=True)
                self.clear_temp()
                os._exit(1)
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
                subprocess.Popen(temp_exe, cwd=os.path.dirname(main_file))
                os._exit(0)
            except Exception:
                logger.updater.critical(f"Не удалось запустить обновление", exc_info=True)
                os._exit(1)

if __name__ == "__main__":
    ftp_connect = connectors.FtpConnection()
    http_connect = connectors.HttpConnection()
    updater = Updater()

    main_file = os.path.abspath(sys.argv[0]) # получаем текущую директорию
    logger.updater.debug(f"Текущая директория: {main_file}")
    work_directory = os.getcwd()
    temp_dir = os.path.abspath("_temp")  #  получение пути к временной директории
    logger.updater.debug(f"Временная директория: {temp_dir}")
    updater.main(main_file, temp_dir)
