from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ConversationBase(BaseModel):
    title: Optional[str] = None


class ConversationCreate(ConversationBase):
    pass


class ConversationRead(ConversationBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

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
    messages: List[MessageRead] = []
