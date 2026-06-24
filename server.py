import json
import os
from aiohttp import web

games = {}
SERVE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_game():
    return {"board": [""]*9, "players": {}, "current": "X", "active": True, "moves": 0}

async def index(request):
    return web.FileResponse(os.path.join(SERVE_DIR, "tic-tac-toe.html"))

async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    game_id = None
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                t = data["type"]
                if t == "join":
                    gid = data.get("game", "default")
                    if gid not in games:
                        games[gid] = create_game()
                    g = games[gid]
                    if len(g["players"]) >= 2:
                        await ws.send_json({"type": "error", "msg": "Game is full"})
                        continue
                    mark = "X" if "X" not in g["players"] else "O"
                    g["players"][mark] = ws
                    game_id = gid
                    await ws.send_json({"type": "joined", "mark": mark, "board": g["board"]})
                    if len(g["players"]) == 2:
                        await g["players"]["X"].send_json({"type": "start", "turn": True})
                        await g["players"]["O"].send_json({"type": "start", "turn": False})
                elif t == "move":
                    g = games.get(game_id)
                    if not g or not g["active"]:
                        continue
                    cell, mark = data["cell"], data["mark"]
                    if mark != g["current"] or g["board"][cell] != "":
                        await ws.send_json({"type": "error", "msg": "Invalid move"})
                        continue
                    g["board"][cell] = mark
                    g["moves"] += 1
                    wins = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]]
                    winner, line = None, None
                    for c in wins:
                        if all(g["board"][i] == mark for i in c):
                            winner, line = mark, c
                            break
                    if winner:
                        g["active"] = False
                        for p in g["players"].values():
                            await p.send_json({"type": "result", "winner": winner, "board": g["board"], "line": line})
                    elif g["moves"] == 9:
                        g["active"] = False
                        for p in g["players"].values():
                            await p.send_json({"type": "result", "winner": "draw", "board": g["board"]})
                    else:
                        g["current"] = "O" if g["current"] == "X" else "X"
                        for m, p in g["players"].items():
                            await p.send_json({"type": "update", "board": g["board"], "turn": g["current"] == m})
                elif t == "restart":
                    g = games.get(game_id)
                    if g:
                        games[game_id] = create_game()
                        games[game_id]["players"] = g["players"]
                        for mark, p in g["players"].items():
                            await p.send_json({"type": "joined", "mark": mark, "board": games[game_id]["board"]})
                        if len(games[game_id]["players"]) == 2:
                            await g["players"]["X"].send_json({"type": "start", "turn": True})
                            await g["players"]["O"].send_json({"type": "start", "turn": False})
            elif msg.type == web.WSMsgType.ERROR:
                break
    finally:
        if game_id and game_id in games:
            g = games[game_id]
            g["active"] = False
            for mark, p in list(g["players"].items()):
                if p == ws:
                    del g["players"][mark]
                else:
                    try:
                        await p.send_json({"type": "opponent_left"})
                    except:
                        pass
            if not g["players"]:
                del games[game_id]
    return ws

app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/tic-tac-toe.html", index)
app.router.add_get("/ws", ws_handler)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Server on port {port}")
    web.run_app(app, host="0.0.0.0", port=port)
