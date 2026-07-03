# Live Sub — 영어를 바로 해석해주는 실시간 자막

컴퓨터에서 나오는 영어 소리를 실시간으로 인식해서
화면에 한국어 자막으로 띄워주는 프로그램입니다.

영어 강의를 들을 때,
또는 언리얼 엔진 같은 DCC 툴을 켜놓고 강의를 같이 볼 때 쓰기 위해 만들었습니다.

## 특징
- 유튜브든 자체 사이트 강의든 **사이트 종류 상관없이** 시스템에서 나오는 소리를 그대로 캡처
- **클릭 통과(click-through)** — 평소엔 자막창이 화면을 가려도 마우스 클릭이 뒤에 있는 언리얼/작업 화면에 그대로 전달됨
- **이어폰/스피커 자동 전환** — 출력 장치를 바꿔도 자동으로 다시 연결
- **듀얼모니터 지원** — Alt+드래그로 아무 모니터, 아무 위치로나 이동
- **글자 크기 조절** — Alt+마우스 휠
- 완전 로컬 실행 (Whisper), 번역만 인터넷 필요

## 설치

```bash
pip install faster-whisper deep-translator pyaudiowpatch numpy --break-system-packages
```

Windows 전용입니다 (WASAPI Loopback 캡처 사용).

⚠️ **파일 저장 위치 주의**: `live_subtitle_translator.py`는 반드시
**한글/공백/특수문자가 없는 경로**(예: `C:\livesub\`)에 두세요.
사용자 폴더명이나 경로에 한글이 섞여 있으면 실행이 깨질 수 있습니다.

## 실행

```bash
python live_subtitle_translator.py
```

## 조작법
| 동작 | 방법 |
|---|---|
| 자막창 이동 | `Alt` 누른 채 드래그 |
| 글자 크기 조절 | `Alt` 누른 채 마우스 휠 |
| 종료 | 실행 중인 콘솔 창에서 `Ctrl+C` |

평소엔 자막창이 화면 위에 떠 있어도 **클릭이 그대로 뒤(언리얼 등)로 전달**됩니다.
자막창 자체를 옮기거나 크기를 바꿀 때만 `Alt`를 누른 채로 조작하세요.

## 사용 팁 — DCC 툴(언리얼 등)과 같이 쓸 때

- **가벼운 작업(뷰포트 조작, 강의 따라하기)** 중에는 자막 켜둔 채로 사용해도 괜찮습니다.
- **무거운 작업(Movie Render Queue 렌더링, 대용량 임포트, 라이트빌드 등)** 을 돌릴 때는
  콘솔 창에서 `Ctrl+C`로 자막 프로그램을 잠깐 꺼두는 걸 추천합니다.
  Whisper와 렌더링이 동시에 CPU를 쓰면 렌더 속도가 느려질 수 있습니다.
- 기본 설정(`MODEL_SIZE = "base"`, `cpu_threads=2`)은 CPU 부담을 낮추는 쪽으로 맞춰져 있습니다.
  더 정확한 자막이 필요하면 `MODEL_SIZE`를 `"small"`로, 부담을 더 줄이려면 `"tiny"`로 바꾸세요.

## 설정 (코드 상단에서 직접 수정)
- `CHUNK_SECONDS`: 몇 초 단위로 잘라서 인식할지 (기본 6초, 길수록 CPU 부담↓ 반응속도↓)
- `MODEL_SIZE`: `tiny`/`base`/`small`/`medium`/`large-v3` (작을수록 가볍고 빠름, 정확도는 약간↓)

## GPU 가속을 쓰려면
기본은 CPU 모드입니다 (CUDA 없이도 바로 작동). CUDA/cuDNN이 설치되어 있다면 코드에서
```python
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8", cpu_threads=2)
```
를
```python
model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")
```
로 바꾸면 훨씬 빨라집니다.

## 자주 발생하는 문제
- **"내부 또는 외부 명령이 아닙니다" 에러**: 파일 경로에 한글/공백이 있는 경우입니다. `C:\livesub` 같은 영문 경로로 파일을 옮기세요.
- **소리를 못 잡아요**: 이어폰이 아니라 스피커로 재생 중인지 확인하세요.
- **cuda 오류**: 기본 설정은 CPU라 발생하지 않습니다. GPU 모드로 직접 바꾼 경우에만 발생하며, `device="cpu"`로 되돌리면 해결됩니다.

## 라이선스
개인 용도로 자유롭게 사용/수정하세요.
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) (OpenAI Whisper 기반), deep-translator, PyAudioWPatch 사용.

---

# English

## What is this?
Live Sub captures whatever audio your computer is playing and shows real-time Korean subtitles on screen —
useful for English courses that don't ship with subtitles.

## Features
- Works with **any site or player** — captures system audio directly, not tied to YouTube captions
- **Click-through overlay** — the subtitle box doesn't block clicks to whatever is behind it (e.g. Unreal Engine)
- **Auto device switching** — keeps working if you plug/unplug headphones
- **Multi-monitor support** — `Alt` + drag to move the overlay anywhere
- **Adjustable font size** — `Alt` + mouse wheel
- Runs 100% locally (Whisper), only translation needs internet

## Install
```bash
pip install faster-whisper deep-translator pyaudiowpatch numpy --break-system-packages
```
Windows only (uses WASAPI Loopback capture).

⚠️ Keep the script in a path with **no non-ASCII characters or spaces** (e.g. `C:\livesub\`),
or it may fail to run.

## Run
```bash
python live_subtitle_translator.py
```

## Controls
| Action | How |
|---|---|
| Move the subtitle box | Hold `Alt` + drag |
| Resize text | Hold `Alt` + scroll |
| Quit | `Ctrl+C` in the console window |

## Usage tip for DCC tools (Unreal, etc.)
Leave it running during light work (viewport navigation, following along with a lecture).
When doing something CPU-heavy (Movie Render Queue, large imports, lighting builds),
press `Ctrl+C` in the console to pause it — running Whisper and a heavy render job
at the same time can slow down the render.

## License
Free to use and modify for personal use.
Built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (OpenAI Whisper), deep-translator, PyAudioWPatch.
