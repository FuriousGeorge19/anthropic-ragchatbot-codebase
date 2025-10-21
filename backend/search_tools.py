from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol

from vector_store import SearchResults, VectorStore


class Tool(ABC):
    """Abstract base class for all tools"""

    @abstractmethod
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given parameters"""
        pass


class CourseSearchTool(Tool):
    """Tool for searching course content with semantic course name matching"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last search

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "search_course_content",
            "description": "Search course materials with smart course name matching and lesson filtering",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in the course content",
                    },
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work, e.g. 'MCP', 'Introduction')",
                    },
                    "lesson_number": {
                        "type": "integer",
                        "description": "Specific lesson number to search within (e.g. 1, 2, 3)",
                    },
                },
                "required": ["query"],
            },
        }

    def execute(
        self,
        query: str,
        course_name: Optional[str] = None,
        lesson_number: Optional[int] = None,
    ) -> str:
        """
        Execute the search tool with given parameters.

        Args:
            query: What to search for
            course_name: Optional course filter
            lesson_number: Optional lesson filter

        Returns:
            Formatted search results or error message
        """

        # Use the vector store's unified search interface
        results = self.store.search(
            query=query, course_name=course_name, lesson_number=lesson_number
        )

        # Handle errors
        if results.error:
            return results.error

        # Handle empty results
        if results.is_empty():
            filter_info = ""
            if course_name:
                filter_info += f" in course '{course_name}'"
            if lesson_number:
                filter_info += f" in lesson {lesson_number}"
            return f"No relevant content found{filter_info}."

        # Format and return results
        return self._format_results(results)

    def _format_results(self, results: SearchResults) -> str:
        """Format search results with course and lesson context"""
        formatted = []
        sources = []  # Track sources for the UI

        for doc, meta in zip(results.documents, results.metadata):
            course_title = meta.get("course_title", "unknown")
            lesson_num = meta.get("lesson_number")

            # Build context header
            header = f"[{course_title}"
            if lesson_num is not None:
                header += f" - Lesson {lesson_num}"
            header += "]"

            # Build source with text and URL
            source_text = course_title
            if lesson_num is not None:
                source_text += f" - Lesson {lesson_num}"

            # Get URL from vector store
            url = None
            if lesson_num is not None:
                url = self.store.get_lesson_link(course_title, lesson_num)
            if not url:  # Fallback to course link if no lesson link
                url = self.store.get_course_link(course_title)

            # Create source object with text and URL
            source = {"text": source_text, "url": url}
            sources.append(source)

            formatted.append(f"{header}\n{doc}")

        # Store sources for retrieval
        self.last_sources = sources

        return "\n\n".join(formatted)


class CourseOutlineTool(Tool):
    """Tool for retrieving course outlines with title, link, and lesson information"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last query

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "get_course_outline",
            "description": "Get course outline including course title, course link, and complete lesson list with numbers and titles. Use this for questions about course structure, outlines, or what lessons are covered.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "course_name": {
                        "type": "string",
                        "description": "Course title to get outline for (partial matches work, e.g. 'MCP', 'Python'). If omitted, returns all available courses.",
                    }
                },
                "required": [],
            },
        }

    def execute(self, course_name: Optional[str] = None) -> str:
        """
        Execute the course outline tool.

        Args:
            course_name: Optional course name to get outline for. If None, returns all courses.

        Returns:
            Formatted course outline(s) or error message
        """
        # Reset sources
        self.last_sources = []

        if course_name:
            # Get outline for specific course
            return self._get_single_course_outline(course_name)
        else:
            # Get all course outlines
            return self._get_all_course_outlines()

    def _get_single_course_outline(self, course_name: str) -> str:
        """Get outline for a single course"""
        # Resolve course name using semantic matching
        resolved_title = self.store._resolve_course_name(course_name)

        if not resolved_title:
            return f"No course found matching '{course_name}'"

        # Get course metadata
        metadata = self.store.get_course_metadata(resolved_title)

        if not metadata:
            return f"Could not retrieve outline for course '{resolved_title}'"

        # Format the outline
        return self._format_course_outline(metadata)

    def _get_all_course_outlines(self) -> str:
        """Get outlines for all courses"""
        all_metadata = self.store.get_all_courses_metadata()

        if not all_metadata:
            return "No courses found in the database"

        # Format all course outlines
        formatted_outlines = []
        for metadata in all_metadata:
            formatted_outlines.append(self._format_course_outline(metadata))

        return "\n\n---\n\n".join(formatted_outlines)

    def _format_course_outline(self, metadata: Dict[str, Any]) -> str:
        """Format a single course outline with all details"""
        title = metadata.get("title", "Unknown Course")
        course_link = metadata.get("course_link")
        instructor = metadata.get("instructor")
        lessons = metadata.get("lessons", [])

        # Build formatted output
        output_lines = [f"Course: {title}"]

        if course_link:
            output_lines.append(f"Course Link: {course_link}")
            # Add to sources for UI
            self.last_sources.append({"text": title, "url": course_link})
        else:
            # Add to sources without URL
            self.last_sources.append({"text": title, "url": None})

        if instructor:
            output_lines.append(f"Instructor: {instructor}")

        # Add lesson list
        if lessons:
            output_lines.append(f"\nLessons ({len(lessons)}):")
            for lesson in lessons:
                lesson_num = lesson.get("lesson_number")
                lesson_title = lesson.get("lesson_title", "Untitled")
                output_lines.append(f"  Lesson {lesson_num}: {lesson_title}")
        else:
            output_lines.append("\nNo lesson information available")

        return "\n".join(output_lines)


class ToolManager:
    """Manages available tools for the AI"""

    def __init__(self):
        self.tools = {}

    def register_tool(self, tool: Tool):
        """Register any tool that implements the Tool interface"""
        tool_def = tool.get_tool_definition()
        tool_name = tool_def.get("name")
        if not tool_name:
            raise ValueError("Tool must have a 'name' in its definition")
        self.tools[tool_name] = tool

    def get_tool_definitions(self) -> list:
        """Get all tool definitions for Anthropic tool calling"""
        return [tool.get_tool_definition() for tool in self.tools.values()]

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name with given parameters"""
        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not found"

        return self.tools[tool_name].execute(**kwargs)

    def get_last_sources(self) -> list:
        """Get sources from the last search operation"""
        # Check all tools for last_sources attribute
        for tool in self.tools.values():
            if hasattr(tool, "last_sources") and tool.last_sources:
                return tool.last_sources
        return []

    def reset_sources(self):
        """Reset sources from all tools that track sources"""
        for tool in self.tools.values():
            if hasattr(tool, "last_sources"):
                tool.last_sources = []
