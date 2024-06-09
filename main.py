import json
import uuid

import socketio
from deep_translator import DeeplTranslator
from loguru import logger
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models.user import UserCreateModel, UserSignInModel


app = FastAPI()
origins = [
    "http://localhost:5173",
    "http://95.163.223.109:8080",
    "http://95.163.223.109",
]

# Socket io (sio) create a Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],
    logger=True,
    engineio_logger=True,
)
# wrap with ASGI application
socket_app = socketio.ASGIApp(sio)
app.mount("/socket.io", socket_app)


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

current_users = []


@app.get("/")
async def root():
    return {}


@app.post("/api/user/create")
async def user_create(user: UserCreateModel):
    user_id = uuid.uuid4()
    for el in current_users:
        if el["username"] == user.username:
            raise HTTPException(status_code=400, detail="Username already exists")
    current_users.append(
        {
            "user_id": str(user_id),
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "online": "Online",
        }
    )
    await sio.emit("update-user-list", {"users": current_users})
    return {
        "user_id": user_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


@app.post("/api/user/sign-in")
async def get_user(user: UserSignInModel):
    i = 0
    for el in current_users:
        if el["username"] == user.username:
            current_users[i]["online"] = "Online"
        i += 1

    for el in current_users:
        if el["username"] == user.username:
            await sio.emit("update-user-list", {"users": current_users})
            return {
                "user_id": el["user_id"],
                "first_name": el["first_name"],
                "last_name": el["last_name"],
            }
    raise HTTPException(status_code=404, detail="User not found")


@sio.on("joinRoom")
async def join_room(sid, data):
    i = 0
    for el in current_users:
        if el["user_id"] == data["user_id"]:
            current_users[i]["online"] = "Online"
        i += 1
    await sio.enter_room(sid, data["user_id"])


@sio.on("requestUserList")
async def request_user_list(sid, data):
    """Update list of users."""

    await sio.emit("update-user-list", {"users": current_users})


@sio.on("userLeave")
async def leave_user(sid, data):
    i = 0
    logger.info(f"User left {data}")
    for el in current_users:
        if el["user_id"] == data:
            current_users[i]["online"] = "Offline"
        i += 1

    await sio.emit("update-user-list", {"users": current_users})


@sio.on("requestCalling")
async def request_calling_user(sid, data):
    current_user_id = data["to"]
    i = 0
    for el in current_users:
        if el["user_id"] == current_user_id:
            current_users[i]["online"] = "InCall"
        i += 1
    await sio.emit("update-user-list", {"users": current_users})
    await sio.emit("request_calling_user", data, room=data["to"])


@sio.on("cancelCall")
async def cancel_call(sid, data):
    await sio.emit("cancel_call", {}, room=data["to"])


@sio.on("confirmCall")
async def confirm_call(sid, data):
    from_user_id = data["from"]
    i = 0
    for el in current_users:
        if el["user_id"] == from_user_id:
            current_users[i]["online"] = "InCall"
        i += 1
    await sio.emit("update-user-list", {"users": current_users})
    await sio.emit("confirm_call", data, room=data["from"])
    await sio.emit("confirm_call", data, room=data["to"])


@sio.on("translate")
async def translate(sid, data):
    text = data["text"]
    original_language = data["original_language"]
    translate_language = data["translate_language"]
    send_to = data["to"]
    print(text)
    translated = DeeplTranslator(
        source=original_language,
        target=translate_language,
        api_key="33358def-90a8-4398-b498-fa95fade6806:fx",
    ).translate(text)

    await sio.emit("translated_text", {"translated_text": translated}, room=send_to)


@sio.on("endCall")
async def end_call(sid, data):
    i = 0
    for el in current_users:
        if el["user_id"] == data["from"] or el["user_id"] == data["to"]:
            current_users[i]["online"] = "Online"
        i += 1
    await sio.emit("end_call", data, room=data["from"])
    await sio.emit("end_call", data, room=data["to"])
    await sio.emit("update-user-list", {"users": current_users})
