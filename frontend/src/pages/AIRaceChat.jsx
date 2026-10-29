import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { Button } from "../components/ui/button.jsx";
import { Card } from "../components/ui/card.jsx";
import { Container, Spinner } from "../components/ui/layout.jsx";
import { Input } from "../components/ui/input.jsx";
import { Typography } from "../components/ui/typography.jsx";
import { MessageBubble } from "../components/chat.jsx";

const suggestions = [
  "How did Lewis Hamilton perform in the 2021 Bahrain Grand Prix?",
  "Who won the 2023 Singapore Grand Prix?",
  "Compare Max Verstappen's and Lewis Hamilton's 2021 season performance.",
  "Which constructor scored the most points in 2024?",
];

export default function AIRaceChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage(question) {
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed, top_k: 5 }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.error || "Chat request failed");
      }

      if (data.success && data.answer) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.answer,
            sources: data.sources || [],
          },
        ]);
      } else {
        setError(data.error || "The chat service returned no answer.");
      }
    } catch (err) {
      setError(err.message || "Could not reach the chat service.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Container>
      <Typography variant="h4" className="mb-2">
        AI Race Intelligence
      </Typography>
      <Typography variant="body2" className="mb-6 text-gray-400">
        Ask questions about the 2021–2025 Formula 1 seasons. Answers are grounded in
        retrieved race records.
      </Typography>

      <Card className="mb-4 flex h-[600px] flex-col p-0">
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="grid gap-2 sm:grid-cols-2">
              {suggestions.map((suggestion) => (
                <MessageBubble
                  key={suggestion}
                  msg={{
                    role: "system",
                    content: suggestion,
                    onClick: () => sendMessage(suggestion),
                  }}
                  isSuggestion
                />
              ))}
            </div>
          )}

          {messages.map((msg, index) => (
            <MessageBubble key={index} msg={msg} />
          ))}

          {loading && (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Spinner size={18} />
              Searching race records...
            </div>
          )}

          {error && (
            <div className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        <form
          className="flex gap-2 border-t border-gray-800 p-3"
          onSubmit={(event) => {
            event.preventDefault();
            sendMessage(input);
          }}
        >
          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about an F1 race, driver, or season..."
            disabled={loading}
            className="flex-1"
          />
          <Button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-accent px-4 py-2 text-white hover:bg-red-500"
          >
            <Send size={16} className="mr-1" />
            Send
          </Button>
        </form>
      </Card>

      {messages.length > 0 && (
        <button
          type="button"
          className="text-xs text-gray-500 hover:text-white"
          onClick={() => {
            setMessages([]);
            setError(null);
          }}
        >
          Clear chat
        </button>
      )}
    </Container>
  );
}
