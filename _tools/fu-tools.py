from cryptography.fernet import Fernet
import win32api
import os
import stat
import hashlib
import hmac
import sys
import json

log_file = os.path.join("output.txt")
sys.stdout = open(log_file, 'a')

def write_json_file(json_file, config):
    with open(json_file, "w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=4)

def read_config_file(json_file):
    with open(json_file, "r", encoding="utf-8") as file:
        config = json.load(file)
        return config

def get_first_other_exe():
    try:
        current_exe = os.path.basename(sys.executable)
    except:
        current_exe = os.path.basename(os.path.abspath(__file__))
    print(current_exe)
    
    try:
        all_files = []
        exe_file = None

        # Сначала соберем все файлы
        for filename in os.listdir():
            all_files.append(filename)
            if filename.endswith('.exe') and filename != current_exe:
                exe_file = filename

        print(os.path.abspath("."))
        print(all_files)
    except Exception as e:
        print("Error:", e)
        exe_file = "None"
        all_files = "None"
    return exe_file, all_files

def get_name_zip(exe_name):
    try:
        exe_name_0 = exe_name.split('.')[0]  # получаем 'file'
        zip_name = f"{exe_name_0}.zip"  # создаем новую строку 'file.zip'
    except Exception as e:
        print("Error:", e)
        zip_name = "None"
    return zip_name

def get_exe_version(file_path):
    try:
        info = win32api.GetFileVersionInfo(file_path, '\\')
        version = info['FileVersionMS'] >> 16, info['FileVersionMS'] & 0xFFFF, info['FileVersionLS'] >> 16, info['FileVersionLS'] & 0xFFFF
        return '.'.join(map(str, version))
    except Exception as e:
        print("Error:", e)
        return None

def get_file_metadata(file_path, field):  # получение конкретного поля из метаданных исполняемого файла
    try:
        language, codepage = win32api.GetFileVersionInfo(file_path, '\\VarFileInfo\\Translation')[0]
        stringfileinfo = u'\\StringFileInfo\\%04X%04X\\%s' % (
        language, codepage, field)  # конкретное поле LegalCopyright
        result = win32api.GetFileVersionInfo(file_path, stringfileinfo)
    except Exception as e:
        print("Error:", e)
        result = "unknown"
    return result

def get_size_file(file_path):
    try:
        file_stats = os.stat(file_path)
        size = file_stats[stat.ST_SIZE]
    except Exception as e:
        print("Error:", e)
        size = "None"
    return size

def sign_metadata(manifest_key, key1, key2, key3, key4):
    try:
        metadata = f"{key1}:{key2}:{key3}:{key4}"
        manifest_key_bytes = manifest_key.encode('utf-8')
        signature = hmac.new(manifest_key_bytes, metadata.encode(), hashlib.sha256).hexdigest()
    except Exception as e:
        print("Error:", e)
        signature = "None"
    return signature

def encrypt_data(crypto_key_bytes, data):
    try:
        cipher = Fernet(crypto_key_bytes)
        encrypted_data = cipher.encrypt(data.encode())
    except Exception as e:
        print("Error:", e)
        encrypted_data = "None"
    return encrypted_data

def decrypt_data(crypto_key_bytes, encrypted_data):
    try:
        encrypted_bytes = encrypted_data.encode('utf-8')
        cipher = Fernet(crypto_key_bytes)
        decrypted_data = cipher.decrypt(encrypted_bytes).decode()
    except Exception as e:
        print("Error:", e)
        decrypted_data = "None"
    return decrypted_data

def main():
    json_file = "fu-tools.json"
    config = read_config_file(json_file)

    manifest_key = config.get("manifest_key")
    crypto_key = config.get("crypto_key")
    crypto_key_bytes = crypto_key.encode('utf-8')

    username = config.get("username")
    password = config.get("password")

    decrypt_data_1 = config.get("decrypt_data_1")
    decrypt_data_2 = config.get("decrypt_data_2")

    exe_name, files_list = get_first_other_exe()
    zip_name = get_name_zip(exe_name)

    print(exe_name)

    version_exe = get_exe_version(exe_name)
    originalfilename_exe = get_file_metadata(exe_name, "OriginalFilename")
    size_exe = get_size_file(exe_name)

    signed_exe = sign_metadata(manifest_key, version_exe, size_exe, exe_name, originalfilename_exe)

    if zip_name in files_list:
        print(zip_name)
        size_zip = get_size_file(zip_name)
        signed_zip = sign_metadata(manifest_key, int(size_zip / len(zip_name)), size_zip, zip_name,"originalfilename")

        manifest_data = {
            exe_name: {
                "version": version_exe,
                "signature": signed_exe
            },
            zip_name: {
                "signature": signed_zip
            }
        }
    else:
        manifest_data = {
            exe_name: {
                "version": version_exe,
                "signature": signed_exe
            }
        }

    manifest = "manifest.json"
    write_json_file(manifest, manifest_data)

    encrypted_data = encrypt_data(crypto_key_bytes, username)
    encrypted_data2 = encrypt_data(crypto_key_bytes, password)

    try: encrypted_data_decode = encrypted_data.decode('utf-8')
    except: encrypted_data_decode = "None"

    try: encrypted_data_decode2 = encrypted_data2.decode('utf-8')
    except: encrypted_data_decode2 = "None"


    print()
    print("Имя пользователя:", encrypted_data_decode)

    print("Пароль:", encrypted_data_decode2)
    print()


    try: decrypted_data_1 = decrypt_data(crypto_key_bytes, decrypt_data_1)
    except: decrypted_data_1 = "None"
    try: decrypted_data_2 = decrypt_data(crypto_key_bytes, decrypt_data_2)
    except: decrypted_data_2 = "None"

    print("Расшифрованные данные:", decrypted_data_1)
    print("Расшифрованные данные 2:", decrypted_data_2)
    print(".")
    print(".")
    print(".")
    print(".")
    input()

if __name__ == "__main__":
    main()

















