from typing import List

import pandas as pd
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings


def df_to_documents(df: pd.DataFrame, content_column_name: str) -> List[Document]:
    """
    Given a dataframe, convert it to a list of documents.

    :param df: pd.DataFrame
    :param content_column_name: str

    :return: List[Document]
    """
    documents = []
    for _, row in df.iterrows():
        metadata = row.to_dict()
        page_content = metadata.pop(content_column_name)
        documents.append(Document(page_content=page_content, metadata=metadata))
    return documents


def documents_to_df(
    content_column_name: str,
    documents: List[Document],
    embedding_model: Embeddings = None,
    with_embeddings: bool = False,
) -> pd.DataFrame:
    """
    Given a list of documents, convert it to a dataframe.

    :param content_column_name: str
    :param documents: List[Document]
    :param embedding_model: Embeddings
    :param with_embeddings: bool

    :return: pd.DataFrame
    """
    if not documents:
        return pd.DataFrame()

    # Extract metadata and page_content in a single pass for efficiency
    meta_list = []
    content_list = []
    for doc in documents:
        # Shallow copy metadata to avoid mutating original
        meta = dict(doc.metadata) if doc.metadata is not None else {}
        meta_list.append(meta)
        content_list.append(doc.page_content)

    # Get all unique metadata keys to ensure consistent column order
    all_keys = set()
    for meta in meta_list:
        all_keys.update(meta.keys())

    # Insert content_column_name as the first field
    columns = [content_column_name] + sorted(k for k in all_keys if k != content_column_name)

    # Build rows as dicts in the right order to avoid reordering DataFrame
    rows = []
    for meta, content in zip(meta_list, content_list):
        row = {k: meta.get(k, None) for k in all_keys}
        row[content_column_name] = content  # Insert content
        rows.append(row)

    # Build DataFrame
    df = pd.DataFrame(rows, columns=columns)

    # Only parse 'date' if it exists in columns.
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if with_embeddings:
        df["embeddings"] = embedding_model.embed_documents(content_list)

    return df
