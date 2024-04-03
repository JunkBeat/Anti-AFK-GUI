from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QMetaObject, Qt, pyqtSlot, QTime

class Timer(QObject):
    timeout = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.timer_started = False
        self.remaining_seconds = 0
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.handle_timeout)
    
    def is_active(self):
        return self.timer_started
        
    def start(self, seconds):
        if not self.timer_started:
            self.remaining_seconds = seconds
            self.timeout.emit() #display first second
            QMetaObject.invokeMethod(self.timer, "start", Qt.QueuedConnection) 
            self.timer_started = True

    def stop(self):
        if self.timer_started:
            QMetaObject.invokeMethod(self.timer, "stop", Qt.QueuedConnection)
            self.timer_started = False

    @pyqtSlot()
    def handle_timeout(self):
        self.remaining_seconds -= 1
        if self.remaining_seconds <= 0:
            self.stop()
            self.finished.emit()
        else:
            self.timeout.emit()
    
    @property
    def formatted_time(self):
        time = QTime(0, 0)
        time = time.addSecs(self.remaining_seconds)

        if time.hour() > 0:
            return time.toString("hh:mm:ss")
        else:
            return time.toString("mm:ss")

class SingleshotTimer(QObject):
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.timer_started = False
        self.one_timed_timer = QTimer()
        self.one_timed_timer.timeout.connect(self.handle_timeout)

    def is_active(self):
        return self.timer_started

    @pyqtSlot()
    def handle_timeout(self):
        self.stop()
        self.finished.emit()

    def start(self, delay_ms):
        self.one_timed_timer.setInterval(delay_ms)
        if not self.timer_started:
            #self.one_timed_timer.start()
            QMetaObject.invokeMethod(self.one_timed_timer, "start", Qt.QueuedConnection)
            self.timer_started = True

    def stop(self):
        if self.timer_started:
            #self.one_timed_timer.stop()
            QMetaObject.invokeMethod(self.one_timed_timer, "stop", Qt.QueuedConnection)
            self.timer_started = False