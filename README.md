# Claude 사용량 위젯

claude.ai(Pro/Max) 세션/주간 사용량과 크레딧을 화면에 항상 표시해주는 위젯 모음입니다.

- [`desktop/`](desktop/) — Windows 데스크톱 위젯 (Python/Tkinter). 자세한 내용은 [desktop/README.md](desktop/README.md) 참고.
- [`android/`](android/) — 안드로이드 앱. 상단 알림바에 상시 표시 + 홈화면 위젯. 자세한 내용은 [android/README.md](android/README.md) 참고.

## ⚠ 공통 안내

두 앱 모두 Anthropic이 공식 지원하지 않는 방식(claude.ai가 내부적으로 쓰는 비공식 API)을 사용합니다. Anthropic이 내부 구조를 바꾸면 언제든 동작이 멈출 수 있습니다.

로그인 세션 쿠키(`sessionKey`)를 사용하며, 이 값은 각 플랫폼의 안전한 저장소에만 암호화 저장되고(Windows Credential Manager / Android Keystore) 오직 `claude.ai`로만 전송됩니다. 그 외 어떤 서버로도 전송되지 않습니다.
