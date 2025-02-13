from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import extractor
import json
import pymongo
from pymongo import MongoClient
import os
import google.generativeai as genai
from dotenv import load_dotenv
from resume_parsing_CRUD import read_resume, update_resume, delete_resume, create_resume
import datetime
import logging
import concurrent.futures
import markdown  # Import the markdown library
from PyPDF2 import PdfReader  # For PDF parsing
from docx import Document  # For Word file parsing

# Load environment variables
load_dotenv(dotenv_path=os.getenv("ENV_PATH", "./config/.env"))

# Configure Generative AI
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Logging setup
logging.basicConfig(level=logging.DEBUG)

# Flask app initialization
app = Flask(__name__)
CORS(app)

# Create a temporary directory dynamically using tempfile
# UPLOAD_FOLDER = tempfile.mkdtemp(prefix="uploads_", dir=os.getcwd())  # Save in project directory
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# print(f"Temporary upload directory: {UPLOAD_FOLDER}")

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(os.getcwd(), 'uploads'))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"Files will be uploaded to: {UPLOAD_FOLDER}")  # For debugging

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DATABASE_NAME", "resumes")
COLLECTION_NAME_RESUME_DATABASE = os.getenv("COLLECTION_NAME_RESUME_DATABASE", "resume_database")
COLLECTION_NAME_EVALUATION_REPORTS = os.getenv("COLLECTION_NAME_EVALUATION_REPORTS", "evaluation_reports")

# Initialize MongoDB client and handle potential connection errors

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME_RESUME_DATABASE]
    evaluation_reports_collection = db[COLLECTION_NAME_EVALUATION_REPORTS]
    logging.info(f"Connected to MongoDB database: {DB_NAME}")
except Exception as e:
    logging.critical(f"Error connecting to MongoDB: {e}")
    raise

# # Clear the collection when the app starts to ensure a clean session
#collection.delete_many({})

# Ensure that the value is fetched as a string and converted into an integer
max_threads_str = os.getenv("DEFAULT_MAX_THREADS", "4")
try:
    DEFAULT_MAX_THREADS = int(max_threads_str)
except ValueError:
    DEFAULT_MAX_THREADS = 4  # Fallback to default if conversion fails

# Routes
# Section 1: Resume Parsing  
@app.route('/')  
def index():  
    return render_template('index.html')  

#========================================PARSE RESUMES FUNCTION===============================================================

@app.route('/parse_resume', methods=['POST'])
def parse_resume():
    try:
        logging.debug("Received a request to parse resumes")
        store_in_mongodb = request.form.get('storeInMongoDB', 'no').lower() == 'yes'

        # Retrieve and validate max_threads
        max_threads = int(request.form.get('max_threads', DEFAULT_MAX_THREADS))
        if not (1 <= max_threads <= 10):
            return jsonify({'error': 'Invalid max_threads value. Must be between 1 and 10.'}), 400

        logging.debug(f"Using {max_threads} threads for processing")

        # Handle folder-based parsing with ThreadPoolExecutor
        folder_path = request.form.get('folder_path')
        if folder_path:
            logging.debug(f"Parsing resumes from folder: {folder_path}")

            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                logging.error(f"Invalid folder path: {folder_path}")
                return jsonify({'error': f'Invalid folder path: {folder_path}'}), 400

            files = [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                     if os.path.isfile(os.path.join(folder_path, f)) and f.endswith(('.pdf', '.docx'))]
            
            results = {}
            logging.info(f"Found {len(files)} valid files to process.")

            # Function to process a single file
            def process_file(file_path):
                try:
                    extracted_info_json = extractor.extract_resume_data(file_path, store_in_mongodb=store_in_mongodb)
                    return file_path, json.loads(extracted_info_json)
                except Exception as e:
                    logging.error(f"Error processing {file_path}: {str(e)}", exc_info=True)
                    return file_path, {'error': str(e)}

            # Process files in parallel using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
                future_to_file = {executor.submit(process_file, file_path): file_path for file_path in files}
                for future in concurrent.futures.as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        file_path, result = future.result()
                        results[os.path.basename(file_path)] = result
                    except Exception as e:
                        logging.error(f"Error in thread for file {file_path}: {str(e)}", exc_info=True)
                        results[os.path.basename(file_path)] = {'error': str(e)}

            return jsonify(results)

        # Handle single file upload
        if 'file' in request.files:
            file = request.files['file']
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            logging.debug(f"Single file uploaded: {file.filename}, saved at {file_path}")

            extracted_info_json = extractor.extract_resume_data(file_path, store_in_mongodb=store_in_mongodb)
            logging.debug(f"Extracted info: {extracted_info_json}")
        
            return jsonify(json.loads(extracted_info_json))

        # Handle multiple file upload
        elif 'files[]' in request.files:
            logging.debug("Multiple files uploaded")
            files = request.files.getlist('files[]')
            results = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
                future_to_file = {executor.submit(process_uploaded_file, file): file for file in files}
                for future in concurrent.futures.as_completed(future_to_file):
                    file = future_to_file[future]
                    try:
                        file_name, result = future.result()
                        results[file_name] = result
                    except Exception as e:
                        logging.error(f"Error processing {file.filename}: {e}")
                        results[file.filename] = {'error': str(e)}
            return jsonify(results)

        return jsonify({'error': 'No file or folder_path provided'}), 400

    except Exception as e:
        logging.critical(f"Unexpected error: {e}")
        return jsonify({'error': 'Unexpected server error occurred'}), 500


