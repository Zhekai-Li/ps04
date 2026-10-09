from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Candidate(StrictModel):
    item_id: str
    source_id: str
    publisher_id: str
    kind: Literal["feed", "youtube", "podcast"]
    title: str
    url: str
    published_at: str | None
    retrieved_at: str
    media_url: str | None
    underlying_id: str | None = None
    native_id: str | None = None
    summary: str | None = None
    transcript_url: str | None = None
    identity_override: str | None = None


class Item(Candidate):
    version_id: str
    text_path: str
    segments_path: str | None
    content_hash: str | None = None
    cache_status: str | None = None


class Segment(StrictModel):
    segment_id: str
    start_seconds: float
    end_seconds: float
    text: str

    @model_validator(mode="after")
    def end_after_start(self) -> "Segment":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must not precede start_seconds")
        return self


class Decision(StrictModel):
    item_id: str
    version_id: str
    decision: Literal["accept", "reject", "defer"]
    reason: str
    piece_ids: list[Literal["01", "02", "03"]]

    @model_validator(mode="after")
    def decision_pieces(self) -> "Decision":
        if self.decision == "accept" and not self.piece_ids:
            raise ValueError("accepted items need at least one piece_id")
        if self.decision != "accept" and self.piece_ids:
            raise ValueError("rejected/deferred items need empty piece_ids")
        return self


class TextLocator(StrictModel):
    type: Literal["text"]
    quote: str


class SegmentLocator(StrictModel):
    type: Literal["segment"]
    segment_id: str


class EvidenceReference(StrictModel):
    item_id: str
    version_id: str
    locator: TextLocator | SegmentLocator


class Claim(StrictModel):
    claim_id: str
    statement: str
    type: Literal["reported_fact", "source_claim", "inference"]
    evidence: list[EvidenceReference] = Field(min_length=1)


class Brief(StrictModel):
    piece_id: Literal["01", "02", "03"]
    title: str
    question: str
    argument: str
    synthesis: str
    limitations: str
    claims: list[Claim] = Field(min_length=1)


class DecisionBatch(StrictModel):
    decisions: list[Decision]


class BriefBatch(StrictModel):
    briefs: list[Brief]


class WrittenPiece(StrictModel):
    piece_id: Literal["01", "02", "03"]
    markdown: str


class WrittenBatch(StrictModel):
    pieces: list[WrittenPiece]

