from email import message
import os
import uuid
import json
import time

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask import Response, stream_with_context
from dotenv import load_dotenv

from mistralai.client import Mistral
from tavily import TavilyClient

from werkzeug.utils import secure_filename
from pypdf import PdfReader

from services.calculator import calculate_expression
from services.study_planner import create_study_plan
from services.rag import (
    create_chunks_from_pdf,
    create_embeddings,
    build_rag_context
)
from services.quiz import generate_quiz
from services.notes import generate_notes

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter

# --------------------------------------------------
# APP SETUP
# --------------------------------------------------

load_dotenv()

app = Flask(__name__)
limiter = Limiter(
    key_func=lambda: session.get("user_id", request.remote_addr),
    app=app,
    default_limits=[],
    headers_enabled=True
)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from flask_migrate import Migrate

migrate = Migrate(app, db)

class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    conversations = db.relationship(
        "Conversation",
        backref="user",
        lazy=True
    )

class Conversation(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    messages = db.relationship(
        "Message",
        backref="conversation",
        lazy=True,
        cascade="all, delete-orphan"
    )

class Message(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("conversation.id"),
        nullable=False
    )
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())    

app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY is not set.")

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"

def is_production():
    return os.getenv("FLASK_ENV") == "production"

class QuizResult(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )
    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("conversation.id"),
        nullable=True
    )
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())


class Document(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )
    filename = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    pages = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    chunks = db.relationship(
        "DocumentChunk",
        backref="document",
        lazy=True,
        cascade="all, delete-orphan"
    )


class DocumentChunk(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("document.id"),
        nullable=False
    )
    text = db.Column(db.Text, nullable=False)
    page = db.Column(db.Integer, nullable=False)
    embedding = db.Column(db.Text, nullable=False)

# --------------------------------------------------
# AI CLIENTS
# --------------------------------------------------

mistral_client = Mistral(
    api_key=os.getenv("MISTRAL_API_KEY")
)

def mistral_chat_complete(**kwargs):

    max_retries = 3

    for attempt in range(max_retries):

        try:

            return mistral_client.chat.complete(
                **kwargs
            )

        except Exception as e:

            error_message = str(e)

            if "429" not in error_message:
                raise

            if attempt == max_retries - 1:
                raise

            wait_time = 2 ** attempt

            print(
                f"Mistral rate limit hit. "
                f"Retrying in {wait_time} seconds..."
            )

            time.sleep(wait_time)

tavily_client = TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY")
)

# --------------------------------------------------
# SERVER-SIDE STORAGE
# --------------------------------------------------

# Conversation history
conversations = {}

# Active quizzes
active_quizzes = {}

# One PDF per user/session
pdf_documents = {}

# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")

# --------------------------------------------------
# TEST TAVILY
# --------------------------------------------------

@app.route("/test-tavily")
def test_tavily():

    if is_production():
        return jsonify({
            "error": "This endpoint is disabled in production."
        }), 404

    try:

        response = tavily_client.search(
            "latest technology news",
            max_results=3
        )

        return jsonify(response)

    except Exception as e:

        print("Tavily error:", e)

        return jsonify({
            "error": str(e)
        }), 500

# --------------------------------------------------
# TEST MISTRAL
# --------------------------------------------------

@app.route("/test-mistral")
def test_mistral():

    if is_production():
        return jsonify({
            "error": "This endpoint is disabled in production."
        }), 404

    try:

        response = mistral_chat_complete(
            model="ministral-3b-2512",
            messages=[
                {
                    "role": "user",
                    "content": "Say hello to DoubtBot."
                }
            ]
        )

        return jsonify({
            "reply": response.choices[0].message.content
        })

    except Exception as e:

        print("Mistral error:", e)

        return jsonify({
            "error": str(e)
        }), 500

# --------------------------------------------------
# INTENT DETECTION
# --------------------------------------------------

def detect_intent(message):

    response = mistral_chat_complete(
        model="ministral-3b-2512",
        messages=[
            {
                "role": "system",
                "content": """
                
                You are an intent classifier for DoubtBot.

                Classify the user's message into exactly ONE
                of these categories:

                explain
                notes
                quiz
                doubt
                simplify
                general

                Return ONLY the category name.
                Do not explain your answer.
                """
            },
            {
                "role": "user",
                "content": message
            }
        ]
    )

    intent = (
        response
        .choices[0]
        .message
        .content
        .strip()
        .lower()
    )

    allowed_intents = [
        "explain",
        "notes",
        "quiz",
        "doubt",
        "simplify",
        "general"
    ]

    if intent not in allowed_intents:
        intent = "general"

    return intent

# --------------------------------------------------
# TEST INTENT
# --------------------------------------------------

