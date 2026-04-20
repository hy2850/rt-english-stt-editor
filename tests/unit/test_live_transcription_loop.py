import queue
import unittest

from realtime_stt_writer.domain.models import FinalizedSegment
from realtime_stt_writer.services.live_loop import LiveTranscriptionLoop


class FakeCapture:
    def __init__(self) -> None:
        self.queue: queue.Queue[dict[str, object]] = queue.Queue()
        self.started = False
        self.stopped = False

    @property
    def is_running(self) -> bool:
        return self.started and not self.stopped

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class RecordingSTT:
    def __init__(self) -> None:
        self.warmups = 0

    def warmup(self) -> None:
        self.warmups += 1


class RecordingSegmenter:
    def __init__(self) -> None:
        self.frames: list[object] = []
        self.flushed = False

    def feed(self, frame):
        self.frames.append(frame)
        return [
            FinalizedSegment(
                audio=frame.samples,
                sample_rate=frame.sample_rate,
                started_at=frame.timestamp,
                ended_at=frame.timestamp + 0.1,
                segment_id='seg-live',
            )
        ]

    def flush(self):
        self.flushed = True
        return None


class RecordingLogger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, message: str) -> None:
        self.lines.append(message)


class RecordingHandler:
    def __init__(self) -> None:
        self.segments: list[FinalizedSegment] = []

    def on_finalized_segment(self, segment: FinalizedSegment) -> None:
        self.segments.append(segment)


class LiveTranscriptionLoopTests(unittest.TestCase):
    def test_processes_captured_audio_frames_into_finalized_segments(self) -> None:
        capture = FakeCapture()
        segmenter = RecordingSegmenter()
        handler = RecordingHandler()
        logger = RecordingLogger()
        loop = LiveTranscriptionLoop(
            capture=capture,
            segmenter=segmenter,
            segment_handler=handler,
            stt_engine=RecordingSTT(),
            logger=logger,
        )
        capture.queue.put(
            {
                'frames': [[0.1], [0.2]],
                'sample_rate': 16000,
                'input_time': 42.0,
                'status': None,
            }
        )

        processed = loop.process_next_chunk(block=False)

        self.assertTrue(processed)
        self.assertEqual(segmenter.frames[0].samples, [0.1, 0.2])
        self.assertEqual(segmenter.frames[0].sample_rate, 16000)
        self.assertEqual(segmenter.frames[0].timestamp, 42.0)
        self.assertEqual(handler.segments[0].segment_id, 'seg-live')
        self.assertIn('[audio] finalized segment seg-live (0.10s)', logger.lines)

    def test_start_warms_stt_before_starting_capture_and_worker(self) -> None:
        events: list[str] = []

        class OrderedSTT(RecordingSTT):
            def warmup(self) -> None:
                events.append('warmup')
                super().warmup()

        class OrderedCapture(FakeCapture):
            def start(self) -> None:
                events.append('capture-start')
                super().start()

        capture = OrderedCapture()
        loop = LiveTranscriptionLoop(
            capture=capture,
            segmenter=RecordingSegmenter(),
            segment_handler=RecordingHandler(),
            stt_engine=OrderedSTT(),
            worker_factory=lambda target: None,
        )

        loop.start()

        self.assertEqual(events, ['warmup', 'capture-start'])
        self.assertTrue(capture.started)

    def test_stop_flushes_pending_segment(self) -> None:
        capture = FakeCapture()

        class FlushSegmenter(RecordingSegmenter):
            def flush(self):
                self.flushed = True
                return FinalizedSegment(
                    audio=[0.5],
                    sample_rate=16000,
                    started_at=1.0,
                    ended_at=1.1,
                    segment_id='flush-seg',
                )

        segmenter = FlushSegmenter()
        handler = RecordingHandler()
        loop = LiveTranscriptionLoop(
            capture=capture,
            segmenter=segmenter,
            segment_handler=handler,
            stt_engine=RecordingSTT(),
            worker_factory=lambda target: None,
        )

        loop.start()
        loop.stop()

        self.assertTrue(capture.stopped)
        self.assertTrue(segmenter.flushed)
        self.assertEqual(handler.segments[0].segment_id, 'flush-seg')


if __name__ == '__main__':
    unittest.main()
