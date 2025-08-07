import ftplib
from cryptography.fernet import Fernet
import sys
import os
import time
import win32api
import stat
import hashlib
import hmac
from functools import reduce
import operator, subprocess, shutil
import configs
import logger
import about

def action_startup_run(config, main_file):
    try: timeout = int(config["actions"]["at_startup"].get("timeout", 15))
    except Exception: timeout = 15

    file_name = config["actions"]["at_startup"].get("file_name", "stop.bat")
    try:
        file_path = os.path.join(os.path.dirname(main_file), "..\\", file_name)
    except Exception:
        logger.updater.error(f"Не удалось определить путь к '{file_name}'", exc_info = True)

    try:
        logger.updater.info(f"Будет запущен '{os.path.normpath(file_path)}', продолжение работы через ({timeout}) секунд")
        subprocess.Popen(file_path)
        time.sleep(timeout)
    except Exception:
        logger.updater.error(f"Не удалось запустить '{file_path}'", exc_info=True)

def action_complete_run(config, main_file):
    file_name = config["actions"]["at_completion"].get("file_name", "start.bat")

    try:
        file_path = os.path.join(os.path.dirname(main_file), "..\\", file_name)
    except Exception:
        logger.updater.error(f"Не удалось определить путь к '{file_name}'", exc_info=True)

    try:
        logger.updater.info(f"Будет запущен '{os.path.normpath(file_path)}'")
        subprocess.Popen(file_path)
    except Exception:
        logger.updater.error(f"Не удалось запустить '{file_name}'", exc_info=True)

def get_exe_metadata(file_path):
    try:
        logger.updater.debug(f"Будут получены метаданные файла '{file_path}'")
        info = win32api.GetFileVersionInfo(file_path, '\\')
        version = info['FileVersionMS'] >> 16, info['FileVersionMS'] & 0xFFFF, info['FileVersionLS'] >> 16, info['FileVersionLS'] & 0xFFFF
        logger.updater.debug(f"Получены метаданные файла '{file_path}':\n{info}")
        return '.'.join(map(str, version))
    except Exception:
        logger.updater.error(f"Не удалось проверить версию исходного файла", exc_info=True)
        return None

def get_file_description(file_path): # получение конкретного поля из метаданных исполняемого файла
    try:
        language, codepage = win32api.GetFileVersionInfo(file_path, '\\VarFileInfo\\Translation')[0]
        stringfileinfo = u'\\StringFileInfo\\%04X%04X\\%s' % (language, codepage, "LegalCopyright") # конкретное поле LegalCopyright
        description = win32api.GetFileVersionInfo(file_path, stringfileinfo)
        logger.updater.debug(f"Получаем значение поля 'LegalCopyright' для файла '{file_path}':\n{description}")
    except Exception:
        logger.updater.error(f"Не удалось получить описание файла на ftp-сервре", exc_info=True)
        description = "unknown"
    return description

def get_size_file(file_path):
    try:
        file_stats = os.stat(file_path)
        size = file_stats[stat.ST_SIZE]
        logger.updater.debug(f"Размер загруженного файла '{file_path}':\n{size}")
        return size
    except Exception:
        pass

def download_temp_file(ftp_server, ftp_username, ftp_password, ftp_path, config, send_timeout, max_attempts, attempt):
    ftp = None
    try:
        main_file = os.path.abspath(sys.argv[0])  # получаем текущую директорию
        exe_name = config["update"].get("exe_name")
        remote_file_path = f"{ftp_path}/{exe_name}"  # путь до файла на фтп с которым сравнивается версия и подпись
        # Установка соединения с FTP сервером
        ftp = ftplib.FTP(ftp_server)
        ftp.login(ftp_username, ftp_password)

        # Создание временного файла для загрузки
        local_file_path = os.path.join(os.path.dirname(main_file), os.path.basename(remote_file_path))
        logger.updater.debug(f"Временный файл '{remote_file_path}' будет загружен в директорию '{os.path.dirname(local_file_path)}'")

        # Загрузка файла с FTP сервера
        with open(local_file_path, 'wb') as local_file:
            ftp.retrbinary('RETR ' + remote_file_path, local_file.write)

        logger.updater.debug(f"Файл '{remote_file_path}' успешно загружен")
        # Закрытие соединения с FTP сервером
        ftp.quit()

        return local_file_path
    except Exception:
        if attempt < max_attempts:
            try:
                ftp.quit()
            except:
                pass
            logger.updater.warn(f"Попытка ({attempt}) загрузить временный файл для проверки обновления, не удалась. Повторная попытка через ({send_timeout}) секунд...")
            attempt += 1
            time.sleep(send_timeout)
            return download_temp_file(ftp_server, ftp_username, ftp_password, ftp_path, config, send_timeout, max_attempts, attempt)
        else:
            try:
                ftp.quit()
            except:
                pass
            logger.updater.error(f"Не удалось загрузить временный файл для проверки обновления", exc_info=True)
            return None

