import { useEffect } from "react";
import { useApp, type Panel } from "../AppState";
import AvailabilityGrid from "./AvailabilityGrid";
import MusicianForm from "./MusicianForm";
import MusicianPanel from "./MusicianPanel";
import ShowForm from "./ShowForm";
import ShowPanel from "./ShowPanel";

function render(panel: Panel) {
  switch (panel.kind) {
    case "show": return <ShowPanel showId={panel.id} />;
    case "musician": return <MusicianPanel musicianId={panel.id} />;
    case "addShow": return <ShowForm initialDate={panel.date} />;
    case "editShow": return <ShowForm showId={panel.id} />;
    case "musicianForm": return <MusicianForm musicianId={panel.id} />;
    case "availability": return <AvailabilityGrid musicianId={panel.id} />;
  }
}

/** One slide-over on the right; panels stack, so "back" returns to where you drilled in from. */
export default function PanelHost() {
  const { panels, backPanel, closePanels } = useApp();
  const top = panels[panels.length - 1];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closePanels(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closePanels]);

  if (!top) return null;
  return (
    <>
      <div className="panel-scrim" onClick={closePanels} />
      <aside className="side-panel" role="dialog" aria-modal="true">
        <div className="panel-nav">
          {panels.length > 1 ? <button className="link-button" onClick={backPanel}>← Back</button> : <span />}
          <button className="link-button" onClick={closePanels} aria-label="Close">Close ✕</button>
        </div>
        <div key={panels.length}>{render(top)}</div>
      </aside>
    </>
  );
}