@app.route("/test-intent", methods=["POST"])
def test_intent():

    if is_production():
        return jsonify({
            "error": "This endpoint is disabled in production."
        }), 404

    data = request.get_json()

    message = data.get("message", "").strip()

    if not message:

        return jsonify({
            "error": "Message is required."
        }), 400

    try:

        intent = detect_intent(message)

        return jsonify({"intent": intent})

    except Exception as e:

        print("Intent error:", e)

        return jsonify({
            "error": str(e)
        }), 500

# --------------------------------------------------
# WEB SEARCH DETECTION
# --------------------------------------------------

def needs_web_search(message):

    keywords = [
        "latest",
        "today",
        "current",
        "recent",
        "news",
        "now",
        "weather",
        "price"
    ]

    message = message.lower()

    return any(
        keyword in message
        for keyword in keywords
    )

# ==================================
# HELPER
# ==================================
def question_matches_pdf(pdf_data, query):

    import re

    stopwords = {
        "what", "why", "how", "when", "where", "who",
        "is", "are", "was", "were", "the", "a", "an",
        "of", "to", "for", "in", "on", "with", "and",
        "or", "this", "that", "explain", "define",
        "meaning", "concept", "tell", "about", "give",
        "describe", "difference", "between", "use", "uses"
    }

    query_words = set(
        re.findall(
            r"\b[a-zA-Z0-9]{3,}\b",
            query.lower()
        )
    )

    query_words -= stopwords

    if not query_words:
        return False, []

    pdf_text = " ".join(
        chunk["text"].lower()
        for chunk in pdf_data.get("chunks", [])
    )

    pdf_words = set(
        re.findall(
            r"\b[a-zA-Z0-9]{3,}\b",
            pdf_text
        )
    )

    matched_words = query_words.intersection(pdf_words)

    return bool(matched_words), sorted(matched_words)

# ==================================================
# CHAT
# ==================================================

