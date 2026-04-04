import unittest


from realtime_stt_writer.cleanup.pipeline import CleanupPipeline
from realtime_stt_writer.cleanup.rule_based import RuleBasedCleanup
from realtime_stt_writer.domain.models import FinalizedSegment
from realtime_stt_writer.domain.models import Transcript
from realtime_stt_writer.services.orchestrator import AppOrchestrator


class FakeSTTEngine:
    def __init__(self, text: str) -> None:
        self.text = text

    def transcribe(
        self,
        audio,
        sample_rate: int,
        *,
        started_at: float,
        ended_at: float,
        segment_id: str,
    ) -> Transcript:
        return Transcript(
            text=self.text,
            language="en",
            started_at=started_at,
            ended_at=ended_at,
            segment_id=segment_id,
        )


class RecordingInjector:
    def __init__(self) -> None:
        self.inserted: list[str] = []

    def insert(self, text: str) -> None:
        self.inserted.append(text)


class AppOrchestratorTests(unittest.TestCase):
    def test_inserts_cleaned_sentence_with_newline_formatting(self) -> None:
        injector = RecordingInjector()
        orchestrator = AppOrchestrator(
            stt_engine=FakeSTTEngine("um I want ask about the homework"),
            cleanup_pipeline=CleanupPipeline(rule_engine=RuleBasedCleanup()),
            injector=injector,
        )

        orchestrator.on_finalized_segment(
            FinalizedSegment(
                audio=[0.1, 0.2],
                sample_rate=16000,
                started_at=1.0,
                ended_at=2.0,
                segment_id="seg-1",
            )
        )

        self.assertEqual(injector.inserted, ["I want ask about the homework.\n"])

    def test_skips_duplicate_segment_ids(self) -> None:
        injector = RecordingInjector()
        orchestrator = AppOrchestrator(
            stt_engine=FakeSTTEngine("hello there"),
            cleanup_pipeline=CleanupPipeline(rule_engine=RuleBasedCleanup()),
            injector=injector,
        )
        segment = FinalizedSegment(
            audio=[0.1],
            sample_rate=16000,
            started_at=1.0,
            ended_at=2.0,
            segment_id="seg-dup",
        )

        orchestrator.on_finalized_segment(segment)
        orchestrator.on_finalized_segment(segment)

        self.assertEqual(injector.inserted, ["hello there.\n"])


if __name__ == "__main__":
    unittest.main()
