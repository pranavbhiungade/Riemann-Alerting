import requests

url = input("Enter the URL : ")
count = int(input("How many times do you want to request this URL? "))

full_url = "http://" + url

for i in range(count):
    try:
        response = requests.get(full_url)
        if response.status_code == 200:
            print(f"[{i+1}] [{full_url}] → Status Code: 200 OK")
        else:
            print(f"[{i+1}] [{full_url}] → Status Code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"[{i+1}] [{full_url}] → Request Failed: {str(e)}")