# Helper function for processing uploaded files
def process_uploaded_file(file):
    try:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        logging.debug(f"Saving file to: {file_path}")  # Add a log to print the exact path
        file.save(file_path)
        extracted_info_json = extractor.extract_resume_data(file_path, store_in_mongodb=True)
        return file.filename, json.loads(extracted_info_json)
    except Exception as e:
        return file.filename, {'error': str(e)}
    
    
#==============================================SEARCH BY SKILLS================================================================
    
# Function to search candidates by skills
def search_candidates_by_skills(skills):
    """
    Searches candidates in MongoDB who have the specified skills.
    :param skills: List of skills to search for.
    :return: List of matching candidates.
    """
    try:
        # Normalize skills input to lowercase
        normalized_skills = [skill.lower() for skill in skills]

        # MongoDB query to match skills in Primary or Secondary Skills
        query = {
            "$or": [
                {"Primary Skills": {"$regex": "|".join(normalized_skills), "$options": "i"}},
                {"Secondary Skills": {"$regex": "|".join(normalized_skills), "$options": "i"}}
            ]
        }

        # Fetch matching candidates
        candidates = list(collection.find(query))

        # Convert ObjectId to string for JSON serialization
        for candidate in candidates:
            candidate["_id"] = str(candidate["_id"])

        return candidates
    except Exception as e:
        logging.error(f"Error searching candidates by skills: {e}")
        return None

# Flask route for skill-based candidate search
@app.route('/search_by_skills', methods=['POST'])
def search_by_skills():
    """
    API endpoint to search candidates by skills.
    Request JSON format: {"skills": ["Python", "Django"]}
    """
    try:
        # Parse request data
        data = request.get_json()
        skills = [skill.lower() for skill in data.get('skills', [])]

        if not skills or not isinstance(skills, list):
            return jsonify({"error": "Skills field is required and must be a list."}), 400

        # Perform search
        candidates = search_candidates_by_skills(skills)

        if candidates is None:
            return jsonify({"error": "An error occurred while searching for candidates."}), 500
        
        if not candidates:
            return jsonify({"message": "No candidates found matching the provided skills."}), 404

        return jsonify({"status": "success", "candidates": candidates}), 200

    except Exception as e:
        logging.error(f"Unexpected error in /search_by_skills: {e}")
        return jsonify({"error": "Unexpected server error occurred."}), 500


#=================================================== CRUD Operations ==================================================================
# Field Mapping for Case Sensitivity
field_mapping = {
    'name': 'Name',
    'email': 'Email Address',
    'contact_number': 'Contact Number',
    'education': 'Education',
    'current_company': 'Current Company Name',
    'current_location': 'Current Location',
    'primary_skills': 'Primary Skills',
    'secondary_skills': 'Secondary Skills',
    'experience_in_skills': 'Experience in Skills',
}

#============================================= 1. READ CANDIDATE API =====================================================================

