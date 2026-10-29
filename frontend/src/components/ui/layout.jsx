import React from "react";
import { Loader2 } from "lucide-react";

const spacing = (value) =>
  typeof value === "number" ? `${value * 0.25}rem` : value;

const maxWidths = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-xl",
  "2xl": "max-w-2xl",
  "4xl": "max-w-4xl",
  "6xl": "max-w-6xl",
  full: "max-w-full",
};

export function Container({ children, className = "", maxW, py, px, minH, ...props }) {
  const style = {};
  if (py !== undefined) {
    style.paddingTop = spacing(py);
    style.paddingBottom = spacing(py);
  }
  if (px !== undefined) {
    style.paddingLeft = spacing(px);
    style.paddingRight = spacing(px);
  }
  if (minH) style.minHeight = minH;

  return (
    <div
      className={`mx-auto w-full ${maxWidths[maxW] || "max-w-6xl"} ${className}`}
      style={style}
      {...props}
    >
      {children}
    </div>
  );
}

export function Box({ children, className = "", flex, ...props }) {
  const style = flex !== undefined ? { flex } : undefined;
  return (
    <div className={className} style={style} {...props}>
      {children}
    </div>
  );
}

export function Select({ children, className = "", onValueChange, onChange, ...props }) {
  return (
    <select
      className={`rounded-md border border-gray-700 bg-charcoal px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-accent ${className}`}
      onChange={(event) => {
        if (onValueChange) onValueChange(event.target.value);
        if (onChange) onChange(event);
      }}
      {...props}
    >
      {children}
    </select>
  );
}

export function Table({ children, className = "", ...props }) {
  return (
    <div className="overflow-x-auto">
      <table className={`w-full text-left text-sm ${className}`} {...props}>
        {children}
      </table>
    </div>
  );
}

export function TableHead({ children, ...props }) {
  return (
    <thead className="border-b border-gray-700 text-xs uppercase tracking-wide text-gray-400" {...props}>
      {children}
    </thead>
  );
}

export function TableBody({ children, ...props }) {
  return <tbody className="divide-y divide-gray-800" {...props}>{children}</tbody>;
}

export function TableFooter({ children, ...props }) {
  return (
    <tfoot className="border-t border-gray-700 font-medium text-white" {...props}>
      {children}
    </tfoot>
  );
}

export function TableRow({ children, ...props }) {
  return <tr {...props}>{children}</tr>;
}

export function TableCell({ children, className = "", ...props }) {
  return (
    <td className={`px-3 py-2 align-top ${className}`} {...props}>
      {children}
    </td>
  );
}

export function Spinner({ size = 24, className = "" }) {
  return <Loader2 size={size} className={`animate-spin text-accent ${className}`} />;
}

export const Loader = Spinner;
