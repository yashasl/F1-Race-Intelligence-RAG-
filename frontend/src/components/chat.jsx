import React from "react";
import { Bot, User } from "lucide-react";
import { Typography } from "./ui/typography.jsx";

export function MessageBubble({ msg, isSuggestion }) {
  const isUser = msg.role === "user";

  if (isSuggestion || msg.role === "system") {
    return (
      <button
        type="button"
        className="w-full rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-2 text-left text-sm text-gray-300 transition-colors hover:border-accent/40 hover:bg-gray-800"
        onClick={msg.onClick}
      >
        {msg.content}
      </button>
    );
  }

  return (
    <div
      className={`flex items-start gap-3 rounded-lg px-4 py-3 text-sm ${
        isUser ? "bg-accent/10" : "bg-gray-900/60"
      }`}
    >
      <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-gray-800">
        {isUser ? (
          <User size={15} className="text-accent" />
        ) : (
          <Bot size={15} className="text-accent" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <Typography variant="caption" className="mb-1 block font-medium text-gray-400">
          {isUser ? "You" : "AI"}
        </Typography>
        <Typography variant="body2" className="whitespace-pre-wrap text-gray-200">
          {msg.content}
        </Typography>
        {msg.sources && msg.sources.length > 0 && (
          <div className="mt-2 space-y-1 text-xs text-gray-500">
            <span className="font-medium text-gray-400">Sources</span>
            {msg.sources.map((src, index) => (
              <div key={index}>
                {[src.season, src.grand_prix, src.driver, src.constructor]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
