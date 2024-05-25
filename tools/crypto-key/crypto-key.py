from cryptography.fernet import Fernet
import os, sys

log_file = os.path.join("code.txt")
sys.stdout = open(log_file, 'a')

def encrypt_data(key, data):
    cipher = Fernet(key)
    encrypted_data = cipher.encrypt(data.encode())
    return encrypted_data

def decrypt_data(key, encrypted_data):
    cipher = Fernet(key)
    decrypted_data = cipher.decrypt(encrypted_data).decode()
    return decrypted_data

# Пример использования:
key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM='  # Ваш ключ
data_to_encrypt = "user"
data_to_encrypt2 = "password"

encrypted_data = encrypt_data(key, data_to_encrypt)
print("Зашифрованные данные:", encrypted_data)

encrypted_data2 = encrypt_data(key, data_to_encrypt2)
print("Зашифрованные данные 2:", encrypted_data2)
print()

decrypted_data = decrypt_data(key, encrypted_data)
print("Расшифрованные данные:", decrypted_data)
decrypted_data2 = decrypt_data(key, encrypted_data2)
print("Расшифрованные данные2:", decrypted_data2)
print()
print()
print()


# если вдруг нужно расшифровать что-то другое этим же ключом =)
data_to_encrypt3 = "gAAAAABmUjbbR3NCcm14lmFezwWFOKeW_nuHKB5Jhr9rLJNIfhU3A2s6o1NhVh3s7Kb74GNh-qHSi2zTNK6n819mxAo9ycFajw=="
decrypted_data3 = decrypt_data(key, data_to_encrypt3)

print("Расшифрованные данные 3:", decrypted_data3)
