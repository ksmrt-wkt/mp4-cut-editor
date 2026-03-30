from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView
)

from .i18n import tr
from .utils import Segment, format_display_time


class SegmentList(QWidget):
    segmentRemoveRequested = pyqtSignal(int)  # index

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._header = QLabel()
        self._header.setStyleSheet("font-weight: bold; font-size: 11px;")
        layout.addWidget(self._header)

        self._table = QTableWidget(0, 4)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(3, 52)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setMinimumWidth(260)
        layout.addWidget(self._table)

        self._total_label = QLabel()
        self._total_label.setStyleSheet("font-size: 10px; color: #aaa;")
        layout.addWidget(self._total_label)

        self._segments: list[Segment] = []
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._header.setText(tr("seg_list_header"))
        self._table.setHorizontalHeaderLabels([
            tr("seg_col_start"), tr("seg_col_end"), tr("seg_col_dur"), ""
        ])
        self.update_segments(self._segments)

    def update_segments(self, segments: list[Segment]) -> None:
        self._segments = list(segments)
        self._table.setRowCount(0)
        total_ms = 0
        for i, seg in enumerate(segments):
            row = self._table.rowCount()
            self._table.insertRow(row)

            self._table.setItem(row, 0, QTableWidgetItem(format_display_time(seg.start_ms)))
            self._table.setItem(row, 1, QTableWidgetItem(format_display_time(seg.end_ms)))
            self._table.setItem(row, 2, QTableWidgetItem(format_display_time(seg.duration_ms)))

            btn = QPushButton(tr("seg_btn_remove"))
            btn.setFixedHeight(22)
            btn.setStyleSheet("font-size: 10px; color: #e05050;")
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _, idx=i: self.segmentRemoveRequested.emit(idx))
            self._table.setCellWidget(row, 3, btn)

            total_ms += seg.duration_ms

        n = len(segments)
        self._total_label.setText(
            tr("seg_total").format(n=n, time=format_display_time(total_ms))
        )
