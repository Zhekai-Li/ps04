# Source strategy and independence judgments

The configured endpoints are a redundant discovery pool, not automatic evidence approval. A pre-run audit must confirm that recent entries directly address the publication’s scope and that at least 18 plausible candidates from nine publishers are available.

| Publisher ID | Input | Perspective and caveat |
| --- | --- | --- |
| `nature` | RSS and podcast | Research publishing and journalism. Both endpoints share one publisher; an article used as a podcast discovery link is one underlying item. |
| `mit` | RSS | Research-institution reporting; institutional incentives and press-release framing still require claim-specific scrutiny. |
| `arxiv` | RSS | Primary preprints without automatic peer-review status; methods and versions matter. |
| `retraction-watch` | RSS | Research-integrity reporting; useful for evidentiary and citation failures, not AI-tool performance by itself. |
| `stanford-hai` | YouTube | Academic research and policy, with institutional framing. |
| `acm` | YouTube | Professional/research community material; talks may summarize older work. |
| `paperpile` | YouTube | Commercial research-writing tooling; product claims are not independent validation. |
| `scispace` | YouTube | Commercial literature/writing tooling; treat demonstrations and self-reported performance as source claims. |
| `the-gradient` | Podcast | Researcher interviews and practitioner interpretation. Check whether an episode duplicates a guest’s paper or video. |
| `latent-space` | Podcast | Commercial/practitioner perspective on AI systems; topics are broader than academic writing. |
| `mlst` | Podcast | Long-form researcher/practitioner discussion; recency of upload does not make an older result new. |

`source_id` identifies an endpoint; `publisher_id` identifies independence. `underlying_id_overrides` and `identity_overrides` in a source definition reconcile known cross-platform copies. Newly discovered duplication must be added to configuration and documented before counting coverage. Reposts, syndication, a podcast plus its YouTube upload, and several stories sourced from the same announcement remain one underlying item.

Collectors were smoke-tested on 2026-10-09 and returned records from all configured endpoint groups. Reachability does not establish relevance, freshness, or credibility; selection and human review do that.
