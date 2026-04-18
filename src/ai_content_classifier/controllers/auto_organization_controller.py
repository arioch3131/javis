# controllers/auto_organization_controller.py
"""Controller for automatic organization and integrated progress reporting."""

import os
import platform
import subprocess
import time
from typing import Dict, List, Tuple
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from ai_content_classifier.core.logger import get_logger
from ai_content_classifier.services.auto_organization import (
    AutoOrganizationDataKey,
    AutoOrganizationOperationCode,
    AutoOrganizationOperationResult,
    AutoOrganizationService,
    OrganizationConfig,
)
from ai_content_classifier.views.widgets.common.operation_state import (
    OperationDetail,
    OperationStat,
    OperationViewState,
)


class OrganizationWorker(QThread):
    """Worker thread pour l'organisation des files."""

    # Signaux
    progress_updated = pyqtSignal(int, int)  # (processed, total)
    file_organized = pyqtSignal(str, str, str)  # (source, target, action)
    organization_completed = pyqtSignal(list)  # List of unified operation results
    organization_error = pyqtSignal(str)  # Erreur

    def __init__(
        self,
        service: AutoOrganizationService,
        file_list: List[str],
        config: OrganizationConfig,
    ):
        super().__init__()
        self.service = service
        self.file_list = file_list
        self.config = config
        self.should_cancel = False

    def cancel(self):
        """Demande l'annulation du processus."""
        self.should_cancel = True

    def run(self):
        """Run file organization."""
        try:
            results = []
            total_files = len(self.file_list)

            for i, file_path in enumerate(self.file_list):
                if self.should_cancel:
                    break

                try:
                    # Organiser ce file
                    result = self.service.organize_single_file(file_path, self.config)
                    results.append(result)

                    if result.success:
                        payload = result.data or {}
                        self.file_organized.emit(
                            str(
                                payload.get(
                                    AutoOrganizationDataKey.SOURCE_PATH.value, ""
                                )
                            ),
                            str(
                                payload.get(
                                    AutoOrganizationDataKey.TARGET_PATH.value, ""
                                )
                            ),
                            str(payload.get(AutoOrganizationDataKey.ACTION.value, "")),
                        )

                    # Émettre progression
                    self.progress_updated.emit(i + 1, total_files)

                except Exception as e:
                    # Create an error result
                    error_result = AutoOrganizationOperationResult(
                        success=False,
                        code=AutoOrganizationOperationCode.UNKNOWN_ERROR,
                        message=f"Unexpected worker error: {e}",
                        data={
                            AutoOrganizationDataKey.SOURCE_PATH.value: file_path,
                            AutoOrganizationDataKey.TARGET_PATH.value: "",
                            AutoOrganizationDataKey.ACTION.value: self.config.organization_action,
                            AutoOrganizationDataKey.ERROR.value: str(e),
                        },
                    )
                    results.append(error_result)

            # Emit results
            self.organization_completed.emit(results)

        except Exception as e:
            self.organization_error.emit(str(e))