@app.route("/chat", methods=["POST"])
@limiter.limit("5 per minute")
def chat():

    if "user_id" not in session:
        return "Please login first"

    data = request.get_json()

    message = data.get("message", "").strip()

    if not message:
        return jsonify({
            "error": "Message cannot be empty."
        }), 400

    if len(message) > 5000:
        return jsonify({
            "error": "Message is too long. Maximum 5000 characters allowed."
        }), 400

    is_regenerate = data.get("regenerate", False)

    if is_regenerate:
        conversation_id = session.get("conversation_id")
        
        if not conversation_id:
            return jsonify({
                "type": "message",
                "reply": "No conversation to regenerate."
            })

        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=session["user_id"]
        ).first()

        if not conversation:
            return jsonify({
                "type": "message",
                "reply": "Conversation not found."
            })

        last_user_message = Message.query.filter_by(
            conversation_id=conversation_id,
            role="user"
        ).order_by(
            Message.created_at.desc()
        ).first()

        if not last_user_message:
            return jsonify({
                "type": "message",
                "reply": "No previous question to regenerate."
            })

        message = last_user_message.content

        last_assistant_message = Message.query.filter_by(
            conversation_id=conversation_id,
            role="assistant"
        ).order_by(
            Message.created_at.desc()
        ).first()

        if last_assistant_message:
            db.session.delete(last_assistant_message)
            db.session.commit() 

    if not message:

        return jsonify({
            "type": "message",
            "reply": "Please enter a message."
        })


    try:

        # --------------------------------------------------
        # CREATE / GET CONVERSATION ID
        # --------------------------------------------------

        conversation_id = session.get("conversation_id")

        conversation = []

        if conversation_id:

            conversation = Conversation.query.filter_by(
                id=conversation_id,
                user_id=session["user_id"]
            ).first()

        else:

            conversation = None

        if not conversation:

            conversation = Conversation(
                title=message[:50],
                user_id=session["user_id"]
            )

            db.session.add(conversation)
            db.session.commit()

            session["conversation_id"] = conversation.id

        conversation_id = conversation.id

        # --------------------------------------------------
        # GET CONVERSATION HISTORY
        # --------------------------------------------------

        conversation_messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(
            Message.created_at.asc()
        ).all()

        conversation = []

        for saved_message in conversation_messages:

            conversation.append({
                "role": saved_message.role,
                "content": saved_message.content
            })

            if is_regenerate and conversation:
                if conversation[-1]["role"] == "user":
                    conversation.pop()
        # --------------------------------------------------
        # GET PDF
        # --------------------------------------------------

        pdf_data = None

        rag_context = ""

        rag_sources = []

        pdf_related = False

        pdf_matched_words = []

        document = None
        
        document_id = session.get("document_id")

        if document_id:
            document = Document.query.filter_by(
                id=document_id,
                user_id=session["user_id"]
            ).first()

        if document:
            
            chunks = DocumentChunk.query.filter_by(
                document_id=document.id
            ).order_by(
                DocumentChunk.id.asc()
            ).all()

            if chunks:
                chunk_data = []
                embeddings = []

                for chunk in chunks:
                    chunk_data.append({
                        "text": chunk.text,
                        "page": chunk.page
                    })

                    embeddings.append(
                        json.loads(chunk.embedding)
                    )

            pdf_data = {

                "filename": document.filename,

                "text": document.content,

                "pages": document.pages,

                "chunks": chunk_data,

                "embeddings": embeddings
            }
            
           
            if pdf_data:
                pdf_related, pdf_matched_words = question_matches_pdf(
                    pdf_data,
                    message
                )

            if pdf_related:
                print("Question appears related to PDF.")
                print("Matched PDF keywords:", pdf_matched_words)
                print("Searching PDF using RAG...")

                rag_context, rag_sources = build_rag_context(
                    mistral_client,
                    pdf_data,
                    message
                )

            else:
                print("Question not related to PDF.")
                print("Skipping RAG.")

        print("Relevant chunks:", len(rag_sources))

        if rag_sources:
            
            print(
                "RAG pages:",
            [
                source["page"]
                for source in rag_sources
            ]
        )

        # --------------------------------------------------
        # PDF INSTRUCTION
        # --------------------------------------------------

        pdf_instruction = ""
        
        if pdf_related and rag_context:
            
            pdf_instruction = f"""
        The user's question is related to the uploaded PDF.
        Use the retrieved PDF context only when answering that question.
        """

        elif pdf_related:
            
            pdf_instruction = """
        The user's question appears related to the uploaded PDF,
        but no sufficiently relevant information was retrieved.
        """

        # --------------------------------------------------
        # DETECT INTENT
        # --------------------------------------------------

        calculator_words = [
            "+", "-", "*", "/", "%", "**"
        ]

        is_calculation = any(
            symbol in message
            for symbol in calculator_words
        )

        study_words = [
            "study plan",
            "study planner",
            "study schedule",
            "study timetable",
            "timetable",
            "padhai ka plan",
            "padhne ka plan",
            "study for",
            "plan my study",
            "days plan",
            "din me",
        ]

        is_study_plan = any(
            word in message.lower()
            for word in study_words
        )

        if is_calculation:
            intent = "calculator"

        elif is_study_plan:
            intent = "study_plan"

        else:
            intent = detect_intent(message)

        print("Detected intent:", intent)

        # ==================================================
        # CALCULATOR
        # ==================================================

        if intent == "calculator":

            result = calculate_expression(message)

            if not is_regenerate:
                save_message(
                    conversation_id,
                    "user",
                    message
                )

            save_message(
                conversation_id,
                "assistant",
                f"🧮 **Answer:** {result}"
            )

            return jsonify({
                "type": "message",
                "reply": f"🧮 **Answer:** {result}"
            })

        # ==================================================
        # STUDY PLAN
        # ==================================================

        if intent == "study_plan":

            import re

            # Extract numbers from user message
            numbers = re.findall(r"\d+(?:\.\d+)?", message)

            if len(numbers) < 2:

                return jsonify({
                    "type": "message",
                    "reply": (
                        "📚 **Study Plan banane ke liye mujhe ye information chahiye:**\n\n"
                        "• Subject\n"
                        "• Kitne days\n"
                        "• Daily kitne hours\n\n"
                        "**Example:**\n"
                        "`Make a study plan for Python for 7 days, 2 hours per day.`"
                    )
                })

            try:
                days = int(float(numbers[0]))
                hours_per_day = float(numbers[1])

                if days <= 0:
                    return jsonify({
                        "type": "message",
                        "reply": "❌ Days 0 se greater hone chahiye."
                    })

                if hours_per_day <= 0:
                    return jsonify({
                        "type": "message",
                        "reply": "❌ Daily study hours 0 se greater hone chahiye."
                    })

                if days > 365:
                    return jsonify({
                        "type": "message",
                        "reply": "❌ Maximum 365 days ka study plan bana sakte hain."
                    })

                if hours_per_day > 24:
                    return jsonify({
                        "type": "message",
                        "reply": "❌ Daily study hours 24 se zyada nahi ho sakte."
                    })

                # Try to extract subject
                subject = message
                subject_patterns = [

                    r"for\s+(.+?)\s+for\s+\d+\s+days?",

                    r"for\s+(.+?)\s+\d+\s+days?",

                    r"study\s+(.+?)\s+for\s+\d+\s+days?",

                    r"plan\s+(?:my\s+)?(?:study\s+)?(?:for\s+)?(.+?)\s+for\s+\d+\s+days?"
                ]

                for pattern in subject_patterns:
                    match = re.search(
                        pattern,
                        message,
                        re.IGNORECASE
                    )

                    if match:
                        subject = match.group(1).strip()
                        break

                # Clean subject
                subject = re.sub(
                    r"\s*,?\s*\d+(?:\.\d+)?\s*hours?.*",
                    "",
                    subject,
                    flags=re.IGNORECASE
                )

                subject = subject.strip(" ,.-")

                if not subject:
                    subject = "General Study"

                plan_data = create_study_plan(
                    subject,
                    days,
                    hours_per_day
                )

                reply = (
                    f"## 📚 {plan_data['subject']} Study Plan\n\n"
                    f"**Duration:** {plan_data['days']} days  \n"
                    f"**Daily Study:** {plan_data['hours_per_day']} hours  \n"
                    f"**Total Study Time:** {plan_data['total_hours']} hours\n\n"
                    f"### 🗓️ Daily Schedule\n\n"
                )

                for day in plan_data["plan"]:
                    reply += (
                        f"**Day {day['day']} — {day['topic']}**\n"
                        f"⏱️ Study Time: {day['hours']} hours\n\n"
                    )

                reply += (
                    "---\n"
                    "💡 **Tip:** Har study session ke end me 10–15 minutes "
                    "revision zaroor karo."
                )

                if not is_regenerate:
                    save_message(
                        conversation_id,
                        "user",
                        message
                    )

                save_message(
                    conversation_id,
                    "assistant",
                    reply
                )

                return jsonify({"type": "message", "reply": reply})


            except Exception as error:

                print(
                    "Study planner error:",
                    error
                )

                return jsonify({
                    "type": "message",
                    "reply": (
                        "❌ Study plan create nahi ho paya.\n\n"
                        "**Example:**\n"
                        "`Make a study plan for Python for 7 days, 2 hours per day.`"
                    )
                })


        # ==================================================
        # QUIZ
        # ==================================================

        if intent == "quiz":

            quiz = generate_quiz(
                mistral_client,
                message
            )

            quiz_id = str(uuid.uuid4())

            active_quizzes[quiz_id] = quiz

            session["quiz_id"] = quiz_id

            return jsonify({
                "type": "quiz",
                "quiz": {
                    "title": quiz.get("title", "Quiz"),
                    "questions": [
                        {
                            "question": q["question"],
                            "options": q["options"]
                        }

                        for q in quiz["questions"]
                    ]
                }
            })

        # ==================================================
        # NOTES
        # ==================================================

        if intent == "notes":

            notes = generate_notes(
                mistral_client,
                message
            )

            if not is_regenerate:
                save_message(
                    conversation_id,
                    "user",
                    message
                )

            save_message(
                    conversation_id,
                    "assistant",
                    notes
                )

            return jsonify({
                "type": "message",
                "reply": notes
            })

        # ==================================================
        # DOUBT SOLVING
        # ==================================================

        if intent == "doubt":

            doubt_response = (
                mistral_chat_complete(
                    model="ministral-3b-2512",
                    messages=[
                        {
                            "role": "system",

                            "content": f"""
                            You are DoubtBot, an AI doubt-solving assistant
                            for students.

                            Follow this structure:

                            1. Understand the problem.
                            2. Give the answer directly.
                            3. Explain step by step.
                            4. Give an example if useful.
                            5. Mention common mistakes if relevant.
                            6. End with a short final answer.
                            
                            Rules:

                            - Use simple student-friendly language.
                            - Do not skip important steps.
                            - For programming questions, explain code and logic.
                            - For mathematics, show calculations.
                            - For science, explain concepts clearly.
                            - Use Markdown.

                            If a PDF is uploaded, use the retrieved PDF
                            context as the PRIMARY SOURCE.

                            {pdf_instruction}
                            """
                        },
                        {
                            "role": "user",
                            "content": message
                        }
                    ]
                )
            )

            doubt_answer = (
                doubt_response
                .choices[0]
                .message
                .content
            )

            if not is_regenerate:
                save_message(
                    conversation_id,
                    "user",
                    message
                )

            save_message(
                conversation_id,
                "assistant",
                doubt_answer
            )

            return jsonify({
                "type": "message",
                "reply": doubt_answer
            })

        # ==================================================
        # SIMPLIFY
        # ==================================================

        if intent == "simplify":

            simplify_response = (
                mistral_chat_complete(
                    model="ministral-3b-2512",
                    messages=[
                        {
                            "role": "system",

                            "content": f"""
                            You are DoubtBot's simplification assistant.

                            Explain difficult topics in very simple language.

                            Follow:

                            1. Simple Meaning
                            2. Easy Explanation
                            3. Real-Life Analogy
                            4. Simple Example
                            5. Important Points
                            6. One-Line Summary

                            Rules:

                            - Assume the student is a beginner.
                            - Avoid unnecessary jargon.
                            - Use short sentences.
                            - Use relatable examples.
                            - Use Markdown.
                            
                            If a PDF is uploaded, use the retrieved PDF
                            context as the PRIMARY SOURCE.
                            
                            {pdf_instruction}
                            """
                        },
                        {
                            "role": "user",
                            "content": message
                        }
                    ]
                )
            )

            simplified_answer = (
                simplify_response
                .choices[0]
                .message
                .content
            )

            if not is_regenerate:
                save_message(
                    conversation_id,
                    "user",
                    message
                )

            save_message(
                conversation_id,
                "assistant",
                simplified_answer
            )

            return jsonify({
                "type": "message",
                "reply": simplified_answer
            })

        # ==================================================
        # WEB SEARCH
        # ==================================================

        context = ""

        if needs_web_search(message):

            search_response = (
                tavily_client.search(
                    message,
                    max_results=3
                )
            )

            search_results = (
                search_response.get(
                    "results",
                    []
                )
            )

            for result in search_results:

                context += f"""
                Title: {result.get('title', '')}

                Content: {result.get('content', '')}

                URL: {result.get('url', '')}

                ---
                """

        # ==================================================
        # AI MESSAGE
        # ==================================================

        messages = [
            {
                "role": "system",
                "content": f"""
                You are DoubtBot, a helpful AI learning assistant
                for students.

                Your main goal is to give clear, useful, and
                appropriately sized answers.

                IMPORTANT ANSWER LENGTH RULES:

                - For simple factual questions, give a short answer
                  in about 2–5 sentences.
                - Do not give a long explanation unless the user
                  asks for more detail.
                - For questions like "What is Python?", "What is a loop?",
                  or "What is RAM?", answer briefly with the main meaning
                  and one useful detail if needed.
                - If the user asks "explain", "in detail", "step by step",
                  "with examples", or asks for notes, provide a more
                   detailed answer.
                - Match the answer length to the user's question.
                - Do not add unnecessary sections, examples, summaries,
                  or extra information to a simple question.
                - Use simple student-friendly language.
                - Use Markdown when useful.

                PDF RULES:

                - If a PDF is uploaded and the retrieved PDF context
                  is relevant, use it as the PRIMARY SOURCE.
                - Use only the relevant information from the retrieved
                  PDF context.
                - Do not explain unrelated sections of the PDF.
                - Do not make the answer longer just because a PDF
                  is available.
                - If the user asks a simple question, keep the answer
                  concise even when PDF context is available.

                {pdf_instruction}
                 """
            }
        ]

        # --------------------------------------------------
        # CONVERSATION HISTORY
        # --------------------------------------------------

        conversation_messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(
            Message.created_at.asc()
        ).all()

        # --------------------------------------------------
        # CURRENT MESSAGE
        # --------------------------------------------------

        current_message = message

        # --------------------------------------------------
        # ADD RAG CONTEXT
        # --------------------------------------------------
        
        # Use PDF context only when it is actually relevant
        # to the user's question.
        
        if pdf_related and rag_context:
            
            current_message = f"""
            
            Retrieved information from uploaded PDF:
            
            {rag_context}
            --------------------------------

            User Question:
            {message}
            """

        # --------------------------------------------------
        # ADD WEB CONTEXT
        # --------------------------------------------------

        if context:
            current_message += f"""
            
            Web Search Results:
            {context}
            """

        messages.append({
            "role": "user",
            "content": current_message
        })

        # ==================================================
        # MISTRAL
        # ==================================================

        response = (
            mistral_chat_complete(
                model="ministral-3b-2512",
                messages=messages
            )
        )

        assistant_message = (
            response
            .choices[0]
            .message
        )

        if assistant_message.tool_calls:

            for tool_call in assistant_message.tool_calls:

                if tool_call.function.name == "calculate_expression":
                    arguments = json.loads(
                        tool_call.function.arguments
                    )

                    expression = arguments["expression"]

                    result = calculate_expression(expression)

                    messages.append(assistant_message)

                    messages.append({
                        "role": "tool",
                        "name": "calculate_expression",
                        "content": str(result),
                        "tool_call_id": tool_call.id
                    })

                    response = (
                        mistral_chat_complete(
                            model="ministral-3b-2512",
                            messages=messages
                        )
                    )

                    assistant_message = (
                        response
                        .choices[0]
                        .message
                    )

        reply = assistant_message.content

        # ==================================================
        # SAVE CONVERSATION
        # ==================================================

        conversation.append({
            "role": "user",
            "content": message
        })

        conversation.append({
            "role": "assistant",
            "content": reply
        })
        
        if not is_regenerate:
            save_message(
                conversation_id,
                "user",
                message
            )

        save_message(
            conversation_id,
            "assistant",
            reply
        )

        # ==================================================
        # RESPONSE
        # ==================================================

        response_data = {
            "type": "message",
            "reply": reply
        }

        # Add source information
        if rag_sources:
            response_data["sources"] = [
                {
                    "page": source["page"]
                }
                for source in rag_sources
            ]

        return jsonify(response_data)

    except Exception as e:
        import traceback
        print("Chat error:", e)
        traceback.print_exc()

        return jsonify({
            "type": "message",
            "reply": "Sorry, something went wrong."
        }), 500
    
