"""
Integration tests for the complete RAG system.
Tests the end-to-end flow of queries through the system.
"""

from unittest.mock import Mock, patch

import pytest

from .test_ai_generator import MockAnthropicResponse, MockTextBlock, MockToolUseBlock


class TestRAGSystemIntegration:
    """End-to-end integration tests for RAG system"""

    def test_query_with_content_search(self, test_rag_system):
        """Test complete query flow that uses content search"""
        # Mock Anthropic API responses
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content",
                    tool_input={"query": "Python syntax"},
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            content=[MockTextBlock("Python uses indentation to define code blocks.")]
        )

        with patch.object(
            test_rag_system.ai_generator.client.messages, "create"
        ) as mock_create:
            mock_create.side_effect = [tool_use_response, final_response]

            # Execute query
            answer, sources = test_rag_system.query("What is Python syntax?")

            # Should return an answer
            assert answer is not None
            assert len(answer) > 0
            assert "Python" in answer

            # Should have sources
            assert len(sources) > 0
            assert isinstance(sources, list)
            # Each source should be a dict
            for source in sources:
                assert isinstance(source, dict)
                assert "text" in source
                assert "url" in source

    def test_query_with_course_outline(self, test_rag_system):
        """Test query that should use course outline tool"""
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="get_course_outline", tool_input={"course_name": "Python"}
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            content=[
                MockTextBlock(
                    "The Python course has 3 lessons covering basics, control flow, and data structures."
                )
            ]
        )

        with patch.object(
            test_rag_system.ai_generator.client.messages, "create"
        ) as mock_create:
            mock_create.side_effect = [tool_use_response, final_response]

            answer, sources = test_rag_system.query(
                "What lessons are in the Python course?"
            )

            assert answer is not None
            assert "lessons" in answer.lower() or "lesson" in answer.lower()

    def test_session_creation(self, test_rag_system):
        """Test that session is created for new query"""
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content", tool_input={"query": "test"}
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(content=[MockTextBlock("Test response")])

        with patch.object(
            test_rag_system.ai_generator.client.messages, "create"
        ) as mock_create:
            mock_create.side_effect = [tool_use_response, final_response]

            # Query without session_id
            answer, sources = test_rag_system.query("Test query", session_id=None)

            # Should still work and create session implicitly through session manager
            assert answer is not None

    def test_conversation_history(self, test_rag_system):
        """Test that conversation history is maintained across queries"""
        # Create a session
        session_id = test_rag_system.session_manager.create_session()

        # Mock responses for both queries
        mock_responses = [
            MockAnthropicResponse(
                content=[
                    MockToolUseBlock("search_course_content", {"query": "Python"})
                ],
                stop_reason="tool_use",
            ),
            MockAnthropicResponse(
                content=[MockTextBlock("Python is a programming language.")]
            ),
            MockAnthropicResponse(
                content=[MockTextBlock("Yes, Python is beginner-friendly.")]
            ),
        ]

        with patch.object(
            test_rag_system.ai_generator.client.messages, "create"
        ) as mock_create:
            mock_create.side_effect = mock_responses

            # First query
            answer1, _ = test_rag_system.query("What is Python?", session_id=session_id)

            # Second query (follow-up)
            answer2, _ = test_rag_system.query(
                "Is it beginner-friendly?", session_id=session_id
            )

            # Both should have answers
            assert answer1 is not None
            assert answer2 is not None

            # History should be stored in session
            history = test_rag_system.session_manager.get_conversation_history(
                session_id
            )
            assert history is not None
            assert len(history) > 0

    def test_source_tracking_and_reset(self, test_rag_system):
        """Test that sources are tracked and reset between queries"""
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content", tool_input={"query": "Python"}
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(content=[MockTextBlock("Answer")])

        with patch.object(
            test_rag_system.ai_generator.client.messages, "create"
        ) as mock_create:
            # First query
            mock_create.side_effect = [tool_use_response, final_response]
            answer1, sources1 = test_rag_system.query("Query 1")

            # Second query
            mock_create.side_effect = [tool_use_response, final_response]
            answer2, sources2 = test_rag_system.query("Query 2")

            # Both should have sources
            assert len(sources1) > 0
            assert len(sources2) > 0

    def test_query_with_course_filter(self, test_rag_system):
        """Test query that should filter by course name"""
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content",
                    tool_input={
                        "query": "regression",
                        "course_name": "Machine Learning",
                    },
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            content=[MockTextBlock("Linear regression is used for prediction.")]
        )

        with patch.object(
            test_rag_system.ai_generator.client.messages, "create"
        ) as mock_create:
            mock_create.side_effect = [tool_use_response, final_response]

            answer, sources = test_rag_system.query(
                "What does the ML course say about regression?"
            )

            assert answer is not None
            assert len(sources) > 0

    def test_empty_results_handling(self, test_rag_system):
        """Test how system handles queries with no relevant content"""
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content",
                    tool_input={"query": "quantum physics black holes"},
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            content=[
                MockTextBlock(
                    "I couldn't find relevant content about that topic in the available courses."
                )
            ]
        )

        with patch.object(
            test_rag_system.ai_generator.client.messages, "create"
        ) as mock_create:
            mock_create.side_effect = [tool_use_response, final_response]

            answer, sources = test_rag_system.query("Tell me about quantum physics")

            # Should still return an answer (even if it says content not found)
            assert answer is not None
            # Sources might be empty for irrelevant queries
            assert isinstance(sources, list)

    def test_multiple_courses_in_database(self, test_rag_system):
        """Test that system can search across multiple courses"""
        analytics = test_rag_system.get_course_analytics()

        # Should have loaded both test courses
        assert analytics["total_courses"] == 2
        assert len(analytics["course_titles"]) == 2

        # Should have both Python and ML courses
        course_titles = analytics["course_titles"]
        assert any("Python" in title for title in course_titles)
        assert any("Machine Learning" in title for title in course_titles)


