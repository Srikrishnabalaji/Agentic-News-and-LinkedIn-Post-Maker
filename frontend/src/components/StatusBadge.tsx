import type { PostStatus } from "../types";

const STYLES: Record<PostStatus, string> = {
  draft: "bg-gray-100 text-gray-600",
  approved: "bg-blue-50 text-linkedin",
  posted: "bg-green-50 text-green-700",
};

export default function StatusBadge({ status }: { status: PostStatus }) {
  return (
    <span
      className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${STYLES[status]}`}
    >
      {status}
    </span>
  );
}
