"""
실시간 시스템 오디오 → Whisper 음성인식 → 한국어 번역 → 화면 자막 오버레이
Boundless 같은 자체 사이트 강의(유튜브 아닌 곳)에서 나오는 소리를
실시간으로 잡아서 한국어 자막으로 화면에 띄워주는 프로그램입니다.

[사용 전 설치 필요 - PowerShell에서 실행]
pip install faster-whisper deep-translator pyaudiowpatch numpy --break-system-packages

Windows 전용입니다 (WASAPI Loopback 캡처 사용).
"""

import numpy as np
import pyaudiowpatch as pyaudio
import threading
import queue
import time
import tkinter as tk
from faster_whisper import WhisperModel
from deep_translator import GoogleTranslator

# ----------------- 설정 -----------------
CHUNK_SECONDS = 6          # 몇 초 단위로 잘라서 인식할지 (길수록 CPU 부담↓, 반응속도↓)
MODEL_SIZE = "base"        # tiny/base/small/medium/large-v3 (작을수록 가볍고 빠름, 정확도는 약간↓)
SAMPLE_RATE = 16000        # Whisper 권장 샘플레이트

audio_queue = queue.Queue()
text_queue = queue.Queue()


def find_loopback_device(p):
    """현재 재생 중인 출력 장치(스피커든 이어폰이든)의 loopback 입력을 매번 새로 찾습니다."""
    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

    if not default_speakers.get("isLoopbackDevice", False):
        for loopback in p.get_loopback_device_info_generator():
            if default_speakers["name"] in loopback["name"]:
                return loopback
    return default_speakers


def audio_capture_thread():
    """
    출력 장치(스피커/이어폰)에서 나오는 소리를 실시간으로 캡처.
    이어폰을 꽂거나 빼서 기본 출력 장치가 바뀌면 자동으로 감지해서 다시 연결합니다.
    """
    while True:  # 장치가 바뀌면 이 바깥 루프가 재시작함
        p = pyaudio.PyAudio()
        stream = None
        try:
            device = find_loopback_device(p)
            current_device_name = device["name"]
            print(f"[오디오 캡처 시작] 장치: {current_device_name}")

            channels = device["maxInputChannels"]
            rate = int(device["defaultSampleRate"])

            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=device["index"],
                frames_per_buffer=1024,
            )

            frames = []
            frames_needed = int(rate * CHUNK_SECONDS / 1024)
            check_counter = 0

            while True:
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)

                if len(frames) >= frames_needed:
                    raw = b"".join(frames)
                    audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    if channels == 2:
                        audio_np = audio_np.reshape(-1, 2).mean(axis=1)
                    max_vol = np.abs(audio_np).max()
                    print(f"[오디오 청크 전달] 최대 볼륨: {max_vol:.4f} (0.01 이상이면 소리 잡힘)")
                    audio_queue.put((audio_np, rate))
                    frames = []

                # 출력 장치가 바뀌었는지 주기적으로 체크 (이어폰 꽂음/뺌 감지)
                check_counter += 1
                if check_counter >= frames_needed * 5:
                    check_counter = 0
                    new_device = find_loopback_device(p)
                    if new_device["name"] != current_device_name:
                        print(f"[출력 장치 변경 감지] {current_device_name} -> {new_device['name']}")
                        raise RuntimeError("device changed")

        except Exception as e:
            print(f"[오디오 스트림 재연결] 사유: {e}")
            try:
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
            except Exception:
                pass
            p.terminate()
            time.sleep(1)


def whisper_thread():
    """큐에 쌓인 오디오를 Whisper로 영어 인식 -> 한국어 번역 -> 텍스트 큐에 넣는 스레드"""
    print("[Whisper 모델 로딩 중...] 처음 실행시 다운로드로 시간이 걸릴 수 있어요")
    # cpu_threads를 제한해서 언리얼 등 다른 프로그램이 쓸 CPU 코어를 남겨둠
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8", cpu_threads=2)
    translator = GoogleTranslator(source="en", target="ko")
    print("[준비 완료] 강의 재생하면 자막이 뜨기 시작합니다")

    while True:
        audio_np, rate = audio_queue.get()

        # 샘플레이트가 16000이 아니면 리샘플 (간단 비율 보정)
        if rate != SAMPLE_RATE:
            ratio = SAMPLE_RATE / rate
            new_len = int(len(audio_np) * ratio)
            audio_np = np.interp(
                np.linspace(0, len(audio_np), new_len),
                np.arange(len(audio_np)),
                audio_np,
            ).astype(np.float32)

        segments, _ = model.transcribe(audio_np, language="en", beam_size=1)
        english_text = " ".join(seg.text for seg in segments).strip()

        if english_text:
            try:
                korean_text = translator.translate(english_text)
            except Exception:
                korean_text = "(번역 실패)"
            text_queue.put((english_text, korean_text))