class AutoOrganizationController(QObject):
    """
    Controller pour orchestrer l'organisation automatique des files.
    Handle l'interface entre la vue et le service d'organisation.
    """

    # Signaux pour la vue
    progress_updated = pyqtSignal(int, int)  # (processed, total)
    file_organized = pyqtSignal(str, str, str)  # (source, target, action)
    organization_completed = pyqtSignal(dict)  # Statistiques finales
    organization_error = pyqtSignal(str)  # Erreur
    organization_started = pyqtSignal()  # Organization started
    organization_cancelled = pyqtSignal()  # Organization cancelled
    preview_ready = pyqtSignal(dict)  # Preview ready

    def __init__(self, content_database_service, parent=None):
        super().__init__(parent)
        self.logger = get_logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # Service d'organisation
        self.service = AutoOrganizationService(content_database_service)

        # State de l'interface
        self.is_organizing = False
        self.current_worker = None
        self.main_window = None
        self._organization_started_at: float | None = None
        self._organization_snapshot: Dict[str, object] = {}

        # Timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._periodic_update)

    def bind_main_window(self, main_window) -> None:
        """Attaches the main window to drive integrated Operations."""
        self.main_window = main_window

    def has_integrated_operations_host(self) -> bool:
        return bool(
            self.main_window and hasattr(self.main_window, "show_operation_state")
        )

    def start_organization(
        self, file_list: List[Tuple[str, str]], config_dict: Dict
    ) -> bool:
        """
        Start file organization.

        Args:
            file_list: Liste de (file_path, directory)
            config_dict: Configuration sous forme de dictionnaire

        Returns:
            bool: True if organization started successfully
        """
        if self.is_organizing:
            self.logger.warning("Organization already in progress")
            self.organization_error.emit("An organization is already in progress")
            return False

        try:
            # Creater la configuration
            config = OrganizationConfig(
                target_directory=config_dict["target_directory"],
                organization_structure=config_dict["organization_structure"],
                organization_action=config_dict.get("organization_action", "copy"),
                custom_rules=config_dict.get("custom_rules"),
            )

            # Valider la configuration
            is_valid, error_message = self.service.validate_config(config)
            if not is_valid:
                self.logger.error(f"Invalid configuration: {error_message}")
                self.organization_error.emit(f"Configuration invalide: {error_message}")
                return False

            # Prepare target structure
            if not self.service.prepare_target_structure(config):
                self.organization_error.emit("Error while preparing target structure")
                return False

            # Extraire juste les chemins des files
            file_paths = [file_path for file_path, _ in file_list]

            self.logger.info(f"Starting organization of {len(file_paths)} files")
            self.logger.debug(f"Organization config: {config}")

            # Create and start worker
            self.current_worker = OrganizationWorker(self.service, file_paths, config)

            # Connectr les signaux
            self.current_worker.progress_updated.connect(self.progress_updated)
            self.current_worker.progress_updated.connect(self._on_progress_updated)
            self.current_worker.file_organized.connect(self.file_organized)
            self.current_worker.file_organized.connect(self._on_file_organized)
            self.current_worker.organization_completed.connect(
                self._on_organization_completed
            )
            self.current_worker.organization_error.connect(self._on_organization_error)
            self.current_worker.finished.connect(self._on_worker_finished)

            # Marquer comme en cours
            self.is_organizing = True
            self._organization_started_at = time.time()
            self._organization_snapshot = {
                "processed": 0,
                "total": len(file_paths),
                "current_file": "",
                "last_target": "",
                "successful": 0,
                "failed": 0,
                "state": "running",
                "target_directory": config.target_directory,
                "action": config.organization_action,
            }
            self._configure_operations_surface()

            # Start worker
            self.current_worker.start()

            # Start update timer
            self.update_timer.start(1000)  # Update every second

            # Emit start signal
            self.organization_started.emit()

            return True

        except Exception as e:
            self.logger.error(f"Error starting organization: {e}")
            self.organization_error.emit(f"Error while starting: {str(e)}")
            return False

    def cancel_organization(self):
        """Cancel l'organisation en cours."""
        if not self.is_organizing or not self.current_worker:
            return

        self.logger.info("Cancelling organization")
        self._organization_snapshot["state"] = "cancelling"
        self._push_operation_state()
        self.current_worker.cancel()

        # Wait briefly then force stop if needed
        if not self.current_worker.wait(3000):  # 3 secondes
            self.current_worker.terminate()
            self.current_worker.wait(1000)  # 1 seconde

        self._cleanup_organization()
        self.organization_cancelled.emit()

    def generate_preview(self, file_list: List[Tuple[str, str]], config_dict: Dict):
        """
        Generate organization preview.

        Args:
            file_list: Liste de (file_path, directory)
            config_dict: Configuration sous forme de dictionnaire
        """
        try:
            # Creater la configuration
            config = OrganizationConfig(
                target_directory=config_dict["target_directory"],
                organization_structure=config_dict["organization_structure"],
                organization_action=config_dict.get("organization_action", "copy"),
                custom_rules=config_dict.get("custom_rules"),
            )

            # Valider la configuration
            is_valid, error_message = self.service.validate_config(config)
            if not is_valid:
                self.preview_ready.emit(
                    {"error": f"Configuration invalide: {error_message}"}
                )
                return

            # Extraire juste les chemins des files
            file_paths = [file_path for file_path, _ in file_list]

            # Generate preview
            preview = self.service.get_organization_preview(file_paths, config)

            # Add additional information
            preview["config"] = {
                "target_directory": config.target_directory,
                "structure": config.organization_structure,
                "action": config.organization_action,
            }

            self.preview_ready.emit(preview)

        except Exception as e:
            self.logger.error(f"Error generating preview: {e}")
            self.preview_ready.emit({"error": str(e)})

    def get_supported_structures(self) -> List[str]:
        """Return list of supported organization structures."""
        return list(self.service.structure_handlers.keys())

    def _on_organization_completed(
        self, results: List[AutoOrganizationOperationResult]
    ):
        """Gestionnaire pour la fin de l'organisation."""
        try:
            # Get configuration from worker
            config = self.current_worker.config if self.current_worker else None

            if config:
                # Calculer les statistiques
                stats = self.service.calculate_statistics(results, config)
                stats["cancelled"] = (
                    self.current_worker.should_cancel if self.current_worker else False
                )

                self.logger.info(
                    f"Organization completed: "
                    f"{stats['successful']}/{stats['total_files']} files successful"
                )
                self._organization_snapshot.update(
                    {
                        "processed": stats.get("total_files", 0),
                        "total": stats.get("total_files", 0),
                        "successful": stats.get("successful", 0),
                        "failed": stats.get("failed", 0),
                        "state": "completed",
                        "target_directory": stats.get(
                            "target_directory", config.target_directory
                        ),
                    }
                )
                self._push_operation_state()
                self.organization_completed.emit(stats)
            else:
                self.organization_error.emit("Erreur: configuration non disponible")

        except Exception as e:
            self.logger.error(f"Error processing organization completion: {e}")
            self.organization_error.emit(f"Erreur lors de la finalisation: {str(e)}")
        finally:
            self._cleanup_organization()

    def _on_progress_updated(self, processed: int, total: int) -> None:
        self._organization_snapshot["processed"] = processed
        self._organization_snapshot["total"] = total
        self._push_operation_state()

    def _on_file_organized(self, source: str, target: str, action: str) -> None:
        del action
        self._organization_snapshot["current_file"] = os.path.basename(source)
        self._organization_snapshot["last_target"] = target
        successful = int(self._organization_snapshot.get("successful", 0))
        self._organization_snapshot["successful"] = successful + 1
        self._push_operation_state()

    def _on_organization_error(self, error_message: str):
        """Gestionnaire pour les errors d'organisation."""
        self.logger.error(f"Organization error: {error_message}")
        self._organization_snapshot["state"] = "failed"
        self._push_operation_state()
        self.organization_error.emit(error_message)
        self._cleanup_organization()

    def _on_worker_finished(self):
        """Gestionnaire pour la fin du worker."""
        self._cleanup_organization()

    def _cleanup_organization(self):
        """Clean state after organization."""
        self.is_organizing = False
        self.update_timer.stop()

        if self.current_worker:
            self.current_worker.deleteLater()
            self.current_worker = None

    def _configure_operations_surface(self) -> None:
        if not self.main_window:
            return
        if hasattr(self.main_window, "set_operation_action_handlers"):
            self.main_window.set_operation_action_handlers(
                {
                    "cancel": self.cancel_organization,
                    "close": self._clear_operation_surface,
                    "open_target": self._open_target_directory,
                }
            )
        self._update_working_state()
        self._push_operation_state()

    def _clear_operation_surface(self) -> None:
        if self.main_window and hasattr(self.main_window, "clear_operation_state"):
            self.main_window.clear_operation_state()
        self._reset_working_state()

    def _push_operation_state(self) -> None:
        if not self.main_window or not hasattr(
            self.main_window, "show_operation_state"
        ):
            return
        snapshot = self._organization_snapshot
        processed = max(0, int(snapshot.get("processed", 0)))
        total = max(0, int(snapshot.get("total", 0)))
        successful = max(0, int(snapshot.get("successful", 0)))
        failed = max(0, int(snapshot.get("failed", 0)))
        state = str(snapshot.get("state", "running"))
        current_file = (
            str(snapshot.get("current_file", "")) or "Waiting for first file..."
        )
        target_directory = str(snapshot.get("target_directory", ""))
        elapsed = self._format_elapsed()
        speed = (
            processed / max(0.001, time.time() - self._organization_started_at)
            if self._organization_started_at and processed > 0
            else 0.0
        )

        if state == "completed":
            title = "Organization completed"
            summary = f"{successful}/{total} files organized"
            primary_action = None
            secondary_action = "open_target" if target_directory else "close"
            secondary_label = "Open folder" if target_directory else "Close"
        elif state == "failed":
            title = "Organization failed"
            summary = "Organization failed or cancelled"
            primary_action = None
            secondary_action = "close"
            secondary_label = "Close"
        elif state == "cancelling":
            title = "Stopping organization"
            summary = f"{processed}/{total} files processed"
            primary_action = None
            secondary_action = None
            secondary_label = None
        else:
            title = "Organizing..."
            summary = f"{processed}/{total} files processed"
            primary_action = "cancel"
            secondary_action = None
            secondary_label = None

        self._update_working_state(processed=processed, total=total, state=state)

        self.main_window.show_operation_state(
            OperationViewState(
                operation_id="organization",
                kind="organization",
                title=title,
                state=state,  # type: ignore[arg-type]
                summary=summary,
                current_item=current_file,
                progress_current=processed,
                progress_total=total,
                is_determinate=total > 0,
                stats=[
                    OperationStat("Processed", str(processed)),
                    OperationStat("Success", str(successful)),
                    OperationStat("Failed", str(failed)),
                ],
                details=[
                    OperationDetail("Processed", f"{processed}/{total}"),
                    OperationDetail(
                        "Rate", self._format_rate(speed, "files") if speed > 0 else "--"
                    ),
                    OperationDetail("Elapsed", elapsed),
                    OperationDetail("Target", target_directory or "--"),
                ],
                primary_action=primary_action,  # type: ignore[arg-type]
                secondary_action=secondary_action,  # type: ignore[arg-type]
                secondary_action_label=secondary_label,
            )
        )

    def _update_working_state(
        self,
        processed: int | None = None,
        total: int | None = None,
        state: str | None = None,
    ) -> None:
        if not self.main_window:
            return
        snapshot = self._organization_snapshot
        processed = max(
            0, int(processed if processed is not None else snapshot.get("processed", 0))
        )
        total = max(0, int(total if total is not None else snapshot.get("total", 0)))
        state = state or str(snapshot.get("state", "running"))
        percentage = int((processed / total) * 100) if total > 0 else 0
        if hasattr(self.main_window, "set_main_status_chip"):
            self.main_window.set_main_status_chip(
                "Working...", is_busy=state != "completed"
            )
        if hasattr(self.main_window, "set_progress_status_chip"):
            self.main_window.set_progress_status_chip(
                f"Organization: {processed}/{total} files ({percentage:.1f}%)",
                is_busy=state in {"running", "cancelling"},
            )
        if hasattr(self.main_window, "update_progress_bar"):
            self.main_window.update_progress_bar(percentage)

    def _reset_working_state(self) -> None:
        if not self.main_window:
            return
        if hasattr(self.main_window, "set_main_status_chip"):
            self.main_window.set_main_status_chip("Ready", is_busy=False)
        if hasattr(self.main_window, "set_progress_status_chip"):
            self.main_window.set_progress_status_chip("Metadata idle", is_busy=False)
        if hasattr(self.main_window, "update_progress_bar"):
            self.main_window.update_progress_bar(0)

    @staticmethod
    def _format_rate(rate: float, unit: str) -> str:
        if rate <= 0:
            return f"0.0 {unit}/s"
        if rate < 1:
            return f"{rate * 60:.1f} {unit}/min"
        return f"{rate:.1f} {unit}/s"

    def _format_elapsed(self) -> str:
        if self._organization_started_at is None:
            return "00:00"
        elapsed = max(0.0, time.time() - self._organization_started_at)
        minutes, seconds = divmod(int(elapsed), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _open_target_directory(self) -> None:
        target_directory = str(self._organization_snapshot.get("target_directory", ""))
        if not target_directory:
            return
        try:
            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", target_directory], check=False)
            elif system == "Darwin":
                subprocess.run(["open", target_directory], check=False)
            else:
                subprocess.run(["xdg-open", target_directory], check=False)
        except Exception as exc:
            self.logger.error(f"Error opening target directory: {exc}")

    def _periodic_update(self):
        """Periodic update during organization."""
        if not self.is_organizing:
            return
        self._push_operation_state()
