# Claude 사용량 위젯

claude.ai(Pro/Max) 세션/주간 사용량과 크레딧을 화면에 항상 떠있는 작은 캐릭터로 보여주는 Windows 데스크톱 위젯입니다.

## ⚠ 중요 안내

이 프로그램은 Anthropic이 공식적으로 지원하지 않는 방식(claude.ai가 내부적으로 쓰는 비공식 API)을 사용합니다.

- Anthropic이 내부 구조를 바꾸면 언제든 동작이 멈출 수 있습니다.
- 로그인 세션 쿠키(`sessionKey`)를 사용하는데, 이 값은 사실상 로그인 자체와 동급으로 민감한 정보입니다. 이 앱은 해당 값을 Windows Credential Manager에 암호화 저장하고 오직 `claude.ai`로만 요청을 보내며, 어떤 외부 서버로도 전송하지 않습니다. 그래도 본인 책임하에 사용해주세요.

## sessionKey 쿠키 가져오는 법

1. Chrome에서 claude.ai에 로그인
2. F12 → Application 탭 → Cookies → `https://claude.ai`
3. `sessionKey` 값을 복사 (Organization ID는 `lastActiveOrg` 값)
4. 위젯 우클릭 → 설정에 붙여넣기

## 다른 사람에게 줄 때

`dist/ClaudeUsageWidget.exe`와 `docs/setup-guide.html` 두 개를 같이 압축해서 보내면 됩니다.
안내 파일은 그림이 들어간 단독 HTML이라 더블클릭하면 브라우저에서 바로 열리고, 인터넷도
필요 없습니다. 받는 사람이 알아보기 쉽게 `설치안내.html` 정도로 이름을 바꿔서 보내세요.

exe에는 만든 사람의 로그인 정보가 들어있지 않습니다 -- sessionKey는 Windows 자격 증명
관리자에, 설정은 `%APPDATA%\ClaudeUsageWidget\`에 따로 저장되므로 받는 사람은 처음 실행
상태에서 본인 값을 넣게 됩니다.

## 개발 환경에서 실행

```bash
pip install -r requirements-dev.txt
python -m pytest
python run.py
```

## 실행파일(.exe) 빌드

```bash
pyinstaller --onefile --windowed --name ClaudeUsageWidget --paths src run.py
```

빌드 결과물은 `dist/ClaudeUsageWidget.exe`.
