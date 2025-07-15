import uvicorn
import os
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket
from dotenv import load_dotenv

import sys

# Adicionar o diretório src ao PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from langchain_openai_voice import OpenAIVoiceReactAgent


from server.utils import websocket_stream
from server.prompt import INSTRUCTIONS
from server.tools import TOOLS

# Recarregar as variáveis de ambiente para garantir que estamos usando a API key mais recente
load_dotenv(override=True)


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    browser_receive_stream = websocket_stream(websocket)

    # Obter a API key diretamente do ambiente
    api_key = os.environ.get("OPENAI_API_KEY")
    print(f"Usando API key: {api_key[:10]}...{api_key[-5:]}")
    
    agent = OpenAIVoiceReactAgent(
        model="gpt-4o-realtime-preview-2024-10-01",
        tools=TOOLS,
        instructions=INSTRUCTIONS,
        openai_api_key=api_key,  # Passar explicitamente a API key
    )

    await agent.aconnect(browser_receive_stream, websocket.send_text)


async def homepage(request):
    with open("src/server/static/index.html") as f:
        html = f.read()
        return HTMLResponse(html)


# catchall route to load files from src/server/static


routes = [Route("/", homepage), WebSocketRoute("/ws", websocket_endpoint)]

app = Starlette(debug=True, routes=routes)

app.mount("/", StaticFiles(directory="src/server/static"), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
