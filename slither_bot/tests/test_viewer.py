"""Testes automatizados para o Servidor Web e WebSocket do Espectador."""

import json
from fastapi.testclient import TestClient

from slither_ai.viewer.server import create_spectator_app


def test_spectator_http_routes():
    """Valida se as rotas estáticas do frontend (HTML, CSS, JS) respondem 200 OK."""
    app = create_spectator_app(model_path=None)
    client = TestClient(app)

    # 1. Rota raiz (index.html)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "gameCanvas" in resp.text
    assert "Slither AI" in resp.text

    # 2. CSS do viewer
    resp = client.get("/viewer.css")
    assert resp.status_code == 200
    assert "gameCanvas" in resp.text

    # 3. JavaScript do viewer
    resp = client.get("/viewer.js")
    assert resp.status_code == 200
    assert "WebSocket" in resp.text


def test_spectator_websocket_stream():
    """Valida a conexão WebSocket e o protocolo de telemetria da arena."""
    app = create_spectator_app(model_path=None)
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        # Recebe o primeiro pacote de dados da simulação
        raw_data = ws.receive_text()
        data = json.loads(raw_data)

        # Valida campos vitais da telemetria
        assert "player_snake" in data
        assert "lidar_readings" in data
        assert "other_snakes" in data
        assert "foods" in data
        assert "arena_radius" in data
        assert "active_brain" in data
        assert data["active_brain"] == "native"
        assert "leaderboard" in data
        assert len(data["leaderboard"]) >= 1
        assert "minimap_dots" in data

        # Valida sensores do LIDAR (16 raios)
        assert len(data["lidar_readings"]) == 16
        for reading in data["lidar_readings"]:
            assert 0.0 <= reading <= 1.0

        # Valida a cobra principal
        player = data["player_snake"]
        assert "x" in player and "y" in player
        assert "angle" in player
        assert "score" in player
        assert "segments" in player
        assert len(player["segments"]) >= 1

        # Testa troca de cérebro dinâmico
        ws.send_text(json.dumps({"cmd": "set_brain", "brain": "manual"}))
        for _ in range(5):
            raw_brain_data = ws.receive_text()
            brain_data = json.loads(raw_brain_data)
            if brain_data.get("active_brain") == "manual":
                break
        assert brain_data["active_brain"] == "manual"

        # Testa envio de comando de reset
        ws.send_text(json.dumps({"cmd": "reset"}))
        for _ in range(5):
            raw_reset_data = ws.receive_text()
            reset_data = json.loads(raw_reset_data)
            if "player_snake" in reset_data:
                break
        assert "player_snake" in reset_data
