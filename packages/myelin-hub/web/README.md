# myelin-hub/web

MYELIN Hub 프런트엔드 — React 18 · Vite 5 · TypeScript · Tailwind 3 + **Emboss preset** (ADR-0007, ADR-0008).

```bash
npm ci
npm run build        # → dist/ (myelin-hub 가 이 폴더를 서빙)
npm run dev          # 개발 서버 127.0.0.1:5173, /api 는 myelin-hub(127.0.0.1:8765)로 프록시
```

규칙
- 색·그림자는 토큰만. Tailwind 기본 팔레트·그림자를 비워 두었으므로 `bg-red-500` 같은 클래스는 생성되지 않는다.
  `python design/build.py --lint` 가 `src/` 의 색 리터럴과 네온 글자색을 막는다.
- 인라인 `style` 금지 — Hub의 CSP(`style-src 'self'`)가 막는다. 클래스만 쓴다.
- 쓰기 요청은 `api.ts` 의 `act()` 만, 그리고 버튼 클릭 핸들러 안에서만. 화면을 여는 것만으로 쓰기가 일어나면 e2e가 실패한다.
- 노트 본문은 HTML로 렌더링하지 않는다 (`<pre>` 텍스트).
