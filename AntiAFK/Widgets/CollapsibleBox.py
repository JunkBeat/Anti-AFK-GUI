from PyQt5.QtCore import pyqtSlot, Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QToolButton, QScrollArea, QVBoxLayout

class CollapsibleBox(QWidget):
    stateChanged = pyqtSignal(bool)

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.content_height = 0

        self.toggle_button = QToolButton(
            text=title, 
            checkable=True, 
            checked=False
        )
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setArrowType(Qt.RightArrow)
        self.toggle_button.toggled.connect(self.on_toggled)
        self.toggle_button.toggled.connect(self.stateChanged)

        self.content_area = QScrollArea(
            maximumHeight=0, 
            minimumHeight=0
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content_area)

    @pyqtSlot(bool)
    def on_toggled(self, checked):
        arrow_type = Qt.DownArrow if checked else Qt.RightArrow
        self.toggle_button.setArrowType(arrow_type)
        content_height = self.content_area.layout().sizeHint().height()
        self.content_area.setFixedHeight(content_height if checked else 0)

    def setContentLayout(self, layout):
        self.content_area.setLayout(layout)

    def isChecked(self):
        return self.toggle_button.isChecked()

    def setChecked(self, checked):
        #self.toggle_button.blockSignals(True)  
        self.toggle_button.setChecked(checked)
        #self.toggle_button.blockSignals(False) 
        self.on_toggled(checked)