# получение подписи на основе .exe файла на фтп-сервере
def sign_metadata(size, version):
    try:
        key = b'R%Q480WMofRwn16L'
        metadata = f"{size}:{version}"
        signature = hmac.new(key, metadata.encode(), hashlib.sha256).hexdigest()
        return signature
    except Exception:
        logger.updater.error(f"Не удалось получить подпись", exc_info=True)

# дешифровка параметров подключения из updater.json
def decrypt_data(encrypted_data):
    try:
        key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM=' # ключ
        cipher = Fernet(key)
        decrypted_data = cipher.decrypt(encrypted_data).decode()
        return decrypted_data
    except Exception:
        logger.updater.error(f"Не пройдена аутентификация на сервере", exc_info=True)

# Параметры FTP сервера
def ftp_connect(config):
    try: encryption_enbled = int(config["ftp"]["userdata"].get("encryption", 0))
    except Exception: encryption_enbled = 0

    try:
        ftp_server = config["ftp"].get("ftp_server")

        if encryption_enbled == False:
            ftp_username = config["ftp"]["userdata"].get("ftp_username")
            ftp_password = config["ftp"]["userdata"].get("ftp_password")
        else:
            ftp_username = decrypt_data(config["ftp"]["userdata"].get("ftp_username"))
            ftp_password = decrypt_data(config["ftp"]["userdata"].get("ftp_password"))
        return ftp_server, ftp_username, ftp_password
    except Exception:
        logger.updater.error("Не удалось определить тип пользовтельских данных для подключения к ftp", exc_info=True)

def local_version(config, parent_directory):
    try:
        exe_name = config["update"].get("exe_name")
        file_path = f"{parent_directory}\\{exe_name}" #путь до локального файла с которым сравнивается версия
        local_version = get_exe_metadata(file_path)
        if local_version:
            logger.updater.debug(f"Получаем информацию о версии файла: '{os.path.abspath(file_path)}'")
            logger.updater.info(f"Версия исходного файла: {local_version}")
            return local_version
    except Exception:
        logger.updater.error(f"Не удалось проверить версию исходного файла")

def ftp_version(config, remote_path, send_timeout, max_attempts, attempt):
    try:
        ftp_server, ftp_username, ftp_password = ftp_connect(config)
        ftp_file_path = download_temp_file(ftp_server, ftp_username, ftp_password, remote_path, config, send_timeout, max_attempts, attempt)
        if ftp_file_path:
            # Получение версии файла на фтп
            ftp_version = get_exe_metadata(ftp_file_path)
            size_file = get_size_file(ftp_file_path)
            file_description = get_file_description(ftp_file_path)
            time.sleep(2)
            os.remove(ftp_file_path)
            if ftp_version:
                logger.updater.info(f"Версия файла на сервере: {ftp_version}")
                return ftp_version, file_description, size_file
    except Exception:
        logger.updater.error(f"Не удалось проверить версию файла на ftp-сервере", exc_info=True)

def updater(ftp, local):
    try:
        # Разбиваем версии на части и преобразуем их в числа
        parts1 = list(map(int, ftp.split('.')))
        parts2 = list(map(int, local.split('.')))

        # Сравниваем каждую часть версии, начиная с первой
        for i in range(len(parts1)):
            if parts1[i] > parts2[i]:
                return True  # Версия первого файла выше
            elif parts1[i] < parts2[i]:
                return False  # Версия первого файла ниже
        return False  # Версии идентичны
    except Exception:
        logger.updater.error(f"Не удалось преобразовать информацию о версии файла '{ftp}' в подходящий формат для сравнения с '{local}'", exc_info=True)
def upgrade(ftp_info, remote, local, send_timeout, max_attempts, attempt):
    ftp = None
    try:
        addr, user, passw = ftp_info
        try:
            ftp = ftplib.FTP(addr)
            ftp.login(user, passw)
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
                return upgrade(ftp_info, remote, local, send_timeout, max_attempts, attempt)
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
        res = map(lambda d: upgrade(ftp_info, os.path.join(remote, d), os.path.join(local, d), send_timeout, max_attempts, attempt), dirs)

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
            return upgrade(ftp_info, remote, local, send_timeout, max_attempts, attempt)
        else:
            try:
                ftp.quit()
            except:
                pass
            logger.updater.error(f"Error: Не удалось произвести обновление после ({max_attempts}) попыток", exc_info=True)
            return None

def upload(ftp_info, date_path, send_timeout, max_attempts, attempt):
    ftp = None
    addr, user, passw = ftp_info
    try:
        ftp = ftplib.FTP(addr)
        ftp.login(user, passw)

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
        logger.updater.info(f"Отправка данных на сервер завершена")
        return True
    except Exception:
        if attempt < max_attempts:
            try:
                ftp.quit()
            except:
                pass
            logger.updater.warn(f"Попытка ({attempt}) отправки данных не удалась. Повторная попытка через ({send_timeout}) секунд...")
            attempt += 1
            time.sleep(send_timeout)
            return upload(ftp_info, date_path, send_timeout, max_attempts, attempt)
        else:
            try:
                ftp.quit()
            except:
                pass
            logger.updater.error(f"Отправка данных на сервер не удалась после ({max_attempts}) попыток", exc_info=True)
            return False

