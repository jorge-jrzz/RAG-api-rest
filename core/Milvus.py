"""
This module contains the MilvusManager class, which is responsible for managing the Milvus database.
"""

import os
import json
from typing import List
import polars as pl
from pymilvus import MilvusClient
from openai import OpenAI
from .utils import get_logger


logger = get_logger(__name__)

class MilvusManager:
    """
    MilvusManager class.
    This class is responsible for managing the Milvus database.
    """

    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model_name = os.getenv("EMBEDDING_MODEL")
        self.milvus_client = MilvusClient(uri=os.getenv("MILVUS_URL"))

    def create_embeddings(self, text: str) -> List:
        """
        Create embeddings for a given text.

        Args:
            text (str): The text to generate embeddings for.

        Returns:
            List: The embeddings generated for the text.
        """

        response = self.openai_client.embeddings.create(input=text, model=self.model_name)
        response_json = json.loads(response.model_dump_json())
        embeddings = response_json['data'][0]['embedding']
        logger.info("Embedding generated for text")
        return embeddings

    def create_collection(self, collection_name: str) -> None:
        """
        Create a collection in Milvus.
        If the collection already exists, it is dropped and recreated.

        Args:
            collection_name (str): The name of the collection.
        
        Returns:
            None
        """

        try:
            if self.milvus_client.has_collection(collection_name=collection_name):
                self.milvus_client.drop_collection(collection_name=collection_name)
            self.milvus_client.create_collection(
                collection_name=collection_name,
                dimension=1536,  # The vectors dimension (from the embedding model)
                auto_id=False, 
            )
            logger.info("Collection created: %s", collection_name)
        except Exception as e:
            logger.error("Error creating collection %s:", e)

    def insert_points(self, collection_name: str, df: pl.DataFrame) -> None:
        """
        Insert points into the Milvus collection.
        Creates embeddings for the text column and inserts them into the collection.

        Args:
            df (pl.DataFrame): The DataFrame containing the text column.

        Returns:
            None
        """

        dtf = df.with_columns((pl.col("text").map_elements(
            self.create_embeddings, 
            return_dtype=pl.List(pl.Float64))
            ).alias("vector"))
        data = dtf.to_dicts()
        _ = self.milvus_client.upsert(
            collection_name=collection_name,
            data=data
        )
        logger.info("Points inserted into collection")

    def search_points(self, collection_name: str, input_text: str, limit: int = 3) -> str:
        """
        Search for points in the Milvus collection.
        Creates embeddings for the input text and searches for similar points in the collection.

        Args:
            collection_name (str): The name of the collection.
            input_text (str): The input text to search for.
            limit (int) default = 3: The number of similar points to return.

        Returns:
            str: The search results in JSON format.
        """

        search_params = {
            "metric_type": "COSINE",
            "params": {
                "radius": 0.4, # Radius of the search circle
                "range_filter": 0.5 # Range filter to filter out vectors that are not within the search circle
            }
        }
        query_embedding = self.create_embeddings(input_text)
        res = self.milvus_client.search(
            collection_name=collection_name,
            data=[query_embedding],
            limit=limit, 
            search_params=search_params, # Search parameters
            output_fields=["text", "metadata"], # Output fields to return
        )
        logger.info("Points searched in collection")
        return json.dumps(res)
