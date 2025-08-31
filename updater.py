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
        self.send_data_enabled = self.config.get("send_data", {}).get("enabled", 1)
        self.update_enabled = self.config.get("update", {}).get("enabled", 1)
        self.signature_check_disable_config = self.config.get("update", {}).get("signature_check_disable_key", "")

        self.remote_path = self.config.get("update", {}).get("ftp_path")  # папка на фтп с которой качаются все файлы для обновления
        self.date_path = self.config.get("send_data", {}).get("local_path", "..\\date")  # путь откуда берём данные для отправки

        self.max_attempts_update = self.config.get("update", {}).get("attempt_count", 5)  # количество попыток
        self.timeout_update = self.config.get("update", {}).get("attempt_timeout", 10)  # тайм-аут

        self.max_attempts_send = self.config.get("send_data", {}).get("attempt_count", 5)  # количество попыток отправки
        self.timeout_send = self.config.get("send_data", {}).get("attempt_timeout", 10)  # тайм-аут для отправки

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
            parts1 = list(map(int, ftp_connect.ftp_version.split('.')))
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
                f"Не удалось преобразовать информацию о версии файла '{ftp_connect.ftp_version}' "
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

                if not signature == ftp_connect.ftp_signature:
                    self.restore_file()
                    raise ValueError(f"Установленный файл '{os.path.abspath(self.old_file)}' "
                                     f"не прошёл проверку целостности и был удалён")
                else:
                    logger.updater.info(f"Проверка целостности пройдена, файл '{os.path.abspath(self.old_file)}' "
                                        f"успешно обновлён")
                    if ftp_connect.zip_name:
                        self.unzip_and_get_files("..")
                    update_successful = True

            else:
                logger.updater.info(f"Файл '{os.path.abspath(self.old_file)}' успешно обновлён")
                if ftp_connect.zip_name:
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
        if temp_file_version != ftp_connect.ftp_version:
            logger.updater.warn(f"Версия загруженного файла отличается от данных 'manifest.json', "
                                f"процесс обновления будет прерван")
            shutil.rmtree(os.path.dirname(self.manifest_file))
            logger.updater.debug(f"Временная директория '{os.path.dirname(self.manifest_file)}' удалена")
            return

        if ftp_connect.zip_name:
            self.zip_path = ftp_connect.download_file(ftp_connect.zip_name, self.remote_path,
                                                             self.timeout_update, self.max_attempts_update,
                                                             attempt=1)
            if not self.signature_check_disable_config == self.signature_check_disable_key:
                size_file = self.get_size_file(self.zip_path)
                signature = self.sign_metadata(int(size_file / len(ftp_connect.zip_name)), size_file,
                                               ftp_connect.zip_name,
                                               "originalfilename")
                if not signature == ftp_connect.zip_signature:
                    logger.updater.warn(f"Zip-архив '{ftp_connect.zip_name}' не прошёл проверку подлинности")
                    shutil.rmtree(os.path.dirname(self.manifest_file))
                    logger.updater.debug(f"Временная директория '{os.path.dirname(self.manifest_file)}' удалена")
                    return
                logger.updater.info(f"Для zip-архива '{ftp_connect.zip_name}' успешно пройдена проверка подлинноcти")
        try:
            if self.action_startup == True:
                self.action_run(self.startup_script, main_file, timeout=True)
                wait_stop_app = self.check_procces_cycle(self.exe_name)

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
        #if main_file.startswith(temp_dir): # если udater запущен из временной директории, то запускаем процесс обновления
        try:
            logger.updater.info(f"updater.exe запущен")
            logger.updater.info(f"Версия исполянемого файла: {about.version}")
            logger.updater.debug(f"Рабочая директория: '{work_directory}'")
            logger.updater.debug(f"Прочитан файл конфигурации: {self.config}")
            ftp_connect.get_ftp_userdata()

            if self.send_data_enabled == True:
                logger.updater.debug(f"Попытка передать данные на сервер: '{ftp_connect.ftp_server}'")

                try:
                    logger.updater.debug(f"Параметры передачи:\n"
                                         f"Путь к передаваемому каталогу:'{os.path.abspath(self.date_path)}'\n"
                                         f"Количество попыток передать содержимое каталога:'{self.max_attempts_send}'\n"
                                         f"Таймаут между попытками:'{self.timeout_send}'")

                    os.chdir(self.date_path)  # меняем рабочий каталог с корневого каталога для скрипта на указанный каталог здесь
                    logger.updater.debug(f"Рабочая директория изменена на: '{os.path.abspath(self.date_path)}'")
                    ftp_connect.upload(self.date_path, self.timeout_send, self.max_attempts_send, attempt=1)
                except Exception:
                    logger.updater.error(f"Передача данных на сервер не удалась", exc_info=True)

                os.chdir(work_directory)
                logger.updater.debug(f"Рабочая директория изменена на: '{work_directory}'")

            if self.update_enabled == True:
                try:
                    logger.updater.info("Проверяется наличие обновлений")
                    local_version = self.local_version("..")
                    # тут обновляем ftp_version и ftp_signature в ftp_connect
                    ftp_connect.check_ftp_version(self.manifest_file, self.remote_path, self.timeout_update,
                                                  self.max_attempts_update, attempt=1)
                    status_update = self.check_update(local_version)

                    if status_update == True:
                        logger.updater.info("Найдено обновление")
                        temp_exe_file = ftp_connect.download_file(self.exe_name, self.remote_path,
                                                                  self.timeout_update, self.max_attempts_update,
                                                                  attempt=1)
                        size_file = self.get_size_file(temp_exe_file)
                        temp_file_version = self.get_exe_version(temp_exe_file)
                        originalfilename = self.get_file_metadata(temp_exe_file, "OriginalFilename")

                        if not self.signature_check_disable_config == self.signature_check_disable_key:
                            signature = self.sign_metadata(temp_file_version, size_file, self.exe_name,
                                                           originalfilename)
                            logger.updater.critical(signature)
                            if not signature == ftp_connect.ftp_signature:
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
        # else:
        #     try:
        #         updater_file = "updater.json" # определяем файл конфига, который нам так же нужно скопировать во временную директорию
        #         configs.read_config_file(updater_file, create=True)
        #         if not os.path.exists(temp_dir):
        #             os.makedirs(temp_dir)
        #         # Копируем исполняемый файл в указанную директорию
        #         temp_exe = os.path.join(temp_dir, os.path.basename(main_file))
        #         source_file = "updater.exe"
        #         shutil.copy(source_file, temp_exe)
        #         # Копируем файл updater.json во временную директорию
        #         updater_temp = os.path.join(temp_dir, updater_file)
        #         shutil.copy(updater_file, updater_temp)
        #         # Запускаем копию утилиты из временной директории
        #         subprocess.Popen(temp_exe, cwd=os.path.dirname(main_file))
        #         os._exit(0)
        #     except Exception:
        #         logger.updater.critical(f"Не удалось запустить обновление", exc_info=True)
        #         self.clear_temp()
        #         os._exit(1)

if __name__ == "__main__":
    ftp_connect = connectors.FtpConnection()
    updater = Updater()
    main_file = os.path.abspath(sys.argv[0]) # получаем текущую директорию
    work_directory = os.getcwd()
    temp_dir = os.path.abspath("_temp")  #  получение пути к временной директории
    updater.main(main_file, temp_dir)
