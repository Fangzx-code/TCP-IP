import socket
import threading
import json
import sys
import time

HOST = '127.0.0.1' 
PORT = 65432
CLIENT_SOCKET = None
MY_USERNAME = None

def receive_messages(sock):
    """接收 Server 訊息"""
    while True:
        try:
            data = sock.recv(4096).decode('utf-8')
            if not data:
                print("\n[系統] 伺服器已斷開。")
                break
            
            for line in data.splitlines():
                if not line: continue
                try:
                    msg = json.loads(line)
                    status = msg.get("status")
                    content = msg.get("message", "")

                    if status == "welcome":
                        print(f"\n✨ {content}")
                        send_action(sock, "register", {"name": MY_USERNAME})
                    elif status == "info":
                        print(f"\n📢 {content}")
                    elif status == "error":
                        print(f"\n❌ {content}")
                    elif status == "draw_result":
                        print(f"🎁 恭喜！抽到了: {msg['prize']}")
                    elif status == "auto_update":
                        print(f"⚡ {content}")

                    sys.stdout.write('> ')
                    sys.stdout.flush()
                except: pass
        except: break
    # 當伺服器斷線，強制結束程式
    print("\n按 Enter 鍵離開...")
    sys.exit()

def send_action(sock, action, data={}):
    payload = {"action": action}
    payload.update(data)
    try:
        sock.sendall((json.dumps(payload) + '\n').encode('utf-8'))
    except: pass

# --- 🔥 新增：退出時的顯示函式 ---
def show_exit_message():
    print("\n" + "="*40)
    print(f"👋 再見，{MY_USERNAME}！")
    print("感謝您參與這次的「多人連線搶分遊戲」。")
    print("希望您玩得愉快！祝您期末專題順利！💯")
    print("="*40 + "\n")
    time.sleep(1) # 稍微停頓一下讓使用者看完

if __name__ == '__main__':
    MY_USERNAME = input("請輸入暱稱: ")
    CLIENT_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        CLIENT_SOCKET.connect((HOST, PORT))
    except:
        print("無法連線至 Server，請確認 Server 是否已啟動。"); sys.exit()

    threading.Thread(target=receive_messages, args=(CLIENT_SOCKET,), daemon=True).start()

    print("\n指令: /ready, /auto, /manual, /draw, /replay, /quit, /help")

    while True:
        try:
            cmd = input('> ').lower().strip()
            
            if cmd == '/quit':
                # --- 在這裡呼叫退出顯示 ---
                show_exit_message()
                break
            
            elif cmd == '/help':
                print("\n=== 📜 指令清單 ===")
                print("/ready   - 準備 (人齊後用)")
                print("/auto    - 投票自動模式")
                print("/manual  - 投票手動模式")
                print("/draw    - 抽獎 (手動模式用)")
                print("/replay  - 再玩一次")
                print("/quit    - 顯示說明並離開遊戲")
                print("===================")
            
            elif cmd == '/ready': send_action(CLIENT_SOCKET, "ready")
            elif cmd == '/auto': send_action(CLIENT_SOCKET, "vote", {"mode": "auto"})
            elif cmd == '/manual': send_action(CLIENT_SOCKET, "vote", {"mode": "manual"})
            elif cmd == '/draw': send_action(CLIENT_SOCKET, "trigger_draw")
            elif cmd == '/replay': send_action(CLIENT_SOCKET, "replay")
        except KeyboardInterrupt:
            # 處理 Ctrl+C 強制結束的情況
            show_exit_message()
            break
        except: break

    if CLIENT_SOCKET: CLIENT_SOCKET.close()