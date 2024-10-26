# 0.4.8
import ftplib
from cryptography.fernet import Fernet
import sys
import os
import time
import json
import win32api
import stat
import hashlib
import hmac
from functools import reduce
import operator, subprocess, shutil
from logger import log_console_out, exception_handler

def read_config_json(json_file):
    try:
        with open(json_file, "r", encoding="utf-8") as file:
            config = json.load(file)
            return config
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None

def get_exe_metadata(file_path):
    try:
        info = win32api.GetFileVersionInfo(file_path, '\\')
        version = info['FileVersionMS'] >> 16, info['FileVersionMS'] & 0xFFFF, info['FileVersionLS'] >> 16, info['FileVersionLS'] & 0xFFFF
        return '.'.join(map(str, version))
    except Exception as e:
        log_console_out(f"Error: Не удалось проверить версию исходного файла")
        exception_handler(type(e), e, e.__traceback__)
        return None

def get_file_description(file_path): # получение конкретного поля из метаданных исполняемого файла
    try:
        language, codepage = win32api.GetFileVersionInfo(file_path, '\\VarFileInfo\\Translation')[0]
        stringfileinfo = u'\\StringFileInfo\\%04X%04X\\%s' % (language, codepage, "LegalCopyright") # конкретное поле LegalCopyright
        description = win32api.GetFileVersionInfo(file_path, stringfileinfo)
    except Exception as e:
        log_console_out(f"Error: Не удалось получить описание файла на ftp-сервре")
        exception_handler(type(e), e, e.__traceback__)
        description = "unknown"
    return description

def get_size_file(file_path):
    try:
        file_stats = os.stat(file_path)
        size = file_stats[stat.ST_SIZE]
        return size
    except Exception:
        pass

def download_temp_file(ftp_server, ftp_username, ftp_password, config, send_timeout, max_attempts, attempt):
    ftp = None
    try:
        main_file = os.path.abspath(sys.argv[0])  # получаем текущую директорию
        ftp_path = config.get("ftp_path")
        exe_name = config.get("exe_name")
        remote_file_path = f"{ftp_path}/{exe_name}"  # путь до файла на фтп с которым сравнивается версия и подпись
        # Установка соединения с FTP сервером
        ftp = ftplib.FTP(ftp_server)
        ftp.login(ftp_username, ftp_password)

        # Создание временного файла для загрузки
        local_file_path = os.path.join(os.path.dirname(main_file), os.path.basename(remote_file_path))

        # Загрузка файла с FTP сервера
        with open(local_file_path, 'wb') as local_file:
            ftp.retrbinary('RETR ' + remote_file_path, local_file.write)

        # Закрытие соединения с FTP сервером
        ftp.quit()

        return local_file_path
    except Exception as e:
        if attempt < max_attempts:
            try:
                ftp.quit()
            except:
                pass
            log_console_out(f"Попытка ({attempt}) загрузить временный файл для проверки обновления, не удалась. Повторная попытка через ({send_timeout}) секунд...")
            attempt += 1
            time.sleep(send_timeout)
            return download_temp_file(ftp_server, ftp_username, ftp_password, config, send_timeout, max_attempts, attempt)
        else:
            try:
                ftp.quit()
            except:
                pass
            log_console_out(f"Error: не удалось загрузить временный файл для проверки обновления")
            exception_handler(type(e), e, e.__traceback__)
            return None

# получение подписи на основе .exe файла на фтп-сервере
def sign_metadata(size, version):
    try:
        key = b'R%Q480WMofRwn16L'
        metadata = f"{size}:{version}"
        signature = hmac.new(key, metadata.encode(), hashlib.sha256).hexdigest()
        return signature
    except Exception as e:
        log_console_out(f"Error: Не удалось получить подпись")
        exception_handler(type(e), e, e.__traceback__)

# дешифровка параметров подключения из updater.json
def decrypt_data(encrypted_data):
    try:
        key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM=' # ключ
        cipher = Fernet(key)
        decrypted_data = cipher.decrypt(encrypted_data).decode()
        return decrypted_data
    except Exception as e:
        log_console_out(f"Error: Не пройдена аутентификация на сервере")
        exception_handler(type(e), e, e.__traceback__)

# Параметры FTP сервера
def ftp_connect(config):
    ftp_server = config.get("ftp_server")
    ftp_username = decrypt_data(config.get("ftp_username"))
    ftp_password = decrypt_data(config.get("ftp_password"))
    return ftp_server, ftp_username, ftp_password

def local_version(config, parent_directory):
    try:
        exe_name = config.get("exe_name")
        file_path = f"{parent_directory}\\{exe_name}" #путь до локального файла с которым сравнивается версия
        local_version = get_exe_metadata(file_path)
        if local_version:
            log_console_out(f"Версия исходного файла: {local_version}")
            return local_version
    except Exception as e:
        log_console_out(f"Error: не удалось проверить версию исходного файла")
        exception_handler(type(e), e, e.__traceback__)

def ftp_version(config, send_timeout, max_attempts, attempt):
    try:
        ftp_server, ftp_username, ftp_password = ftp_connect(config)
        ftp_file_path = download_temp_file(ftp_server, ftp_username, ftp_password, config, send_timeout, max_attempts, attempt)
        if ftp_file_path:
            # Получение версии файла на фтп
            ftp_version = get_exe_metadata(ftp_file_path)
            size_file = get_size_file(ftp_file_path)
            file_description = get_file_description(ftp_file_path)
            os.remove(ftp_file_path)
            if ftp_version:
                log_console_out(f"Версия файла на сервере: {ftp_version}")
                return ftp_version, file_description, size_file
    except Exception as e:
        log_console_out(f"Error: не удалось проверить версию файла на ftp-сервере")
        exception_handler(type(e), e, e.__traceback__)

