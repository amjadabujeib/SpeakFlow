from pydantic import BaseModel


class GrammarCheckRequest(BaseModel):
    text: str


class VocabularyLookupRequest(BaseModel):
    word: str
