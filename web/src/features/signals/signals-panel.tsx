import { Panel } from "@/components/layout/panel";
import { PanelModuleOff } from "@/components/layout/states";

export function SignalsPanel() {
  return (
    <Panel title="Signals" className="shrink-0">
      <PanelModuleOff
        title="Signal engine not enabled (Phase 4)"
        hint="Trend and signal rows will appear here once the signal engine is approved and enabled."
      />
    </Panel>
  );
}
