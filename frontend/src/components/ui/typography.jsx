import React from "react";

const variants = {
  h1: "text-4xl font-bold text-white",
  h2: "text-3xl font-bold text-white",
  h3: "text-2xl font-bold text-white",
  h4: "text-2xl font-bold text-white",
  h5: "text-xl font-medium text-white",
  body1: "text-base text-white",
  body2: "text-sm text-gray-300",
  caption: "text-xs text-gray-500",
};

const tags = {
  h1: "h1",
  h2: "h2",
  h3: "h3",
  h4: "h2",
  h5: "h3",
  body1: "p",
  body2: "p",
  caption: "span",
};

export function Typography({ variant = "body1", className = "", children, ...props }) {
  const Tag = tags[variant] || "p";
  const variantClasses = variants[variant] || "text-white";

  return (
    <Tag className={`${variantClasses} ${className}`} {...props}>
      {children}
    </Tag>
  );
}
