"""
This module contains the TextChunk class, which is used to handle text chunks and add them to a Polars DataFrame
"""

import json
import copy
import sqlite3
from typing import List, Dict, Optional, Union
import polars as pl
from sqlalchemy import create_engine
from .utils import get_logger


logger = get_logger(__name__)

class TextChunk():
    """
    Class to handle text chunks and add them to a Polars DataFrame
    """
    
    @classmethod
    def _pdf_chunk(cls, data_df: pl.DataFrame, json_data: List[Dict]) -> pl.DataFrame:
        """
        Create a DataFrame from a list of dictionaries with text chunks from a PDF file

        Args:
            data_df (pl.DataFrame): DataFrame that will be updated with the new data (Current DataFrame)
            json_data (List[Dict]): List of dictionaries with text chunks from a PDF file
        
        Returns:
            pl.DataFrame: polars DataFrame with the text chunks
        """
        for item in json_data:
            item['metadata'] = json.dumps(item['metadata'])
            # Decodificar el texto a UTF-8
            item['text'] = item['text'].decode('utf-8')
        # Crea el DataFrame de Polars con los datos y un índice que empieza en el último índice del DataFrame actual
        new_df = pl.DataFrame(json_data).with_row_index('id', offset=len(data_df)+1)
        logger.info("DataFrame created from PDF chunks")
        return new_df

    @classmethod
    def _add_if_not_exists(cls, data_df: pl.DataFrame, 
                           new_data: Union[pl.DataFrame, Dict], 
                           key_columns: Optional[List] = None) -> pl.DataFrame:
        """
        Add new data to the current DataFrame if it does not exist. 

        Args:
            data_df (pl.DataFrame): DataFrame that will be updated with the new data (Current DataFrame)
            new_data (Union[pl.DataFrame, Dict]): New data to add to the DataFrame
            key_columns (Optional[List]): List of columns to use as keys to identify existing data, by default None -> ['metadata', 'text']

        Returns:
            pl.DataFrame: Updated DataFrame with the new data added or the same DataFrame if no new data is found

        Raises:
            TypeError: If new_data is not a DataFrame or a dictionary
        """
        # Inicializar la lista de columnas clave si no se proporciona
        if key_columns is None:
            key_columns = ['metadata', 'text']
        # Si nuevos_datos es un diccionario, convertirlo a DataFrame, si no, verificar que sea un DataFrame
        if isinstance(new_data, dict):
            new_data = pl.DataFrame([new_data])
        elif not isinstance(new_data, pl.DataFrame):
            logger.error("new_data must be a Polars DataFrame or a dictionary")
            raise TypeError("new_data must be a Polars DataFrame or a dictionary")
        # Si el DataFrame actual está vacío, asignarle los nuevos datos y retornarlo
        if data_df.is_empty():
            data_df = data_df.vstack(new_data)
            logger.info("New data added to the DataFrame")
            return data_df
        # Crear una expresión para verificar si los datos ya existen
        condition = pl.all_horizontal([
            pl.col(col).is_in(new_data[col])
            for col in key_columns
        ])
        # Filtrar los datos existentes
        existing_data = data_df.filter(condition)
        # Identificar los datos nuevos
        new = new_data.join(
            existing_data.select(key_columns),
            on=key_columns,
            how="anti"
        )
        # Si hay datos nuevos, agregarlos al DataFrame original
        if not new.is_empty():
            logger.info("New data found to add")
            data_df = pl.concat([data_df, new], how="vertical")
        else:
            logger.warning("No new data to add")
        return data_df
    
    @classmethod
    def add_chunks_to_dataframe(cls, data_df: pl.DataFrame, json_data: List[Dict]) -> pl.DataFrame:
        """
        Add text chunks to the current DataFrame. The method will identify the type of file and call the corresponding method to process the data

        Args:
            data_df (pl.DataFrame): DataFrame that will be updated with the new data (Current DataFrame)
            json_data (List[Dict]): List of dictionaries with text chunks
        
        Returns:
            pl.DataFrame: Currently updated polars DataFrame with the new data added or the same DataFrame if the filetype is not supported
        """

        filetype = json_data[0]['metadata']['filetype']
        df = None
        if filetype == "application/pdf":
            df = cls._pdf_chunk(data_df, json_data)
            logger.info("PDF chunks added to the DataFrame")
        elif filetype.startswith('text'):
            # Crear una copia profunda de los datos para evitar modificar el original
            data = copy.deepcopy(json_data)
            data[0]['metadata'] = json.dumps(data[0]['metadata'])
            df = pl.DataFrame(data).with_row_index('id', offset=len(data_df)+1)
            logger.info("Text chunks added to the DataFrame")
        if df is not None:
            updated_df = cls._add_if_not_exists(data_df, new_data=df)
            logger.info("Data added to the DataFrame")
            return updated_df
        logger.error("Filetype not supported")
        return data_df

    @classmethod
    def save_checkpoint(cls, data_df: pl.DataFrame, checkpoint_path: str, table_name: Optional[str] = 'ocr_data') -> None:
        """
        Save the current DataFrame to a SQLite database

        Args:
            data_df (pl.DataFrame): DataFrame to save to the SQLite database (current DataFrame)
            checkpoint_path (str): Path to the SQLite database
            table_name (Optional[str]): Name of the table to store the data, by default 'ocr_data'

        Returns:
            None
        """

        conn = sqlite3.connect(checkpoint_path)
        temp_df = data_df.clone()
        temp_df.drop_in_place('id')
        temp_df.write_database(table_name=table_name, connection=f"sqlite:///{checkpoint_path}", if_table_exists="replace")
        conn.close()
        logger.info("DataFrame saved to SQLite database")
    
    @classmethod
    def load_checkpoint(cls, checkpoint_path: str, table_name: Optional[str] = 'ocr_data') -> pl.DataFrame:
        """
        Load a DataFrame from a SQLite database

        Args:
            checkpoint_path (str): Path to the SQLite database
            table_name (Optional[str]): Name of the table to load the data from, by default 'ocr_data'

        Returns:
            pl.DataFrame: DataFrame loaded from the SQLite database (current DataFrame)
        """

        conn = create_engine(f"sqlite:///{checkpoint_path}")
        query = f"SELECT * FROM {table_name}"
        data_df = pl.read_database(query=query, connection=conn.connect()).with_row_index('id')
        return data_df
