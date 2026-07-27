import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _runtime.llm_runtime import _generate_single_llm

class TestLlmRuntime(unittest.TestCase):
    @patch('os.getenv')
    @patch('_runtime.llm_runtime.OpenAI')
    def test_ollama_provider(self, mock_openai_class, mock_getenv):
        # Setup mock for getenv
        def getenv_side_effect(key, default=None):
            if key == "OLLAMA_BASE_URL":
                return "http://localhost:11434"
            if key == "OLLAMA_API_KEY":
                return "test-key"
            return default
        mock_getenv.side_effect = getenv_side_effect
        
        # Setup mock for OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Ollama response"))
        ]
        
        # Call the function
        result = _generate_single_llm("ollama", "qwen2.5:7b", "Hi")
        
        # Verify OpenAI was initialized with correct base_url
        mock_openai_class.assert_called_once_with(
            api_key="test-key",
            base_url="http://localhost:11434/v1"
        )
        
        # Verify the call
        mock_client.chat.completions.create.assert_called_once()
        self.assertEqual(result, "Ollama response")

    @patch('os.getenv')
    @patch('_runtime.llm_runtime.OpenAI')
    def test_ollama_default_base_url(self, mock_openai_class, mock_getenv):
        # Setup mock for getenv to return defaults (None)
        mock_getenv.side_effect = lambda key, default=None: default
        
        # Setup mock for OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Ollama response"))
        ]
        
        # Call the function
        _generate_single_llm("ollama", "qwen2.5:7b", "Hi")
        
        # Verify OpenAI was initialized with default ollama base_url
        mock_openai_class.assert_called_once_with(
            api_key="ollama",
            base_url="http://localhost:11434/v1"
        )

if __name__ == "__main__":
    unittest.main()
