# Citation reliability of frontier large language models in medical writing and its automated verification

Code, prompts, generated outputs, verification results, and analysis scripts for the study evaluating reference hallucination in three frontier large language models (Claude Opus 4.8, GPT-5.5, Gemini 3.5 Flash) generating cardiology narrative reviews with web search enabled, and validating an LLM-based Chain-of-Verification (CoVe) reference verifier against an expert gold standard.

Shin R, Lee J-M, Kwun J-S, Cho H-W, Kang S-H, Jeon K-H. Manuscript under submission (2026). A Zenodo DOI will be added on acceptance.

## What is here

| Path | Content |
|---|---|
| `prompts/` | Standardized generation prompt, PubMed search strings for publication-volume levels, analysis plan |
| `generation/gen_ws.py` | Generates the 270 reviews via each provider's API with native web search or grounding enabled (main condition). `gen.py` is the no-tools condition used only for the supplement |
| `verification/verify.py` | Automated PubMed-based field verification. Fixed rule-based program (NCBI E-utilities + Crossref), no LLM. Assigns each reference to one of seven categories |
| `data/verdicts_websearch.jsonl` | Verification outcome for every one of the 8,050 references in the main condition (primary data) |
| `data/raw_reviews/` | The 270 generated reviews with parsed reference lists (JSON) |
| `data/parametric_supp/` | No-tools condition outputs and verdicts (supplement only) |
| `data/expert_adjudication_270.csv` | Expert-adjudicated gold standard for the 270-reference validation set |
| `data/validation_set_key.json` | Mapping from validation review codes R1 to R9 to model, topic, and run |
| `cove/` | Chain-of-Verification inputs (`input/`), per-review verdicts (`output/`), the three-way comparison script `compare.py`, and the claim-level demonstration (`q67_*.json`) |
| `analysis/` | Mixed-effects models (`glmm_main.R`, `simple_effects.R`, `export_emm.R`), misclassification sensitivity analysis, table and figure scripts |
| `figures/` | Final figures (PNG 300 dpi and vector PDF) |

## Reproducing the analysis

1. Verification of a fresh generation run: `python verification/verify.py` (requires an NCBI API key in a local `.env`, never committed).
2. Primary model comparison: `Rscript analysis/glmm_main.R` (R 4.4.0, lme4 2.0.1, emmeans 2.0.2) reads `data/verdicts_websearch.jsonl`.
3. Simple effects and adjusted estimates: `Rscript analysis/simple_effects.R`, `Rscript analysis/export_emm.R`.
4. Misclassification sensitivity analysis: `python analysis/supplement_misclass.py`.
5. CoVe versus expert comparison: `python cove/compare.py`.
6. Figures: `python analysis/build_figs_npj.py`.

Python 3.12.2 with NumPy 2.4.1 and matplotlib was used. The CoVe runs themselves were executed with an LLM agent following the factored Chain-of-Verification procedure described in the manuscript, using PubMed tool calls; the per-reference inputs and outputs of those runs are provided in full in `cove/`.

## Notes on the data

The generated reviews are model outputs and contain no patient data. Reference verification used public bibliographic databases only. API keys are not part of this repository.

## License

Code: MIT. Data and generated outputs: CC BY 4.0. See `LICENSE`.
