import requests

URL = "http://127.0.0.1:5500/prompt"

prompt = input("Enter your prompt: ")

response = requests.post(URL, json={"prompt": prompt})

if response.status_code == 200:
    data = response.json()
    print(f"\nResponse:\n{data['response']}")
else:
    print(f"\nError: {response.json()}")
