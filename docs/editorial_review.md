# Human editorial review and policy revision

This record must be completed by Zhekai Li after live run one. It is intentionally not pre-filled with fabricated judgments.

## Run and policy versions

- Live run one: `runs/live-20261009T183914Z-438d5dc4`
- Pre-revision policy: `runs/live-20261009T183914Z-438d5dc4/config/editorial_policy.md`
- Revised policy: `config/editorial_policy.md` (version 3; version 2 was tested and then clarified after it failed to change the reviewed testimonial decision).
- Day-two version-2 validation run: `runs/live-20261010T141700Z-ca069018` (technically successful, but it still rejected the reviewed testimonial; preserved as an intermediate audit artifact).
- Corrected day-two rerun: `runs/live-20261010T142614Z-b7aaa14e` (version 3 policy; automated review, human approval, packaging, and publication completed).
- Corrected rerun decisions and briefs: `runs/live-20261010T142614Z-b7aaa14e/decisions.jsonl` and `runs/live-20261010T142614Z-b7aaa14e/briefs.jsonl`.

## Decision sample

Review at least three accepted and three rejected or deferred records.

| Item/version | AI decision and reason | Zhekai’s judgment | Evidence checked | Keep/change |
| --- | --- | --- | --- | --- |
| MIT News, “3 Questions: What is the best path forward for AI in academia?”<br>`feed:https://news.mit.edu/2026/3-questions-what-best-path-forward-ai-academia-0925`<br>`10b8fcf0d90ad50055eda601d251cadc95ee09dfde1a272876d12c1ebf987a36` | **Accept.** Directly concerns graduate research, formative work, auditing model output, reproduction, and intellectual responsibility; it is expert perspective rather than measured evidence. | **Accept.** The material is relevant to AI’s effects on research training and scholarly judgment. | `data/assets/2b7c7a753ae49ea47c93/10b8fcf0d90ad50055eda601d251cadc95ee09dfde1a272876d12c1ebf987a36.txt` | Keep AI decision. |
| SciSpace, “AI in Academic Writing: Red Flags Journal Reviewers Notice”<br>`youtube:3sDQyUPl6yA`<br>`ce3d5dcf23d4ce001c8947e7bb05a1950c0c0f3c6fc716abee50181f56cb776c` | **Accept.** A journal/grant reviewer gives concrete examples of fabricated authors, incorrect DOIs, mismatched evidence, and copied chatbot text. Vendor-hosted and not a controlled study. | **Accept.** It provides authentic journal-review experience and a distinctive evaluative perspective. | `data/assets/ccfa78cb9d0951d373cf/ce3d5dcf23d4ce001c8947e7bb05a1950c0c0f3c6fc716abee50181f56cb776c.txt` | Keep AI decision. |
| Latent Space, “Academia is for Ambition — Alex Zhang, MIT”<br>`podcast:substack:post:218414422`<br>`d004b24a9d7a37163bac6a8870c701f9a604053168678fe944543c6789aee856` | **Accept.** Practitioner discussion of research taste, originality, benchmark limits, expert verification, and human steering; informed opinion rather than controlled evidence. | **Accept.** It clearly describes AI’s limitations and the irreplaceable role of human expertise and judgment. | `data/assets/6d327334b30140097722/d004b24a9d7a37163bac6a8870c701f9a604053168678fe944543c6789aee856.txt` | Keep AI decision. |
| MIT News, “Discovering the value of humanistic inquiry”<br>`feed:https://news.mit.edu/2026/discovering-value-humanistic-inquiry-1007`<br>`1bdc23363d47efbce0f41204da6d78bda89d1cba4e7ae0c6d68da1361c6668ae` | **Reject.** It concerns first-year humanities and broad judgment, not AI-assisted research, academic writing, or the intended graduate audience. | **Reject.** It is not sufficiently related to the series topic, and its intended audience does not match the project’s audience. | `data/assets/9ec565420004558c70d6/1bdc23363d47efbce0f41204da6d78bda89d1cba4e7ae0c6d68da1361c6668ae.txt` | Keep AI decision. |
| SciSpace, “A Medical Doctor on How SciSpace Changed Her Research Process”<br>`youtube:q_g-rU1kW2o`<br>`1972602e5362635f440c0256b31d08016785947e9d7ac2657fc4405cfe1dd3a2` | **Reject.** The vendor testimonial’s two-years-to-one-weekend comparison is self-reported and lacks comparable tasks, quality assessment, or corroboration. | **Accept with limits.** It can reflect users’ views and experiences with AI research tools and is therefore valuable as perspective evidence. Use it as personal experience, not as verified evidence of the claimed time saving. | `data/assets/9bb71838454f2e9cbbaf/1972602e5362635f440c0256b31d08016785947e9d7ac2657fc4405cfe1dd3a2.txt` | **Change AI decision.** The policy needs a bounded category for relevant stakeholder perspective that is clearly labelled and not used to substantiate performance claims. |
| Nature Podcast, “Nobel Prizes 2026 …”<br>`podcast:6ac673cf9fea6e0a64d06d1a`<br>`7ed24c719e862102da5f9df4bdd1682ed94761e713c587e68b2c86ccfb269bc2` | **Reject.** The episode covers Nobel Prizes, sports-viewing research, black-hole jets, and the ancient gut microbiome, not AI-assisted research or writing. | **Reject.** It has no substantive connection to the series topic. | `data/assets/58e57d77e1c1701c67f5/7ed24c719e862102da5f9df4bdd1682ed94761e713c587e68b2c86ccfb269bc2.txt` | Keep AI decision. |

