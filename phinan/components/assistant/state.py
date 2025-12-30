"""Assistant state for chat interface.

The assistant is the primary interface - it maintains conversation context
and can invoke tools from all modules.
"""

import reflex as rx
from typing import Any


class AssistantState(rx.State):
    """State for the persistent AI assistant.

    Manages:
    - Chat message history
    - Current input
    - Loading/thinking states
    - Tool call results
    """

    # Chat messages: list of {"role": "user"|"assistant", "content": str}
    messages: list[dict[str, Any]] = []

    # Current input
    current_input: str = ""

    # Loading state
    is_thinking: bool = False

    # Session tracking
    session_id: str = ""

    # Error state
    error_message: str = ""

    @rx.var
    def message_count(self) -> int:
        """Number of messages in conversation."""
        return len(self.messages)

    @rx.var
    def has_messages(self) -> bool:
        """Whether conversation has any messages."""
        return len(self.messages) > 0

    @rx.var
    def last_message(self) -> dict:
        """Get last message or empty dict."""
        if self.messages:
            return self.messages[-1]
        return {}

    def set_input(self, value: str):
        """Update current input."""
        self.current_input = value

    def clear_input(self):
        """Clear current input."""
        self.current_input = ""

    async def handle_key_down(self, key: str):
        """Handle key down event."""
        if key == "Enter":
            async for item in self.send_message():
                yield item

    async def send_message(self):
        """Send message to assistant and get response."""
        if not self.current_input.strip():
            return

        user_message = self.current_input.strip()
        self.current_input = ""
        self.error_message = ""

        # Add user message to history
        self.messages = self.messages + [{"role": "user", "content": user_message}]
        
        self.is_thinking = True
        yield

        try:
            from ...services import services

            # Build system prompt with user context
            system_prompt = self._build_system_prompt()

            # Get response from LLM
            response = services.llm.chat(
                messages=self.messages,
                system=system_prompt,
                tools=self._get_tool_definitions(),
            )

            # Add assistant response
            assistant_content = response.get("content", "I couldn't generate a response.")

            # Check for tool calls and execute them
            if response.get("tool_calls"):
                tool_results = await self._execute_tools(response["tool_calls"])
                assistant_content += f"\n\n{tool_results}"

            self.messages = self.messages + [{"role": "assistant", "content": assistant_content}]

            # Save to database
            self._save_message("user", user_message)
            self._save_message("assistant", assistant_content)

        except Exception as e:
            self.error_message = str(e)
            self.messages = self.messages + [
                {"role": "assistant", "content": f"Sorry, I encountered an error: {str(e)}"}
            ]
        finally:
            self.is_thinking = False

    def _build_system_prompt(self) -> str:
        """Build system prompt with context."""
        return """You are Phin, an AI finance assistant for the Phinan Finance Suite.

You help users with:
- Researching stocks and companies for options trading
- Analyzing market data and news sentiment
- Managing their watchlist and tracking trades
- Understanding structured financial products

You have access to tools for looking up ticker information, market data, and managing the user's portfolio.

Key principles:
1. Be concise and actionable
2. Reference specific data when discussing stocks
3. Remember the user's risk tolerance and trading style
4. Never give specific investment advice - provide information for their decisions

When you don't have enough data, say so and suggest what additional research might help."""

    def _get_tool_definitions(self) -> list[dict]:
        """Get available tool definitions for LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "lookup_ticker",
                    "description": "Look up detailed research on a stock ticker including price, fundamentals, and analyst data",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Stock ticker symbol (e.g., AAPL, NVDA)",
                            },
                        },
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_price_range",
                    "description": "Get price range analysis for a stock over a specified period",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Stock ticker symbol"},
                            "period": {
                                "type": "string",
                                "description": "Time period: 1mo, 3mo, 6mo, 1y",
                                "default": "3mo",
                            },
                        },
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_to_watchlist",
                    "description": "Add a stock to the user's watchlist",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Stock ticker symbol"},
                        },
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_news",
                    "description": "Get recent news headlines for a stock",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Stock ticker symbol"},
                        },
                        "required": ["symbol"],
                    },
                },
            },
        ]

    async def _execute_tools(self, tool_calls: list) -> str:
        """Execute tool calls and return formatted results."""
        from ...services import services

        results = []

        for call in tool_calls:
            func = call.get("function", {})
            name = func.get("name")
            args = func.get("arguments", {})

            if isinstance(args, str):
                import json

                args = json.loads(args)

            try:
                if name == "lookup_ticker":
                    info = services.market_data.get_ticker_info(args.get("symbol", ""))
                    if info:
                        results.append(
                            f"**{info.symbol}** - {info.name}\n"
                            f"- Price: ${info.current_price:.2f}\n"
                            f"- P/E: {info.pe_ratio}\n"
                            f"- Dividend Yield: {info.dividend_yield:.2%}\n"
                            f"- Analyst Rating: {info.analyst_rating}"
                        )
                    else:
                        results.append(f"Could not find ticker: {args.get('symbol')}")

                elif name == "get_price_range":
                    range_data = services.market_data.get_price_range(
                        args.get("symbol", ""), args.get("period", "3mo")
                    )
                    if range_data:
                        results.append(
                            f"**{args.get('symbol')} Price Range ({range_data.period})**\n"
                            f"- High: ${range_data.high:.2f}\n"
                            f"- Low: ${range_data.low:.2f}\n"
                            f"- Current: ${range_data.current:.2f}\n"
                            f"- Position: {range_data.percent_of_range:.0%} of range"
                        )
                    else:
                        results.append(f"Could not get range for: {args.get('symbol')}")

                elif name == "add_to_watchlist":
                    # Get user context state and add to watchlist
                    from ...state.user_context import UserContextState

                    user_ctx = await self.get_state(UserContextState)
                    user_ctx.add_to_watchlist(args.get("symbol", ""))
                    results.append(f"Added {args.get('symbol')} to watchlist")

                elif name == "get_news":
                    news = services.market_data.get_news(args.get("symbol", ""))
                    if news:
                        news_text = f"**Recent news for {args.get('symbol')}:**\n"
                        for item in news[:5]:
                            news_text += f"- {item.title} ({item.publisher})\n"
                        results.append(news_text)
                    else:
                        results.append(f"No recent news for {args.get('symbol')}")

                else:
                    results.append(f"Unknown tool: {name}")

            except Exception as e:
                results.append(f"Error executing {name}: {str(e)}")

        return "\n\n".join(results)

    def _save_message(self, role: str, content: str):
        """Save message to database."""
        from ...services import services
        import json

        try:
            services.db.execute(
                """
                INSERT INTO chat_history (session_id, role, content, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (self.session_id or "default", role, content, json.dumps({})),
            )
        except Exception:
            pass  # Silent fail for history saving

    def clear_chat(self):
        """Clear conversation history."""
        self.messages = []
        self.error_message = ""

    def new_conversation(self):
        """Start a new conversation."""
        import uuid

        self.messages = []
        self.session_id = str(uuid.uuid4())
        self.error_message = ""
