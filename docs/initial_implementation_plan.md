# macOS 실시간 영어 음성 → 문장 보정 → 텍스트 에디터 삽입 설계도

## 1. 목표

MacBook M3 Pro의 내장 마이크로 들어오는 **영어 음성**을 실시간으로 받아,

1. `mlx-audio`의 `CohereLabs/cohere-transcribe-03-2026` 모델로 전사하고
2. 영어 학습자의 **머뭇거림(filler words)** 과 **문법 오류**를 줄여 자연스러운 문장으로 정리한 뒤
3. 사용자가 **마우스 커서를 올려 둔 텍스트 에디터 위치**를 기준으로 해당 문장을 자동 입력하는 프로그램을 만든다.

이 문서는 **Python 기반 macOS 앱/데몬 1차 버전**을 기준으로 작성한다. 이후 메뉴바 앱, 다른 ASR 모델, 다른 보정 모델로 확장 가능하도록 처음부터 계층을 분리한다.

---

## 2. 요구사항을 설계로 번역한 결과

### 필수 요구사항 매핑

#### 요구사항 1
> `mlx-audio`의 `CohereLabs/cohere-transcribe-03-2026` 모델을 사용. 나중에 다른 모델로 바꿀 수 있도록 scalable 하게 설계

**설계 결정**
- STT 엔진을 바로 호출하지 않고 `STTEngine` 인터페이스를 둔다.
- 현재 구현체는 `CohereMLXEngine` 하나만 만든다.
- 나중에 `WhisperMLXEngine`, `ParakeetEngine`, `RemoteASREngine` 등을 같은 인터페이스로 추가한다.

#### 요구사항 2
> 영어학습자라서 filler words가 많고 문법 오류가 있다. 이것들을 필터링하고 문법적으로 자연스러운 한 문장으로 만들어야 한다.

**설계 결정**
- 전사 결과를 바로 삽입하지 않고 `CleanupPipeline`을 둔다.
- `규칙 기반 정리` + `LLM 기반 최소 보정` 2단계로 처리한다.
- 보정은 **의미 유지**, **정보 추가 금지**, **과도한 리라이팅 금지**를 원칙으로 한다.

#### 요구사항 3
> 원하는 텍스트 에디터에 마우스 커서를 올려두면, 그 커서 지점부터 결과가 작성되어야 한다.

**설계 결정**
- 이것을 그대로 구현하려면 macOS에서 **마우스 위치 기준으로 UI 요소를 식별**하고,
  필요 시 **그 지점에 caret(삽입점)을 놓은 뒤**, 텍스트를 삽입해야 한다.
- 완전한 범용성은 어렵기 때문에 **하이브리드 방식**으로 구현한다.
  1. 마우스 위치를 anchor로 저장
  2. anchor 지점에 클릭을 보내 caret을 놓음
  3. 가장 호환성이 높은 방식인 **paste 기반 입력**을 기본으로 사용
  4. 일부 네이티브 텍스트 필드에서는 Accessibility API 기반 직접 삽입을 시도하고, 실패하면 paste로 fallback

즉, 이 요구사항은 구현상 다음처럼 해석한다.

> **“사용자가 마우스를 원하는 입력 위치에 올려두고 target arm을 실행하면, 앱은 그 위치를 기준 anchor로 기억하고, 이후 확정된 문장을 그 위치의 편집기 입력 지점에 이어서 삽입한다.”**

---

## 3. 핵심 설계 원칙

1. **문장 단위 확정 후 삽입**
   - 단어/토큰 단위로 바로 에디터에 쓰지 않는다.
   - 이유: 영어 학습자의 중간 머뭇거림, self-correction, partial STT 흔들림 때문에 결과가 지저분해진다.
   - 따라서 “잠정 partial transcript”와 “확정 final sentence”를 분리한다.

2. **실시간성보다 안정성 우선**
   - 목표는 “즉시 타이핑되는 느낌”이지 “50ms 단위 실시간 자막”이 아니다.
   - 사용자가 원하는 것은 문장 입력 자동화이므로, **발화 종료 후 0.7~1.5초 내 확정 삽입**을 목표로 한다.

3. **모듈별 교체 가능성 확보**
   - Audio capture / endpointing / STT / cleanup / insertion 을 모두 분리한다.
   - 어느 한 모델이나 기술에 종속되지 않게 한다.

4. **macOS 호환성은 하이브리드 전략으로 해결**
   - 모든 에디터가 Accessibility text API를 잘 노출하지는 않는다.
   - 따라서 “직접 삽입”과 “paste 삽입”을 둘 다 지원해야 한다.

5. **로컬 우선**
   - 기본 모드는 전부 로컬에서 동작하도록 한다.
   - 오디오나 전사 결과를 외부 API로 보내지 않는다.
   - 단, cleanup LLM만 옵션으로 외부 API를 허용할 수 있다.

---

## 4. 전체 아키텍처

