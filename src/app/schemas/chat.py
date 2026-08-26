from datetime import datetime

from pydantic import BaseModel


class ConversationBase(BaseModel):
    title: str | None = None


class ConversationCreate(ConversationBase):
    pass


class ConversationRead(ConversationBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class MessageBase(BaseModel):
    content: str


class MessageCreate(MessageBase):
    conversation_id: int


class MessageRead(MessageBase):
    id: int
    conversation_id: int
    sender_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationWithMessages(ConversationRead):
    messages: list[MessageRead] = []
