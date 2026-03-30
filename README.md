# DRM6 — 고등학생의 시간대별 하루 일상 경험 조사

> **Day Reconstruction Method (DRM)** 기반 시간대별 일상 경험 설문 시스템

[![GitHub Pages](https://img.shields.io/badge/Survey-Live-brightgreen?style=for-the-badge&logo=github)](https://edu-data.github.io/DRM6/)

## 📋 개요

DRM6은 **일상재구성법(Day Reconstruction Method)**을 활용하여 고등학생의 하루를 시간대별로 재구성하고, 각 활동에서 느끼는 정서를 체계적으로 측정하는 연구용 설문 시스템입니다.

### DRM4 → DRM6 핵심 개선

| 항목 | DRM4 | DRM6 |
|------|------|------|
| **활동 분류** | 긍정/부정 이분법 (인위적) | 🌅☀️🌙 시간대별 자연스러운 회상 |
| **설문 흐름** | 긍정→부정→배경조사 | 활동기록→정서기록→인적사항 (2단계 분리) |
| **정서 항목** | 6개 항목 | **9개 항목** (각성 수준 기반 설계) |
| **데이터 저장** | Positive/Negative 분리 | **Activities 통합** (TimeBlock 구분) |
| **반복측정** | 매회 전체 응답 | **인적사항 1회만** (localStorage 자동 스킵) |

## 🔗 설문 링크

**👉 [설문 시작하기](https://edu-data.github.io/DRM6/)**

## 🕐 설문 구조

### 3분할 시간대

| 시간대 | 범위 | 아이콘 |
|--------|------|--------|
| 오전·점심 | 오전 8시 ~ 오후 1시 | 🌅 |
| 오후 | 오후 1시 ~ 오후 6시 | ☀️ |
| 저녁 | 저녁 6시 ~ 11시 | 🌙 |

### 설문 흐름

```
1️⃣  안내문 + 핸드폰 번호 입력
     ↓
2️⃣  시간대별 활동 기록 (1~5개씩)
    · 일화(기억에 남는 활동은?), 무슨 시간, 누구와, 어디서, 이유
    · 시간대별 맞춤 예시 제공 (오전/오후/저녁 각각 다른 placeholder)
     ↓
3️⃣  활동별 정서 평가 (9항목 × 7점 리커트)
    · 😊 긍정: 즐거운(고각성), 행복한(중각성), 편안한(저각성)
    · 😞 부정: 짜증나는(고각성), 부정적인(중각성), 무기력한(저각성)
    · ✨ 의미·가치: 의미있는, 가치있는, 만족할만한
     ↓
4️⃣  인적사항 (성별, 소재지, 학교유형, 학년, 진로결정)
    ※ 반복측정 시 동일 핸드폰 번호 → 자동 스킵
```

### 활동 카드 구성

| 필드 | 설명 |
|------|------|
| 📝 일화 | "기억에 남는 활동은?" — 시간대별 맞춤 예시 |
| ⏰ 무슨 시간 | 교과시간, 전문교과, 쉬는시간, 점심시간, 방과후, 동아리, 상담, 학원, 아침(등교 전), 저녁시간, 귀가후시간, 취침전, 기타 |
| 👥 누구와 | 혼자, 교사, 친구, 선후배, 가족, 성인, 이웃/지인, 온라인 친구, AI, 기타 |
| 📍 어디서 | 교실, 도서실, 운동장, 학원, 집, 기숙사, 카페/식당 등 |
| 💬 이유 | 시간대별 맞춤 예시 제공 |

### 학교유형 옵션

- 일반계고
- 특성화고 (경영고, 공고, 과학기술고, 농고 등)
- 기타

## 🔄 반복측정 지원

- **핸드폰 번호**를 응답자 식별 ID로 활용
- 인적사항은 **첫 응답 시 1회만** 입력 → `localStorage`에 저장
- 2차 이후 설문 시 인적사항 페이지 자동 스킵, 저장된 데이터 재사용
- Activities 시트에 **날짜(Date)**와 **요일(DayOfWeek)** 자동 기록 → 측정 시점 구분

## 🛠️ 기술 스택

| 구성 | 기술 |
|------|------|
| **Frontend** | HTML5, CSS3 (Glassmorphism), Vanilla JS (ES6+) |
| **Backend** | Google Apps Script (GAS) Web App |
| **데이터 저장** | Google Sheets (Responses + Activities 시트) |
| **호스팅** | GitHub Pages |
| **데이터 보호** | sessionStorage 자동 저장/복원, beforeunload 경고 |
| **반복측정** | localStorage 기반 인적사항 캐싱 |

## 📂 프로젝트 구조

```
DRM6/
├── index.html          # 4페이지 설문 HTML
├── css/
│   └── style.css       # 다크 글래스모피즘 디자인 시스템
├── js/
│   ├── config.js       # GAS URL 설정
│   └── app.js          # 설문 로직 (시간대 탭, 페이지네이션, 검증)
└── gas/
    └── Code.gs         # Google Apps Script 백엔드
```

## 📊 데이터 구조

### Responses 시트
| Timestamp | RespondentID | PhoneNumber | MorningCount | AfternoonCount | EveningCount | Gender | SchoolLocation | SchoolType | Grade | CareerDecision |

### Activities 시트
| RespondentID | PhoneNumber | Date | DayOfWeek | TimeBlock | ActivityNum | Activity | TimeCategory | Companion | Location | Reason | EmoJoyful | EmoHappy | EmoComfortable | EmoAnnoyed | EmoNegative | EmoLethargic | EmoMeaningful | EmoValuable | EmoSatisfying |

## 📝 최근 변경사항 (v6.1)

- **시간대별 맞춤 예시**: 활동 일화 및 이유의 placeholder를 오전/오후/저녁에 맞게 차별화
- **학교유형 간소화**: 일반계고, 특성화고(경영고, 공고, 과학기술고, 농고 등), 기타 3가지로 정리
- **무슨시간 옵션 개선**: 전문교과·쉬는시간 추가, 주말/휴일 옵션 삭제, 취침전 순서 조정
- **일화 질문 개선**: "무엇을 했나요?" → "기억에 남는 활동은?"으로 변경
- **제출 안내 문구 추가**: 설문 완료 버튼 앞에 응답 제출 대기 안내 표시

## 📜 라이선스

본 설문 시스템은 연구 목적으로 개발되었습니다.

---

*Research Survey 2026 — GAIM Lab*
