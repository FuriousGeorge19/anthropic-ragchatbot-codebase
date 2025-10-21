from typing import Dict, List, Optional

import anthropic


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to two specialized tools for course information.

Tool Selection:
- **get_course_outline**: Use for questions about:
  - Course structure, outlines, or what's covered
  - List of lessons in a course
  - Course titles, links, and instructor information
  - "What is the outline of..." or "What lessons are in..."

- **search_course_content**: Use for questions about:
  - Specific content within course materials
  - Detailed explanations of topics covered in lessons
  - "What does the course say about..." or "How is X explained..."

Tool Usage Rules:
- **Sequential tool calls allowed**: You can make up to 2 tool calls to gather information
- **Think step by step**: If you need more information after the first tool result, you can call another tool
- **Examples of sequential use**:
  - First call search_course_content to find relevant courses
  - Then call get_course_outline for detailed lesson structure
  - Or search for one topic, then search for a related topic to compare
- **Be efficient**: Only make a second call if truly needed
- Choose the most appropriate tool based on the question
- Synthesize tool results into accurate, fact-based responses
- If tool yields no results, state this clearly without offering alternatives

Response Protocol for Course Outlines:
- When returning course outlines, always include:
  - Course title
  - Course link (if available)
  - Complete lesson list with lesson numbers and titles
- Format clearly with proper structure

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course-specific questions**: Use appropriate tool first, then answer
- **No meta-commentary**:
  - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
  - Do not mention "based on the tool results" or "I used the outline tool"

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    # Maximum number of sequential tool calling rounds
    MAX_TOOL_ROUNDS = 2

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to 2 sequential rounds of tool calling.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Initialize message list with user query
        messages = [{"role": "user", "content": query}]
        round_count = 0

        # If no tools provided, make single call and return
        if not tools or not tool_manager:
            api_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content,
            }
            response = self.client.messages.create(**api_params)
            return self._extract_text_response(response)

        # ITERATIVE TOOL EXECUTION LOOP (up to MAX_TOOL_ROUNDS)
        while round_count < self.MAX_TOOL_ROUNDS:
            round_count += 1

            # Make API call with tools enabled
            api_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content,
                "tools": tools,
                "tool_choice": {"type": "auto"},
            }

            response = self.client.messages.create(**api_params)

            # TERMINAL CONDITION 1: No tool use detected
            if response.stop_reason != "tool_use":
                return self._extract_text_response(response)

            # Execute tools for this round
            try:
                tool_results = self._execute_tool_round(response, tool_manager)
            except Exception as e:
                # TERMINAL CONDITION 2: Tool execution failed
                return f"Error during tool execution: {str(e)}"

            # Accumulate this round's messages
            messages = self._accumulate_messages(messages, response, tool_results)

            # Continue to next round (or exit if max_rounds reached)

        # FINAL SYNTHESIS: Make final call WITHOUT tools to force text response
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content,
            # Note: NO tools parameter - forces Claude to synthesize answer
        }

        final_response = self.client.messages.create(**final_params)
        return self._extract_text_response(final_response)

    def _execute_tool_round(self, response, tool_manager) -> List[Dict]:
        """
        Execute all tools in a single round.

        Args:
            response: API response containing tool_use blocks
            tool_manager: Manager to execute tools

        Returns:
            List of tool_result dictionaries

        Raises:
            Exception if tool execution fails
        """
        tool_results = []

        for content_block in response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name, **content_block.input
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result,
                    }
                )

        if not tool_results:
            raise ValueError(
                "No tool_use blocks found in response with stop_reason='tool_use'"
            )

        return tool_results

    def _accumulate_messages(
        self, messages: List[Dict], assistant_response, tool_results: List[Dict]
    ) -> List[Dict]:
        """
        Add one round's messages to the conversation.

        Args:
            messages: Current message list
            assistant_response: API response with tool_use blocks
            tool_results: List of tool_result dictionaries

        Returns:
            Updated message list
        """
        # Add assistant's tool_use response
        messages.append({"role": "assistant", "content": assistant_response.content})

        # Add tool results as user message
        messages.append({"role": "user", "content": tool_results})

        return messages

    def _extract_text_response(self, response) -> str:
        """
        Extract text content from API response.

        Args:
            response: API response

        Returns:
            Text content as string
        """
        for block in response.content:
            if hasattr(block, "text"):
                return block.text

        return "Error: No text content in response"
