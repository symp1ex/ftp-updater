import logger
import configs
import sys_manager
import connectors
import about
from functools import reduce
import ftplib
import subprocess
import sys
import os
import time
import operator
import shutil

def upgrade(remote, local, send_timeout, max_attempts, attempt):
    ftp = None
    try:
        try:
            ftp = ftplib.FTP(ftp_connect.ftp_server)
            ftp.login(ftp_connect.ftp_username, ftp_connect.ftp_password)
            ftp.cwd(remote.replace('\\', '/'))
        except Exception:
            if attempt < max_attempts:
                try:
                    ftp.quit()
                except:
                    pass
                logger.updater.warn(
                    f"При попытке ({attempt}) скачать обновление, была потеряна связь с ftp-сервером. Повторная попытка через ({send_timeout}) секунд...")
                attempt += 1
                time.sleep(send_timeout)
                return upgrade(remote, local, send_timeout, max_attempts, attempt)
            else:
                try:
                    ftp.quit()
                except:
                    pass
                logger.updater.error(f"Не удалось произвести обновление после ({max_attempts}) попыток", exc_info=True)
            return False

        if not os.path.exists(local):
            os.makedirs(local)

        dirs = []
        for filename in ftp.nlst():
            try:
                ftp.size(filename)
                ftp.retrbinary('RETR ' + filename, open(os.path.join(local, filename), 'wb').write)
            except:
                dirs.append(filename)
        ftp.quit()
        res = map(lambda d: upgrade(os.path.join(remote, d), os.path.join(local, d), send_timeout, max_attempts, attempt), dirs)

        update_successful = reduce(operator.iand, res, True)
        if update_successful:
            logger.updater.info("Обновление установлено")  # Выводим сообщение только если обновление успешно
        return update_successful
    except Exception:
        if attempt < max_attempts:
            try:
                ftp.quit()
            except:
                pass
            logger.updater.warn(f"Попытка ({attempt}) скачать обновление, не удалась. Повторная попытка через ({send_timeout}) секунд...")
            attempt += 1
            time.sleep(send_timeout)
            return upgrade(remote, local, send_timeout, max_attempts, attempt)
        else:
            try:
                ftp.quit()
            except:
                pass
            logger.updater.error(f"Error: Не удалось произвести обновление после ({max_attempts}) попыток", exc_info=True)
            os._exit(1)

class Updater(sys_manager.ProcessManagement):
    def __init__(self):
        super().__init__()
        self.send_data_enabled = self.config.get("send_data", {}).get("enabled")
        self.update_enabled = self.config.get("update", {}).get("enabled", 1)
        self.exe_name = self.config["update"].get("exe_name")

        self.remote_path = self.config.get("update", {}).get("ftp_path")  # папка на фтп с которой качаются все файлы для обновления
        self.date_path = self.config.get("send_data", {}).get("local_path", "..\\date")  # путь откуда берём данные для отправки

        self.max_attempts_update = self.config.get("update", {}).get("attempt_count", 5)  # количество попыток отправки
        self.timeout_update = self.config.get("update", {}).get("attempt_timeout", 10)  # тайм-аут для отправки

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

    def check_update(self, ftp_version, local_version):
        try:
            # Разбиваем версии на части и преобразуем их в числа
            parts1 = list(map(int, ftp_version.split('.')))
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
                f"Не удалось преобразовать информацию о версии файла '{ftp_version}' в подходящий формат для сравнения с '{local_version}'",
                exc_info=True)
            os._exit(1)

    def update_run(self, temp_file_version, ftp_version):
        logger.updater.debug(f"Версия загруженного файла: {temp_file_version}")
        if temp_file_version != ftp_version:
            logger.updater.warn(f"Версия загруженного файла отличается от данных 'manifest.json', процесс обновления будет прерван")
            shutil.rmtree(os.path.dirname(self.manifest_file))
            logger.updater.debug(f"Временная директория '{os.path.dirname(self.manifest_file)}' удалена")
            return
        try:
            if self.action_startup == True:
                self.action_run(self.startup_script, main_file, timeout=True)
                wait_stop_app = self.check_procces_cycle(self.exe_name)

                if wait_stop_app == True:
                    try:
                        logger.updater.info("Начато обновление")
                        upgrade(self.remote_path, "..\\", self.timeout_update, self.max_attempts_update, attempt=1)

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
                logger.updater.info(f"Версия исполянемого файла: {about.version}")
                logger.updater.info(f"Рабочая директория: '{work_directory}'")
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
                        ftp_version, ftp_signature = ftp_connect.check_ftp_version(self.manifest_file, self.exe_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)
                        status_update = self.check_update(ftp_version, local_version)

                        if status_update == True:
                            logger.updater.info("Найдено обновление")
                            signature_check_disable_config = self.config.get("update", {}).get("signature_check_disable_key", 0)
                            temp_exe_file = ftp_connect.download_file(self.exe_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)
                            size_file = self.get_size_file(temp_exe_file)
                            temp_file_version = self.get_exe_version(temp_exe_file)
                            originalfilename = self.get_file_metadata(temp_exe_file, "OriginalFilename")

                            if not signature_check_disable_config == self.signature_check_disable_key:
                                signature = self.sign_metadata(temp_file_version, size_file, self.exe_name, originalfilename)
                                if not signature == ftp_signature:
                                    logger.updater.warn("Файл на сервере не прошёл проверку подлинности")
                                    shutil.rmtree(os.path.dirname(self.manifest_file))
                                    logger.updater.debug(f"Временная директория '{os.path.dirname(self.manifest_file)}' удалена")
                                else:
                                    logger.updater.info("Проверка подлинноcти пройдена")
                                    self.update_run(temp_file_version, ftp_version)
                            else:
                                logger.updater.warn("Внимание, проверка подписи файла на сервере выключена")
                                self.update_run(temp_file_version, ftp_version)
                        else:
                            logger.updater.info("Обновление не найдено")
                            shutil.rmtree(os.path.dirname(self.manifest_file))
                            logger.updater.debug(f"Временная директория '{os.path.dirname(self.manifest_file)}' удалена")

                    except Exception:
                        logger.updater.error(f"Не удалось произвести обновление", exc_info=True)
                self.clear_temp()
                os._exit(0)
            except Exception:
                logger.updater.error(f"Произошло нештатное прерывание основного потока", exc_info=True)
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
                source_file = "updater.exe"
                shutil.copy(source_file, temp_exe)
                # Копируем файл updater.json во временную директорию
                updater_temp = os.path.join(temp_dir, updater_file)
                shutil.copy(updater_file, updater_temp)
                # Запускаем копию утилиты из временной директории
                subprocess.Popen(temp_exe)
                os._exit(0)
            except Exception:
                logger.updater.error(f"Не удалось запустить обновление", exc_info=True)
                os._exit(1)

if __name__ == "__main__":
    ftp_connect = connectors.FtpConnection()
    updater = Updater()
    main_file = os.path.abspath(sys.argv[0]) # получаем текущую директорию
    work_directory = os.getcwd()
    temp_dir = os.path.abspath("_temp")  #  получение пути к временной директории
    updater.main(main_file, temp_dir)