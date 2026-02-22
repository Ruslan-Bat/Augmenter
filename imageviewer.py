from __future__ import annotations
import os
import csv
import shutil

from PyQt5.QtPrintSupport import QPrintDialog, QPrinter
from PyQt5.QtWidgets import (
    QApplication, QDialog, QFileDialog, QLabel,
    QMainWindow, QMessageBox, QScrollArea,
    QSizePolicy, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QCheckBox, QTextEdit, QPushButton,
    QLineEdit
)
from PyQt5.QtGui import (
    QColorSpace, QGuiApplication,
    QImageReader, QImageWriter, QKeySequence,
    QPalette, QPainter, QPixmap
)
from PyQt5.QtCore import QDir, QStandardPaths, Qt, pyqtSlot


ABOUT = """<p>The <b>Image Viewer</b> example shows how to combine QLabel
and QScrollArea to display an image. QLabel is typically used
for displaying a text, but it can also display an image.
QScrollArea provides a scrolling view around another widget.
If the child widget exceeds the size of the frame, QScrollArea
automatically provides scroll bars. </p><p>The example
demonstrates how QLabel's ability to scale its contents
(QLabel.scaledContents), and QScrollArea's ability to
automatically resize its contents
(QScrollArea.widgetResizable), can be used to implement
zooming and scaling features. </p><p>In addition the example
shows how to use QPainter to print an image.</p>
"""


