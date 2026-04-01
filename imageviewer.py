from __future__ import annotations
import os
import csv
import shutil
import subprocess
import sys
import json

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

        # Viewer tab: contains a toggle and the viewer (scroll area)
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
        # Search row: input + button
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Поиск по описанию...")
        self._search_btn = QPushButton("Поиск")
        self._search_btn.clicked.connect(self._search_by_description)
        search_row.addWidget(self._search_input)
        search_row.addWidget(self._search_btn)
        tab2_layout.addLayout(search_row)
        # Path search row: input + button
        search_path_row = QHBoxLayout()
        self._search_path_input = QLineEdit()
        self._search_path_input.setPlaceholderText("Поиск по пути (абсолютный или относительный от Images)")
        self._search_path_btn = QPushButton("Поиск по пути")
        self._search_path_btn.clicked.connect(self._search_by_path)
        search_path_row.addWidget(self._search_path_input)
        search_path_row.addWidget(self._search_path_btn)
        tab2_layout.addLayout(search_path_row)
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

        # (No description field here; Mass Processing only needs
        # source/destination selectors and the Create button.)

        # Augmentation methods selector (scrollable list of checkboxes)
        aug_label = QLabel("Available augmentations:")
        tab3_layout.addWidget(aug_label)

        self._aug_scroll = QScrollArea()
        self._aug_scroll.setWidgetResizable(True)
        aug_container = QWidget()
        self._aug_layout = QVBoxLayout()
        aug_container.setLayout(self._aug_layout)
        self._aug_scroll.setWidget(aug_container)
        # set a reasonable max height so many options can be scrolled
        self._aug_scroll.setFixedHeight(220)
        tab3_layout.addWidget(self._aug_scroll)

        # Placeholder: dynamically load available augmentations from package
        # For now, populate with a stub list of methods
        self._aug_checkboxes = []
        def _load_placeholder_methods(n=10):
            methods = []
            for i in range(1, n + 1):
                methods.append((f"method_{i}", f"Method {i}", f"Description for method {i}"))
            return methods

        self._available_methods = _load_placeholder_methods(12)
        for mid, name, descr in self._available_methods:
            cb = QCheckBox(f"{name}: {descr}")
            cb.setObjectName(mid)
            self._aug_layout.addWidget(cb)
            self._aug_checkboxes.append(cb)

        # spacer below checkbox list
        self._aug_layout.addStretch()

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

        # try to load existing description from info.csv
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
        """Save description and image path to info.csv (CSV formatted).

        Copies the current image into the project's Images folder (if not
        already there) and writes the path relative to Images into info.xls.
        """
        desc = self._description_edit.toPlainText().strip()
        img_path = getattr(self, '_current_file', '') or self.windowFilePath() or ''

        if not img_path or not os.path.exists(img_path):
            QMessageBox.information(self, 'Error', 'No image to save')
            return

        images_root = os.path.join(self._project_root, 'Images')
        os.makedirs(images_root, exist_ok=True)

        # determine destination path inside Images; if already inside Images, keep it
        try:
            img_abs = os.path.abspath(img_path)
            imgs_abs = os.path.abspath(images_root)
            inside_images = False
            try:
                inside_images = (os.path.commonpath([img_abs, imgs_abs]) == imgs_abs)
            except ValueError:
                # different drives on Windows -> not inside Images
                inside_images = False

            base = os.path.basename(img_abs)
            dest = os.path.join(images_root, base)
            # If image already is inside Images folder, keep it; otherwise, we'll copy later if needed
            if inside_images:
                dest = img_abs
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Copy failed: {e}')
            return
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Copy failed: {e}')
            return

        # path to store in CSV: relative to Images folder
        try:
            rel_path = os.path.relpath(dest, images_root).replace('\\', '/')
        except Exception:
            rel_path = os.path.basename(dest)

        info_path = os.path.join(self._project_root, 'info.csv')

        # helper: check whether rel_path exists in info.csv
        def _image_in_info(rel):
            if not os.path.exists(info_path):
                return False
            try:
                with open(info_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f, delimiter=';')
                    rows = list(reader)
            except Exception:
                return False
            for r in rows[1:]:
                if len(r) >= 2 and r[1] == rel:
                    return True
            return False

        def _update_description(rel, new_desc):
            # read, update matching row, write back
            try:
                rows = []
                with open(info_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f, delimiter=';')
                    rows = list(reader)
            except Exception:
                return False
            header = rows[0] if rows else ['index', 'path', 'description']
            updated = False
            for i in range(1, len(rows)):
                if len(rows[i]) >= 2 and rows[i][1] == rel:
                    while len(rows[i]) < 3:
                        rows[i].append('')
                    rows[i][2] = new_desc
                    updated = True
                    break
            if updated:
                try:
                    with open(info_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f, delimiter=';')
                        writer.writerow(header)
                        for r in rows[1:]:
                            # handle missing index
                            if r and str(r[0]).strip():
                                idx = r[0]
                            else:
                                idx = ''
                            row_to_write = [idx] + r[1:]
                            writer.writerow(row_to_write)
                    return True
                except Exception:
                    return False
            return False

        exists = _image_in_info(rel_path)

        try:
            if exists:
                # update description only
                ok = _update_description(rel_path, desc)
                if not ok:
                    QMessageBox.information(self, 'Error', f'Не удалось обновить {info_path}')
                    return
            else:
                # copy image into Images (may overwrite existing file of same name)
                try:
                    if not inside_images:
                        shutil.copy2(img_abs, dest)
                except Exception as e:
                    QMessageBox.information(self, 'Error', f'Copy failed: {e}')
                    return

                # append new row
                rows = []
                header = ['index', 'path', 'description']
                if os.path.exists(info_path):
                    try:
                        with open(info_path, 'r', newline='', encoding='utf-8') as f:
                            reader = csv.reader(f, delimiter=';')
                            rows = list(reader)
                            if rows:
                                header = rows[0]
                    except Exception:
                        rows = []

                next_index = 1
                if rows and len(rows) > 1:
                    try:
                        existing_indexes = [int(r[0]) for r in rows[1:] if r and str(r[0]).isdigit()]
                        if existing_indexes:
                            next_index = max(existing_indexes) + 1
                        else:
                            next_index = len(rows)
                    except Exception:
                        next_index = len(rows)

                write_header = not os.path.exists(info_path)
                try:
                    with open(info_path, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f, delimiter=';')
                        if write_header:
                            writer.writerow(header)
                        writer.writerow([next_index, rel_path, desc])
                except Exception as e:
                    QMessageBox.information(self, 'Error', f'Cannot write to {info_path}: {e}')
                    return
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Ошибка при обновлении info: {e}')
            return

        self.statusBar().showMessage(f'Записано в {info_path}')
        self._description_edit.clear()

    @pyqtSlot()
    def _search_by_description(self):
        query = self._search_input.text().strip()
        if not query:
            QMessageBox.information(self, 'Error', 'Введите текст для поиска')
            return

        # call the top-level Find_image.py script and parse JSON output
        script = os.path.join(self._project_root, 'Find_image.py')
        if not os.path.exists(script):
            QMessageBox.information(self, 'Error', f'Не найден {script}')
            return

        try:
            proc = subprocess.run([sys.executable, script, query], cwd=self._project_root,
                                  capture_output=True, text=True, timeout=30)
            out = proc.stdout.strip()
            try:
                paths = json.loads(out) if out else []
            except Exception:
                paths = []
            # debug prints
            print(f"DEBUG: subprocess returncode={proc.returncode}")
            print("DEBUG: subprocess stdout:")
            print(out)
            print("DEBUG: subprocess stderr:")
            print(proc.stderr)
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Ошибка поиска: {e}')
            return

        if not paths:
            QMessageBox.information(self, 'Ничего не найдено', 'Ничего не найдено. Попробуй изменить запрос')
            return

        # open first result
        path = paths[0]
        if not os.path.exists(path):
            QMessageBox.information(self, 'Error', f'Файл не найден: {path}')
            return

        self.load_file(path)

    @pyqtSlot()
    def _search_by_path(self):
        raw = self._search_path_input.text().strip()
        if not raw:
            QMessageBox.information(self, 'Error', 'Введите путь для поиска')
            return

        # normalize
        candidate = os.path.expanduser(raw)
        candidate = os.path.normpath(candidate)

        candidates = []
        # absolute
        if os.path.isabs(candidate):
            candidates.append(candidate)
        else:
            # direct relative to project
            candidates.append(os.path.join(self._project_root, candidate))
            # relative inside Images folder
            candidates.append(os.path.join(self._project_root, 'Images', candidate))
            # also try if user provided a path starting with 'Images' already
            if candidate.lower().startswith('images' + os.sep.lower()):
                candidates.append(os.path.join(self._project_root, candidate[len('Images'+os.sep):]))

        found = None
        for p in candidates:
            try:
                if os.path.exists(p) and os.path.isfile(p):
                    found = p
                    break
            except Exception:
                continue

        if not found:
            QMessageBox.information(self, 'Ничего не найдено', 'Ничего не найдено. Попробуйте еще раз')
            return

        self.load_file(found)

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

        # only process files that were actually copied in this operation
        image_files = copied_files if copied_files is not None else []

        if not image_files:
            QMessageBox.information(self, 'No images', 'No image files found in the destination')
            return

        # determine which augmentation methods are selected
        selected_methods = [cb.objectName() for cb in getattr(self, '_aug_checkboxes', []) if cb.isChecked()]

        # if any method selected, simulate augmentation by duplicating files
        augmented_files = []
        if selected_methods:
            for img in list(image_files):
                base_dir = os.path.dirname(img)
                fname = os.path.basename(img)
                name, ext = os.path.splitext(fname)
                for m in selected_methods:
                    new_name = f"{name}_{m}{ext}"
                    target = os.path.join(base_dir, new_name)
                    # avoid clobbering existing files by adding numeric suffix
                    if os.path.exists(target):
                        counter = 1
                        while True:
                            alt = os.path.join(base_dir, f"{name}_{m}_{counter}{ext}")
                            if not os.path.exists(alt):
                                target = alt
                                break
                            counter += 1
                    try:
                        shutil.copy2(img, target)
                        augmented_files.append(target)
                    except Exception:
                        # non-fatal: skip augmentation if copy fails
                        continue

        # include augmented files in the set for reporting
        if augmented_files:
            image_files = image_files + augmented_files

        QMessageBox.information(self, 'Success', f'Dataset created at {dst} (files: {len(image_files)}, augmented: {len(augmented_files)})')

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
        """Load description from info.csv for the current image, if present."""
        info_path = os.path.join(self._project_root, 'info.csv')
        if not os.path.exists(info_path):
            # nothing to load
            self._description_edit.clear()
            return

        try:
            with open(info_path, 'r', newline='', encoding='utf-8') as f:
                reader = list(csv.reader(f, delimiter=';'))
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
