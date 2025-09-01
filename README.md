# ftp-updater

## Описание
Утилита для обновления приложений Windows с FTP-сервера.

Предполагается, что исполняемый файл утилиты находится в каталоге **`updater`**; каталог **`updater`** должен находиться в корне обновляемого приложения. 

Обновление осуществляется в 5 этапов, переход на следующий этап происходит только в случае успешного завершения предыдущего:

1. Загрузка **`manifest.json`**  из указанного в конфиге каталога на сервере. С ним сверяются имя исполняемого файла, версия и имя архива с файлами обновления (при наличии)

2. Загрузка исполняемого файла и проверка его подлинности

3. Загрузка архива с остальными файлами обновления (при наличии) и проверка его подлинности

4. Установка исполняемого файла с проверкой целостности и откат к старому файлу, если проверка не пройдена

5. Распаковка архива с сохранением структуры каталогов и последующее удаление всех временных файлов


Утилита работает из временной директории, для возможности самообновления вместе с основным приложением. Присутствует шифрование учётных данных от FTP-сервера. Проверка целостности загруженных файлов осуществляется на основе проверки подлинности.

Остановка и запуск основного приложения, при наличии обновления, организованы через настраиваемые cmd-скрипты.

## Требования
- Windows 7/8/10/11 (На `Win7` и `Embedded` может появиться сообщение об ошибке при запуске, тогда понадобится установка обновления безопасности `KB3063858`. Гуглится по номеру обновления и названию Винды, весит 900кб. Для `Win7` отдельный установщик, для `Embedded` отдельный)

- Python 3.8.10+ 32-bit (не требуется, если утилита запускается из исполняемого `.exe-файла`)


## Конфигурация

### updater.json
<details>
<summary>Описание файла конфигурации</summary>

```json
{
    "ftp": {
        "ftp_server": "ftp.server.com",
        "userdata": {
            "encryption": false,
            "ftp_username": "username",
            "ftp_password": "password"
        }
    },
    "update": {
        "enabled": true,
        "ftp_path": "updater",
        "exe_name": "app.exe",
        "attempt_count": 20,
        "attempt_timeout": 20,
        "signature_check_disable_key": "aTdW<<9XyeqNM*LS2<"
    },
    "send_data": {
        "enabled": false,
        "local_path": "..\\date",
        "attempt_count": 20,
        "attempt_timeout": 20
    },
    "actions": {
        "at_startup": {
            "enabled": false,
            "file_name": "stop.bat",
            "timeout": 15
        },
        "at_completion": {
            "enabled": false,
            "file_name": "start.bat"
        }
    },
    "logs": {
        "level": "info",
        "path": "..\\logs",
        "clear_days": 7
    }
}
```

Параметры FTP-сервера:
- `ftp_server`: адрес FTP-сервера
- `encryption`: включение\отключение шифрования учётных данных
- `ftp_username`: логин
- `ftp_password`: пароль

Параметры обновления:
- `enabled`: включение\отключение обновления
- `ftp_path`: каталог на FTP-сервере, в котором лежат файлы для обновления
- `exe_name`: имя исполняемого файла основного приложения (должен располагаться рядом с папкой `updater` в корне приложения)
- `attempt_count`: количество попыток проверки наличия обновления и его загрузки
- `attempt_timeout`: интервал между попытками (в секундах)
- `signature_check_disable_key`: ключ отключающий проверку подписи файла на сервере

Параметры отправки данных на FTP-сервер:
- `enabled`: включение\отключение отправки данных
- `local_path`: путь до каталога, содержимое которого будет выгружаться на FTP-сервер
- `attempt_count`: количество попыток отправки данных на FTP-сервер
- `attempt_timeout`: интервал между попытками (в секундах)

Параметры выполняемых cmd-скриптов, при наличии обновления:
- `at_startup`: конфигурация запускаемого скрипта, при обнаружении обновления
- `enabled`: включение\отключение выполнения скрипта
- `file_name`: путь к скрипту (по умолчанию ожидается что скрипт лежит рядом с файлом `updater.exe`)
- `timeout`: тайм-аут, в течении которого проверяется активность процесса обновляемого приложения, если процесс остаётся запущен, обновление прерывается
<br>

- `at_completion`: конфигурация запускаемого скрипта, после установки обновления
- `enabled`: включение\отключение выполнения скрипта
- `file_name`: путь к скрипту (по умолчанию ожидается что скрипт лежит рядом с файлом `updater.exe`)

Параметры логирования:
- `level`: уровень логирования
- `path`: путь к каталогу с логами
- `clear_days`: срок хранения логов (дни)

</details>

## Сборка

### PyInstaller

При сборке желательно явно указать некоторые импорты, команда выглядит так:

```bash
py -3.8 -m PyInstaller --hidden-import pythoncom --hidden-import wmi --hidden-import cryptography.fernet --onefile --noconsole --icon=favicon.ico updater.py
```

