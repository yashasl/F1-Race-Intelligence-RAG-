import React from "react";

export function Input({ placeholder, value, onChange, disabled, className, ...props }) {
  return (
    <input
      type="text"
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      disabled={disabled}
      className={`
        rounded-md border-input bg-transparent px-3 py-2 text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors
        ${className}
      `}
      {...props}
    />
  );
}