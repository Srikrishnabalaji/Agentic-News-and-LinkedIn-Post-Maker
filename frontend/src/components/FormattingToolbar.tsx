import { useState, type RefObject } from "react";

interface Props {
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}

// --- Unicode bold mapping (LinkedIn has no rich text) -----------------------
function toBold(c: string): string {
  const code = c.codePointAt(0)!;
  if (c >= "A" && c <= "Z") return String.fromCodePoint(0x1d5d4 + code - 65);
  if (c >= "a" && c <= "z") return String.fromCodePoint(0x1d5ee + code - 97);
  if (c >= "0" && c <= "9") return String.fromCodePoint(0x1d7ec + code - 48);
  return c;
}

function fromBold(c: string): string {
  const code = c.codePointAt(0)!;
  if (code >= 0x1d5d4 && code <= 0x1d5ed)
    return String.fromCharCode(65 + (code - 0x1d5d4)); // A-Z
  if (code >= 0x1d5ee && code <= 0x1d607)
    return String.fromCharCode(97 + (code - 0x1d5ee)); // a-z
  if (code >= 0x1d7ec && code <= 0x1d7f5)
    return String.fromCharCode(48 + (code - 0x1d7ec)); // 0-9
  return c;
}

function isBoldChar(c: string): boolean {
  return fromBold(c) !== c;
}

function isAlnum(c: string): boolean {
  return /[A-Za-z0-9]/.test(c);
}

const mapStr = (s: string, fn: (c: string) => string) =>
  Array.from(s).map(fn).join("");

// --- Emoji picker data (static, no dependency) ------------------------------
const EMOJI_GROUPS: { name: string; emojis: [string, string][] }[] = [
  {
    name: "Smileys",
    emojis: [
      ["😀", "grin smile happy"], ["😄", "smile happy"], ["😉", "wink"],
      ["🙂", "slight smile"], ["😊", "blush smile"], ["😎", "cool sunglasses"],
      ["🤔", "thinking"], ["😮", "surprised wow"], ["😱", "shock scream fear"],
      ["😅", "sweat nervous"], ["🙌", "celebrate hands"], ["👏", "clap applause"],
      ["👍", "thumbs up like"], ["👎", "thumbs down"], ["👀", "eyes look"],
      ["🙏", "thanks pray please"], ["💪", "strong muscle"], ["🤝", "handshake deal"],
    ],
  },
  {
    name: "Objects",
    emojis: [
      ["🔒", "lock secure security"], ["🔑", "key password"], ["🛡️", "shield protect defense"],
      ["💻", "laptop computer"], ["📱", "phone mobile"], ["🖥️", "desktop monitor"],
      ["📧", "email mail"], ["📨", "incoming mail"], ["💳", "credit card payment"],
      ["💰", "money bag cash"], ["💵", "dollar money cash"], ["🏦", "bank"],
      ["📊", "bar chart data"], ["📈", "chart up growth"], ["📉", "chart down loss"],
      ["💡", "idea bulb tip"], ["🔍", "search magnify"], ["📰", "news newspaper"],
      ["⚙️", "settings gear"], ["🧰", "toolbox tools"], ["📌", "pin"],
      ["🗂️", "files folder"], ["📂", "open folder"], ["🔔", "bell alert notify"],
    ],
  },
  {
    name: "Symbols",
    emojis: [
      ["✅", "check done success"], ["❌", "cross no error fail"], ["⚠️", "warning caution"],
      ["🚨", "alert siren emergency"], ["🔥", "fire hot trending"], ["⭐", "star"],
      ["❗", "exclamation important"], ["❓", "question"], ["➡️", "arrow right"],
      ["⬆️", "arrow up"], ["⬇️", "arrow down"], ["✔️", "check mark"],
      ["💯", "hundred perfect"], ["🎯", "target goal bullseye"], ["⏰", "alarm time clock"],
      ["📍", "location pin"], ["🔗", "link chain"], ["©️", "copyright"],
    ],
  },
];

