import sys
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QApplication, QWidget, QDesktopWidget

class Screensaver(QWidget):
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        desktop = QDesktopWidget().screenGeometry()
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0))

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setCursor(Qt.BlankCursor)
        self.setGeometry(0, 0, desktop.width(), desktop.height())
        self.setPalette(palette)
        self.setMouseTracking(True);

    def mouseMoveEvent(self, event):
        self.close()
        self.closed.emit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    screensaver = Screensaver()
    screensaver.showFullScreen()
    sys.exit(app.exec_())
