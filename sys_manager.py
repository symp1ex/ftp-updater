import about
import configs
import logger
from cryptography.fernet import Fernet
import os
import time
import subprocess
import sys
import hashlib
import hmac
import win32api
import stat
import zipfile

class ResourceManagement:
    signature_check_disable_key = "aTdW<<9XyeqNM*LS2<"
    signature_key = b'R%Q480WMofRwn16L'
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
        logger.updater.debug(f"Получены данные из файла '{os.path.abspath(self.manifest_file)}': {self.manifest}")

    def get_exe_version(self, file_path):
        try:
            info = win32api.GetFileVersionInfo(file_path, '\\')
            version = info['FileVersionMS'] >> 16, info['FileVersionMS'] & 0xFFFF, info['FileVersionLS'] >> 16, info[
                'FileVersionLS'] & 0xFFFF
            logger.updater.debug(f"Получены метаданные файла '{os.path.abspath(file_path)}': {info}")
            return '.'.join(map(str, version))
        except Exception:
            logger.updater.error(f"Не удалось проверить версию файла: '{os.path.abspath(file_path)}'", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def get_file_metadata(self, file_path, field):  # получение конкретного поля из метаданных исполняемого файла
        try:
            language, codepage = win32api.GetFileVersionInfo(file_path, '\\VarFileInfo\\Translation')[0]
            stringfileinfo = u'\\StringFileInfo\\%04X%04X\\%s' % (
            language, codepage, field)  # конкретное поле LegalCopyright
            result = win32api.GetFileVersionInfo(file_path, stringfileinfo)
            logger.updater.debug(f"Успешно получено значение поля '{field}' для файла '{file_path}': '{result}'")
        except Exception:
            logger.updater.error(f"Не удалось получить описание файла на ftp-сервре", exc_info=True)
            result = "unknown"
        return result

    def get_size_file(self, file_path):
        try:
            file_stats = os.stat(file_path)
            size = file_stats[stat.ST_SIZE]
            logger.updater.debug(f"Размер загруженного файла '{file_path}': {size}")
            return size
        except Exception:
            logger.updater.error(f"Не удалось получить размер файла: '{os.path.abspath(file_path)}'", exc_info=True)
            self.clear_temp()
            os._exit(1)

    def get_name_zip(self):
        base_name = self.exe_name.split('.')[0]  # получаем 'file'
        key = f"{base_name}.zip"  # создаем новую строку 'file.zip'

        try:
            # Прямая проверка ключа
            if key in self.manifest:
                self.zip_name = key
                logger.updater.debug(f"Ключ '{key}' найден в '{self.manifest_file}'")
                return True
            logger.updater.debug(f"Ключ '{key}' не найден в '{self.manifest_file}'")
            return False
        except Exception:
            logger.updater.error(f"Ошибка при поиске ключа '{key}' в {self.manifest_file}", exc_info=True)
            return False

    def restore_file(self):
        try:
            time.sleep(1)
            os.remove(self.old_file)
            time.sleep(1)
            os.rename(self.temp_old_file, self.old_file)
            time.sleep(1)
            logger.updater.info(f"Резервная копия файла '{os.path.abspath(self.old_file)}' успешно восстановлена")
        except Exception:
            logger.updater.critical(f"Не удалось восстановить резервную капию файла '{os.path.abspath(self.old_file)}'",
                                    exc_info=True)

    def unzip_and_get_files(self, extract_path):
        self.zip_files_list = []
        try:
            # Открываем zip архив
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                # Получаем список всех файлов в архиве
                for file_info in zip_ref.infolist():
                    if not file_info.filename.endswith('/'):  # Пропускаем директории
                        self.zip_files_list.append(file_info.filename)
                # Распаковываем архив
                logger.updater.debug(f"Получен список файлов в архиве: '{self.zip_files_list}'")
                zip_ref.extractall(extract_path)
                logger.updater.info(f"Zip-архив '{self.zip_path}' успешно распакован в '{os.path.abspath(extract_path)}'")
        except Exception:
            logger.updater.error(f"Ошибка при распаковке архива '{self.zip_path}'", exc_info=True)
            self.restore_file()
            raise

    def clear_temp(self):
        try:
            main_file = os.path.abspath(sys.argv[0])
            temp_dir = os.path.dirname(main_file)
            # Команда для удаления файла
            command = f"timeout /t 45 > nul && rd /q/s \"{temp_dir}\""
            working_directory = os.path.dirname(os.path.dirname(temp_dir))
            # Выполняем команду в отдельном процессе
            subprocess.Popen(command, shell=True, cwd=working_directory)
            logger.updater.debug(f"Отправлена команда на очистку временной директории: '{os.path.abspath(temp_dir)}'")
        except Exception:
            logger.updater.error(f'Не удалось очистить временную директорию', exc_info=True)
            os._exit(1)

    def sign_metadata(self, key1, key2, key3, key4):
        try:
            metadata = f"{key1}:{key2}:{key3}:{key4}"
            signature = hmac.new(self.signature_key, metadata.encode(), hashlib.sha256).hexdigest()
            return signature
        except Exception:
            logger.updater.error(f"Не удалось получить подпись из загруженного файла", exc_info=True)
            self.clear_temp()
            os._exit(1)

    # дешифровка параметров подключения из updater.json
    def decrypt_data(self, encrypted_data):
        try:
            cipher = Fernet(self.crypto_key)
            decrypted_data = cipher.decrypt(encrypted_data).decode()
            return decrypted_data
        except Exception:
            logger.updater.error(f"Не пройдена аутентификация на сервере", exc_info=True)
            self.clear_temp()
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
            logger.updater.error(f"Не удалось определить путь к '{file_name}'", exc_info=True)

        try:
            logger.updater.info(f"Будет запущен '{os.path.normpath(file_path)}'")
            if timeout:
                logger.updater.info(f"Продолжение работы через ({self.action_timeout}) секунд")
            subprocess.Popen(file_path)
        except Exception:
            logger.updater.error(f"Не удалось запустить '{file_path}'", exc_info=True)
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
                logger.updater.debug(f"Процесс '{file_name}' активен")
                return True
            elif result.returncode == 1:
                logger.updater.debug(f"Процесс '{file_name}' неактивен")
                return False
            else:
                # Если returncode не 0 или 1, это указывает на ошибку выполнения команды
                logger.updater.warning(
                    f"Ошибка выполнения команды CMD для процесса '{file_name}'. Код возврата: {result.returncode}",)
                return None

        except FileNotFoundError:
            # Это исключение может возникнуть, если 'cmd.exe' или одна из команд
            # ('tasklist', 'findstr') не найдена в системном PATH.
            logger.updater.error( f"Команда CMD или ее компоненты (tasklist/findstr) не найдены. "
                                                 f"Убедитесь, что они доступны в системном PATH.", exc_info=True)
            return None
        except Exception:
            logger.updater.error(
                f"Не удалось получить статус процесса '{file_name}' через CMD (tasklist|findstr)", exc_info=True)
            return None

    def check_process_cycle(self, exe_name):
        count_attempt = int(self.action_timeout / 5 + 1)

        try:
            logger.updater.info(f"Проверяем активность процесса '{exe_name}'")
            for attempt in range(count_attempt):
                process_found = self.check_process(exe_name)

                if process_found:
                    logger.updater.debug(f"Cледующая проверка через (5) секунд.")
                    time.sleep(5)
                    continue
                else:
                    logger.updater.info(f"Процесс '{exe_name}' завершил свою работу или не был запущен")
                    return True
            logger.updater.warn(
                f"Процесс '{exe_name}' остаётся активным в течении ({self.action_timeout}) секунд, "
                f"процесс обновления будет прерван")
            return False
        except Exception:
            logger.updater.error(f"Не удалось отследить состояние процесса '{exe_name}'", exc_info=True)
            self.clear_temp()
            os._exit(1)