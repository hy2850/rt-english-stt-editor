import unittest

from realtime_stt_writer.audio.capture import MicrophoneCapture


class FakeStream:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


class MicrophoneCaptureTests(unittest.TestCase):
    def test_callback_pushes_frames_into_queue(self) -> None:
        stream = FakeStream()
        captured_kwargs: dict[str, object] = {}

        def stream_factory(**kwargs):
            captured_kwargs.update(kwargs)
            return stream

        capture = MicrophoneCapture(
            sample_rate=16000,
            channels=1,
            blocksize=480,
            stream_factory=stream_factory,
        )

        capture.start()
        callback = captured_kwargs['callback']
        callback(b'frames', 3, {'input_buffer_adc_time': 1.25}, None)
        chunk = capture.queue.get_nowait()

        self.assertEqual(chunk['frames'], b'frames')
        self.assertEqual(chunk['frame_count'], 3)
        self.assertEqual(chunk['input_time'], 1.25)

    def test_start_and_stop_update_running_state_and_stream_lifecycle(self) -> None:
        stream = FakeStream()
        capture = MicrophoneCapture(
            sample_rate=16000,
            channels=1,
            blocksize=480,
            stream_factory=lambda **_kwargs: stream,
        )

        capture.start()
        self.assertTrue(capture.is_running)
        self.assertTrue(stream.started)

        capture.stop()
        self.assertFalse(capture.is_running)
        self.assertTrue(stream.stopped)
        self.assertTrue(stream.closed)

    def test_stream_builder_receives_sample_rate_and_channel_config(self) -> None:
        captured_kwargs: dict[str, object] = {}
        capture = MicrophoneCapture(
            sample_rate=22050,
            channels=2,
            blocksize=882,
            device='Built-in Microphone',
            stream_factory=lambda **kwargs: captured_kwargs.update(kwargs) or FakeStream(),
        )

        capture.start()

        self.assertEqual(captured_kwargs['samplerate'], 22050)
        self.assertEqual(captured_kwargs['channels'], 2)
        self.assertEqual(captured_kwargs['blocksize'], 882)
        self.assertEqual(captured_kwargs['device'], 'Built-in Microphone')


if __name__ == '__main__':
    unittest.main()
