# AIcruiter
An AI-powered resume parsing tool that leverages Gemini AI to optimize recruitment and hiring processes.

# Resume Data Extraction and Analysis Project
## Overview
This project focuses on extracting, analyzing, and managing resume data using various AI and data processing techniques. The core functionalities include resume data extraction, parsing, and candidate search for the best-fit candidates based on job descriptions. It utilizes a Flask web application to provide an interactive interface.
## Components
### 1. **Data Extraction and Parsing**
- **extractor.py**: This module is responsible for extracting relevant information from resumes. It employs techniques to parse and structure data for further analysis.
- **resume_parsing_CRUD.py**: This module provides CRUD (Create, Read, Update, Delete) operations on the extracted resume data, using MongoDB for data storage.
    - **Libraries Used**:
        ```python
        import json
        import pymongo
        from pymongo import MongoClient
        ```
### 2. **Candidate Search**
- **resume_candidate_search.py**: This script implements functionality to search for the best-fit candidates based on job descriptions using the Gemini AI model.
    - **Gemini API Key**: Ensure you have the Gemini API key for authentication.
### 3. **Flask Application**
- **app.py**: The main Flask application that integrates the functionalities of the above modules and serves as the backend for the project.
    - **Libraries Used**:
        ```python
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
        ```
### 4. **Frontend**
- **index.html**: This file serves as the frontend interface of the application. It uses internal CSS, JavaScript, and Bootstrap for styling and functionality. The frontend enables users to interact with the application, upload resumes, and view results.
