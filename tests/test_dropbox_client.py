"""Tests for Dropbox client auth behavior."""
from unittest.mock import Mock, patch

from src.pipeline.dropbox_client import DropboxClient


class TestDropboxClientAuth:
    """Test auth error handling and refresh retry behavior."""

    def test_detects_invalid_access_token_error_marker(self):
        """Auth marker detection includes invalid_access_token errors."""
        with patch("src.pipeline.dropbox_client.AuthError", Exception):
            assert DropboxClient._is_access_token_auth_error(Exception("invalid_access_token"))

    def test_detects_expired_access_token_error_marker(self):
        """Auth marker detection includes expired_access_token errors."""
        with patch("src.pipeline.dropbox_client.AuthError", Exception):
            assert DropboxClient._is_access_token_auth_error(Exception("expired_access_token"))

    def test_retries_with_refresh_credentials_on_auth_error(self):
        """Client retries once when auth fails and refresh credentials are available."""
        client = DropboxClient(
            access_token="stale-token",
            refresh_token="refresh-token",
            app_key="app-key",
        )

        first_error = Exception("invalid_access_token")
        fn = Mock(side_effect=[first_error, "ok"])

        with patch("src.pipeline.dropbox_client.AuthError", Exception):
            result = client._call_with_auth_retry("upload", fn, dropbox_path="/path/file.png")

        assert result == "ok"
        assert fn.call_count == 2

    def test_uses_none_access_token_when_refresh_only(self):
        """Refresh-only initialization passes None access token to Dropbox SDK."""
        with patch("src.pipeline.dropbox_client.dropbox.Dropbox") as mock_sdk:
            DropboxClient(
                access_token="",
                refresh_token="refresh-token",
                app_key="app-key",
            )

            assert mock_sdk.call_count == 1
            kwargs = mock_sdk.call_args.kwargs
            assert kwargs["oauth2_access_token"] is None
            assert kwargs["oauth2_refresh_token"] == "refresh-token"
            assert kwargs["app_key"] == "app-key"
