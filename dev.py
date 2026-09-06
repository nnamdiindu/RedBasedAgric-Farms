import uvicorn

# Local dev runner. Run with: python dev.py
# Uses the exact same `app` object Vercel deploys — no drift possible.

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)