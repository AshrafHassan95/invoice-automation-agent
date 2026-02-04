"""Run the Invoice Automation Agent server."""
import uvicorn

if __name__ == "__main__":
    print("Starting Invoice Automation Agent...")
    print("Server running at: http://localhost:8000")
    print("Press CTRL+C to stop.\n")
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
