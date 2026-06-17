import {
  defaultNewsletterId,
  filterBlurbsByStoryUrls,
  filterByPublishedDate,
  indexBlurbs,
  listAvailableDates,
  listPublishedDates,
  loadBlurbsAll,
  loadNewsletters,
  loadScoredAll,
  topPerSection,
} from '@/lib/data';
import { shortDate } from '@/lib/utils';
import Nav from '@/components/Nav';
import DatePicker from '@/components/DatePicker';
import NewsletterPicker from '@/components/NewsletterPicker';
import StoryRow from '@/components/StoryRow';
import DetailPane from '@/components/DetailPane';
import CurateNewsletterView from '@/components/CurateNewsletterView';

export const dynamic = 'force-dynamic'; // always read fresh files

interface Search {
  date?: string;
  nl?: string;
  story?: string;
  nl_detail?: string;
}

export default function Page({ searchParams }: { searchParams: Search }) {
  const scrapeDates = listAvailableDates();
  const dates = listPublishedDates();
  const newsletters = loadNewsletters();
  const nlIds = Object.keys(newsletters);

  if (dates.length === 0) {
    return (
      <main>
        <Nav />
        <div className="px-6 py-10 text-text-mute">
          No scored runs yet. Run <code className="text-text font-mono">tldr refresh</code> first.
        </div>
      </main>
    );
  }

  const selectedDate = searchParams.date ?? dates[0];
  const selectedNl = searchParams.nl ?? defaultNewsletterId();

  // Always load across every scrape file, then filter by the story's UTC
  // publish date — so "Filter by date" means *published on this day*, not
  // "scraped on this day". A story published Jun 16 that the cron fetched
  // on Jun 17 stays under Jun 16.
  const scoredAll = loadScoredAll(scrapeDates);
  const blurbsAll = loadBlurbsAll(scrapeDates);
  let scored: any[];
  let blurbs: any[];
  if (selectedDate === 'All') {
    scored = scoredAll;
    blurbs = blurbsAll;
  } else {
    scored = filterByPublishedDate(scoredAll, selectedDate);
    const urls = new Set(scored.map((s) => s.story.url));
    blurbs = filterBlurbsByStoryUrls(blurbsAll, urls);
  }
  const blurbIdx = indexBlurbs(blurbs);

  // Compute counts per newsletter
  const perNlCounts: Record<string, number> = {};
  for (const id of nlIds) perNlCounts[id] = 0;
  for (const s of scored) {
    const nlsByThis = new Set<string>();
    for (const a of s.assignments) {
      if (a.newsletter in perNlCounts && !nlsByThis.has(a.newsletter)) {
        nlsByThis.add(a.newsletter);
        perNlCounts[a.newsletter] += 1;
      }
    }
  }

  // Pipeline pills (just counts in the data we loaded)
  const blurbedCount = blurbs.length;
  const scoredCount = scored.length;

  const pills = (
    <div className="text-[11px] text-text-dim">
      scored <b className="text-text font-semibold">{scoredCount}</b> · blurbed{' '}
      <b className="text-text font-semibold">{blurbedCount}</b>
    </div>
  );

  // Build the selected newsletter view
  const targetYear = selectedDate === 'All' ? new Date().getFullYear() : Number(selectedDate.slice(0, 4));

  const brandNames: Record<string, string> = {};
  for (const id of nlIds) brandNames[id] = newsletters[id].brand_name;

  // CURATE: rail = newsletters, middle = section-grouped stories, right = detail pane
  const isBacklog = selectedNl === '__backlog__';

  let middleContent: React.ReactNode;
  let selectedStory: any = null;
  let detailNewsletter: any = null;
  let selectedBlurb: any = undefined;

  if (isBacklog) {
    // Backlog: every scored story in the loaded data
    const sorted = [...scored].sort((a, b) => b.score - a.score);
    const headerMeta =
      selectedDate === 'All'
        ? `${sorted.length} stories across all scrape dates`
        : `${sorted.length} stories scraped on ${selectedDate}`;

    middleContent = (
      <div>
        <SectionHeader title="★ Backlog" meta={headerMeta} />
        {sorted.length === 0 ? (
          <Empty>No scored stories for this date.</Empty>
        ) : (
          sorted.map((s, i) => {
            const primary = s.assignments[0]; // already-sorted by primary
            if (!primary) return null;
            const detailNlId = searchParams.nl_detail ?? primary.newsletter;
            const sec = newsletters[primary.newsletter]?.sections.find(
              (x: any) => x.id === primary.section_id,
            );
            const b = blurbIdx.get(`${s.story.url}||${primary.newsletter}`);
            return (
              <StoryRow
                key={s.story.url}
                story={s}
                newsletterId={'__backlog__'}
                detailNewsletterId={primary.newsletter}
                rank={i + 1}
                blurb={b}
                selected={searchParams.story === s.story.url && (searchParams.nl_detail ?? primary.newsletter) === detailNlId}
                sectionMin={sec?.min_words ?? 40}
                sectionMax={sec?.max_words ?? 80}
                publishedShort={shortDate(s.story.published_at, targetYear)}
              />
            );
          })
        )}
      </div>
    );
  } else {
    const nl = newsletters[selectedNl];
    if (nl) {
      // Flatten every story assigned to this newsletter (no per-section cap).
      // CurateNewsletterView handles the "Accepted" group + per-section top-N
      // client-side so accepted stories are pinned to the top regardless of
      // whether they made the section cap.
      const candidates = scored
        .map((s: any) => {
          const a = s.assignments.find((x: any) => x.newsletter === selectedNl);
          if (!a) return null;
          return {
            story: s,
            blurb: blurbIdx.get(`${s.story.url}||${selectedNl}`) ?? null,
            sectionId: a.section_id,
            scoreInSection: a.score,
            publishedShort: shortDate(s.story.published_at, targetYear),
          };
        })
        .filter(Boolean) as any[];
      middleContent = (
        <CurateNewsletterView
          newsletterId={selectedNl}
          newsletterBrand={nl.brand_name}
          sections={nl.sections as any}
          candidates={candidates}
          selectedDate={selectedDate}
          selectedStoryUrl={searchParams.story}
          selectedDetailNlId={searchParams.nl_detail ?? selectedNl}
        />
      );
    }
  }

  // Find the selected story for the detail pane
  if (searchParams.story) {
    selectedStory = scored.find((s) => s.story.url === searchParams.story) ?? null;
    const detailId = searchParams.nl_detail ?? (selectedStory?.assignments[0]?.newsletter ?? selectedNl);
    detailNewsletter = newsletters[detailId] ?? null;
    if (selectedStory && detailNewsletter) {
      selectedBlurb = blurbIdx.get(`${selectedStory.story.url}||${detailNewsletter.id}`);
    }
  }

  return (
    <main>
      <Nav pipelinePills={pills} />
      <div className="flex gap-3 px-5 py-3 border-b border-border items-center">
        <DatePicker dates={dates} value={selectedDate} />
        <div className="text-[10px] text-text-mute">{nlIds.length} newsletters · {dates.length} dates available</div>
      </div>
      <div className="grid grid-cols-[220px_minmax(0,_3fr)_minmax(0,_2fr)] gap-4 px-5 py-3">
        <div className="border-r border-border pr-3 sticky top-0 self-start max-h-screen overflow-y-auto scroll-y">
          <NewsletterPicker
            ids={nlIds}
            brandNames={brandNames}
            value={selectedNl}
            includeBacklog
          />
        </div>
        <div className="overflow-y-auto scroll-y">{middleContent}</div>
        <div className="border-l border-border pl-4 sticky top-0 self-start max-h-screen overflow-y-auto scroll-y">
          <DetailPane story={selectedStory} newsletter={detailNewsletter} blurb={selectedBlurb} />
        </div>
      </div>
    </main>
  );
}

function SectionHeader({ title, meta }: { title: string; meta: string }) {
  return (
    <div className="flex items-baseline gap-3 pb-3 mb-1 border-b border-border-strong">
      <h2 className="text-[13px] font-bold tracking-tight m-0">{title}</h2>
      <span className="text-[11px] text-text-mute ml-auto">{meta}</span>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="text-text-mute text-[12px] py-5 px-1">{children}</div>;
}
