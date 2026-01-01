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
            system_prompt = await self._build_system_prompt()
            
            print(f"--- Sending to LLM ---\nMessages: {len(self.messages)}")

            # Get response from LLM
            response = services.llm.chat(
                messages=self.messages,
                system=system_prompt,
                tools=self._get_tool_definitions(),
            )
            
            print(f"--- LLM Response ---\n{response}")

            # Add assistant response - handle None content from Gemini tool calls
            assistant_content = response.get("content") or ""

            # Check for tool calls and execute them
            if response.get("tool_calls"):
                tool_results = await self._execute_tools(response["tool_calls"])
                
                # IMPORTANT: Append tool output as a separate observation or part of the answer
                # For this simple chat integration, we append it to the content for display
                # But for proper history, we might need a better structure in the future
                assistant_content += f"\n\n{tool_results}"
                print(f"--- Tool Results ---\n{tool_results}")

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

    async def _build_system_prompt(self) -> str:
        """Build system prompt with dynamic user context."""
        from datetime import datetime
        from ...state.user_context import UserContextState
        
        # Fetch user context
        user_ctx = await self.get_state(UserContextState)
        profile_name = user_ctx.profile_display_name
        risk_tolerance = user_ctx.risk_tolerance
        watchlist = ", ".join(user_ctx.watchlist[:10]) if user_ctx.watchlist else "Empty"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        return f"""You are Phin, an AI finance assistant for the Phinan Finance Suite.

**Current Time:** {current_time}
**Active User Profile:** {profile_name}
**Risk Tolerance:** {risk_tolerance}
**Watchlist (up to 10):** {watchlist}

**Your Capabilities:**
1. **Stock Research**: Look up detailed info on any ticker (price, fundamentals, analyst ratings).
2. **Price Range Analysis**: Get high/low/current position over 1mo, 3mo, 6mo, or 1y periods.
3. **News & Sentiment**: Fetch recent news headlines for any stock.
4. **Watchlist Management**: Add stocks to the user's watchlist.

**Available Tools:**
- `lookup_ticker(symbol)` - Get stock details
- `get_price_range(symbol, period)` - Analyze price position in range
- `add_to_watchlist(symbol)` - Add to user's watchlist
- `get_news(symbol)` - Get recent news

**IMPORTANT: Answering Questions**
- If the user asks a general or meta question like "Who are you?", "What can you do?", "What are your capabilities?", or "What time is it?", answer directly using your knowledge and the context above. Do NOT call any tool unless the question is specifically about a stock ticker.
- If the user asks about a specific stock (e.g., "Tell me about AAPL"), then use the `lookup_ticker` tool.
- Always stay on topic. If you previously discussed a ticker, that context is for reference, but new questions may not be about that ticker.

**User Profiles:**
The app supports different trading profiles (Papi, Tio, Franky) with different risk tolerances and strategies.
- Papi: Conservative, entry/exit plays, 2-week timeframe.
- Tio: Aggressive, directional plays, 1-2 month timeframe.
- Franky: Learning mode, varies.

You are currently assisting **{profile_name}** with a **{risk_tolerance}** risk tolerance.

**Key Principles:**
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
            {
                "type": "function",
                "function": {
                    "name": "get_capabilities",
                    "description": "Get information about what the assistant can do. Use this when asked 'what can you do' or 'help'.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
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

    async def _tool_get_capabilities(self, args: dict) -> str:
        """Tool: Get capabilities."""
        return """**My Capabilities:**
1. **Stock Research**: Look up detailed info on any ticker (price, fundamentals, analyst ratings).
2. **Price Range Analysis**: Get high/low/current position over 1mo, 3mo, 6mo, or 1y periods.
3. **News & Sentiment**: Fetch recent news headlines for any stock.
4. **Watchlist Management**: Add stocks to the user's watchlist.

Just ask me to "Research AAPL" or "Add NVDA to my watchlist"!"""

    @property
    def _tool_registry(self):
        """Registry of available tools."""
        return {
            "lookup_ticker": self._tool_lookup_ticker,
            "get_price_range": self._tool_get_price_range,
            "add_to_watchlist": self._tool_add_to_watchlist,
            "get_news": self._tool_get_news,
            "get_capabilities": self._tool_get_capabilities,
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
