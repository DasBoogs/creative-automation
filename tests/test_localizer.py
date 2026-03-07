"""Tests for the localizer module."""
import pytest
from unittest.mock import Mock, patch

from src.pipeline.localizer import (
    _resolve_language,
    localize_message,
    localize_description,
)


class TestResolveLanguage:
    """Tests for _resolve_language function."""
    
    def test_english_region_no_translation(self):
        """Should return None for English-speaking regions without brief language."""
        assert _resolve_language("US", None) is None
        assert _resolve_language("UK", None) is None
        assert _resolve_language("AU", None) is None
        assert _resolve_language("CA", None) is None
    
    def test_non_english_region(self):
        """Should return target language for non-English regions."""
        assert _resolve_language("IT", None) == "Italian"
        assert _resolve_language("FR", None) == "French"
        assert _resolve_language("DE", None) == "German"
        assert _resolve_language("ES", None) == "Spanish"
    
    def test_english_region_with_different_brief_language(self):
        """Should translate when brief language differs from English."""
        assert _resolve_language("US", "Spanish") == "Spanish"
        assert _resolve_language("UK", "French") == "French"
    
    def test_english_region_with_english_brief_language(self):
        """Should not translate when brief is in English."""
        assert _resolve_language("US", "English") is None
        assert _resolve_language("UK", "en") is None
    
    def test_matching_brief_and_region_language(self):
        """Should not translate when brief language matches region."""
        assert _resolve_language("IT", "Italian") is None
        assert _resolve_language("FR", "French") is None
        assert _resolve_language("DE", "German") is None
    
    def test_case_insensitive(self):
        """Should handle case variations."""
        assert _resolve_language("it", None) == "Italian"
        assert _resolve_language("IT", "italian") is None


class TestLocalizeMessage:
    """Tests for localize_message function."""
    
    @patch("src.pipeline.localizer.genai.Client")
    def test_localize_to_italian(self, mock_genai):
        """Should translate message to Italian for IT region."""
        # Mock Gemini API response
        mock_response = Mock()
        mock_response.text = "Preparati per l'avventura estiva perfetta"
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.return_value = mock_client
        
        message = "Gear up for the perfect summer adventure"
        localized, language = localize_message(message, "IT", "fake_api_key")
        
        assert localized == "Preparati per l'avventura estiva perfetta"
        assert language == "Italian"
        mock_genai.assert_called_once_with(api_key="fake_api_key")
    
    def test_no_translation_for_us_region(self):
        """Should not translate for US region."""
        message = "Gear up for the perfect summer adventure"
        localized, language = localize_message(message, "US", "fake_api_key")
        
        assert localized == message
        assert language is None
    
    @patch("src.pipeline.localizer.genai.Client")
    def test_fallback_on_api_error(self, mock_genai):
        """Should return original message on API error."""
        mock_genai.side_effect = Exception("API Error")
        
        message = "Gear up for the perfect summer adventure"
        localized, language = localize_message(message, "IT", "fake_api_key")
        
        assert localized == message
        assert language is None


class TestLocalizeDescription:
    """Tests for localize_description function."""
    
    @patch("src.pipeline.localizer.genai.Client")
    def test_localize_description_to_french(self, mock_genai):
        """Should translate description to French for FR region."""
        mock_response = Mock()
        mock_response.text = "Crème solaire minérale légère et résistante à l'eau."
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.return_value = mock_client
        
        description = "Lightweight, water-resistant mineral sunscreen."
        localized, language = localize_description(description, "FR", "fake_api_key")
        
        assert localized == "Crème solaire minérale légère et résistante à l'eau."
        assert language == "French"
    
    def test_empty_description(self):
        """Should return empty description unchanged."""
        localized, language = localize_description("", "FR", "fake_api_key")
        
        assert localized == ""
        assert language is None
    
    def test_no_translation_for_uk_region(self):
        """Should not translate for UK region."""
        description = "Lightweight, water-resistant mineral sunscreen."
        localized, language = localize_description(description, "UK", "fake_api_key")
        
        assert localized == description
        assert language is None
    
    def test_no_translation_when_brief_matches_region(self):
        """Should not translate when brief language matches region."""
        description = "Crème solaire minérale légère."
        localized, language = localize_description(
            description, "FR", "fake_api_key", brief_language="French"
        )
        
        assert localized == description
        assert language is None
