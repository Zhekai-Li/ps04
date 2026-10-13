# Production handoff

## Published final set

The three 3–5 minute audience videos were produced in Google Vids, exported as MP4, and published to YouTube as Unlisted videos. Their paired articles were published for free access on Scholar in the Loop. Final public links are recorded in `publication_links.json`; durations, media properties, and QA results are recorded in `video_drafts.json`. Earlier drafts remain private and are recorded in `video_drafts_history.json`; none were deleted.

The current final set is video 01 v4.1, video 02 v4, and video 03 v4.1. The visual system is a restrained academic-business presentation style: Arial throughout; a strict 28/18/11 pt hierarchy; compact line spacing; warm paper, ink, teal, and sand as the four visual color roles; flat cards with consistent internal padding; 42 pt safe margins; and one visual argument per scene. Audience-facing labels such as `VIDEO 02`, page counters, and internal claim IDs are absent. Ambiguous coordinate charts were replaced with explicit comparison cards and decision frameworks.

This revision specifically corrects the first video's Claim/Source/Dependency container row, moves the second and third videos' content regions clear of every title, and enlarges or simplifies tight cards in the third video. All cards now retain conversion-safe horizontal and vertical slack after Google Vids import. Final MP4 contact sheets, full-resolution spot checks, codec reports, subtitle counts, silence reports, and the design audit are in `video_qc_v4/final/`. Article-to-video correspondence remains documented in `article_video_crosswalk.json` because the narration and substantive claims did not change.

## Verification completed

1. All three videos contain eight scenes and eight Nyla voiceovers.
2. Durations are approximately 3:36, 3:30, and 3:54, within the required 3–5 minute range.
3. All exports are 1920×1080 H.264 with stereo AAC audio and an English `mov_text` subtitle track.
4. Automated geometry review of all 24 source slides found no text outside its nearest container, no scroll overflow inside a fixed container, and no intersection between a title region and its content region.
5. The typography audit found one font family and exactly three font sizes. Line-height rules are 1.08 for titles, 1.18–1.24 for display and lead text, and 1.30 for body text.
6. Final MP4 contact-sheet review found no clipped or overlapping text. Full-resolution checks cover video 01's Claim/Source/Dependency row; video 02's title clearance and conclusion surface; and video 03's correction flow, detailed decision lineage, and public-disclosure cards.
7. No audience slide contains a video number, page counter, internal claim ID, circular arrow container, or unclear coordinate chart.
8. The final MP4s contain 101, 86, and 107 English caption blocks respectively. Audio analysis found no silence interval longer than two seconds.
9. Each video follows the structure and claims of its matching reviewed article; only visual presentation changed in this revision.

## Publication verification completed

1. All three articles are published with free, shareable access.
2. All three audience videos are uploaded to YouTube as Unlisted and fall within the required duration.
3. Every article links to its matching video; every video description links to its article and source references.
4. The three article/video pairs were checked through their public links, and `publication_links.json` contains no null URL.
5. The separate 5:57 technical demonstration is uploaded to YouTube as Unlisted: https://youtu.be/-XfGao1GRJs.

No publication step remains. Google Vids project links and local export names are retained only as production provenance; the submitted viewer-facing links are the Substack and YouTube URLs.
