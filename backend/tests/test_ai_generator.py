"""
Tests for AIGenerator and its interaction with ToolManager.
Tests verify that the AI correctly calls tools and processes results.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from ai_generator import AIGenerator


class MockAnthropicResponse:
    """Mock response from Anthropic API"""

    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class MockToolUseBlock:
    """Mock tool use content block"""

    def __init__(self, tool_name, tool_input, tool_id="test-tool-id"):
        self.type = "tool_use"
        self.name = tool_name
        self.input = tool_input
        self.id = tool_id


class MockTextBlock:
    """Mock text content block"""

    def __init__(self, text):
        self.type = "text"
        self.text = text


class TestAIGeneratorToolCalling:
    """Test suite for AIGenerator's tool calling functionality"""

    def test_generate_response_without_tools(self, test_ai_generator):
        """Test generating response without any tools available"""
        # Mock the API response
        mock_response = MockAnthropicResponse(
            [MockTextBlock("This is a test response")]
        )

        with patch.object(
            test_ai_generator.client.messages, "create", return_value=mock_response
        ):
            response = test_ai_generator.generate_response(
                query="What is Python?", tools=None, tool_manager=None
            )

            assert response == "This is a test response"

    def test_generate_response_with_tools_not_used(
        self, test_ai_generator, test_tool_manager
    ):
        """Test when tools are available but Claude doesn't use them"""
        mock_response = MockAnthropicResponse(
            [MockTextBlock("Direct answer without tool use")]
        )

        with patch.object(
            test_ai_generator.client.messages, "create", return_value=mock_response
        ):
            response = test_ai_generator.generate_response(
                query="What is 2+2?",
                tools=test_tool_manager.get_tool_definitions(),
                tool_manager=test_tool_manager,
            )

            assert response == "Direct answer without tool use"

    def test_tool_execution_loop(self, test_ai_generator, test_tool_manager):
        """Test the complete tool execution loop"""
        # First response: Claude wants to use a tool
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content",
                    tool_input={"query": "Python basics"},
                )
            ],
            stop_reason="tool_use",
        )

        # Second response: Claude's final answer after tool execution
        final_response = MockAnthropicResponse(
            content=[
                MockTextBlock(
                    "Based on the course content, Python is a programming language."
                )
            ]
        )

        with patch.object(test_ai_generator.client.messages, "create") as mock_create:
            # Set up the mock to return different responses on consecutive calls
            mock_create.side_effect = [tool_use_response, final_response]

            response = test_ai_generator.generate_response(
                query="What is Python?",
                tools=test_tool_manager.get_tool_definitions(),
                tool_manager=test_tool_manager,
            )

            # Should return the final synthesized answer
            assert "Python is a programming language" in response
            # API should be called twice: once for tool use, once for final answer
            assert mock_create.call_count == 2

    def test_tool_manager_execute_called(self, test_ai_generator, test_tool_manager):
        """Test that tool_manager.execute_tool is called correctly"""
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content",
                    tool_input={"query": "machine learning", "course_name": "ML"},
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(content=[MockTextBlock("Final answer")])

        with patch.object(test_ai_generator.client.messages, "create") as mock_create:
            mock_create.side_effect = [tool_use_response, final_response]

            # Mock the tool_manager's execute_tool method to verify it's called
            with patch.object(
                test_tool_manager, "execute_tool", return_value="Tool result"
            ) as mock_execute:
                response = test_ai_generator.generate_response(
                    query="Tell me about ML",
                    tools=test_tool_manager.get_tool_definitions(),
                    tool_manager=test_tool_manager,
                )

                # Verify execute_tool was called with correct parameters
                mock_execute.assert_called_once_with(
                    "search_course_content", query="machine learning", course_name="ML"
                )

    def test_conversation_history_included(self, test_ai_generator):
        """Test that conversation history is properly included in API call"""
        mock_response = MockAnthropicResponse([MockTextBlock("Response with history")])

        with patch.object(test_ai_generator.client.messages, "create") as mock_create:
            mock_create.return_value = mock_response

            history = "User: Previous question\nAssistant: Previous answer"
            response = test_ai_generator.generate_response(
                query="Current question",
                conversation_history=history,
                tools=None,
                tool_manager=None,
            )

            # Verify system prompt includes history
            call_kwargs = mock_create.call_args[1]
            assert "Previous conversation" in call_kwargs["system"]
            assert history in call_kwargs["system"]

    def test_multiple_tool_calls(self, test_ai_generator, test_tool_manager):
        """Test handling multiple tool calls in one response"""
        # Response with two tool calls
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content",
                    tool_input={"query": "Python"},
                    tool_id="tool-1",
                ),
                MockToolUseBlock(
                    tool_name="search_course_content",
                    tool_input={"query": "ML"},
                    tool_id="tool-2",
                ),
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            content=[MockTextBlock("Combined answer from both searches")]
        )

        with patch.object(test_ai_generator.client.messages, "create") as mock_create:
            mock_create.side_effect = [tool_use_response, final_response]

            with patch.object(
                test_tool_manager, "execute_tool", return_value="Tool result"
            ) as mock_execute:
                response = test_ai_generator.generate_response(
                    query="Compare Python and ML",
                    tools=test_tool_manager.get_tool_definitions(),
                    tool_manager=test_tool_manager,
                )

                # Both tools should be executed
                assert mock_execute.call_count == 2
                assert "Combined answer from both searches" in response

    def test_tool_definitions_format(self, test_tool_manager):
        """Test that tool definitions are in correct format for Anthropic API"""
        tool_defs = test_tool_manager.get_tool_definitions()

        # Should have at least the search tool
        assert len(tool_defs) > 0

        # Each tool should have required fields
        for tool_def in tool_defs:
            assert "name" in tool_def
            assert "description" in tool_def
            assert "input_schema" in tool_def
            # input_schema should have required Anthropic format
            assert tool_def["input_schema"]["type"] == "object"
            assert "properties" in tool_def["input_schema"]
            assert "required" in tool_def["input_schema"]

    def test_api_parameters(self, test_ai_generator):
        """Test that API is called with correct parameters"""
        mock_response = MockAnthropicResponse([MockTextBlock("Test")])

        with patch.object(test_ai_generator.client.messages, "create") as mock_create:
            mock_create.return_value = mock_response

            test_ai_generator.generate_response(
                query="Test query", tools=None, tool_manager=None
            )

            # Verify API call parameters
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["model"] == test_ai_generator.model
            assert call_kwargs["temperature"] == 0
            assert call_kwargs["max_tokens"] == 800
            assert "messages" in call_kwargs
            assert len(call_kwargs["messages"]) == 1
            assert call_kwargs["messages"][0]["role"] == "user"

    def test_tool_choice_auto_when_tools_provided(
        self, test_ai_generator, test_tool_manager
    ):
        """Test that tool_choice is set to auto when tools are available"""
        mock_response = MockAnthropicResponse([MockTextBlock("Test")])

        with patch.object(test_ai_generator.client.messages, "create") as mock_create:
            mock_create.return_value = mock_response

            test_ai_generator.generate_response(
                query="Test query",
                tools=test_tool_manager.get_tool_definitions(),
                tool_manager=test_tool_manager,
            )

            # Verify tool_choice is set
            call_kwargs = mock_create.call_args[1]
            assert "tool_choice" in call_kwargs
            assert call_kwargs["tool_choice"] == {"type": "auto"}


