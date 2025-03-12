from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import mysql.connector
from mysql.connector import errorcode
import os
from dotenv import load_dotenv
from datetime import datetime
import traceback  # Add traceback for better error logging

# Import with try-except to handle potential import errors
try:
    from search_vector import search_researchers
    print("Successfully imported search_researchers")
except Exception as e:
    print(f"Error importing search_researchers: {str(e)}")
    traceback.print_exc()

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# CORSミドルウェアを追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app-advanced3-4-aygnfjh3hxbyducf.canadacentral-01.azurewebsites.net",  # Production
        "http://localhost:3000",  # Local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# データベース接続情報の設定
config = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'database': os.getenv("DB_NAME"),
    'charset': 'utf8mb4',  # 日本語を扱うための設定
}

# If running on Azure, add SSL configuration
if os.getenv("AZURE_DEPLOYMENT", "false").lower() == "true":
    config.update({
        'client_flags': [mysql.connector.ClientFlag.SSL],
        'ssl_ca': '/home/site/certificates/DigiCertGlobalRootCA.crt.pem'
    })

def get_db_connection():
    try:
        conn = mysql.connector.connect(**config)
        return conn
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            raise HTTPException(
                status_code=500, detail="Database access denied")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            raise HTTPException(
                status_code=500, detail="Database does not exist")
        else:
            raise HTTPException(status_code=500, detail=str(err))


@app.get("/")
def read_root():
    return {"Hello": "World_updated"}


@app.get("/researchers")
def get_researchers():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM researcher_tsukuba LIMIT 10")
        researchers = cursor.fetchall()
        return {"researchers": researchers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if conn:
            conn.close()


# リクエストモデル
class SearchRequest(BaseModel):
    category: str
    field: str
    description: str
    top_k: int = 10  # 10件取得

# レスポンスモデル
class ResearcherResponse(BaseModel):
    researcher_id: str
    research_field_jp: str
    keywords_jp: str
    research_project_title: str
    explanation: str
    score: float


@app.post("/search_researchers", response_model=List[ResearcherResponse])
async def search_researchers_api(request: SearchRequest):
    try:
        print(f"Received search request: {request.dict()}")
        
        if 'search_researchers' not in globals():
            raise HTTPException(
                status_code=500, 
                detail="search_researchers function not available. Check module import."
            )
            
        search_results = search_researchers(
            category=request.category,
            field=request.field,
            description=request.description,
            top_k=request.top_k
        )
        
        if not search_results:
            print("No search results returned")
            return []
            
        print(f"Found {len(search_results)} results")
        return search_results
        
    except Exception as e:
        error_message = str(e)
        print(f"Error in search_researchers_api: {error_message}")
        traceback.print_exc()  # Print full traceback for debugging
        raise HTTPException(status_code=500, detail=error_message)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)