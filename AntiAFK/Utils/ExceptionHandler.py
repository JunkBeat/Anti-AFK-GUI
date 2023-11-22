from PyQt5.QtCore import QObject, pyqtSignal
import datetime
import traceback
import os

class ExceptionHandler(QObject):
    show_error_message = pyqtSignal(str, str)

    def __init__(self, ex_cls, ex, tb):
        super().__init__()
        self.ex_cls = ex_cls
        self.ex = ex
        self.tb = tb

    def main(self):
        text = '{}: {}:\n'.format(self.ex_cls.__name__, self.ex)
        short_text = text
        text += ''.join(traceback.format_tb(self.tb))
        print(text)
        self.create_report(text)
        self.show_error_message.emit(short_text, text)

    def create_report(self, text):
        current_datetime = datetime.datetime.now()
        formatted_datetime = current_datetime.strftime("%Y.%m.%d_%H.%M.%S")
        
        file = f"crash_report_{formatted_datetime}.txt"
        folder = "crash_reports"

        if not os.path.exists(folder):
            os.makedirs(folder)
        
        with open(os.path.join(folder, file), 'w') as report_file:
            report_file.write(text)