```text
┌─────────────────────────────────────────────────────────────┐
│                    Control / UI Layer                      │
│  - global hotkeys                                          │
│  - menu bar or CLI control                                 │
│  - target arm / start / stop / retry                       │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Audio Capture Layer                      │
│  - sounddevice InputStream                                 │
│  - mono conversion                                          │
│  - sample-rate normalization                                │
│  - ring buffer                                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 Endpointing / Segmenter                     │
│  - VAD or pause detector                                    │
│  - pre-roll / post-roll                                     │
│  - sentence-finalization window                             │
└─────────────────────────────────────────────────────────────┘
                          │ finalized audio chunks
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                         STT Layer                           │
│  STTEngine interface                                        │
│   └─ CohereMLXEngine (current default)                      │
└─────────────────────────────────────────────────────────────┘
                          │ raw transcript
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     Cleanup Pipeline                        │
│  - disfluency filter                                        │
│  - repetition collapse                                      │
│  - grammar repair LLM                                       │
│  - minimal-style policy                                     │
└─────────────────────────────────────────────────────────────┘
                          │ cleaned sentence
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 Target Resolver / Text Injector             │
│  - capture mouse anchor                                     │
│  - resolve UI element under pointer                         │
│  - focus caret at anchor                                    │
│  - AX direct insert OR clipboard-preserving paste fallback  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Destination Text Editor                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 권장 동작 방식

### 사용 시나리오

1. 사용자가 프로그램을 켠다.
2. 사용자는 텍스트가 들어갈 에디터를 화면에 띄운다.
3. 사용자는 **마우스를 원하는 입력 위치 위에 올려둔 상태에서 “Target Arm” 단축키**를 누른다.
4. 앱은 현재 마우스 좌표와 대상 앱/에디터 정보를 저장한다.
5. 사용자가 온라인 수업 중 말한다.
6. 앱은 발화를 문장 단위로 끊어 STT 한다.
7. 결과를 filler 제거 + 문법 보정한다.
8. 확정된 문장을 anchor 위치의 에디터에 자동 삽입한다.
9. 다음 문장도 이어서 삽입한다.

### 왜 이 흐름이 좋은가

- 사용자가 **직접 타이핑하지 않아도 됨**
- partial transcript 때문에 편집기 내용이 계속 바뀌지 않음
- 머뭇거림이 제거된 **깔끔한 문장**만 입력됨
- macOS 상의 여러 에디터(TextEdit, Notes, VS Code, 브라우저 text area 등)에 대응하기 쉬움

---

## 6. 런타임 파이프라인 상세

## 6.1 Audio Capture

### 권장 구현
- 라이브러리: `sounddevice`
- 입력 장치: 기본 마이크 또는 사용자가 설정한 특정 input device
- 채널: mono
- dtype: `float32`
- preferred sample rate: `16000`
- fallback: 장치가 16k 직접 지원하지 않으면 native sample rate로 읽고 내부 resample

### 추천 설정
- block size: 20~30ms
- pre-roll buffer: 200~300ms
- max utterance length: 10~12초
- silence to finalize: 600~800ms

### 왜 이렇게 잡는가
- 너무 짧으면 segment가 잘게 쪼개진다.
- 너무 길면 전사 지연이 커지고, cleanup LLM 지연도 커진다.
- 영어 학습자의 말하기는 pause가 많기 때문에 **약 700ms 전후 endpoint**가 적절하다.

### 오디오 관련 주의점
- 온라인 수업 상대방 음성이 스피커로 새어 들어오면 앱이 상대방 말까지 전사할 수 있다.
- 가능하면 **이어폰/헤드셋** 사용을 기본 가정으로 둔다.
- 초기 버전에서는 noise reduction을 넣지 않는다.
  - 이유: 불필요한 전처리는 오히려 ASR 품질을 망칠 수 있다.
  - 정말 필요할 때만 optional plugin으로 추가한다.

---

## 6.2 Endpointing / Segmenter

이 단계의 역할은 “지금 사용자가 말이 끝났는가?”를 판단하는 것이다.

### 권장 구조

`Segmenter`는 아래 상태 머신을 가진다.

```text
IDLE
 └─(speech start detected)→ IN_SPEECH
IN_SPEECH
 ├─(silence < threshold)→ IN_SPEECH
 ├─(silence >= threshold)→ FINALIZE_SEGMENT
 └─(max_len exceeded)→ FORCE_FINALIZE
```

### 구현 선택지

#### 선택지 A. 단순 에너지 기반 pause detector
- 구현이 가장 쉽다.
- 하지만 키보드 소리, 숨소리, 주변 소음에 약하다.

#### 선택지 B. WebRTC VAD
- 가볍고 빠르다.
- MVP에 적합하다.

#### 선택지 C. Silero VAD
- 더 robust 할 가능성이 높다.
- 다만 의존성과 모델 로딩이 추가된다.

### 추천 결론
- **MVP는 WebRTC VAD 또는 단순 VAD adapter**
- 구조만 인터페이스화해서, 나중에 Silero VAD로 갈아끼울 수 있게 한다.

### Segmenter 출력

`FinalizedSegment`
- `audio: np.ndarray`
- `sample_rate: int`
- `started_at: float`
- `ended_at: float`
- `segment_id: str`

---

## 6.3 STT Layer

### 인터페이스 정의

```python
from dataclasses import dataclass
from typing import Protocol
import numpy as np

@dataclass
class Transcript:
    text: str
    language: str
    started_at: float
    ended_at: float
    segment_id: str

