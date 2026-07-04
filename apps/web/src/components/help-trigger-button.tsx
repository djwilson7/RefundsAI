"use client";

import { useApplicationHelpLayer } from "./application-help-layer";
import { HelpButton } from "./help-button";

export function HelpTriggerButton() {
  const { isAvailable, isOpen, panelId, toggle } = useApplicationHelpLayer();

  if (!isAvailable) {
    return null;
  }

  return <HelpButton isOpen={isOpen} onClick={toggle} panelId={panelId} />;
}
