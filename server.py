import socket
import threading
import json
import random
import time
import sys

# --- 伺服器配置 ---
HOST = '0.0.0.0'
PORT = 65432
MAX_PLAYERS = 2       # 測試時設為 2，正式遊玩可依需求增加
GAME_DURATION = 60    # 遊戲時間 (秒)

# --- 遊戲狀態常數 ---
STATE_WAITING = 0     # 等待人齊
STATE_READY_CHECK = 1 # 等待 /ready
STATE_VOTING = 2      # 投票模式 (Auto/Manual)
STATE_PLAYING = 3     # 遊戲進行中
STATE_FINISHED = 4    # 結算

# --- 全域變數 ---
clients = {}          # {socket: username}
ready_players = set() # 儲存已 /ready 的 username
votes = {}            # {username: 'auto' or 'manual'}
scores = {}           # {username: total_points}
prize_pool = []       # 儲存剩餘的獎品物件
game_state = STATE_WAITING
game_mode = None      
stop_game_event = threading.Event()

# --- 核心邏輯 ---

def broadcast(message):
    """廣播訊息給所有人"""
    json_message = json.dumps(message) + '\n'
    for client_socket in list(clients.keys()):
        try:
            client_socket.sendall(json_message.encode('utf-8'))
        except:
            pass 

def init_prize_pool(num_players):
    """初始化有限的獎品池"""
    global prize_pool
    prize_pool = []
    
    # --- 🔥 修改點 1: 增加獎品數量係數 (改成 * 100) ---
    total_items = num_players * 100
    
    # --- 🔥 修改點 2: 簡化獎品名稱 ---
    # 100分 (10%)
    for _ in range(int(total_items * 0.1)): 
        prize_pool.append({"score": 100, "name": "(100分)"})
    
    # 50分 (20%)
    for _ in range(int(total_items * 0.2)): 
        prize_pool.append({"score": 50,  "name": "(50分)"})
    
    # 10分 (40%)
    for _ in range(int(total_items * 0.4)): 
        prize_pool.append({"score": 10,  "name": "(10分)"})
    
    # 0分 (30%)
    for _ in range(int(total_items * 0.3)): 
        prize_pool.append({"score": 0,   "name": "銘謝惠顧 (0分)"})
    
    # 打亂順序
    random.shuffle(prize_pool)
    print(f"[系統] 獎品池已建立，共有 {len(prize_pool)} 個獎項。")

def draw_one_prize(username):
    """從池中抽出一個獎品 (不重複)"""
    global prize_pool
    
    if not prize_pool:
        return None # 獎池空了
    
    prize = prize_pool.pop() # 取出並移除
    
    # 伺服器端顯示抽獎結果
    print(f"[遊戲中] {username} 抽到了: {prize['name']}")
    
    return prize

def reset_game():
    global game_state, ready_players, scores, votes, stop_game_event
    game_state = STATE_WAITING
    ready_players.clear()
    votes.clear()
    scores = {name: 0 for name in clients.values()}
    stop_game_event.clear()
    
    broadcast({"status": "info", "message": "🔄 遊戲已重置！等待所有玩家輸入 /ready 重新開始。"})
    check_room_status()

def game_timer_thread():
    """遊戲主迴圈"""
    global game_state
    remaining_time = GAME_DURATION
    
    # 初始化獎池
    init_prize_pool(len(clients))

    start_msg = f"🏁 遊戲開始！模式：{game_mode} | 限時 {GAME_DURATION} 秒 | 獎品數量：{len(prize_pool)}"
    broadcast({"status": "info", "message": start_msg})
    print(f"[系統] {start_msg}")

    while remaining_time > 0 and not stop_game_event.is_set():
        
        # 若獎池空了，提早結束
        if not prize_pool:
            broadcast({"status": "info", "message": "😲 獎品已被搶購一空！遊戲提早結束！"})
            break

        if game_mode == 'auto':
            round_results = []
            # 自動幫每個人抽
            for sock, name in clients.items():
                if not prize_pool: break # 抽到一半沒了
                
                prize = draw_one_prize(name)
                if prize:
                    scores[name] += prize['score']
                    round_results.append(f"{name}:{prize['name']}")
            
            if round_results:
                broadcast({"status": "auto_update", "message": f"⏱ {remaining_time}s | " + " | ".join(round_results)})
        
        else:
            # 手動模式只報時
            if remaining_time % 10 == 0 or remaining_time <= 5:
                broadcast({"status": "info", "message": f"⏳ 剩餘時間：{remaining_time} 秒 (剩餘獎品: {len(prize_pool)}個)"})

        time.sleep(1)
        remaining_time -= 1

    game_state = STATE_FINISHED
    print("[系統] 遊戲時間結束，進行結算。")
    show_ranking()

def show_ranking():
    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    rank_msg = "\n🏆 === 最終排行榜 === 🏆\n"
    rank = 1
    for name, score in sorted_scores:
        icon = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"No.{rank}"
        rank_msg += f"{icon} {name}: {score} 分\n"
        rank += 1
    rank_msg += "=======================\n👉 輸入 /replay 再玩一次，或 /quit 離開。"
    
    broadcast({"status": "info", "message": rank_msg})
    print(rank_msg)