class STTEngine(Protocol):
    def warmup(self) -> None: ...
    def transcribe(self, audio: np.ndarray, sample_rate: int, *, started_at: float, ended_at: float, segment_id: str) -> Transcript: ...
```

### 현재 구현체: `CohereMLXEngine`

- 내부적으로 `mlx_audio.stt.load()` 로 모델 로드
- microphone chunk는 **in-memory numpy array** 로 전달
- `model.transcribe(audio_arrays=[...], sample_rates=[...], language="en", punctuation=True)` 형태를 사용

### 코드 예시

```python
from dataclasses import dataclass
import numpy as np
from mlx_audio.stt import load

@dataclass
class Transcript:
    text: str
    language: str
    started_at: float
    ended_at: float
    segment_id: str

class CohereMLXEngine:
    def __init__(self, model_id: str = "CohereLabs/cohere-transcribe-03-2026", language: str = "en"):
        self.model_id = model_id
        self.language = language
        self.model = None

    def warmup(self) -> None:
        self.model = load(self.model_id)
        silence = np.zeros(16000, dtype=np.float32)
        _ = self.model.transcribe(
            language=self.language,
            audio_arrays=[silence],
            sample_rates=[16000],
            punctuation=True,
        )

    def transcribe(self, audio: np.ndarray, sample_rate: int, *, started_at: float, ended_at: float, segment_id: str) -> Transcript:
        if self.model is None:
            raise RuntimeError("Model not loaded")

        texts = self.model.transcribe(
            language=self.language,
            audio_arrays=[audio.astype(np.float32)],
            sample_rates=[sample_rate],
            punctuation=True,
        )
        text = texts[0].strip()
        return Transcript(
            text=text,
            language=self.language,
            started_at=started_at,
            ended_at=ended_at,
            segment_id=segment_id,
        )
```

### STT 레이어 설계 포인트

1. `transcribe()` 입력은 항상 **audio array + sample_rate** 로 통일
2. 파일 경로 기반 API는 batch/offline 테스트에서만 사용
3. 모델 warmup을 startup 시점에 수행해 첫 문장 지연을 줄인다
4. 같은 인터페이스로 다른 모델을 쉽게 붙인다

### 나중에 추가 가능한 구현체

- `WhisperMLXEngine`
- `ParakeetMLXEngine`
- `FasterWhisperEngine`
- `RemoteOpenAICompatibleASREngine`

---

## 6.4 Cleanup Pipeline

이 단계가 이 프로젝트의 핵심이다. 단순 전사 앱이 아니라 **영어 학습자의 실제 발화**를 문장으로 다듬는 단계이기 때문이다.

### 목표
- `um`, `uh`, `erm`, `ah` 같은 filler 제거
- 중복된 시작어/끊김 정리
- 문법 오류 최소 수정
- 의미 추가 금지
- 너무 polished 하게 바꾸지 않기

### 권장 2단계 구조

#### 1단계. Rule-based cleanup
가볍고 deterministic 한 정리

예시:
- `um I think I can join tomorrow` → `I think I can join tomorrow`
- `I I want to ask` → `I want to ask`
- `uh can I maybe reschedule it` → `can I maybe reschedule it`

처리 규칙 예시:
- 단독 filler 제거
- 반복 whitespace 축소
- 반복 시작 토큰 제거 (`I I`, `we we`, `can can`)
- 문장 끝 punctuation normalize

#### 2단계. LLM-based minimal grammar fix
규칙 기반 정리만으로 부족한 문법을 보정

예시:
- `I want ask about yesterday homework.`
- rule pass 후 거의 그대로
- LLM 후: `I want to ask about yesterday's homework.`

### 왜 2단계로 나누는가

- filler 제거와 grammar correction을 한 번에 모두 LLM에 맡기면 latency와 비용이 커진다.
- 먼저 rule pass로 잡음을 줄이면 LLM이 더 안정적으로 동작한다.
- cleanup queue backlog가 생기면 **LLM 단계를 끄고 rule-only 모드로 degrade** 할 수 있다.

### Cleanup 인터페이스

```python
from typing import Protocol

class CleanupEngine(Protocol):
    def cleanup(self, text: str, *, previous_sentences: list[str] | None = None) -> str: ...
```

### Rule-based cleanup 예시

```python
import re

FILLERS = {
    "um", "uh", "erm", "ah", "hmm"
}

class RuleBasedCleanup:
    def cleanup(self, text: str, *, previous_sentences: list[str] | None = None) -> str:
        s = text.strip()

        # standalone fillers 제거
        s = re.sub(r"\b(?:um|uh|erm|ah|hmm)\b", " ", s, flags=re.IGNORECASE)

        # 반복 토큰 축소: I I -> I
        s = re.sub(r"\b(\w+)\s+\1\b", r"\1", s, flags=re.IGNORECASE)

        # 공백 정리
        s = re.sub(r"\s+", " ", s).strip()

        # 너무 짧으면 그대로 반환
        if not s:
            return ""

        return s
```

### LLM cleanup 권장 방식

#### 옵션 A. 로컬 MLX LLM
- 권장 기본값
- 장점: privacy / 오프라인 / 응답 일관성
- 권장 후보:
  - `mlx-community/Qwen2.5-1.5B-Instruct-4bit`
  - `mlx-community/Llama-3.2-3B-Instruct-4bit`

