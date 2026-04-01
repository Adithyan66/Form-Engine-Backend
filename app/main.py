import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router

app = FastAPI(title="Dynamic Form Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Start Slack Socket Mode when credentials are configured
if os.environ.get("SLACK_BOT_TOKEN") and os.environ.get("SLACK_APP_TOKEN"):
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from app.slack.bot import slack_app

    @app.on_event("startup")
    async def start_slack_socket_mode():
        handler = AsyncSocketModeHandler(
            slack_app, os.environ["SLACK_APP_TOKEN"]
        )
        asyncio.create_task(handler.start_async())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3333)
