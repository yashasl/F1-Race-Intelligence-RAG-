import React from "react";

export function Button({ children, onClick, disabled, className, ...props }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2
        ${className}
      `}
      {...props}
    >
      {children}
    </button>
  );
}