"""
Tests for CourseSearchTool.execute() method and related functionality.
"""

import pytest
from search_tools import CourseSearchTool
from vector_store import SearchResults


class TestCourseSearchToolExecute:
    """Test suite for CourseSearchTool.execute() method"""

    def test_search_with_results(self, test_search_tool):
        """Test that search returns results for valid query"""
        result = test_search_tool.execute(query="Python programming language")

        # Should return formatted results, not error
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain course context in brackets
        assert "[Introduction to Python Programming" in result
        # Should not be an error message
        assert "No relevant content found" not in result
        assert "error" not in result.lower()

    def test_search_with_course_filter(self, test_search_tool):
        """Test searching with course name filter"""
        result = test_search_tool.execute(
            query="linear regression", course_name="Machine Learning"
        )

        # Should return results from ML course only
        assert result is not None
        assert "Machine Learning Fundamentals" in result
        # Should not include Python course content
        assert "Python Programming" not in result

    def test_search_with_lesson_filter(self, test_search_tool):
        """Test searching with lesson number filter"""
        result = test_search_tool.execute(
            query="data structures", course_name="Python", lesson_number=2
        )

        # Should return results
        assert result is not None
        assert "Lesson 2" in result

    def test_search_fuzzy_course_matching(self, test_search_tool):
        """Test that partial course names work via semantic matching"""
        # Search with just "Python" should match "Introduction to Python Programming"
        result = test_search_tool.execute(query="variables", course_name="Python")

        assert result is not None
        assert "Introduction to Python Programming" in result

    def test_search_empty_results(self, test_search_tool):
        """Test behavior when no results are found"""
        result = test_search_tool.execute(
            query="quantum mechanics differential equations"
        )

        # Should return appropriate message for no results
        assert result is not None
        assert "No relevant content found" in result

    def test_search_nonexistent_course(self, test_search_tool):
        """Test searching for a course that doesn't exist"""
        result = test_search_tool.execute(
            query="test query", course_name="Nonexistent Course About Unicorns"
        )

        # Should return error about course not found
        assert result is not None
        assert "No course found matching" in result

    def test_search_invalid_lesson_number(self, test_search_tool):
        """Test searching with lesson number that doesn't exist"""
        result = test_search_tool.execute(
            query="test query", course_name="Python", lesson_number=999
        )

        # Should return no results found for that lesson
        assert result is not None
        # Either returns "No relevant content found" or actual empty result
        assert "No relevant content found" in result or len(result) == 0

    def test_result_formatting(self, test_search_tool):
        """Test that results are properly formatted with course and lesson info"""
        result = test_search_tool.execute(query="Python syntax")

        # Should have proper format: [Course - Lesson X]\ncontent
        assert "[Introduction to Python Programming" in result
        assert "Lesson" in result
        assert result.count("[") > 0  # At least one header
        assert result.count("]") > 0

    def test_source_tracking(self, test_search_tool):
        """Test that sources are properly tracked after search"""
        # Clear any previous sources
        test_search_tool.last_sources = []

        # Execute search
        result = test_search_tool.execute(query="Python programming")

        # Check sources were recorded
        assert len(test_search_tool.last_sources) > 0
        # Each source should be a dict with 'text' and 'url' keys
        for source in test_search_tool.last_sources:
            assert isinstance(source, dict)
            assert "text" in source
            assert "url" in source

    def test_source_text_format(self, test_search_tool):
        """Test that source text is properly formatted"""
        test_search_tool.last_sources = []
        result = test_search_tool.execute(query="control flow", course_name="Python")

        # Sources should include course name and lesson number
        assert len(test_search_tool.last_sources) > 0
        source_text = test_search_tool.last_sources[0]["text"]
        assert "Introduction to Python Programming" in source_text
        # Should have lesson number
        assert "Lesson" in source_text

    def test_source_url_extraction(self, test_search_tool):
        """Test that URLs are extracted from course metadata"""
        test_search_tool.last_sources = []
        result = test_search_tool.execute(query="Python basics")

        # Should have URLs
        assert len(test_search_tool.last_sources) > 0
        url = test_search_tool.last_sources[0]["url"]
        # URL should be present and valid
        assert url is not None
        assert url.startswith("http")

    def test_multiple_results_formatting(self, test_search_tool):
        """Test that multiple results are properly separated"""
        result = test_search_tool.execute(query="programming")

        # Should have multiple results separated by blank lines
        assert result.count("\n\n") >= 1  # At least one separator
        # Each result should have a header
        headers = result.count("[")
        assert headers >= 1

    def test_query_required(self, test_search_tool):
        """Test that query parameter is required"""
        # This should raise an error since query is required
        with pytest.raises(TypeError):
            test_search_tool.execute()

    def test_sources_reset_between_searches(self, test_search_tool):
        """Test that sources are properly updated for each new search"""
        # First search
        result1 = test_search_tool.execute(query="Python")
        sources1_count = len(test_search_tool.last_sources)

        # Second search
        result2 = test_search_tool.execute(query="machine learning")
        sources2_count = len(test_search_tool.last_sources)

        # Sources should be different (new search replaces old sources)
        assert sources2_count > 0
        # Verify sources contain ML content
        assert any(
            "Machine Learning" in s["text"] for s in test_search_tool.last_sources
        )


class TestSearchResultsDataclass:
    """Test the SearchResults dataclass functionality"""

    def test_from_chroma(self, sample_search_results):
        """Test creating SearchResults from ChromaDB results"""
        results = SearchResults.from_chroma(sample_search_results)

        assert len(results.documents) == 1
        assert len(results.metadata) == 1
        assert len(results.distances) == 1
        assert results.error is None

    def test_empty_results(self):
        """Test creating empty results with error"""
        results = SearchResults.empty("Test error message")

        assert len(results.documents) == 0
        assert results.is_empty()
        assert results.error == "Test error message"

    def test_is_empty(self):
        """Test is_empty method"""
        empty = SearchResults(documents=[], metadata=[], distances=[])
        non_empty = SearchResults(
            documents=["test"], metadata=[{"test": "meta"}], distances=[0.5]
        )

        assert empty.is_empty()
        assert not non_empty.is_empty()
