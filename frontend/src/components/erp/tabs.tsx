import * as RadixTabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

/** Radix Tabs with the app's tab recipe (theme.css .tabs-*). */
export function Tabs({ tabs, value, onValueChange, defaultValue }: { tabs: { value: string; label: ReactNode; content: ReactNode }[]; value?: string; onValueChange?: (v: string) => void; defaultValue?: string }) {
  return (
    <RadixTabs.Root value={value} onValueChange={onValueChange} defaultValue={defaultValue ?? tabs[0]?.value} className="w-full min-w-0">
      <RadixTabs.List className="tabs-list">
        {tabs.map((t) => (
          <RadixTabs.Trigger key={t.value} value={t.value} className="tabs-trigger">
            {t.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {tabs.map((t) => (
        <RadixTabs.Content key={t.value} value={t.value} className="tabs-content">
          {t.content}
        </RadixTabs.Content>
      ))}
    </RadixTabs.Root>
  );
}
