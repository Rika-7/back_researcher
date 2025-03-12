import os
import pandas as pd
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

print("Environment variables loaded from .env file")

# 環境変数からAzureのAPIキーを取得
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_GPT_API_KEY = os.getenv("AZURE_OPENAI_GPT_API_KEY")
AZURE_OPENAI_GPT_ENDPOINT = os.getenv("AZURE_OPENAI_GPT_ENDPOINT")
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY") or ""
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")
AZURE_OPENAI_GPT_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_GPT_DEPLOYMENT_NAME")

# Initialize Azure OpenAI client (new style)
azure_openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version="2023-07-01-preview",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

# Azure AI Search クライアント設定
search_client = SearchClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    index_name=AZURE_SEARCH_INDEX_NAME,
    credential=AzureKeyCredential(AZURE_SEARCH_API_KEY)
)

# ヘルパー関数：インデックスの構造を調べる
def explore_index_structure():
    try:
        # 最初のドキュメントを取得してフィールド構造を確認
        results = search_client.search(search_text="*", top=1)
        sample_doc = next(results, None)
        
        if sample_doc:
            print("\nインデックスのフィールド構造:")
            for field_name in sample_doc.keys():
                if not field_name.startswith('@'):
                    field_value = sample_doc[field_name]
                    value_preview = str(field_value)[:50] + "..." if len(str(field_value)) > 50 else str(field_value)
                    print(f"- {field_name}: {value_preview}")
            return True
        else:
            print("インデックスにドキュメントが見つかりませんでした。")
            return False
    except Exception as e:
        print(f"インデックス構造の確認中にエラーが発生しました: {str(e)}")
        return False

# 埋め込みを取得する関数
def get_embedding(text):
    response = azure_openai_client.embeddings.create(
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
    # エンドポイントURLの構築
    api_version = "2024-08-01-preview"  # 使用するAPIバージョンを指定
    endpoint = f"{AZURE_OPENAI_GPT_ENDPOINT}/openai/deployments/{AZURE_OPENAI_GPT_DEPLOYMENT_NAME}/chat/completions?api-version={api_version}"

    # ヘッダーの設定
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_GPT_API_KEY
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
    # 以前は research_field_jp と keywords_jp を使っていたが、
    # インデックスに存在するフィールド名を使用するよう修正
    research_field = researcher.get("research_field_pi", researcher.get("research_field_jp", ""))
    keywords = researcher.get("keywords_pi", researcher.get("keywords_jp", ""))
    title = researcher.get("research_project_title", "")
    
    prompt = f"""
    依頼内容: {query_text}
    研究名: {title}
    研究分野: {research_field}
    研究キーワード: {keywords}
    
    なぜこの研究者が依頼内容に適しているのかを簡潔に説明してください。
    """
    messages = [{"role": "system", "content": "あなたは検索結果の解説を行うアシスタントです。"},
                {"role": "user", "content": prompt}]

    return get_openai_response(messages)

# ベクトル検索
def search_researchers(category, field, description, top_k=10):
    query_text = f"{category} {field} {description}"
    embedding = get_embedding(query_text)

    # まずインデックスの構造を探索
    explore_index_structure()

    try:
        # ベクトル検索を実行
        results = search_client.search(
            search_text=None,  # ベクトル検索のみ行う場合はテキストクエリは空None
            vector_queries=[
                VectorizedQuery(
                    vector=embedding,
                    k_nearest_neighbors=top_k,
                    fields="research_field_vectorization"  # 正しいフィールド名
                )
            ],
            select=["id", "researcher_id", "research_field_pi", "keywords_pi", "research_project_title"]
        )

        search_results = []
        result_count = 0
        
        for result in results:
            result_count += 1
            try:
                explanation = generate_explanation(query_text, result)
                search_results.append({
                    "researcher_id": result.get("researcher_id", "不明"),
                    "research_field_pi": result.get("research_field_pi", result.get("research_field_jp", "不明")),
                    "keywords_pi": result.get("keywords_pi", result.get("keywords_jp", "不明")),
                    "research_project_title": result.get("research_project_title", "不明"),
                    "explanation": explanation,
                    "score": result.get('@search.score', 0),  # スコア取得
                })
            except Exception as e:
                print(f"結果 {result_count} の処理中にエラーが発生しました: {str(e)}")
        
        return search_results
    
    except Exception as e:
        print(f"検索中にエラーが発生しました: {str(e)}")
        if "Cannot find nested property" in str(e):
            print("エラー解決のヒント: インデックスのフィールド名が一致していない可能性があります。")
            print("register_index.py を実行して正しいフィールド定義のインデックスを作成してから、研究者データを登録してください。")
        return []

# Test functionality when run directly
if __name__ == "__main__":
    print("Script is running directly - performing a test search")
    try:
        # Simple test with sample data
        test_category = "AI"
        test_field = "自然言語処理"
        test_description = "文章の感情分析に関する研究"
        
        print(f"Testing search with: Category: {test_category}, Field: {test_field}, Description: {test_description}")
        
        # Get embeddings to test the OpenAI connection
        print("Getting embeddings...")
        test_text = f"{test_category} {test_field} {test_description}"
        try:
            embedding = get_embedding(test_text)
            print(f"Successfully generated embedding with {len(embedding)} dimensions")
        except Exception as e:
            print(f"Error getting embedding: {str(e)}")
            raise
        
        # Perform search to test the Azure Search connection
        print("Performing search...")
        results = search_researchers(test_category, test_field, test_description, top_k=3)
        
        # Display results
        print(f"\nFound {len(results)} matching researchers:")
        for i, result in enumerate(results):
            print(f"\n--- Result {i+1} ---")
            print(f"Researcher ID: {result['researcher_id']}")
            print(f"Research Title: {result['research_project_title']}")
            print(f"Research Field: {result['research_field_pi']}")
            print(f"Keywords: {result['keywords_pi']}")
            print(f"Score: {result['score']}")
            print(f"Explanation: {result['explanation']}")
            
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {str(e)}")