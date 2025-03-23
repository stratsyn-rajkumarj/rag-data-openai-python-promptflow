from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
import os
load_dotenv()

project_connection_string = "eastus2.api.azureml.ms;12631ede-6470-4184-a488-02c65b69628f;walled-garden-gen-ai-s;r72272-josephrajkumar"

project = AIProjectClient.from_connection_string(
    conn_str=project_connection_string, credential=DefaultAzureCredential()
)

chat = project.inference.get_chat_completions_client()
response = chat.complete(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": "You are an AI assistant that speaks like a techno punk rocker from 2350. Be cool but not too cool. Ya dig?",
        },
        {"role": "user", "content": "Hey, can you help me with my taxes? I'm a freelancer."},
    ],
)

print(response.choices[0].message.content)