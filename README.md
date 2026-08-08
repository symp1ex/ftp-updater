# ftp-updater

## Описание
Утилита для обновления приложений Windows с FTP-сервера или HTTP-хранилища.

Предполагается, что исполняемый файл утилиты находится в каталоге **`updater`**; каталог **`updater`** должен находиться в корне обновляемого приложения. 

Обновление осуществляется в 5 этапов, переход на следующий этап происходит только в случае успешного завершения предыдущего:

1. Загрузка **`manifest.json`**  из указанного в конфиге каталога на сервере. С ним сверяются имя исполняемого файла, версия и имя архива с файлами обновления (при наличии)

2. Загрузка исполняемого файла и проверка его подлинности

3. Загрузка архива с остальными файлами обновления (при наличии) и проверка его подлинности

4. Установка исполняемого файла с проверкой целостности и откат к старому файлу, если проверка не пройдена

5. Распаковка архива с сохранением структуры каталогов и последующее удаление всех временных файлов


Утилита работает из временной директории, для возможности самообновления вместе с основным приложением. Присутствует шифрование учётных данных от HTTP/FTP-сервера.

## Требования
- Windows 7/8/10/11 (На `Win7` и `Embedded` может появиться сообщение об ошибке при запуске, тогда понадобится установка обновления безопасности `KB3063858`. Гуглится по номеру обновления и названию Винды, весит 900кб. Для `Win7` отдельный установщик, для `Embedded` отдельный)

- Python 3.8 32-bit (не требуется, если утилита запускается из исполняемого `.exe-файла`)


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
        "ftp_path": "updater",
        "exe_name": "app.exe",
        "attempt_count": 10,
        "attempt_timeout": 10,
        "signature_check_disable_key": "",
        "http_update": {
            "enabled": false,
            "ftp_mirror_update": false,
            "data connection": {
                "encryption": false,
                "url": "http://server.com/updater/"
            }
        }
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
Для неиспользуемых функций позволяется удалять целые разделы из конфига.

Параметры FTP-сервера:
- `ftp_server`: адрес FTP-сервера
- `encryption`: включение\отключение шифрования учётных данных
- `ftp_username`: логин
- `ftp_password`: пароль

Параметры обновления:
- `ftp_path`: каталог на FTP-сервере, в котором лежат файлы для обновления
- `exe_name`: имя исполняемого файла основного приложения (должен располагаться рядом с папкой `updater` в корне приложения)
- `attempt_count`: количество попыток проверки наличия обновления и его загрузки
- `attempt_timeout`: интервал между попытками (в секундах)
- `signature_check_disable_key`: ключ отключающий проверку подписи файла на сервере
<br><br>
- `http_update`: конфигурация обновления с HTTP-хранилища
- `enabled`: использование HTTP-хранилища, вместо FTP-сервера
- `ftp_mirror_update`: позволяет использовать FTP-сервер как зеркало, при недоступности HTTP-хранилища
- `encryption`: включение\отключение шифрования url-адреса HTTP-хранилища
- `url`: url-адрес HTTP-хранилища, указывается полный путь до каталога с файлами обновления

Параметры выполняемых cmd-скриптов, при наличии обновления:
- `at_startup`: конфигурация запускаемого скрипта, при обнаружении обновления
- `enabled`: включение\отключение выполнения скрипта
- `file_name`: путь к скрипту (по умолчанию ожидается что скрипт лежит рядом с файлом `updater.exe`)
- `timeout`: тайм-аут, в течении которого проверяется активность процесса обновляемого приложения, если процесс остаётся запущен, обновление прерывается
<br><br>
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
py -3.8 -m PyInstaller --hidden-import cryptography.fernet --onefile --noconsole --icon=favicon.ico --add-data "icon.ico:." ftpupdater.py
```

Параметр **`--onefile`** является обязательным.

### Замена ключей безопасности

Ключи безопасности определяются в конструкторе класса **`ResourceManagement()`** в файле **`sys_manager.py`** . Перед сборкой приложения рекомендуется заменить их на собственные уникальные ключи. 

```python
class ResourceManagement:
    signature_check_disable_key = "aTdW<<9XyeqNM*LS2<"
    signature_public_key = bytes.fromhex("4d37cceab50a53ad61f43535754423cd1ecf9ff0c98ebf4ee8db9ade72df9d51")
    crypto_key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM='
