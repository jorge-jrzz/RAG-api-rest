import json
import copy
import sqlite3
from typing import List, Dict, Optional, Union
from sqlalchemy import create_engine
import polars as pl


class TextChunk():
    """
    Class to handle text chunks and add them to a Polars DataFrame
    """
    def __init__(self, current_df: Optional[pl.DataFrame] = pl.DataFrame()):
        self.current_df = current_df
    
    def _pdf_chunk(self, json_data: List[Dict]) -> pl.DataFrame:
        """
        Create a DataFrame from a list of dictionaries with text chunks from a PDF file

        Args:
            json_data (List[Dict]): List of dictionaries with text chunks from a PDF file
        
        Returns:
            pl.DataFrame: polars DataFrame with the text chunks
        """
        for item in json_data:
            item['metadata'] = json.dumps(item['metadata'])
            item['text'] = item['text'].decode('utf-8')
        # Crea el DataFrame de Polars con los datos y un índice que empieza en el último índice del DataFrame actual
        return pl.DataFrame(json_data).with_row_index('id', offset=len(self.current_df)+1)

    def _add_if_not_exists(self, new_data: Union[pl.DataFrame, Dict], key_columns: Optional[List] = ['metadata', 'text']) -> pl.DataFrame:
        """
        Add new data to the current DataFrame if it does not exist

        Args:
            new_data (Union[pl.DataFrame, Dict]): New data to add to the DataFrame
            key_columns (Optional[List]): Columns to use as keys to identify if the data already exists, by default ['metadata', 'text']
        
        Returns:
            pl.DataFrame: Currently updated polars DataFrame
        """
        # Si nuevos_datos es un diccionario, convertirlo a DataFrame, si no, verificar que sea un DataFrame
        if isinstance(new_data, dict):
            new_data = pl.DataFrame([new_data])
        elif not isinstance(new_data, pl.DataFrame):
            raise TypeError("nuevos_datos debe ser un DataFrame de Polars o un diccionario")
        # Si el DataFrame actual está vacío, asignarle los nuevos datos y retornarlo
        if self.current_df.is_empty():
            self.current_df = self.current_df.vstack(new_data)
            return self.current_df
        # Crear una expresión para verificar si los datos ya existen
        condition = pl.all_horizontal([
            pl.col(col).is_in(new_data[col])
            for col in key_columns
        ])
        # Filtrar los datos existentes
        existing_data = self.current_df.filter(condition)
        # Identificar los datos nuevos
        new = new_data.join(
            existing_data.select(key_columns),
            on=key_columns,
            how="anti"
        )
        # Si hay datos nuevos, agregarlos al DataFrame original
        if not new.is_empty():
            print("Se han encontrado datos nuevos para agregar")
            self.current_df = pl.concat([self.current_df, new], how="vertical")
        else:
            print("No hay datos nuevos para agregar")
        return self.current_df
    
    def add_chunks_to_dataframe(self, json_data: List[Dict]) -> pl.DataFrame:
        """
        Add text chunks to the current DataFrame. The method will identify the type of file and call the corresponding method to process the data

        Args:
            json_data (List[Dict]): List of dictionaries with text chunks
        
        Returns:
            pl.DataFrame: Currently updated polars DataFrame
        """
        filetype = json_data[0]['metadata']['filetype']
        if filetype == "application/pdf":
            df = self._pdf_chunk(json_data)
        elif filetype.startswith('text'):
            data = copy.deepcopy(json_data)
            data[0]['metadata'] = json.dumps(data[0]['metadata'])
            df = pl.DataFrame(data).with_row_index('id', offset=len(self.current_df)+1)
        self._add_if_not_exists(new_data=df)
        return self.current_df

    def save_checkpoint(self, checkpoint_path: str, table_name: Optional[str] = 'ocr_data') -> None:
        """
        Save the current DataFrame to a SQLite database

        Args:
            checkpoint_path (str): Path to the SQLite database
            table_name (Optional[str]): Name of the table to store the data, by default 'ocr_data'

        Returns:
            None
        """
        conn = sqlite3.connect(checkpoint_path)
        temp_df = self.current_df.clone()
        temp_df.drop_in_place('id')
        temp_df.write_database(table_name=table_name, connection=f"sqlite:///{checkpoint_path}", if_table_exists="replace")
        conn.close()
    
    def load_checkpoint(self, checkpoint_path: str, table_name: Optional[str] = 'ocr_data') -> pl.DataFrame:
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
        self.current_df = pl.read_database(query=query, connection=conn.connect()).with_row_index('id')
        return self.current_df
