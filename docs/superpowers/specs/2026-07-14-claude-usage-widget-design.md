# Claude 사용량 위젯 — 설계 문서

- 작성일: 2026-07-14
- 상태: 승인됨 (v2, 축소 범위)

## 배경 / 목적

claude.ai 데스크톱 앱 설정 > 사용량 화면에는 다음 정보가 표시된다:

- 현재 세션 사용률(%) 및 리셋까지 남은 시간 (5시간 롤링 윈도우)
- 주간 한도(%) — 모든 모델 기준, 그리고 개별 모델(예: Fable) 기준. 매주 지정 요일에 리셋
- 사용 크레딧(옵션) — 한도 초과 시 추가 과금되는 크레딧의 사용액/비율

이 화면을 보려면 매번 앱을 열고 설정 > 사용량으로 들어가야 한다. 이 정보를 항상 떠있는 작은 데스크톱 위젯으로 미러링해서, 클릭 없이 바로 확인할 수 있게 한다.

**범위가 아닌 것** (검토 후 제외):
- Admin API(조직 관리자 API 키) 기반 조직 전체 비용 조회 — 별도 과금 체계라 이 프로젝트의 목적(개인 Pro/Max 한도 확인)과 무관
- Claude Code 로컬 세션 로그의 토큰/비용 집계 — Claude Code가 claude.ai(Pro/Max) 계정으로 로그인되어 있어 세션/주간 한도를 이미 공유하므로, 별도로 계산할 필요 없음

## 데이터 소스

claude.ai가 설정 > 사용량 화면을 렌더링할 때 호출하는 내부(비공식) API를 그대로 호출한다. Anthropic이 공식적으로 문서화하거나 지원하는 API가 아니며, 다음 특성을 가진다:

- 인증: 브라우저의 `sessionKey` 쿠키 값 (httpOnly라 JS로는 못 읽음 — 로그인 후 브라우저 개발자도구 > Application > Cookies에서 사용자가 직접 복사)
- organization ID: `lastActiveOrg` 쿠키 값 그대로 사용 (수동 입력 불필요, 위젯이 쿠키를 못 읽는 경우를 대비해 설정에 수동 입력란은 남겨둠)
- **엔드포인트 확정**: `GET https://claude.ai/api/organizations/{org_id}/usage` (실제 로그인 세션으로 확인 완료, 2026-07-14)
- **응답 JSON 구조** (필요한 필드만):
  ```json
  {
    "five_hour": { "utilization": 9, "resets_at": "2026-07-14T09:00:00Z" },
    "seven_day": { "utilization": 17, "resets_at": "2026-07-19T02:00:00Z" },
    "limits": [
      { "kind": "session", "percent": 9, "resets_at": "...", "severity": "normal" },
      { "kind": "weekly_all", "percent": 17, "resets_at": "...", "severity": "normal" },
      { "kind": "weekly_scoped", "percent": 19, "resets_at": "...", "scope": { "model": { "display_name": "Fable" } }, "severity": "normal" }
    ],
    "spend": {
      "enabled": false,
      "percent": 0,
      "used": { "amount_minor": 0, "currency": "USD", "exponent": 2 },
      "limit": null
    }
  }
  ```
  - 세션 % = `five_hour.utilization` (또는 `limits[kind=session].percent`, 동일 값)
  - 주간(전체 모델) % = `seven_day.utilization` (또는 `limits[kind=weekly_all].percent`)
  - 주간(개별 모델) % = `limits[kind=weekly_scoped]` — 여러 개 있을 수 있음(모델별로), `scope.model.display_name`으로 구분
  - 크레딧 = `spend.enabled`가 true일 때만 `spend.percent`, `spend.used`, `spend.limit` 사용
- 요청 시 `Cookie: sessionKey=<값>` 헤더만 실어 보내면 됨 (다른 인증 헤더 불필요)
- 언제든 Anthropic이 내부 구조를 바꾸면 깨질 수 있는 비공식 방식이라는 점을 README와 앱 내 안내에 명시

## 아키텍처

- **언어/런타임**: Python 3.11+, 단일 상주 프로세스
- **위젯 UI**: Tkinter (Toplevel, 테두리 없음, 항상 위, 반투명 배경) — 원형 캐릭터 아이콘
- **트레이 아이콘**: pystray — 우클릭 메뉴(설정 열기 / 종료), 작업표시줄에서 위젯 숨김·표시 토글
- **설정 저장**: `%APPDATA%\ClaudeUsageWidget\config.json` — 새로고침 주기, 위젯 위치, 크레딧 표시 여부, 자동시작 여부 등 비민감 값만 저장
- **비밀값 저장**: `sessionKey` 쿠키 값은 `keyring` 라이브러리를 통해 Windows Credential Manager에 암호화 저장. 평문 파일에 절대 저장하지 않음
- **패키징**: PyInstaller `--onefile --windowed` → `ClaudeUsageWidget.exe` 단일 실행파일
- **자동 시작**: 최초 실행 시 "PC 켜질 때 자동으로 시작할까요?" 확인 후, 동의 시 `shell:startup` 폴더에 바로가기 생성 (설정에서 언제든 켜고 끌 수 있음)

