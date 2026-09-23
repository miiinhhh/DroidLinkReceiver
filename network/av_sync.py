import time


class AVSync:
    def __init__(self):
        self.started = False
        self.stream_start_timestamp = 0
        self.playback_start_time = 0

    def reset(self):
        self.started = False
        self.stream_start_timestamp = 0
        self.playback_start_time = 0

    def start(self, timestamp_ms):
        if self.started:
            return

        self.started = True
        self.stream_start_timestamp = timestamp_ms
        self.playback_start_time = time.monotonic()

        print(
            f"[AVSync] Start timestamp: "
            f"{timestamp_ms} ms"
        )

    def get_delay(self, timestamp_ms):
        if not self.started:
            self.start(timestamp_ms)
            return 0

        elapsed_stream_ms = (
            timestamp_ms - self.stream_start_timestamp
        )

        elapsed_local_ms = (
            time.monotonic() -
            self.playback_start_time
        ) * 1000

        delay_ms = (
            elapsed_stream_ms -
            elapsed_local_ms
        )

        return max(0, delay_ms)