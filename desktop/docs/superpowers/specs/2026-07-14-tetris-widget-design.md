# 테트리스 위젯 UI — 설계 문서

- 작성일: 2026-07-14
- 상태: 승인됨

## 배경 / 목적

기존 둥근 캐릭터 위젯(`CharacterWidget`, 40~60px 원형, 표정/색으로 무드 표시)을 더 귀엽고 눈에 띄는 형태로 바꾼다. 사용자가 제시한 3가지 아이디어(컵에 물 채우기 / 좌우로 달리기 / 테트리스 쌓기+게임오버) 중 테트리스 쌓기를 선택했다.

**범위**: 기존 원형 위젯을 완전히 대체한다 (설정에서 고르는 디자인 옵션이 아님). `widget.py`만 새로 작성하고, `widget_state.py`(무드/임계값 계산)와 `app.py`의 오케스트레이션 로직은 그대로 재사용한다 — 이미 계산되어 있는 `WidgetState.headline_percent`(세션%·주간% 중 큰 값)를 블록 쌓기 기준으로 그대로 쓴다.

## 보드 규격

- 세로 10칸 컬럼 보드. 1칸 = 10%. `headline_percent`를 10으로 나눠 올림한 값만큼 아래부터 칸을 채운다 (예: 65% → 7칸).
- `headline_percent`는 0~100으로 클램프한다 (API가 100을 넘는 값을 주더라도 — 실제로 크레딧 필드는 108%까지 관측된 적 있음 — 보드 칸 수 계산에는 100을 상한으로 쓴다).
- 보드 크기: 폭 40px, 높이 100px 내외 (칸당 폭 36px, 높이 10px 안팎) — 기존 위젯과 비슷한 화면 점유 면적을 유지한다.

## 칸 색상 (기존 무드 임계값 재사용)

`WidgetState`가 이미 갖고 있는 임계값 정보를 그대로 쓴다 — `widget_state.py`의 `compute_widget_state`가 참조하는 `thresholds`(warning/danger)를 그대로 앱 설정에서 가져와 위젯에 전달한다:

- 칸의 "높이 기준 사용량"이 warning 임계값 미만 구간 → 파랑 (`MOOD_COLORS[Mood.CALM]`)
- warning 이상 danger 미만 구간 → 노랑 (`MOOD_COLORS[Mood.WARNING]`)
- danger 이상 구간 → 빨강 (`MOOD_COLORS[Mood.DANGER]`)

즉 칸마다 자기 위치(몇 %에 해당하는 칸인지)를 기준으로 색이 계단식으로 바뀐다. 위젯 전체의 무드/이모지 개념(`Mood` enum)은 더 이상 표정으로 그리지 않지만, 색상 팔레트는 그대로 재사용해 일관성을 유지한다.

## 애니메이션

- **채워질 때(사용량 증가)**: 이전에 그렸던 칸 수보다 목표 칸 수가 많으면, 늘어난 칸만큼 위에서 아래로 "톡" 떨어지는 애니메이션을 순차 재생한다 (칸당 약 0.3~0.5초, `after()`로 스케줄링). 진행 중 새 `apply_state` 호출이 들어오면 현재 애니메이션을 중단하고 새 목표로 즉시 재계산한다 (안 그러면 애니메이션 큐가 밀릴 수 있음).
- **비워질 때(한도 리셋으로 사용량 감소)**: 애니메이션 없이 즉시 목표 칸 수로 다시 그린다. 리셋은 순간적 이벤트이므로 자연스러운 연출이 필요 없다.
- 위젯 생성 직후 첫 `apply_state` 호출은 항상 애니메이션 없이 즉시 그린다 (시작할 때부터 블록이 튀는 건 어색함).

## GAME OVER

- `headline_percent >= 100`이면 보드 위에 반투명 오버레이 + "GAME OVER" 텍스트를 표시한다.
- claude.ai에서 실제로 한도가 리셋되어 다음 새로고침 때 `headline_percent < 100`이 되면 오버레이가 자동으로 사라지고 보드가 비워진다 (위 "비워질 때" 규칙 적용).
- 오버레이가 떠 있는 동안에도 드래그·우클릭 상세패널·트레이 메뉴는 평소처럼 동작한다 (인터랙션을 막지 않음).

## 인터페이스 (기존 유지 vs 변경)

**그대로 유지**:
- `CharacterWidget(root, initial_pos, on_move, on_right_click)` 생성자 시그니처
- `.apply_state(state: WidgetState) -> None`
- `.top`(`tk.Toplevel`), 드래그, 우클릭 콜백, 호버 툴팁 동작

**변경**:
- `CharacterWidget.SIZE`(정사각형 가정) → `CharacterWidget.WIDTH`, `CharacterWidget.HEIGHT`로 분리
- `app.py`의 `_on_widget_right_click`에서 상세패널 세로 위치를 잡을 때 쓰던 `CharacterWidget.SIZE` 참조를 `CharacterWidget.HEIGHT`로 1줄 수정

**`widget_state.py`/그 외 `app.py` 로직은 변경 없음** — `WidgetState.headline_percent`와 앱 설정의 `thresholds` 딕셔너리를 그대로 위젯에 전달하면 되므로, 위젯이 필요로 하는 정보는 이미 다 갖춰져 있다.

`apply_state`의 시그니처를 `apply_state(state: WidgetState, thresholds: dict) -> None`으로 확장한다 (생성자에서 한 번만 받아 보관하는 대신 매번 인자로 받는다 — 사용자가 설정에서 임계값을 바꾸면 다음 새로고침 때 곧바로 반영되어야 하는데, 위젯은 `App.__init__`에서 한 번만 생성되므로 생성자 보관 방식은 임계값 변경이 반영되지 않는 문제가 생긴다). `app.py`의 호출부(`_apply_state` 등, 이미 `self.config["thresholds"]`를 갖고 있음)에서 `self.widget.apply_state(state, self.config["thresholds"])`처럼 인자를 하나 추가하는 배선 변경이 필요하다.

## 테스트

- 색상 밴딩 로직(칸 인덱스 → warning/danger 임계값 기준 색상 결정)은 순수 함수로 분리해 유닛 테스트 가능하게 만든다 (Tkinter 없이 테스트).
- 칸 수 계산(`headline_percent` → 채워진 칸 수, 클램프 포함)도 순수 함수로 분리해 유닛 테스트.
- GAME OVER 오버레이 표시 여부(`headline_percent >= 100`)도 순수 함수로 분리 가능.
- Tkinter 위젯 자체(드래그, 우클릭, 실제 캔버스 렌더링)는 기존 `test_widget.py`와 같은 방식으로 실제 디스플레이에서 검증한다 (애니메이션 타이밍 자체를 유닛 테스트하진 않고, 목표 칸 수/색상 배열이 최종적으로 캔버스에 반영되는지만 확인).

## 범위가 아닌 것

- 실제 테트리스 게임플레이(여러 모양의 테트로미노, 회전, 줄 삭제)는 만들지 않는다. "단일 컬럼에 칸이 쌓이는" 시각적 은유일 뿐이다.
- 설정에서 디자인을 고르는 기능은 넣지 않는다 (완전 교체).
