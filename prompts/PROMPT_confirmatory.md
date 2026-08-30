# Standard Generation Prompt — Confirmatory Study (D7, locked)

> 3 모델(Claude Opus 4.8 / GPT-5.5 / Gemini 3.5)에 **글자 단위 동일**하게 투입.
> `[TOPIC]`만 9개 주제로 치환. no-tools / no-web (API 레벨에서 web search·tool use 비활성).
> 확정: 2026-06-18

---

```
You are writing a narrative review for a medical journal.

Topic: [TOPIC]

Write a concise narrative review (approximately 600–900 words) on this topic,
citing exactly 30 references. Use Vancouver-style numbered citations in the
text (e.g., [1], [2]).

Base the review solely on your own knowledge. Do not browse the web or use
any external tools. Cite only peer-reviewed articles indexed in PubMed.

After the review body, output the full reference list as a single JSON array
inside a fenced ```json code block. Each element must have exactly these keys:

  {
    "index":   <integer, 1–30, matching the in-text citation number>,
    "authors": "<full author list as cited, e.g. 'Smith J, Lee K, et al.'>",
    "title":   "<article title>",
    "journal": "<journal name>",
    "year":    <integer>,
    "volume":  "<volume>",
    "issue":   "<issue, or empty string>",
    "pages":   "<page range>",
    "pmid":    "<PubMed ID>",
    "doi":     "<DOI>"
  }

Provide the PMID and DOI for each reference. Output the review body first,
then the JSON block. Do not add any text after the JSON block.
```

---

## 설계 노트 (사전등록 반영)
- **PubMed 한정 생성**: "Cite only peer-reviewed articles indexed in PubMed." → resource 카운트·oracle·생성 3축 일관.
  연구 scope = "PubMed 등재 문헌 인용 시나리오"로 명시. (소스 종류만 제한; PMID 제공은 아래 중립 유지.)
- **중립 문구 채택**: "Provide the PMID and DOI for each reference" — omission을 강제하지도(채워라),
  명시적으로 허용하지도(모르면 비워라) 않음. 표준 인용 요청 시나리오 재현 → 모델 간 자연 calibration(omission) 차이 관찰.
  ※ "valid PMID를 반드시 넣어라"로 강제 안 함 — 강제 시 honest omission(calibration secondary outcome) 소멸하므로.
- **분량 600–900 단어**: 30 refs를 자연스럽게 인용할 정도.
- **필드 10개**: index / authors / title / journal / year / volume / issue / pages / pmid / doi.
  - `index` = 본문 Vancouver 인용번호 ↔ JSON reference 연결키 (파싱 정렬 + 본문-list 정합성 점검용).
  - `issue` 빈 문자열 허용 (PubMed가 issue를 항상 기록하지 않음 → full-field 매칭 시 issue는 benign 취급 후보).
- **언어**: 영어 통일.
- **산출물 형태 = 옵션 1**: narrative 본문 + 끝에 JSON reference 블록 (생태적 타당도 + 파싱 안정 동시 확보).
  잠재 위험(본문 인용 ≠ JSON)은 index로 정합성 점검.
