"""Live connection check. Run explicitly; ordinary test discovery skips this file."""

import unittest

from app.llm.llm_connection import llm_connection


class LLMConnectionTest(unittest.TestCase):
    def test_llm_responds(self):
        question = "What is capital of India?"
        try:
            with llm_connection() as (client, model):
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": question}],
                )
        except Exception as error:
            # Provider error messages can contain credentials or connection details.
            raise AssertionError(f"LLM request failed: {type(error).__name__}. Check .env and connectivity.") from None

        self.assertTrue(response.choices, "The model returned no choices.")
        answer = response.choices[0].message.content or ""
        self.assertTrue(answer.strip(), "The model returned an empty answer.")
        print(f"Question: {question}\nAnswer: {answer}")


if __name__ == "__main__":
    unittest.main()
