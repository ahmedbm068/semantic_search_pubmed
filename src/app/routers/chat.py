
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.app.core.security import get_current_user
from src.app.db.session import get_db
from src.app.models.conversation import Conversation
from src.app.models.message import Message
from src.app.models.user import User
from src.app.schemas.chat import (
    ConversationCreate,
    ConversationRead,
    ConversationWithMessages,
    MessageCreate,
    MessageRead,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConversationRead]:
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return conversations


@router.post(
    "/conversations",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationRead:
    convo = Conversation(
        user_id=current_user.id,
        title=data.title or "New conversation",
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationWithMessages,
)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationWithMessages:
    convo = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return convo


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    convo = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    db.delete(convo)
    db.commit()
    return


@router.post(
    "/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageRead:
    convo = (
        db.query(Conversation)
        .filter(
            Conversation.id == data.conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not convo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg = Message(
        conversation_id=convo.id,
        sender_type="user",
        content=data.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg
