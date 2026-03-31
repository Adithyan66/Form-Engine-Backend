import os

from fastapi import FastAPI, Request
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

# Mount Slack endpoints only when Slack credentials are configured
if os.environ.get("SLACK_BOT_TOKEN") and os.environ.get("SLACK_SIGNING_SECRET"):
    from app.slack.bot import slack_handler

    @app.post("/slack/events")
    async def slack_events(request: Request):
        """Slack Events API and Interactivity endpoint."""
        return await slack_handler.handle(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