## Policy revision

Observed failure: the original policy correctly rejected an unsupported vendor efficiency claim, but the decision discarded the whole item even though the human reviewer found the stakeholder perspective useful.

Exact rule changed: policy version 3 requires selection of directly relevant stakeholder testimony when it contains a specific qualitative perspective useful to cross-source synthesis. An unsupported quantitative claim in the same item must be excluded from evidentiary use, but it is not by itself grounds to discard the usable qualitative perspective. The source and incentives must be disclosed, and testimony cannot support quantitative performance, prevalence, or causal claims without independent corroboration. Briefs and final pieces must label it as testimony rather than a measured result.

Evidence for the change: the SciSpace testimonial contains a relevant account of how a researcher perceives the division of labor between AI-assisted literature work and human analysis, even though its two-years-to-one-weekend comparison is not independently supported.

Validation history: run `live-20261010T141700Z-ca069018` used version 2, but still rejected the testimonial because the wording was permissive rather than decisive. This real intermediate result is preserved.

Corrected rerun effect: run `live-20261010T142614Z-b7aaa14e` used version 3 and changed the SciSpace testimonial from `reject` with no piece assignment to `accept` for pieces `02` and `03`. The decision retains only the qualitative division of labor—AI for literature triage and summarization while humans retain selection, analysis, reasoning, judgment, and paper shaping—and explicitly excludes the unsupported two-years-to-one-weekend claim from quantitative evidentiary use. Brief `03` incorporates that bounded perspective into its cross-source synthesis. Article and video script `03` label it as commercially published practitioner testimony and state that it is not independent evidence of product performance.

## Factual corrections

| Piece/claim | Original wording | Corrected wording | Exact evidence | Reason |
| --- | --- | --- | --- | --- |
| Piece 01 | No correction requested. | No change. | The human reviewer checked final article and video script `01` from `live-20261010T142614Z-b7aaa14e`. | Zhekai Li approved piece 01 as accurate and acceptable. |
| Piece 02 | No factual correction requested. | No claim or evidence change. The matching video script was shortened for the 3–5 minute production target without changing its six claim markers. | The human reviewer checked final article and video script `02` from `live-20261010T142614Z-b7aaa14e`. | Zhekai Li approved the content of piece 02 as accurate and acceptable. |
| Piece 03 | No factual correction requested. | No claim or evidence change. The article and matching video script were shortened to their production targets without changing their six claim markers. | The human reviewer checked final article and video script `03` from `live-20261010T142614Z-b7aaa14e`. | Zhekai Li approved the content of piece 03 as accurate and acceptable. |

## Approval record

Run one’s automated review is `runs/live-20261009T183914Z-438d5dc4/review.json`. The corrected day-two run’s final automated review is `runs/live-20261010T142614Z-b7aaa14e/review.json` with review ID `1361c8b77a6b8cfd5bf5ecb2b071e46f25b467acb55f2a0273039a612da4194a`; it passed after the reviewed length edits. Zhekai Li personally created `runs/live-20261010T142614Z-b7aaa14e/approval.json`, approving all three final articles and video scripts at `2026-10-10T15:13:43Z`. Packaging verified the matching approval, and the final run now has status `published`. Remaining uncertainty is stated in the source limitations inside each piece. Publication, reciprocal-link checks, and signed-out access verification were completed on October 11, 2026; 1080p YouTube processing was rechecked on October 12. The final URLs are in `SUBMISSION.md` and `package/publication_links.json`.

