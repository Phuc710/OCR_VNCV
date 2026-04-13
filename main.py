from fastapi import FastAPI
from router import ocr_router, mount_web

app = FastAPI()
app.include_router(ocr_router)
mount_web(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

