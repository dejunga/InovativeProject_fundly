import requests

url = "https://data.gov.hr/ckan/api/3/action/package_search"
params = {"rows": 10, "sort": "metadata_modified desc"}
r = requests.get(url, params=params)
print(r.json())