```

- `signature_check_disable_key`: ключ отключения проверки подписи файла при обновлении, может быть случайным набором латинских символов любой длинны
- `signature_public_key `: публичный **`ed25519`**-ключ для проверки подписи файла, получить пару ключей можно выполнив скрипт **`ed25519-keypair.py`** в каталоге **`_scripts`**
- `crypto_key`: `fernet`-ключ, которым шифруются учётные данные от HTTP/FTP-сервера, получить новый уникальный ключ можно выполнив скрипт **`fernet-key.py`** в каталоге **`_scripts`**

### Запуск из исходников в виртуальном окружении

Исходники подготовлены для сборки утилиты в .exe-файл. Для запуска в виртуальном окружении, необходимо в файле  **`updater.py`** из метода **`main()`** класса **`Updater()`** убрать часть кода, отвечающую за перемещение исполняемого файла в каталог **`_temp`**

<details>
<summary>Пример того, как в этом случае должен выглядеть метод <b>main()</b> в <b>updater.py</b></summary>
    
```python
class Updater(sys_manager.ProcessManagement):
    ...
    ...
    ...
        def main(
            self,
            main_file,
            temp_dir,
            forwarded_args=None,
            progress_callback=None,
            exit_on_complete=True,
            cleanup_on_complete=True):
            try:
                result = update_flow.UpdateResult(False, False, "The update did not complete correctly")
                logger.updater.info(f"updater.exe started")
                logger.updater.info(f"Executable file version: {about.version}")
                logger.updater.debug(f"Working directory: '{work_directory}'")
                logger.updater.debug(f"Configuration file read: {self.config}")
    
                update_flow.initialize_connection(self, http_connect, ftp_connect, progress_callback=progress_callback)
    
                try:
                    status_update = update_flow.check_for_update(
                        self,
                        http_connect,
                        ftp_connect,
                        application_directory="..",
                        progress_callback=progress_callback
                    )
    
                    if status_update == True:
                        logger.updater.info("Update found")
                        update_flow.emit_progress(
                            progress_callback,
                            "update_found",
                            "Update found",
                            progress=54
                        )
                        if self.update_method == "http":
                            temp_exe_file = http_connect.download_file(
                                self.exe_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)[0]
                        else:
                            temp_exe_file = ftp_connect.download_file(
                                self.exe_name, self.remote_path, self.timeout_update, self.max_attempts_update, attempt=1)[0]
                        update_flow.emit_progress(
                            progress_callback,
                            "update_file_downloaded",
                            f"File '{self.exe_name}' downloaded",
                            progress=60
                        )
    
                        size_file = self.get_size_file(temp_exe_file)
                        temp_file_version = self.get_exe_version(temp_exe_file)
                        file_hash = self.file_sha256(os.path.abspath(temp_exe_file))
    
                        if not self.signature_check_disable_config == self.signature_check_disable_key:
                            signature_valid = self.verify_metadata(
                                self.exe_signature,
                                temp_file_version,
                                size_file,
                                self.exe_name,
                                file_hash
                            )
    
                            if not signature_valid:
                                logger.updater.warn(f"File '{self.exe_name}' failed authenticity verification")
                                self.clear_update_resources()
                                result = update_flow.UpdateResult(
                                    False,
                                    False,
                                    f"File '{self.exe_name}' failed authenticity verification"
                                )
                            else:
                                logger.updater.info(f"File '{self.exe_name}' passed authenticity verification")
                                update_flow.emit_progress(
                                    progress_callback,
                                    "update_file_verified",
                                    f"File '{self.exe_name}' passed authenticity verification",
                                    progress=66
                                )
                                update_status = self.update_run(
                                    temp_file_version,
                                    main_file_path=main_file,
                                    http_connection=http_connect,
                                    ftp_connection=ftp_connect,
                                    progress_callback=progress_callback
                                )
                                if update_status:
                                    result = update_flow.completed_result(updated=True)
                        else:
                            logger.updater.warn("Warning: server file signature verification is disabled")
                            update_status = self.update_run(
                                temp_file_version,
                                main_file_path=main_file,
                                http_connection=http_connect,
                                ftp_connection=ftp_connect,
                                progress_callback=progress_callback
                            )
                            if update_status:
                                result = update_flow.completed_result(updated=True)
                    else:
                        logger.updater.info("Update not found")
                        self.clear_update_resources()
                        result = update_flow.completed_result(updated=False)
    
                except Exception:
                    logger.updater.error(f"Failed to perform the update", exc_info=True)
                    result = update_flow.UpdateResult(False, False, "Failed to perform the update")
    
                if result.success:
                    update_flow.emit_progress(
                        progress_callback,
                        "completed",
                        result.message,
                        status="completed",
                        progress=100
                    )
                elif progress_callback is not None:
                    update_flow.emit_progress(
                        progress_callback,
                        "error",
                        result.message,
                        status="error"
                    )
    
                if cleanup_on_complete:
                    self.clear_temp()
                if exit_on_complete:
                    os._exit(0)
                return result
            except Exception:
                logger.updater.critical(f"Unexpected interruption of the main thread occurred", exc_info=True)
                if cleanup_on_complete:
                    self.clear_temp()
                if exit_on_complete:
                    os._exit(1)
                result = update_flow.UpdateResult(False, False, "Unexpected interruption of the main thread occurred")
                update_flow.emit_progress(progress_callback, "error", result.message, status="error")
                return result
