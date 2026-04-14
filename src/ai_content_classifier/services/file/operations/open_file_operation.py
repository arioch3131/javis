"""Open-file operation implementation."""

import os
import subprocess
import sys
from typing import Any

from ai_content_classifier.services.file.operations.types import FileOperationKind
from ai_content_classifier.services.file.types import (
    FileOperationCode,
    FileOperationResult,
)


class OpenFileOperation:
    """Open a local file with the OS default application."""

    kind = FileOperationKind.OPEN_FILE

    def __init__(self, logger: Any):
        self.logger = logger

    def execute(self, file_path: str) -> FileOperationResult:
        normalized_path = str(file_path or "").strip()
        if not normalized_path or not os.path.isfile(normalized_path):
            return FileOperationResult(
                success=False,
                code=FileOperationCode.FILE_NOT_FOUND,
                message="File not found.",
                data={"path": normalized_path},
            )

        try:
            if sys.platform.startswith("win"):
                startfile = getattr(os, "startfile", None)
                if startfile is None:
                    return FileOperationResult(
                        success=False,
                        code=FileOperationCode.UNKNOWN_ERROR,
                        message="Open file is not supported on this platform.",
                        data={"path": normalized_path, "platform": sys.platform},
                    )
                startfile(normalized_path)
            elif sys.platform == "darwin":
                process = subprocess.run(
                    ["open", normalized_path],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if process.returncode != 0:
                    return self._map_open_command_failure(
                        process, "open", normalized_path
                    )
            elif sys.platform.startswith("linux"):
                process = subprocess.run(
                    ["xdg-open", normalized_path],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if process.returncode != 0:
                    return self._map_open_command_failure(
                        process, "xdg-open", normalized_path
                    )
            else:
                return FileOperationResult(
                    success=False,
                    code=FileOperationCode.UNKNOWN_ERROR,
                    message=f"Open file is not supported on platform '{sys.platform}'.",
                    data={"path": normalized_path, "platform": sys.platform},
                )

            return FileOperationResult(
                success=True,
                code=FileOperationCode.OK,
                message="File opened successfully.",
                data={"path": normalized_path},
            )
        except PermissionError:
            return FileOperationResult(
                success=False,
                code=FileOperationCode.ACCESS_DENIED,
                message="Access denied while opening the file.",
                data={"path": normalized_path},
            )
        except FileNotFoundError as exc:
            # Typically command missing (`xdg-open`/`open`) or stale file reference.
            return FileOperationResult(
                success=False,
                code=FileOperationCode.NO_DEFAULT_APP,
                message="No default application is available to open this file.",
                data={"path": normalized_path, "error": str(exc)},
            )
        except OSError as exc:
            winerror = getattr(exc, "winerror", None)
            if winerror in {5}:
                code = FileOperationCode.ACCESS_DENIED
                message = "Access denied while opening the file."
            elif winerror in {2, 3}:
                code = FileOperationCode.FILE_NOT_FOUND
                message = "File not found."
            elif winerror in {1155}:
                code = FileOperationCode.NO_DEFAULT_APP
                message = "No default application is available to open this file."
            else:
                code = FileOperationCode.UNKNOWN_ERROR
                message = "Unable to open the file due to an unexpected system error."
            return FileOperationResult(
                success=False,
                code=code,
                message=message,
                data={"path": normalized_path, "error": str(exc), "winerror": winerror},
            )
        except Exception as exc:  # pragma: no cover - defensive fallback.
            self.logger.error(
                "Unexpected error while opening file '%s': %s",
                normalized_path,
                exc,
                exc_info=True,
            )
            return FileOperationResult(
                success=False,
                code=FileOperationCode.UNKNOWN_ERROR,
                message="Unable to open the file due to an unexpected error.",
                data={"path": normalized_path, "error": str(exc)},
            )

    def _map_open_command_failure(
        self, process: subprocess.CompletedProcess, command: str, file_path: str
    ) -> FileOperationResult:
        details = " ".join(
            part.strip()
            for part in (process.stdout or "", process.stderr or "")
            if part and part.strip()
        ).lower()

        code = FileOperationCode.UNKNOWN_ERROR
        message = "Unable to open the file due to an unexpected system error."

        if "permission denied" in details:
            code = FileOperationCode.ACCESS_DENIED
            message = "Access denied while opening the file."
        elif process.returncode in {2, 3} or "no method available" in details:
            code = FileOperationCode.NO_DEFAULT_APP
            message = "No default application is available to open this file."

        return FileOperationResult(
            success=False,
            code=code,
            message=message,
            data={
                "path": file_path,
                "command": command,
                "return_code": process.returncode,
                "stdout": process.stdout or "",
                "stderr": process.stderr or "",
            },
        )
