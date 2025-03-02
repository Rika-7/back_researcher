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

#データベース接続情報の設定
config = {
    'host': os.getenv("DB_HOST"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'database': os.getenv("DB_NAME"),
    'charset': 'utf8mb4', # 日本語を扱うための設定
}

# If running on Azure, add SSL configuration
if os.getenv("AZURE_DEPLOYMENT", "false").lower() == "true":
    config.update({
        'client_flags': [mysql.connector.ClientFlag.SSL],
        'ssl_ca': '/home/site/certificates/DigiCertGlobalRootCA.crt.pem'
    })

#データベース接続情報の設定
def get_db_connection():
    try:
        conn = mysql.connector.connect(**config)
        return conn
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            raise HTTPException(status_code=500, detail="Database access denied")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            raise HTTPException(status_code=500, detail="Database does not exist")
        else:
            raise HTTPException(status_code=500, detail=str(err))

@app.get("/")
def read_root():
    return {"Hello": "World_updated"}

@app.get("/researchers")
def get_researchers():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM researcher_tsukuba LIMIT 10")
        researchers = cursor.fetchall()
        return {"researchers": researchers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
