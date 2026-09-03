import os
import sys
import argparse
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings, BASE_DIR
from app.database import init_db
from app.bot.bot_app import create_bot_application

# Routers
from app.web.routes.auth_routes import router as auth_router
from app.web.routes.dashboard_routes import router as dashboard_router
from app.web.routes.vacancy_routes import router as vacancy_router
from app.web.routes.application_routes import router as application_router
from app.web.routes.candidate_routes import router as candidate_router
from app.web.routes.settings_routes import router as settings_router
from app.web.routes.interview_routes import router as interview_router

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

bot_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_instance
    logger.info("Initializing Recruitment Automation Platform...")
    
    # 1. Initialize database tables and seeds
    await init_db()
    logger.info("Database initialized successfully.")

    # 2. Start Telegram Bot if configured and not explicitly disabled
    run_bot = os.getenv("RUN_BOT", "true").lower() == "true"
    if run_bot and settings.TELEGRAM_BOT_TOKEN:
        try:
            bot_instance = create_bot_application(settings.TELEGRAM_BOT_TOKEN)
            if bot_instance:
                await bot_instance.initialize()
                await bot_instance.start()
                await bot_instance.updater.start_polling()
                logger.info("Telegram Bot polling started successfully!")
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot: {e}", exc_info=True)
    else:
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.info("TELEGRAM_BOT_TOKEN not provided. Bot runner is idle. Web dashboard is active.")

    yield

    # Shutdown
    if bot_instance:
        logger.info("Stopping Telegram Bot...")
        try:
            if bot_instance.updater and bot_instance.updater.running:
                await bot_instance.updater.stop()
            if bot_instance.running:
                await bot_instance.stop()
            await bot_instance.shutdown()
            logger.info("Telegram Bot stopped cleanly.")
        except Exception as e:
            logger.error(f"Error during bot shutdown: {e}")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None
)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# Custom exception handler for browser auth redirects
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 307 and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=303)
    if exc.status_code == 401 and not request.url.path.startswith("/api/"):
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=303)
    return await http_exception_handler(request, exc)

# Mount Static Files
static_dir = os.path.join(BASE_DIR, "app/web/static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include Routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(vacancy_router)
app.include_router(application_router)
app.include_router(candidate_router)
app.include_router(interview_router)
app.include_router(settings_router)

def run_cli():
    parser = argparse.ArgumentParser(description="Telegram Recruitment Automation Platform")
    parser.add_argument("--mode", choices=["all", "web", "bot"], default="all", help="Execution mode")
    parser.add_argument("--host", default=settings.HOST, help="Web server host")
    parser.add_argument("--port", type=int, default=settings.PORT, help="Web server port")
    args = parser.parse_args()

    if args.mode == "web":
        os.environ["RUN_BOT"] = "false"
    elif args.mode == "bot":
        async def start_only_bot():
            await init_db()
            if not settings.TELEGRAM_BOT_TOKEN:
                logger.error("TELEGRAM_BOT_TOKEN required to run bot mode.")
                return
            bot = create_bot_application(settings.TELEGRAM_BOT_TOKEN)
            await bot.initialize()
            await bot.start()
            await bot.updater.start_polling()
            logger.info("Bot running in standalone mode. Press Ctrl+C to stop.")
            while True:
                await asyncio.sleep(3600)
        try:
            asyncio.run(start_only_bot())
        except (KeyboardInterrupt, SystemExit):
            pass
        return

    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=settings.DEBUG)

if __name__ == "__main__":
    run_cli()
