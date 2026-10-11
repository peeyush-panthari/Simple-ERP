/** Dual-month date-range popover (click a start day, then an end day; Done commits). */
import * as Popover from "@radix-ui/react-popover";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { ActionButton } from "@/components/erp/ui";
import { monthGrid, monthLabel, shiftMonth, shortDate, tagRange } from "@/lib/calendar";
import { todayIso } from "@/lib/format";
import { cn } from "@/lib/utils";

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

function Month({ anchor, draftFrom, draftTo, onPick, prev, next }: { anchor: string; draftFrom: string; draftTo: string; onPick: (iso: string) => void; prev?: () => void; next?: () => void }) {
  const cells = tagRange(monthGrid(anchor), draftFrom, draftTo);
  return (
    <div className="flex flex-col items-start gap-2">
      <div className="flex w-full items-center justify-between">
        {prev ? <button type="button" className="calendar-nav-btn" onClick={prev} aria-label="Previous month"><ChevronLeft size={16} /></button> : <span className="calendar-nav-btn" />}
        <span className="text-sm font-bold">{monthLabel(anchor)}</span>
        {next ? <button type="button" className="calendar-nav-btn" onClick={next} aria-label="Next month"><ChevronRight size={16} /></button> : <span className="calendar-nav-btn" />}
      </div>
      <div className="grid grid-cols-7">
        {WEEKDAYS.map((w) => <span key={w} className="calendar-weekday">{w}</span>)}
        {cells.map((c, i) =>
          c.inMonth ? (
            <button key={i} type="button" onClick={() => onPick(c.iso)} className={cn("calendar-day", (c.isStart || c.isEnd) && "calendar-day-selected", !(c.isStart || c.isEnd) && c.inRange && "calendar-day-in-range")}>
              {c.day}
            </button>
          ) : (
            <span key={i} className="calendar-day calendar-day-empty" />
          ),
        )}
      </div>
    </div>
  );
}

/** `from`/`to` are the applied filter (ISO, "" = none); `onApply` fires on Done (or Clear with two empty strings). */
export function DateRangePicker({ from, to, onApply }: { from: string; to: string; onApply: (from: string, to: string) => void }) {
  const [open, setOpen] = useState(false);
  const [draftFrom, setDraftFrom] = useState("");
  const [draftTo, setDraftTo] = useState("");
  const [anchor, setAnchor] = useState("");

  // Re-seed from what's applied on every open, so dismissing without Done never leaks a half-made pick.
  const changeOpen = (o: boolean) => {
    setOpen(o);
    if (o) {
      setDraftFrom(from);
      setDraftTo(to);
      setAnchor(from ? from.slice(0, 7) : todayIso().slice(0, 7));
    }
  };
  const pick = (iso: string) => {
    if (!draftFrom || draftTo) {
      setDraftFrom(iso);
      setDraftTo("");
      return;
    }
    const [a, b] = iso < draftFrom ? [iso, draftFrom] : [draftFrom, iso];
    setDraftFrom(a);
    setDraftTo(b);
  };
  const label = !from ? "Production date range" : !to || to === from ? shortDate(from) : `${shortDate(from)} - ${shortDate(to)}`;
  const current = anchor || todayIso().slice(0, 7);

  return (
    <Popover.Root open={open} onOpenChange={changeOpen}>
      <Popover.Trigger asChild>
        <button type="button" className="filter-select flex items-center gap-2">
          <CalendarDays size={14} />
          <span>{label}</span>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="popover-content" style={{ padding: "1rem", width: "auto", maxWidth: "calc(100vw - 2rem)" }} align="start" sideOffset={4}>
          <div className="flex flex-col items-start gap-3">
            <div className="desktop-only">
              <div className="flex items-start gap-5">
                <Month anchor={current} draftFrom={draftFrom} draftTo={draftTo} onPick={pick} prev={() => setAnchor(shiftMonth(current, -1))} />
                <Month anchor={shiftMonth(current, 1)} draftFrom={draftFrom} draftTo={draftTo} onPick={pick} next={() => setAnchor(shiftMonth(current, 1))} />
              </div>
            </div>
            <div className="mobile-only">
              <Month anchor={current} draftFrom={draftFrom} draftTo={draftTo} onPick={pick} prev={() => setAnchor(shiftMonth(current, -1))} next={() => setAnchor(shiftMonth(current, 1))} />
            </div>
            <div className="flex w-full items-center">
              {from && (
                <ActionButton size="sm" tone="ghost" onClick={() => { setOpen(false); onApply("", ""); }}>Clear</ActionButton>
              )}
              <div className="flex-1" />
              <ActionButton size="sm" onClick={() => { setOpen(false); onApply(draftFrom, draftTo); }}>Done</ActionButton>
            </div>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
