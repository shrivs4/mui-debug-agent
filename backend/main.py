from fastapi import FastAPI
from pydantic import BaseModel
from agent import call_claude, is_mui

app = FastAPI()


class Question(BaseModel):
    question: str
    conversation_id: str


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.post("/ask")
def ask(body: Question):
    question = body.question
    if not is_mui(question):
        return {
            "answer": """I can only help with MUI (Material UI, MUI X, Joy UI) questions — bugs, errors, theming or styling. Try asking about a component that isn't behaving."""
        }
    else:
        conversation_id = body.conversation_id
        response = call_claude(question, conversation_id)
        return {"answer": response}