@app.route('/read_candidate', methods=['POST'])
def read_candidate():
    data = request.get_json()
    print(f"Request Data: {data}")  # Debugging line

    # Validate input
    name_email = data.get('name_email')
    fields = data.get('fields', 'all')  # Default to 'all' if fields not provided

    if not name_email:
        return jsonify({'error': 'The "name_email" field is required'}), 400

    # Determine whether to query by email or name
    query = {'Email Address': name_email} if '@' in name_email else {'Name': name_email}

    # Fetch candidate
    result = collection.find_one(query)
    if not result:
        return jsonify({'status': 'not_found', 'message': 'No candidate found with the provided details'}), 404

    # Filter fields if requested
    if fields and fields != 'all':
        field_mapping = {
            'name': 'Name',
            'email': 'Email Address',
            'contact_number': 'Contact Number',
            'education': 'Education',
            'current_company': 'Current Company Name',
            'current_location': 'Current Location',
            'primary_skills': 'Primary Skills',
            'secondary_skills': 'Secondary Skills',
            'experience_in_skills': 'Experience in Skills',
        }
        # Map and filter fields
        mapped_fields = {field: field_mapping.get(field.lower(), field) for field in fields}
        filtered_result = {key: result[key] for key in mapped_fields.values() if key in result}

        # Add placeholder if requested fields are not found
        for field in mapped_fields.values():
            if field not in filtered_result:
                filtered_result[field] = 'data not found'

        return jsonify({'status': 'success', 'data': filtered_result}), 200

    # Convert ObjectId to string for JSON serialization
    result['_id'] = str(result['_id'])

    return jsonify({'status': 'success', 'data': result}), 200

#=========================================================== 2. UPDATE API CALL===============================================================

@app.route('/update_candidate', methods=['POST'])  
def update_candidate():  
    data = request.get_json()  
    # name = data['name']  
    name = data.get('name')
    # updated_data = data['details']  
    updated_data = data.get('details')
    if not name or not updated_data:
        return jsonify({'error': 'Name and details are required'}), 400
    
    # Update candidate
    result = collection.update_one({'Name': name}, {'$set': updated_data})
    if result.matched_count == 0:
        return jsonify({'error': 'No candidate found'}), 404
    return jsonify({'message': 'Candidate updated successfully'})


#============================================================ 3. DELETE API CALL ==============================================================

@app.route('/delete_candidate', methods=['POST'])  
def delete_candidate():  
    data = request.get_json()  
    # name_email = data['name_email']  
    name_email = data.get('name_email')

    if not name_email:
        return jsonify({'error': 'name_email field is required'}), 400

    # Delete candidate
    query = {'Email Address': name_email} if '@' in name_email else {'Name': name_email}
    result = collection.delete_one(query)
    if result.deleted_count == 0:
        return jsonify({'error': 'No candidate found'}), 404
    return jsonify({'message': 'Candidate deleted successfully'})


#========================================================== FIND BEST CANDIDATE API CALL ===============================================
# Best Fit Candidate Search  

@app.route('/api/find_best_fit_candidates', methods=['POST'])
def find_best_fit_candidates():
    print("Inside find_best_fit_candidates route.")  # Debug print

    # Handle multipart/form-data (form submission)
    job_level = request.form.get('jobLevel') or request.form.get('job_level')
    print(f"Received Job Level: {job_level}")
    job_description = request.form.get('jobDescription')  # From textarea (name="jobDescription")
    file = request.files.get('file')  # From file input (name="file")

    # Debug: Print the received inputs
    print(f"Job Level: {job_level}")
    print(f"Job Description: {job_description}")
    if file:
        print(f"File Uploaded: {file.filename}")
    else:
        print("No file uploaded.")

    # Validate inputs
    if not job_level:
        return {"error": "Job level is required."}, 400
    if not job_description and not file:
        return {"error": "Either job description or file is required."}, 400

    # If a file is uploaded, process it to extract job description
    if file:
        try:
            file_path = os.path.join('/tmp', file.filename)
            file.save(file_path)  # Save the file temporarily
            job_description = read_job_description_file(file_path)  # Custom function to read file content
            print(f"Extracted Job Description from file: {job_description}")
        except Exception as e:
            print(f"Error processing file: {e}")
            return jsonify({"error": "Failed to process the uploaded file."}), 500

    # Load candidate data (assuming a custom function to fetch candidates)
    try:
        candidates_data_mongo = load_candidates_from_mongo()  # Custom function
        candidates_text = convert_candidates_to_text(candidates_data_mongo)  # Convert candidates to text
    except Exception as e:
        print(f"Error loading candidates: {e}")
        return jsonify({"error": "Failed to load candidates."}), 500

    # Analyze candidates with the job description
    try:
        evaluation_report = analyze_candidates_with_job_description(
            job_description, job_level, candidates_text
        )
        print(f"Evaluation Report: {evaluation_report}")
    except Exception as e:
        print(f"Error during analysis: {e}")
        return jsonify({"error": "Analysis failed."}), 500

    # Save the evaluation report to MongoDB
    report_document = {
        "job_level": job_level,
        "job_description": job_description,
        "evaluation_report": evaluation_report,
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
    }

    try:
        # Save the evaluation report to MongoDB
        result= evaluation_reports_collection.insert_one(report_document)
        report_document["_id"] = str(result.inserted_id)  # Convert ObjectId to string
        print("Report saved successfully.")
    except Exception as e:
        print(f"Error saving report to MongoDB: {e}")
        return jsonify({"error": "Failed to save the evaluation report."}), 500

    # Return the evaluation report
    return jsonify(report_document), 200

