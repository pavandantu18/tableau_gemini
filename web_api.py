# web_api.py – Gemini 2.5 Flash Tableau Dashboard Assistant

import os
import pandas as pd
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware # NEW: For Vercel/Cloud Deployment
from pydantic import BaseModel

import google.generativeai as genai

# ----------------------
# Load environment (.env)
# ----------------------
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set in .env")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-2.5-flash"
gemini_model = genai.GenerativeModel(MODEL_NAME)

# ----------------------
# FastAPI app setup
# ----------------------
app = FastAPI(
    title="Tableau Gemini Dashboard Assistant",
    description="Gemini chatbot that reads Tableau worksheet data",
)

# ----------------------
# ✨ CORS MIDDLEWARE SETUP (Required for Vercel/Cloud Deployment) ✨
# ----------------------
# IMPORTANT: Replace these with your actual Tableau Cloud/Server domains
tableau_origins = [
    "http://127.0.0.1:8000",                  # Localhost for local testing
    "http://localhost:8000",                  # Localhost for local testing
    "https://us-east-1.online.tableau.com",   # Tableau Cloud domain
    # Add your Vercel URL here after deployment (e.g., "https://gemini-tableau-app.vercel.app")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=tableau_origins, 
    allow_methods=["POST", "GET"], 
    allow_headers=["*"],
    allow_credentials=True, 
)

app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    message: str
    tableau: dict | None = None  # { sheetName, columns, rows }


class ChatResponse(BaseModel):
    response: str


@app.get("/")
def home():
    """Serve the main HTML page (extension UI)."""
    return FileResponse("static/index.html")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Main chat endpoint. Receives user message and Tableau data context."""
    try:
        user_message = request.message
        tableau_info = request.tableau or {}

        tableau_context = "No Tableau data was provided for context. Answer the question generally."
        
        if tableau_info:
            sheet_name = tableau_info.get("sheetName", "Unknown worksheet")
            columns = tableau_info.get("columns", [])
            rows = tableau_info.get("rows", [])

            try:
                # 1. Create DataFrame
                df = pd.DataFrame(rows, columns=columns)

                # 2. Type Coercion: Attempt to convert all columns to numeric, coercing errors to NaN
                # This ensures cleaner data for Gemini to interpret
                df = df.apply(pd.to_numeric, errors='ignore')

                row_count = len(df)
                col_count = len(df.columns)

                # 3. CONVERT DATA TO CSV STRING for the AI
                data_csv = df.to_csv(index=False)
                
                # 4. Construct Data Context for Gemini with Raw Data
                tableau_context = (
                    f"The user is viewing a Tableau worksheet named '{sheet_name}'.\n"
                    f"It contains {row_count} rows and {col_count} columns.\n"
                    f"Column names: {columns}.\n"
                    "The **full raw data** extracted from the current worksheet is provided below in CSV format. "
                    "Use this data to perform detailed analysis, comparisons, and calculations to answer the user's question.\n"
                    "Ensure your analysis is precise and based strictly on the provided data.\n\n"
                    f"--- RAW DATA START ---\n"
                    f"{data_csv}\n"
                    f"--- RAW DATA END ---\n"
                )

            except Exception as e:
                # Fallback context if data processing fails
                tableau_context = (
                    f"Tableau data was provided but could not be processed into CSV: {e}. "
                    "Answer the question generally based on the column names: {columns}."
                )

        # 5. Construct the final Prompt
        prompt = (
            "You are an expert data analyst AI assistant embedded in a Tableau dashboard. "
            "You have received the **raw data** from the user's current worksheet in CSV format. "
            "**Perform the necessary calculations and analysis based on the provided data context.** "
            "Answer the user's question clearly, precisely, and maintain a professional, analytic tone.\n\n"
            f"User question:\n{user_message}\n\n"
            f"Tableau data context:\n{tableau_context}"
        )

        # 6. Generate Content using Gemini
        response = gemini_model.generate_content(prompt)
        answer = getattr(response, "text", "") or ""
        
        if not answer.strip():
            answer = "I couldn't generate a response. The model may have blocked the content or the prompt was too vague. Please try rephrasing your question."

        return ChatResponse(response=answer)

    except Exception as e:
        print("GEMINI/BACKEND ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e!r}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)