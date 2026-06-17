import base64
import hashlib
import hmac
from typing import Any, TypedDict
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from leasing_voice_assistant.answer_orchestration import AnswerOrchestrator
from leasing_voice_assistant.config import Settings, get_settings
from leasing_voice_assistant.conversation_session import ConversationSessionService
from leasing_voice_assistant.database_tools import DatabaseQueryTools
from leasing_voice_assistant.fakes import (
    FakeModelProvider,
    FakeSpeechToTextProvider,
    FakeTextToSpeechProvider,
)
from leasing_voice_assistant.knowledge_base import MarkdownKnowledgeRetriever
from leasing_voice_assistant.persistence import (
    SQLitePropertyRepository,
    SQLiteProspectRepository,
    initialize_database,
)
from leasing_voice_assistant.prospect_capture import ProspectCaptureService
from leasing_voice_assistant.provider_adapters import (
    DeepgramSpeechToTextProvider,
    ElevenLabsTextToSpeechProvider,
    OpenAICompatibleModelProvider,
)
from leasing_voice_assistant.twilio_transport import (
    TwilioCallManager,
    TwilioVoiceWebhook,
    build_twilio_voice_twiml,
)
from leasing_voice_assistant.voice_pipeline import VoicePipeline


class HealthResponse(TypedDict):
    status: str
    service: str


def health() -> HealthResponse:
    return {"status": "ok", "service": "leasing-voice-assistant"}


def create_app(
    *,
    settings: Settings | None = None,
    twilio_call_manager: TwilioCallManager | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Leasing Voice Assistant")
    app.state.settings = settings
    app.state.twilio_call_manager = twilio_call_manager or build_twilio_call_manager(settings)

    app.get("/health", response_model=HealthResponse)(health)
    app.post("/twilio/voice")(twilio_voice)
    app.websocket("/twilio/media")(twilio_media)

    return app


async def twilio_voice(request: Request) -> Response:
    form = _parse_form(await request.body())
    settings: Settings = request.app.state.settings
    _validate_twilio_signature(settings, request, form)
    call_sid = form.get("CallSid", "")
    caller_phone = form.get("From")
    request.app.state.twilio_call_manager.start_call(call_sid, caller_phone=caller_phone)
    twiml = build_twilio_voice_twiml(
        TwilioVoiceWebhook(
            call_sid=call_sid,
            caller_phone=caller_phone,
            public_base_url=settings.telephony_public_base_url or str(request.base_url),
        )
    )
    return Response(content=twiml, media_type="application/xml")


async def twilio_media(websocket: WebSocket) -> None:
    await websocket.accept()
    manager: TwilioCallManager = websocket.app.state.twilio_call_manager
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            result = manager.handle_event(message)
            for outbound in result.outbound_messages:
                await websocket.send_json(outbound)
    except WebSocketDisconnect:
        return


def build_twilio_call_manager(settings: Settings) -> TwilioCallManager:
    return TwilioCallManager(voice_pipeline=build_voice_pipeline(settings))


def build_voice_pipeline(settings: Settings) -> VoicePipeline:
    connection = initialize_database()
    database_tools = DatabaseQueryTools(SQLitePropertyRepository(connection))
    session_service = ConversationSessionService(
        answer_orchestrator=AnswerOrchestrator(
            database_tools=database_tools,
            knowledge_retriever=MarkdownKnowledgeRetriever.from_directory(),
        ),
        prospect_capture_service=ProspectCaptureService(
            prospect_repository=SQLiteProspectRepository(connection)
        ),
        source="twilio_call",
    )
    return VoicePipeline(
        speech_to_text=_speech_to_text_provider(settings),
        model=_model_provider(settings),
        text_to_speech=_text_to_speech_provider(settings),
        session_service=session_service,
    )


def _model_provider(settings: Settings) -> Any:
    if settings.model_provider == "fake":
        return FakeModelProvider()
    return OpenAICompatibleModelProvider(
        api_key=settings.model_api_key,
        model=settings.model_name,
        base_url=settings.model_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
    )


def _speech_to_text_provider(settings: Settings) -> Any:
    if settings.speech_to_text_provider == "fake":
        return FakeSpeechToTextProvider()
    return DeepgramSpeechToTextProvider(
        api_key=settings.speech_to_text_api_key,
        model=settings.speech_to_text_model,
        timeout_seconds=settings.provider_timeout_seconds,
    )


def _text_to_speech_provider(settings: Settings) -> Any:
    if settings.text_to_speech_provider == "fake":
        return FakeTextToSpeechProvider()
    return ElevenLabsTextToSpeechProvider(
        api_key=settings.text_to_speech_api_key,
        voice_id=settings.text_to_speech_voice_id,
        model=settings.text_to_speech_model,
        output_format=settings.text_to_speech_output_format,
        timeout_seconds=settings.provider_timeout_seconds,
    )


def _parse_form(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode(), keep_blank_values=True)
    return {
        key: values[-1]
        for key, values in parsed.items()
        if values and isinstance(key, str) and isinstance(values[-1], str)
    }


def _validate_twilio_signature(
    settings: Settings,
    request: Request,
    form: dict[str, str],
) -> None:
    if settings.telephony_auth_token is None:
        return
    provided = request.headers.get("x-twilio-signature")
    if not provided:
        raise HTTPException(status_code=403, detail="Missing Twilio signature")
    public_base_url = settings.telephony_public_base_url
    url = (
        f"{public_base_url.rstrip('/')}{request.url.path}" if public_base_url else str(request.url)
    )
    expected = _twilio_signature(
        url,
        form,
        settings.telephony_auth_token.get_secret_value(),
    )
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


def _twilio_signature(url: str, form: dict[str, str], auth_token: str) -> str:
    signed = url + "".join(f"{key}{form[key]}" for key in sorted(form))
    digest = hmac.new(auth_token.encode(), signed.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


app = create_app()