#### 옵션 B. 외부 API LLM
- 더 좋은 correction 품질이 필요할 때
- 단점: 네트워크 의존, 개인정보/비용 고려 필요

### 프롬프트 원칙

**절대 과도하게 rewrite 하지 말 것.**

권장 system prompt:

```text
You are a spoken-English cleanup engine for an English learner.
Your job is to minimally rewrite raw ASR text.

Rules:
1. Remove filler words like um, uh, erm when they do not change meaning.
2. Fix grammar errors.
3. Keep the original meaning.
4. Do not add new information.
5. Do not make the sentence more formal than necessary.
6. Preserve names, technical terms, and intent.
7. Return exactly one cleaned sentence and nothing else.
```

권장 user prompt 템플릿:

```text
Previous cleaned context:
- {prev_1}
- {prev_2}

Raw ASR:
{raw_text}
```

### Cleanup pipeline 조합 예시

```python
class CleanupPipeline:
    def __init__(self, rule_engine, llm_engine=None):
        self.rule_engine = rule_engine
        self.llm_engine = llm_engine

    def cleanup(self, text: str, previous_sentences: list[str] | None = None) -> str:
        text = self.rule_engine.cleanup(text, previous_sentences=previous_sentences)
        if not text:
            return ""

        if self.llm_engine is None:
            return text

        try:
            return self.llm_engine.cleanup(text, previous_sentences=previous_sentences)
        except Exception:
            # LLM 실패 시 raw insert 대신 rule-based 결과 사용
            return text
```

### 권장 정책

- 기본값: `rule + local_llm`
- backlog 발생 시: `rule_only`
- 너무 짧은 segment (`< 3 words`)는 LLM 호출 안 함
- 문장 중간이 잘린 느낌이면 다음 segment와 merge 시도 가능

---

## 6.5 Target Resolver / Text Injection

이 단계가 macOS 특화 난이도가 가장 높은 부분이다.

### 핵심 문제
사용자는 “마우스를 올려둔 위치”에 텍스트를 쓰고 싶다. 하지만 macOS에는 “임의의 화면 좌표에 그냥 문자열을 넣는다” 같은 범용 API가 없다.

따라서 아래 순서로 해결한다.

1. **마우스 좌표를 anchor로 저장**
2. 그 좌표 아래 UI element를 파악
3. 필요하면 그 좌표에 synthetic click을 보내 caret을 놓음
4. 텍스트를 삽입
   - 가능하면 AX 기반 직접 삽입
   - 안 되면 clipboard-preserving paste

### 권장 삽입 모드

#### 모드 1. `focused_editor`
- 사용자가 직접 에디터에 caret을 놓아둠
- 앱은 현재 포커스된 입력창에만 삽입
- 가장 안정적
- 하지만 요구사항 3을 100% 만족하진 않음

#### 모드 2. `hover_anchor_paste`  ← **권장 기본값**
- 사용자가 마우스를 원하는 위치에 올려두고 arm
- 앱이 그 위치를 클릭해 caret을 둠
- 이후 문장마다 paste로 삽입
- 가장 범용성 좋음

#### 모드 3. `hover_anchor_ax_direct`
- anchor 위치의 AX element를 찾고 직접 값/선택 영역에 반영 시도
- 잘 되면 포커스 전환이 줄어든다
- 앱/에디터별 편차가 크므로 fallback 필요

### 최종 권장 결론

**기본 구현은 `hover_anchor_paste` 로 가고, 내부적으로 AX direct insert를 optional optimization으로 넣는다.**

### Anchor 데이터 구조

```python
from dataclasses import dataclass

@dataclass
class TargetAnchor:
    x: float
    y: float
    pid: int | None
    bundle_id: str | None
    app_name: str | None
```

### 삽입 인터페이스

```python
class TextInjector(Protocol):
    def insert(self, text: str) -> None: ...
```

### 하이브리드 injector 동작

```text
insert(text)
 ├─ target anchor valid?
 │   └─ no → raise / show warning
 ├─ try AX direct insert
 │   └─ success → done
 ├─ else click anchor point
 ├─ do clipboard-preserving paste
 └─ restore clipboard
```

### clipboard-preserving paste 방식을 기본으로 추천하는 이유

- TextEdit, Notes, 브라우저 text area, VS Code, Electron 계열 편집기 등에서 가장 잘 먹힌다.
- AX 직접 set은 앱마다 attribute 구조가 달라 깨질 가능성이 있다.
- paste는 “현재 caret 위치에 넣는다”는 개념이 대부분의 편집기에서 동일하게 동작한다.

### clipboard-preserving paste 구현 원칙

1. 현재 클립보드를 snapshot
2. 삽입할 문자열을 클립보드에 잠깐 넣음
3. `⌘V` 전송
4. 원래 클립보드 restore

### 삽입 텍스트 formatting 정책

기본 옵션:
- 문장 끝에 punctuation 없으면 `.` 추가할지 여부: `true`
- 문장 사이 separator: `" "` 또는 `"\n"`
- 추천 기본값: `" "`

사용 케이스별 추천:
- 일반 메모장: newline mode
- 채팅 입력창 / 문장 이어쓰기: space mode

### 주의할 점

