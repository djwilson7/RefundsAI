"use client";

import { useApplicationHelpLayer } from "./application-help-layer";
import { HelpButton } from "./help-button";

export function HelpTriggerButton({ inline = false }: { inline?: boolean }) {
  const { isAvailable, isOpen, panelId, toggle } = useApplicationHelpLayer();

  if (!isAvailable) {
    return null;
  }

  return <HelpButton inline={inline} isOpen={isOpen} onClick={toggle} panelId={panelId} />;
}