# ==================================================
# QUIZ SUBMISSION
# ==================================================

@app.route("/submit-quiz",methods=["POST"])
def submit_quiz():

    if "user_id" not in session:
        return jsonify({
            "error": "Please login first."
        }), 401

    data = request.get_json()
    user_answers = data.get("answers", [])

    quiz_id = session.get("quiz_id")
    quiz = active_quizzes.get(quiz_id)

    if not quiz:
        return jsonify({
            "error": "No active quiz found."
        }), 400

    questions = quiz.get("questions", [])

    score = 0
    results = []

    for i, question in enumerate(questions):

        correct_answer = (question["answer"])

        if i < len(user_answers):
            user_answer = (user_answers[i])

        else:
            user_answer = -1

        is_correct = (
            user_answer == correct_answer)

        if is_correct:
            score += 1

        results.append({
            "question": question["question"],
            "selected": user_answer,
            "correct": correct_answer,
            "explanation": question["explanation"],
            "is_correct": is_correct
        })
        
    quiz_result = QuizResult(
        user_id=session["user_id"],
        conversation_id=session.get("conversation_id"),
        score=score,
        total_questions=len(questions)
    )
        
    db.session.add(quiz_result)
    db.session.commit()

    del active_quizzes[quiz_id]

    session.pop("quiz_id", None)

    return jsonify({
        "score": score,
        "total": len(questions),
        "results": results
    })

