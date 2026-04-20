import unittest

from realtime_stt_writer.audio.segmenter import EndpointingSegmenter
from realtime_stt_writer.domain.models import AudioFrame


class EndpointingSegmenterTests(unittest.TestCase):
    def test_emits_segment_after_speech_then_configured_silence(self) -> None:
        segmenter = EndpointingSegmenter(
            sample_rate=1000,
            rms_threshold=0.05,
            min_speech_ms=100,
            end_silence_ms=200,
            max_segment_sec=5,
        )

        emitted = []
        emitted.extend(segmenter.feed(AudioFrame(samples=[0.2] * 100, sample_rate=1000, timestamp=1.0)))
        emitted.extend(segmenter.feed(AudioFrame(samples=[0.0] * 100, sample_rate=1000, timestamp=1.1)))
        emitted.extend(segmenter.feed(AudioFrame(samples=[0.0] * 100, sample_rate=1000, timestamp=1.2)))

        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].sample_rate, 1000)
        self.assertEqual(emitted[0].started_at, 1.0)
        self.assertAlmostEqual(emitted[0].ended_at, 1.3)
        self.assertEqual(len(emitted[0].audio), 300)

    def test_flush_emits_pending_speech_segment(self) -> None:
        segmenter = EndpointingSegmenter(
            sample_rate=1000,
            rms_threshold=0.05,
            min_speech_ms=100,
            end_silence_ms=500,
            max_segment_sec=5,
        )
        segmenter.feed(AudioFrame(samples=[0.2] * 120, sample_rate=1000, timestamp=2.0))

        segment = segmenter.flush()

        self.assertIsNotNone(segment)
        assert segment is not None
        self.assertEqual(segment.started_at, 2.0)
        self.assertAlmostEqual(segment.ended_at, 2.12)

    def test_drops_noise_shorter_than_min_speech(self) -> None:
        segmenter = EndpointingSegmenter(
            sample_rate=1000,
            rms_threshold=0.05,
            min_speech_ms=100,
            end_silence_ms=50,
            max_segment_sec=5,
        )
        segmenter.feed(AudioFrame(samples=[0.2] * 40, sample_rate=1000, timestamp=0.0))
        emitted = segmenter.feed(AudioFrame(samples=[0.0] * 60, sample_rate=1000, timestamp=0.04))

        self.assertEqual(emitted, [])
        self.assertIsNone(segmenter.flush())


if __name__ == '__main__':
    unittest.main()
