import json
import pymongo
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables from the config/.env file
load_dotenv()

# Get MongoDB URI from environment variables
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

# Connect to MongoDB using the URI from environment variables
client = MongoClient(mongo_uri)

# Access your database and collection
db = client['resume_database']
collection = db['resumes']

# Function to load resume data from JSON file into MongoDB
def load_resume_data(json_file):
    # Read JSON file from environment variable or use an alternative cloud storage location
    with open(json_file, 'r') as f:
        resume_data = json.load(f)
        for filename, candidate_data in resume_data.items():
            candidate_name = candidate_data.get('Name', filename)  # Ensure 'Name' is from parsed data
            if candidate_name:
                candidate_data['Name'] = candidate_name
            else:
                candidate_data['Name'] = filename  # Fall back to filename if 'Name' is missing

            # Insert the resume data into MongoDB
            collection.insert_one(candidate_data)
    print("Resume data loaded into MongoDB successfully.")

# Function to read a candidate's resume from MongoDB by name or email
def read_resume(name=None, email=None, fields=None):
    query = {}
    if name:
        query['Name'] = name
    if email:
        query['Email Address'] = email

    # Find the matching resume
    result = collection.find_one(query)
    if result:
        # Convert ObjectId to string for JSON serialization
        result['_id'] = str(result['_id'])

        # Return only the specified fields or the whole document
        if fields and fields != 'all':
            output = {}
            for field in fields:
                if "." in field:  # Check for nested fields like 'Experience in Years for Each Relevant Skill.Python'
                    top_field, sub_field = field.split(".", 1)
                    output[field] = result.get(top_field, {}).get(sub_field, 'data not found')
                else:
                    output[field] = result.get(field, 'data not found')
            return output
        
        return result
    else:
        return None


# Function to update a candidate's resume in MongoDB by name or email
def update_resume(name=None, email=None, updated_data=None):
    if not updated_data:
        return "No data provided to update."

    query = {}
    if name:
        query['Name'] = name
    if email:
        query['Email Address'] = email

    # Update the document with the new data
    update_result = collection.update_one(query, {"$set": updated_data})

    if update_result.matched_count:
        return f"Resume updated for {name or email}."
    else:
        return f"No resume found to update for {name or email}."

# Function to delete a candidate's resume from MongoDB by name or email
def delete_resume(name=None, email=None):
    query = {}
    if name:
        query['Name'] = name
    if email:
        query['Email Address'] = email

    # Delete the document
    delete_result = collection.delete_one(query)

    if delete_result.deleted_count:
        return f"Resume deleted for {name or email}."
    else:
        return f"No resume found to delete for {name or email}."

# Function to insert a new candidate resume into MongoDB
def create_resume(new_resume_data):
    # Validate that required fields are present
    if not new_resume_data.get('Name') or not new_resume_data.get('Email Address'):
        return "Resume must have at least 'Name' and 'Email Address'."

    try:
        # Insert the new resume data into the collection
        insert_result = collection.insert_one(new_resume_data)
        if insert_result.inserted_id:
            return f"Resume created for {new_resume_data['Name']}."
        else:
            return "Failed to insert the resume."
    except Exception as e:
        return f"An error occurred while inserting the resume: {str(e)}"

# Main script execution
if __name__ == "__main__":
    # Load the resume data from extracted_resume_data.json (ensure the file is located in a cloud-compatible location)
    json_file_path = os.getenv("EXTRACTED_RESUME_FILE_PATH", "path/to/extracted_resume_data_new.json")
    load_resume_data(json_file_path)

    # Operations:

    # 1. Read a resume by name
    print(read_resume(name="VEERA RAGHAVAN CHANDRAN", fields=['Name', 'Email Address']))

    # 2. Read a resume by email
    print(read_resume(email="cvraghavan75@gmail.com", fields=['Primary Skills', 'Current Company Name']))

    # 3. Update a resume with various fields
    updated_data = {
        "Primary Skills": "Python, Machine Learning, Deep Learning",
        "Current Location": "New York, NY",
        "Total Experience": "5 years",
        "Email Address": "newemail@example.com"  # Example of updating email
    }
    print(update_resume(name="SABARI", updated_data=updated_data))

    # 4. Delete a resume by name
    print(delete_resume(name="Praveen charles.M"))

    # 5. Delete a resume by email
    print(delete_resume(email="pree@gmail.com"))  # Replace with an actual email to test

    # 6. Insert a new resume
    new_resume = {
        "Name": "Roopa S",
        "Email Address": "roopa@gmail.com",
        "Primary Skills": "Python, AI/ML",
        "Total Experience": "2 years",
        "Location": "Los Angeles, CA"
    }
    print(create_resume(new_resume))