# ==================================================
# CLEAR CHAT
# ==================================================

@app.route("/clear-chat",methods=["POST"])
def clear_chat():

    if "user_id" not in session:
        return jsonify({
            "error": "Please login first."
        }), 401

    conversation_id = session.get("conversation_id")

    if conversation_id:

        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=session["user_id"]
        ).first()

        if conversation:

            db.session.delete(conversation)
            db.session.commit()

    session.pop("conversation_id", None)

    quiz_id = session.get("quiz_id")

    if quiz_id:
        active_quizzes.pop(quiz_id, None)

    session.pop("quiz_id", None)

    return jsonify({"success": True})

# ======================================
# PDF STATUS
# ======================================

@app.route("/pdf-status",methods=["GET"])
def pdf_status():

    if "user_id" not in session:
        return jsonify({
            "error": "Please login first."
        }), 401

    pdf_id = session.get("pdf_id")

    print("PDF STATUS - pdf_id:", pdf_id)
    print("PDF STATUS - document_id:", session.get("document_id"))

    if not pdf_id:
        print("PDF STATUS - No pdf_id in session")
        return jsonify({"active": False})

    pdf_data = pdf_documents.get(pdf_id)

    if not pdf_data:

        document_id = session.get("document_id")
        
        if document_id:

            print("PDF STATUS - Stale pdf_id, trying database recovery")
            
            document = Document.query.filter_by(
                id=document_id,
                user_id=session["user_id"]
            ).first()

            if document: 
                chunks = DocumentChunk.query.filter_by(
                document_id=document.id
            ).order_by(
                DocumentChunk.id.asc()
            ).all()

            if chunks:

                chunk_data = []
                embeddings = []

                for chunk in chunks:

                    chunk_data.append({
                        "text": chunk.text,
                        "page": chunk.page
                    })

                    embeddings.append(
                        json.loads(chunk.embedding)
                    )

                new_pdf_id = str(uuid.uuid4())

                pdf_documents[new_pdf_id] = {

                    "filename": document.filename,

                    "text": document.content,

                    "pages": document.pages,

                    "chunks": chunk_data,

                    "embeddings": embeddings
                }

                session["pdf_id"] = new_pdf_id

                return jsonify({
                    "active": True,
                    "filename": document.filename,
                    "pages": document.pages
                })

    session.pop("pdf_id", None)
    session.pop("document_id", None)

    return jsonify({"active": False})

