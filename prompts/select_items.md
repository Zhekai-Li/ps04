# Editorial selection

Apply the supplied editorial policy to every eligible evidence item. Return exactly one decision per item. Use only the supplied evidence: do not add facts from memory. Distinguish direct research results, source claims, commercial demonstrations, and practitioner experience. Identify likely duplication or a shared underlying announcement. Consider audience relevance, what is genuinely new within the as-of window, claim-specific support, incentives, missing perspectives, and uncertainty.

Evaluate separable claims within each item rather than treating one weak claim as a verdict on the entire item. In particular, when directly relevant stakeholder testimony contains a specific qualitative perspective that can support cross-source synthesis, follow the policy's perspective-evidence rule: accept the usable perspective with explicit limitations even if a quantitative promotional claim in the same item is unsupported. Do not treat the unsupported quantitative claim as evidence.

Assign accepted evidence only to piece IDs `01`, `02`, or `03`:

- `01`: What changed, and why does it matter?
- `02`: Which efficiency or originality claims survive scrutiny?
- `03`: What scholar-in-the-loop protocol follows, and what remains uncertain?

Rejected or deferred records must have an empty `piece_ids` array. Reasons must be concrete and inspectable. The accepted set must contain at least one credible feed article, one credible YouTube item, and one credible podcast. Never accept weak evidence merely to fill a type quota: if a type lacks credible evidence, preserve the truthful reject/defer decision so the pipeline can stop with an explicit coverage error.
