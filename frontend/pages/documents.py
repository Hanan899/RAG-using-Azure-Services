"""Documents page for uploads, metrics, and document management."""

from __future__ import annotations

import os
import streamlit as st
from dotenv import load_dotenv

from utils.api_client import ApiClientError, delete_document, list_documents, upload_document
from utils.ui import inject_global_styles, render_page_header, render_sidebar_nav
from utils.view_models import build_document_stats

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "https://ragchatbotbackend.azurewebsites.net")

st.set_page_config(page_title="Documents · RAG Chatbot", layout="wide")
inject_global_styles()
render_sidebar_nav("Documents")

render_page_header(
    "Documents",
    "Upload files and review indexing coverage across chunks.",
)

st.subheader("Upload")
file = st.file_uploader(
    "Upload a document", type=["pdf", "txt", "docx"], accept_multiple_files=False
)
if st.button("Upload", type="primary", disabled=file is None):
    try:
        with st.spinner("Uploading document..."):
            response = upload_document(BACKEND_URL, file.name, file.getvalue())
        st.success(f"Uploaded {response.get('filename', file.name)}")
    except ApiClientError:
        st.error("Upload failed. Check backend logs and file format.")

st.divider()

st.subheader("Indexed Coverage")
try:
    docs_response = list_documents(BACKEND_URL)
    documents = docs_response.get("documents", [])
    stats = build_document_stats(
        documents,
        file_count=docs_response.get("file_count"),
        chunk_count=docs_response.get("chunk_count"),
    )
except ApiClientError:
    documents = []
    stats = build_document_stats([])
    st.warning("Unable to fetch documents.")

metric_cols = st.columns(2)
metric_cols[0].metric("Files", stats["file_count"])
metric_cols[1].metric("Chunks", stats["chunk_count"])

if stats["chart_data"]:
    st.vega_lite_chart(
        stats["chart_data"],
        {
            "mark": {"type": "bar", "cornerRadius": 6},
            "encoding": {
                "x": {"field": "title", "type": "nominal", "sort": "-y"},
                "y": {"field": "chunk_count", "type": "quantitative"},
                "tooltip": [{"field": "title"}, {"field": "chunk_count"}],
            },
            "height": 220,
        },
        use_container_width=True,
    )
else:
    st.info("No documents indexed yet.")

st.divider()
st.subheader("Documents")

if documents:
    for doc in documents:
        doc_id = doc.get("id") or (doc.get("metadata") or {}).get("id")
        title = doc.get("title") or doc_id or "Document"
        chunk_meta = (doc.get("metadata") or {}).get("chunk_count") or 0
        cols = st.columns([6, 2])
        cols[0].markdown(
            f"**{title}**  \nChunks: {chunk_meta}",
        )
        if doc_id and cols[1].button("Remove", key=f"delete-{doc_id}"):
            try:
                delete_document(BACKEND_URL, doc_id)
                st.success("Deleted document")
            except ApiClientError:
                st.error("Delete failed")
else:
    st.caption("No documents indexed yet.")
