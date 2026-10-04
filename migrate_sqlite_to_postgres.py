import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import (
    User,
    Conversation,
    Message,
    QuizResult,
    Document,
    DocumentChunk
)


load_dotenv()

# --------------------------------------------------
# SQLite database
# --------------------------------------------------

sqlite_engine = create_engine(
    "sqlite:///instance/doubtbot.db"
)

SQLiteSession = sessionmaker(
    bind=sqlite_engine
)

sqlite_db = SQLiteSession()


# --------------------------------------------------
# PostgreSQL database
# --------------------------------------------------

postgres_url = os.getenv("DATABASE_URL")

if not postgres_url:
    raise RuntimeError(
        "DATABASE_URL is not set in .env"
    )

postgres_engine = create_engine(
    postgres_url
)

PostgreSQLSession = sessionmaker(
    bind=postgres_engine
)

postgres_db = PostgreSQLSession()


try:

    print("Starting SQLite → PostgreSQL migration...")
    print()

    # --------------------------------------------------
    # 1. Users
    # --------------------------------------------------

    users = sqlite_db.query(User).order_by(User.id).all()

    for user in users:
        postgres_db.add(
            User(
                id=user.id,
                username=user.username,
                email=user.email,
                password=user.password
            )
        )

    postgres_db.flush()

    print(f"Users migrated: {len(users)}")


    # --------------------------------------------------
    # 2. Conversations
    # --------------------------------------------------

    conversations = (
        sqlite_db
        .query(Conversation)
        .order_by(Conversation.id)
        .all()
    )

    for conversation in conversations:
        postgres_db.add(
            Conversation(
                id=conversation.id,
                title=conversation.title,
                user_id=conversation.user_id,
                created_at=conversation.created_at
            )
        )

    postgres_db.flush()

    print(
        f"Conversations migrated: "
        f"{len(conversations)}"
    )


    # --------------------------------------------------
    # 3. Messages
    # --------------------------------------------------

    messages = (
        sqlite_db
        .query(Message)
        .order_by(Message.id)
        .all()
    )

    for message in messages:
        postgres_db.add(
            Message(
                id=message.id,
                conversation_id=message.conversation_id,
                role=message.role,
                content=message.content,
                created_at=message.created_at
            )
        )

    postgres_db.flush()

    print(
        f"Messages migrated: "
        f"{len(messages)}"
    )


    # --------------------------------------------------
    # 4. Quiz Results
    # --------------------------------------------------

    quiz_results = (
        sqlite_db
        .query(QuizResult)
        .order_by(QuizResult.id)
        .all()
    )

    for result in quiz_results:
        postgres_db.add(
            QuizResult(
                id=result.id,
                user_id=result.user_id,
                conversation_id=result.conversation_id,
                score=result.score,
                total_questions=result.total_questions,
                created_at=result.created_at
            )
        )

    postgres_db.flush()

    print(
        f"Quiz results migrated: "
        f"{len(quiz_results)}"
    )


    # --------------------------------------------------
    # 5. Documents
    # --------------------------------------------------

    documents = (
        sqlite_db
        .query(Document)
        .order_by(Document.id)
        .all()
    )

    for document in documents:
        postgres_db.add(
            Document(
                id=document.id,
                user_id=document.user_id,
                filename=document.filename,
                content=document.content,
                pages=document.pages,
                created_at=document.created_at
            )
        )

    postgres_db.flush()

    print(
        f"Documents migrated: "
        f"{len(documents)}"
    )


    # --------------------------------------------------
    # 6. Document Chunks
    # --------------------------------------------------

    document_chunks = (
        sqlite_db
        .query(DocumentChunk)
        .order_by(DocumentChunk.id)
        .all()
    )

    for chunk in document_chunks:
        postgres_db.add(
            DocumentChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                text=chunk.text,
                page=chunk.page,
                embedding=chunk.embedding
            )
        )

    postgres_db.flush()

    print(
        f"Document chunks migrated: "
        f"{len(document_chunks)}"
    )


    # --------------------------------------------------
    # Commit everything
    # --------------------------------------------------

    postgres_db.commit()

    print()
    print("======================================")
    print("Migration completed successfully!")
    print("======================================")


except Exception as e:

    postgres_db.rollback()

    print()
    print("Migration failed!")
    print("No changes were committed to PostgreSQL.")
    print()
    print("Error:", e)

    raise


finally:

    sqlite_db.close()
    postgres_db.close()