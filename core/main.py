from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.orchestrator_structured import ask_friday
from services.api.websocket import friday_websocket


app = FastAPI(
    title="FRIDAY",
    description="Personal AI Operating Layer",
    version="0.1.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================


class ChatRequest(BaseModel):

    message: str


# ============================================================
# ROOT
# ============================================================


@app.get("/")
async def root():

    return {
        "name": "FRIDAY",
        "status": "online",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():

    return {
        "status": "healthy",
    }


# ============================================================
# CHAT
# ============================================================


@app.post("/chat")
async def chat(request: ChatRequest):

    try:

        response = await ask_friday(
            request.message
        )

        return {
            "response": response,
        }

    except Exception as error:

        print(
            f"[FRIDAY] Chat error: {error}"
        )

        return {
            "response": (
                "I couldn't complete that request "
                "because the AI service is currently "
                "unavailable. Please try again."
            ),
            "error": str(error),
        }


# ============================================================
# WEBSOCKET
# ============================================================


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await friday_websocket(websocket)
