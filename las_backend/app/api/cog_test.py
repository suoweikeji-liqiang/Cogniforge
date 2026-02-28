from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from app.services.llm_service import llm_service
from app.core.auth import get_current_user

router = APIRouter(prefix="/cog-test", tags=["cognitive-test"])


@router.get("/stream-test")
async def stream_test(current_user=Depends(get_current_user)):
    async def event_generator():
        async for token in llm_service.stream_generate(
            messages=[{"role": "user", "content": "Say hello in 10 words"}],
            system_prompt="You are a helpful assistant.",
        ):
            yield {"event": "token", "data": token}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())
