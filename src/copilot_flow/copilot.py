# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
# set environment variables before importing any other code
from dotenv import load_dotenv
load_dotenv()

from pathlib import Path

from typing import TypedDict

from openai import AzureOpenAI

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from promptflow.tracing import trace
from promptflow.core import Prompty, AzureOpenAIModelConfiguration

class ChatResponse(TypedDict):
    context: dict
    reply: str

@trace
def get_chat_response(chat_input: str, chat_history: list = []) -> ChatResponse:

    model_config = AzureOpenAIModelConfiguration(
        azure_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"]
    )

    searchQuery = chat_input

    # Only extract intent if there is chat_history
    if len(chat_history) > 0:
        # extract current query intent given chat_history
        path_to_prompty = f"{Path(__file__).parent.absolute().as_posix()}/queryIntent.prompty" # pass absolute file path to prompty
        intentPrompty = Prompty.load(path_to_prompty, model={
            'configuration': model_config,
            'parameters': { 
                'max_tokens': 256,
            }
        })
        searchQuery = intentPrompty(query=chat_input, chat_history=chat_history)

    # retrieve relevant documents and context given chat_history and current user query (chat_input)
    print(os.environ["AZURE_OPENAI_API_KEY"])
    documents = get_documents(searchQuery, 3)

    # send query + document context to chat completion for a response
    path_to_prompty = f"{Path(__file__).parent.absolute().as_posix()}/chat.prompty"
    chatPrompty = Prompty.load(path_to_prompty, model={
        'configuration': model_config,
        'parameters': { 
            'max_tokens': 256,
            'temperature': 0.2,
            'stream': False # always stream responses, consumers/clients should handle streamed response
        }
    })
    result = chatPrompty(
        chat_history=chat_history,
        chat_input=chat_input,
        documents=documents
    )

    return dict(reply=result, context=documents)

@trace
def get_documents(search_query: str, num_docs=3):

    index_name = os.environ["AZUREAI_SEARCH_INDEX_NAME"]

    #  retrieve documents relevant to the user's query from Azure AI Search index
    search_client = SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["AZURE_SEARCH_KEY"]),
        index_name=index_name)

    aoai_client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"]
    )

    # generate a vector embedding of the user's question
    embedding = aoai_client.embeddings.create(input=search_query,
                                            model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"])
    embedding_to_query = embedding.data[0].embedding

    context = ""
    # use the vector embedding to do a vector search on the index
    vector_query = VectorizedQuery(vector=embedding_to_query, k_nearest_neighbors=num_docs, fields="contentVector")
    results = trace(search_client.search)(
        search_text="",
        vector_queries=[vector_query],
        select=["id", "content"])

    for result in results:
        context += f"\n>>> From: {result['id']}\n{result['content']}"

    return context
