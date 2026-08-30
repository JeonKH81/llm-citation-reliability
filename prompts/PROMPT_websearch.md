# Standard Generation Prompt — MAIN arm (web-search / "current practice", D7-v2)

> 3 모델에 글자 단위 동일 투입. `[TOPIC]`만 9개 주제로 치환.
> 각 모델의 **native 웹검색/grounding 도구를 켠 상태**로 생성(현재 실제 사용 방식 반영).
> PubMed 전용 도구/MCP는 제공하지 않음(모델 자체 검색만). 확정: 2026-06-18

---

```
You are writing a narrative review for a medical journal.

Topic: [TOPIC]

Write a concise narrative review (approximately 600–900 words) on this topic,
citing exactly 30 references. Use Vancouver-style numbered citations in the
text (e.g., [1], [2]).

You may use web search to find and verify the references. Cite peer-reviewed
articles indexed in PubMed where possible.

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

## 설계 노트 (parametric arm 대비 변경점)
- **삭제**: "Base the review solely on your own knowledge. Do not browse..." (이제 검색 허용).
- **추가**: "You may use web search to find and verify the references." → refusal 회피 + 현재 실사용 반영.
- PubMed 등재 선호 문구는 "where possible"로 완화(검색으로 실제 논문을 찾도록).
- 나머지(30 refs, Vancouver, 10필드 JSON, 중립 PMID 문구, 영어)는 parametric arm과 동일 → 두 arm 비교 가능.
- 도구: Anthropic web_search_20250305 / OpenAI Responses web_search / Gemini google_search grounding (native만).