class SubtitleOverlay:
    """
    화면에 떠 있는 자막 창.
    - 평소엔 클릭이 아래 화면(언리얼 등)으로 그대로 통과됨 (작업 방해 안 함)
    - Alt를 누르고 있는 동안만 드래그로 이동 가능
    - 마우스 휠(Alt+휠)로 글자 크기 조절
    - 듀얼모니터 아무 위치로나 이동 가능
    """

    def __init__(self, root):
        self.root = root
        self.font_size = 22
        self.drag_data = {"x": 0, "y": 0}

        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.85)
        root.configure(bg="black")

        # 듀얼모니터 전체 영역 기준으로 배치 (기본은 주 모니터 하단)
        screen_w = root.winfo_screenwidth()
        win_w, win_h = 700, 130
        x = (screen_w - win_w) // 2
        y = root.winfo_screenheight() - win_h - 80
        root.geometry(f"{win_w}x{win_h}+{x}+{y}")

        # 클릭 통과 설정 (Windows 전용) - 평소엔 마우스 클릭이 뒤로 그대로 전달됨
        self.hwnd = None
        self.clickthrough_enabled = True
        self.root.after(100, self.make_clickthrough)

        top_bar = tk.Frame(root, bg="#222222", height=22)
        top_bar.pack(fill="x", side="top")
        top_bar.pack_propagate(False)

        hint = tk.Label(
            top_bar, text="Alt를 누른 채 드래그: 이동 ｜ Alt+휠: 크기조절",
            fg="#888888", bg="#222222", font=("맑은 고딕", 9)
        )
        hint.pack(side="left", padx=6)

        self.label_ko = tk.Label(
            root, text="자막 대기 중...", fg="yellow", bg="black",
            font=("맑은 고딕", self.font_size, "bold"), wraplength=win_w - 20, justify="center"
        )
        self.label_ko.pack(expand=True, fill="both", pady=(6, 0))

        self.label_en = tk.Label(
            root, text="", fg="gray", bg="black",
            font=("Arial", 11), wraplength=win_w - 20, justify="center"
        )
        self.label_en.pack(fill="x", pady=(0, 6))

        for widget in (top_bar, hint, self.label_ko, self.label_en, root):
            widget.bind("<ButtonPress-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.do_drag)
            widget.bind("<MouseWheel>", self.change_font_size)

        # Alt 키를 실제로 누르고 있는지 50ms마다 감시.
        # Alt를 누르면 클릭통과를 잠깐 끔(조작 가능) -> 떼면 다시 켬(뒤 화면 조작 가능)
        self.alt_currently_held = False
        self.watch_alt_key()
        self.update_loop()

    def watch_alt_key(self):
        import ctypes
        VK_MENU = 0x12  # Alt 키 코드
        alt_held_now = bool(ctypes.windll.user32.GetAsyncKeyState(VK_MENU) & 0x8000)

        if alt_held_now and not self.alt_currently_held:
            self.set_clickthrough(False)   # Alt 누름 -> 조작 가능 모드
        elif not alt_held_now and self.alt_currently_held:
            self.set_clickthrough(True)    # Alt 뗌 -> 다시 클릭 통과 모드

        self.alt_currently_held = alt_held_now
        self.root.after(50, self.watch_alt_key)

    def make_clickthrough(self):
        """Windows API로 이 창의 핸들을 가져와 클릭통과를 최초 설정"""
        try:
            import ctypes
            self.hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            self.set_clickthrough(True)
        except Exception as e:
            print(f"[클릭통과 설정 실패 - 무시하고 계속 진행] {e}")

    def set_clickthrough(self, enable: bool):
        if self.hwnd is None:
            return
        import ctypes
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x80000
        WS_EX_TRANSPARENT = 0x20
        style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        if enable:
            ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
        else:
            ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, (style | WS_EX_LAYERED) & ~WS_EX_TRANSPARENT)
        self.clickthrough_enabled = enable

    def start_drag(self, event):
        self.drag_data["x"] = event.x_root - self.root.winfo_x()
        self.drag_data["y"] = event.y_root - self.root.winfo_y()

    def do_drag(self, event):
        # 듀얼모니터 전체로 자유롭게 이동 가능 (좌표 제한 없음)
        x = event.x_root - self.drag_data["x"]
        y = event.y_root - self.drag_data["y"]
        self.root.geometry(f"+{x}+{y}")

    def change_font_size(self, event):
        if event.delta > 0:
            self.font_size = min(self.font_size + 2, 60)
        else:
            self.font_size = max(self.font_size - 2, 10)
        self.label_ko.config(font=("맑은 고딕", self.font_size, "bold"))

    def update_loop(self):
        try:
            while True:
                en, ko = text_queue.get_nowait()
                self.label_ko.config(text=ko)
                self.label_en.config(text=en)
        except queue.Empty:
            pass
        self.root.after(300, self.update_loop)


def main():
    threading.Thread(target=audio_capture_thread, daemon=True).start()
    threading.Thread(target=whisper_thread, daemon=True).start()

    root = tk.Tk()
    app = SubtitleOverlay(root)
    root.mainloop()


if __name__ == "__main__":
    main()
