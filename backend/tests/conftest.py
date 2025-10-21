"""
Shared test fixtures for RAG chatbot tests.
"""

import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from ai_generator import AIGenerator
from document_processor import DocumentProcessor
from rag_system import RAGSystem
from search_tools import CourseOutlineTool, CourseSearchTool, ToolManager
from session_manager import SessionManager
from vector_store import VectorStore


@dataclass
class TestConfig:
    """Test configuration that mirrors production config"""

    ANTHROPIC_API_KEY: str = "test-api-key"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_RESULTS: int = 5  # Note: production has 0, we use 5 for tests
    MAX_HISTORY: int = 2
    CHROMA_PATH: str = ""  # Will be set to temp directory


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration"""
    return TestConfig()


@pytest.fixture(scope="function")
def temp_chroma_dir():
    """Create a temporary ChromaDB directory for each test"""
    temp_dir = tempfile.mkdtemp(prefix="test_chroma_")
    yield temp_dir
    # Cleanup after test
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")
def test_vector_store(temp_chroma_dir, test_config):
    """Create a fresh vector store for each test with test documents loaded"""
    # Create vector store with temp directory
    vector_store = VectorStore(
        chroma_path=temp_chroma_dir,
        embedding_model=test_config.EMBEDDING_MODEL,
        max_results=test_config.MAX_RESULTS,
    )

    # Load test documents
    fixtures_dir = Path(__file__).parent / "fixtures"
    doc_processor = DocumentProcessor(
        chunk_size=test_config.CHUNK_SIZE, chunk_overlap=test_config.CHUNK_OVERLAP
    )

    # Process and add both test courses
    for test_file in ["test_course_1.txt", "test_course_2.txt"]:
        file_path = fixtures_dir / test_file
        if file_path.exists():
            course, chunks = doc_processor.process_course_document(str(file_path))
            vector_store.add_course_metadata(course)
            vector_store.add_course_content(chunks)

    return vector_store


@pytest.fixture(scope="function")
def test_search_tool(test_vector_store):
    """Create a CourseSearchTool with test vector store"""
    return CourseSearchTool(test_vector_store)


@pytest.fixture(scope="function")
def test_outline_tool(test_vector_store):
    """Create a CourseOutlineTool with test vector store"""
    return CourseOutlineTool(test_vector_store)


@pytest.fixture(scope="function")
def test_tool_manager(test_search_tool, test_outline_tool):
    """Create a ToolManager with test tools"""
    manager = ToolManager()
    manager.register_tool(test_search_tool)
    manager.register_tool(test_outline_tool)
    return manager


@pytest.fixture(scope="function")
def test_ai_generator(test_config):
    """Create an AIGenerator for testing"""
    return AIGenerator(
        api_key=test_config.ANTHROPIC_API_KEY, model=test_config.ANTHROPIC_MODEL
    )


@pytest.fixture(scope="function")
def test_session_manager(test_config):
    """Create a SessionManager for testing"""
    return SessionManager(max_history=test_config.MAX_HISTORY)


@pytest.fixture(scope="function")
def test_rag_system(temp_chroma_dir, test_config):
    """Create a complete RAG system for integration tests"""
    # Update config with temp directory
    test_config.CHROMA_PATH = temp_chroma_dir

    # Create RAG system
    rag_system = RAGSystem(test_config)

    # Load test documents
    fixtures_dir = Path(__file__).parent / "fixtures"
    for test_file in ["test_course_1.txt", "test_course_2.txt"]:
        file_path = fixtures_dir / test_file
        if file_path.exists():
            rag_system.add_course_document(str(file_path))

    return rag_system


@pytest.fixture
def sample_search_results():
    """Sample search results for testing formatting"""
    return {
        "documents": [
            ["Python is a high-level programming language known for its simplicity."],
            [
                "Control flow statements allow you to control the execution of your code."
            ],
        ],
        "metadatas": [
            [
                {
                    "course_title": "Introduction to Python Programming",
                    "lesson_number": 0,
                }
            ],
            [
                {
                    "course_title": "Introduction to Python Programming",
                    "lesson_number": 1,
                }
            ],
        ],
        "distances": [[0.1], [0.2]],
    }


# API Test Fixtures (for test_api.py)

from unittest.mock import Mock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient
from pydantic import BaseModel
from typing import List, Optional, Dict


@pytest.fixture
def mock_rag_system():
    """Provides a fully mocked RAG system for API testing."""
    mock = Mock()
    mock.query.return_value = (
        "Python is a high-level programming language.",
        [
            {"text": "Introduction to Python - Lesson 1", "url": "https://example.com/python/lesson1"}
        ],
    )
    mock.get_course_analytics.return_value = {
        "total_courses": 1,
        "course_titles": ["Introduction to Python"],
    }
    mock.session_manager = Mock()
    mock.session_manager.create_session.return_value = "test-session-id"
    return mock


@pytest.fixture
def test_app(mock_rag_system):
    """
    Provides a test FastAPI app without static file mounting.

    This avoids the issue where app.py tries to mount ../frontend
    which doesn't exist in the test environment.
    """
    # Create test app
    app = FastAPI(title="Course Materials RAG System - Test", root_path="")

    # Add CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Define request/response models (same as in app.py)
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Dict[str, Optional[str]]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    # Define endpoints inline (same as app.py but without static mounting)
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()

            answer, sources = mock_rag_system.query(request.query, session_id)

            return QueryResponse(
                answer=answer, sources=sources, session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def test_client(test_app):
    """Provides a synchronous test client for the FastAPI app."""
    return TestClient(test_app)


@pytest.fixture
async def async_test_client(test_app):
    """Provides an asynchronous test client for the FastAPI app."""
    from httpx import ASGITransport
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