# ==================================================
# REMOVE CURRENT PDF
# ==================================================

@app.route("/remove-pdf",methods=["POST"])
def remove_pdf():

    if "user_id" not in session:
        return jsonify({
            "error": "Please login first."
        }), 401

    pdf_id = session.get("pdf_id")
    document_id = session.get("document_id")

    if pdf_id:
        pdf_documents.pop(pdf_id, None)

    if document_id:

        document = Document.query.filter_by(
            id=document_id,
            user_id=session["user_id"]
        ).first()

        if document:
            db.session.delete(document)
            db.session.commit()

    session.pop("pdf_id", None)
    session.pop("document_id", None)

    return jsonify({
        "success": True,
        "message": "PDF removed successfully."
    })

# ==================================================
# UPLOAD PDF + RAG INDEXING
# ==================================================

@app.route("/upload-pdf", methods=["POST"])
@limiter.limit("5 per hour")
def upload_pdf():

    if "user_id" not in session:
        return jsonify({
            "error": "Please login first."
        }), 401

    # --------------------------------------------------
    # ONLY ONE PDF ALLOWED
    # --------------------------------------------------

    current_pdf_id = session.get("pdf_id")

    if (
        current_pdf_id
        and current_pdf_id in pdf_documents
    ):

        return jsonify({
            "error":
            "A PDF is already uploaded. Remove the current PDF before uploading another."
        }), 409

    if (
        current_pdf_id
        and current_pdf_id not in pdf_documents
    ):

        session.pop(
            "pdf_id",
            None
        )

        session.pop(
            "document_id",
            None
        )

    # --------------------------------------------------
    # CHECK FILE
    # --------------------------------------------------

    if "pdf" not in request.files:
        return jsonify({"error": "No PDF file received."}), 400

    pdf = request.files["pdf"]

    if pdf.filename == "":
        return jsonify({"error": "No file selected."}), 400


    if not pdf.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are allowed."}), 400

    try:

        # --------------------------------------------------
        # READ FILE
        # --------------------------------------------------

        pdf_bytes = pdf.read()

        if len(pdf_bytes) > 10 * 1024 * 1024:
            return jsonify({
                "error": "PDF file is too large. Maximum size is 10 MB."
            }), 400

        if not pdf_bytes:
            return jsonify({"error": "Uploaded PDF is empty."}), 400

        # --------------------------------------------------
        # CHECK PDF SIGNATURE
        # --------------------------------------------------

        if not pdf_bytes.startswith(b"%PDF"):

            return jsonify({
                "error": "The selected file is not a valid PDF."
            }), 400

        # --------------------------------------------------
        # SAVE FILE
        # --------------------------------------------------

        filename = secure_filename(pdf.filename)

        original_filename = secure_filename(pdf.filename)

        filename = (
            str(uuid.uuid4())
            + "_"
            + original_filename
        )

        upload_folder = os.path.join(
            app.root_path,
            "uploads"
        )

        os.makedirs(
            upload_folder,
            exist_ok=True
        )

        file_path = os.path.join(
            upload_folder,
            filename
        )

        with open(file_path,"wb") as f:
            f.write(pdf_bytes)

        # --------------------------------------------------
        # READ PDF
        # --------------------------------------------------

        reader = PdfReader(file_path)

        text = ""

        for page in reader.pages:

            page_text = (page.extract_text())

            if page_text:
                text += (page_text + "\n")

        if not text.strip():

            return jsonify({
                "error":
                "PDF uploaded, but no readable text was found."
            }), 400

        # --------------------------------------------------
        # CREATE CHUNKS
        # --------------------------------------------------

        chunks = create_chunks_from_pdf(reader)

        print("PDF chunks created:", len(chunks))

        if not chunks:

            return jsonify({
                "error":
                "Could not create PDF chunks."
            }), 400

        # --------------------------------------------------
        # EXTRACT CHUNK TEXT
        # --------------------------------------------------

        chunk_texts = [
            chunk["text"]
            for chunk in chunks
        ]

        # --------------------------------------------------
        # CREATE EMBEDDINGS
        # --------------------------------------------------

        print("Creating embeddings...")

        embeddings = create_embeddings(
            mistral_client,
            chunk_texts
        )

        print("Embeddings created:",len(embeddings))

        # --------------------------------------------------
        # VALIDATE
        # --------------------------------------------------

        if len(embeddings) != len(chunks):

            return jsonify({
                "error":
                "Embedding count does not match chunk count."
            }), 500


        # --------------------------------------------------
        # CREATE PDF ID
        # --------------------------------------------------

        pdf_id = str(uuid.uuid4())

        # --------------------------------------------------
        # STORE PDF + RAG DATA
        # --------------------------------------------------

        pdf_documents[pdf_id] = {

            "filename": filename,

            "text": text,

            "pages": len(reader.pages),

            "chunks": chunks,

            "embeddings": embeddings
        }

        # --------------------------------------------------
        # SAVE PDF TO DATABASE
        # --------------------------------------------------

        document = Document(
            user_id=session["user_id"],
            filename=filename,
            content=text,
            pages=len(reader.pages)
        )

        db.session.add(document)
        db.session.flush()

        for chunk, embedding in zip(chunks, embeddings):

            document_chunk = DocumentChunk(
                document_id=document.id,
                text=chunk["text"],
                page=chunk["page"],
                embedding=json.dumps(embedding)
            )

            db.session.add(document_chunk)

        db.session.commit()

        session["document_id"] = document.id

        # --------------------------------------------------
        # SAVE PDF ID
        # --------------------------------------------------

        session["pdf_id"] = pdf_id

        # --------------------------------------------------
        # RESPONSE
        # --------------------------------------------------

        return jsonify({

            "success": True,

            "filename": filename,

            "pages": len(reader.pages),

            "characters": len(text),

            "chunks": len(chunks),

            "message": "PDF uploaded and indexed for RAG successfully."
        })

    except Exception as e:
        db.session.rollback()
        print("PDF / RAG error:", e)
        return jsonify({"error": str(e)}), 500

