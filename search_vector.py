import os
import pandas as pd
import openai
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchFieldDataType,
    VectorSearch, HnswAlgorithmConfiguration, HnswParameters, VectorSearchProfile
)
import requests
import json
from dotenv import load_dotenv

load_dotenv()


# 環境変数からAzureのAPIキーを取得
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_GPT_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_GPT_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")

# OpenAI API クライアント設定
openai.api_type = "azure"
openai.api_key = AZURE_OPENAI_API_KEY
openai.api_base = AZURE_OPENAI_ENDPOINT
openai.api_version = "2023-07-01-preview"

# Azure AI Search クライアント設定
search_client = SearchClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    index_name=AZURE_SEARCH_INDEX_NAME,
    credential=AzureKeyCredential(AZURE_SEARCH_API_KEY)
)

# 埋め込みを取得する関数


def get_embedding(text):
    response = openai.embeddings.create(
        input=text,
        model="text-embedding-3-large"
    )
    return response.data[0].embedding

# ChatGPTの応答設定


def get_openai_response(messages):
    """
    Azure OpenAI Serviceにチャットメッセージを送信し、応答を取得する関数。

    Parameters:
    messages (list): チャットメッセージのリスト。各メッセージは辞書で、'role'と'content'を含む。

    Returns:
    str: アシスタントからの応答メッセージ。
    """
    # 環境変数からAPIキーとエンドポイントを取得
    api_key = os.getenv("AZURE_OPENAI_GPT_API_KEY")
    api_base = os.getenv("AZURE_OPENAI_GPT_ENDPOINT")
    deployment_name = os.getenv(
        "AZURE_OPENAI_GPT_DEPLOYMENT_NAME")  # デプロイメント名を環境変数から取得

    # エンドポイントURLの構築
    api_version = "2024-08-01-preview"  # 使用するAPIバージョンを指定
    endpoint = f"{api_base}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"

    # ヘッダーの設定
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    # リクエストデータの作成
    data = {
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 300
    }

    # POSTリクエストの送信
    response = requests.post(endpoint, headers=headers, data=json.dumps(data))

    # レスポンスの処理
    if response.status_code == 200:
        response_data = response.json()
        return response_data['choices'][0]['message']['content']
    else:
        raise Exception(
            f"Request failed with status code {response.status_code}: {response.text}")

# 研究者のマッチ理由を生成


def generate_explanation(query_text, researcher):
    prompt = f"""
    依頼内容: {query_text}
    研究名: {researcher["research_project_title"]}
    研究分野: {researcher["research_field_jp"]}
    研究キーワード: {researcher["keywords_jp"]}

    
    なぜこの研究者が依頼内容に適しているのかを簡潔に説明してください。
    """
    messages = [{"role": "system", "content": "あなたは検索結果の解説を行うアシスタントです。"},
                {"role": "user", "content": prompt}]

    return get_openai_response(messages)

# ベクトル検索


def search_researchers(category, field, description, top_k=10):
    query_text = f"{category} {field} {description}"
    embedding = get_embedding(query_text)

    results = search_client.search(
        search_text=None,  # ベクトル検索のみ行う場合はテキストクエリは空None
        vector_queries=[
            VectorizedQuery(
                vector=embedding,
                k_nearest_neighbors=top_k,
                fields="research_field_vectorization"
            )
        ],
        select=["researcher_id", "research_field_jp",
                "keywords_jp", "research_project_title"]
    )

    search_results = []
    for result in results:
        explanation = generate_explanation(query_text, result)
        search_results.append({
            "researcher_id": result["researcher_id"],
            "research_field_jp": result["research_field_jp"],
            "keywords_jp": result["keywords_jp"],
            "research_project_title": result["research_project_title"],
            "explanation": explanation,
            "score": result['@search.score'],  # スコア取得
        })

    return search_results
