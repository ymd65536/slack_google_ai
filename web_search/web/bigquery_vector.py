import os

from langchain_community.vectorstores import BigQueryVectorSearch
from langchain.vectorstores.utils import DistanceStrategy
from langchain_google_vertexai import VertexAIEmbeddings

PROJECT_ID = os.environ.get("PROJECT_ID", None)
use_embedding_model_name = os.environ.get("USE_MODEL_NAME", None)
REGION = os.environ.get("REGION", None)


def get_VertexAIEmbeddings():
    return VertexAIEmbeddings(
        model_name=use_embedding_model_name, project=PROJECT_ID
    )


def get_bigquery_vector_store(DATASET, TABLE):
    """
        BigQuery Vector Searchオブジェクトを生成するメソッド
    Returns:
        _type_: BigQuery Vector Search オブジェクト
    """

    embedding = get_VertexAIEmbeddings()

    store = BigQueryVectorSearch(
        project_id=PROJECT_ID,
        dataset_name=DATASET,
        table_name=TABLE,
        location=REGION,
        embedding=embedding,
        distance_strategy=DistanceStrategy.EUCLIDEAN_DISTANCE,
    )

    return store