class ImageViewer(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        # project root (directory of this file) -- use instead of cwd
        self._project_root = os.path.dirname(os.path.abspath(__file__))

        self._scale_factor = 1.0
        self._first_file_dialog = True

        self._image_label = QLabel()
        self._image_label.setBackgroundRole(QPalette.Base)
        self._image_label.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Ignored
        )
        self._image_label.setScaledContents(True)

        self._scroll_area = QScrollArea()
        self._scroll_area.setBackgroundRole(QPalette.Dark)
        self._scroll_area.setWidget(self._image_label)
        self._scroll_area.setVisible(False)
        # Create a tab widget and place the viewer into the second tab
        self._tab_widget = QTabWidget()

        # First tab: placeholder
        tab1 = QWidget()
        tab1_layout = QVBoxLayout()
        tab1_layout.addWidget(QLabel("Placeholder Tab 1"))
        tab1.setLayout(tab1_layout)

        # Second tab: contains a toggle and the viewer (scroll area)
        tab2 = QWidget()
        tab2_layout = QVBoxLayout()
        top_row = QHBoxLayout()
        self._viewer_toggle = QCheckBox("Enable Viewer")
        # reflect initial visibility
        self._viewer_toggle.setChecked(self._scroll_area.isVisible())
        # toggle visibility of the scroll area (viewer)
        self._viewer_toggle.toggled.connect(self._scroll_area.setVisible)
        top_row.addWidget(self._viewer_toggle)
        top_row.addStretch()
        tab2_layout.addLayout(top_row)
        tab2_layout.addWidget(self._scroll_area)
        # Bottom: description field and save button
        bottom_row = QHBoxLayout()
        self._description_edit = QTextEdit()
        self._description_edit.setPlaceholderText("Введите описание...")
        self._description_edit.setFixedHeight(80)
        self._save_button = QPushButton("Сохранить")
        self._save_button.clicked.connect(self._save_info)
        bottom_row.addWidget(self._description_edit)
        bottom_row.addWidget(self._save_button)
        tab2_layout.addLayout(bottom_row)
        tab2.setLayout(tab2_layout)

        self._tab_widget.addTab(tab1, "Tab 1")
        self._tab_widget.addTab(tab2, "Viewer")

        # Third tab: Mass Processing
        tab3 = QWidget()
        tab3_layout = QVBoxLayout()

        # Source directory selector
        src_row = QHBoxLayout()
        src_label = QLabel("Source directory:")
        self._src_lineedit = QLineEdit()
        self._src_browse = QPushButton("Browse...")
        self._src_browse.clicked.connect(self._choose_source_dir)
        src_row.addWidget(src_label)
        src_row.addWidget(self._src_lineedit)
        src_row.addWidget(self._src_browse)
        tab3_layout.addLayout(src_row)

        # Destination directory selector (defaults to source)
        dst_row = QHBoxLayout()
        dst_label = QLabel("Destination directory:")
        self._dst_lineedit = QLineEdit()
        self._dst_browse = QPushButton("Browse...")
        self._dst_browse.clicked.connect(self._choose_dest_dir)
        # default destination: project Images folder
        try:
            default_images = os.path.join(self._project_root, 'Images')
            self._dst_lineedit.setText(default_images)
        except Exception:
            pass
        dst_row.addWidget(dst_label)
        dst_row.addWidget(self._dst_lineedit)
        dst_row.addWidget(self._dst_browse)
        tab3_layout.addLayout(dst_row)

        # Spacer
        tab3_layout.addStretch()

        # Description field (required)
        desc_label = QLabel("Description (required):")
        tab3_layout.addWidget(desc_label)
        self._mass_description = QTextEdit()
        self._mass_description.setFixedHeight(80)
        tab3_layout.addWidget(self._mass_description)

        # Create dataset button
        create_row = QHBoxLayout()
        create_row.addStretch()
        self._create_dataset_btn = QPushButton("Create a dataset")
        self._create_dataset_btn.clicked.connect(self._create_dataset)
        create_row.addWidget(self._create_dataset_btn)
        tab3_layout.addLayout(create_row)

        tab3.setLayout(tab3_layout)
        self._tab_widget.addTab(tab3, "Mass Processing")

        self.setCentralWidget(self._tab_widget)

        self._create_actions()

        self.resize(
            QGuiApplication.primaryScreen().availableSize() * 3 / 5
        )

    def load_file(self, fileName):
        reader = QImageReader(fileName)
        reader.setAutoTransform(True)
        new_image = reader.read()

        native_filename = QDir.toNativeSeparators(fileName)
        if new_image.isNull():
            error = reader.errorString()
            QMessageBox.information(
                self,
                QGuiApplication.applicationDisplayName(),
                f"Cannot load {native_filename}: {error}"
            )
            return False

        self._set_image(new_image)
        self.setWindowFilePath(fileName)
        # remember current file path for saving metadata
        self._current_file = fileName

        # try to load existing description from info.xls
        try:
            self._load_description_for_current_file()
        except Exception:
            # non-fatal: ignore lookup errors
            pass

        w = self._image.width()
        h = self._image.height()
        d = self._image.depth()
        color_space = self._image.colorSpace()
        description = "valid" if color_space.isValid() else "unknown"

        message = (
            f'Opened "{native_filename}", {w}x{h}, '
            f'Depth: {d} ({description})'
        )
        self.statusBar().showMessage(message)
        return True


    def _set_image(self, new_image):
        self._image = new_image

        if self._image.colorSpace().isValid():
            color_space = QColorSpace(QColorSpace.SRgb)
            self._image.convertToColorSpace(color_space)

        self._image_label.setPixmap(QPixmap.fromImage(self._image))
        self._scale_factor = 1.0

        self._scroll_area.setVisible(True)
        self._print_act.setEnabled(True)
        self._fit_to_window_act.setEnabled(True)
        self._update_actions()

        if not self._fit_to_window_act.isChecked():
            self._image_label.adjustSize()

    def _save_file(self, fileName):
        writer = QImageWriter(fileName)
        native_filename = QDir.toNativeSeparators(fileName)

        if not writer.write(self._image):
            error = writer.errorString()
            QMessageBox.information(
                self,
                QGuiApplication.applicationDisplayName(),
                f"Cannot write {native_filename}: {error}"
            )
            return False

        self.statusBar().showMessage(f'Wrote "{native_filename}"')
        return True

    @pyqtSlot()
    def _open(self):
        dialog = QFileDialog(self, "Open File")
        self._initialize_image_filedialog(
            dialog, QFileDialog.AcceptOpen
        )
        while (
            dialog.exec_() == QDialog.Accepted
            and not self.load_file(dialog.selectedFiles()[0])
        ):
            pass

    @pyqtSlot()
    def _save_as(self):
        dialog = QFileDialog(self, "Save File As")
        self._initialize_image_filedialog(
            dialog, QFileDialog.AcceptSave
        )
        while (
            dialog.exec_() == QDialog.Accepted
            and not self._save_file(dialog.selectedFiles()[0])
        ):
            pass

    @pyqtSlot()
    def _print_(self):
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec_() == QDialog.Accepted:
            painter = QPainter(printer)
            pixmap = self._image_label.pixmap()

            rect = painter.viewport()
            size = pixmap.size()
            size.scale(rect.size(), Qt.KeepAspectRatio)

            painter.setViewport(
                rect.x(), rect.y(),
                size.width(), size.height()
            )
            painter.setWindow(pixmap.rect())
            painter.drawPixmap(0, 0, pixmap)
            painter.end()

    @pyqtSlot()
    def _copy(self):
        QGuiApplication.clipboard().setImage(self._image)

    from PyQt5.QtCore import pyqtSlot

    @pyqtSlot()
    def _paste(self):
        new_image = QGuiApplication.clipboard().image()
        if new_image.isNull():
            self.statusBar().showMessage("No image in clipboard")
        else:
            self._set_image(new_image)
            self.setWindowFilePath("")
            self._current_file = ""
            w = new_image.width()
            h = new_image.height()
            d = new_image.depth()
            message = f"Obtained image from clipboard, {w}x{h}, Depth: {d}"
            self.statusBar().showMessage(message)


    @pyqtSlot()
    def _zoom_in(self):
        self._scale_image(1.25)

    @pyqtSlot()
    def _zoom_out(self):
        self._scale_image(0.8)

    @pyqtSlot()
    def _normal_size(self):
        self._image_label.adjustSize()
        self._scale_factor = 1.0

    @pyqtSlot()
    def _fit_to_window(self):
        fit = self._fit_to_window_act.isChecked()
        self._scroll_area.setWidgetResizable(fit)
        if not fit:
            self._normal_size()
        self._update_actions()

    @pyqtSlot()
    def _about(self):
        QMessageBox.about(self, "About Image Viewer", ABOUT)

    def _create_actions(self):
        file_menu = self.menuBar().addMenu("&File")

        self._open_act = file_menu.addAction("&Open...")
        self._open_act.triggered.connect(self._open)
        self._open_act.setShortcut(QKeySequence.Open)

        self._save_as_act = file_menu.addAction("&Save As...")
        self._save_as_act.triggered.connect(self._save_as)
        self._save_as_act.setEnabled(False)

        self._print_act = file_menu.addAction("&Print...")
        self._print_act.triggered.connect(self._print_)
        self._print_act.setShortcut(QKeySequence.Print)
        self._print_act.setEnabled(False)

        file_menu.addSeparator()

        exit_act = file_menu.addAction("E&xit")
        exit_act.triggered.connect(self.close)
        exit_act.setShortcut("Ctrl+Q")

        edit_menu = self.menuBar().addMenu("&Edit")

        self._copy_act = edit_menu.addAction("&Copy")
        self._copy_act.triggered.connect(self._copy)
        self._copy_act.setShortcut(QKeySequence.Copy)
        self._copy_act.setEnabled(False)

        paste_act = edit_menu.addAction("&Paste")
        paste_act.triggered.connect(self._paste)
        paste_act.setShortcut(QKeySequence.Paste)

        view_menu = self.menuBar().addMenu("&View")

        self._zoom_in_act = view_menu.addAction("Zoom &In (25%)")
        self._zoom_in_act.triggered.connect(self._zoom_in)
        self._zoom_in_act.setShortcut(QKeySequence.ZoomIn)
        self._zoom_in_act.setEnabled(False)

        self._zoom_out_act = view_menu.addAction("Zoom &Out (25%)")
        self._zoom_out_act.triggered.connect(self._zoom_out)
        self._zoom_out_act.setShortcut(QKeySequence.ZoomOut)
        self._zoom_out_act.setEnabled(False)

        self._normal_size_act = view_menu.addAction("&Normal Size")
        self._normal_size_act.triggered.connect(self._normal_size)
        self._normal_size_act.setEnabled(False)

        view_menu.addSeparator()

        self._fit_to_window_act = view_menu.addAction("&Fit to Window")
        self._fit_to_window_act.setCheckable(True)
        self._fit_to_window_act.triggered.connect(self._fit_to_window)
        self._fit_to_window_act.setShortcut("Ctrl+F")
        self._fit_to_window_act.setEnabled(False)

        help_menu = self.menuBar().addMenu("&Help")

        about_act = help_menu.addAction("&About")
        about_act.triggered.connect(self._about)

        about_qt_act = help_menu.addAction("About &Qt")
        about_qt_act.triggered.connect(QApplication.aboutQt)

    def _update_actions(self):
        has_image = not self._image.isNull()
        self._save_as_act.setEnabled(has_image)
        self._copy_act.setEnabled(has_image)

        enable_zoom = not self._fit_to_window_act.isChecked()
        self._zoom_in_act.setEnabled(enable_zoom)
        self._zoom_out_act.setEnabled(enable_zoom)
        self._normal_size_act.setEnabled(enable_zoom)

    def _scale_image(self, factor):
        self._scale_factor *= factor
        self._image_label.resize(
            self._scale_factor * self._image_label.pixmap().size()
        )

        self._adjust_scrollbar(
            self._scroll_area.horizontalScrollBar(), factor
        )
        self._adjust_scrollbar(
            self._scroll_area.verticalScrollBar(), factor
        )

        self._zoom_in_act.setEnabled(self._scale_factor < 3.0)
        self._zoom_out_act.setEnabled(self._scale_factor > 0.333)

    def _adjust_scrollbar(self, scrollBar, factor):
        scrollBar.setValue(
            int(
                factor * scrollBar.value()
                + ((factor - 1) * scrollBar.pageStep() / 2)
            )
        )

    def _initialize_image_filedialog(self, dialog, acceptMode):
        if self._first_file_dialog:
            self._first_file_dialog = False
            locations = QStandardPaths.standardLocations(
                QStandardPaths.PicturesLocation
            )
            dialog.setDirectory(
                locations[-1] if locations else QDir.currentPath()
            )

        mime_types = [
            bytes(m).decode("utf-8")
            for m in QImageWriter.supportedMimeTypes()
        ]
        mime_types.sort()

        dialog.setMimeTypeFilters(mime_types)
        dialog.selectMimeTypeFilter("image/jpeg")
        dialog.setAcceptMode(acceptMode)

        if acceptMode == QFileDialog.AcceptSave:
            dialog.setDefaultSuffix("jpg")

    def _save_info(self):
        """Save description and image path to info.xls (CSV formatted)."""
        desc = self._description_edit.toPlainText().strip()
        img_path = getattr(self, '_current_file', '') or self.windowFilePath() or ''
        info_path = os.path.join(self._project_root, 'info.xls')
        # load existing rows (if any)
        rows = []
        header = ['index', 'path', 'description']
        try:
            if os.path.exists(info_path):
                with open(info_path, 'r', newline='', encoding='utf-8') as f:
                    reader = list(csv.reader(f))
                    if reader:
                        header = reader[0]
                        rows = reader[1:]
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Cannot read {info_path}: {e}')
            return

        # search for existing entry for this image
        found = False
        for r in rows:
            if len(r) < 2:
                continue
            existing_path = r[1]
            if self._paths_match(existing_path, img_path):
                # update description
                # ensure row has at least 3 columns
                while len(r) < 3:
                    r.append('')
                r[2] = desc
                found = True
                break

        try:
            if found:
                # rewrite whole file with updated rows
                with open(info_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                    for i, r in enumerate(rows, start=1):
                        # ensure index column is present and reasonable
                        if len(r) >= 1 and r[0].strip():
                            idx = r[0]
                        else:
                            idx = i
                        row_to_write = [idx] + r[1:]
                        writer.writerow(row_to_write)
            else:
                # append new row, compute next index
                next_index = 1
                if rows:
                    try:
                        existing_indexes = [int(r[0]) for r in rows if r and r[0].isdigit()]
                        if existing_indexes:
                            next_index = max(existing_indexes) + 1
                        else:
                            next_index = len(rows) + 1
                    except Exception:
                        next_index = len(rows) + 1

                # if file didn't exist, create and write header first
                write_header = not os.path.exists(info_path)
                mode = 'a'
                with open(info_path, mode, newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    if write_header:
                        writer.writerow(header)
                    writer.writerow([next_index, img_path, desc])
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Cannot write to {info_path}: {e}')
            return

        self.statusBar().showMessage(f'Записано в {info_path}')
        self._description_edit.clear()

    def _choose_source_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select source directory", self._project_root)
        if d:
            self._src_lineedit.setText(d)
            if not self._dst_lineedit.text().strip():
                self._dst_lineedit.setText(d)

    def _choose_dest_dir(self):
        start = self._src_lineedit.text().strip() or self._project_root
        d = QFileDialog.getExistingDirectory(self, "Select destination directory", start)
        if d:
            self._dst_lineedit.setText(d)

    def _create_dataset(self):
        desc = self._mass_description.toPlainText().strip()
        if not desc:
            QMessageBox.information(self, 'No description', 'No description')
            return

        src = self._src_lineedit.text().strip()
        dst = self._dst_lineedit.text().strip() or src

        if not src or not os.path.isdir(src):
            QMessageBox.information(self, 'Error', 'Source directory is not valid')
            return

        try:
            copied_files = self._copy_dir_contents(src, dst)
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Copy failed: {e}')
            return

        # append info.xls with one row per image (path relative to Images folder)
        info_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'info.xls')
        rows = []
        header = ['index', 'path', 'description']
        try:
            if os.path.exists(info_path):
                with open(info_path, 'r', newline='', encoding='utf-8') as f:
                    reader = list(csv.reader(f))
                    if reader:
                        header = reader[0]
                        rows = reader[1:]
        except Exception:
            pass

        # only process files that were actually copied in this operation
        image_files = copied_files if copied_files is not None else []

        if not image_files:
            QMessageBox.information(self, 'No images', 'No image files found in the destination')
            return

        # determine starting index
        next_index = 1
        if rows:
            try:
                existing_indexes = [int(r[0]) for r in rows if r and r[0].isdigit()]
                if existing_indexes:
                    next_index = max(existing_indexes) + 1
                else:
                    next_index = len(rows) + 1
            except Exception:
                next_index = len(rows) + 1

        images_root = os.path.join(self._project_root, 'Images')
        # Append a new row for each image (do not check for existing similar images)
        write_header = not os.path.exists(info_path)
        try:
            with open(info_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(header)
                for img in image_files:
                    try:
                        rel = os.path.relpath(img, images_root).replace('\\', '/')
                    except Exception:
                        rel = os.path.relpath(img, self._project_root).replace('\\', '/')
                    writer.writerow([next_index, rel, desc])
                    next_index += 1
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Cannot write to {info_path}: {e}')
            return

        QMessageBox.information(self, 'Success', f'Dataset created at {dst}')
        self._mass_description.clear()

    def _copy_dir_contents(self, src, dst):
        os.makedirs(dst, exist_ok=True)
        copied = []
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            target_root = os.path.join(dst, rel) if rel != '.' else dst
            os.makedirs(target_root, exist_ok=True)
            for f in files:
                s = os.path.join(root, f)
                t = os.path.join(target_root, f)
                # if target exists, generate a unique filename by appending _1, _2, ...
                if os.path.exists(t):
                    name, ext = os.path.splitext(f)
                    counter = 1
                    while True:
                        new_name = f"{name}_{counter}{ext}"
                        t2 = os.path.join(target_root, new_name)
                        if not os.path.exists(t2):
                            t = t2
                            break
                        counter += 1
                shutil.copy2(s, t)
                copied.append(t)
        return copied

    def _paths_match(self, a: str, b: str) -> bool:
        """Return True if paths a and b refer to the same image.

        Attempts absolute normalized comparison first, then falls back to
        (no fallback to basename to avoid incorrect matches).
        """
        if not a or not b:
            return False
        try:
            # resolve relative stored paths relative to project Images folder
            def resolve(p):
                if not p:
                    return p
                if os.path.isabs(p):
                    return os.path.abspath(p)
                # treat relative stored paths as relative to project Images
                imgs_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Images')
                return os.path.abspath(os.path.join(imgs_root, p))

            a_abs = resolve(a)
            b_abs = resolve(b)
        except Exception:
            a_abs = a
            b_abs = b

        try:
            if os.path.normcase(a_abs) == os.path.normcase(b_abs):
                return True
        except Exception:
            pass
        return False

    def _load_description_for_current_file(self):
        """Load description from info.xls for the current image, if present."""
        info_path = os.path.join(os.getcwd(), 'info.xls')
        if not os.path.exists(info_path):
            # nothing to load
            self._description_edit.clear()
            return

        try:
            with open(info_path, 'r', newline='', encoding='utf-8') as f:
                reader = list(csv.reader(f))
        except Exception:
            # ignore read errors
            return

        if not reader or len(reader) < 2:
            self._description_edit.clear()
            return

        img_path = getattr(self, '_current_file', '') or self.windowFilePath() or ''
        for row in reader[1:]:
            if len(row) < 3:
                continue
            row_path = row[1]
            if self._paths_match(row_path, img_path):
                self._description_edit.setPlainText(row[2])
                return

        self._description_edit.clear()
