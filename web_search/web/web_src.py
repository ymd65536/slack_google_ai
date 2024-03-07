import os
import datetime

from web import bigquery_vector

from langchain_community.document_loaders.recursive_url_loader import RecursiveUrlLoader
from langchain_community.document_transformers import Html2TextTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain_google_vertexai import VertexAI
from langchain.chains import RetrievalQA

from google.cloud.discoveryengine import SearchServiceClient, SearchRequest
from google.protobuf.json_format import MessageToDict

PROJECT_ID = os.environ.get("PROJECT_ID", None)


def _get_keyword(prompt: str, filter_words: list):
    """
        LLMがプロンプトからキーワード弾き出したあと機械的に特定の文字列を削除して取得する
    Returns:
        _type_: 特定のキーワードを削除したあとの文字列
    """
    llm = VertexAI(
        model_name=os.environ.get("GEMINI_MODEL_NAME", None),
        max_output_tokens=1024,
        temperature=0.1,
        top_p=0.8,
        top_k=40,
        verbose=True,
    )
    template = f"次の文から主要なキーワードのみをスペース区切りで抜き出してください。: {prompt}"
    keyword = llm.invoke(template)

    for filter_word in filter_words:
        keyword = keyword.replace(filter_word, '')

    return keyword


def _search_web(keyword: str):
    """
        Webページとメタデータを取得する

    Returns:
        _type_: Webページの情報を格納した辞書型の変数、検索にヒットしなかった場合:documentsキーに空の配列を返す
    """

    discov_client = SearchServiceClient()
    serving_config = discov_client.serving_config_path(
        project=PROJECT_ID,
        location='global',
        data_store=os.environ.get("DATA_STORE_WEB", None),
        serving_config='default_config'
    )

    results = discov_client.search(
        SearchRequest(
            serving_config=serving_config,
            query=keyword,
            page_size=3
        )
    )
    documents = []
    responses = {"keyword": keyword}

    if not results.results:
        responses['documents'] = documents
    else:
        for r in results.results:
            document_info = {}
            r_dct = MessageToDict(r._pb)
            document_info['title'] = r_dct['document']['derivedStructData']['title']
            document_info['link'] = r_dct['document']['derivedStructData']['link']
            document_info['html_file_name'] = r_dct['document']['derivedStructData']['link'].split('/')[-1]
            if not document_info['html_file_name'] == "":
                documents.append(document_info)
        responses['documents'] = documents

    return responses


def _get_web_page_document(url: str, start_tag: str, end_tag: str) -> list:
    """
        Webページのドキュメントを取得してBody部分だけ取り出すメソッド
    Returns:
        _type_: WebページのうちBodyタグで囲まれた文字列(htmlパース後の文字列)
    """
    loader = RecursiveUrlLoader(url)
    documents = loader.load()

    for document in documents:
        start_index = document.page_content.find(start_tag)
        end_index = document.page_content.find(end_tag)
        documents[0].page_content = document.page_content[start_index:end_index]

    html2text = Html2TextTransformer()
    plain_text = html2text.transform_documents(documents)

    # 1000文字単位で分割する際、1000文字未満の文字列だと1000文字分割は意味がないためそのまま格納
    text_li = []
    if len(plain_text[0].page_content) > 999:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["\n\n", "。"]
        )
        text_li.extend(text_splitter.split_documents(plain_text))

    else:
        text_li.extend(plain_text)

    return text_li


def _get_documents(prompt, keyword, documents):
    """
        Webページから本文とメタデータを取り出す
    Returns:
        _type_: 辞書型:vector_storeに利用するWebページのメタデータセット
    """
    docs = []
    metadatas = []

    DIFF_JST_FROM_UTC = 9
    result_time = datetime.datetime.utcnow() + datetime.timedelta(hours=DIFF_JST_FROM_UTC)
    yyyymmdd = f"{result_time.strftime('%Y')}-{result_time.strftime('%m')}-{result_time.strftime('%d')}"
    hourminsec = f" {result_time.strftime('%H')}:{result_time.strftime('%M')}:{result_time.strftime('%S')}"

    for document in documents:
        html_file_name = document['html_file_name']
        html_docs = _get_web_page_document(document['link'], '<main', '</main')

        for html_doc in html_docs:
            docs.append("タイトル" + document["title"] + "\nリンク:" + document['link'] + '\n' + html_doc.page_content)
            metadatas.append(
                {
                    "yyyymmdd": yyyymmdd,
                    "hourminsec": hourminsec,
                    "prompt": prompt,
                    "keyword": keyword,
                    "title": document["title"],
                    "link": document['link'],
                    "len": str(len(html_doc.page_content)),
                    "html_file": html_file_name,
                    "update_time": str(result_time)
                }
            )
    return {"docs": docs, "metadatas": metadatas}


def _create_main_prompt(input_prompt: str):
    return input_prompt + "お客様名から書き始めて、100文字で要約し、最後にリンクをつけてください。"


def run_query(prompt: str, filter_words):
    """
        ユーザが入力したプロンプトに応じてLLMを実行する
    Returns:
        _type_: 質問と回答の組み合わせをもつ辞書型の変数
    """

    key_word = _get_keyword(
        prompt=prompt,
        filter_words=filter_words
    )

    responses = _search_web(key_word)
    documents = responses['documents']

    if not documents:
        result = {'query': prompt, 'result': "No Answer"}
    else:
        docs_and_metadata = _get_documents(prompt, key_word, documents)
        vector_store = bigquery_vector.get_bigquery_vector_store(
            os.environ.get('BIGQUERY_DATASET', None),
            os.environ.get('BIGQUERY_TABLE', None)
        )

        NUMBER_OF_RESULTS = 3
        retriever = vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": NUMBER_OF_RESULTS}
        )

        vector_store.add_texts(
            docs_and_metadata['docs'],
            metadatas=docs_and_metadata['metadatas']
        )
        chat = VertexAI(
            model_name=os.environ.get("USE_TEXT_MODEL_NAME", None),
            temperature=0
        )

        qa_chain = RetrievalQA.from_chain_type(
            llm=chat, chain_type="stuff",
            retriever=retriever
        )

        main_prompt = _create_main_prompt(prompt)
        result = qa_chain.invoke(main_prompt)

    return result
