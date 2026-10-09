# Editorial selection

Apply the supplied editorial policy to every eligible evidence item. Return exactly one decision per item. Use only the supplied evidence: do not add facts from memory. Distinguish direct research results, source claims, commercial demonstrations, and practitioner experience. Identify likely duplication or a shared underlying announcement. Consider audience relevance, what is genuinely new within the as-of window, claim-specific support, incentives, missing perspectives, and uncertainty.

Assign accepted evidence only to piece IDs `01`, `02`, or `03`:

- `01`: What changed, and why does it matter?
- `02`: Which efficiency or originality claims survive scrutiny?
- `03`: What scholar-in-the-loop protocol follows, and what remains uncertain?

Rejected or deferred records must have an empty `piece_ids` array. Reasons must be concrete and inspectable.