# ======================
# NEW CHAT
# ======================

@app.route("/new-chat")
def new_chat():

    if "user_id" not in session:
        return redirect(url_for("login"))

    session.pop("conversation_id", None)
    session.pop("document_id", None)
    session.pop("pdf_id", None)

    return redirect(url_for("home"))

# ==========================
# RECENT CHAT
# ==========================
@app.route("/conversations")
def conversations_page():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_conversations = Conversation.query.filter_by(
        user_id=session["user_id"]
    ).order_by(
        Conversation.created_at.desc()
    ).all()

    return render_template(
        "conversations.html",
        conversations=user_conversations
    )

# ==========================
# CONVERSATION MESSAGE
# ==========================

@app.route("/conversation-messages")
def conversation_messages():

    if "user_id" not in session:
        return jsonify({
            "messages": []
        })

    conversation_id = session.get("conversation_id")

    if not conversation_id:
        return jsonify({
            "messages": []
        })

    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=session["user_id"]
    ).first()

    if not conversation:
        return jsonify({
            "messages": []
        })

    messages = Message.query.filter_by(
        conversation_id=conversation.id
    ).order_by(
        Message.created_at.asc()
    ).all()

    return jsonify({
        "messages": [
            {
                "role": message.role,
                "content": message.content
            }
            for message in messages
        ]
    })

