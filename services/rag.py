# ===========================
# MATH 
# ===========================

import math

EMBEDDING_MODEL = "mistral-embed"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = 3
SIMILARITY_THRESHOLD = 0.60
EMBEDDING_BATCH_SIZE = 16


def create_chunks_from_pdf(reader, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()

        if not page_text:
            continue

        page_text = page_text.strip()

        if not page_text:
            continue

        start = 0
        text_length = len(page_text)

        while start < text_length:
            end = start + chunk_size
            chunk_text = page_text[start:end].strip()

            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "page": page_number
                })

            if end >= text_length:
                break

            start = end - overlap

    return chunks


def create_embeddings(mistral_client, texts):
    all_embeddings = []

    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]

        response = mistral_client.embeddings.create(
            model=EMBEDDING_MODEL,
            inputs=batch
        )

        batch_embeddings = [
            item.embedding
            for item in response.data
        ]

        all_embeddings.extend(batch_embeddings)

    return all_embeddings


def cosine_similarity(vector_a, vector_b):
    dot_product = sum(
        a * b
        for a, b in zip(vector_a, vector_b)
    )

    magnitude_a = math.sqrt(
        sum(a * a for a in vector_a)
    )

    magnitude_b = math.sqrt(
        sum(b * b for b in vector_b)
    )

    if magnitude_a == 0 or magnitude_b == 0:
        return 0

    return dot_product / (
        magnitude_a * magnitude_b
    )


def retrieve_pdf_chunks(mistral_client, pdf_data, query):
    chunks = pdf_data.get("chunks", [])
    embeddings = pdf_data.get("embeddings", [])

    if not chunks or not embeddings:
        return []

    query_response = mistral_client.embeddings.create(
        model=EMBEDDING_MODEL,
        inputs=[query]
    )

    query_embedding = query_response.data[0].embedding

    similarities = []

    for index, chunk_embedding in enumerate(embeddings):
        score = cosine_similarity(
            query_embedding,
            chunk_embedding
        )

        similarities.append({
            "index": index,
            "score": score
        })

    similarities.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    print("RAG similarity scores:")
    for result in similarities[:10]:
        print(round(result["score"], 3))

    relevant_chunks = []

    for result in similarities:
        if result["score"] < SIMILARITY_THRESHOLD:
            continue

        index = result["index"]
        chunk = chunks[index]

        relevant_chunks.append({
            "text": chunk["text"],
            "page": chunk["page"],
            "score": result["score"]
        })

        if len(relevant_chunks) >= TOP_K:
            break

    return relevant_chunks


def build_rag_context(mistral_client, pdf_data, query):
    relevant_chunks = retrieve_pdf_chunks(
        mistral_client,
        pdf_data,
        query
    )

    if not relevant_chunks:
        return "", []

    context = ""
    sources = []

    for index, chunk in enumerate(
        relevant_chunks,
        start=1
    ):
        context += f"""
        --- PDF Chunk {index} ---
        Page: {chunk["page"]}

        {chunk["text"]}
        """

        sources.append({
            "page": chunk["page"],
            "score": round(chunk["score"], 3)
        })

    return context, sources