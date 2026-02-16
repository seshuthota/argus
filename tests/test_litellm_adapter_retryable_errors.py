import unittest

import litellm

from argus.models.litellm_adapter import LiteLLMAdapter


class TestLiteLLMAdapterRetryableErrors(unittest.TestCase):
    def test_api_error_is_retryable(self) -> None:
        adapter = LiteLLMAdapter(api_key="x", api_base="https://example.com")
        exc = litellm.APIError(
            500,
            "OpenrouterException - ERROR",
            "openrouter",
            "openrouter/aurora-alpha",
        )
        self.assertTrue(adapter._is_retryable_error(exc))

    def test_service_unavailable_is_retryable(self) -> None:
        adapter = LiteLLMAdapter(api_key="x", api_base="https://example.com")
        exc = litellm.ServiceUnavailableError(
            "Service unavailable",
            "openrouter",
            "openrouter/aurora-alpha",
        )
        self.assertTrue(adapter._is_retryable_error(exc))