# ================================
# OLD CHAT LOAD
# ================================

@app.route("/load-chat/<int:conversation_id>")
def load_chat(conversation_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=session["user_id"]
    ).first()

    if not conversation:
        return "Conversation not found", 404

    session["conversation_id"] = conversation.id

    return redirect(url_for("home"))

# ==================================
# REGISTER
# ==================================    

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        username = username.strip()
        email = email.strip()

        if not username or not email or not password or not confirm_password:
            return render_template(
                "register.html",
                error="All fields are required."
            )

        if len(username) < 3 or len(username) > 30:
            return render_template(
                "register.html",
                error="Username must be between 3 and 30 characters."
            )

        if len(password) < 8:
            return render_template(
                "register.html",
                error="Password must be at least 8 characters long."
            )

        if password != confirm_password:
            return render_template(
                "register.html",
                error="Your password is wrong"
            )

        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user:
            return render_template(
                "register.html",
                error="You already have an account. Please login."
            )

        existing_email = User.query.filter_by(
            email=email
        ).first()

        if existing_email:
            return render_template(
                "register.html",
                error="This email is already registered. Please login."
            )

        

        hashed_password = generate_password_hash(password)

        user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

# =================================
# LOGIN
# =================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        username = username.strip()

        if not username or not password:
            return render_template(
                "login.html",
                error="Username and password are required."
            )

        if len(username) > 30:
            return render_template(
                "login.html",
                error="Invalid username or password."
            )

        if len(password) > 128:
            return render_template(
                "login.html",
                error="Invalid username or password."
            )

        user = User.query.filter(
            db.func.lower(User.username) == username.lower()
        ).first()

        if not user:
            return render_template(
                "login.html",
                error="Username or password is incorrect. Please try again."
            )

        if not check_password_hash(
            user.password,
            password
        ):
            return render_template(
                "login.html",
                error="Password is incorrect. Please enter your password again."
            )

        session["user_id"] = user.id
        session["username"] = user.username

        return redirect(url_for("home"))

    return render_template("login.html")

# =======================
# LOGOUT
# =======================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))

# ========================
# PROFILE
# ========================

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return "Please login first"

    user = User.query.get(session["user_id"])

    quiz_results = QuizResult.query.filter_by(
        user_id=session["user_id"]
    ).order_by(
        QuizResult.created_at.desc()
    ).all()


    return render_template(
        "profile.html",
        user=user,
        quiz_results=quiz_results
    )

# ==================================================
# RUN APP
# ==================================================

def save_message(conversation_id, role, content):

    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content
    )

    db.session.add(message)
    db.session.commit()

def load_documents_from_database():

    with app.app_context():

        documents = Document.query.all()

        for document in documents:

            chunks = DocumentChunk.query.filter_by(
                document_id=document.id
            ).order_by(
                DocumentChunk.id.asc()
            ).all()

            if not chunks:
                continue

            chunk_data = []
            embeddings = []

            for chunk in chunks:

                chunk_data.append({
                    "text": chunk.text,
                    "page": chunk.page
                })

                embeddings.append(
                    json.loads(chunk.embedding)
                )

            pdf_id = str(uuid.uuid4())

            pdf_documents[pdf_id] = {

                "filename": document.filename,

                "text": document.content,

                "pages": document.pages,

                "chunks": chunk_data,

                "embeddings": embeddings
            }

            print(
                "PDF loaded from database:",
                document.filename
            )

with app.app_context():
    db.create_all()

load_documents_from_database()

if __name__ == "__main__":
    app.run(debug=False)