```
</details>

## Режимы работы

### 1. Запуск без аргументов

В этом режиме **`updater`** запускается без аргументов запуска, необходимую конфигурацию логгера, скриптов запуска и остановки обновляемого приложения он получает из **`updater.json`**. Скрипты запуска и остановки обновляемого приложения в этом режиме располагаются рядом с исполняемым файлом **`updater.exe`**.

### 2. Запуск с аргументами

Второй режим подразумевает получение с аргументами запуска необходимой конфигурации и команды на запуск обновляемого приложения, от самого приложения. В **`updater.json`** в этом режиме допускается оставить только данные для подключения к **`HTTP/FTP`**-серверу 

**Основные аргументы запуска:**

- `--check` - одиночный аргумент, при запуске с которым **`updater`** только проверит наличие обновления и вернёт в **`stdout`** либо **`True`**, либо **`False`**. С аргументом `check` утилита больше ничего в **`stdout`** не пишет, т.е. если вернулось что-то другое, ни вернулось ничего или **`updater`** завершился с **`exit_code = 1`**, значит проверка завершилась ошибкой

- `--upgrade` - запускает полный цикл проверки и установки обновления как и при запуске без аргументов, но добавляет поддержку опциональных аргументов

**Опциональные аргументы запуска (работают только вместе с `--upgrade`):**

- `--gui` - показывает окно с прогрессом обновления
- `--cmd` - команда, которая будет выполнена в **`CMD`** после успешной установки обновления или после закрытия окна с прогрессом, при использовании `--gui`
- `--logs-dir` - путь к каталогу с логами
- `--logs-level` - уровень логирования
- `--logs-clear` - срок хранения логов (дни)

В обоих слуаях обязательно требуется передать утилите рабочую директорию в которой расположен исполняемый файл **`updater.exe`**

## Обновление

### 1. Получение manifest.json

Нужно положить рядом с **`ftpupdater.exe`** исполняемый файл обновляемого приложения, название которого будет совпадать со значением `exe_name` в конфиге и в метаданных которого будет указана его версия.

Если обновление содержит другие файлы, кроме исполняемого, их нужно запаковать в zip-архив, с сохранением структуры каталогов и так же положить его рядом с **`ftpupdater.exe`**. Имя архива должно совпадать с именем исполняемого файла (пример: **`app.exe`** и **`app.zip`**). Сам исполняемый файл в архив лучше не запаковывать.

Запустить **`ftpupdater.exe --mkey "you_private_ed25519_key"`** (`70a59dead66ebbfea76ce9dcc1bc2f2206fe06e5422e1bb2171a1c67871ae46a` - ключ для тестовой сборки)

Полученный **`manifest.json`** загружается на сервер вместе с исполняемым файлом и zip-архивом.

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

### 2. Шифрование учётных данных

Чтобы записать в конфиг адрес подключения к HTTP-хранилищу или учётные данные от FTP-сервера в зашифрованном виде, используются аргументы запуска **`--http`**, **`--ftpuser`**, **`--ftppass`**

**Пример**:<br>
**`ftpupdater.exe --http http://server.com/updater/`**<br>
**`ftpupdater.exe --ftpuser user --ftppass password`**


### 3. Отключение проверки подписи

Для этого в файле конфигурации **`updater.json`** нужно указать уникальный ключ для параметра `signature_check_disable_key`.

На проверке подписи так же завязана проверка целостности загруженных файлов. Функция добавлена для отладки и её использование не рекомендуется.

Если проверка подписи отключена, то **`manifest.json`** можно взять из примера. Достаточно в нём прописать имя исполняемого файла, его версию и имя zip-архива. Ключ **`signature`** в этом случае не проверяется, его можно убрать, оставить как есть или заменить пустой строкой.

Если в обновлении имеется только исполняемый файл, нужно из **`manifest.json`** убрать ключ с именем архива или изменить его так, чтобы он не совпадал с именем исполняемого файла (пример: **`app.exe`** и **`app123.zip`**)

## Ключи, используемые в тестовой сборке

- **`t_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM=`**: ключ для шифрования учётных данных
- **`aTdW<<9XyeqNM*LS2<`**: ключ для отключения проверки подписи
- **`70a59dead66ebbfea76ce9dcc1bc2f2206fe06e5422e1bb2171a1c67871ae46a`**: приватный ключ для генерации подписи исполняемого файла
