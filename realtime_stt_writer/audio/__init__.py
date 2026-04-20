"""Audio capture and segmentation."""

from realtime_stt_writer.audio.capture import MicrophoneCapture
from realtime_stt_writer.audio.segmenter import EndpointingSegmenter

__all__ = ['EndpointingSegmenter', 'MicrophoneCapture']