- Google Docs, Notion, Slack, 브라우저 기반 입력창은 **paste 방식이 훨씬 안전**하다.
- 터미널/특수 IDE 입력창은 per-character typing fallback이 더 잘 맞을 수 있다.
- 일부 보안 앱/원격 데스크톱 환경은 synthetic paste를 막을 수 있다.

---

## 7. macOS 권한 및 시스템 연동

### 필요한 권한

1. **Microphone 권한**
   - 내장 마이크 입력 캡처용

2. **Accessibility 권한**
   - 마우스 anchor 위치 대상 탐색
   - synthetic click / key event
   - 일부 경우 AX direct insert

### 권장 권한 체크 흐름

앱 시작 시:
1. 마이크 접근 가능 여부 확인
2. Accessibility trusted 여부 확인
3. 없으면 설정 화면 유도
4. 두 권한이 있어야만 `Start Listening` 활성화

### 구현 포인트
- `AXIsProcessTrustedWithOptions()` 로 trusted accessibility client 여부 확인
- `AXUIElementCreateSystemWide()` 로 system-wide accessibility object 획득
- `AXUIElementCopyElementAtPosition()` 으로 마우스 좌표 아래 요소 파악
- `AXUIElementSetAttributeValue()` 계열은 일부 네이티브 텍스트 필드에서만 최적화 경로로 시도

---

## 8. 추천 패키지 구조

```text
realtime_stt_writer/
├─ pyproject.toml
├─ README.md
├─ config/
│  └─ default.yaml
├─ app/
│  ├─ main.py
│  ├─ state.py
│  ├─ events.py
│  ├─ config.py
│  ├─ logging.py
│  ├─ domain/
│  │  ├─ models.py
│  │  └─ protocols.py
│  ├─ audio/
│  │  ├─ capture.py
│  │  ├─ ring_buffer.py
│  │  ├─ resampler.py
│  │  ├─ vad_base.py
│  │  ├─ vad_energy.py
│  │  ├─ vad_webrtc.py
│  │  └─ segmenter.py
│  ├─ stt/
│  │  ├─ base.py
│  │  ├─ cohere_mlx.py
│  │  └─ factory.py
│  ├─ cleanup/
│  │  ├─ base.py
│  │  ├─ rule_based.py
│  │  ├─ mlx_llm.py
│  │  ├─ remote_llm.py
│  │  └─ pipeline.py
│  ├─ inject/
│  │  ├─ base.py
│  │  ├─ anchor.py
│  │  ├─ mac_ax.py
│  │  ├─ mac_paste.py
│  │  ├─ mac_click.py
│  │  └─ hybrid_injector.py
│  ├─ control/
│  │  ├─ hotkeys.py
│  │  ├─ commands.py
│  │  └─ tray.py
│  └─ services/
│     ├─ orchestrator.py
│     └─ backlog_policy.py
└─ tests/
   ├─ unit/
   ├─ integration/
   └─ manual/
```

---

## 9. 설정 파일 예시

```yaml
app:
  language: en
  mode: local
  log_level: INFO

audio:
  device: default
  channels: 1
  preferred_sample_rate: 16000
  block_ms: 30
  pre_roll_ms: 250
  max_segment_sec: 12

endpointing:
  engine: webrtcvad
  start_speech_ms: 90
  end_silence_ms: 700
  force_finalize_sec: 12

stt:
  engine: cohere_mlx
  model_id: CohereLabs/cohere-transcribe-03-2026
  language: en
  punctuation: true

cleanup:
  enabled: true
  mode: local_llm
  remove_fillers: true
  fix_grammar: true
  use_context: true
  context_size: 2
  llm:
    engine: mlx_lm
    model_id: mlx-community/Qwen2.5-1.5B-Instruct-4bit
    temperature: 0.0
    max_tokens: 80

injection:
  mode: hybrid
  separator: " "
  append_terminal_punctuation: true
  restore_clipboard: true
  click_before_insert: true
  direct_ax_first: true

hotkeys:
  start_stop: "alt+cmd+s"
  arm_target: "alt+cmd+a"
  retry_last_insert: "alt+cmd+r"
  pause_insertion: "alt+cmd+p"
```

---

## 10. 권장 동시성 모델

### 왜 멀티스레드/큐 구조가 필요한가

- audio callback 안에서 STT를 돌리면 오디오 드롭이 발생한다.
- cleanup LLM이 느려질 수 있다.
- injection은 OS 이벤트이므로 타이밍이 민감하다.

### 추천 구조

```text
audio callback thread
  → raw_audio_queue
segmenter worker
  → finalized_segment_queue
stt worker
  → transcript_queue
cleanup worker
  → cleaned_text_queue
inject worker
```

### 권장 정책
- 각 queue에 `maxsize` 설정
- backlog가 쌓이면 cleanup을 `rule_only` 로 degrade
- inject 실패 시 last message 보관 후 retry 가능

---

## 11. 오케스트레이터 설계

