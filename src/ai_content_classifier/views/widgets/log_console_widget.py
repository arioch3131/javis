# ai_content_classifier/views/widgets/log_console_widget.py
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QTextEdit


class LogConsoleWidget(QTextEdit):
    """
    A simple console widget to display application log messages.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Courier", 9))
        self.setStyleSheet("background-color: #000; color: #0f0;")

    def log_message(self, message, level="INFO"):
        """
        Adds a message to the console with a log level.
        """
        color_map = {
            "INFO": "#0f0",  # Green
            "DEBUG": "#00f",  # Blue
            "WARNING": "#ff0",  # Yellow
            "ERROR": "#f00",  # Red
            "CRITICAL": "#f00",  # Red
        }
        color = color_map.get(level.upper(), "#fff")  # White by default

        log_entry = f'<font color="{color}">[{level.upper()}] {message}</font>'
        self.append(log_entry)
