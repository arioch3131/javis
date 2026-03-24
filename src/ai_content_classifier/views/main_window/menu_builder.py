# views/main_window/menu_builder.py
"""
MenuBuilder - Menu and toolbar builder for MainWindow.

Responsible for creating and configuring menus, toolbars,
and actions for the main interface.
"""

from typing import Dict, List, Optional

from ai_content_classifier.core.logger import LoggableMixin
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup, QKeySequence
from PyQt6.QtWidgets import QMenu, QMenuBar, QToolBar, QWidget
from ai_content_classifier.services.i18n.i18n_service import tr


class MenuBuilder(LoggableMixin):
    """
    Modular menu and toolbar builder.

    Responsibilities:
    - Create main menus
    - Configure toolbars
    - Manage actions and shortcuts
    - Keep command hierarchy organized
    """

    def __init__(self, main_window):
        self.__init_logger__()
        self.main_window = main_window

        # Registries
        self.menus: Dict[str, QMenu] = {}
        self.actions: Dict[str, QAction] = {}
        self.toolbars: Dict[str, QToolBar] = {}
        self.action_groups: Dict[str, QActionGroup] = {}

        self.logger.debug("MenuBuilder initialized")

    def create_menus_and_toolbars(self):
        """Create all menus and toolbars."""
        try:
            self.logger.info("Creating menus and toolbars...")

            # 1. Create base actions
            self.create_core_actions()

            # 2. Create menu bar
            self.create_menu_bar()

            # 3. Create toolbars
            self.create_toolbars()

            # 4. Configure shortcuts and groups
            self.setup_action_groups()

            # 5. Final setup
            self.finalize_menus()

            self.logger.info("Menus and toolbars created successfully")

        except Exception as e:
            self.logger.error(f"Error creating menus and toolbars: {e}", exc_info=True)
            raise

    def create_core_actions(self):
        """Create the main application actions."""
        self.logger.debug("Creating core actions...")

        # === FILE ACTIONS ===
        self._create_file_actions()

        # === SCAN ACTIONS ===
        self._create_scan_actions()

        # === VIEW ACTIONS ===
        self._create_view_actions()

        # === TOOLS ACTIONS ===
        self._create_tools_actions()

        # === FILTER ACTIONS ===
        self._create_filter_actions()

        # === HELP ACTIONS ===
        self._create_help_actions()

        self.logger.debug(f"Created {len(self.actions)} core actions")

    def _create_file_actions(self):
        """Create actions for the File menu."""
        actions_data = [
            {
                "id": "file_open",
                "text": "📁 &Scan Folder...",
                "shortcut": "Ctrl+O",
                "tooltip": "Scan a folder for files",
                "status_tip": "Select and scan a folder for content classification",
            },
            {
                "id": "file_recent",
                "text": "📂 &Recent Folders",
                "tooltip": "Open recently scanned folders",
            },
            {
                "id": "file_export",
                "text": "📤 &Export Results...",
                "shortcut": "Ctrl+E",
                "tooltip": "Export classification results to file",
                "enabled": False,
            },
            {
                "id": "file_import",
                "text": "📥 &Import Settings...",
                "tooltip": "Import application settings from file",
                "enabled": False,
            },
            None,  # Separator
            {
                "id": "file_exit",
                "text": "🚪 E&xit",
                "shortcut": "Ctrl+Q",
                "tooltip": "Exit the application",
            },
        ]

        self._create_actions_from_data("file", actions_data)

    def _create_scan_actions(self):
        """Create actions for the Scan menu."""
        actions_data = [
            {
                "id": "scan_quick",
                "text": "⚡ &Quick Scan",
                "shortcut": "Ctrl+Shift+S",
                "tooltip": "Perform a quick scan of the current folder",
                "icon": "⚡",
            },
            {
                "id": "scan_advanced",
                "text": "🔍 &Advanced Scan...",
                "shortcut": "Ctrl+Shift+A",
                "tooltip": "Open advanced scan dialog with custom options",
                "icon": "🔍",
            },
            {
                "id": "scan_scheduled",
                "text": "⏰ &Scheduled Scan...",
                "tooltip": "Configure automatic scheduled scans",
                "enabled": False,
            },
            None,  # Separator
            {
                "id": "scan_stop",
                "text": "⏹️ &Stop Scan",
                "shortcut": "Escape",
                "tooltip": "Stop the current scan operation",
                "enabled": False,
            },
            None,  # Separator
            {
                "id": "scan_refresh",
                "text": "🔄 &Refresh",
                "shortcut": "F5",
                "tooltip": "Refresh the current file list",
                "icon": "🔄",
            },
        ]

        self._create_actions_from_data("scan", actions_data)

    def _create_view_actions(self):
        """Create actions for the View menu."""
        actions_data = [
            # View modes
            {
                "id": "view_grid",
                "text": "⊞ &Grid View",
                "shortcut": "Ctrl+1",
                "tooltip": "Show files in grid view with thumbnails",
                "checkable": True,
                "checked": True,
            },
            {
                "id": "view_list",
                "text": "☰ &List View",
                "shortcut": "Ctrl+2",
                "tooltip": "Show files in detailed list view",
                "checkable": True,
            },
            {
                "id": "view_columns",
                "text": "🗂️ &Columns View",
                "shortcut": "Ctrl+3",
                "tooltip": "Show files in columns view",
                "checkable": True,
            },
            None,  # Separator
            # Panels
            {
                "id": "view_sidebar",
                "text": "📋 &Sidebar",
                "shortcut": "Ctrl+Shift+1",
                "tooltip": "Show/hide the sidebar",
                "checkable": True,
                "checked": True,
            },
            None,  # Separator
            # Zoom
            {
                "id": "view_zoom_in",
                "text": "🔍+ Zoom &In",
                "shortcut": "Ctrl+=",
                "tooltip": "Increase thumbnail size",
            },
            {
                "id": "view_zoom_out",
                "text": "🔍- Zoom &Out",
                "shortcut": "Ctrl+-",
                "tooltip": "Decrease thumbnail size",
            },
            {
                "id": "view_zoom_reset",
                "text": "🔍 &Reset Zoom",
                "shortcut": "Ctrl+0",
                "tooltip": "Reset thumbnail size to default",
            },
            None,  # Separator
            # Other
            {
                "id": "view_fullscreen",
                "text": "🖥️ &Full Screen",
                "shortcut": "F11",
                "tooltip": "Toggle full screen mode",
                "checkable": True,
            },
            None,  # Separator
            {
                "id": "view_themes",
                "text": "🎨 &Themes...",
                "tooltip": "Change application theme",
            },
        ]

        self._create_actions_from_data("view", actions_data)

    def _create_tools_actions(self):
        """Create actions for the Tools menu."""
        actions_data = [
            # Classification
            {
                "id": "tools_categorize",
                "text": "🏷️ &Categorize Files...",
                "shortcut": "Ctrl+T",
                "tooltip": "Categorize files using AI classification",
                "enabled": False,
            },
            {
                "id": "tools_organize",
                "text": "📁 &Organize Files...",
                "tooltip": "Organize files into folders based on categories",
                "enabled": False,
            },
            None,  # Separator
            # Database
            {
                "id": "tools_clear_db",
                "text": "🗑️ &Clear Database",
                "tooltip": "Clear all data from the content database",
            },
            {
                "id": "tools_remove_filtered_db",
                "text": "🧹 Remove &Filtered Results from Database",
                "tooltip": "Remove only the currently displayed filtered results from the content database",
                "enabled": False,
            },
            {
                "id": "tools_compact_db",
                "text": "🗜️ &Compact Database",
                "tooltip": "Compact and optimize the database",
            },
            None,  # Separator
            # Configuration
            {
                "id": "tools_settings",
                "text": "⚙️ &Settings...",
                "shortcut": "Ctrl+,",
                "tooltip": "Open application settings",
            },
            {
                "id": "tools_llm_test",
                "text": "🔗 Test &LLM Connection",
                "tooltip": "Test connection to LLM services",
            },
        ]

        self._create_actions_from_data("tools", actions_data)

    def _create_filter_actions(self):
        """Create actions for the Filter menu."""
        actions_data = [
            {
                "id": "filter_by_category",
                "text": "🏷️ By Category...",
                "tooltip": "Filter files by category",
            },
            {
                "id": "filter_by_year",
                "text": "📅 By Year...",
                "tooltip": "Filter files by creation year",
            },
            {
                "id": "filter_by_extension",
                "text": "📎 By Extension...",
                "tooltip": "Filter files by extension",
            },
            None,  # Separator
            {
                "id": "filter_reset",
                "text": "🧹 Reset Filters",
                "shortcut": "Ctrl+R",
                "tooltip": "Reset all active filters",
            },
        ]
        self._create_actions_from_data("filter", actions_data)

    def _create_help_actions(self):
        """Create actions for the Help menu."""
        actions_data = [
            {
                "id": "help_documentation",
                "text": "📖 &Documentation",
                "shortcut": "F1",
                "tooltip": "Open user documentation",
                "enabled": False,
            },
            {
                "id": "help_shortcuts",
                "text": "⌨️ &Keyboard Shortcuts",
                "tooltip": "Show keyboard shortcuts reference",
                "enabled": False,
            },
            None,  # Separator
            {
                "id": "help_logs",
                "text": "📝 Show &Logs",
                "tooltip": "Open application logs window",
            },
            {
                "id": "help_debug",
                "text": "🐛 &Debug Info",
                "tooltip": "Show debug information",
            },
            None,  # Separator
            {
                "id": "help_about",
                "text": "ℹ️ &About",
                "tooltip": "About this application",
            },
        ]

        self._create_actions_from_data("help", actions_data)

    def _create_actions_from_data(self, category: str, actions_data: List):
        """Create actions from structured data."""
        for action_data in actions_data:
            if action_data is None:
                continue  # Separator, ignored here

            action_id = action_data["id"]
            action_text = tr(f"actions.{action_id}.text", action_data["text"])
            action = QAction(action_text, self.main_window)
            action.setObjectName(action_id)

            # Property setup
            if "shortcut" in action_data:
                action.setShortcut(QKeySequence(action_data["shortcut"]))

            if "tooltip" in action_data:
                action.setToolTip(
                    tr(f"actions.{action_id}.tooltip", action_data["tooltip"])
                )

            if "status_tip" in action_data:
                action.setStatusTip(
                    tr(f"actions.{action_id}.status_tip", action_data["status_tip"])
                )

            if "checkable" in action_data:
                action.setCheckable(action_data["checkable"])

            if "checked" in action_data:
                action.setChecked(action_data["checked"])

            if "enabled" in action_data:
                action.setEnabled(action_data["enabled"])

            # Icon (currently emoji-based, can be replaced with real icons)
            if "icon" in action_data:
                # action.setIcon(QIcon(action_data['icon']))  # Implement with real icons
                pass

            # Register action
            self.actions[action_id] = action

            # Connect to handler if available
            handler_name = f"handle_{action_id}"
            if hasattr(self.main_window, handler_name):
                handler = getattr(self.main_window, handler_name)
                action.triggered.connect(handler)
            else:
                # Default debug handler
                action.triggered.connect(
                    lambda checked, aid=action_id: self._default_action_handler(aid)
                )

    def _default_action_handler(self, action_id: str):
        """Default handler for actions without implementation."""
        self.logger.debug(f"Action triggered: {action_id} (no handler implemented)")

    def create_menu_bar(self):
        """Create the main menu bar."""
        self.logger.debug("Creating menu bar...")

        menubar = self.main_window.menuBar()
        menubar.clear()

        # === FILE MENU ===
        file_menu = self._create_file_menu(menubar)
        self.menus["file"] = file_menu

        # === SCAN MENU ===
        scan_menu = self._create_scan_menu(menubar)
        self.menus["scan"] = scan_menu

        # === VIEW MENU ===
        view_menu = self._create_view_menu(menubar)
        self.menus["view"] = view_menu

        # === TOOLS MENU ===
        tools_menu = self._create_tools_menu(menubar)
        self.menus["tools"] = tools_menu

        # === FILTER MENU ===
        filter_menu = self._create_filter_menu(menubar)
        self.menus["filter"] = filter_menu

        # === HELP MENU ===
        help_menu = self._create_help_menu(menubar)
        self.menus["help"] = help_menu

        self.logger.debug("Menu bar created")

    def _create_file_menu(self, menubar: QMenuBar) -> QMenu:
        """Create the File menu."""
        menu = menubar.addMenu(tr("menus.file", "&File"))
        menu.setObjectName("fileMenu")

        # Actions in order
        menu.addAction(self.actions["file_open"])

        menu.addSeparator()
        menu.addAction(self.actions["file_export"])
        menu.addAction(self.actions["file_import"])
        menu.addSeparator()
        menu.addAction(self.actions["file_exit"])

        return menu

    def _create_scan_menu(self, menubar: QMenuBar) -> QMenu:
        """Create the Scan menu."""
        menu = menubar.addMenu(tr("menus.scan", "&Scan"))
        menu.setObjectName("scanMenu")

        menu.addAction(self.actions["scan_quick"])
        menu.addAction(self.actions["scan_advanced"])
        menu.addAction(self.actions["scan_scheduled"])
        menu.addSeparator()
        menu.addAction(self.actions["scan_refresh"])

        return menu

    def _create_view_menu(self, menubar: QMenuBar) -> QMenu:
        """Create the View menu."""
        menu = menubar.addMenu(tr("menus.view", "&View"))
        menu.setObjectName("viewMenu")

        # Panels
        panels_menu = menu.addMenu(tr("menus.panels", "📋 &Panels"))
        panels_menu.addAction(self.actions["view_sidebar"])

        menu.addSeparator()

        # Zoom
        zoom_menu = menu.addMenu(tr("menus.zoom", "🔍 &Zoom"))
        zoom_menu.addAction(self.actions["view_zoom_in"])
        zoom_menu.addAction(self.actions["view_zoom_out"])
        zoom_menu.addAction(self.actions["view_zoom_reset"])

        menu.addSeparator()
        menu.addAction(self.actions["view_fullscreen"])
        menu.addAction(self.actions["view_themes"])

        return menu

    def _create_tools_menu(self, menubar: QMenuBar) -> QMenu:
        """Create the Tools menu."""
        menu = menubar.addMenu(tr("menus.tools", "&Tools"))
        menu.setObjectName("toolsMenu")

        menu.addAction(self.actions["tools_categorize"])
        menu.addAction(self.actions["tools_organize"])
        menu.addSeparator()

        # Database submenu
        db_menu = menu.addMenu(tr("menus.database", "🗄️ &Database"))
        db_menu.addAction(self.actions["tools_clear_db"])
        db_menu.addAction(self.actions["tools_remove_filtered_db"])
        db_menu.addAction(self.actions["tools_compact_db"])

        menu.addSeparator()
        menu.addAction(self.actions["tools_settings"])
        menu.addAction(self.actions["tools_llm_test"])

        return menu

    def _create_filter_menu(self, menubar: QMenuBar) -> QMenu:
        """Create the Filter menu."""
        menu = menubar.addMenu(tr("menus.filter", "&Filter"))
        menu.setObjectName("filterMenu")

        menu.addAction(self.actions["filter_by_category"])
        menu.addAction(self.actions["filter_by_year"])
        menu.addAction(self.actions["filter_by_extension"])
        menu.addSeparator()
        menu.addAction(self.actions["filter_reset"])

        return menu

    def _create_help_menu(self, menubar: QMenuBar) -> QMenu:
        """Create the Help menu."""
        menu = menubar.addMenu(tr("menus.help", "&Help"))
        menu.setObjectName("helpMenu")

        menu.addAction(self.actions["help_documentation"])
        menu.addAction(self.actions["help_shortcuts"])
        menu.addSeparator()
        menu.addAction(self.actions["help_logs"])
        menu.addAction(self.actions["help_debug"])
        menu.addSeparator()
        menu.addAction(self.actions["help_about"])

        return menu

    def create_toolbars(self):
        """Create toolbars."""
        self.logger.debug("Creating toolbars...")

        # === MAIN TOOLBAR ===
        self._create_main_toolbar()

        # === SCAN TOOLBAR ===
        self._create_scan_toolbar()

        # === VIEW TOOLBAR ===
        self._create_view_toolbar()

        self.logger.debug("Toolbars created")

    def _create_main_toolbar(self):
        """Create the main toolbar."""
        toolbar = self.main_window.addToolBar(tr("toolbar.main", "Main"))
        toolbar.setObjectName("mainToolbar")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # Main actions
        toolbar.addAction(self.actions["file_open"])
        toolbar.addSeparator()
        toolbar.addAction(self.actions["scan_advanced"])
        toolbar.addSeparator()
        toolbar.addAction(self.actions["tools_categorize"])
        toolbar.addAction(self.actions["tools_organize"])
        toolbar.addAction(self.actions["tools_settings"])

        self.toolbars["main"] = toolbar

    def _create_scan_toolbar(self):
        """Create the scan toolbar."""
        toolbar = self.main_window.addToolBar(tr("toolbar.scan", "Scan"))
        toolbar.setObjectName("scanToolbar")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        # Scan buttons
        toolbar.addAction(self.actions["scan_quick"])
        toolbar.addAction(self.actions["scan_advanced"])
        toolbar.addAction(self.actions["scan_refresh"])
        toolbar.addSeparator()
        toolbar.addAction(self.actions["scan_stop"])

        # Custom widget: quick folder selector
        self._add_folder_selector_widget(toolbar)

        # Hidden by default
        toolbar.hide()

        self.toolbars["scan"] = toolbar

    def _create_view_toolbar(self):
        """Create the view toolbar."""
        toolbar = self.main_window.addToolBar(tr("toolbar.view", "View"))
        toolbar.setObjectName("viewToolbar")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        # Zoom
        toolbar.addAction(self.actions["view_zoom_out"])
        toolbar.addAction(self.actions["view_zoom_reset"])
        toolbar.addAction(self.actions["view_zoom_in"])
        toolbar.addSeparator()

        # Panels
        toolbar.addAction(self.actions["view_sidebar"])

        self.toolbars["view"] = toolbar

    def _add_folder_selector_widget(self, toolbar: QToolBar):
        """Add a quick folder-selection widget."""
        from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton

        # Widget container
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Label
        from PyQt6.QtWidgets import QLabel

        label = QLabel("📁")
        layout.addWidget(label)

        # Path input
        path_input = QLineEdit()
        path_input.setObjectName("quickPathInput")
        path_input.setPlaceholderText(
            tr("quick_scan.enter_folder_path", "Enter folder path...")
        )
        path_input.setMinimumWidth(200)
        layout.addWidget(path_input)

        # Browse button
        browse_button = QPushButton("...")
        browse_button.setObjectName("quickBrowseButton")
        browse_button.setMaximumWidth(30)
        browse_button.clicked.connect(self._on_quick_browse_clicked)
        layout.addWidget(browse_button)

        # Scan button
        scan_button = QPushButton("▶")
        scan_button.setObjectName("quickScanButton")
        scan_button.setMaximumWidth(30)
        scan_button.setToolTip(tr("quick_scan.tooltip", "Quick scan this folder"))
        scan_button.clicked.connect(self._on_quick_scan_clicked)
        layout.addWidget(scan_button)

        # Add to toolbar
        toolbar.addWidget(container)

        # Save references
        self.main_window.quick_path_input = path_input

    def _on_quick_browse_clicked(self):
        """Open folder browser for quick scan."""
        from PyQt6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(
            self.main_window,
            tr(
                "quick_scan.select_folder_dialog_title",
                "Select folder for quick scan",
            ),
        )

        if folder and hasattr(self.main_window, "quick_path_input"):
            self.main_window.quick_path_input.setText(folder)

    def _on_quick_scan_clicked(self):
        """Run a quick scan."""
        if hasattr(self.main_window, "quick_path_input"):
            path = self.main_window.quick_path_input.text().strip()
            if path:
                # Delegate to quick scan handler
                if hasattr(self.main_window, "handle_quick_scan_request"):
                    self.main_window.handle_quick_scan_request(path)
                else:
                    self.logger.warning("Quick scan handler not implemented")

    def setup_action_groups(self):
        """Configure action groups and shortcuts."""
        self.logger.debug("Setting up action groups...")

        # === VIEW MODE GROUP ===
        view_mode_group = QActionGroup(self.main_window)
        view_mode_group.setExclusive(True)
        view_mode_group.addAction(self.actions["view_grid"])
        view_mode_group.addAction(self.actions["view_list"])
        view_mode_group.addAction(self.actions["view_columns"])
        self.action_groups["view_mode"] = view_mode_group

        # Ensure connection is made after finalization
        # Store reference for later connection
        self.main_window.view_mode_group = view_mode_group

        # === GLOBAL SHORTCUTS ===
        self._setup_global_shortcuts()

        self.logger.debug("Action groups configured")

    def _on_view_mode_triggered(self, action: QAction):
        """Called when a view mode is selected."""
        mode_mapping = {
            "view_grid": "grid",
            "view_list": "list",
            "view_columns": "columns",
        }

        action_id = action.objectName()
        mode = mode_mapping.get(action_id)

        if mode and hasattr(self.main_window, "set_view_mode"):
            self.main_window.set_view_mode(mode)

    def _setup_global_shortcuts(self):
        """Configure global keyboard shortcuts."""
        # Shortcuts are already set on actions.
        # Add special shortcuts here if needed.
        pass

    def finalize_menus(self):
        """Finalize menu configuration."""
        self.logger.debug("Finalizing menus...")

        try:
            # === CONFIGURE INITIAL STATES ===
            self._setup_initial_states()

            # === SYNC WITH UI STATE ===
            self._sync_with_ui_state()

            self.logger.debug("Menus finalized")

        except Exception as e:
            self.logger.error(f"Error finalizing menus: {e}")

    def connect_handlers(self):
        """Connect actions to MainWindow handlers after initialization."""
        self.logger.debug("Connecting actions to handlers...")
        self._connect_existing_handlers()

        # Connect view mode group
        if hasattr(self.main_window, "view_mode_group"):
            self.main_window.view_mode_group.triggered.connect(
                self._on_view_mode_triggered
            )
            self.logger.debug("Connected view mode group signals")

    def _connect_existing_handlers(self):
        """Connects actions to their corresponding handlers on MainWindow."""
        handler_mappings = {
            "file_open": "handle_open_folder_request",
            "scan_quick": "handle_quick_scan_request",
            "scan_advanced": "handle_scan_request",
            "scan_refresh": "handle_refresh_request",
            "tools_categorize": "handle_categorization_request",
            "tools_organize": "handle_auto_organize_request",
            "tools_clear_db": "handle_clear_db_request",
            "tools_remove_filtered_db": "handle_remove_filtered_results_request",
            "tools_settings": "handle_settings_request",
            "file_exit": "close",
            "help_about": "handle_about_request",
            "help_documentation": "handle_documentation_request",
            "help_logs": "handle_logs_request",
            "help_debug": "handle_debug_request",
            "tools_llm_test": "handle_llm_test_request",
            "view_fullscreen": "handle_fullscreen_toggle",
            "view_themes": "handle_theme_request",
            # Filters
            "filter_by_category": "handle_filter_by_category_request",
            "filter_by_year": "handle_filter_by_year_request",
            "filter_by_extension": "handle_filter_by_extension_request",
            "filter_reset": "handle_filter_reset_request",
            "view_zoom_in": "handle_zoom_in_request",
            "view_zoom_out": "handle_zoom_out_request",
            "view_zoom_reset": "handle_zoom_reset_request",
            "view_sidebar": "handle_view_sidebar_request",
        }

        for action_id, handler_name in handler_mappings.items():
            if action_id in self.actions:
                action = self.actions[action_id]
                if hasattr(self.main_window, handler_name):
                    handler = getattr(self.main_window, handler_name)
                    # Disconnect any previous connections to be safe
                    try:
                        action.triggered.disconnect()
                    except (TypeError, RuntimeError):
                        pass  # No connections to disconnect

                    # Connect using a lambda to ignore the 'checked' argument
                    action.triggered.connect(lambda checked=False, h=handler: h())
                    self.logger.debug(
                        f"Connected action '{action_id}' to handler '{handler_name}'"
                    )
                else:
                    self.logger.warning(
                        f"Handler '{handler_name}' not found on MainWindow for action '{action_id}'"
                    )

    def _setup_initial_states(self):
        """Configure initial action states."""
        # Disabled by default (enabled later based on context)
        disabled_actions = [
            "file_export",
            "scan_stop",
            "tools_categorize",
            "tools_organize",
        ]

        for action_id in disabled_actions:
            if action_id in self.actions:
                self.actions[action_id].setEnabled(False)

    def _sync_with_ui_state(self):
        """Synchronize menus with current UI state."""
        # Sync with UIBuilder if available
        if hasattr(self.main_window, "ui_builder"):
            ui_builder = self.main_window.ui_builder

            # Sync view modes
            if hasattr(ui_builder, "get_interface_state"):
                state = ui_builder.get_interface_state()

                # View mode
                view_mode = state.get("view_mode", 0)
                mode_actions = ["view_grid", "view_list", "view_columns"]
                if 0 <= view_mode < len(mode_actions):
                    action_id = mode_actions[view_mode]
                    if action_id in self.actions:
                        self.actions[action_id].setChecked(True)

    # === PUBLIC API ===

    def get_action(self, action_id: str) -> Optional[QAction]:
        """Return an action by ID."""
        return self.actions.get(action_id)

    def enable_action(self, action_id: str, enabled: bool = True):
        """Enable/disable an action."""
        if action_id in self.actions:
            self.actions[action_id].setEnabled(enabled)

    def check_action(self, action_id: str, checked: bool = True):
        """Check/uncheck an action."""
        if action_id in self.actions:
            action = self.actions[action_id]
            if action.isCheckable():
                action.setChecked(checked)
