import os
import sys
import traceback
from datetime import datetime, timedelta

def log_with_timestamp(message):
    try:
        log_folder = "..\\l"

        if not os.path.exists(log_folder):
            os.makedirs(log_folder)

        # Получаем текущую дату
        current_date = datetime.now()

        # Определяем дату, старше которой логи будут удаляться
        old_date_limit = current_date - timedelta(days=14)

        # Удаляем логи старше 10 дней
        for file_name in os.listdir(log_folder):
            file_path = os.path.join(log_folder, file_name)
            file_creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
            if file_creation_time < old_date_limit:
                os.remove(file_path)

        timestamp = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_folder, f"{timestamp}-updater.log")
        default_stdout = sys.stdout
        sys.stdout = open(log_file, 'a', encoding="utf-8")

        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S.%f")[:-3]+"]"
        print(f"{timestamp} {message}")
        sys.stdout.close()
        sys.stdout = default_stdout
    except:
        pass


def log_console_out(message):
    try:
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S.%f")[:-3]+"]"
        print(f"{timestamp} {message}")
        log_with_timestamp(message)
    except:
        pass
    
    
def exception_handler(exc_type, exc_value, exc_traceback):
    try:
        error_message = f"ERROR: An exception occurred + \n"
        error_message += ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        log_with_timestamp(error_message)
        # Вызываем стандартный обработчик исключений для вывода на экран
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    except:
        pass
