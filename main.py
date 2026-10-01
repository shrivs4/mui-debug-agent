from fastapi import FastAPI
from pydantic import BaseModel
from agent import call_claude

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
    conversation_id = body.conversation_id
    response = call_claude(question, conversation_id)
    return {"answer": response}
