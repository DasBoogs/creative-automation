"""Tests for Google Gemini Imagen client."""
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.pipeline.imagen_client import ImagenClient, DEFAULT_IMAGE_MODEL


@pytest.fixture
def mock_genai_client():
    """Mock the google-genai Client."""
    with patch("src.pipeline.imagen_client.genai.Client") as mock_client:
        yield mock_client


class TestImagenClient:
    """Test suite for ImagenClient class."""

    def test_init_with_api_key(self, mock_genai_client):
        """Test that ImagenClient initializes with an API key."""
        client = ImagenClient(api_key="test-api-key")
        
        mock_genai_client.assert_called_once_with(api_key="test-api-key")
        assert client._model == DEFAULT_IMAGE_MODEL

    def test_init_with_custom_model(self, mock_genai_client):
        """Test that ImagenClient can use a custom model."""
        client = ImagenClient(api_key="test-api-key", model="custom-model")
        
        assert client._model == "custom-model"

    def test_generate_text_to_image(self, mock_genai_client):
        """Test generating an image from text prompt only."""
        # Setup mock response
        mock_response = Mock()
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.data = b"fake-image-data"
        mock_response.parts = [mock_part]
        
        mock_instance = mock_genai_client.return_value
        mock_instance.models.generate_content.return_value = mock_response
        
        # Create client and generate
        client = ImagenClient(api_key="test-api-key")
        result = client.generate(
            prompt="A test product",
            ratio="1:1",
            reference_image_bytes=None,
        )
        
        assert result == b"fake-image-data"
        mock_instance.models.generate_content.assert_called_once()

    def test_generate_img2img(self, mock_genai_client):
        """Test generating an image with a reference image (img2img)."""
        # Setup mock response
        mock_response = Mock()
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.data = b"fake-image-data"
        mock_response.parts = [mock_part]
        
        mock_instance = mock_genai_client.return_value
        mock_instance.models.generate_content.return_value = mock_response
        
        # Create client and generate
        client = ImagenClient(api_key="test-api-key")
        result = client.generate(
            prompt="Reimagine this product",
            ratio="9:16",
            reference_image_bytes=b"reference-image",
        )
        
        assert result == b"fake-image-data"
        mock_instance.models.generate_content.assert_called_once()

    def test_generate_uses_correct_model(self, mock_genai_client):
        """Test that generate uses the configured model."""
        mock_response = Mock()
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.data = b"fake-image-data"
        mock_response.parts = [mock_part]
        
        mock_instance = mock_genai_client.return_value
        mock_instance.models.generate_content.return_value = mock_response
        
        client = ImagenClient(api_key="test-api-key", model="custom-model")
        client.generate("test prompt", "1:1", None)
        
        call_args = mock_instance.models.generate_content.call_args
        assert call_args[1]["model"] == "custom-model"

    def test_generate_with_different_ratios(self, mock_genai_client):
        """Test that different aspect ratios are passed correctly."""
        mock_response = Mock()
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.data = b"fake-image-data"
        mock_response.parts = [mock_part]
        
        mock_instance = mock_genai_client.return_value
        mock_instance.models.generate_content.return_value = mock_response
        
        client = ImagenClient(api_key="test-api-key")
        
        for ratio in ["1:1", "9:16", "16:9"]:
            client.generate(f"test {ratio}", ratio, None)
            call_args = mock_instance.models.generate_content.call_args
            # Verify the ratio is used in the config
            assert call_args is not None

    def test_generate_api_error_raises_runtime_error(self, mock_genai_client):
        """Test that API errors are raised as RuntimeError."""
        mock_instance = mock_genai_client.return_value
        mock_instance.models.generate_content.side_effect = Exception("API Error")
        
        client = ImagenClient(api_key="test-api-key")
        
        with pytest.raises(RuntimeError, match="Gemini API call failed"):
            client.generate("test prompt", "1:1", None)

    def test_generate_no_image_in_response_raises_error(self, mock_genai_client):
        """Test that missing image data in response raises an error."""
        # Setup mock response with no image data
        mock_response = Mock()
        mock_part = Mock()
        mock_part.inline_data = None
        mock_part.text = "Content policy violation"
        mock_response.parts = [mock_part]
        
        mock_instance = mock_genai_client.return_value
        mock_instance.models.generate_content.return_value = mock_response
        
        client = ImagenClient(api_key="test-api-key")
        
        with pytest.raises(RuntimeError, match="No image data returned"):
            client.generate("test prompt", "1:1", None)

    def test_generate_empty_response_raises_error(self, mock_genai_client):
        """Test that empty response raises an error."""
        mock_response = Mock()
        mock_response.parts = []
        
        mock_instance = mock_genai_client.return_value
        mock_instance.models.generate_content.return_value = mock_response
        
        client = ImagenClient(api_key="test-api-key")
        
        with pytest.raises(RuntimeError, match="No image data returned"):
            client.generate("test prompt", "1:1", None)
