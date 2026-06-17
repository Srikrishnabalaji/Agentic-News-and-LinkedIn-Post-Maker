import { LINKEDIN_LIMIT } from "../types";

interface Props {
  body: string;
  hashtags: string[];
  imageUrl: string | null;
  imageAttribution: string | null;
}

// Mimics how a LinkedIn feed post renders, including the ~210-char
// "…see more" truncation so the editor can judge the hook.
export default function LinkedInPreview({
  body,
  hashtags,
  imageUrl,
  imageAttribution,
}: Props) {
  const tagLine = hashtags.map((h) => `#${h}`).join(" ");
  const fullText = tagLine ? `${body}\n\n${tagLine}` : body;
  const count = fullText.length;
  const over = count > LINKEDIN_LIMIT;
  const SEE_MORE = 210;
  const truncated = fullText.length > SEE_MORE;

  return (
    <div className="flex flex-col gap-2">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 max-w-[555px]">
        <div className="flex items-center gap-3 p-4 pb-2">
          <div className="w-12 h-12 rounded-full bg-linkedin text-white flex items-center justify-center font-bold text-lg">
            Q
          </div>
          <div className="leading-tight">
            <div className="font-semibold text-[15px] text-gray-900">
              QuantrixLabs
            </div>
            <div className="text-xs text-gray-500">
              Cybersecurity, explained · Just now
            </div>
          </div>
        </div>

        <div className="px-4 pb-2 text-[14px] text-gray-900 whitespace-pre-wrap leading-snug">
          {truncated ? (
            <>
              {fullText.slice(0, SEE_MORE)}
              <span className="text-gray-400">… </span>
              <span className="text-gray-500">see more</span>
            </>
          ) : (
            fullText
          )}
        </div>

        {imageUrl && (
          <div className="mt-1">
            <img
              src={imageUrl}
              alt=""
              className="w-full max-h-[320px] object-cover border-t border-gray-100"
            />
          </div>
        )}

        <div className="flex justify-around text-gray-500 text-sm py-2 border-t border-gray-100 mt-1">
          <span>👍 Like</span>
          <span>💬 Comment</span>
          <span>↗ Share</span>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs px-1">
        <span className={over ? "text-red-600 font-semibold" : "text-gray-500"}>
          {count.toLocaleString()} / {LINKEDIN_LIMIT.toLocaleString()} characters
          {over && " — over LinkedIn limit"}
        </span>
        {imageAttribution && (
          <span className="text-gray-400 truncate max-w-[260px]">
            {imageAttribution}
          </span>
        )}
      </div>
    </div>
  );
}