export default function FormattingToolbar({
  textareaRef,
  value,
  onChange,
  disabled,
}: Props) {
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [search, setSearch] = useState("");

  // Apply an edit, then restore focus + a sensible selection/caret.
  const commit = (next: string, selStart: number, selEnd: number) => {
    onChange(next);
    const ta = textareaRef.current;
    if (!ta) return;
    requestAnimationFrame(() => {
      ta.focus();
      ta.setSelectionRange(selStart, selEnd);
    });
  };

  const getSel = (): [number, number] => {
    const ta = textareaRef.current;
    if (!ta) return [value.length, value.length];
    return [ta.selectionStart ?? value.length, ta.selectionEnd ?? value.length];
  };

  const bold = () => {
    const [start, end] = getSel();
    if (start === end) return; // nothing selected
    const sel = value.slice(start, end);
    // A char counts as "meaningful" if it's an ASCII alnum (boldable) or
    // already bold — so toggling off detects an all-bold selection correctly.
    const meaningful = Array.from(sel).filter((c) => isAlnum(c) || isBoldChar(c));
    const allBold = meaningful.length > 0 && meaningful.every(isBoldChar);
    const transformed = mapStr(sel, allBold ? fromBold : toBold);
    const next = value.slice(0, start) + transformed + value.slice(end);
    commit(next, start, start + transformed.length);
  };

  const bullets = () => {
    const [start, end] = getSel();
    // Expand selection to whole lines.
    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
    let lineEnd = value.indexOf("\n", end);
    if (lineEnd === -1) lineEnd = value.length;
    const block = value.slice(lineStart, lineEnd);
    const lines = block.split("\n");
    const allBulleted = lines.every((l) => l.trimStart().startsWith("• ") || l.trim() === "");
    const out = lines
      .map((l) => {
        if (l.trim() === "") return l;
        return allBulleted ? l.replace(/^(\s*)• ?/, "$1") : `• ${l}`;
      })
      .join("\n");
    const next = value.slice(0, lineStart) + out + value.slice(lineEnd);
    commit(next, lineStart, lineStart + out.length);
  };

  const spacing = () => {
    const [start, end] = getSel();
    const next = value.slice(0, start) + "\n\n" + value.slice(end);
    commit(next, start + 2, start + 2);
  };

  const insertEmoji = (emoji: string) => {
    const [start, end] = getSel();
    const next = value.slice(0, start) + emoji + value.slice(end);
    commit(next, start + emoji.length, start + emoji.length);
    setEmojiOpen(false);
    setSearch("");
  };

  const btn =
    "text-sm w-8 h-8 flex items-center justify-center rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40";

  const filtered = EMOJI_GROUPS.map((g) => ({
    ...g,
    emojis: search
      ? g.emojis.filter(([, kw]) => kw.includes(search.toLowerCase()))
      : g.emojis,
  })).filter((g) => g.emojis.length > 0);

  return (
    <div className="relative flex items-center gap-1">
      <button type="button" onClick={bold} disabled={disabled} className={`${btn} font-bold`} title="Bold selection">
        B
      </button>
      <button type="button" onClick={bullets} disabled={disabled} className={btn} title="Bullet selected lines">
        •
      </button>
      <button
        type="button"
        onClick={() => setEmojiOpen((o) => !o)}
        disabled={disabled}
        className={btn}
        title="Insert emoji"
      >
        ☺
      </button>
      <button type="button" onClick={spacing} disabled={disabled} className={btn} title="Insert line break">
        ↵
      </button>

      {emojiOpen && (
        <div className="absolute top-9 left-0 z-20 w-72 bg-white border border-gray-200 rounded-lg shadow-lg p-2">
          <input
            autoFocus
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search emoji…"
            className="w-full text-sm border border-gray-200 rounded-md px-2 py-1 mb-2 outline-none focus:border-linkedin"
          />
          <div className="max-h-56 overflow-y-auto">
            {filtered.map((g) => (
              <div key={g.name} className="mb-2">
                <div className="text-[10px] uppercase tracking-wide text-gray-400 px-1 mb-1">
                  {g.name}
                </div>
                <div className="grid grid-cols-8 gap-0.5">
                  {g.emojis.map(([e]) => (
                    <button
                      key={e}
                      type="button"
                      onClick={() => insertEmoji(e)}
                      className="text-lg w-8 h-8 flex items-center justify-center rounded hover:bg-gray-100"
                    >
                      {e}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {!filtered.length && (
              <div className="text-xs text-gray-400 p-2 text-center">No matches</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
