"""PTY relay: leave the native UI intact, own Ctrl+C and its exit epilogue."""
from __future__ import annotations

import contextlib
import errno
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import subprocess
import sys
import termios
import threading
import time
import tty


PASTE_ON, PASTE_OFF = b"\x1b[?2004h", b"\x1b[?2004l"
ANSI = re.compile(rb"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[()][0-2A-Z]|[\x40-\x5a\x5c\x5e-\x5f])")
RESET = (b"\x1b[?1006l\x1b[?1015l\x1b[?1003l\x1b[?1002l\x1b[?1000l"
         b"\x1b[<1u\x1b[<u\x1b[>4;0m\x1b[?1007l\x1b[?2004l\x1b[?1004l"
         b"\x1b[0m\x1b[0 q\x1b[?25h\x1b]7501;state=clear\x1b\\")


class InputFilter:
    """Recognize Ctrl+C, including enhanced keyboards, but never inside paste."""
    def __init__(self):
        self.pending = b""
        self.pasting = False
        self.interrupted = False

    def feed(self, data):
        data = self.pending + data
        self.pending = b""
        output = bytearray()
        while data and not self.interrupted:
            if data.startswith(b"\x1b["):
                match = re.match(rb"\x1b\[[0-?]*[ -/]*[@-~]", data)
                if not match:
                    if len(data) < 64:
                        self.pending = data
                        break
                    output.append(data[0])
                    data = data[1:]
                    continue
                key = match[0]
                if key == b"\x1b[200~":
                    self.pasting = True
                elif key == b"\x1b[201~":
                    self.pasting = False
                elif not self.pasting and (re.fullmatch(rb"\x1b\[99;5(?::[12])?u", key)
                                          or key == b"\x1b[27;5;99~"):
                    self.interrupted = True
                    break
                output.extend(key)
                data = data[len(key):]
            elif data == b"\x1b":
                self.pending = data
                break
            else:
                if data[0] == 3 and not self.pasting:
                    self.interrupted = True
                    break
                output.append(data[0])
                data = data[1:]
        # Do not submit a buffered Enter from the same read as Ctrl+C.
        return b"" if self.interrupted else bytes(output)

    def flush_escape(self):
        # A lone Escape remains a native key rather than waiting for another key.
        if self.pending == b"\x1b":
            self.pending = b""
            return b"\x1b"
        return b""


class ExitOutput:
    """Filter only after native terminal teardown, never inside conversation text.

    Codex 0.163.0 disables bracketed paste before printing its remote epilogue.
    Other output, including external editors and errors, continues to stream.
    """
    markers = (PASTE_ON, PASTE_OFF, b"\x1b[?1049h", b"\x1b[?1049l")
    footer_prefixes = (b"Disconnected from this task. Any running work continues.", b"To reconnect, run:",
                       b"codex --remote ", b"codex resume ", b"Stop the current turn: run codex ",
                       b"Token usage so far: ")

    def __init__(self, write):
        self.write = write
        self.pending = b""
        self.tail = None
        self.active = False
        self.alternate = False
        self.passthrough = False
        self.had_ui = False

    def _emit(self, data):
        if self.tail is None:
            self.write(data)
        else:
            self.tail.extend(data)
            self._flush_tail()

    def _flush_tail(self, final=False):
        while self.tail:
            if self.passthrough:
                end = self.tail.find(b"\n") + 1
                if not end:
                    self.write(bytes(self.tail))
                    self.tail.clear()
                    return
                self.write(bytes(self.tail[:end]))
                del self.tail[:end]
                self.passthrough = False
                continue
            if self.tail.startswith(b"\x1b"):
                escape = ANSI.match(self.tail)
                if escape:
                    self.write(escape[0])
                    del self.tail[:escape.end()]
                    continue
                if not final and len(self.tail) < 4096:
                    return
            end = self.tail.find(b"\n") + 1
            part = bytes(self.tail[:end] if end else self.tail)
            plain = ANSI.sub(b"", part).strip()
            prefixes = self.footer_prefixes
            candidate = any(p.startswith(plain) or plain.startswith(p) for p in prefixes)
            if end or final:
                hidden = plain in prefixes[:2] or any(plain.startswith(p) for p in prefixes[2:])
                self.write(b"".join(ANSI.findall(part)) if hidden else part)
                del self.tail[:len(part)]
            elif candidate and len(part) < 8192:
                return
            else:
                self.write(part)
                self.tail.clear()
                self.passthrough = True

    def feed(self, data):
        data = self.pending + data
        while data:
            hits = [(data.find(m), m) for m in self.markers if m in data]
            if not hits:
                # Keep only a partial marker, avoiding latency for ordinary UI text.
                keep = max((n for m in self.markers for n in range(1, len(m))
                            if data.endswith(m[:n])), default=0)
                self._emit(data[:-keep] if keep else data)
                self.pending = data[-keep:] if keep else b""
                return
            index, marker = min(hits)
            self._emit(data[:index])
            if marker == PASTE_ON:
                if self.tail is not None:
                    self.write(bytes(self.tail))
                    self.tail = None
                self.active = True
                self.had_ui = True
            elif marker == PASTE_OFF and self.active:
                self.tail = bytearray()
                self.passthrough = False
                self.active = False
            elif marker == b"\x1b[?1049h":
                self.alternate = True
            elif marker == b"\x1b[?1049l":
                self.alternate = False
            self._emit(marker)
            data = data[index + len(marker):]
        self.pending = b""

    def finish(self):
        self._emit(self.pending)
        self.pending = b""
        if self.tail is not None:
            self._flush_tail(final=True)
            self.tail = None
        if self.had_ui or self.alternate:
            if self.alternate:
                self.write(b"\x1b[?1049l")
            self.write(RESET)
            self.active = self.alternate = False
            self.had_ui = False


