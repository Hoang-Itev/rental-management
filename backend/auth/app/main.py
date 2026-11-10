from fastapi import FastAPI

app = FastAPI(title="auth", version="0.1.0")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}

# TODO: /ready must check the dependencies needed for serving requests.
# TODO: add routers after their API contracts and schemas are implemented.