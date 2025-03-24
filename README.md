# Installation

    cd docker
    docker compose up --build

# Frontend

    cd frontend
    npm install
    npm run dev

# Backend

Set env vars :
- JUPYER_KERNEL_HTTP_GATEWAY=http://localhost:8888
- JUPYER_KERNEL_WS_GATEWAY=ws://localhost:8888;
- OPENAI_API_KEY=<api_key>

Run backend :

    cd backend
    pip install -r ./requirements.txt
    python main.py