def process_voting_result():
    """計算投票結果並開始遊戲"""
    global game_mode, game_state
    
    auto_votes = list(votes.values()).count('auto')
    manual_votes = list(votes.values()).count('manual')
    
    msg = f"🗳️ 投票結束！ Auto: {auto_votes} 票 vs Manual: {manual_votes} 票。"
    print(f"[系統] {msg}")
    
    if auto_votes > manual_votes:
        game_mode = 'auto'
        msg += " (多數決：自動模式)"
    elif manual_votes > auto_votes:
        game_mode = 'manual'
        msg += " (多數決：手動模式)"
    else:
        # 平手隨機二選一
        game_mode = random.choice(['auto', 'manual'])
        msg += f" (⚖️ 平手！系統隨機骰出：**{game_mode}** 模式)"
    
    broadcast({"status": "info", "message": msg})
    
    # 進入遊戲狀態
    game_state = STATE_PLAYING
    threading.Thread(target=game_timer_thread).start()

def check_room_status():
    global game_state
    current_count = len(clients)
    
    if game_state == STATE_WAITING:
        if current_count >= MAX_PLAYERS:
            game_state = STATE_READY_CHECK
            broadcast({"status": "info", "message": f"👥 人員到齊！請輸入 **/ready** 準備。"})
        else:
            broadcast({"status": "info", "message": f"等待玩家... ({current_count}/{MAX_PLAYERS})"})

    elif game_state == STATE_READY_CHECK:
        all_ready = (len(ready_players) >= len(clients)) and (len(clients) >= MAX_PLAYERS)
        if all_ready:
            game_state = STATE_VOTING
            broadcast({"status": "info", "message": "✅ 全員準備就緒！\n🗳️ 請投票選擇模式：\n輸入 **/auto** (自動抽)\n輸入 **/manual** (手動搶)"})

def handle_client(conn, addr):
    global game_state, game_mode
    print(f"[連線] {addr} 已連線")
    
    try:
        conn.sendall((json.dumps({"status": "welcome", "message": "歡迎！請輸入暱稱註冊。"})+'\n').encode('utf-8'))
    except:
        conn.close()
        return

    username = None
    try:
        while True:
            data = conn.recv(1024).decode('utf-8')
            if not data: break
            
            for line in data.splitlines():
                if not line: continue
                try:
                    msg_obj = json.loads(line)
                    action = msg_obj.get("action")

                    # 1. 註冊
                    if action == "register" and not username:
                        requested_name = msg_obj.get("name", "Player")
                        if requested_name in clients.values(): requested_name += f"_{random.randint(1,99)}"
                        username = requested_name
                        clients[conn] = username
                        scores[username] = 0
                        print(f"[加入] {username} 加入遊戲")
                        broadcast({"status": "info", "message": f"👋 {username} 進場！"})
                        check_room_status()

                    # 2. 準備 /ready
                    elif action == "ready":
                        if game_state == STATE_READY_CHECK:
                            ready_players.add(username)
                            broadcast({"status": "info", "message": f"✅ {username} 準備好了 ({len(ready_players)}/{len(clients)})"})
                            check_room_status()

                    # 3. 投票 /auto 或 /manual
                    elif action == "vote":
                        if game_state == STATE_VOTING:
                            if username in votes:
                                conn.sendall((json.dumps({"status":"info", "message":"您已經投過票了。"})+'\n').encode('utf-8'))
                                continue
                            vote_val = msg_obj.get("mode")
                            votes[username] = vote_val
                            broadcast({"status": "info", "message": f"🗳️ {username} 投給了 {vote_val} ({len(votes)}/{len(clients)})"})
                            
                            if len(votes) >= len(clients):
                                process_voting_result()
                        else:
                            conn.sendall((json.dumps({"status":"error", "message":"現在不是投票時間"})+'\n').encode('utf-8'))

                    # 4. 抽獎 /draw
                    elif action == "trigger_draw":
                        if game_state == STATE_PLAYING and game_mode == 'manual':
                            prize = draw_one_prize(username)
                            if prize:
                                scores[username] += prize['score']
                                conn.sendall((json.dumps({"status":"draw_result", "prize": prize['name']})+'\n').encode('utf-8'))
                            else:
                                conn.sendall((json.dumps({"status":"error", "message":"手慢了！獎品已被搶光！"})+'\n').encode('utf-8'))
                        elif game_mode == 'auto':
                            conn.sendall((json.dumps({"status":"error", "message":"自動模式中，請勿手動操作"})+'\n').encode('utf-8'))

                    # 5. 重玩
                    elif action == "replay":
                        if game_state == STATE_FINISHED:
                            reset_game()

                except Exception as e:
                    print(f"Error: {e}")

    finally:
        if conn in clients:
            del clients[conn]
            if username in votes: del votes[username]
            if username in ready_players: ready_players.remove(username)
            broadcast({"status": "info", "message": f"🏃 {username} 離開了"})
            print(f"[離開] {username} 離線")
        conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((HOST, PORT))
        server.listen()
        print(f"Server 啟動於 {HOST}:{PORT}, 需要 {MAX_PLAYERS} 人開始...")
        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn, addr)).start()
    except Exception as e:
        print(f"Server 啟動失敗: {e}")
    finally:
        server.close()

if __name__ == '__main__':
    start_server()