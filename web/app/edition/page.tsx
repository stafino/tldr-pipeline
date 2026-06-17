import {
  defaultNewsletterId,
  indexBlurbs,
  listAvailableDates,
  loadBlurbs,
  loadNewsletters,
  loadScored,
} from '@/lib/data';
import { canonicalDomain } from '@/lib/utils';
import Nav from '@/components/Nav';
import DatePicker from '@/components/DatePicker';
import EditionStories from '@/components/EditionStories';

export const dynamic = 'force-dynamic';

export default function EditionPage({
  searchParams,
}: {
  searchParams: { date?: string; nl?: string };
}) {
  const dates = listAvailableDates();
  const newsletters = loadNewsletters();
  const nlIds = Object.keys(newsletters);

  if (dates.length === 0) {
    return (
      <main>
        <Nav />
        <div className="px-6 py-10 text-text-mute">No scored runs yet.</div>
      </main>
    );
  }

  // Edition is always day-scoped (you publish one issue per day)
  const requested = searchParams.date && searchParams.date !== 'All' ? searchParams.date : dates[0];
  const selectedDate = dates.includes(requested) ? requested : dates[0];
  const selectedNl = searchParams.nl ?? defaultNewsletterId();
  const nl = newsletters[selectedNl];

  const scored = loadScored(selectedDate);
  const blurbs = loadBlurbs(selectedDate);
  const blurbIdx = indexBlurbs(blurbs);

  // Build approved stories per section (filtering happens client-side because
  // decisions live in localStorage). We pass all candidate stories + sections,
  // and the client component filters by approval.
  const candidates = scored
    .map((s) => {
      const a = s.assignments.find((x) => x.newsletter === selectedNl);
      if (!a) return null;
      return { story: s, assignment: a };
    })
    .filter(Boolean) as { story: any; assignment: any }[];

  return (
    <main>
      <Nav />
      <div className="flex gap-3 px-5 py-3 border-b border-border items-center">
        <DatePicker dates={dates} value={selectedDate} allowAll={false} />
        <label className="inline-flex items-center gap-2 text-[11px] text-text-mute uppercase tracking-[0.06em] font-semibold">
          <span>Newsletter</span>
          <select
            defaultValue={selectedNl}
            onChange={(e) => (window.location.search = `?nl=${e.target.value}&date=${selectedDate}`)}
            className="bg-surface border border-border text-text text-[12px] rounded px-2 py-1 outline-none normal-case font-normal tracking-normal"
          >
            {nlIds.map((id) => (
              <option key={id} value={id}>
                {newsletters[id].brand_name}
              </option>
            ))}
          </select>
        </label>
        {nl && (
          <div className="text-[10px] text-text-mute">
            edition cap: {nl.edition_size} stories · {nl.sections.length} sections
          </div>
        )}
      </div>
      {nl && (
        <EditionStories
          newsletterId={selectedNl}
          newsletterBrand={nl.brand_name}
          editionSize={nl.edition_size}
          sections={nl.sections}
          candidates={candidates.map(({ story, assignment }) => ({
            url: story.story.url,
            title: story.story.title,
            domain: canonicalDomain(story.story.url) || story.story.source,
            sectionId: assignment.section_id,
            score: Math.round(assignment.score),
            blurb: blurbIdx.get(`${story.story.url}||${selectedNl}`)?.blurb ?? '',
            minute_read: blurbIdx.get(`${story.story.url}||${selectedNl}`)?.minute_read ?? 5,
          }))}
          date={selectedDate}
        />
      )}
    </main>
  );
}
