import os
import json
import polars as pl
from pymilvus import MilvusClient
from openai import OpenAI


class MilvusManager:
    def __init__(self, collection_name):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model_name = "text-embedding-3-small"
        self.milvus_client = MilvusClient(uri="http://localhost:19530")
        self.collection_name = collection_name


    def create_embeddings(self, text):
        response = self.openai_client.embeddings.create(input=text, model=self.model_name)
        response_json = json.loads(response.model_dump_json())
        embedding = response_json['data'][0]['embedding']
        # logger.info("Embedding generated for text")
        return embedding
    

    def create_collection(self):
        try:
            if self.milvus_client.has_collection(collection_name=self.collection_name):
                self.milvus_client.drop_collection(collection_name=self.collection_name)
            self.milvus_client.create_collection(
                collection_name=self.collection_name,
                dimension=1536,  # The vectors we will use in this demo has 768 dimensions
                auto_id=False, 
            )
            # logger.info(f"Collection created: {self.collection_name}")
            print(f"Collection created: {self.collection_name}")
        except Exception as e:
            # logger.error(f"Error creating collection: {e}")
            print(f"Error creating collection: {e}")


    def insert_points(self, df: pl.DataFrame):
        dtf = df.with_columns((pl.col("text").map_elements(self.create_embeddings, return_dtype=pl.List(pl.Float64))).alias("vector"))
        data = dtf.to_dicts()
        res = self.milvus_client.upsert(
            collection_name=self.collection_name,
            data=data
        )
        print(res)


    def search(self, input_text, limit=3):
        search_params = {
            "metric_type": "COSINE",
            "params": {
                "radius": 0.5, # Radius of the search circle
                "range_filter": 0.8 # Range filter to filter out vectors that are not within the search circle
            }
        }
        query_embedding = self.create_embeddings(input_text)
        res = self.milvus_client.search(
            collection_name=self.collection_name,
            data=[query_embedding],
            limit=limit, 
            search_params=search_params, # Search parameters
            output_fields=["text", "metadata"], # Output fields to return
        )
        return json.dumps(res)