```python
class AppOrchestrator:
    def __init__(self, capture, segmenter, stt_engine, cleanup_pipeline, injector):
        self.capture = capture
        self.segmenter = segmenter
        self.stt_engine = stt_engine
        self.cleanup_pipeline = cleanup_pipeline
        self.injector = injector
        self.previous_sentences: list[str] = []

    def on_finalized_segment(self, segment):
        transcript = self.stt_engine.transcribe(
            segment.audio,
            segment.sample_rate,
            started_at=segment.started_at,
            ended_at=segment.ended_at,
            segment_id=segment.segment_id,
        )

        if not transcript.text.strip():
            return

        cleaned = self.cleanup_pipeline.cleanup(
            transcript.text,
            previous_sentences=self.previous_sentences[-2:],
        )

        if not cleaned:
            return

        self.injector.insert(cleaned)
        self.previous_sentences.append(cleaned)
        self.previous_sentences = self.previous_sentences[-10:]
```

### 중복 삽입 방지

같은 segment가 두 번 처리될 수 있으니 아래를 둔다.
- `last_inserted_segment_id`
- `last_inserted_text_hash`

둘 중 하나라도 같으면 skip

---

## 12. 문장 정리 정책 상세

### “문법적 오류 없이 만들어달라”의 해석

이 요구는 강하지만, 실제 구현에서는 **의미를 바꾸지 않는 최소 수정**이 가장 중요하다.

### 권장 우선순위

1. filler 제거
2. obvious grammar fix
3. punctuation normalize
4. subject/verb agreement fix
5. article/preposition fix
6. contraction/표현 polishing은 최소한만

### 하지 말아야 할 것
- 사용자가 말하지 않은 내용을 보태기
- 너무 원어민스러운 문장으로 완전히 재작성하기
- 학습자 의도를 바꾸기
- 질문을 진술문으로 바꾸기

### 예시

#### 예시 1
Raw:
`um I want ask about the homework that we did yesterday`

Cleaned:
`I want to ask about the homework we did yesterday.`

#### 예시 2
Raw:
`uh can I maybe move our meeting to next Tuesday`

Cleaned:
`Can I move our meeting to next Tuesday?`

#### 예시 3
Raw:
`I was, uh, thinking maybe I should finish this first`

Cleaned:
`I was thinking maybe I should finish this first.`

---

## 13. Text insertion 전략 상세

## 13.1 가장 현실적인 기본 전략

### Arm 단계
- 사용자가 마우스를 원하는 입력 위치에 둠
- `arm_target()` 실행
- 현재 마우스 좌표 저장
- 가능한 경우 좌표 아래 AX element, PID, bundle id 저장

### Insert 단계
- anchor 좌표로 synthetic click
- caret placement 확인 또는 짧은 wait
- text paste
- clipboard restore

### 왜 이 방식이 필요한가
- “마우스 커서가 놓인 지점부터 입력”이라는 UX를 가장 직접적으로 만족한다.
- 많은 편집기에서 클릭이 caret 위치를 결정한다.
- 이후 paste는 에디터 종류와 상관없이 잘 먹힌다.

## 13.2 Fallback 계층

1. `AX direct insert`
2. `click + paste`
3. `focus + per-character typing`

### fallback 3가 필요한 이유
- 터미널류, 일부 게임/원격 환경, 보안 입력창에서는 paste가 막힐 수 있다.

---

## 14. 추천 UI/UX

### MVP UI
- CLI + global hotkeys
- 상태 로그를 터미널에 표시

### 추천 hotkeys
- `⌥⌘S`: start/stop listening
- `⌥⌘A`: arm target at mouse position
- `⌥⌘R`: retry last insertion
- `⌥⌘P`: pause/resume insertion

### 2차 버전 UI
- macOS 메뉴바 앱
- 현재 상태 표시
  - `Idle`
  - `Listening`
  - `Speech detected`
  - `Transcribing`
  - `Inserted`
  - `Error`
- 마지막 raw / cleaned 문장 미리보기

### preview overlay는 optional
- partial transcript를 작게 보여줄 수는 있다.
- 하지만 **에디터 삽입은 final sentence만** 해야 한다.

---

## 15. 초기 구현 범위(MVP)

### 반드시 포함
- live microphone capture
- sentence endpointing
- Cohere MLX STT adapter
- filler removal + grammar correction
- mouse-hover target arm
- click + paste insertion
- accessibility permission check
- retry last sentence

### MVP에서는 과감히 제외 가능
- diarization
- speaker separation
- noise reduction
- partial transcript overlay
- background AX direct insert advanced optimization
- multi-language auto-detect
- auto-save transcript history UI

---

## 16. 단계별 구현 계획

## Phase 1. Cohere STT 단독 검증

### 목표
녹음된 wav 또는 numpy array를 `CohereLabs/cohere-transcribe-03-2026` 로 전사하는 최소 기능 검증

### 작업
1. 가상환경 생성
2. `mlx-audio` 설치
3. 모델 다운로드/로딩 테스트
4. 짧은 WAV 파일 전사
5. numpy in-memory audio array 전사
6. warmup 시간/첫 호출 시간 측정

### 완료 기준
- `audio_arrays=[numpy_array]` 경로가 안정적으로 동작
- 영어 전사가 정상 출력

---

## Phase 2. 마이크 실시간 입력 캡처

### 목표
내장 마이크에서 실시간 PCM을 받아 queue에 쌓기

### 작업
1. `sounddevice.InputStream` 구성
2. mono/float32 변환
3. 16k 우선 요청
4. 장치 미지원 시 resample fallback
5. ring buffer 구성
6. 로그로 RMS/packet size 확인

