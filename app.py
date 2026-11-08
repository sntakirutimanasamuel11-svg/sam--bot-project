from flask import Flask, render_template, request, redirect
import sqlite3
import requests
from dotenv import load_dotenv
import os
import re
from datetime import datetime

load_dotenv()

app = Flask(__name__)


# ==============================
# TEXT NORMALIZATION
# ==============================

def normalize_text(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)

    return text


# ==============================
# DATABASE SETUP
# ==============================

def setup_database():

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            question TEXT UNIQUE,
            answer TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            message TEXT
        )
    """)

    # Add time column if the old database does not have it
    cursor.execute("PRAGMA table_info(chat_history)")
    columns = [column[1] for column in cursor.fetchall()]

    if "time" not in columns:
        cursor.execute(
            "ALTER TABLE chat_history ADD COLUMN time TEXT"
        )

    conn.commit()
    conn.close()


# ==============================
# GET LEARNED ANSWER
# ==============================

def get_answer(question):

    normalized_question = normalize_text(question)

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT question, answer FROM knowledge"
    )

    rows = cursor.fetchall()

    conn.close()

    for saved_question, answer in rows:

        if normalize_text(saved_question) == normalized_question:
            return answer

    return None


def ask_ai(question):

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return None

    url = "https://api.openai.com/v1/responses"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-4.1-mini",
        "instructions": "You are Sam Bot, an educational assistant. Explain clearly and simply. Support English and Kinyarwanda.",
        "input": question
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=30
        )

        if response.status_code != 200:
            return "AI service error: " + str(response.status_code)

        result = response.json()

        for item in result.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text")

        return None

    except requests.RequestException:
        return "I could not connect to the AI service. Please try again."


# ==============================
# BUILT-IN ANSWERS
# ==============================

def built_in_answer(question):

    question = normalize_text(question)

    greetings = {

        "hello":
            "Hello! 👋 I am Sam Bot. How can I help you?",

        "hi":
            "Hi! 👋 Nice to talk with you.",

        "hey":
            "Hey! 👋 How can I help you?",

        "good morning":
            "Good morning! ☀️ Have a great day.",

        "good afternoon":
            "Good afternoon! 😊 How can I help you?",

        "good evening":
            "Good evening! 🌙 How can I help you?"

    }

    return greetings.get(question)


# ==============================
# TEACH BOT
# ==============================

def teach_bot(question, answer):

    normalized_question = normalize_text(question)

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT question FROM knowledge"
    )

    rows = cursor.fetchall()

    existing_question = None

    for row in rows:

        if normalize_text(row[0]) == normalized_question:
            existing_question = row[0]
            break

    if existing_question:

        cursor.execute(
            """
            UPDATE knowledge
            SET answer = ?
            WHERE question = ?
            """,
            (answer, existing_question)
        )

    else:

        cursor.execute(
            """
            INSERT INTO knowledge
            (question, answer)
            VALUES (?, ?)
            """,
            (question.strip(), answer)
        )

    conn.commit()
    conn.close()


# ==============================
# UPDATE KNOWLEDGE
# ==============================

def update_knowledge(question, answer):

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE knowledge
        SET answer = ?
        WHERE question = ?
        """,
        (answer, question)
    )

    conn.commit()
    conn.close()


# ==============================
# LOAD KNOWLEDGE
# ==============================

def load_knowledge():

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT question, answer
        FROM knowledge
        ORDER BY question
        """
    )

    knowledge = cursor.fetchall()

    conn.close()

    return knowledge


# ==============================
# DELETE KNOWLEDGE
# ==============================

def delete_knowledge(question):

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM knowledge
        WHERE question = ?
        """,
        (question,)
    )

    conn.commit()
    conn.close()


# ==============================
# SAVE MESSAGE
# ==============================

def save_message(sender, message):

    current_time = datetime.now().strftime("%H:%M")

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO chat_history
        (sender, message, time)
        VALUES (?, ?, ?)
        """,
        (sender, message, current_time)
    )

    conn.commit()
    conn.close()


# ==============================
# LOAD CHAT HISTORY
# ==============================

def load_messages():

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT sender, message, time
        FROM chat_history
        ORDER BY id
        """
    )

    history = cursor.fetchall()

    conn.close()

    return history


# ==============================
# SEARCH CHAT
# ==============================

def search_messages(search_text):

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT sender, message, time
        FROM chat_history
        WHERE message LIKE ?
        ORDER BY id
        """,
        ("%" + search_text + "%",)
    )

    results = cursor.fetchall()

    conn.close()

    return results


# ==============================
# CLEAR CHAT
# ==============================

def clear_chat():

    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM chat_history"
    )

    conn.commit()
    conn.close()


# ==============================
# HOME
# ==============================

@app.route("/", methods=["GET", "POST"])
def home():

    reply = ""
    question = ""

    if request.method == "POST":

        question = request.form.get(
            "message",
            ""
        ).strip()

        if question:

            answer = get_answer(question)

            if answer:

                reply = answer

            else:

                answer = built_in_answer(question)

                if answer:

                    reply = answer

                else:

                    answer = ask_ai(question)

                    if answer:
                        reply = answer
                    else:
                        reply = "I don't know yet. Please teach me."

            save_message(
                "You",
                question
            )

            save_message(
                "Bot",
                reply
            )

    messages = load_messages()
    knowledge = load_knowledge()

    return render_template(
        "index.html",
        messages=messages,
        knowledge=knowledge,
        reply=reply,
        question=question,
        search_text=""
    )


# ==============================
# TEACH
# ==============================

@app.route(
    "/teach",
    methods=["POST"]
)
def teach():

    question = request.form.get(
        "question",
        ""
    ).strip()

    answer = request.form.get(
        "answer",
        ""
    ).strip()

    if question and answer:

        teach_bot(
            question,
            answer
        )

        reply = (
            "Thank you! "
            "I learned something new."
        )

        save_message(
            "Bot",
            reply
        )

    else:

        reply = (
            "Please provide both "
            "a question and an answer."
        )

    messages = load_messages()
    knowledge = load_knowledge()

    return render_template(
        "index.html",
        messages=messages,
        knowledge=knowledge,
        reply=reply,
        question="",
        search_text=""
    )


# ==============================
# SEARCH
# ==============================

@app.route(
    "/search",
    methods=["POST"]
)
def search():

    search_text = request.form.get(
        "search",
        ""
    ).strip()

    if search_text:

        messages = search_messages(
            search_text
        )

    else:

        messages = load_messages()

    knowledge = load_knowledge()

    return render_template(
        "index.html",
        messages=messages,
        knowledge=knowledge,
        reply="",
        question="",
        search_text=search_text
    )


# ==============================
# EDIT KNOWLEDGE
# ==============================

@app.route(
    "/edit-knowledge",
    methods=["POST"]
)
def edit_knowledge():

    question = request.form.get(
        "question",
        ""
    ).strip()

    answer = request.form.get(
        "answer",
        ""
    ).strip()

    if question and answer:

        update_knowledge(
            question,
            answer
        )

    return redirect("/")


# ==============================
# DELETE KNOWLEDGE
# ==============================

@app.route(
    "/delete-knowledge",
    methods=["POST"]
)
def delete_knowledge_route():

    question = request.form.get(
        "question",
        ""
    ).strip()

    if question:

        delete_knowledge(
            question
        )

    return redirect("/")


# ==============================
# CLEAR CHAT
# ==============================

@app.route(
    "/clear",
    methods=["POST"]
)
def clear():

    clear_chat()

    return redirect("/")


# ==============================
# RUN APP
# ==============================

setup_database()


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
