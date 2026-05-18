"use client";

import { useEffect, useState } from "react";
import type { RecommendationResponse } from "@/lib/types";
import { ArrowRightIcon, FlameIcon, SearchIcon, SparkIcon } from "./Icon";
import { FilterChips } from "./FilterChips";
import { ListingCard } from "./ListingCard";

const SAMPLES = [
  { label: "Toronto · 1BR · pets · subway",
    q: "Toronto, $2500/mo max, 1 bedroom, pet-friendly, walkable to a subway station" },
  { label: "Vancouver · 2BR · seawall",
    q: "Moving to Vancouver, $3500 budget, 2 bedrooms, want a quiet neighbourhood near the seawall" },
  { label: "Montreal · studio · Plateau",
    q: "Furnished studio in Montreal under $1800, heat and internet included, near Plateau" },
  { label: "Calgary · dog · C-Train",
    q: "Calgary, $2000, 2 bed, dog allowed, close to a C-Train station, 6-month lease" },
];

const LOADING_STAGES = [
  "Understanding your request",
  "Filtering 4,400 listings",
  "Ranking by neighbourhood fit",
  "Writing your recommendation",
];

type Props = {
  onResult: (result: RecommendationResponse | null) => void;
  selectedId: number | null;
  hoveredId: number | null;
  onHover: (id: number | null) => void;
  onSelect: (id: number) => void;
};

export function QueryPanel({ onResult, selectedId, hoveredId, onHover, onSelect }: Props) {
  const [query, setQuery] = useState(SAMPLES[0].q);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState(0);
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Cycle the loading stage so the spinner shows visible progress
  useEffect(() => {
    if (!loading) return;
    const id = setInterval(() => {
      setStage((s) => Math.min(s + 1, LOADING_STAGES.length - 1));
    }, 1400);
    return () => clearInterval(id);
  }, [loading]);

  async function run(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setStage(0);
    setError(null);
    setResult(null);
    onResult(null);
    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: RecommendationResponse = await res.json();
      setResult(data);
      onResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      onResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <aside className="flex h-full w-[500px] shrink-0 flex-col border-r border-line bg-card">
      {/* Header */}
      <header className="border-b border-line px-6 pb-5 pt-6">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-ink text-white">
            <FlameIcon size={15} />
          </span>
          <div className="leading-tight">
            <div className="font-semibold tracking-tight text-ink">EZrelocate</div>
            <div className="text-[11px] text-ink-muted">
              Canadian rentals · hybrid retrieval + Claude
            </div>
          </div>
        </div>
      </header>

      {/* Search */}
      <div className="border-b border-line px-6 py-4">
        <div className="relative">
          <SearchIcon
            size={15}
            className="pointer-events-none absolute left-3 top-3 text-ink-muted"
          />
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") run(query);
            }}
            rows={3}
            placeholder='e.g. "Toronto, 1 bedroom, pet-friendly, near a subway, under $2500"'
            className="w-full resize-none rounded-xl border border-line bg-white py-2.5 pl-9 pr-3 text-[13px] leading-relaxed text-ink placeholder:text-ink-muted/70 focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-100"
          />
        </div>
        <button
          onClick={() => run(query)}
          disabled={loading || !query.trim()}
          className="mt-2 inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-ink px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-all hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {loading ? "Searching…" : (
            <>
              Find rentals <ArrowRightIcon size={14} />
            </>
          )}
        </button>
        <div className="mt-1 text-right text-[10px] text-ink-muted">⌘↵ to search</div>

        {/* Sample chips */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {SAMPLES.map((s) => (
            <button
              key={s.q}
              onClick={() => { setQuery(s.q); run(s.q); }}
              className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-2.5 py-1 text-[11px] text-ink-2 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
            >
              <SparkIcon size={11} className="text-brand-600" />
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <LoadingState stage={stage} />
        )}

        {error && !loading && (
          <div className="mx-6 mt-5 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {error}
          </div>
        )}

        {!loading && result && (
          <div className="px-6 pb-8 pt-5">
            <FilterChips parsed={result.parsed} />

            <section className="rl-fade-up mt-4 rounded-xl bg-ink/95 px-4 py-3.5 text-[13px] leading-relaxed text-white shadow-(--shadow-card)">
              {result.reasoning}
            </section>

            {result.listings.length > 0 ? (
              <div className="mt-5">
                <div className="mb-2 flex items-center justify-between text-[11px] uppercase tracking-wider text-ink-muted">
                  <span>Top matches</span>
                  <span>{result.listings.length} of 4,400+</span>
                </div>
                <ol className="space-y-2.5">
                  {result.listings.map((l, i) => (
                    <div key={l.id} className="rl-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
                      <ListingCard
                        listing={l}
                        rank={i + 1}
                        selected={selectedId === l.id}
                        onHover={onHover}
                        onSelect={onSelect}
                      />
                    </div>
                  ))}
                </ol>
              </div>
            ) : (
              <div className="mt-5 rounded-xl border border-line bg-slate-50/50 px-4 py-6 text-center text-xs text-ink-muted">
                No matches. Try widening price or bedroom count.
              </div>
            )}
          </div>
        )}

        {!loading && !result && !error && <EmptyState />}
      </div>
    </aside>
  );
}

function LoadingState({ stage }: { stage: number }) {
  return (
    <div className="px-6 pt-8">
      <div className="rl-pulse mb-4 inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-[11px] text-ink-2">
        <span className="block h-1 w-1 rounded-full bg-brand-600" />
        <span className="block h-1 w-1 rounded-full bg-brand-600" />
        <span className="block h-1 w-1 rounded-full bg-brand-600" />
      </div>
      <ul className="space-y-2 text-sm">
        {LOADING_STAGES.map((s, i) => (
          <li
            key={s}
            className={
              "flex items-center gap-2 transition-opacity duration-300 " +
              (i < stage ? "text-ink-muted line-through opacity-60"
                : i === stage ? "text-ink"
                : "text-ink-muted/60")
            }
          >
            <span
              className={
                "grid h-4 w-4 place-items-center rounded-full text-[9px] " +
                (i < stage
                  ? "bg-brand-100 text-brand-700"
                  : i === stage
                    ? "bg-ink text-white"
                    : "border border-line text-ink-muted")
              }
            >
              {i < stage ? "✓" : i + 1}
            </span>
            {s}
          </li>
        ))}
      </ul>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="px-6 pt-10">
      <div className="rounded-xl border border-dashed border-line bg-white/60 px-4 py-8 text-center">
        <div className="mx-auto grid h-9 w-9 place-items-center rounded-full bg-brand-50 text-brand-700">
          <SparkIcon size={16} />
        </div>
        <h3 className="mt-3 text-sm font-semibold text-ink">Ask in plain English</h3>
        <p className="mx-auto mt-1 max-w-xs text-xs leading-relaxed text-ink-muted">
          Describe what matters — neighbourhood vibe, commute, budget, pets. Claude turns it
          into filters; pgvector ranks 4,400+ listings; PostGIS handles location.
        </p>
        <p className="mt-3 text-[10px] uppercase tracking-wider text-ink-muted/80">
          Try a sample query above
        </p>
      </div>
    </div>
  );
}