def updater(ftp, local):
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

def upgrade(ftp_info, remote, local, send_timeout, max_attempts, attempt):
    ftp = None
    try:
        addr, user, passw = ftp_info
        try:
            ftp = ftplib.FTP(addr)
            ftp.login(user, passw)
            ftp.cwd(remote.replace('\\', '/'))
        except Exception as e:
            # try:
            #     ftp.quit()
            # except:
            #     pass
            if attempt < max_attempts:
                try:
                    ftp.quit()
                except:
                    pass
                log_console_out(
                    f"При попытке ({attempt}) скачать обновление, была потеряна связь с ftp-сервером. Повторная попытка через ({send_timeout}) секунд...")
                attempt += 1
                time.sleep(send_timeout)
                return upgrade(ftp_info, remote, local, send_timeout, max_attempts, attempt)
            else:
                try:
                    ftp.quit()
                except:
                    pass
                log_console_out(f'Error: Invalid input ftp data!')
                log_console_out(f"Error: Не удалось произвести обновление после ({max_attempts}) попыток")
                exception_handler(type(e), e, e.__traceback__)
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
            log_console_out("Обновление установлено")  # Выводим сообщение только если обновление успешно
        return update_successful
    except Exception as e:
        if attempt < max_attempts:
            try:
                ftp.quit()
            except:
                pass
            log_console_out(f"Попытка ({attempt}) скачать обновление, не удалась. Повторная попытка через ({send_timeout}) секунд...")
            attempt += 1
            time.sleep(send_timeout)
            return upgrade(ftp_info, remote, local, send_timeout, max_attempts, attempt)
        else:
            try:
                ftp.quit()
            except:
                pass
            log_console_out(f"Error: Не удалось произвести обновление после ({max_attempts}) попыток")
            exception_handler(type(e), e, e.__traceback__)
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
        log_console_out(f"Отправка данных на сервер завершена")
        return True
    except Exception as e:
        if attempt < max_attempts:
            try:
                ftp.quit()
            except:
                pass
            log_console_out(f"Попытка ({attempt}) отправки данных не удалась. Повторная попытка через ({send_timeout}) секунд...")
            attempt += 1
            time.sleep(send_timeout)
            return upload(ftp_info, date_path, send_timeout, max_attempts, attempt)
        else:
            try:
                ftp.quit()
            except:
                pass
            log_console_out(f"Error: Отправка данных на сервер не удалась после ({max_attempts}) попыток")
            exception_handler(type(e), e, e.__traceback__)
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
    except Exception as e:
        log_console_out(f'Error: Не удалось очистить временную директорию')
        exception_handler(type(e), e, e.__traceback__)

def main(main_file, temp_dir):
    if main_file.startswith(temp_dir): # если udater запущен из временной директории, то запускаем процесс обновления
        log_console_out(f"updater.exe запущен")

        json_file = os.path.join(os.getcwd(), "updater.json")
        config = read_config_json(json_file)
        ftp_server, ftp_username, ftp_password = ftp_connect(config)
        ftp_info = (ftp_server, ftp_username, ftp_password)  # создаём кортеж

        try:
            date_path = config.get("send_path", "..\\date")  # путь откуда берём данные для отправки
            send_timeout = config.get("send_timeout", 10)  # тайм-аут для отправки
            max_attempts = config.get("send_count", 5)  # количество попыток отправки
            os.chdir(date_path)  # меняем рабочий каталог с корневого каталога для скрипта на указанный каталог здесь
            upload(ftp_info, date_path, send_timeout, max_attempts, attempt=1)
        except Exception as e:
            log_console_out(f"Error: Отправка данных на сервер не удалась")
            exception_handler(type(e), e, e.__traceback__)

        try:
            log_console_out("Проверяется наличие обновлений")
            local = local_version(config, "..")
            ftp, description, size_file = ftp_version(config, send_timeout, max_attempts, attempt=1)
            signature = sign_metadata(ftp, size_file)
            status_update = updater(ftp, local)

            if status_update == True:
                log_console_out("Найдено обновление")
                if not signature == description:
                    log_console_out("Файл на сервере не прошёл проверку подлинности")
                else:
                    log_console_out("Проверка подлинноcти пройдена")

                    remote = config.get("ftp_path") # папка на фтп с которой качаются все файлы для обновления

                    log_console_out("Начато обновление")
                    upgrade(ftp_info, remote, "..\\", send_timeout, max_attempts, attempt=1)
            else:
                log_console_out("Обновление не найдено")
        except Exception as e:
            log_console_out(f"Error: не удалось произвести обновление")
            exception_handler(type(e), e, e.__traceback__)
        clear_temp()

    else:
        try:
            updater_file = "updater.json" # определяем файл конфига, который нам так же нужно скопировать во временную директорию
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
            sys.exit()
        except Exception as e:
            log_console_out(f"Error: не удалось запустить обновление")
            exception_handler(type(e), e, e.__traceback__)

if __name__ == "__main__":
    main_file = os.path.abspath(sys.argv[0]) # получаем текущую директорию
    temp_dir = os.path.abspath("_temp")  #  получение пути к временной директории
    main(main_file, temp_dir)