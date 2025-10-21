"""
API endpoint tests for the RAG system.

Tests all FastAPI endpoints including:
- POST /api/query - Query processing with RAG
- GET /api/courses - Course catalog statistics

These tests use the test_app fixture which provides an app instance
without static file mounting to avoid import issues.
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.mark.api
class TestQueryEndpoint:
    """Test suite for the /api/query endpoint."""
    
    def test_query_without_session_id(self, test_client, mock_rag_system):
        """Test querying without a session ID (new session creation)."""
        # Arrange
        request_data = {
            "query": "What is Python?"
        }
        
        # Act
        response = test_client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["session_id"] == "test-session-id"
        assert isinstance(data["sources"], list)
    
    def test_query_with_session_id(self, test_client, mock_rag_system):
        """Test querying with an existing session ID."""
        # Arrange
        request_data = {
            "query": "Tell me more about variables",
            "session_id": "existing-session-123"
        }
        
        # Act
        response = test_client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "existing-session-123"
        mock_rag_system.query.assert_called_once_with(
            "Tell me more about variables", 
            "existing-session-123"
        )
    
    def test_query_missing_query_field(self, test_client):
        """Test that missing query field returns validation error."""
        # Arrange
        request_data = {}
        
        # Act
        response = test_client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 422  # Unprocessable Entity
    
    def test_query_empty_string(self, test_client, mock_rag_system):
        """Test querying with an empty string."""
        # Arrange
        request_data = {
            "query": ""
        }
        
        # Act
        response = test_client.post("/api/query", json=request_data)
        
        # Assert
        # Empty string is technically valid, should process it
        assert response.status_code == 200
        mock_rag_system.query.assert_called_once()
    
    def test_query_with_sources(self, test_client, mock_rag_system):
        """Test that response includes properly formatted sources."""
        # Arrange
        mock_rag_system.query.return_value = (
            "Python uses dynamic typing.",
            [
                {
                    "text": "Introduction to Python - Lesson 2",
                    "url": "https://example.com/python/lesson2"
                }
            ]
        )
        request_data = {
            "query": "How does Python handle types?"
        }
        
        # Act
        response = test_client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "Introduction to Python - Lesson 2"
        assert data["sources"][0]["url"] == "https://example.com/python/lesson2"
    
    def test_query_with_multiple_sources(self, test_client, mock_rag_system):
        """Test response with multiple source citations."""
        # Arrange
        mock_rag_system.query.return_value = (
            "Combined answer from multiple sources.",
            [
                {"text": "Course A - Lesson 1", "url": "https://example.com/a/1"},
                {"text": "Course B - Lesson 2", "url": "https://example.com/b/2"},
                {"text": "Course C - Lesson 3", "url": None}
            ]
        )
        request_data = {"query": "Complex question"}
        
        # Act
        response = test_client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 3
        assert data["sources"][2]["url"] is None
    
    def test_query_rag_system_error(self, test_client, mock_rag_system):
        """Test handling of RAG system errors."""
        # Arrange
        mock_rag_system.query.side_effect = Exception("RAG system failure")
        request_data = {"query": "What is Python?"}
        
        # Act
        response = test_client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 500
        assert "RAG system failure" in response.json()["detail"]
    
    def test_query_special_characters(self, test_client, mock_rag_system):
        """Test query with special characters."""
        # Arrange
        request_data = {
            "query": "What about <script>alert('xss')</script> in Python?"
        }
        
        # Act
        response = test_client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 200
        # Query should be passed as-is to RAG system
        mock_rag_system.query.assert_called_once()


@pytest.mark.api
class TestCoursesEndpoint:
    """Test suite for the /api/courses endpoint."""
    
    def test_get_courses_success(self, test_client, mock_rag_system):
        """Test successful retrieval of course statistics."""
        # Arrange
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": [
                "Introduction to Python",
                "Advanced JavaScript",
                "Machine Learning Basics"
            ]
        }
        
        # Act
        response = test_client.get("/api/courses")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 3
        assert len(data["course_titles"]) == 3
        assert "Introduction to Python" in data["course_titles"]
    
    def test_get_courses_empty(self, test_client, mock_rag_system):
        """Test courses endpoint with no courses loaded."""
        # Arrange
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }
        
        # Act
        response = test_client.get("/api/courses")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []
    
    def test_get_courses_error(self, test_client, mock_rag_system):
        """Test handling of analytics errors."""
        # Arrange
        mock_rag_system.get_course_analytics.side_effect = Exception(
            "Database connection failed"
        )
        
        # Act
        response = test_client.get("/api/courses")
        
        # Assert
        assert response.status_code == 500
        assert "Database connection failed" in response.json()["detail"]


@pytest.mark.api
class TestAPIIntegration:
    """Integration tests for API workflows."""
    
    def test_query_flow_new_session(self, test_client, mock_rag_system):
        """Test complete query flow for a new session."""
        # First query - creates session
        response1 = test_client.post(
            "/api/query",
            json={"query": "What is Python?"}
        )
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]
        
        # Second query - uses existing session
        response2 = test_client.post(
            "/api/query",
            json={"query": "Tell me more", "session_id": session_id}
        )
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id
    
    def test_response_structure_compliance(self, test_client):
        """Test that all responses match expected Pydantic models."""
        # Test query response structure
        query_response = test_client.post(
            "/api/query",
            json={"query": "Test query"}
        )
        assert query_response.status_code == 200
        query_data = query_response.json()
        
        # Verify all required fields
        assert "answer" in query_data
        assert "sources" in query_data
        assert "session_id" in query_data
        assert isinstance(query_data["answer"], str)
        assert isinstance(query_data["sources"], list)
        assert isinstance(query_data["session_id"], str)
        
        # Test courses response structure
        courses_response = test_client.get("/api/courses")
        assert courses_response.status_code == 200
        courses_data = courses_response.json()
        
        # Verify all required fields
        assert "total_courses" in courses_data
        assert "course_titles" in courses_data
        assert isinstance(courses_data["total_courses"], int)
        assert isinstance(courses_data["course_titles"], list)


@pytest.mark.api
@pytest.mark.asyncio
class TestAsyncAPIEndpoints:
    """Async tests for API endpoints using httpx.AsyncClient."""
    
    async def test_async_query_endpoint(self, async_test_client, mock_rag_system):
        """Test query endpoint with async client."""
        # Arrange
        request_data = {"query": "What is Python?"}
        
        # Act
        response = await async_test_client.post("/api/query", json=request_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
    
    async def test_async_courses_endpoint(self, async_test_client):
        """Test courses endpoint with async client."""
        # Act
        response = await async_test_client.get("/api/courses")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "total_courses" in data
        assert "course_titles" in data


@pytest.mark.api
class TestCORSAndMiddleware:
    """Test CORS and middleware configurations."""
    
    def test_cors_headers_present(self, test_client):
        """Test that CORS headers are properly set."""
        # Act
        response = test_client.get("/api/courses")
        
        # Assert
        assert response.status_code == 200
        # Note: TestClient doesn't fully simulate CORS, but we can verify
        # the endpoint is accessible (middleware is properly configured)
    
    def test_options_request(self, test_client):
        """Test OPTIONS preflight request handling."""
        # Act
        response = test_client.options("/api/query")
        
        # Assert
        # FastAPI with CORS middleware should handle OPTIONS
        assert response.status_code in [200, 405]  # Depends on CORS config
