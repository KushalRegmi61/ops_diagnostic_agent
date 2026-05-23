from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class PdfLocator(BaseModel):
    type: Literal["pdf"] = "pdf"
    page: int
    span_start: int
    span_end: int


class DocxLocator(BaseModel):
    type: Literal["docx"] = "docx"
    paragraph_index: int
    span_start: int
    span_end: int


class TextLocator(BaseModel):
    type: Literal["text"] = "text"
    line_start: int
    line_end: int


class TranscriptLocator(BaseModel):
    type: Literal["transcript"] = "transcript"
    line_start: int
    line_end: int
    ts_start: str
    ts_end: str


class TableLocator(BaseModel):
    type: Literal["table"] = "table"
    row_index: int


class XlsxLocator(BaseModel):
    type: Literal["xlsx"] = "xlsx"
    sheet: str
    row_index: int


class MboxLocator(BaseModel):
    type: Literal["mbox"] = "mbox"
    message_id: str
    section: Literal["header", "body"] = "body"


class JsonLocator(BaseModel):
    type: Literal["json"] = "json"
    pointer: str  # RFC 6901


AnyLocator = Annotated[
    Union[
        PdfLocator, DocxLocator, TextLocator, TranscriptLocator,
        TableLocator, XlsxLocator, MboxLocator, JsonLocator,
    ],
    Field(discriminator="type"),
]


FileType = Literal[
    "pdf", "docx", "md", "txt",
    "transcript_vtt", "transcript_srt",
    "csv", "xlsx", "mbox", "json",
]


class Source(BaseModel):
    file_id: str
    file_name: str
    type: FileType
    locator: dict


class ParsedSegment(BaseModel):
    text: str
    locator: dict


class ParsedFile(BaseModel):
    file_id: str
    file_name: str
    type: FileType
    segments: list[ParsedSegment]


class ExtractionError(BaseModel):
    file_id: str
    stage: Literal["parse", "agent", "review"]
    message: str


class FileRef(BaseModel):
    file_id: str
    file_name: str
    mime_type: str
    blob_path: str
    parser_status: Literal["ok", "error", "pending"]
