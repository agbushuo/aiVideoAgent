// Transcript / subtitle types

export interface Segment {
  segment_id: number;
  start: number;
  end: number;
  text: string;
}

export interface TranscriptResponse {
  language: string;
  duration: number;
  segments: Segment[];
}

export interface TranscriptUpdateRequest {
  segments: Segment[];
}

export interface SegmentUpdateRequest {
  text: string;
}
