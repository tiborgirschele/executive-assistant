from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Hardened boot logging
print("\n" + "!"*40, flush=True)
print("🚀 CHIEF OF STAFF SYSTEM BOOTING", flush=True)
print("!"*40 + "\n", flush=True)

from app.server import app
from app.poll_listener import poll_loop
from app.scheduler import scheduler_loop

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # This block executes when the server starts
    print("🤖 Background Threads: INITIALIZING...", flush=True)
    p_task = asyncio.create_task(poll_loop())
    s_task = asyncio.create_task(scheduler_loop())
    
    yield
    
    # Cleanup on shutdown
    print("🛑 Background Threads: TERMINATING...", flush=True)
    p_task.cancel()
    s_task.cancel()

# Attach lifespan to the existing FastAPI instance
app.router.lifespan_context = lifespan