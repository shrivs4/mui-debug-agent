from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()


def embed_text(text):
    response = client.embeddings.create(model="text-embedding-3-small", input=text)
    return response.data[0].embedding
