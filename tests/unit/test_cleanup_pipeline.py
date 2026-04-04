import unittest


from realtime_stt_writer.cleanup.pipeline import CleanupPipeline
from realtime_stt_writer.cleanup.rule_based import RuleBasedCleanup


class ExplodingCleanupEngine:
    def cleanup(self, text: str, *, previous_sentences=None) -> str:
        raise RuntimeError("boom")


class CleanupPipelineTests(unittest.TestCase):
    def test_rule_based_cleanup_removes_fillers_and_repeated_tokens(self) -> None:
        cleaner = RuleBasedCleanup()

        cleaned = cleaner.cleanup("um I I want to ask about the homework")

        self.assertEqual(cleaned, "I want to ask about the homework")

    def test_pipeline_falls_back_to_rule_based_text_when_llm_cleanup_fails(self) -> None:
        pipeline = CleanupPipeline(
            rule_engine=RuleBasedCleanup(),
            llm_engine=ExplodingCleanupEngine(),
        )

        cleaned = pipeline.cleanup("uh can can I join tomorrow")

        self.assertEqual(cleaned, "can I join tomorrow")


if __name__ == "__main__":
    unittest.main()
