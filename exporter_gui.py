#!/usr/bin/env python3
"""
===============================================================================
 KingAI TunerPro XDF + BIN Universal Exporter - PySide6 Qt GUI
===============================================================================

 Author:       Jason King
 GitHub:       https://github.com/KingAiCodeForge
 Email:        jason.king@kingai.com.au

 Company:      KingAi PTY LTD
 Website:      kingai.com.au

 Enhancements v3.2:
  - Drag & drop support for XDF and BIN files
  - Recent files history (last 10 XDF/BIN pairs)
  - Batch processing mode (multiple BIN files with same XDF)
  - Category filter (export specific categories only)
  - Auto-detect matching BIN when XDF selected
  - Quick access buttons for TunerPro Files directory
  - Preview mode (show element count before export)
  - CSV export format added
  - Open output folder after export option
  - Keyboard shortcuts

===============================================================================
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

# Check for PySide6 before importing
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit, QCheckBox, QGroupBox, QFileDialog,
        QTextEdit, QProgressBar, QMessageBox, QStatusBar, QFrame, QSpacerItem,
        QSizePolicy, QComboBox, QListWidget, QListWidgetItem, QSplitter,
        QTabWidget, QMenu, QToolButton, QToolBar, QDockWidget, QAbstractItemView
    )
    from PySide6.QtCore import Qt, QThread, Signal, QSize, QSettings, QUrl, QMimeData
    from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QDragEnterEvent, QDropEvent, QKeySequence, QShortcut, QAction
except ImportError:
    print("=" * 60)
    print(" ERROR: PySide6 is not installed!")
    print("=" * 60)
    print()
    print(" Please install PySide6 using:")
    print("   pip install PySide6")
    print()
    print(" Or run the installer:")
    print("   install.bat")
    print()
    print("=" * 60)
    sys.exit(1)

# Import the core exporter
try:
    from tunerpro_exporter import UniversalXDFExporter
except ImportError:
    # Try to find it in the same directory
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir))
    try:
        from tunerpro_exporter import UniversalXDFExporter
    except ImportError:
        print("ERROR: Could not import tunerpro_exporter.py")
        print("       Make sure it's in the same directory as this GUI.")
        sys.exit(1)


__version__ = "3.2.0"
__author__ = "Jason King"
__author_github__ = "KingAiCodeForge"
__author_alias__ = "kingaustraliagg"  # PCMHacking forum username

# Default paths for quick access (fallback list if user hasn't set custom path)
DEFAULT_TUNERPRO_PATHS = [
    Path(r"E:\Users\jason\Documents\TunerPro Files"),
    Path(r"C:\Users\jason\OneDrive\Documents\TunerPro Files"),
    Path.home() / "Documents" / "TunerPro Files",
]

# Settings keys
SETTINGS_KEY_DEFAULT_PATH = "default_tunerpro_path"

# Recent files settings
MAX_RECENT_FILES = 10
SETTINGS_ORG = "KingAI"
SETTINGS_APP = "TunerProExporter"


class ExportWorker(QThread):
    """Background worker thread for export operations"""
    
    progress = Signal(str)  # Progress message
    finished = Signal(bool, str, list)  # Success flag, message, output files
    element_count = Signal(int, int, int)  # constants, flags, tables
    
    def __init__(self, xdf_path: str, bin_path: str, output_path: str, formats: list):
        super().__init__()
        self.xdf_path = xdf_path
        self.bin_path = bin_path
        self.output_path = output_path
        self.formats = formats
        self.output_files = []
    
    def run(self):
        """Execute the export operation"""
        try:
            self.progress.emit("Loading XDF definition...")
            exporter = UniversalXDFExporter(self.xdf_path, self.bin_path)
            
            self.progress.emit("Validating binary file...")
            if not exporter.validate_bin_file():
                self.finished.emit(False, f"Binary validation failed!\n\nCould not read: {self.bin_path}", [])
                return
            
            self.progress.emit("Parsing XDF structure...")
            if not exporter.parse_xdf():
                self.finished.emit(False, f"XDF parsing failed!\n\nCould not parse: {self.xdf_path}", [])
                return
            
            # Emit element counts for preview
            self.element_count.emit(
                len(exporter.elements['constants']),
                len(exporter.elements['flags']),
                len(exporter.elements['tables'])
            )
            
            self.output_files = []
            
            for fmt in self.formats:
                self.progress.emit(f"Exporting to {fmt.upper()} format...")
                
                # Determine output filename
                output_base = Path(self.output_path)
                if output_base.suffix.lower() in ['.txt', '.json', '.md', '.text', '.test', '.csv']:
                    output_file = str(output_base.with_suffix(f'.{fmt}'))
                else:
                    output_file = f"{self.output_path}.{fmt}"
                
                if fmt in ['txt', 'text', 'test']:
                    exporter.export_to_text(output_file)
                elif fmt == 'json':
                    exporter.export_to_json(output_file)
                elif fmt == 'md':
                    exporter.export_to_markdown(output_file)
                elif fmt == 'csv':
                    # Export to CSV format
                    self._export_csv(exporter, output_file)
                
                self.output_files.append(output_file)
            
            files_str = ", ".join([Path(f).name for f in self.output_files])
            self.finished.emit(True, f"Export complete!\n\nCreated: {files_str}", self.output_files)
        
        except Exception as e:
            self.finished.emit(False, f"Export failed!\n\nError: {str(e)}", [])
    
    def _export_csv(self, exporter, output_file: str):
        """Export to CSV format for spreadsheet analysis"""
        import csv
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Type', 'Category', 'Title', 'Address', 'Value', 'Units', 'Description'])
            
            for const in exporter.elements['constants']:
                writer.writerow([
                    'Constant',
                    const.get('category', 'Uncategorized'),
                    const.get('title', 'Unknown'),
                    f"0x{const.get('address', 0):X}",
                    const.get('value', ''),
                    const.get('units', ''),
                    const.get('description', '')[:100]
                ])
            
            for flag in exporter.elements['flags']:
                writer.writerow([
                    'Flag',
                    flag.get('category', 'Uncategorized'),
                    flag.get('title', 'Unknown'),
                    f"0x{flag.get('address', 0):X}",
                    'Set' if flag.get('value', False) else 'Not Set',
                    '',
                    flag.get('description', '')[:100]
                ])
            
            for table in exporter.elements['tables']:
                writer.writerow([
                    'Table',
                    table.get('category', 'Uncategorized'),
                    table.get('title', 'Unknown'),
                    f"0x{table.get('address', 0):X}",
                    f"{table.get('rows', 0)}x{table.get('cols', 0)}",
                    table.get('units', ''),
                    table.get('description', '')[:100]
                ])


class TunerProExporterGUI(QMainWindow):
    """Main GUI window for the TunerPro XDF+BIN Exporter with enhanced features"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self.recent_files = []
        self.last_output_files = []
        self.element_counts = (0, 0, 0)  # constants, flags, tables
        self._load_recent_files()
        self.init_ui()
        self._setup_shortcuts()
        
        # Enable drag and drop
        self.setAcceptDrops(True)
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle(f"KingAI TunerPro Exporter v{__version__}")
        self.setMinimumSize(700, 550)
        self.resize(750, 600)
        
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title header
        title_frame = self._create_title_frame()
        main_layout.addWidget(title_frame)
        
        # File selection group
        file_group = self._create_file_selection_group()
        main_layout.addWidget(file_group)
        
        # Output settings group
        output_group = self._create_output_settings_group()
        main_layout.addWidget(output_group)
        
        # Format selection group
        format_group = self._create_format_selection_group()
        main_layout.addWidget(format_group)
        
        # Export button
        self.export_btn = QPushButton("  Export  ")
        self.export_btn.setMinimumHeight(45)
        self.export_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.export_btn.clicked.connect(self.start_export)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 30px;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
            QPushButton:pressed {
                background-color: #1b5e20;
            }
            QPushButton:disabled {
                background-color: #9e9e9e;
            }
        """)
        main_layout.addWidget(self.export_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(0)  # Indeterminate mode
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Log output
        log_group = QGroupBox("Output Log")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(120)
        self.log_output.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_output)
        main_layout.addWidget(log_group)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Select XDF and BIN files to begin")
        
        # Apply dark theme
        self._apply_theme()
        
        self.log("KingAI TunerPro Exporter v" + __version__)
        self.log("Author: Jason King (kingaustraliagg)")
        self.log("Ready to export XDF + BIN to multiple formats")
    
    def _create_title_frame(self) -> QFrame:
        """Create the title header frame"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1e3a5f;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(frame)
        
        title = QLabel("KingAI TunerPro XDF + BIN Exporter")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        subtitle = QLabel("Universal Export Tool - TXT, JSON, Markdown")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #b0bec5;")
        layout.addWidget(subtitle)
        
        author = QLabel("by Jason King (kingaustraliagg) • kingai.com.au")
        author.setFont(QFont("Segoe UI", 9))
        author.setAlignment(Qt.AlignCenter)
        author.setStyleSheet("color: #78909c;")
        layout.addWidget(author)
        
        # Settings button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setFixedWidth(100)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #37474f;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #455a64;
            }
        """)
        settings_btn.clicked.connect(self._show_settings_dialog)
        btn_layout.addWidget(settings_btn)
        
        quick_btn = QPushButton("📁 Quick Open")
        quick_btn.setFixedWidth(100)
        quick_btn.setStyleSheet("""
            QPushButton {
                background-color: #37474f;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #455a64;
            }
        """)
        quick_btn.clicked.connect(self._open_default_folder)
        btn_layout.addWidget(quick_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return frame
    
    def _create_file_selection_group(self) -> QGroupBox:
        """Create the file selection group"""
        group = QGroupBox("Input Files")
        layout = QVBoxLayout(group)
        
        # XDF file row
        xdf_layout = QHBoxLayout()
        xdf_label = QLabel("XDF Definition:")
        xdf_label.setMinimumWidth(100)
        self.xdf_input = QLineEdit()
        self.xdf_input.setPlaceholderText("Select XDF definition file...")
        xdf_btn = QPushButton("Browse...")
        xdf_btn.setMinimumWidth(100)
        xdf_btn.clicked.connect(self.browse_xdf)
        xdf_layout.addWidget(xdf_label)
        xdf_layout.addWidget(self.xdf_input)
        xdf_layout.addWidget(xdf_btn)
        layout.addLayout(xdf_layout)
        
        # BIN file row
        bin_layout = QHBoxLayout()
        bin_label = QLabel("BIN Firmware:")
        bin_label.setMinimumWidth(100)
        self.bin_input = QLineEdit()
        self.bin_input.setPlaceholderText("Select BIN firmware file...")
        bin_btn = QPushButton("Browse...")
        bin_btn.setMinimumWidth(100)
        bin_btn.clicked.connect(self.browse_bin)
        bin_layout.addWidget(bin_label)
        bin_layout.addWidget(self.bin_input)
        bin_layout.addWidget(bin_btn)
        layout.addLayout(bin_layout)
        
        return group
    
    def _create_output_settings_group(self) -> QGroupBox:
        """Create the output settings group"""
        group = QGroupBox("Output Settings")
        layout = QVBoxLayout(group)
        
        # Output folder row
        folder_layout = QHBoxLayout()
        folder_label = QLabel("Output Folder:")
        folder_label.setMinimumWidth(100)
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select output folder...")
        folder_btn = QPushButton("Browse...")
        folder_btn.setMinimumWidth(100)
        folder_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(folder_label)
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(folder_btn)
        layout.addLayout(folder_layout)
        
        # Output filename row
        name_layout = QHBoxLayout()
        name_label = QLabel("Output Name:")
        name_label.setMinimumWidth(100)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter output filename (without extension)...")
        self.name_input.setText("export")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        return group
    
    def _create_format_selection_group(self) -> QGroupBox:
        """Create the format selection group"""
        group = QGroupBox("Export Formats (select one or more)")
        layout = QHBoxLayout(group)
        
        # Checkbox for each format
        self.fmt_txt = QCheckBox("TXT (TunerPro)")
        self.fmt_txt.setChecked(True)
        self.fmt_txt.setToolTip("Standard TunerPro text export format")
        
        self.fmt_json = QCheckBox("JSON (Data)")
        self.fmt_json.setToolTip("Structured JSON for programmatic access")
        
        self.fmt_md = QCheckBox("MD (Docs)")
        self.fmt_md.setToolTip("Markdown documentation format")
        
        self.fmt_csv = QCheckBox("CSV (Spreadsheet)")
        self.fmt_csv.setToolTip("CSV format for Excel/Sheets analysis")
        
        self.fmt_test = QCheckBox("TEST")
        self.fmt_test.setToolTip("Alternate text format for testing")
        
        layout.addWidget(self.fmt_txt)
        layout.addWidget(self.fmt_json)
        layout.addWidget(self.fmt_md)
        layout.addWidget(self.fmt_csv)
        layout.addWidget(self.fmt_test)
        layout.addStretch()
        
        return group
    
    def _apply_theme(self):
        """Apply dark theme to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #424242;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #424242;
                border-radius: 4px;
                padding: 8px;
                color: #e0e0e0;
            }
            QLineEdit:focus {
                border: 1px solid #4fc3f7;
            }
            QPushButton {
                background-color: #424242;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #616161;
            }
            QPushButton:pressed {
                background-color: #757575;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #424242;
                border-radius: 4px;
                padding: 5px;
            }
            QProgressBar {
                border: 1px solid #424242;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4fc3f7;
            }
            QStatusBar {
                background-color: #2d2d2d;
                color: #9e9e9e;
            }
        """)
    
    def log(self, message: str):
        """Add a message to the log output"""
        self.log_output.append(message)
    
    def browse_xdf(self):
        """Open file dialog to select XDF file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select XDF Definition File",
            "",
            "XDF Files (*.xdf);;All Files (*.*)"
        )
        if file_path:
            self.xdf_input.setText(file_path)
            self.log(f"Selected XDF: {Path(file_path).name}")
            
            # Auto-set output folder if not set
            if not self.folder_input.text():
                self.folder_input.setText(str(Path(file_path).parent))
    
    def browse_bin(self):
        """Open file dialog to select BIN file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select BIN Firmware File",
            "",
            "BIN Files (*.bin);;All Files (*.*)"
        )
        if file_path:
            self.bin_input.setText(file_path)
            self.log(f"Selected BIN: {Path(file_path).name}")
            
            # Auto-set output name based on BIN filename
            if self.name_input.text() == "export":
                self.name_input.setText(Path(file_path).stem + "_export")
    
    def browse_folder(self):
        """Open folder dialog to select output folder"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            ""
        )
        if folder_path:
            self.folder_input.setText(folder_path)
            self.log(f"Output folder: {folder_path}")
    
    def validate_inputs(self) -> tuple:
        """Validate all inputs before export"""
        errors = []
        
        # Check XDF file
        xdf_path = self.xdf_input.text().strip()
        if not xdf_path:
            errors.append("XDF definition file is required")
        elif not Path(xdf_path).exists():
            errors.append(f"XDF file not found: {xdf_path}")
        
        # Check BIN file
        bin_path = self.bin_input.text().strip()
        if not bin_path:
            errors.append("BIN firmware file is required")
        elif not Path(bin_path).exists():
            errors.append(f"BIN file not found: {bin_path}")
        
        # Check output folder
        folder_path = self.folder_input.text().strip()
        if not folder_path:
            errors.append("Output folder is required")
        elif not Path(folder_path).exists():
            errors.append(f"Output folder not found: {folder_path}")
        
        # Check output name
        output_name = self.name_input.text().strip()
        if not output_name:
            errors.append("Output filename is required")
        
        # Check at least one format selected
        formats = self.get_selected_formats()
        if not formats:
            errors.append("At least one export format must be selected")
        
        return len(errors) == 0, errors
    
    def get_selected_formats(self) -> list:
        """Get list of selected export formats"""
        formats = []
        if self.fmt_txt.isChecked():
            formats.append('txt')
        if self.fmt_json.isChecked():
            formats.append('json')
        if self.fmt_md.isChecked():
            formats.append('md')
        if self.fmt_csv.isChecked():
            formats.append('csv')
        if self.fmt_test.isChecked():
            formats.append('text')  # Use 'text' internally for test format
        return formats
    
    def start_export(self):
        """Start the export operation"""
        # Validate inputs
        valid, errors = self.validate_inputs()
        if not valid:
            QMessageBox.warning(
                self,
                "Validation Error",
                "\n".join(errors)
            )
            return
        
        # Gather parameters
        xdf_path = self.xdf_input.text().strip()
        bin_path = self.bin_input.text().strip()
        output_folder = self.folder_input.text().strip()
        output_name = self.name_input.text().strip()
        output_path = str(Path(output_folder) / output_name)
        formats = self.get_selected_formats()
        
        # Disable UI during export
        self.export_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("Exporting...")
        
        self.log("")
        self.log("=" * 50)
        self.log(f"Starting export...")
        self.log(f"XDF: {Path(xdf_path).name}")
        self.log(f"BIN: {Path(bin_path).name}")
        self.log(f"Formats: {', '.join(formats)}")
        
        # Start worker thread
        self.worker = ExportWorker(xdf_path, bin_path, output_path, formats)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.element_count.connect(self.on_element_count)
        self.worker.start()
    
    def on_progress(self, message: str):
        """Handle progress updates from worker"""
        self.log(message)
        self.status_bar.showMessage(message)
    
    def on_element_count(self, constants: int, flags: int, tables: int):
        """Handle element count updates"""
        self.element_counts = (constants, flags, tables)
        self.log(f"Found: {constants} constants, {flags} flags, {tables} tables")
    
    def on_finished(self, success: bool, message: str, output_files: list):
        """Handle export completion"""
        self.export_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.last_output_files = output_files
        
        if success:
            # Save to recent files
            xdf_path = self.xdf_input.text().strip()
            bin_path = self.bin_input.text().strip()
            self._add_recent_file(xdf_path, bin_path)
            
            self.status_bar.showMessage("Export complete!")
            self.log("=" * 50)
            self.log("✓ Export completed successfully!")
            
            # Ask to open output folder
            reply = QMessageBox.question(
                self,
                "Export Complete",
                f"{message}\n\nOpen output folder?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self._open_output_folder()
        else:
            self.status_bar.showMessage("Export failed!")
            self.log("=" * 50)
            self.log("✗ Export failed!")
            self.log(message)
            QMessageBox.critical(self, "Export Failed", message)
    
    # ========================================================================
    # DRAG AND DROP SUPPORT
    # ========================================================================
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event for file drops"""
        if event.mimeData().hasUrls():
            # Check if any dropped file is XDF or BIN
            for url in event.mimeData().urls():
                file_path = url.toLocalFile().lower()
                if file_path.endswith('.xdf') or file_path.endswith('.bin'):
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        """Handle file drop event"""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            lower_path = file_path.lower()
            
            if lower_path.endswith('.xdf'):
                self.xdf_input.setText(file_path)
                self.log(f"Dropped XDF: {Path(file_path).name}")
                self._auto_find_matching_bin(file_path)
                
                # Auto-set output folder
                if not self.folder_input.text():
                    self.folder_input.setText(str(Path(file_path).parent))
                    
            elif lower_path.endswith('.bin'):
                self.bin_input.setText(file_path)
                self.log(f"Dropped BIN: {Path(file_path).name}")
                
                # Auto-set output name
                if self.name_input.text() == "export":
                    self.name_input.setText(Path(file_path).stem + "_export")
        
        event.acceptProposedAction()
    
    # ========================================================================
    # KEYBOARD SHORTCUTS
    # ========================================================================
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Ctrl+O - Open XDF
        shortcut_xdf = QShortcut(QKeySequence("Ctrl+O"), self)
        shortcut_xdf.activated.connect(self.browse_xdf)
        
        # Ctrl+B - Open BIN
        shortcut_bin = QShortcut(QKeySequence("Ctrl+B"), self)
        shortcut_bin.activated.connect(self.browse_bin)
        
        # Ctrl+E or Enter - Export
        shortcut_export = QShortcut(QKeySequence("Ctrl+E"), self)
        shortcut_export.activated.connect(self.start_export)
        
        # Ctrl+D - Open default TunerPro folder
        shortcut_default = QShortcut(QKeySequence("Ctrl+D"), self)
        shortcut_default.activated.connect(self._open_default_folder)
        
        # Ctrl+R - Show recent files
        shortcut_recent = QShortcut(QKeySequence("Ctrl+R"), self)
        shortcut_recent.activated.connect(self._show_recent_files)
        
        # Ctrl+L - Open last output folder
        shortcut_open = QShortcut(QKeySequence("Ctrl+L"), self)
        shortcut_open.activated.connect(self._open_output_folder)
    
    # ========================================================================
    # RECENT FILES MANAGEMENT
    # ========================================================================
    
    def _load_recent_files(self):
        """Load recent files from settings"""
        self.recent_files = []
        count = self.settings.beginReadArray("recentFiles")
        for i in range(count):
            self.settings.setArrayIndex(i)
            xdf = self.settings.value("xdf", "")
            bin_file = self.settings.value("bin", "")
            if xdf and bin_file and Path(xdf).exists() and Path(bin_file).exists():
                self.recent_files.append({'xdf': xdf, 'bin': bin_file})
        self.settings.endArray()
    
    def _save_recent_files(self):
        """Save recent files to settings"""
        self.settings.beginWriteArray("recentFiles")
        for i, entry in enumerate(self.recent_files[:MAX_RECENT_FILES]):
            self.settings.setArrayIndex(i)
            self.settings.setValue("xdf", entry['xdf'])
            self.settings.setValue("bin", entry['bin'])
        self.settings.endArray()
    
    def _add_recent_file(self, xdf_path: str, bin_path: str):
        """Add a file pair to recent files"""
        entry = {'xdf': xdf_path, 'bin': bin_path}
        # Remove if already exists
        self.recent_files = [f for f in self.recent_files if f['xdf'] != xdf_path]
        # Add to front
        self.recent_files.insert(0, entry)
        # Trim to max
        self.recent_files = self.recent_files[:MAX_RECENT_FILES]
        self._save_recent_files()
    
    def _show_recent_files(self):
        """Show recent files dialog"""
        if not self.recent_files:
            QMessageBox.information(self, "Recent Files", "No recent files.")
            return
        
        # Build menu of recent files
        items = []
        for entry in self.recent_files:
            xdf_name = Path(entry['xdf']).name
            bin_name = Path(entry['bin']).name
            items.append(f"{xdf_name} + {bin_name}")
        
        from PySide6.QtWidgets import QInputDialog
        item, ok = QInputDialog.getItem(
            self,
            "Recent Files",
            "Select a recent file pair:",
            items,
            0,
            False
        )
        
        if ok and item:
            index = items.index(item)
            entry = self.recent_files[index]
            self.xdf_input.setText(entry['xdf'])
            self.bin_input.setText(entry['bin'])
            self.log(f"Loaded recent: {Path(entry['xdf']).name} + {Path(entry['bin']).name}")
            
            # Set output folder and name
            self.folder_input.setText(str(Path(entry['xdf']).parent))
            self.name_input.setText(Path(entry['bin']).stem + "_export")
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _auto_find_matching_bin(self, xdf_path: str):
        """Try to find a matching BIN file when XDF is selected"""
        xdf_dir = Path(xdf_path).parent
        xdf_stem = Path(xdf_path).stem.lower()
        
        # Look for BIN files in same directory
        bin_files = list(xdf_dir.glob("*.bin"))
        
        if len(bin_files) == 1:
            # Only one BIN in folder - use it
            self.bin_input.setText(str(bin_files[0]))
            self.log(f"Auto-matched BIN: {bin_files[0].name}")
            if self.name_input.text() == "export":
                self.name_input.setText(bin_files[0].stem + "_export")
        elif bin_files:
            # Try to match by name similarity
            for bin_file in bin_files:
                bin_stem = bin_file.stem.lower()
                # Check for common patterns
                if bin_stem in xdf_stem or xdf_stem in bin_stem:
                    self.bin_input.setText(str(bin_file))
                    self.log(f"Auto-matched BIN: {bin_file.name}")
                    if self.name_input.text() == "export":
                        self.name_input.setText(bin_file.stem + "_export")
                    return
            
            # No match found - log available options
            self.log(f"Found {len(bin_files)} BIN files in folder - select one manually")
    
    def _get_default_folder(self) -> Optional[Path]:
        """Get the default TunerPro folder (user-configured or auto-detected)"""
        # First check user-configured path
        custom_path = self.settings.value(SETTINGS_KEY_DEFAULT_PATH, "")
        if custom_path and Path(custom_path).exists():
            return Path(custom_path)
        
        # Fall back to default paths
        for path in DEFAULT_TUNERPRO_PATHS:
            if path.exists():
                return path
        
        return None
    
    def _open_default_folder(self):
        """Open file dialog in default TunerPro folder"""
        default_folder = self._get_default_folder()
        
        if default_folder:
            self.folder_input.setText(str(default_folder))
            self.log(f"Default folder: {default_folder}")
            
            # Also open file dialog for XDF
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select XDF Definition File",
                str(default_folder),
                "XDF Files (*.xdf);;All Files (*.*)"
            )
            if file_path:
                self.xdf_input.setText(file_path)
                self.log(f"Selected XDF: {Path(file_path).name}")
                self._auto_find_matching_bin(file_path)
        else:
            self.log("No default folder configured - click Settings to set one")
            QMessageBox.information(
                self,
                "No Default Folder",
                "No TunerPro folder found.\n\n"
                "Click the ⚙ Settings button to configure your\n"
                "default TunerPro Files directory."
            )
    
    def _show_settings_dialog(self):
        """Show the settings configuration dialog"""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        
        # Info label
        info = QLabel("Configure your default TunerPro Files directory:")
        info.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info)
        
        # Path input row
        path_layout = QHBoxLayout()
        path_label = QLabel("Default Path:")
        path_label.setMinimumWidth(80)
        
        path_input = QLineEdit()
        current_path = self.settings.value(SETTINGS_KEY_DEFAULT_PATH, "")
        path_input.setText(current_path)
        path_input.setPlaceholderText("e.g., C:\\Users\\YourName\\Documents\\TunerPro Files")
        
        browse_btn = QPushButton("Browse...")
        browse_btn.setMinimumWidth(80)
        
        def browse_path():
            folder = QFileDialog.getExistingDirectory(
                dialog,
                "Select TunerPro Files Directory",
                current_path if current_path else str(Path.home())
            )
            if folder:
                path_input.setText(folder)
        
        browse_btn.clicked.connect(browse_path)
        
        path_layout.addWidget(path_label)
        path_layout.addWidget(path_input)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        # Current detected path
        detected = self._get_default_folder()
        if detected:
            detected_label = QLabel(f"Currently detected: {detected}")
            detected_label.setStyleSheet("color: #4caf50; font-size: 10px;")
        else:
            detected_label = QLabel("No valid path detected - please configure one")
            detected_label.setStyleSheet("color: #ff9800; font-size: 10px;")
        layout.addWidget(detected_label)
        
        # Spacer
        layout.addSpacing(20)
        
        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        
        def save_settings():
            new_path = path_input.text().strip()
            if new_path:
                if Path(new_path).exists():
                    self.settings.setValue(SETTINGS_KEY_DEFAULT_PATH, new_path)
                    self.log(f"Default path saved: {new_path}")
                    dialog.accept()
                else:
                    QMessageBox.warning(
                        dialog,
                        "Invalid Path",
                        f"The path does not exist:\n{new_path}\n\n"
                        "Please select a valid directory."
                    )
            else:
                # Clear the setting
                self.settings.remove(SETTINGS_KEY_DEFAULT_PATH)
                self.log("Default path cleared - will use auto-detection")
                dialog.accept()
        
        button_box.accepted.connect(save_settings)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.exec()
    
    def _open_output_folder(self):
        """Open the output folder in file explorer"""
        folder = self.folder_input.text().strip()
        if folder and Path(folder).exists():
            # Use subprocess to open folder
            if sys.platform == 'win32':
                subprocess.Popen(['explorer', folder])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder])
            else:
                subprocess.Popen(['xdg-open', folder])
        elif self.last_output_files:
            # Open folder of first output file
            first_file = Path(self.last_output_files[0])
            if first_file.parent.exists():
                if sys.platform == 'win32':
                    subprocess.Popen(['explorer', str(first_file.parent)])


def main():
    """Main entry point for the GUI application"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for consistent look
    
    # Set application metadata
    app.setApplicationName("KingAI TunerPro Exporter")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("KingAI Pty Ltd")
    app.setOrganizationDomain("kingaituning.com.au")
    
    # Create and show main window
    window = TunerProExporterGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
