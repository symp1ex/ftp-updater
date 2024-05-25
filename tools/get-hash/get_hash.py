import win32api
import os
import stat
import hashlib
import hmac
import sys

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

key = b'R%Q480WMofRwn16L'

def sign_metadata(size, version):
    metadata = f"{size}:{version}"
    signature = hmac.new(key, metadata.encode(), hashlib.sha256).hexdigest()
    return signature


file_path = ".\\getad.exe"
version = get_exe_metadata(file_path)
size = get_size_file(file_path)
metadata = sign_metadata(version, size)
print(version)
print(size)
print(metadata)