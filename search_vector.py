import os
import pandas as pd
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
import requests
import json
from dotenv import load_dotenv

load_dotenv()

print("Environment variables loaded from .env file")

# Environment variables with proper string defaults
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_GPT_API_KEY = os.getenv("AZURE_OPENAI_GPT_API_KEY", "")
AZURE_OPENAI_GPT_ENDPOINT = os.getenv("AZURE_OPENAI_GPT_ENDPOINT", "")
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY", "")
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "")
AZURE_OPENAI_GPT_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_GPT_DEPLOYMENT_NAME", "")

print(f"AZURE_SEARCH_INDEX_NAME: {AZURE_SEARCH_INDEX_NAME}")

# Azure AI Search client setting
try:
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY)
    )
    print("Azure Search client initialized successfully")
except Exception as e:
    print(f"Error initializing Azure Search client: {str(e)}")
    search_client = None

# Helper function: Examine index structure
def explore_index_structure():
    try:
        if not search_client:
            print("Search client not initialized")
            return False
            
        # Get first document to check field structure
        results = search_client.search(search_text="*", top=1)
        sample_doc = next(results, None)
        
        if sample_doc:
            print("\nIndex structure:")
            for field_name in sample_doc.keys():
                if not field_name.startswith('@'):
                    field_value = sample_doc[field_name]
                    value_preview = str(field_value)[:50] + "..." if len(str(field_value)) > 50 else str(field_value)
                    print(f"- {field_name}: {value_preview}")
            return True
        else:
            print("No documents found in index.")
            return False
    except Exception as e:
        print(f"Error checking index structure: {str(e)}")
        return False

# Get embedding using direct REST API call
def get_embedding(text):
    try:
        api_version = "2023-07-01-preview"
        endpoint = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/text-embedding-3-large/embeddings?api-version={api_version}"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_API_KEY
        }
        
        data = {
            "input": text,
            "model": "text-embedding-3-large"
        }
        
        response = requests.post(endpoint, headers=headers, data=json.dumps(data))
        
        if response.status_code == 200:
            response_data = response.json()
            return response_data['data'][0]['embedding']
        else:
            print(f"Embedding API error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Error generating embedding: {str(e)}")
        return []

# ChatGPT response using direct REST API call
def get_openai_response(messages):
    try:
        api_version = "2024-08-01-preview"
        endpoint = f"{AZURE_OPENAI_GPT_ENDPOINT}/openai/deployments/{AZURE_OPENAI_GPT_DEPLOYMENT_NAME}/chat/completions?api-version={api_version}"

        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_GPT_API_KEY
        }

        data = {
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 300
        }

        response = requests.post(endpoint, headers=headers, data=json.dumps(data))

        if response.status_code == 200:
            response_data = response.json()
            return response_data['choices'][0]['message']['content']
        else:
            error_msg = f"Request failed with status code {response.status_code}: {response.text}"
            print(error_msg)
            return f"Error occurred: {error_msg}"
    except Exception as e:
        print(f"API call error: {str(e)}")
        return f"Error occurred: {str(e)}"

# Generate explanation for researcher match
def generate_explanation(query_text, researcher):
    # Use fields that exist in the index
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

# Vector search
def search_researchers(category, field, description, top_k=10):
    print(f"Search request: category={category}, field={field}, description={description}, top_k={top_k}")
    query_text = f"{category} {field} {description}"
    
    try:
        print(f"Generating embedding for: {query_text}")
        embedding = get_embedding(query_text)
        if not embedding or len(embedding) == 0:
            print("Failed to generate embedding")
            return []
    except Exception as e:
        print(f"Error getting embedding: {str(e)}")
        return []

    # Explore index structure first
    explore_index_structure()

    try:
        print("Executing vector search")
        # Execute vector search
        results = search_client.search(
            search_text=None,  # No text query for vector-only search
            vector_queries=[
                VectorizedQuery(
                    vector=embedding,
                    k_nearest_neighbors=top_k,
                    fields="research_field_vectorization"  # Correct field name
                )
            ],
            select=["id", "researcher_id", "research_field_pi", "keywords_pi", "research_project_title"]
        )

        search_results = []
        result_count = 0
        
        for result in results:
            result_count += 1
            try:
                print(f"Processing result {result_count}")
                explanation = generate_explanation(query_text, result)
                search_results.append({
                    "researcher_id": result.get("researcher_id", "不明"),
                    "research_field_jp": result.get("research_field_pi", "不明"),  # Map to expected response model field
                    "keywords_jp": result.get("keywords_pi", "不明"),  # Map to expected response model field
                    "research_project_title": result.get("research_project_title", "不明"),
                    "explanation": explanation,
                    "score": result.get('@search.score', 0),  # Get score
                })
                print(f"Processed result {result_count}")
            except Exception as e:
                print(f"Error processing result {result_count}: {str(e)}")
        
        print(f"Found {len(search_results)} results")
        return search_results
    
    except Exception as e:
        print(f"Search error: {str(e)}")
        if "Cannot find nested property" in str(e):
            print("Error hint: Index field names might not match. Run register_index.py to create a properly defined index and register researcher data.")
        return []

# Test functionality when run directly
if __name__ == "__main__":
    print("Script is running directly - performing a test search")
    try:
        # Simple test with sample data
        test_category = "AI"
        test_field = "自然言語処理"
        test_description = "文章の感情分析に関する研究"
        
        print(f"Testing search with: Category={test_category}, Field={test_field}, Description={test_description}")
        
        # Get embeddings to test the OpenAI connection
        print("Getting embeddings...")
        test_text = f"{test_category} {test_field} {test_description}"
        try:
            embedding = get_embedding(test_text)
            if embedding and len(embedding) > 0:
                print(f"Successfully generated embedding with {len(embedding)} dimensions")
            else:
                print("Failed to generate embedding")
        except Exception as e:
            print(f"Error getting embedding: {str(e)}")
        
        # Perform search to test the Azure Search connection
        print("Performing search...")
        results = search_researchers(test_category, test_field, test_description, top_k=3)
        
        # Display results
        print(f"\nFound {len(results)} matching researchers:")
        for i, result in enumerate(results):
            print(f"\n--- Result {i+1} ---")
            print(f"Researcher ID: {result['researcher_id']}")
            print(f"Research Title: {result['research_project_title']}")
            print(f"Research Field: {result['research_field_jp']}")
            print(f"Keywords: {result['keywords_jp']}")
            print(f"Score: {result['score']}")
            print(f"Explanation: {result['explanation']}")
            
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {str(e)}")