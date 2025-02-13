import requests

# API endpoint
url = "http://localhost:5000/api/find_best_fit_candidates"

# File to upload
files = {'file': open("D:\\AIcruiter-main\\uploads\\Sample_Job_Description.docx", 'rb')}  # Replace with the actual file path

# Form data
data = {
    "job_level": "Senior",
    "job_description": ""  # Optional, as file content may replace this
}

# Make the POST request
response = requests.post(url, data=data, files=files)

# Print the response
print(response.status_code)
print(response.json())
