"""Shared DeepSeek transport. Caller owns state, budgets and disclosure scope."""
import json
import os
from urllib.request import Request, urlopen

def chat(payload, timeout=40):
    req = Request('https://api.deepseek.com/chat/completions', data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + os.environ['DEEPSEEK_API_KEY'], 'Content-Type': 'application/json'})
    with urlopen(req, timeout=timeout) as response:
        return json.load(response)