class TestSequentialToolCalling:
    """Test suite for sequential tool calling functionality (up to 2 rounds)"""

    def test_two_sequential_tool_calls(self, test_ai_generator, test_tool_manager):
        """Test that Claude can make 2 sequential tool calls"""
        # Round 1: Claude uses first tool
        tool_use_response_1 = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content",
                    tool_input={"query": "Python basics"},
                    tool_id="tool-1",
                )
            ],
            stop_reason="tool_use",
        )

        # Round 2: Claude uses second tool based on first result
        tool_use_response_2 = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="get_course_outline",
                    tool_input={"course_name": "Python"},
                    tool_id="tool-2",
                )
            ],
            stop_reason="tool_use",
        )

        # Final: Claude provides synthesized answer
        final_response = MockAnthropicResponse(
            content=[MockTextBlock("Based on both searches, here's the answer...")]
        )

        with patch.object(test_ai_generator.client.messages, "create") as mock_create:
            # Set up responses for 3 API calls
            mock_create.side_effect = [
                tool_use_response_1,
                tool_use_response_2,
                final_response,
            ]

            response = test_ai_generator.generate_response(
                query="What does Python course cover?",
                tools=test_tool_manager.get_tool_definitions(),
                tool_manager=test_tool_manager,
            )

            # Should make 3 API calls total (2 tool rounds + 1 final)
            assert mock_create.call_count == 3
            assert "Based on both searches" in response

    def test_max_rounds_enforced(self, test_ai_generator, test_tool_manager):
        """Test that after 2 rounds, a final call is made without tools"""
        # Both rounds return tool_use
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content", tool_input={"query": "test"}
                )
            ],
            stop_reason="tool_use",
        )

        # Final response after max rounds
        final_response = MockAnthropicResponse(
            content=[MockTextBlock("Final answer after max rounds")]
        )

        with patch.object(test_ai_generator.client.messages, "create") as mock_create:
            # Return tool_use twice, then final response
            mock_create.side_effect = [
                tool_use_response,
                tool_use_response,
                final_response,
            ]

            response = test_ai_generator.generate_response(
                query="Complex query",
                tools=test_tool_manager.get_tool_definitions(),
                tool_manager=test_tool_manager,
            )

            # Should make exactly 3 API calls (max 2 rounds + final)
            assert mock_create.call_count == 3

            # Verify third call has NO tools parameter
            third_call_kwargs = mock_create.call_args_list[2][1]
            assert "tools" not in third_call_kwargs
            assert "Final answer after max rounds" in response

    def test_early_exit_after_one_tool_call(self, test_ai_generator, test_tool_manager):
        """Test that if Claude doesn't use tools in round 2, we exit early"""
        # Round 1: Tool use
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content", tool_input={"query": "Python"}
                )
            ],
            stop_reason="tool_use",
        )

        # Round 2: Direct answer (no tool use)
        text_response = MockAnthropicResponse(
            content=[MockTextBlock("Direct answer after one tool call")]
        )

        with patch.object(test_ai_generator.client.messages, "create") as mock_create:
            mock_create.side_effect = [tool_use_response, text_response]

            response = test_ai_generator.generate_response(
                query="Simple query",
                tools=test_tool_manager.get_tool_definitions(),
                tool_manager=test_tool_manager,
            )

            # Should make only 2 API calls (1 tool round + exit)
            assert mock_create.call_count == 2
            assert "Direct answer after one tool call" in response

    def test_zero_tool_calls_with_tools_available(
        self, test_ai_generator, test_tool_manager
    ):
        """Test that Claude can answer directly even when tools are available"""
        # Claude answers directly without tools
        direct_response = MockAnthropicResponse(
            content=[MockTextBlock("Direct answer without tools")]
        )

        with patch.object(test_ai_generator.client.messages, "create") as mock_create:
            mock_create.return_value = direct_response

            response = test_ai_generator.generate_response(
                query="What is 2+2?",
                tools=test_tool_manager.get_tool_definitions(),
                tool_manager=test_tool_manager,
            )

            # Should make only 1 API call
            assert mock_create.call_count == 1
            assert "Direct answer without tools" in response

    def test_tool_execution_error_handling(self, test_ai_generator, test_tool_manager):
        """Test that tool execution errors are handled gracefully"""
        tool_use_response = MockAnthropicResponse(
            content=[
                MockToolUseBlock(
                    tool_name="search_course_content", tool_input={"query": "test"}
                )
            ],
            stop_reason="tool_use",
        )

        with patch.object(test_ai_generator.client.messages, "create") as mock_create:
            mock_create.return_value = tool_use_response

            # Mock tool execution to raise an error
            with patch.object(
                test_tool_manager, "execute_tool", side_effect=Exception("Tool failed")
            ):
                response = test_ai_generator.generate_response(
                    query="Test query",
                    tools=test_tool_manager.get_tool_definitions(),
                    tool_manager=test_tool_manager,
                )

                # Should return error message
                assert "Error during tool execution" in response
                assert "Tool failed" in response


