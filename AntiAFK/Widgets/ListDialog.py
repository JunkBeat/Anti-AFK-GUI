import sys
from PyQt5.QtWidgets import QDialog, QGridLayout, QApplication, QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QListWidget, QInputDialog, QLineEdit, QListWidgetItem
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon

class EditableItemWidget(QWidget):
    def __init__(self, text, list_widget):
        super().__init__()
        self.list_widget = list_widget
        self.line_edit = QLineEdit(text)
        self.line_edit.setFont(QFont('Arial', 7))
        
        self.remove_button = QPushButton("Remove")
        self.remove_button.setFocusPolicy(Qt.NoFocus)
        self.remove_button.setFont(QFont('Arial', 8))
        self.remove_button.clicked.connect(self.remove_item)

        layout = QHBoxLayout(self)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.remove_button)
        layout.setContentsMargins(10, 5, 10, 0)

    def remove_item(self):
        item_index = self.list_widget.indexAt(self.pos())
        self.list_widget.takeItem(item_index.row())
        self.deleteLater()

class ListDialog(QDialog):
    def __init__(self, text_list, title="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)

        self.text_list = text_list
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("QListWidget::item:hover { background-color: transparent; }")

        add_button = QPushButton("Add")
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")

        add_button.clicked.connect(self.ask_and_add)
        ok_button.clicked.connect(self.save_and_close)
        cancel_button.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addWidget(add_button)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)
        layout.addLayout(button_layout)

        self.setFixedSize(300, 300)
        self.parse_and_add()

    def parse_and_add(self):
        items = self.text_list.split(',')
        for item in items:
            self.add_item(item.strip())

    def ask_and_add(self):
        item_text, ok = QInputDialog.getText(self, "Add Item", "Enter item:")
        if ok and item_text:
            self.add_item(item_text)

    def add_item(self, text):
        item = EditableItemWidget(text, self.list_widget)
        list_item = QListWidgetItem()
        list_item.setSizeHint(item.sizeHint())
        self.list_widget.addItem(list_item)
        self.list_widget.setItemWidget(list_item, item)

    def save_and_close(self):
        new_text = ", ".join(
            [
                self.list_widget.itemWidget(self.list_widget.item(i)).line_edit.text().strip()
                for i in range(self.list_widget.count())
            ]
        )
        self.text_list = new_text
        self.accept()

class MyWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.text_edit = QLineEdit("1,10,1,2,3,6")
        self.expand_button = QPushButton("Expand")
        self.expand_button.clicked.connect(self.show_expanded_view)

        layout = QVBoxLayout(self)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.expand_button)

    def show_expanded_view(self):
        self.setDisabled(True)

        list_dialog = ListDialog(self.text_edit.text(), parent=self)

        if list_dialog.exec():
            self.text_edit.setText(list_dialog.text_list)

        list_dialog.deleteLater()
        self.setDisabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec_())
