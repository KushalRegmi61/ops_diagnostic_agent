from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (register tables with Base.metadata)
from app.database import Base, engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Ops Diagnostic Agent", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
