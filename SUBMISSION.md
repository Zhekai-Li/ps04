# Problem Set 4 Student Submission

Complete this document with your project details and links. Keep the course instructions in [README.md](README.md) and the required contracts in [ARCHITECTURE.md](ARCHITECTURE.md).

**Student:** To complete  
**GitHub repository:** Add your repository link

## Topic and Audience

- **Publication name:** To complete
- **Topic:** To complete
- **Audience and assumed knowledge:** To complete
- **Central question:** To complete
- **Scope and exclusions:** To complete
- **Reason for readers to return:** To complete

## Published Series

Replace each placeholder with the title or working link. Verify that course staff can open every publication.

| Piece | Title | Substack article | YouTube video |
| --- | --- | --- | --- |
| 1 | To complete | Add link | Add link |
| 2 | To complete | Add link | Add link |
| 3 | To complete | Add link | Add link |

**Separate technical demonstration video:** Add link

## Setup and Execution

Document the required tools and versions, installation commands, model or provider choices, and configuration steps. List credential environment variable names without including secret values. Explain how to populate the project configuration, source list, editorial policy, and prompts.

After implementation, the required entry commands are:

```bash
bash run.sh
bash run.sh --package runs/RUN_ID
```

Replace `RUN_ID` with an actual run directory. Add any setup or stage-replay commands a reviewer needs.

## Architecture and Manual Handoffs

Add a diagram of your implemented pipeline and explain any additional components or helpers. Show where models are called and where evidence is stored.

Describe the human editorial review, Google Vids or HeyGen production, and Substack and YouTube publishing steps. Identify the files passed into each manual step and the resulting artifacts.

## Evidence and Runs

Link to the retained evidence, editorial decisions, briefs, content checks, and intermediate artifacts needed to inspect the complete workflow. Keep referenced text and transcript files accessible. Explain how to retrieve media omitted from the repository.

| Run | Actual date | Run artifacts and logs | Elapsed time | Approximate cost |
| --- | --- | --- | --- | --- |
| First live run | To complete | Add path or link | To complete | To complete |
| Second live run | To complete | Add path or link | To complete | To complete |

Explain what changed between runs. Identify unknown or estimated costs. Provide the records demonstrating duplicate handling, the date-window checks, and collection failure or recovery. Label any fixture replay or simulated failure.

Trace one published claim to its brief, editorial decision, source version, and exact supporting passage or timestamp.

## Editorial Review

Link to the editorial policy and prompts used. Provide your review of at least three accepted and three rejected or deferred items, comparing the AI's reasons with your own judgment.

Show the policy before and after your revision, the affected stage outputs, and what changed. Record factual corrections, remaining limitations, and the evidence for your final publication approval.

## Reflection

Explain one insight the system produced, one editorial failure or limitation, and the next improvement you would make. Discuss one architectural tradeoff and why your choice fits this project.
