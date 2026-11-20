import os
import sys
import time
import unittest
from unittest.mock import patch

import main


class AskTests(unittest.TestCase):
    def test_int_reprompts_until_known_id(self):
        with patch("builtins.input", side_effect=["x", "9", "2"]):
            self.assertEqual(main.ask_int("ID", valid={2}), 2)

    def test_cents_reprompts_until_valid_amount(self):
        with patch("builtins.input", side_effect=["abc", "-1", "20", "12.5"]):
            self.assertEqual(main.ask_cents("Pay", maximum=1500), 1250)

    def test_date_reprompts_until_iso(self):
        with patch("builtins.input", side_effect=["11-11-2026", "2026-11-11"]):
            self.assertEqual(main.ask_date("Date"), "2026-11-11")


@unittest.skipIf(main.termios is None, "Esc needs termios (not on Windows)")
class ReadKeysTests(unittest.TestCase):
    """read() in a real pseudo-terminal, typing keys one write at a time."""

    def run_keys(self, *keys):
        import pty
        sys.stdout.flush()  # or the child re-prints our buffered output
        pid, fd = pty.fork()
        if pid == 0:
            sys.stdin = open(0, closefd=False)  # undo pytest's capture
            sys.stdout = open(1, "w", closefd=False)
            try:
                result = repr(main.read())
            except KeyboardInterrupt:
                result = "BACK"
            os.write(1, f"\n<{result}>".encode())
            os._exit(0)
        time.sleep(0.3)
        for k in keys:
            os.write(fd, k)
            time.sleep(0.1)  # longer than read()'s 50 ms Esc wait
        out = b""
        try:
            while chunk := os.read(fd, 1024):
                out += chunk
        except OSError:  # Linux: child closed the terminal
            pass
        os.waitpid(pid, 0)
        return out.decode().rsplit("<", 1)[1].split(">")[0]

    def test_lone_esc_backs_out(self):
        self.assertEqual(self.run_keys(b"abc", b"\x1b"), "BACK")

    def test_edit_keys_and_utf8(self):
        # arrow key + digit in one write: only the arrow is dropped
        self.assertEqual(
            self.run_keys(b"Jos\xc3\xa9x", b"\x7f", b"\x1b[A5", b"\r"),
            "'José5'")


if __name__ == "__main__":
    unittest.main()