### 완료 기준
- 5분 이상 실행해도 오디오 드롭 없이 동작
- capture callback에서 blocking 작업이 없음

---

## Phase 3. Endpointing 추가

### 목표
음성을 문장 단위 segment로 finalize

### 작업
1. `VADAdapter` 인터페이스 설계
2. 에너지 기반 또는 WebRTC VAD MVP 구현
3. pre-roll/post-roll 처리
4. silence threshold 튜닝
5. max segment forced flush 구현

### 완료 기준
- 일반적인 영어 한 문장이 1개 segment로 안정적으로 분리됨
- 너무 짧은 잡음 segment가 과도하게 생기지 않음

---

## Phase 4. STT 파이프라인 연결

### 목표
finalized segment가 바로 전사되도록 연결

### 작업
1. `Segmenter -> STT worker` 큐 연결
2. segment metadata ìnscript skip
4. 중복 segment 방지 키 추가

### 완료 기준
- 실제 말하면 문장 단위 raw transcript가 로그에 나옴

---

## Phase 5. Cleanup pipeline 구축

### 목표
raw transcript를 영어 학습자용 문장으로 정리

### 작업
1. filler list 및 repetition rule 구현
2. `RuleBasedCleanup` 테스트 추가
3. `LocalMLXLLMCleanup` 구현
4. minimal rewrite prompt 설계
5. timeout / fallback 정책 구현
6. backlog 시 rule-only degrade 구현

### 완료 기준
- filler/ëw speech가 자연스러운 1문장으로 바뀜
- LLM 실패 시에도 서비스가 죽지 않음

---

## Phase 6. macOS target anchor + insertion

### 목표
마우스 위치를 기준으로 자동 입력

### 작업
1. Accessibility trusted 여부 체크
2. 현재 마우스 좌표 획득
3. `arm_target()` 구현
4. anchor point synthetic click 구현
5. clipboard snapshot/restore 구현
6. paste injection 구현
7. retry last insert 구현

### 완료 기준
- TextEdit에서 안정적으로 동작
- VStext area에서도 최소 1개 이상 성공

---

## Phase 7. 전체 오케스트레이션 및 hotkeys

### 목표
사용자가 실제로 쓸 수 있는 end-to-end 앱 완성

### 작업
1. global hotkeys 연결
2. 상태 머신 도입
3. start/stop/pause/arm/retry 명령 정리
4. 로그 및 에러 알림 정리
5. 설정 파일 로딩

### 완료 기준
- 사용자가 앱 실행 후 hotkey만으로 실제 온라인 수업 중 사용 가능

---

## Phase 8. 하드닝

### 목표
실사용 안정성 향ì### 작업
1. queue overflow 보호
2. injector 실패 시 fallback 강화
3. 긴 발화 처리 개선
4. duplicate insertion 방지 강화
5. manual test matrix 작성
6. 성능 프로파일링

### 완료 기준
- 30분 이상 사용해도 치명적 중단 없음

---

## 17. 권장 의존성

```bash
pip install "mlx-audio[stt]"
pip install sounddevice numpy pyyaml pydantic
pip install mlx-lm
pip install pyobjc-framework-AppKit pyobjc-framework-Quartz pyobjc-framework-ApplicationServices
# endpointing êip install webrtcvad-wheels
```

### 선택 의존성
- `silero-vad` : 더 robust한 endpointing 실험용
- `rich` : CLI 상태 출력 개선
- `rumps` 또는 PyObjC 상태바 구현용 패키지 : 메뉴바 앱 확장용

---

## 18. 테스트 전략

## 18.1 Unit test

### audio/segmenter
- silence only 입력
- 짧은 speech burst
- 긴 speech + forced flush
- pre-roll 동작 확인

### cleanup
- filler 제거 케이스
- 반복 토큰 제거 케이스
- punctuation normalize
- LLM timeout fallback


- clipboard snapshot/restore
- empty text skip
- duplicate insert guard

## 18.2 Integration test

- prerecorded wav → STT → cleanup
- microphone live → segmenter → STT
- cleaned sentence → TextEdit insert

## 18.3 Manual acceptance test matrix

최소 아래 편집기 4종 확인 권장:
- TextEdit
- Apple Notes
- VS Code
- Chrome/Safari text area

가능하면 추가:
- Google Docs
- Notion
- Slack 입력창

---

## 19. 실패 시 fallback 정책

### STT 실패
- 해당 segment skip
- 사용ì비스는 계속 유지

### Cleanup LLM 실패
- rule-based 결과만 삽입

### AX direct insert 실패
- click + paste fallback

### paste 실패
- per-character typing fallback 또는 insertion queue 보류

### focus loss
- 다음 insert 시 anchor re-click

---

## 20. 성능 최적화 포인트

1. startup 시 STT 모델 warmup
2. cleanup LLM도 startup warmup
3. segment 길이를 2~6초 중심으로 유지
4. 긴 segment는 forced finalize
5. partial transcript는 로그/overlay 전용으로만6. inject는 메인 스레드 또는 OS 이벤트 전송 전용 worker로 분리

### backlog 대응
- cleanup queue 길이 > 2 이면 `rule_only`
- segment queue 길이 > 3 이면 가장 오래된 partial 성격 segment drop 고려

---

## 21. 이후 확장 방향

