from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import health, datasets, udruge, pipeline, financiranje

app = FastAPI(
    title="HR Open Data API",
    description="Croatian Open Data Pipeline — NGO Registry and more",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(datasets.router)
app.include_router(udruge.router)
app.include_router(pipeline.router)
app.include_router(financiranje.router)


@app.get("/")
def root():
    return {"message": "HR Open Data API", "docs": "/docs"}