# Function to analyze candidates with job description and job level
# Helper functions


def read_job_description_file(file_path):
    """Reads job description from a file."""
    print(f"Processing file: {file_path}")
    file_extension = os.path.splitext(file_path)[1].lower()  # Extract file extension in lowercase

    try:
        if file_extension == ".txt":
            with open(file_path, "r", encoding="utf-8-sig") as file:  # Explicit encoding
                return file.read()
        elif file_extension == ".pdf":
            pdf = PdfReader(file_path)
            return "".join(page.extract_text() for page in pdf.pages).strip()
        elif file_extension == ".docx":
            doc = Document(file_path)
            return "\n".join(para.text for para in doc.paragraphs).strip()
        else:
            raise ValueError("Unsupported file format. Only .txt, .pdf, or .docx files are allowed.")
    except Exception as e:
        print(f"Error processing file: {e}")
        raise

# Function to analyze candidates with job description and job level
def analyze_candidates_with_job_description(job_description, job_level, candidates_text):
    """Analyzes candidates against job description and job level."""
    prompt_template = load_prompt_template()
    if not prompt_template:
        raise ValueError("Prompt template could not be loaded.")

    # Format the prompt
    prompt = prompt_template.format(
        job_description=job_description,
        job_level=job_level,
        candidates_text=candidates_text
    )

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('*', '').replace('#', '')
        return markdown.markdown(cleaned_response)  # Return HTML output
    except Exception as e:
        print(f"Error generating content: {e}")
        raise ValueError("Content generation failed.")

def load_candidate_data(json_file):  
    with open(json_file, 'r') as f:  
        return json.load(f) 

def load_candidates_from_mongo():  
    candidates = collection.find()  # Retrieve all candidates from MongoDB
    candidates_data = {}
    for candidate in candidates:
        candidate['_id'] = str(candidate['_id'])  # Convert ObjectId to string
        candidates_data[candidate['Name']] = candidate  # Use Name as the key (or adjust as needed)
    return candidates_data  

# Function to convert candidate data into formatted text
def convert_candidates_to_text(candidates):  
    candidate_texts = []  
    for candidate in candidates.values():  
        text = f"Candidate Name: {candidate.get('Name', 'NA')}\n" \
               f"Email: {candidate.get('Email Address', 'NA')}\n" \
               f"Primary Skills: {candidate.get('Primary Skills', 'NA')}\n" \
               f"Secondary Skills: {candidate.get('Secondary Skills', 'NA')}\n" \
               f"Total Experience: {candidate.get('Total Experience', 'NA')}\n" \
               f"Relevant Experience in Primary Skills: {candidate.get('Relevant Experience in Primary Skills', 'NA')}\n" \
               f"Relevant Experience in Secondary Skills: {candidate.get('Relevant Experience in Secondary Skills', 'NA')}\n"  
        candidate_texts.append(text.strip())  
    return "\n\n".join(candidate_texts)  

# Load environment variables from the .env file in the config folder
load_dotenv(r'./config/.env')

def load_prompt_template():
    try:
        # Read the prompt template from the file
        with open(os.getenv("PROMPT_TEMPLATE_PATH", "./config/evaluation_prompt_template.txt"), 'r') as file:
            return file.read()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return None

#======================================================== CLEAR COLLECTION API ===========================================================
# Clear the collections (as an example)
@app.route('/clear_collection', methods=['POST'])
def clear_collection():
    try:
        # Get the collection name from the request body
        data = request.get_json()
        collection_name = data['collection']
        
        # Log the collection name to verify it's correct
        logging.info(f"Attempting to clear collection: {collection_name}")
        
        # Get the collection from the database
        collection = db[collection_name]

        # Log the number of documents before deletion
        pre_delete_count = collection.count_documents({})
        logging.info(f"Pre-deletion count for {collection_name}: {pre_delete_count}")
        
        # Delete all documents in the collection
        result = collection.delete_many({})

        # Log the number of documents deleted
        logging.info(f"Deleted {result.deleted_count} documents from {collection_name}")
        
        # Return the count of deleted documents
        return jsonify({"deletedCount": result.deleted_count})
    
    except Exception as e:
        logging.error(f"Error clearing collection {collection_name}: {e}")
        return jsonify({"error": f"Error clearing collection {collection_name}: {str(e)}"}), 500


if __name__ == '__main__':  
    app.run(threaded=False)