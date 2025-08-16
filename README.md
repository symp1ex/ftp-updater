# ftp-updater

## Описание
Утилита для обновления приложений Windows с FTP-сервера.

Предполагается, что исполняемый файл утилиты находится в каталоге **`updater`**; каталог **`updater`** должен находиться в корне обновляемого приложения. 

Логика работы следующая: утилита проверяет версию **`exe-файла`**, указанного в конфиге **`updater.json`** ключ **`exe_name`**. Затем она проверяет версию файла на FTP-сервере по пути, также указанному в конфиге по ключу **`ftp_path`**. Если версия файла на FTP-сервере выше, то утилита скачивает всё содержимое каталога **`ftp_path`**, сохраняя его структуру.<br>Остановка и запуск основного приложения при наличии обновления, организованы через настраиваемые cmd-скрипты.

Утилита работает из временной директории, для возможности самообновления вместе с основным приложением. Присутствуют проверка подписи файла на сервере и шифрование учётных данных от FTP-сервера.

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
        "exe_name": "name.exe",
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
- `ftp_path`: папка на FTP-сервере, в которой лежат файлы для обновления
- `exe_name`: имя исполняемого файла основного приложения (расположен рядом с папкой `updater` в корне приложения)
- `attempt_count`: количество попыток проверки и скачивания обновления
- `attempt_timeout`: интервал между попытками (в секундах)
- `signature_check_disable_key`: ключ отключающий проверку подписи файла на сервере

Параметры отправки данных на FTP-сервер:
- `enabled`: включение\отключение отправки данных
- `local_path`: путь до папки, содержимое которой будет отправляться на FTP-сервер
- `attempt_count`: количество попыток проверки и скачивания обновления
- `attempt_timeout`: интервал между попытками (в секундах)

Параметры выполняемых cmd-скриптов, при наличии обновления:
- `at_startup`: скрипт запускаемых когда обновление было обнаружено
- `enabled`: включение\отключение запуска этого скрипта
- `file_name`: путь к скрипту (по умолчанию ожидается что скрипт лежит рядом с файлом `updater.exe`)
- `timeout`: задержка после выполнения скрипта
<br>

- `at_completion`: скрипт запускаемых когда обновление установлено
- `enabled`: включение\отключение запуска этого скрипта
- `file_name`: путь к скрипту (по умолчанию ожидается что скрипт лежит рядом с файлом `updater.exe`)

Параметры логирования:
- `level`: уровень логирования
- `path`: путь к папке с логами
- `clear_days`: срок хранения логов (дни)

</details>

## Проверка подписи файла на сервере

### Подпись файла для обновления
В **`tools/get-hash/`** лежит скрипт, который содержит переменные **`key`** и **`file_path`**.

<details>
<summary><b>get-hash.py</b></summary>
  
```python
log_file = os.path.join("hash.txt")
sys.stdout = open(log_file, 'a')

def get_exe_metadata(file_path):
    try:
        info = win32api.GetFileVersionInfo(file_path, '\\')
        version = info['FileVersionMS'] >> 16, info['FileVersionMS'] & 0xFFFF, info['FileVersionLS'] >> 16, info['FileVersionLS'] & 0xFFFF
        return '.'.join(map(str, version))
    except Exception as e:
        print("Error:", e)
        return None

def get_size_file(file_path):
    file_stats = os.stat(file_path)
    size = file_stats[stat.ST_SIZE]
    return size

key = b'R%Q480WMofRwn16L' # ключ

def sign_metadata(size, version):
    metadata = f"{size}:{version}"
    signature = hmac.new(key, metadata.encode(), hashlib.sha256).hexdigest()
    return signature


file_path = ".\\getad.exe" #путь к файлу, на основе которого хотим получить подпись
version = get_exe_metadata(file_path)
size = get_size_file(file_path)
metadata = sign_metadata(version, size)
print(version)
print(size)
print(metadata)
```
</details>

В **`file_path`** указываем путь до исполняемого файла обновляемого приложение. В метаданных файла обязательно должа быть указана версия файла. В **`key`** указывется уникальный ключ, на основе которого генерируется подпись. Ключ может быть любыи набором символов любой длинны.<br>После выполнения скрипта получим текстовый документ содержащий хэш подписи вида **`71f90f211642fac46a57c7463d1b60e5aea3a879753fd8fda3bf5ddc713afee0`**, его необходимо добавить к метаданным файла в поле **`LegalCopyright`**


### Отключение проверки подписи
Для этого в конфиге нужно указать уникальный ключ для параметра `signature_check_disable_key`. Ключ проверяется в **`updater.py`** в функции **`main()`**. Ключ может быть любым набором символов любой длинны.

<details>
<summary><b>updater.py</b></summary>
  
```python
if not check_signature_disabled_key == "aTdW<<9XyeqNM*LS2<": # ключ
    signature = sign_metadata(ftp, size_file)
    if not signature == description:
```
</details>

## Использование шифрования учётных данных

Переменная **`key`** функции **`decrypt_data()`** в файле **`updater.py`** сожержит ключ, которым шифруются учётные данные для получения доступа к FTP-серверу

<details>
<summary><b>updater.py</b></summary>
  
```python
def decrypt_data(encrypted_data):
    try:
        key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM=' # ключ
        cipher = Fernet(key)
        decrypted_data = cipher.decrypt(encrypted_data).decode()
        return decrypted_data
    except Exception:
        logger.logger_service.error("Не удалось дешифровать данные для подключения к боту", exc_info=True)
```
</details>

В **`tools\crypto-key`** лежит скрипт, в который нужно вставить свои учётные данные и выполнить его. На выходе получите текстовый документ с зашифрованными данными, которые нужно будет вставить в конфиг

<details>
<summary><b>crypto-key.py</b></summary>
  
```python
# Пример использования:
key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM='  # Ваш ключ
data_to_encrypt = "user"
data_to_encrypt2 = "password"
```
</details>

Там же лежит **`gen-key.py`**, запустив который, можно сгенерировать свой уникальный ключ.

## Ключи, используемые в тестовой сборке
- **`t_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM=`**: ключ для шифрования учтёных данных
- **`R%Q480WMofRwn16L`**: ключ для генерации подписи исполняемого файла
- **`aTdW<<9XyeqNM*LS2<`**: ключ для отключения проверки подписи