def clear_temp():
    try:
        main_file = os.path.abspath(sys.argv[0])
        temp_dir = os.path.dirname(main_file)
        # Команда для удаления файла
        command = f"timeout /t 60 > nul && rd /q/s \"{temp_dir}\""
        working_directory = os.path.dirname(os.path.dirname(temp_dir))
        # Выполняем команду в отдельном процессе
        subprocess.Popen(command, shell=True, cwd=working_directory)
    except Exception:
        logger.updater.error(f'Не удалось очистить временную директорию', exc_info=True)

def main(main_file, temp_dir):
    if main_file.startswith(temp_dir): # если udater запущен из временной директории, то запускаем процесс обновления
        try:
            logger.updater.info(f"updater.exe запущен")
            logger.updater.info(f"Версия исполянемого файла: {about.version}")
            logger.updater.info(f"Рабочая директория: '{about.work_directory}'")

            json_file = os.path.join(os.getcwd(), "updater.json")
            config = configs.read_config_file(json_file, create=True)
            logger.updater.debug(f"Использован конфиг:\n{config}")
            ftp_server, ftp_username, ftp_password = ftp_connect(config)
            ftp_info = (ftp_server, ftp_username, ftp_password)  # создаём кортеж

            send_data_enbled = config["send_data"].get("enabled")
            if send_data_enbled == True:
                try:
                    date_path = config["send_data"].get("local_path", "..\\date")  # путь откуда берём данные для отправки
                    max_attempts = config["send_data"].get("attempt_count", 5)  # количество попыток отправки
                    send_timeout = config["send_data"].get("attempt_timeout", 10)  # тайм-аут для отправки

                    os.chdir(date_path)  # меняем рабочий каталог с корневого каталога для скрипта на указанный каталог здесь
                    logger.updater.debug(f"Рабочая директория изменена на: '{os.path.abspath(date_path)}'")
                    upload(ftp_info, date_path, send_timeout, max_attempts, attempt=1)
                except Exception:
                    logger.updater.error(f"Отправка данных на сервер не удалась", exc_info=True)

                os.chdir(about.work_directory)
                logger.updater.debug(f"Рабочая директория изменена на: '{about.work_directory}'")

            update_enbled = config["update"].get("enabled")
            if update_enbled == True:
                max_attempts = config["update"].get("attempt_count", 5)  # количество попыток отправки
                send_timeout = config["update"].get("attempt_timeout", 10)  # тайм-аут для отправки

                try:
                    remote_path = config["update"].get("ftp_path")  # папка на фтп с которой качаются все файлы для обновления

                    logger.updater.info("Проверяется наличие обновлений")
                    local = local_version(config, "..")
                    ftp, description, size_file = ftp_version(config, remote_path, send_timeout, max_attempts, attempt=1)
                    status_update = updater(ftp, local)

                    if status_update == True:
                        logger.updater.info("Найдено обновление")
                        check_signature_disabled_key = config["update"].get("signature_check_disable_key", 0)

                        if not check_signature_disabled_key == "aTdW<<9XyeqNM*LS2<":
                            signature = sign_metadata(ftp, size_file)
                            if not signature == description:
                                logger.updater.warn("Файл на сервере не прошёл проверку подлинности")
                            else:
                                logger.updater.info("Проверка подлинноcти пройдена")

                                try: action_startup = int(config["actions"]["at_startup"].get("enabled", 0))
                                except Exception: action_startup = 0

                                if action_startup == True:
                                    action_startup_run(config, main_file)

                                logger.updater.info("Начато обновление")
                                upgrade(ftp_info, remote_path, "..\\", send_timeout, max_attempts, attempt=1)

                                try: action_completion = int(config["actions"]["at_completion"].get("enabled", 0))
                                except Exception: action_completion = 0

                                if action_completion == True:
                                    action_complete_run(config, main_file)
                        else:
                            logger.updater.warn("Внимание, проверка подписи файла на сервере выключена")

                            try: action_startup = int(config["actions"]["at_startup"].get("enabled", 0))
                            except Exception: action_startup = 0

                            if action_startup == True:
                                action_startup_run(config, main_file)

                            logger.updater.info("Начато обновление")
                            upgrade(ftp_info, remote_path, "..\\", send_timeout, max_attempts, attempt=1)

                            try: action_completion = int(config["actions"]["at_completion"].get("enabled", 0))
                            except Exception: action_completion = 0

                            if action_completion == True:
                                action_complete_run(config, main_file)
                    else:
                        logger.updater.info("Обновление не найдено")
                except Exception:
                    logger.updater.error(f"Не удалось произвести обновление", exc_info=True)
            clear_temp()
            os._exit(0)
        except Exception:
            logger.updater.error(f"Произошло нештатное прерывание основного потока", exc_info=True)

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

if __name__ == "__main__":
    main_file = os.path.abspath(sys.argv[0]) # получаем текущую директорию
    temp_dir = os.path.abspath("_temp")  #  получение пути к временной директории
    main(main_file, temp_dir)