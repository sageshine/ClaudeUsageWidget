# Claude 사용량 위젯 (Android)

claude.ai(Pro/Max) 세션/주간 사용량을 상단 알림바에 상시 표시하고, 홈화면 위젯으로도 볼 수 있는 안드로이드 앱입니다. [`../desktop`](../desktop)의 Windows 위젯과 로직(사용량 계산, null 재설정시각 처리 등)을 그대로 포팅했습니다.

## 빌드

```
./gradlew assembleDebug
```

`app/build/outputs/apk/debug/app-debug.apk`가 생성됩니다. 서명 없는 디버그 빌드라 사이드로드(직접 설치) 전용입니다.

## 구조

- `SecureStore` — sessionKey/Organization ID를 Android Keystore 기반 EncryptedSharedPreferences에 저장
- `ApiClient` — claude.ai usage API 호출/파싱
- `WidgetStateCalculator` — 퍼센트/무드/재설정 카운트다운 계산
- `UsageForegroundService` — 3분마다 갱신, 알림바에 표시 (Android 13+에서 스와이프로 지워도 즉시 재게시)
- `UsageWidgetProvider` — 홈화면 위젯 (큰 글씨로 퍼센트 표시)
- `MainActivity` — sessionKey/Organization ID 입력 + 비공식 API 사용 고지

## sessionKey 쿠키 가져오는 법

desktop 위젯과 동일합니다 — [`../desktop/README.md`](../desktop/README.md) 참고.
