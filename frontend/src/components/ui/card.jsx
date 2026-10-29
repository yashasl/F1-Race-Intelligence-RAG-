import React from "react";

export function Card({ children, className, ...props }) {
  return (
    <div
      className={`
        rounded-lg border border-gray-700 bg-gray-900/50 backdrop-blur-sm p-6 transition-colors hover:bg-gray-900/80
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
}