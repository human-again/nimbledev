import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")


class LLMAdapterTest(unittest.TestCase):
    def test_default_provider_creates_anthropic_client(self) -> None:
        from agents.llm import AnthropicLLMClient, create_llm_client

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            os.environ.pop("LLM_PROVIDER", None)
            self.assertIsInstance(create_llm_client(), AnthropicLLMClient)

    def test_unsupported_provider_fails_clearly(self) -> None:
        from agents.llm import create_llm_client

        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=False):
            with self.assertRaisesRegex(
                ValueError,
                "Unsupported LLM_PROVIDER='openai'. Supported providers: anthropic.",
            ):
                create_llm_client()

    def test_model_prefers_generic_model_over_anthropic_model(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "test-key",
                "GITHUB_TOKEN": "test-github-token",
                "MODEL": "generic-model",
                "ANTHROPIC_MODEL": "anthropic-model",
            },
            clear=False,
        ):
            import config.settings as settings

            reloaded = importlib.reload(settings)
            self.assertEqual("generic-model", reloaded.MODEL)

    def test_anthropic_response_is_normalized(self) -> None:
        from agents.llm import AnthropicLLMClient

        fake_response = SimpleNamespace(
            stop_reason="tool_use",
            content=[
                SimpleNamespace(type="text", text="Reading diff."),
                SimpleNamespace(
                    type="tool_use",
                    id="toolu_1",
                    name="get_pr_diff",
                    input={"owner": "octo", "repo": "repo", "pr_number": 1},
                ),
            ],
            usage=SimpleNamespace(input_tokens=12, output_tokens=7),
        )
        fake_messages = SimpleNamespace(create=lambda **kwargs: fake_response)
        fake_client = SimpleNamespace(messages=fake_messages)

        client = AnthropicLLMClient(api_key="test-key", anthropic_client=fake_client)
        response = client.create_message(
            model="claude-test",
            max_tokens=100,
            system="system",
            tools=[],
            messages=[],
        )

        self.assertEqual("tool_use", response.stop_reason)
        self.assertEqual("Reading diff.", response.content[0].text)
        self.assertEqual("get_pr_diff", response.content[1].name)
        self.assertEqual({"owner": "octo", "repo": "repo", "pr_number": 1}, response.content[1].input)
        self.assertEqual(12, response.usage.input_tokens)
        self.assertEqual(7, response.usage.output_tokens)


if __name__ == "__main__":
    unittest.main()
