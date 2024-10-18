"""
This module contains the main code for the RAG API
"""

import os
from typing import Optional, List, Dict
import json
import polars as pl
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify
from core import FileManager, AcceptedFiles, Another, OCR, TextChunk, MilvusManager, get_logger, delete_files_directory


UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = ['txt', 'html', 'md', 'java', 'py', 'c', 'cpp', 'js', 'pdf', 
                      'png', 'jpg', 'jpeg', 'ppt', 'pptx', 'doc', 'docx']

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
milvus_manager = MilvusManager()
logger = get_logger(__name__)


def allowed_file(filename: str, extensions: List[str]) -> bool:
    """
    Function to check if the file format is allowed.

    Args:
        extensions (List[str]): The list of allowed extensions.
        filename (str): The name of the file.

    Returns:
        bool: True if the file format is allowed, False otherwise.
    """

    # Primero crea una lista con el nombre del archivo y la extensión
    # Selecciona el segundo elemento de la lista, que es la extensión y la convierte a minúsculas
    # Comprueba si la extensión está en la lista de extensiones permitidas
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in extensions

def ensure_file_format(file: str) -> Optional[str]:
    """
    Function to aplly the strategy pattern to move the file to the destination directory.

    Args:
        file (str): The path of the file.

    Returns:
        Optional[str]: The path of the file moved to the destination directory.
    """

    file_manager = FileManager()
    if allowed_file(file, ALLOWED_EXTENSIONS[:9]):
        file_manager.set_strategy(AcceptedFiles())
    else:
        file_manager.set_strategy(Another())
    path = file_manager.execute_strategy(file, dst_dir='./uploads/documents/')
    return path

def make_ocr(file: str) -> List[Dict]:
    """
    Function to extract text from a file using OCR.

    Args:
        file (str): The path of the file.
    
    Returns:
        List[Dict]: A list of dictionaries containing the text and metadata of the file.
    """

    if file is not None and file.lower().endswith('.pdf'):
        data = OCR.get_ocr(file)
    else:
        data = OCR.get_dev_ocr(file)
    return data

def get_text_chunks(ocr_text: List[Dict]) -> pl.DataFrame:
    """
    Function to add text chunks to a Polars DataFrame.

    Args:
        ocr_text (List[Dict]): A list of dictionaries containing the text and metadata of the file.
    
    Returns:
        pl.DataFrame: A Polars DataFrame with the text chunks
    """

    data_df = pl.DataFrame({})
    df_text = TextChunk.add_chunks_to_dataframe(data_df, ocr_text)
    TextChunk.save_checkpoint(df_text, './data/checkpoint.db')
    return df_text

def insert_points(df_points: pl.DataFrame) -> None:
    """
    Function to insert points in Milvus.

    Args:
        df_points (pl.DataFrame): The DataFrame containing the text column.

    Returns:
        None
    """

    milvus_manager.create_collection("collection")
    milvus_manager.insert_points("collection", df_points)

def get_context(query: str) -> List[str]:
    """
    Function to get the context of a query.

    Args:
        query (str): The query to search for.

    Returns:
        List[str]: A list of strings with the context of the query.
    """

    data = milvus_manager.search_points("collection", query)
    points = json.loads(data)
    context = []
    for point in points[0]:
        context.append(point['entity'])
    return context


# Routes: /hello, /upload, /search

@app.get("/hello")
def hello():
    return "<h1>Hello, World!</h1>"

@app.post('/upload')
def upload_file():
    # check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({"error": "No file has been sent: 'file'"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file has been sent: 'file'"}), 401
    
    if file and allowed_file(file.filename, ALLOWED_EXTENSIONS):
        filename = secure_filename(file.filename)
        path_file = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path_file)
        accepted_file = ensure_file_format(path_file)       # Ensure file format
        text_file = make_ocr(accepted_file)                 # Extract text from file (OCR)
        text_chunks = get_text_chunks(text_file)            # Get text chunks (pl.DataFrame)
        insert_points(text_chunks)                          # Insert points in Milvus
        return jsonify({"message": "File uploaded successfully"}), 200
    else:
        return jsonify({"error": "Invalid file format: 'file'"}), 400
    
@app.post('/search')
def search_similarity():
    text_query = request.args.get('text_query')
    if text_query is None:
        return jsonify({"error": "No query has been sent: 'text_query'"}), 400
    context = get_context(text_query)
    return jsonify({"context": context}), 200
    

if __name__ == "__main__":
    app.run(debug=True)
