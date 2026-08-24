# 강의자료 → PowerPoint 생성기

`lecture/index.html` 강의자료를 읽어 **python-pptx** 로 63장짜리 `.pptx` 를 만든다.
HTML 이 단일 원본이고 PPTX 는 거기서 파생되므로, 내용을 고칠 때는 HTML 만 고치고
다시 빌드하면 된다.

```bash
pip install python-pptx
python build_pptx.py                     # → 조사연구방법과_논문작성법.pptx
```

## 사용법

```bash
python build_pptx.py --out 특강.pptx      # 파일 이름 지정
python build_pptx.py --only 1,5,28-34    # 일부 슬라이드만 (판면 확인용)
python build_pptx.py --no-notes          # 발표자 노트 제외
```

빌드가 끝나면 어떤 슬라이드에 축소가 적용됐는지, 넘치는 슬라이드가 있는지 보고한다.

```
축소가 적용된 슬라이드 (글자/도해 배율):
   실습 3                         0.76 / 0.76
   매개와 조절                       1.00 / 0.64
넘치는 슬라이드 없음.
```

## 구성

| 파일 | 역할 |
|------|------|
| `theme.py` | 색·글꼴·판면 치수·글자 크기 토큰, 텍스트 폭/높이 근사 |
| `parse_html.py` | `index.html` → 슬라이드 데이터 (dict 목록) |
| `blocks.py` | 블록별 높이 측정과 그리기 (카드·콜아웃·표·대조·목록·도해) |
| `build_pptx.py` | 슬라이드 조립, 판면 맞춤, CLI |
| `render_figures.py` | (선택) 인라인 SVG 도해 → `figures/*.png` 재생성 |
| `qa_preview.py` | (선택) 만들어진 pptx 를 PNG 로 미리보고 넘침 검사 |

## 판면이 정해지는 방식

한글은 상자에서 잘 넘친다. 그래서 그리기 전에 먼저 높이를 잰다.

1. `theme.wrapped_lines()` 가 **어절 단위 그리디 줄바꿈을 그대로 흉내 내어** 줄 수를 센다.
   총 글자폭을 폭으로 나누는 방식은 줄 끝에 남는 빈 자리를 놓쳐 실제보다 적게 나온다.
   고정폭 서체는 폭 계산이 달라 `mono=True` 로 따로 잰다.
2. `blocks.measure()` 가 블록 트리 전체의 높이를 재귀적으로 합산한다.
3. `build_pptx._fit()` 이 배율을 고른다 — 여유가 있으면 최대 1.15배까지 키우고,
   넘치면 **도해를 먼저 줄인 뒤** 마지막에 글자를 줄인다. 읽어야 하는 글자보다
   그림이 먼저 양보하는 편이 강의자료로서 낫다.

측정과 그리기는 같은 함수를 공유하므로 둘이 어긋나지 않는다.

## 도해

본문의 SVG 도해 9개는 `figures/fig-00.png` … 로 미리 구워 저장소에 함께 둔다.
그래서 빌드에는 브라우저가 필요 없다. HTML 의 도해를 고쳤다면:

```bash
pip install playwright && playwright install chromium
python render_figures.py
```

`.fig` 가 문서에 나타나는 순서가 곧 파일 번호다. PNG 가 없으면 자리 표시로 대체된다.

## 미리보기와 넘침 검사

LibreOffice 없이 판면을 확인할 수 있다. **만들 때 쓴 근사가 아니라 파일에 실제로
기록된** 좌표·크기·글자를 실제 폰트 메트릭으로 다시 그리므로 검사로서 더 엄격하다.

```bash
pip install Pillow
python qa_preview.py 조사연구방법과_논문작성법.pptx --out preview
python qa_preview.py 조사연구방법과_논문작성법.pptx --pages 15,48,56
```

## 글꼴

| 용도 | 라틴 | 한글 |
|------|------|------|
| 본문·제목 | Arial | 맑은 고딕 |
| 라벨·수치·개요 | Courier New | 맑은 고딕 |

`blocks.set_font()` 이 `<a:latin>` 과 `<a:ea>` 를 함께 지정한다 —
python-pptx 의 `font.name` 은 라틴만 건드리므로 한글이 기본 서체로 떨어진다.
맥에서 열 일이 많다면 `theme.SANS_EA` 를 `"Apple SD Gothic Neo"` 로 바꾼다.

## 고칠 만한 곳

- **색·글자 크기** — `theme.py` 상단. `MAG` 하나만 바꿔도 강조색 전체가 따라온다.
- **판면 여백** — `theme.py` 의 `MARGIN_*`, `BODY_BOT`, `GAP`, `COL_GAP`.
- **축소 정책** — `build_pptx.py` 의 `UP_SCALES` / `FIG_SCALES` / `TEXT_SCALES`.
- **새 블록 종류** — `blocks.py` 에 `measure()` 분기와 `_d_*()` 를 추가하고
  `_DRAW` 에 등록한 뒤, `parse_html._blocks_from()` 에서 해당 클래스를 잡아준다.
