import { Panel } from "@/components/layout/panel";
import { PanelModuleOff } from "@/components/layout/states";

export function NewsPanel() {
  return (
    <Panel title="News" className="flex-1">
      <PanelModuleOff
        title="News agent not enabled (Phase 3)"
        hint="Headlines from the configured RSS sources will appear here once the news agent ships."
      />
    </Panel>
  );
}
