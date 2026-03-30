import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fintech import request

while True:
    try:
        user_prompt = input("🙍🏻 ")
    except (EOFError, KeyboardInterrupt):
        print("\nEncerrando a conversa.")
        break

    if user_prompt.lower() in ("sair", "end", "fim","tchau","bye"):
        print("Encerrando a conversa.")
        break

    try:
        response = request(user_prompt)
        print(response['messages'][1].content)
    except Exception as e:
        print(str(e))