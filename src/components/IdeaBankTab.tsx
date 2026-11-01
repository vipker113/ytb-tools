"use client";

import {
  CheckSquare,
  Flame,
  Lightbulb,
  Plus,
  Square,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import type { SavedIdea, SubConversionChecklist } from "@/lib/types";

interface IdeaBankTabProps {
  ideas: SavedIdea[];
  onAddIdea: (idea: Partial<SavedIdea>) => Promise<void>;
  onUpdateIdea: (ideaId: string, patch: Partial<SavedIdea>) => Promise<void>;
  onDeleteIdea: (ideaId: string) => Promise<void>;
}

const STATUS_COLUMNS: Array<{
  key: SavedIdea["status"];
  label: string;
  badgeColor: string;
}> = [
  {
    key: "backlog",
    label: "Kho ý tưởng chờ",
    badgeColor: "bg-zinc-800 text-zinc-300",
  },
  {
    key: "scripting",
    label: "Đang viết kịch bản",
    badgeColor: "bg-amber-500/20 text-amber-300",
  },
  {
    key: "filming",
    label: "Đang quay / dựng",
    badgeColor: "bg-sky-500/20 text-sky-300",
  },
  {
    key: "published",
    label: "Đã đăng lên kênh",
    badgeColor: "bg-emerald-500/20 text-emerald-300",
  },
];

const CHECKLIST_ITEMS: Array<{
  key: keyof SubConversionChecklist;
  label: string;
}> = [
  { key: "hook5s", label: "Hook 5 giây đầu cam kết kết quả rõ ràng" },
  {
    key: "peakValueCta",
    label: "Xin Sub đúng khoảnh khắc vừa trao mẹo hay nhất (Phút 2–4)",
  },
  {
    key: "subConfirmationLink",
    label: "Chèn link ?sub_confirmation=1 trong Mô tả",
  },
  {
    key: "pinnedCommentCta",
    label: "Ghim bình luận đầu tiên đặt câu hỏi + dẫn link",
  },
  {
    key: "endScreenSub",
    label: "Gắn nút Đăng ký + Video tiếp theo ở 20s End Screen",
  },
];

export function IdeaBankTab({
  ideas,
  onAddIdea,
  onUpdateIdea,
  onDeleteIdea,
}: IdeaBankTabProps) {
  const [newTitle, setNewTitle] = useState("");
  const [newKeyword, setNewKeyword] = useState("");
  const [newFormat, setNewFormat] = useState<"long" | "short">("long");
  const [statusFilter, setStatusFilter] = useState<"all" | SavedIdea["status"]>(
    "all"
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    await onAddIdea({
      title: newTitle.trim(),
      remakeTitle: newTitle.trim(),
      targetKeyword: newKeyword.trim(),
      format: newFormat,
      status: "backlog",
    });
    setNewTitle("");
    setNewKeyword("");
  };

  const visibleIdeas =
    statusFilter === "all"
      ? ideas
      : ideas.filter((i) => i.status === statusFilter);

  return (
    <div className="space-y-6">
      {/* Add Idea Card */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
        <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-1">
          <Lightbulb className="h-5 w-5 text-amber-400" />
          Kho Ý Tưởng Viral & Checklist Kéo Sub Thực Chiến
        </h2>
        <p className="text-xs sm:text-sm text-zinc-400 mb-4">
          Lưu lại các chủ đề Outlier thắng lớn từ đối thủ và kiểm tra đủ{" "}
          <strong className="text-zinc-200">5 điểm chạm chuyển đổi Sub</strong> trước khi bấm Xuất bản lên YouTube Studio.
        </p>

        <form
          onSubmit={handleCreate}
          className="grid grid-cols-1 md:grid-cols-12 gap-3"
        >
          <div className="md:col-span-5">
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="Nhập tiêu đề dự kiến hoặc ý tưởng video..."
              className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2.5 text-sm text-white placeholder:text-zinc-500 focus:border-red-500 focus:outline-none"
            />
          </div>
          <div className="md:col-span-3">
            <input
              type="text"
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              placeholder="Từ khóa chính..."
              className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2.5 text-sm text-white placeholder:text-zinc-500 focus:border-red-500 focus:outline-none"
            />
          </div>
          <div className="md:col-span-2">
            <select
              value={newFormat}
              onChange={(e) => setNewFormat(e.target.value as "long" | "short")}
              className="w-full h-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-200 focus:outline-none"
            >
              <option value="long">Video dài</option>
              <option value="short">YouTube Shorts</option>
            </select>
          </div>
          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={!newTitle.trim()}
              className="w-full h-full inline-flex items-center justify-center gap-1.5 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-50 px-4 py-2.5 text-sm font-semibold text-white transition cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              Thêm mới
            </button>
          </div>
        </form>
      </div>

      {/* Status Filter Bar */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setStatusFilter("all")}
          className={`rounded-xl px-3.5 py-1.5 text-xs font-semibold transition cursor-pointer ${
            statusFilter === "all"
              ? "bg-white text-zinc-950"
              : "bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white"
          }`}
        >
          Tất cả ({ideas.length})
        </button>
        {STATUS_COLUMNS.map((col) => {
          const count = ideas.filter((i) => i.status === col.key).length;
          return (
            <button
              key={col.key}
              onClick={() => setStatusFilter(col.key)}
              className={`rounded-xl px-3.5 py-1.5 text-xs font-semibold transition cursor-pointer ${
                statusFilter === col.key
                  ? "bg-red-600 text-white"
                  : "bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white"
              }`}
            >
              {col.label} ({count})
            </button>
          );
        })}
      </div>

      {/* Ideas Cards */}
      {visibleIdeas.length === 0 ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-12 text-center text-sm text-zinc-400">
          Chưa có ý tưởng nào trong mục này. Hãy bấm &ldquo;Nhân bản chủ đề&rdquo; từ tab Săn Video Outlier hoặc thêm ý tưởng mới ở trên!
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {visibleIdeas.map((idea) => {
            const doneCount = Object.values(idea.checklist).filter(Boolean).length;
            return (
              <div
                key={idea.id}
                className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 flex flex-col justify-between gap-4"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${
                          idea.format === "short"
                            ? "bg-rose-500/20 text-rose-300"
                            : "bg-sky-500/20 text-sky-300"
                        }`}
                      >
                        {idea.format === "short" ? "YouTube Shorts" : "Video dài"}
                      </span>
                      {idea.sourceOutlierScore && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-300">
                          <Flame className="h-3 w-3" />
                          Nguồn {idea.sourceOutlierScore.toFixed(1)}x Outlier
                        </span>
                      )}
                      {idea.targetKeyword && (
                        <span className="rounded-md bg-zinc-800 px-2 py-0.5 text-[11px] text-zinc-300">
                          🎯 {idea.targetKeyword}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <select
                        value={idea.status}
                        onChange={(e) =>
                          onUpdateIdea(idea.id, {
                            status: e.target.value as SavedIdea["status"],
                          })
                        }
                        className="rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1 text-xs text-zinc-200 focus:outline-none"
                      >
                        {STATUS_COLUMNS.map((s) => (
                          <option key={s.key} value={s.key}>
                            {s.label}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => onDeleteIdea(idea.id)}
                        className="text-zinc-500 hover:text-red-400 transition cursor-pointer"
                        title="Xóa ý tưởng"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  <h3 className="text-base font-bold text-white leading-snug mb-1.5">
                    {idea.remakeTitle || idea.title}
                  </h3>

                  {idea.sourceChannelTitle && (
                    <p className="text-xs text-zinc-500 mb-2">
                      Cảm hứng từ kênh:{" "}
                      <span className="text-zinc-300">
                        {idea.sourceChannelTitle}
                      </span>
                    </p>
                  )}

                  {idea.notes && (
                    <p className="rounded-xl bg-zinc-950/70 border border-zinc-800/80 p-3 text-xs text-zinc-300 leading-relaxed mb-3">
                      {idea.notes}
                    </p>
                  )}

                  {/* 5-Step Subscriber Conversion Checklist */}
                  <div className="rounded-xl border border-zinc-800/90 bg-zinc-950/50 p-3.5">
                    <div className="flex items-center justify-between text-xs font-semibold text-zinc-300 mb-2">
                      <span>Checklist Chuyển Đổi Sub Thật</span>
                      <span
                        className={
                          doneCount === 5
                            ? "text-emerald-400"
                            : "text-zinc-400"
                        }
                      >
                        {doneCount}/5 hoàn tất
                      </span>
                    </div>

                    <div className="space-y-1.5">
                      {CHECKLIST_ITEMS.map((chk) => {
                        const checked = idea.checklist[chk.key];
                        return (
                          <button
                            key={chk.key}
                            type="button"
                            onClick={() =>
                              onUpdateIdea(idea.id, {
                                checklist: {
                                  ...idea.checklist,
                                  [chk.key]: !checked,
                                },
                              })
                            }
                            className="w-full flex items-center gap-2 text-left text-xs py-0.5 hover:text-white transition cursor-pointer"
                          >
                            {checked ? (
                              <CheckSquare className="h-4 w-4 text-emerald-400 shrink-0" />
                            ) : (
                              <Square className="h-4 w-4 text-zinc-600 shrink-0" />
                            )}
                            <span
                              className={
                                checked
                                  ? "line-through text-zinc-500"
                                  : "text-zinc-300"
                              }
                            >
                              {chk.label}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
