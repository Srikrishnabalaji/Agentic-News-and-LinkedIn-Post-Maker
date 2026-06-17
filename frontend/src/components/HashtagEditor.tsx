import { useState } from "react";

interface Props {
  tags: string[];
  onChange: (tags: string[]) => void;
}

export default function HashtagEditor({ tags, onChange }: Props) {
  const [input, setInput] = useState("");

  const add = () => {
    const clean = input.trim().replace(/^#/, "").replace(/\s+/g, "");
    if (clean && !tags.some((t) => t.toLowerCase() === clean.toLowerCase())) {
      onChange([...tags, clean]);
    }
    setInput("");
  };

  return (
    <div>
      <label className="block text-xs font-semibold text-gray-500 mb-1">
        HASHTAGS
      </label>
      <div className="flex flex-wrap gap-2">
        {tags.map((t) => (
          <span
            key={t}
            className="inline-flex items-center gap-1 bg-blue-50 text-linkedin text-sm px-2.5 py-1 rounded-full"
          >
            #{t}
            <button
              onClick={() => onChange(tags.filter((x) => x !== t))}
              className="text-linkedin/60 hover:text-red-500 font-bold leading-none"
              aria-label={`Remove ${t}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add();
            }
          }}
          onBlur={add}
          placeholder="+ add"
          className="text-sm px-2 py-1 w-24 border-b border-gray-200 focus:border-linkedin outline-none"
        />
      </div>
    </div>
  );
}