### 1) 더 나은 문장화
- 2문장 이상 발화를 문맥적으로 분할
- 질문/진술 자동 punctuation 개선

### 2) partial preview overlay
- 확정 전 문장 후보를 작은 HUD에 띄우기

### 3) transcript history
- raw / cle 저장해서 학습 복기 자료로 사용

### 4) learner mode
- cleanup 강도 조절
  - `minimal`
  - `balanced`
  - `polished`

### 5) model hot-swap
- config 변경만으로 ASR/LLM 교체

### 6) macOS native app 포장
- Python backend 유지
- Swift/PyObjC wrapper로 메뉴바 앱화

---

## 22. 실전 구현 시 가장 중요한 판단 요약

### 반드시 지킬 것
- **에디터 삽입은 final sentence만**
- **cleanup은 의미 보존이 최우선**
- **injection은 paste fallback이 핵ì **모든 단계는 queue 기반 비동기 처리**
- **STT/cleanup/injector를 인터페이스로 분리**

### 가장 추천하는 MVP 조합
- Audio: `sounddevice`
- Endpointing: `WebRTC VAD` 또는 단순 pause detector
- STT: `mlx-audio + CohereLabs/cohere-transcribe-03-2026`
- Cleanup: `RuleBasedCleanup + local MLX LLM`
- Insert: `hover anchor + click + clipboard-preserving paste`
- Control: `CLI + hotkeys`

---

## 23. Coding Agent에게 바로 넘길 수 있는 구현 지시문

아래 순서대로면 된다.

```text
1. Create a Python project for macOS only.
2. Add a pluggable STT engine interface and implement CohereMLXEngine using mlx-audio with model CohereLabs/cohere-transcribe-03-2026.
3. Build microphone capture with sounddevice using non-blocking callback and queue.
4. Add segment finalization using a VAD/pause detector with pre-roll, post-roll, and max segment duration.
5. Build a cleanup pipeline with:
   - rule-based filler removal
   - repetition collapse
   - optional MLX-LM grammar corn
6. Add a macOS target anchor service that captures mouse position on hotkey.
7. Add a text injector that:
   - tries direct accessibility insertion first
   - falls back to click + clipboard-preserving paste
8. Add global hotkeys for start/stop, arm target, retry insertion, and pause.
9. Keep all heavy work off the audio callback thread.
10. Add logging, error handling, queue backpressure rules, and duplicate insertion guards.
11. Verify end-to-end behavior in TextEdit first, then VS Code, then browser text areas.
```

---

## 24. 참고 구현 메모

### arm_target 동작 개념

```python
class TargetAnchorService:
    def arm_from_current_mouse_position(self) -> TargetAnchor:
        # 1. read current mouse location
        # 2. find UI element under pointer if possible
        # 3. store x, y, pid, bundle_id
        # 4. return TargetAnchor
        ...
```

### insert 동작 개념

```python
class HybridInjector:
    def __init__(self, ax_injector, paste_injector, clicker, anchor_service):
        selr = ax_injector
        self.paste_injector = paste_injector
        self.clicker = clicker
        self.anchor_service = anchor_service

    def insert(self, text: str) -> None:
        anchor = self.anchor_service.get_active_anchor()
        if anchor is None:
            raise RuntimeError("Target is not armed")

        if self.ax_injector.try_insert(text, anchor):
            return

        self.clicker.click(anchor.x, anchor.y)
        self.paste_injector.insert(text)
```

### separator 처리 개념hon
def format_for_insert(text: str, separator: str = " ", add_terminal_punctuation: bool = True) -> str:
    s = text.strip()
    if not s:
        return ""

    if add_terminal_punctuation and s[-1] not in ".?!":
        s += "."

    return s + separator
```

---

## 25. 최종 결론

이 프로젝트의 가장 현실적이고 확장 가능한 설계는 아래 한 줄로 정리된다.

> **“마이크 입력을 문장 단위로 finalize → Cohere MLX STT로 전사 → rule+LLM으로 filler 제거와 최소 문법 보정 → 마우스 anchor 지점의 에디터에 click+paste 중심으로 삽입하는 하이브리드 macOS 앱”**

핵심은 다음 3가지다.

1. **STT와 cleanup을 분리할 것**
2. **에디터 삽입은 partial이 아니라 final sentence 기준일 것**
3. **macOS 입력은 AX direct insert만 믿지 말고 paste fallback을 기본 전략으로 둘 것**

이 구조로 시작하면, 나중에 ASR 모델 교체, 문법 교정 모델 교체, 메뉴바 앱화, transcript history 저ì© 분석 기능 추가까지 자연스럽게 확장할 수 있다.

---

## 26. References

- https://github.com/Blaizzy/mlx-audio
- https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/stt/models/cohere_asr/README.md
- https://huggingface.co/CohereLabs/cohere-transcribe-03-2026
- https://github.com/ml-explore/mlx-lm
- https://developer.apple.com/documentation/applicationservices/1459186-axisprocesstrustedwithoptions
- https://developer.apple.com/documentation/applicationservices/1462095-axuielementcremwide
- https://developer.apple.com/documentation/applicationservices/1462077-axuielementcopyelementatposition
- https://developer.apple.com/documentation/applicationservices/1460434-axuielementsetattributevalue

