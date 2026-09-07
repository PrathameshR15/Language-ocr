import requests

url = 'http://localhost:8000/api/v1/upload'
files = {'files': open('test_arial_rupee.pdf', 'rb')}
try:
    response = requests.post(url, files=files)
    print("Status Code:", response.status_code)
    print("Response Text:", response.text)
except Exception as e:
    print("Request failed:", e)
