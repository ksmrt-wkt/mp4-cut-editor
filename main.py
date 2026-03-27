import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from app.main_window import MainWindow
from app import ffmpeg_runner


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MP4 カットエディタ")
    app.setStyle("Fusion")

    # Dark palette
    from PyQt6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(40, 40, 40))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(60, 60, 60))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Button, QColor(55, 55, 55))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Link, QColor(80, 160, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(60, 130, 200))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    # Check ffmpeg
    try:
        ffmpeg_runner.find_ffmpeg()
    except RuntimeError as e:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("ffmpeg が見つかりません")
        msg.setText(str(e))
        msg.exec()
        sys.exit(1)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