class TestToolManager:
    """Test suite for ToolManager functionality"""

    def test_register_tool(self, test_search_tool):
        """Test registering a tool"""
        from search_tools import ToolManager

        manager = ToolManager()

        manager.register_tool(test_search_tool)

        # Tool should be registered
        assert "search_course_content" in manager.tools

    def test_get_tool_definitions(self, test_tool_manager):
        """Test getting all tool definitions"""
        defs = test_tool_manager.get_tool_definitions()

        # Should have both search and outline tools
        assert len(defs) >= 2
        tool_names = [d["name"] for d in defs]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names

    def test_execute_tool_success(self, test_tool_manager):
        """Test executing a registered tool"""
        result = test_tool_manager.execute_tool("search_course_content", query="Python")

        # Should return valid result
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_execute_nonexistent_tool(self, test_tool_manager):
        """Test executing a tool that doesn't exist"""
        result = test_tool_manager.execute_tool("nonexistent_tool", query="test")

        # Should return error message
        assert "not found" in result

    def test_get_last_sources(self, test_tool_manager):
        """Test retrieving sources from last tool execution"""
        # Execute a search
        test_tool_manager.execute_tool(
            "search_course_content", query="Python programming"
        )

        # Get sources
        sources = test_tool_manager.get_last_sources()

        # Should have sources
        assert len(sources) > 0
        # Each source should have text and url
        for source in sources:
            assert "text" in source
            assert "url" in source

    def test_reset_sources(self, test_tool_manager):
        """Test resetting sources"""
        # Execute a search to populate sources
        test_tool_manager.execute_tool("search_course_content", query="Python")

        # Verify sources exist
        assert len(test_tool_manager.get_last_sources()) > 0

        # Reset sources
        test_tool_manager.reset_sources()

        # Sources should be empty
        assert len(test_tool_manager.get_last_sources()) == 0
