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


class RecordingLogger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, message: str) -> None:
        self.lines.append(message)


class FailingInjector:
    def insert(self, text: str) -> None:
        raise RuntimeError('Unable to resolve the focused text cursor')


class RecordingInjector:
    def __init__(self) -> None:
        self.inserted: list[str] = []

    def insert(self, text: str) -> None:
        self.inserted.append(text)


class AppOrchestratorTests(unittest.TestCase):
    def test_inserts_cleaned_sentence_with_newline_formatting(self) -> None:
        injector = RecordingInjector()
        logger = RecordingLogger()
        orchestrator = AppOrchestrator(
            stt_engine=FakeSTTEngine("um I want ask about the homework"),
            cleanup_pipeline=CleanupPipeline(rule_engine=RuleBasedCleanup()),
            injector=injector,
            logger=logger,
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
        self.assertIn('[stt] seg-1 raw: um I want ask about the homework', logger.lines)
        self.assertIn('[insert] seg-1 inserted: I want ask about the homework.', logger.lines)


    def test_logs_insertion_failures_without_crashing_worker(self) -> None:
        logger = RecordingLogger()
        orchestrator = AppOrchestrator(
            stt_engine=FakeSTTEngine("hello there"),
            cleanup_pipeline=CleanupPipeline(rule_engine=RuleBasedCleanup()),
            injector=FailingInjector(),
            logger=logger,
        )

        orchestrator.on_finalized_segment(
            FinalizedSegment(
                audio=[0.1],
                sample_rate=16000,
                started_at=1.0,
                ended_at=2.0,
                segment_id="seg-fail",
            )
        )

        self.assertIn(
            '[insert] seg-fail failed: Unable to resolve the focused text cursor',
            logger.lines,
        )
        self.assertIsNone(orchestrator.last_inserted_segment_id)

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