## 데이터 흐름

1. 백그라운드 타이머(기본 3분, 설정에서 조절 가능)가 주기적으로 내부 API 호출
2. 응답을 파싱해 세션 %, 세션 리셋 시각, 주간(전체 모델) %, 주간(개별 모델) %, 주간 리셋 시각, (옵션) 크레딧 사용액/비율을 추출
3. 위젯 상태 갱신: `max(세션 %, 주간 전체 %)` 값을 기준으로 캐릭터 표정/색 결정
   - < 60%: 평온(파랑, 🙂)
   - 60~85%: 주의(노랑, 😐)
   - > 85%: 위험(빨강, 😰)
   - 임계값은 설정에서 조정 가능
4. "마지막 업데이트: n분 전" 텍스트도 함께 갱신 (그림 속 화면과 동일)
5. 우클릭 시 상세 패널에 세션/주간(전체)/주간(개별 모델)/크레딧 막대를 그림과 동일한 레이아웃으로 표시

## 위젯 UI

- 40~60px 원형 캐릭터, 화면 우하단 기본 위치, 드래그로 이동 가능 (위치는 config에 저장되어 다음 실행 시 유지)
- 좌클릭/호버: 요약 툴팁 (예: "세션 6% · 주간 16%")
- 우클릭: 상세 패널 팝업 — 사용량 막대 + 새로고침 버튼 + 설정 버튼 + 종료
- 트레이 아이콘: 항상 유지, 위젯 표시/숨김 토글 및 설정/종료 메뉴 제공

## 설정 화면

- `sessionKey` 쿠키 입력 필드 (+ 가져오는 방법 안내: F12 개발자도구 > Application > Cookies)
- organization ID 입력 필드 (자동 감지 실패 시 수동 입력)
- 새로고침 주기 조절 (기본 3분, 최소 1분)
- 캐릭터 상태 임계값(평온/주의/위험 경계값) 조절
- 크레딧 표시 on/off
- 자동 시작 등록 체크박스

## 에러 처리

- `sessionKey`가 만료되었거나 유효하지 않으면 위젯에 "⚠ 재로그인 필요" 표시, 상세 패널에서 재입력 유도. 앱 전체가 죽지 않음
- 네트워크 오류/일시적 실패 시 마지막으로 성공한 값을 유지하며 조용히 재시도 (지수 백오프, 최대 간격 15분)
- API 응답 구조가 예상과 다르면(Anthropic 내부 변경) 파싱 실패를 로그 파일(`%APPDATA%\ClaudeUsageWidget\log.txt`)에 기록하고, 트레이 풍선 알림으로 1회만 사용자에게 알림 (스팸 방지)

## 보안 고지

- `sessionKey` 쿠키는 사실상 로그인 세션 자체와 동급의 민감 정보 — 탈취되면 계정에 접근 가능. 로컬 암호화 저장소에만 보관하고, 오직 claude.ai로만 요청을 보내며, 어떤 원격 서버로도 전송하지 않는다는 점을 README에 명확히 고지
- 이 방식은 Anthropic의 공식 지원을 받지 않는 비공식 방식이며, 서비스 약관과 관련해 사용자 본인의 책임하에 사용한다는 점을 최초 실행 시 안내 문구로 표시

## 테스트/검증

- API 파서: 실제(또는 캡처해둔 샘플) 응답 JSON으로 세션/주간/크레딧 값 추출 유닛 테스트
- 위젯 렌더링/드래그/상태 전환(평온→주의→위험): 수동 스크린샷 확인
- 자격 증명 저장/로드: Credential Manager 저장 후 재시작해도 값이 유지되는지 확인
- 에러 경로: 쿠키를 일부러 잘못된 값으로 넣어 "재로그인 필요" 표시와 앱 생존 확인
- 최종 빌드: PyInstaller로 만든 `.exe`를 더블클릭 실행해 정상 동작 확인, 자동 시작 등록/해제 확인

## 구현 순서 (다음 단계 plan에서 상세화)

1. API 클라이언트 + 로컬 파서/캐시 구현 (엔드포인트/응답 구조는 확정됨, 위 참고)
2. Tkinter 위젯 + pystray 트레이 아이콘 구현
3. 설정 화면 + Credential Manager 연동
4. 에러 처리/재시도 로직
5. PyInstaller 패키징 + 자동 시작 등록
6. 수동 테스트 및 사용자 검수
