# MYELIN Emboss — Obsidian Theme

백색 엠보(뉴모피즘) + Violet/Neon 강조. **라이트 모드만** 바꿉니다 (다크 모드는 Obsidian 기본).

## 설치
1. 이 폴더(`obsidian-myelin-emboss/`)를 Vault의 `.obsidian/themes/MYELIN Emboss/` 로 복사합니다.
   (폴더 이름은 manifest의 `name` 과 같아야 합니다.)
   ```bash
   mkdir -p ~/MyVault/.obsidian/themes/"MYELIN Emboss"
   cp theme/obsidian-myelin-emboss/{manifest.json,theme.css} ~/MyVault/.obsidian/themes/"MYELIN Emboss"/
   ```
2. Obsidian → 설정 → 모양(Appearance) → 테마 → **MYELIN Emboss**, 기본 색상 모드는 **라이트**.

## 무엇이 바뀌나
- 배경·글자·강조색·태그 등 Obsidian 색 변수를 Emboss 토큰으로 매핑
- 파일 탐색기 활성 항목 = Inset, 버튼 = Raised(누르면 Inset), 주 버튼 = Violet
- 입력창 = Inset + 경계선 + focus 링, Properties·Callout = Raised 카드, 태그 = Chip
- 노트에 `cssclasses: [mx-verified]` 또는 `[mx-ai]` 를 주면 제목에 Lime/Cyan 밑줄

## 고치려면
`theme.css` 는 생성 파일입니다. `design/tokens.json`(값)이나 `design/src/obsidian.css`(규칙)를 고친 뒤
`python design/build.py` 를 실행하세요. 색을 직접 쓰면 `--lint` 가 막습니다.
