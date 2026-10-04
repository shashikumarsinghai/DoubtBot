# DoubtBot

Your AI Learning Assistant 🎓

DoubtBot is an AI-powered learning assistant designed to help students understand concepts, ask questions, study from PDFs, generate quizzes, create notes, and plan their studies from a single platform.

## Features

- 🤖 AI Chatbot
- 🌐 Web Search
- 📄 PDF Q&A / RAG
- 📝 AI Quiz Generation
- 📚 AI Notes Generation
- 🧮 Calculator
- 📅 Study Planner
- 💬 Chat History
- 📖 Study History
- 🔐 User Login & Registration
- 👤 User Profile
- 📊 Learning Statistics
- 🗄️ PostgreSQL Database
- 🛡️ Rate Limiting
- 🔒 Security & Input Validation
- 🌙 Dark / Light Mode
- 📱 Responsive UI
- 💻 Code Blocks & Syntax Highlighting
- 📋 Copy & Regenerate Responses
- 🔎 Search in Chat

## Tech Stack

### Frontend
- HTML
- CSS
- JavaScript
- Bootstrap

### Backend
- Python
- Flask

### AI
- Mistral AI API
- Mistral Embeddings

### Search
- Tavily API

### Database
- PostgreSQL
- SQLAlchemy
- Flask-Migrate

### PDF / RAG
- PyPDF
- Document chunking
- Embeddings
- Semantic retrieval

## Architecture

```text
User
  ↓
DoubtBot Web UI
  ↓
JavaScript
  ↓
Flask Backend
  ↓
 ┌───────────────┬────────────────┐
 │               │                │
Mistral AI    Tavily Search    PostgreSQL
 │               │                │
 └───────────────┴────────────────┘
                  ↓
              Response
                  ↓
                 User

```

## Project Structure

```text
DoubtBot/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── migrate_sqlite_to_postgres.py
│
├── migrations/
│
├── models/
│   └── __init__.py
│
├── routes/
│   └── __init__.py
│
├── services/
│   ├── calculator.py
│   ├── notes.py
│   ├── quiz.py
│   ├── rag.py
│   ├── study_planner.py
│   └── __init__.py
│
├── static/
│   ├── css/
│   │   └── style.css
│   ├── images/
│   └── js/
│       └── chat.js
│
├── templates/
│   ├── conversations.html
│   ├── index.html
│   ├── login.html
│   ├── profile.html
│   └── register.html
│
├── uploads/
│
└── utils/
    └── __init__.py

```

## Security

DoubtBot includes several security measures:

API keys stored in environment variables
.env excluded from Git
Secure session configuration
HTTPOnly session cookies
SameSite cookie protection
Production secure cookies
Input validation
File upload validation
PDF size restrictions
Authentication protection
User-specific data isolation
Rate limiting
Production debug mode disabled

## Database

DoubtBot uses PostgreSQL for persistent application data.

The database stores:

Users
Conversations
Messages
Quiz Results
Uploaded Documents
Document Chunks
Document Embeddings

## RAG Pipeline

For PDF-based questions, DoubtBot uses a Retrieval-Augmented Generation workflow:

```text
PDF Upload
    ↓
PDF Text Extraction
    ↓
Text Chunking
    ↓
Mistral Embeddings
    ↓
PostgreSQL Storage
    ↓
User Question
    ↓
Semantic Retrieval
    ↓
Relevant Document Chunks
    ↓
Mistral AI
    ↓
Answer
```

## Local Setup

# 1. Clone the repository
git clone <repository-url>
cd DoubtBot

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
Windows PowerShell:

.venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment variables
Create a .env file:

MISTRAL_API_KEY=your_mistral_api_key
TAVILY_API_KEY=your_tavily_api_key
FLASK_SECRET_KEY=your_secret_key
DATABASE_URL=your_postgresql_database_url

# 6. Run the application
python app.py

Open:

http://127.0.0.1:5000


## Author

# Shashi Kumar Singh

Built as a student-focused AI learning assistant project.