def write_all(fd, data):
    while data:
        count = os.write(fd, data)
        data = data[count:]


class TerminalRelay:
    def __init__(self, command, *, env, cwd):
        self.input_fd, self.output_fd = sys.stdin.fileno(), sys.stdout.fileno()
        self.settings = termios.tcgetattr(self.input_fd)
        self.interrupted = threading.Event()
        self.stop_input = threading.Event()
        self.stopping = threading.Event()
        self.error = None
        self.input = InputFilter()
        self.output = ExitOutput(lambda data: write_all(self.output_fd, data))
        self.master, slave = pty.openpty()
        self.proc = None
        self.thread = None
        try:
            termios.tcsetattr(slave, termios.TCSANOW, self.settings)
            self.size = fcntl.ioctl(self.input_fd, termios.TIOCGWINSZ, b"\0" * 8)
            fcntl.ioctl(slave, termios.TIOCSWINSZ, self.size)
            helper = str(Path(__file__))
            self.proc = subprocess.Popen([sys.executable, helper, *command], env=env, cwd=cwd,
                                         stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
            tty.setraw(self.input_fd)
            self.thread = threading.Thread(target=self._run, name="cdx-terminal", daemon=True)
            self.thread.start()
        except BaseException:
            if self.proc:
                self.proc.kill()
                self.proc.wait()
            os.close(self.master)
            termios.tcsetattr(self.input_fd, termios.TCSADRAIN, self.settings)
            raise
        finally:
            os.close(slave)

    def _run(self):
        last_input = 0
        try:
            while not self.stopping.is_set():
                size = fcntl.ioctl(self.input_fd, termios.TIOCGWINSZ, b"\0" * 8)
                if size != self.size:
                    fcntl.ioctl(self.master, termios.TIOCSWINSZ, size)
                    self.size = size
                readers = [self.master]
                if not self.stop_input.is_set():
                    readers.append(self.input_fd)
                ready = select.select(readers, [], [], .05)[0]
                if self.master in ready:
                    try:
                        data = os.read(self.master, 65536)
                    except OSError as exc:
                        if exc.errno == errno.EIO:  # Slave closed: normal PTY EOF.
                            break
                        raise
                    if not data:
                        break
                    self.output.feed(data)
                if self.input_fd in ready and not self.stop_input.is_set():
                    last_input = time.monotonic()
                    data = os.read(self.input_fd, 65536)
                    if not data:
                        self.interrupted.set()
                        self.stop_input.set()
                    else:
                        forwarded = self.input.feed(data)
                        if self.input.interrupted:
                            self.interrupted.set()
                            self.stop_input.set()
                        else:
                            write_all(self.master, forwarded)
                elif time.monotonic() - last_input >= .05 and not self.stop_input.is_set():
                    write_all(self.master, self.input.flush_escape())
        except OSError as exc:
            self.error = exc
            self.interrupted.set()
        finally:
            self.stop_input.set()

    def close(self):
        self.stop_input.set()
        try:
            # Ask the native UI to restore its screen first. The controller still
            # confirms interruption of every backend task before saving/exiting.
            for timeout in (.4, 1.0):
                if self.proc.poll() is not None:
                    break
                with contextlib.suppress(OSError):
                    write_all(self.master, b"\x03")
                try:
                    self.proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    pass
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=3)
            self.thread.join(timeout=1)
            self.stopping.set()
            self.thread.join(timeout=1)
            self.output.finish()
        finally:
            self.stopping.set()
            os.close(self.master)
            termios.tcsetattr(self.input_fd, termios.TCSADRAIN, self.settings)


if __name__ == "__main__":
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    try:
        os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
    except OSError as exc:
        print(f"无法启动 Codex 界面：{exc}", file=sys.stderr)
        sys.exit(127)