class TestVectorStoreIntegration:
    """Integration tests for vector store with real ChromaDB"""

    def test_course_catalog_search(self, test_vector_store):
        """Test searching the course catalog"""
        # Should be able to find courses by name
        result = test_vector_store._resolve_course_name("Python")
        assert result is not None
        assert "Python" in result

    def test_content_search_no_filters(self, test_vector_store):
        """Test searching content without filters"""
        results = test_vector_store.search(query="programming language")

        assert not results.is_empty()
        assert len(results.documents) > 0
        assert len(results.metadata) > 0

    def test_content_search_with_course_filter(self, test_vector_store):
        """Test searching with course name filter"""
        results = test_vector_store.search(
            query="regression", course_name="Machine Learning"
        )

        # Should return results from ML course only
        assert not results.is_empty()
        for meta in results.metadata:
            assert "Machine Learning" in meta["course_title"]

    def test_content_search_with_lesson_filter(self, test_vector_store):
        """Test searching with lesson number filter"""
        results = test_vector_store.search(
            query="data structures", course_name="Python", lesson_number=2
        )

        # Should return results from lesson 2 only
        if not results.is_empty():
            for meta in results.metadata:
                assert meta["lesson_number"] == 2

    def test_get_course_metadata(self, test_vector_store):
        """Test retrieving course metadata"""
        metadata = test_vector_store.get_course_metadata(
            "Introduction to Python Programming"
        )

        assert metadata is not None
        assert metadata["title"] == "Introduction to Python Programming"
        assert "lessons" in metadata
        assert len(metadata["lessons"]) == 3  # Our test course has 3 lessons

    def test_get_all_courses_metadata(self, test_vector_store):
        """Test retrieving all courses metadata"""
        all_metadata = test_vector_store.get_all_courses_metadata()

        assert len(all_metadata) == 2  # We loaded 2 test courses
        # Each should have lessons
        for course_meta in all_metadata:
            assert "title" in course_meta
            assert "lessons" in course_meta
            assert len(course_meta["lessons"]) > 0

    def test_get_course_link(self, test_vector_store):
        """Test retrieving course link"""
        link = test_vector_store.get_course_link("Introduction to Python Programming")

        assert link is not None
        assert link.startswith("http")

    def test_get_lesson_link(self, test_vector_store):
        """Test retrieving lesson link"""
        link = test_vector_store.get_lesson_link(
            "Introduction to Python Programming", 0
        )

        assert link is not None
        assert link.startswith("http")


class TestDocumentProcessing:
    """Integration tests for document processing pipeline"""

    def test_add_course_document(self, test_rag_system):
        """Test adding a course document to the system"""
        from pathlib import Path

        # Get path to test course
        test_file = Path(__file__).parent / "fixtures" / "test_course_1.txt"

        # Add course (note: might already be loaded by fixture)
        course, chunk_count = test_rag_system.add_course_document(str(test_file))

        # Should successfully process
        assert course is not None
        assert course.title == "Introduction to Python Programming"
        assert chunk_count > 0

    def test_duplicate_course_handling(self, test_rag_system):
        """Test that duplicate courses are properly handled"""
        # Courses are already loaded by fixture
        initial_count = test_rag_system.vector_store.get_course_count()

        # Try to add same courses again via folder
        from pathlib import Path

        fixtures_dir = Path(__file__).parent / "fixtures"

        courses_added, chunks_added = test_rag_system.add_course_folder(
            str(fixtures_dir), clear_existing=False
        )

        # Should not add duplicates
        final_count = test_rag_system.vector_store.get_course_count()
        assert final_count == initial_count


class TestSessionManager:
    """Integration tests for session management"""

    def test_create_and_retrieve_session(self, test_session_manager):
        """Test creating and retrieving a session"""
        session_id = test_session_manager.create_session()

        assert session_id is not None
        assert len(session_id) > 0

    def test_add_exchange_to_session(self, test_session_manager):
        """Test adding conversation exchanges to session"""
        session_id = test_session_manager.create_session()

        test_session_manager.add_exchange(session_id, "Question 1", "Answer 1")
        test_session_manager.add_exchange(session_id, "Question 2", "Answer 2")

        history = test_session_manager.get_conversation_history(session_id)

        assert history is not None
        assert "Question 1" in history
        assert "Answer 1" in history

    def test_history_limit(self, test_session_manager):
        """Test that history respects max_history limit"""
        session_id = test_session_manager.create_session()

        # Add more exchanges than the limit
        for i in range(5):
            test_session_manager.add_exchange(
                session_id, f"Question {i}", f"Answer {i}"
            )

        history = test_session_manager.get_conversation_history(session_id)

        # History should only contain last MAX_HISTORY exchanges (2 in our config)
        # So we should see Question 3, 4 but not 0, 1, 2
        assert "Question 3" in history or "Question 4" in history
        assert "Question 0" not in history
