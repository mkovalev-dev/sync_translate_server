import json
from io import BytesIO

from deep_translator import DeeplTranslator
import socketio
from fastapi import FastAPI
from loguru import logger
from pydub import AudioSegment

from vosk import Model, KaldiRecognizer

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio)
app = FastAPI()

app.mount("/", socket_app)  # Here we mount socket app to main fastapi app

connected_users = {}

russian_rec = KaldiRecognizer(
    Model(model_path="./lib/vosk-model-small-ru-0.22 2"), 48000
)
english_rec = KaldiRecognizer(
    Model(model_path="./lib/vosk-model-en-us-0.22-lgraph"), 48000
)


@sio.on("connect")
async def connect(sid, env):
    """Handle initial connection of socket user."""
    connected_users[sid] = {"inCalling": False, "callInfo": {}}
    logger.info(f"User {sid} connected")


@sio.on("disconnect")
async def disconnect(sid):
    """Handle disconnection."""
    connected_users.pop(sid)
    logger.info(f"User {sid} disconnected")


@sio.on("checkExistCallingUser")
async def check_exist_calling_user(sid, data):
    await sio.emit(
        "checkExistCallingUser",
        {
            "user_exist": True if connected_users.get(data["to"], None) else False,
            "calling_user": data["to"],
        },
        to=sid,
    )


@sio.on("checkUserBusy")
async def check_user_busy(sid, data):
    if calling_user := connected_users.get(data["to"], None):
        await sio.emit(
            "checkUserBusy",
            {
                "user_busy": calling_user["inCalling"],
                "calling_user": data["to"],
            },
            to=sid,
        )


@sio.on("requestCall")
async def request_call(sid, data):
    connected_users[data["to"]]["inCalling"] = True
    connected_users[sid]["inCalling"] = True
    await sio.emit("requestCall", {"from": sid}, to=data["to"])


@sio.on("cancelRequestCall")
async def cancel_request_call(sid, data):
    connected_users[data["to"]]["inCalling"] = False
    connected_users[sid]["inCalling"] = False
    await sio.emit("cancelRequestCall", {"from": sid}, to=data["to"])


@sio.on("cancelOfferCall")
async def cancel_offer_call(sid, data):
    connected_users[data["from"]]["inCalling"] = False
    connected_users[sid]["inCalling"] = False
    await sio.emit("cancelOfferCall", {}, to=data["from"])


@sio.on("acceptOfferCall")
async def accept_offer_call(sid, data):
    await sio.emit(
        "acceptOfferCall", {"from": data["from"], "to": sid}, to=data["from"]
    )
    await sio.emit("acceptOfferCall", {"from": data["from"], "to": sid}, to=sid)


@sio.on("endCall")
async def end_call(sid, data):
    connected_users[data["from"]]["inCalling"] = False
    connected_users[sid]["inCalling"] = False

    await sio.emit("endCall", {"from": data["from"], "to": sid}, to=data["from"])


@sio.on("audioTransfer")
async def audio_transfer(sid, data):
    if data["originalVoice"] == "RU":
        rec = russian_rec
        original_translation_voice = "ru"
    elif data["originalVoice"] == "EN-US":
        rec = english_rec
        original_translation_voice = "en"
    else:
        raise AttributeError("Original Voice not supported")

    if data["translateVoice"] == "RU":
        translation_voice = "ru"
    elif data["translateVoice"] == "EN-US":
        translation_voice = "en"
    else:
        raise AttributeError("Original Voice not supported")

    logger.info(f"User {sid} audio stream")
    sound = AudioSegment.from_file(BytesIO(data["audio"]), codec="opus")
    if rec.AcceptWaveform(sound.raw_data):
        res = rec.Result()
        original_text = str(json.loads(res)["text"])
        logger.info(f"User {sid} send transcript: {original_text} to {data['to']}")
        translated = DeeplTranslator(
            source=original_translation_voice,
            target=translation_voice,
            api_key="33358def-90a8-4398-b498-fa95fade6806:fx",
        ).translate(original_text)
        await sio.emit(
            "audioTransfer",
            {
                "text": translated,
                "from": sid,
                "to": data["to"],
            },
            to=data["to"],
        )
        logger.info(
            f"User {original_text} send translated transcript: {translated} to {data['to']}"
        )