Параметр **`--onefile`** является обязательным.

### Замена ключей безопасности

Ключи безопасности определяются в **`sys_manager.py`** в классе **`ResourceManagement()`**. Перед сборкой приложения рекомендуется заменить их на собственные уникальные ключи. 

```python
class ResourceManagement:
    signature_check_disable_key = "aTdW<<9XyeqNM*LS2<"
    signature_key = b'R%Q480WMofRwn16L'
    crypto_key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM='
```

- `signature_check_disable_key`: ключ отключения проверки подписи файла при обновлении, может быть случайным набором латинских символов любой длинны
- `signature_key`: ключ которым формируется уникальная подпись файлов обновления, может быть случайным набором латниских символов любой длинны
- `crypto_key`: ключ которым шифруются учётные данные от FTP-сервера, имеет определённые требования, получить новый уникальный ключ можно выполнив скрипт **`gen-key.py`** в каталоге **`_tools`**

### Запуск из исходников в виртуальном окружении

Исходники подготовлены для сборки утилиты в .exe-файл. Для запуска в виртуальном окружении, необходимо в файле  **`updater.py`** из метода **`main()`** класса **`Updater()`** убрать часть кода, отвечающую за перемещение исполняемого файла в каталог **`_temp`**

<details>
<summary>Пример того, как в этом случае должен выглядеть метод <b>main()</b> в <b>updater.py</b></summary>
    
```python
class Updater(sys_manager.ProcessManagement):
    ...
    ...
    ...
    def main(self, main_file, temp_dir):
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
```
</details>

## Обновление

### 1. Получение manifest.json и шифрование учётных данных

В каталоге **`_tools`** лежит скрипт **`fu-tools.py`**. Нужно положить рядом с ним исполняемый файл обновляемого приложения, в метаданных которого будет указана его версия.

Если обновление содержит другия файлы, кроме исполняемого, их нужно запаковать в zip-архив, с сохранением структуры каталогов и так же положить его рядом с **`fu-tools.py`**. Имя архива должно совпадать с именем исполняемого файла (пример: **`app.exe`** и **`app.zip`**). Сам исполняемый файл в архив лучше не запаковывать.

После выполнения скрипта рядом появятся файлы **`manifest.json`** и **`output.txt`**

Полученный **`manifest.json`** загружается на FTP-сервер вместе с исполнямеый файлом и zip-архивом.

В **`output.txt`** будет содержаться логин и пароль от FTP-сервера в зашифрованном виде. Их нужно получить только один раз, учётные данные перед запуском скрипта необходимо прописать в конфиге **`fu-tools.json`** 

<details>
<summary>Описание файла конфигурации <b>fu-tools.json</b></summary>

```json
{
	"manifest_key": "HVJ7X^Q?+4Z6rwoB",
	"crypto_key": "t_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM=",
	"username": "user",
	"password": "password",
	"decrypt_data_1": "",
	"decrypt_data_2": ""
}
```
- `manifest_key`: ключ которым формируется уникальная подпись файлов обновления
- `crypto_key`: ключ которым шифруются учётные данные от FTP-сервера
- `username`: имя пользователя
- `password`: пароль
- `decrypt_data_1`, `decrypt_data_2`: эти два параметры добавлены на случай, если необходимо что-то расшифровать тем же ключом

</details>

Пример получаемого **`manifest.json`**

```json
{
    "app.exe": {
        "version": "1.1.2.0",
        "signature": "440536984ecae3a86364ce324c2c239d6247ee518f746beeb999e0ebecf34dbe"
    },
    "app.zip": {
        "signature": "336738db1d2b952fe16c21baa636fcafa196a995c4a1c3f9ef054af4469b176b"
    }
}
```

### 2. Отключение проверки подписи

Для этого в файле конфигурации **`updater.json`** нужно указать уникальный ключ для параметра `signature_check_disable_key`.

На проверке подписи так же завязана проверка целостности загруженных файлов. Функция добавлена для отладки и её использование не рекомендуется.

Если проверка подписи отключена, то **`manifest.json`** можно взять из примера. Достаточно в нём прописать имя исполняемого файла, его версию и имя zip-архива. Ключ **`signature`** в этом случае не проверяется, его можно убрать, оставить как есть или заменить пустой строкой.

Если в обновлении имеется только исполняемый файл, нужно из **`manifest.json`** убрать ключ с именем архива или изменить его так, чтобы он не совпадал с именем исполнямемого файла (пример: **`app.exe`** и **`app123.zip`**)

## Ключи, используемые в тестовой сборке

- **`t_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM=`**: ключ для шифрования учтёных данных
- **`R%Q480WMofRwn16L`**: ключ для генерации подписи исполняемого файла
- **`aTdW<<9XyeqNM*LS2<`**: ключ для отключения проверки подписи

