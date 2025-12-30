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


    async def _tool_lookup_ticker(self, args: dict) -> str:
        """Tool: Lookup ticker information."""
        from ...services import services

        symbol = args.get("symbol", "")
        info = services.market_data.get_ticker_info(symbol)
        if info:
            # Safe formatting helpers
            price = f"${info.current_price:.2f}" if info.current_price is not None else "N/A"
            pe = info.pe_ratio if info.pe_ratio is not None else "N/A"
            div = f"{info.dividend_yield:.2%}" if info.dividend_yield is not None else "N/A"
            rating = info.analyst_rating or "N/A"
            
            return (
                f"**{info.symbol}** - {info.name}\n"
                f"- Price: {price}\n"
                f"- P/E: {pe}\n"
                f"- Dividend Yield: {div}\n"
                f"- Analyst Rating: {rating}"
            )
        return f"Could not find ticker: {symbol}"

    async def _tool_get_price_range(self, args: dict) -> str:
        """Tool: Get price range."""
        from ...services import services

        symbol = args.get("symbol", "")
        period = args.get("period", "3mo")
        range_data = services.market_data.get_price_range(symbol, period)
        if range_data:
            return (
                f"**{symbol} Price Range ({range_data.period})**\n"
                f"- High: ${range_data.high:.2f}\n"
                f"- Low: ${range_data.low:.2f}\n"
                f"- Current: ${range_data.current:.2f}\n"
                f"- Position: {range_data.percent_of_range:.0%} of range"
            )
        return f"Could not get range for: {symbol}"

    async def _tool_add_to_watchlist(self, args: dict) -> str:
        """Tool: Add to watchlist."""
        from ...state.user_context import UserContextState

        symbol = args.get("symbol", "")
        user_ctx = await self.get_state(UserContextState)
        user_ctx.add_to_watchlist(symbol)
        return f"Added {symbol} to watchlist"

    async def _tool_get_news(self, args: dict) -> str:
        """Tool: Get news."""
        from ...services import services

        symbol = args.get("symbol", "")
        news = services.market_data.get_news(symbol)
        if news:
            news_text = f"**Recent news for {symbol}:**\n"
            for item in news[:5]:
                news_text += f"- {item.title} ({item.publisher})\n"
            return news_text
        return f"No recent news for {symbol}"

    @property
    def _tool_registry(self):
        """Registry of available tools."""
        return {
            "lookup_ticker": self._tool_lookup_ticker,
            "get_price_range": self._tool_get_price_range,
            "add_to_watchlist": self._tool_add_to_watchlist,
            "get_news": self._tool_get_news,
        }

    async def _execute_tools(self, tool_calls: list) -> str:
        """Execute tool calls and return formatted results."""
        results = []

        for call in tool_calls:
            func = call.get("function", {})
            name = func.get("name")
            args = func.get("arguments", {})

            if isinstance(args, str):
                import json
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    results.append(f"Error parsing arguments for {name}")
                    continue

            try:
                if name in self._tool_registry:
                    tool_func = self._tool_registry[name]
                    # Check if tool function is async
                    import inspect
                    if inspect.iscoroutinefunction(tool_func):
                        result = await tool_func(args)
                    else:
                        result = await tool_func(args) # Fallback if not async defined but called async, though here all are async
                    results.append(result)
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
