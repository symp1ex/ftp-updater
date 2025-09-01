import base64
import os, sys

log_file = os.path.join("key.txt")
sys.stdout = open(log_file, 'a')

# Генерация случайного ключа длиной 32 байта
key = base64.urlsafe_b64encode(os.urandom(32))

# Ключ в виде строки
key_str = key.decode()

print(f"Сгенерированный ключ: {key_str}")
