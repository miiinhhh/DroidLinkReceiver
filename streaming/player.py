import subprocess


class FFplayPlayer:
    def __init__(self):
        self.process = None

    def start(self):
        command = [
            "ffplay",
            "-loglevel", "warning",
            "-f", "h264",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-framedrop",
            "-window_title", "DroidLink",
            "pipe:0",
        ]

        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
        )

    def stop(self):
        if not self.process:
            return

        try:
            if self.process.stdin:
                self.process.stdin.close()
        except OSError:
            pass

        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                self.process.terminate()
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                except OSError:
                    pass

        self.process = None
