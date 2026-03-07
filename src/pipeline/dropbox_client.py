"""Dropbox SDK wrapper for asset storage."""
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import dropbox
from dropbox import files as dbx_files
from dropbox.exceptions import AuthError

log = logging.getLogger(__name__)
T = TypeVar("T")


class DropboxClient:
    """Wraps the Dropbox SDK for upload, download, and temporary link generation."""

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        app_key: str | None = None,
        app_secret: str | None = None,
    ) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._app_key = app_key
        self._app_secret = app_secret
        self._supports_refresh = bool(refresh_token and app_key)
        self._dbx = self._new_client()

    def _new_client(self) -> dropbox.Dropbox:
        if self._supports_refresh:
            return dropbox.Dropbox(
                oauth2_access_token=self._access_token or None,
                oauth2_refresh_token=self._refresh_token,
                app_key=self._app_key,
                app_secret=self._app_secret,
            )
        return dropbox.Dropbox(oauth2_access_token=self._access_token)

    @staticmethod
    def _is_access_token_auth_error(exc: Exception) -> bool:
        if not isinstance(exc, AuthError):
            return False
        text = str(exc)
        return any(marker in text for marker in (
            "expired_access_token",
            "invalid_access_token",
            "token_revoked",
        ))

    def _call_with_auth_retry(
        self,
        operation: str,
        fn: Callable[[], T],
        *,
        dropbox_path: str | None = None,
    ) -> T:
        try:
            return fn()
        except Exception as exc:
            if self._is_access_token_auth_error(exc):
                if self._supports_refresh:
                    log.warning("Dropbox access token failed during %s; retrying with refresh token", operation)
                    self._dbx = self._new_client()
                    return fn()
                msg = (
                    "Dropbox access token is invalid or expired. Configure either a new "
                    "DROPBOX_ACCESS_TOKEN or set DROPBOX_REFRESH_TOKEN + DROPBOX_APP_KEY "
                    "(and DROPBOX_APP_SECRET if required) to enable automatic refresh."
                )
                if dropbox_path:
                    msg = f"{msg} Failing path: {dropbox_path}"
                raise RuntimeError(msg) from exc
            raise

    def upload(self, data: bytes, dropbox_path: str) -> str:
        """Upload bytes to Dropbox, overwriting if the file already exists.

        Args:
            data: Raw bytes to upload.
            dropbox_path: Full Dropbox path (e.g. "/{dropbox_app_name}/outputs/run1/prod/1x1.png").

        Returns:
            The path_display of the uploaded file.
        """
        try:
            result = self._call_with_auth_retry(
                "upload",
                lambda: self._dbx.files_upload(
                    data,
                    dropbox_path,
                    mode=dbx_files.WriteMode.overwrite,
                ),
                dropbox_path=dropbox_path,
            )
        except Exception as exc:
            log.error("Dropbox upload failed path=%s: %s", dropbox_path, exc)
            raise
        log.debug("Uploaded %d bytes → %s", len(data), result.path_display)
        return result.path_display

    def download(self, dropbox_path: str) -> bytes:
        """Download a file from Dropbox and return its raw bytes.

        Args:
            dropbox_path: Full Dropbox path to the file.

        Returns:
            Raw file bytes.
        """
        try:
            _, response = self._call_with_auth_retry(
                "download",
                lambda: self._dbx.files_download(path=dropbox_path),
                dropbox_path=dropbox_path,
            )
        except Exception as exc:
            log.error("Dropbox download failed path=%s: %s", dropbox_path, exc)
            raise
        return response.content

    def list_folder(self, dropbox_path: str) -> Any:
        """List folder entries from Dropbox."""
        try:
            return self._call_with_auth_retry(
                "list_folder",
                lambda: self._dbx.files_list_folder(dropbox_path),
                dropbox_path=dropbox_path,
            )
        except Exception as exc:
            log.error("Dropbox list_folder failed path=%s: %s", dropbox_path, exc)
            raise

    def get_temporary_link(self, dropbox_path: str) -> str:
        """Generate a 4-hour temporary download link for a Dropbox file.

        Args:
            dropbox_path: Full Dropbox path to the file.

        Returns:
            HTTPS URL string for the temporary link.
        """
        try:
            result = self._call_with_auth_retry(
                "get_temporary_link",
                lambda: self._dbx.files_get_temporary_link(path=dropbox_path),
                dropbox_path=dropbox_path,
            )
        except Exception as exc:
            log.error("Dropbox get_temporary_link failed path=%s: %s", dropbox_path, exc)
            raise
        return result.link
